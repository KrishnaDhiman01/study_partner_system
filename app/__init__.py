import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from config import Config
import logging

db = SQLAlchemy()
socketio = SocketIO()

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True,
                static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

    if not app.config.get('SQLALCHEMY_DATABASE_URI') and not os.environ.get('FLASK_TESTING'): 
        app.logger.critical("FATAL: SQLALCHEMY_DATABASE_URI not configured and not in testing mode. Application cannot start.")
        
    logging.basicConfig(level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO),
                        format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    
    if app.debug:
        app.logger.info(f"Flask App '{app.name}' created in DEBUG mode.")
    else:
        app.logger.info(f"Flask App '{app.name}' created in PRODUCTION mode (Debug=False).")


    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.error(f"Error creating instance path {app.instance_path}: {e}")
        pass 

    db.init_app(app)
   
    socketio.init_app(app, async_mode=None, cors_allowed_origins="*") 
    app.logger.info("SQLAlchemy & SocketIO initialized.")

    
    try:
        from .routes import main_bp 
        from .admin.routes import admin_bp 
        
        app.register_blueprint(main_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.logger.info("Blueprints 'main' and 'admin' registered.")
    except ImportError as e:
        app.logger.error(f"Error importing/registering blueprints: {e}")


    
    try:
        from . import chat_events 
        app.logger.info("Chat event handlers registered.")
    except ImportError as e:
        app.logger.error(f"Error importing chat_events: {e}")


    with app.app_context():
        app.logger.info("Attempting to connect to database and create tables (if they don't exist)...")
        try:
            
            db.create_all()
            app.logger.info("Database tables checked/created successfully.")
        except Exception as e:
            app.logger.error(f"ERROR DURING DATABASE SETUP (db.create_all): {e.__class__.__name__}: {e}")
            app.logger.error("Please ensure your database server is running and configuration in .env is correct.")
            app.logger.error(f"Attempted URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    
    app.logger.info("🚀 Flask App instance created and configured.")
    return app