from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name='default'):
    """Fabryka aplikacji Flask."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # --------------------------------------------------------
    # Inicjalizacja rozszerzeń
    # --------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Zaloguj się aby uzyskać dostęp.'
    login_manager.login_message_category = 'info'

    # --------------------------------------------------------
    # Ładowanie użytkownika dla Flask-Login
    # --------------------------------------------------------
    from app.models.uzytkownik import Uzytkownik

    @login_manager.user_loader
    def load_user(user_id):
        return Uzytkownik.query.get(int(user_id))

    # --------------------------------------------------------
    # Rejestracja blueprintów
    # --------------------------------------------------------
    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.student.routes import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    # --------------------------------------------------------
    # Obsługa błędów HTTP
    # --------------------------------------------------------
    @app.errorhandler(401)
    def unauthorized(e):
        from flask import render_template
        return render_template('errors/401.html'), 401

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    return app
