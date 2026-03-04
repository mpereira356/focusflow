from datetime import datetime, date
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='owner', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=25)
    is_recurring = db.Column(db.Boolean, default=True)
    color = db.Column(db.String(7), default='#4A9EFF')
    icon = db.Column(db.String(50), default='timer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    sessions = db.relationship('TaskSession', backref='task', lazy='dynamic', cascade='all, delete-orphan')

    def get_today_session(self):
        today = date.today()
        return TaskSession.query.filter_by(
            task_id=self.id,
            date=today
        ).first()

    def get_or_create_today_session(self):
        session = self.get_today_session()
        if not session:
            session = TaskSession(
                task_id=self.id,
                date=date.today(),
                time_completed=0,
                status='pending'
            )
            db.session.add(session)
            db.session.commit()
        return session

    def __repr__(self):
        return f'<Task {self.name}>'


class TaskSession(db.Model):
    __tablename__ = 'task_sessions'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    time_completed = db.Column(db.Integer, default=0)  # seconds completed
    status = db.Column(db.String(20), default='pending')  # pending, running, paused, completed
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    last_tick = db.Column(db.DateTime, nullable=True)  # last time we synced

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'date': self.date.isoformat(),
            'time_completed': self.time_completed,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
        }

    def __repr__(self):
        return f'<TaskSession task={self.task_id} date={self.date} status={self.status}>'
