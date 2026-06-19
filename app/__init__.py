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
    if 'task_type' in columns:
        return

    if db.engine.dialect.name == 'sqlite':
        db.session.execute(text(
            "ALTER TABLE tasks ADD COLUMN task_type VARCHAR(20) NOT NULL DEFAULT 'timer'"
        ))
    else:
        db.session.execute(text(
            "ALTER TABLE tasks ADD COLUMN task_type VARCHAR(20) NOT NULL DEFAULT 'timer'"
        ))
    db.session.commit()
