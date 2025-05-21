import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from werkzeug.security import generate_password_hash 

basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f" Warning: .env file not found at {dotenv_path}. Relying on environment variables or defaults.")

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-that-you-should-change'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
    PORT = int(os.environ.get('FLASK_PORT', 5000))

    MYSQL_USER = os.environ.get("MYSQL_USER")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
    MYSQL_HOST = os.environ.get("MYSQL_HOST")
    MYSQL_DB = os.environ.get("MYSQL_DB")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", 3306)

    SQLALCHEMY_DATABASE_URI = None
    if all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB]):
        try:
            encoded_password = quote_plus(MYSQL_PASSWORD)
            SQLALCHEMY_DATABASE_URI = (
                f'mysql+mysqlconnector://{MYSQL_USER}:{encoded_password}'
                f'@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4'
            )
        except Exception as e:
             print(f"Error configuring DB URI: {e}")
    else:
        print("Critical Error: One or more MySQL environment variables are missing.")

    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    LOG_LEVEL = "DEBUG" if DEBUG else "INFO"


    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH') or generate_password_hash('adminpass', method='pbkdf2:sha256') 