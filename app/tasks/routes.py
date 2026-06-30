import json
import os
import uuid
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.models import Task, TaskSession

tasks_bp = Blueprint('tasks', __name__)

TASK_COLORS = ['#4A9EFF', '#7C3AED', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#06B6D4', '#84CC16', '#14B8A6', '#F97316']
TASK_ICONS = [
    'timer', 'book', 'code', 'fitness_center', 'music_note', 'brush', 'science', 'language', 'task_alt', 'work',
    'school', 'terminal', 'edit_note', 'menu_book', 'payments', 'shopping_cart', 'medical_services', 'campaign',
    'event', 'groups', 'calculate', 'psychology', 'travel_explore', 'inventory_2', 'rocket_launch', 'checklist_rtl',
]
PRIORITY_OPTIONS = [
    {'value': 'low', 'label': 'Baixa', 'color': '#10B981'},
    {'value': 'medium', 'label': 'Media', 'color': '#F59E0B'},
    {'value': 'high', 'label': 'Alta', 'color': '#FB923C'},
    {'value': 'urgent', 'label': 'Urgente', 'color': '#EF4444'},
]
REMINDER_OPTIONS = [
    {'value': '', 'label': 'Sem lembrete'},
    {'value': '0', 'label': 'No horario'},
    {'value': '5', 'label': '5 minutos antes'},
    {'value': '10', 'label': '10 minutos antes'},
    {'value': '30', 'label': '30 minutos antes'},
    {'value': '60', 'label': '1 hora antes'},
    {'value': '1440', 'label': '1 dia antes'},
]
RECURRENCE_OPTIONS = [
    {'value': 'none', 'label': 'Nao repetir'},
    {'value': 'daily', 'label': 'Diariamente'},
    {'value': 'weekdays', 'label': 'Segunda a Sexta'},
    {'value': 'weekly', 'label': 'Semanalmente'},
    {'value': 'monthly', 'label': 'Mensalmente'},
    {'value': 'yearly', 'label': 'Anualmente'},
    {'value': 'custom', 'label': 'Personalizado'},
]
WEEKDAY_OPTIONS = [
    {'value': 'mon', 'label': 'Seg'},
    {'value': 'tue', 'label': 'Ter'},
    {'value': 'wed', 'label': 'Qua'},
    {'value': 'thu', 'label': 'Qui'},
    {'value': 'fri', 'label': 'Sex'},
    {'value': 'sat', 'label': 'Sab'},
    {'value': 'sun', 'label': 'Dom'},
]
PROJECT_OPTIONS = ['Trabalho', 'Faculdade', 'Estudos', 'Academia', 'Casa', 'Pessoal']
LOCATION_OPTIONS = ['Casa', 'Empresa', 'Academia', 'Mercado', 'Online']
DURATION_PRESETS = [
    {'label': '15 min', 'minutes': 15},
    {'label': '25 min', 'minutes': 25},
    {'label': '30 min', 'minutes': 30},
    {'label': '45 min', 'minutes': 45},
    {'label': '1h', 'minutes': 60},
    {'label': '1h30', 'minutes': 90},
    {'label': '2h', 'minutes': 120},
]


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


def _active_tasks_query(include_drafts=False):
    query = Task.query.filter_by(user_id=current_user.id, is_active=True)
    if not include_drafts:
        query = query.filter_by(is_draft=False)
    return query


def _ordered_tasks_query(include_drafts=False):
    return _active_tasks_query(include_drafts=include_drafts).order_by(
        Task.display_order.asc(), Task.created_at.desc(), Task.id.desc()
    )


def _task_form_context(**kwargs):
    context = {
        'colors': TASK_COLORS,
        'icons': TASK_ICONS,
        'priority_options': PRIORITY_OPTIONS,
        'reminder_options': REMINDER_OPTIONS,
        'recurrence_options': RECURRENCE_OPTIONS,
        'weekday_options': WEEKDAY_OPTIONS,
        'project_options': PROJECT_OPTIONS,
        'location_options': LOCATION_OPTIONS,
        'duration_presets': DURATION_PRESETS,
        'now': datetime.utcnow(),
    }
    context.update(kwargs)
    return context


def _serialize_lines(raw_value, separators=None):
    separators = separators or ['\n', ',']
    value = raw_value or ''
    for separator in separators[1:]:
        value = value.replace(separator, separators[0])
    items = []
    seen = set()
    for item in value.split(separators[0]):
        cleaned = item.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            items.append(cleaned)
            seen.add(key)
    return items


def _parse_int(raw_value, default=None, minimum=None, maximum=None):
    if raw_value in (None, ''):
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _save_uploaded_file(storage, subdir):
    if not storage or not storage.filename:
        return None
    filename = secure_filename(storage.filename)
    if not filename:
        return None
    ext = os.path.splitext(filename)[1]
    unique_name = f'{uuid.uuid4().hex}{ext}'
    relative_dir = os.path.join('uploads', subdir, str(current_user.id))
    absolute_dir = os.path.join(current_app.static_folder, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)
    absolute_path = os.path.join(absolute_dir, unique_name)
    storage.save(absolute_path)
    return {
        'name': filename,
        'url': url_for('static', filename=f'{relative_dir}/{unique_name}'.replace('\\', '/')),
        'type': ext.lower().lstrip('.'),
    }


def _build_task_clone(task):
    clone = Task(
        user_id=current_user.id,
        name=f'{task.name} (copia)',
        description=task.description,
        duration_minutes=task.duration_minutes,
        task_type=task.task_type,
        is_recurring=task.is_recurring,
        recurrence_type=task.recurrence_type,
        recurrence_interval=task.recurrence_interval,
        recurrence_days=task.recurrence_days,
        recurrence_end_date=task.recurrence_end_date,
        priority=task.priority,
        due_at=task.due_at,
        reminder_offset_minutes=task.reminder_offset_minutes,
        project_name=task.project_name,
        tags_json=task.tags_json,
        subtasks_json=task.subtasks_json,
        attachments_json=task.attachments_json,
        useful_links_json=task.useful_links_json,
        effort_level=task.effort_level,
        energy_level=task.energy_level,
        location=task.location,
        is_draft=task.is_draft,
        icon_emoji=task.icon_emoji,
        custom_icon_image=task.custom_icon_image,
        color=task.color,
        icon=task.icon,
        is_active=True,
    )
    return clone


@tasks_bp.route('/')
@login_required
def list_tasks():
    tasks = _ordered_tasks_query().all()
    drafts = (
        Task.query
        .filter_by(user_id=current_user.id, is_active=True, is_draft=True)
        .order_by(Task.created_at.desc(), Task.id.desc())
        .all()
    )
    task_data = []
    for task in tasks:
        task_data.append(_build_task_payload(task, task.get_or_create_today_session()))
    return render_template('tasks/list.html', task_data=task_data, drafts=drafts, **_task_form_context())


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        form_action = request.form.get('form_action', 'publish')
        form_data = _parse_task_form(request, allow_draft=form_action == 'draft')
        if form_data['error']:
            return render_template('tasks/form.html', **_task_form_context(
                error=form_data['error'],
                form_data=form_data['values'],
                raw_form=request.form,
            ))

        task = Task(user_id=current_user.id, **form_data['values'])
        max_order = db.session.query(db.func.max(Task.display_order)).filter_by(user_id=current_user.id).scalar()
        task.display_order = (max_order or 0) + 1
        db.session.add(task)
        db.session.commit()
        return redirect(url_for('tasks.list_tasks' if task.is_draft else 'main.dashboard'))

    return render_template('tasks/form.html', **_task_form_context())


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        form_action = request.form.get('form_action', 'publish')
        form_data = _parse_task_form(request, allow_draft=form_action == 'draft', existing_task=task)
        if form_data['error']:
            return render_template('tasks/form.html', **_task_form_context(
                task=task,
                error=form_data['error'],
                form_data=form_data['values'],
                raw_form=request.form,
            ))

        for field, value in form_data['values'].items():
            setattr(task, field, value)
        db.session.commit()
        return redirect(url_for('tasks.list_tasks' if task.is_draft else 'tasks.list_tasks'))

    return render_template('tasks/form.html', **_task_form_context(task=task))


@tasks_bp.route('/<int:task_id>/duplicate', methods=['POST'])
@login_required
def duplicate_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    duplicate = _build_task_clone(task)
    max_order = db.session.query(db.func.max(Task.display_order)).filter_by(user_id=current_user.id).scalar()
    duplicate.display_order = (max_order or 0) + 1
    db.session.add(duplicate)
    db.session.commit()
    return redirect(url_for('tasks.edit_task', task_id=duplicate.id))


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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, is_draft=False).first_or_404()
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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, is_draft=False).first_or_404()
    if task.is_check_task:
        return jsonify({'error': 'Esta tarefa e concluida manualmente por check.'}), 400

    today = date.today()
    running = (
        TaskSession.query
        .join(Task)
        .filter(
            Task.user_id == current_user.id,
            Task.is_draft == False,
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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, is_draft=False).first_or_404()
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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, is_draft=False).first_or_404()
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
    task = Task.query.filter_by(id=task_id, user_id=current_user.id, is_draft=False).first_or_404()
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
    tasks = _ordered_tasks_query().all()
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


@tasks_bp.route('/api/reorder', methods=['POST'])
@login_required
def reorder_tasks():
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get('task_ids')

    if not isinstance(ordered_ids, list) or not ordered_ids:
        return jsonify({'error': 'Lista de tarefas invalida.'}), 400

    try:
        ordered_ids = [int(task_id) for task_id in ordered_ids]
    except (TypeError, ValueError):
        return jsonify({'error': 'Lista de tarefas invalida.'}), 400

    tasks = _ordered_tasks_query().all()
    existing_ids = [task.id for task in tasks]

    if sorted(ordered_ids) != sorted(existing_ids):
        return jsonify({'error': 'A lista enviada nao corresponde as tarefas ativas.'}), 400

    task_by_id = {task.id: task for task in tasks}
    for index, task_id in enumerate(ordered_ids, start=1):
        task_by_id[task_id].display_order = index

    db.session.commit()
    return jsonify({'status': 'ok'})


def _parse_task_form(req, allow_draft=False, existing_task=None):
    form_action = req.form.get('form_action', 'publish')
    name = req.form.get('name', '').strip()
    description = req.form.get('description', '').strip()
    task_type = req.form.get('task_type', 'timer')
    duration_preset = req.form.get('duration_preset', '')
    duration_hours = _parse_int(req.form.get('duration_hours'), default=0, minimum=0, maximum=8)
    duration_minutes_extra = _parse_int(req.form.get('duration_minutes_extra'), default=0, minimum=0, maximum=59)
    priority = req.form.get('priority', 'medium')
    due_date_raw = req.form.get('due_date', '').strip()
    due_time_raw = req.form.get('due_time', '').strip()
    reminder_offset = _parse_int(req.form.get('reminder_offset_minutes'), default=None, minimum=0, maximum=10080)
    recurrence_type = req.form.get('recurrence_type', 'daily')
    recurrence_interval = _parse_int(req.form.get('recurrence_interval'), default=1, minimum=1, maximum=365)
    recurrence_days = req.form.getlist('recurrence_days')
    recurrence_end_date_raw = req.form.get('recurrence_end_date', '').strip()
    project_name = req.form.get('project_name', '').strip()
    tags = _serialize_lines(req.form.get('tags', ''))
    useful_links = _serialize_lines(req.form.get('useful_links', ''))
    subtasks = _serialize_lines(req.form.get('subtasks', ''))
    effort_level = _parse_int(req.form.get('effort_level'), default=None, minimum=1, maximum=5)
    energy_level = _parse_int(req.form.get('energy_level'), default=None, minimum=1, maximum=3)
    location = req.form.get('location', '').strip()
    color = req.form.get('color', '#4A9EFF')
    icon = req.form.get('icon', 'timer')
    icon_emoji = req.form.get('icon_emoji', '').strip()

    duration_minutes = 0
    if duration_preset:
        duration_minutes = _parse_int(duration_preset, default=0, minimum=0, maximum=480) or 0
    else:
        duration_minutes = (duration_hours or 0) * 60 + (duration_minutes_extra or 0)

    due_at = None
    if due_date_raw:
        try:
            due_at = datetime.strptime(
                f'{due_date_raw} {due_time_raw or "00:00"}',
                '%Y-%m-%d %H:%M'
            )
        except ValueError:
            due_at = 'invalid'

    recurrence_end_date = None
    if recurrence_end_date_raw:
        try:
            recurrence_end_date = datetime.strptime(recurrence_end_date_raw, '%Y-%m-%d').date()
        except ValueError:
            recurrence_end_date = 'invalid'

    allowed_priorities = {item['value'] for item in PRIORITY_OPTIONS}
    allowed_recurrence = {item['value'] for item in RECURRENCE_OPTIONS}
    allowed_weekdays = {item['value'] for item in WEEKDAY_OPTIONS}

    existing_attachments = existing_task.attachments if existing_task else []
    uploaded_attachments = []
    for storage in req.files.getlist('attachments'):
        saved = _save_uploaded_file(storage, 'tasks')
        if saved:
            uploaded_attachments.append(saved)

    attachment_links = _serialize_lines(req.form.get('attachment_links', ''))
    link_attachments = [{'name': link, 'url': link, 'type': 'link'} for link in attachment_links]

    custom_icon_image = existing_task.custom_icon_image if existing_task else None
    custom_icon_upload = req.files.get('custom_icon_upload')
    saved_icon = _save_uploaded_file(custom_icon_upload, 'task-icons')
    if saved_icon:
        custom_icon_image = saved_icon['url']

    values = {
        'name': name,
        'description': description,
        'task_type': task_type if task_type in {'timer', 'check'} else 'timer',
        'duration_minutes': duration_minutes,
        'is_recurring': recurrence_type != 'none',
        'recurrence_type': recurrence_type if recurrence_type in allowed_recurrence else 'daily',
        'recurrence_interval': recurrence_interval or 1,
        'recurrence_days': ','.join(day for day in recurrence_days if day in allowed_weekdays),
        'recurrence_end_date': recurrence_end_date if recurrence_end_date != 'invalid' else recurrence_end_date_raw,
        'priority': priority if priority in allowed_priorities else 'medium',
        'due_at': due_at if due_at != 'invalid' else due_date_raw,
        'reminder_offset_minutes': reminder_offset,
        'project_name': project_name,
        'tags_json': json.dumps(tags),
        'subtasks_json': json.dumps([{'title': item, 'done': False} for item in subtasks]),
        'attachments_json': json.dumps(existing_attachments + uploaded_attachments + link_attachments),
        'useful_links_json': json.dumps(useful_links),
        'effort_level': effort_level,
        'energy_level': energy_level,
        'location': location,
        'is_draft': form_action == 'draft',
        'icon_emoji': icon_emoji or None,
        'custom_icon_image': custom_icon_image,
        'color': color,
        'icon': icon,
    }

    if values['task_type'] == 'check':
        values['duration_minutes'] = 0
        if icon == 'timer':
            values['icon'] = 'task_alt'

    if values['recurrence_type'] != 'custom':
        values['recurrence_interval'] = 1
        values['recurrence_days'] = ''
        values['recurrence_end_date'] = recurrence_end_date if recurrence_end_date != 'invalid' else None

    if values['recurrence_type'] == 'weekdays':
        values['recurrence_days'] = 'mon,tue,wed,thu,fri'

    if allow_draft and not name:
        values['name'] = 'Rascunho sem titulo'

    if not values['name']:
        return {'error': 'Nome e obrigatorio.', 'values': values}

    if due_at == 'invalid':
        return {'error': 'Data de vencimento invalida.', 'values': values}

    if recurrence_end_date == 'invalid':
        return {'error': 'Data final da recorrencia invalida.', 'values': values}

    if values['task_type'] == 'timer' and not values['is_draft']:
        if values['duration_minutes'] < 1 or values['duration_minutes'] > 480:
            return {'error': 'Duracao deve ser entre 1 e 480 minutos.', 'values': values}

    if values['task_type'] == 'timer' and values['duration_minutes'] == 0 and values['is_draft']:
        values['duration_minutes'] = 25

    if values['recurrence_type'] == 'custom' and values['recurrence_days'] and not values['recurrence_interval']:
        return {'error': 'Defina o intervalo da recorrencia personalizada.', 'values': values}

    return {'error': None, 'values': values}


def _sync_elapsed(session):
    if session.status == 'running' and session.last_tick:
        now = datetime.utcnow()
        delta = (now - session.last_tick).total_seconds()
        duration_seconds = session.task.target_seconds
        session.time_completed = min(int(session.time_completed + delta), duration_seconds)
        session.last_tick = now
