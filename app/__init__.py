"""
Flask application factory for Maggpi.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
import markdown

db = SQLAlchemy()


def markdown_filter(text):
    """Convert markdown text to HTML."""
    if not text:
        return ''
    # Convert markdown to HTML
    html = markdown.markdown(text, extensions=['nl2br'])
    return Markup(html)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load configuration
    from app.config import Config
    app.config.from_object(Config)

    # Register custom Jinja2 filters
    app.jinja_env.filters['markdown'] = markdown_filter

    # Initialize database
    db.init_app(app)

    # Configure SQLite for better concurrency (WAL mode)
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Create database tables
    with app.app_context():
        db.create_all()

        # Initialize scheduler
        from app.services.scheduler import init_scheduler
        init_scheduler(app)

    return app
