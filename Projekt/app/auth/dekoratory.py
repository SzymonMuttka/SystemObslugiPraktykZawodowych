from functools import wraps
from flask import abort
from flask_login import current_user


def rola_wymagana(*role):
    """
    Dekorator sprawdzający czy zalogowany użytkownik
    posiada jedną z wymaganych ról.

    Użycie:
        @rola_wymagana('student')
        @rola_wymagana('dziekanat', 'dyrektor')
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.ma_role(*role):
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper


def student_wymagany(fn):
    """Skrót: dostęp tylko dla studenta."""
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.ma_role('student'):
            abort(403)
        return fn(*args, **kwargs)
    return decorated


def pracownik_wymagany(fn):
    """Skrót: dostęp dla wszystkich pracowników uczelni."""
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.ma_role(
            'opiekun_uczelniany', 'dziekanat', 'dyrektor', 'czlonek_komisji'
        ):
            abort(403)
        return fn(*args, **kwargs)
    return decorated
