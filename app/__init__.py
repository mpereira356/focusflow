from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()


def create_app(config_name='default'):
    load_dotenv()
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'

    from app.auth.routes import auth_bp
    from app.tasks.routes import tasks_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(main_bp)

    # Ensure tables exist when running through `flask run` in local/dev.
    with app.app_context():
        db.create_all()
        _run_lightweight_migrations()

    return app


def _run_lightweight_migrations():
    inspector = inspect(db.engine)
    columns = {column['name'] for column in inspector.get_columns('tasks')}
    migrations_ran = False

    migration_specs = [
        ('task_type', "ALTER TABLE tasks ADD COLUMN task_type VARCHAR(20) NOT NULL DEFAULT 'timer'"),
        ('display_order', "ALTER TABLE tasks ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0"),
        ('recurrence_type', "ALTER TABLE tasks ADD COLUMN recurrence_type VARCHAR(30) NOT NULL DEFAULT 'daily'"),
        ('recurrence_interval', "ALTER TABLE tasks ADD COLUMN recurrence_interval INTEGER NOT NULL DEFAULT 1"),
        ('recurrence_days', "ALTER TABLE tasks ADD COLUMN recurrence_days VARCHAR(50)"),
        ('recurrence_end_date', "ALTER TABLE tasks ADD COLUMN recurrence_end_date DATE"),
        ('priority', "ALTER TABLE tasks ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'medium'"),
        ('due_at', "ALTER TABLE tasks ADD COLUMN due_at DATETIME"),
        ('reminder_offset_minutes', "ALTER TABLE tasks ADD COLUMN reminder_offset_minutes INTEGER"),
        ('project_name', "ALTER TABLE tasks ADD COLUMN project_name VARCHAR(120)"),
        ('tags_json', "ALTER TABLE tasks ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'"),
        ('subtasks_json', "ALTER TABLE tasks ADD COLUMN subtasks_json TEXT NOT NULL DEFAULT '[]'"),
        ('attachments_json', "ALTER TABLE tasks ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'"),
        ('useful_links_json', "ALTER TABLE tasks ADD COLUMN useful_links_json TEXT NOT NULL DEFAULT '[]'"),
        ('effort_level', "ALTER TABLE tasks ADD COLUMN effort_level INTEGER"),
        ('energy_level', "ALTER TABLE tasks ADD COLUMN energy_level INTEGER"),
        ('location', "ALTER TABLE tasks ADD COLUMN location VARCHAR(120)"),
        ('is_draft', "ALTER TABLE tasks ADD COLUMN is_draft BOOLEAN NOT NULL DEFAULT 0"),
        ('icon_emoji', "ALTER TABLE tasks ADD COLUMN icon_emoji VARCHAR(16)"),
        ('custom_icon_image', "ALTER TABLE tasks ADD COLUMN custom_icon_image VARCHAR(255)"),
    ]

    for column_name, ddl in migration_specs:
        if column_name not in columns:
            db.session.execute(text(ddl))
            migrations_ran = True

    if migrations_ran:
        if 'recurrence_type' not in columns and 'is_recurring' in columns:
            db.session.execute(text(
                "UPDATE tasks SET recurrence_type = CASE WHEN is_recurring = 1 THEN 'daily' ELSE 'none' END"
            ))
        rows = db.session.execute(text(
            "SELECT id FROM tasks ORDER BY created_at DESC, id DESC"
        )).fetchall()
        for index, row in enumerate(rows, start=1):
            db.session.execute(
                text("UPDATE tasks SET display_order = :display_order WHERE id = :task_id"),
                {"display_order": index, "task_id": row.id},
            )
        db.session.commit()
