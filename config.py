import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'focusflow-secret-key-change-in-production-2024'
    
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'focusflow')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

    # Priority: explicit DATABASE_URL -> configured MySQL -> local SQLite fallback.
    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    elif os.environ.get('MYSQL_PASSWORD'):
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
            f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///focusflow.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
