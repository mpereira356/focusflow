from flask import render_template, redirect, url_for, request, jsonify, Blueprint
from flask_login import login_required, current_user
from datetime import datetime, date
from app import db
from app.models import Task, TaskSession

tasks_bp = Blueprint('tasks', __name__)

TASK_COLORS = ['#4A9EFF', '#7C3AED', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#06B6D4', '#84CC16']
TASK_ICONS  = ['timer', 'book', 'code', 'fitness_center', 'music_note', 'brush', 'science', 'language']


@tasks_bp.route('/')
@login_required
def list_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).order_by(Task.created_at.desc()).all()
    task_data = []
    for task in tasks:
        session = task.get_or_create_today_session()
        duration_seconds = task.duration_minutes * 60
        progress = min(100, int((session.time_completed / duration_seconds) * 100)) if duration_seconds > 0 else 0
        task_data.append({'task': task, 'session': session, 'progress': progress})
    return render_template('tasks/list.html', task_data=task_data, colors=TASK_COLORS, icons=TASK_ICONS)


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        duration = request.form.get('duration_minutes', 25)
        is_recurring = request.form.get('is_recurring') == 'on'
        color = request.form.get('color', '#4A9EFF')
        icon = request.form.get('icon', 'timer')

        if not name:
            return render_template('tasks/form.html', error='Nome é obrigatório.', colors=TASK_COLORS, icons=TASK_ICONS)

        try:
            duration = int(duration)
            if duration < 1 or duration > 480:
                raise ValueError
        except (ValueError, TypeError):
            return render_template('tasks/form.html', error='Duração deve ser entre 1 e 480 minutos.', colors=TASK_COLORS, icons=TASK_ICONS)

        task = Task(
            user_id=current_user.id,
            name=name,
            description=description,
            duration_minutes=duration,
            is_recurring=is_recurring,
            color=color,
            icon=icon
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for('main.dashboard'))

    return render_template('tasks/form.html', colors=TASK_COLORS, icons=TASK_ICONS)


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        duration = request.form.get('duration_minutes', 25)
        is_recurring = request.form.get('is_recurring') == 'on'
        color = request.form.get('color', '#4A9EFF')
        icon = request.form.get('icon', 'timer')

        if not name:
            return render_template('tasks/form.html', task=task, error='Nome é obrigatório.', colors=TASK_COLORS, icons=TASK_ICONS)

        try:
            duration = int(duration)
        except (ValueError, TypeError):
            duration = 25

        task.name = name
        task.description = description
        task.duration_minutes = duration
        task.is_recurring = is_recurring
        task.color = color
        task.icon = icon
        db.session.commit()
        return redirect(url_for('tasks.list_tasks'))

    return render_template('tasks/form.html', task=task, colors=TASK_COLORS, icons=TASK_ICONS)


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('tasks.list_tasks'))


# ─── Timer API ────────────────────────────────────────────────────────────────

@tasks_bp.route('/api/timer/start/<int:task_id>', methods=['POST'])
@login_required
def timer_start(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    # Pause all other running sessions today
    today = date.today()
    running = (TaskSession.query
               .join(Task)
               .filter(Task.user_id == current_user.id,
                       TaskSession.date == today,
                       TaskSession.status == 'running')
               .all())
    for s in running:
        if s.task_id != task_id:
            _sync_elapsed(s)
            s.status = 'paused'
    db.session.flush()

    session = task.get_or_create_today_session()
    if session.status == 'completed':
        return jsonify({'error': 'Tarefa já concluída hoje.'}), 400

    now = datetime.utcnow()
    if not session.started_at:
        session.started_at = now
    session.status = 'running'
    session.last_tick = now
    db.session.commit()

    return jsonify({'status': 'running', 'session': session.to_dict(),
                    'duration_seconds': task.duration_minutes * 60})


@tasks_bp.route('/api/timer/pause/<int:task_id>', methods=['POST'])
@login_required
def timer_pause(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    session = task.get_today_session()
    if not session or session.status != 'running':
        return jsonify({'error': 'Timer não está rodando.'}), 400

    _sync_elapsed(session)
    session.status = 'paused'
    db.session.commit()
    return jsonify({'status': 'paused', 'session': session.to_dict()})


@tasks_bp.route('/api/timer/reset/<int:task_id>', methods=['POST'])
@login_required
def timer_reset(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    session = task.get_today_session()
    if not session:
        return jsonify({'status': 'ok'})

    session.time_completed = 0
    session.status = 'pending'
    session.started_at = None
    session.ended_at = None
    session.last_tick = None
    db.session.commit()
    return jsonify({'status': 'reset', 'session': session.to_dict()})


@tasks_bp.route('/api/timer/sync/<int:task_id>', methods=['POST'])
@login_required
def timer_sync(task_id):
    """Receive elapsed seconds from client and update DB."""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    session = task.get_today_session()
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.get_json(silent=True) or {}
    elapsed = data.get('elapsed_seconds', None)

    if elapsed is not None:
        duration_seconds = task.duration_minutes * 60
        session.time_completed = min(int(elapsed), duration_seconds)
        session.last_tick = datetime.utcnow()

        if session.time_completed >= duration_seconds:
            session.status = 'completed'
            session.ended_at = datetime.utcnow()

        db.session.commit()

    return jsonify({'status': session.status, 'session': session.to_dict(),
                    'duration_seconds': task.duration_minutes * 60})


@tasks_bp.route('/api/tasks/state', methods=['GET'])
@login_required
def tasks_state():
    """Return today's state for all user tasks."""
    today = date.today()
    tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).all()
    result = []
    for task in tasks:
        session = task.get_or_create_today_session()
        result.append({
            'task_id': task.id,
            'duration_seconds': task.duration_minutes * 60,
            'session': session.to_dict()
        })
    return jsonify(result)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sync_elapsed(session):
    """Calculate how many seconds passed since last_tick and add to time_completed."""
    if session.status == 'running' and session.last_tick:
        now = datetime.utcnow()
        delta = (now - session.last_tick).total_seconds()
        task = session.task
        duration_seconds = task.duration_minutes * 60
        session.time_completed = min(int(session.time_completed + delta), duration_seconds)
        session.last_tick = now
