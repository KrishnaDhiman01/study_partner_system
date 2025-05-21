import os
from app import create_app, socketio
from datetime import datetime, UTC

if os.environ.get('DEBUG', 'False').lower() == 'true':
     os.environ['FLASK_ENV'] = 'development'

app = create_app()

@app.context_processor
def inject_now():
    try:
        return {'now': datetime.now(UTC)}
    except Exception:
        return {'now': None}

if __name__ == "__main__":
    is_debug = app.config.get('DEBUG', False)
    host = '127.0.0.1'
    port = 5000
    print(f"🚦 Starting Flask-SocketIO server on http://{host}:{port} (Debug={is_debug})...")
    socketio.run(app, host=host, port=port, debug=is_debug, use_reloader=is_debug)