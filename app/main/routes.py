from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import date, timedelta
from app.models import Task, TaskSession
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    
    # Get all active tasks
    tasks = Task.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    # Build task cards with today's sessions
    task_data = []
    total_minutes_goal = 0
    total_seconds_done = 0
    completed_count = 0

    for task in tasks:
        session = task.get_or_create_today_session()
        duration_seconds = task.duration_minutes * 60
        progress = min(100, int((session.time_completed / duration_seconds) * 100)) if duration_seconds > 0 else 0
        
        total_minutes_goal += task.duration_minutes
        total_seconds_done += session.time_completed
        if session.status == 'completed':
            completed_count += 1

        task_data.append({
            'task': task,
            'session': session,
            'progress': progress,
            'remaining_seconds': max(0, duration_seconds - session.time_completed),
        })

    # Overall daily progress
    total_seconds_goal = total_minutes_goal * 60
    daily_progress = min(100, int((total_seconds_done / total_seconds_goal) * 100)) if total_seconds_goal > 0 else 0

    # Last 7 days history summary
    history_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        sessions = (TaskSession.query
                    .join(Task)
                    .filter(Task.user_id == current_user.id, TaskSession.date == d)
                    .all())
        total_sec = sum(s.time_completed for s in sessions)
        completed = sum(1 for s in sessions if s.status == 'completed')
        history_data.append({
            'date': d,
            'label': 'Hoje' if i == 0 else d.strftime('%a'),
            'total_minutes': total_sec // 60,
            'completed': completed,
            'total_tasks': len(sessions),
        })

    return render_template('dashboard.html',
        task_data=task_data,
        daily_progress=daily_progress,
        total_minutes_goal=total_minutes_goal,
        total_seconds_done=total_seconds_done,
        completed_count=completed_count,
        total_tasks=len(tasks),
        history_data=history_data,
        today=today
    )


@main_bp.route('/history')
@login_required
def history():
    today = date.today()
    days_back = 30
    
    history_days = []
    for i in range(days_back):
        d = today - timedelta(days=i)
        sessions = (TaskSession.query
                    .join(Task)
                    .filter(Task.user_id == current_user.id, TaskSession.date == d)
                    .all())
        if sessions or i == 0:
            day_sessions = []
            for s in sessions:
                day_sessions.append({
                    'session': s,
                    'task': s.task,
                    'progress': min(100, int((s.time_completed / (s.task.duration_minutes * 60)) * 100)) if s.task.duration_minutes > 0 else 0
                })
            history_days.append({
                'date': d,
                'sessions': day_sessions,
                'total_minutes': sum(s.time_completed for s in sessions) // 60,
                'completed': sum(1 for s in sessions if s.status == 'completed'),
            })

    return render_template('history.html', history_days=history_days)
