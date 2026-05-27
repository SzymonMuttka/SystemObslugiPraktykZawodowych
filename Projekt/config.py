import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # --------------------------------------------------------
    # Ogólne
    # --------------------------------------------------------
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

    # --------------------------------------------------------
    # Baza danych
    # --------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///praktyki.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --------------------------------------------------------
    # Microsoft Entra ID
    # --------------------------------------------------------
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
    MICROSOFT_TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID')
    MICROSOFT_REDIRECT_URI = os.environ.get(
        'MICROSOFT_REDIRECT_URI',
        'http://localhost:5000/auth/callback'
    )
    MICROSOFT_AUTHORITY = (
        f"https://login.microsoftonline.com/"
        f"{os.environ.get('MICROSOFT_TENANT_ID', 'common')}"
    )
    MICROSOFT_SCOPES = ['User.Read']

    # --------------------------------------------------------
    # Domeny uczelni
    # --------------------------------------------------------
    STUDENT_DOMAIN = os.environ.get('STUDENT_DOMAIN', 'student.ans.edu.pl')
    STAFF_DOMAIN = os.environ.get('STAFF_DOMAIN', 'ans.edu.pl')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
