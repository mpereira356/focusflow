from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Task, TaskSession

tasks_bp = Blueprint('tasks', __name__)

TASK_COLORS = ['#4A9EFF', '#7C3AED', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#06B6D4', '#84CC16']
TASK_ICONS = ['timer', 'book', 'code', 'fitness_center', 'music_note', 'brush', 'science', 'language', 'task_alt']


def _build_task_payload(task, session):
    duration_seconds = task.target_seconds
    progress = 100 if session.status == 'completed' else (
        min(100, int((session.time_completed / duration_seconds) * 100)) if duration_seconds > 0 else 0
    )
    return {
        'task': task,
        'session': session,
        'progress': progress,
        'duration_seconds': duration_seconds,
    }


@tasks_bp.route('/')
@login_required
def list_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).order_by(Task.created_at.desc()).all()
    task_data = []
    for task in tasks:
        task_data.append(_build_task_payload(task, task.get_or_create_today_session()))
    return render_template('tasks/list.html', task_data=task_data, colors=TASK_COLORS, icons=TASK_ICONS)


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        form_data = _parse_task_form(request)
        if form_data['error']:
            return render_template(
                'tasks/form.html',
                error=form_data['error'],
                form_data=form_data['values'],
                colors=TASK_COLORS,
                icons=TASK_ICONS,
            )

        task = Task(user_id=current_user.id, **form_data['values'])
        db.session.add(task)
        db.session.commit()
        return redirect(url_for('main.dashboard'))

    return render_template('tasks/form.html', colors=TASK_COLORS, icons=TASK_ICONS)


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        form_data = _parse_task_form(request)
        if form_data['error']:
            return render_template(
                'tasks/form.html',
                task=task,
                error=form_data['error'],
                form_data=form_data['values'],
                colors=TASK_COLORS,
                icons=TASK_ICONS,
            )

        for field, value in form_data['values'].items():
            setattr(task, field, value)
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


@tasks_bp.route('/<int:task_id>/check', methods=['POST'])
@login_required
def toggle_check_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if not task.is_check_task:
        return redirect(request.referrer or url_for('tasks.list_tasks'))

    session = task.get_or_create_today_session()
    mark_done = request.form.get('done', '1') == '1'

    if mark_done:
        now = datetime.utcnow()
        session.time_completed = 1
        session.status = 'completed'
        session.started_at = session.started_at or now
        session.ended_at = now
        session.last_tick = None
    else:
        session.time_completed = 0
        session.status = 'pending'
        session.started_at = None
        session.ended_at = None
        session.last_tick = None

    db.session.commit()
    return redirect(request.referrer or url_for('tasks.list_tasks'))


@tasks_bp.route('/api/timer/start/<int:task_id>', methods=['POST'])
@login_required
def timer_start(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if task.is_check_task:
        return jsonify({'error': 'Esta tarefa e concluida manualmente por check.'}), 400

    today = date.today()
    running = (
        TaskSession.query
        .join(Task)
        .filter(
            Task.user_id == current_user.id,
            TaskSession.date == today,
            TaskSession.status == 'running',
        )
        .all()
    )
    for session in running:
        if session.task_id != task_id:
            _sync_elapsed(session)
            session.status = 'paused'
    db.session.flush()

    session = task.get_or_create_today_session()
    if session.status == 'completed':
        return jsonify({'error': 'Tarefa ja concluida hoje.'}), 400

    now = datetime.utcnow()
    if not session.started_at:
        session.started_at = now
    session.status = 'running'
    session.last_tick = now
    db.session.commit()

    return jsonify({
        'status': 'running',
        'session': session.to_dict(),
        'duration_seconds': task.target_seconds,
    })


@tasks_bp.route('/api/timer/pause/<int:task_id>', methods=['POST'])
@login_required
def timer_pause(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if task.is_check_task:
        return jsonify({'error': 'Esta tarefa nao usa timer.'}), 400

    session = task.get_today_session()
    if not session or session.status != 'running':
        return jsonify({'error': 'Timer nao esta rodando.'}), 400

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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    if task.is_check_task:
        return jsonify({'error': 'Esta tarefa nao usa timer.'}), 400

    session = task.get_today_session()
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.get_json(silent=True) or {}
    elapsed = data.get('elapsed_seconds')

    if elapsed is not None:
        duration_seconds = task.target_seconds
        session.time_completed = min(int(elapsed), duration_seconds)
        session.last_tick = datetime.utcnow()

        if session.time_completed >= duration_seconds:
            session.status = 'completed'
            session.ended_at = datetime.utcnow()

        db.session.commit()

    return jsonify({
        'status': session.status,
        'session': session.to_dict(),
        'duration_seconds': task.target_seconds,
    })


@tasks_bp.route('/api/tasks/state', methods=['GET'])
@login_required
def tasks_state():
    tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).all()
    result = []
    for task in tasks:
        session = task.get_or_create_today_session()
        result.append({
            'task_id': task.id,
            'task_type': task.task_type,
            'duration_seconds': task.target_seconds,
            'session': session.to_dict(),
        })
    return jsonify(result)


def _parse_task_form(req):
    name = req.form.get('name', '').strip()
    description = req.form.get('description', '').strip()
    task_type = req.form.get('task_type', 'timer')
    duration_raw = req.form.get('duration_minutes', 25)
    is_recurring = req.form.get('is_recurring') == 'on'
    color = req.form.get('color', '#4A9EFF')
    icon = req.form.get('icon', 'timer')

    values = {
        'name': name,
        'description': description,
        'task_type': task_type if task_type in {'timer', 'check'} else 'timer',
        'duration_minutes': 25,
        'is_recurring': is_recurring,
        'color': color,
        'icon': icon,
    }

    if not name:
        return {'error': 'Nome e obrigatorio.', 'values': values}

    if values['task_type'] == 'timer':
        try:
            duration = int(duration_raw)
            if duration < 1 or duration > 480:
                raise ValueError
        except (ValueError, TypeError):
            values['duration_minutes'] = duration_raw
            return {'error': 'Duracao deve ser entre 1 e 480 minutos.', 'values': values}
        values['duration_minutes'] = duration
    else:
        values['duration_minutes'] = 0
        if icon == 'timer':
            values['icon'] = 'task_alt'

    return {'error': None, 'values': values}


def _sync_elapsed(session):
    if session.status == 'running' and session.last_tick:
        now = datetime.utcnow()
        delta = (now - session.last_tick).total_seconds()
        duration_seconds = session.task.target_seconds
        session.time_completed = min(int(session.time_completed + delta), duration_seconds)
        session.last_tick = now
