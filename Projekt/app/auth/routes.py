from flask import (
    Blueprint, redirect, url_for,
    session, request, current_app, render_template,
    flash
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models.uzytkownik import Uzytkownik, Rola
from app.auth.microsoft import (
    pobierz_url_logowania,
    pobierz_token_z_kodu,
    pobierz_dane_uzytkownika
)

bp = Blueprint('auth', __name__, url_prefix='/auth')


# ============================================================
# Pomocnicze: logika pierwszego logowania
# ============================================================

def _ustal_role_z_domeny(email):
    """
    Ustala rolę użytkownika na podstawie domeny email.

    Zwraca:
        (nazwa_roli, wymaga_zatwierdzenia)
    """
    domena = email.split('@')[-1].lower() if '@' in email else ''

    student_domain = current_app.config.get('STUDENT_DOMAIN', '')
    staff_domain = current_app.config.get('STAFF_DOMAIN', '')

    if domena == student_domain:
        return 'student', False
    elif domena == staff_domain:
        return 'dziekanat', True  # konto czeka na zatwierdzenie i przypisanie roli
    else:
        return None, False


def _znajdz_lub_utworz_uzytkownika(dane_ms):
    """
    Obsługuje logikę pierwszego logowania.

    1. Szuka użytkownika po external_id (Microsoft OID)
    2. Szuka po emailu (na wypadek zmiany OID)
    3. Tworzy nowe konto jeśli nie istnieje
    4. Przypisuje rolę na podstawie domeny

    Zwraca:
        (uzytkownik, czy_nowy)
        lub (None, False) jeśli domena niedozwolona
    """
    external_id = dane_ms.get('external_id')
    email = dane_ms.get('email', '').lower()

    # Szukanie po external_id
    uzytkownik = Uzytkownik.query.filter_by(
        external_id=external_id
    ).first()

    # Szukanie po emailu jako fallback
    if not uzytkownik and email:
        uzytkownik = Uzytkownik.query.filter_by(email=email).first()
        if uzytkownik and not uzytkownik.external_id:
            uzytkownik.external_id = external_id
            db.session.commit()

    # Użytkownik istnieje - zwróć bez tworzenia
    if uzytkownik:
        return uzytkownik, False

    # Nowy użytkownik - ustal rolę
    nazwa_roli, wymaga_zatwierdzenia = _ustal_role_z_domeny(email)

    if nazwa_roli is None:
        current_app.logger.warning(
            f"Próba logowania z niedozwolonej domeny: {email}"
        )
        return None, False

    rola = Rola.query.filter_by(nazwa=nazwa_roli).first()
    if not rola:
        current_app.logger.error(
            f"Rola '{nazwa_roli}' nie istnieje w bazie danych"
        )
        return None, False

    nowy_uzytkownik = Uzytkownik(
        imie=dane_ms.get('imie', ''),
        nazwisko=dane_ms.get('nazwisko', ''),
        email=email,
        auth_provider='microsoft',
        external_id=external_id,
        rola_id=rola.id,
        wymaga_zatwierdzenia=wymaga_zatwierdzenia,
        jest_aktywny=not wymaga_zatwierdzenia
    )

    db.session.add(nowy_uzytkownik)
    db.session.commit()

    current_app.logger.info(
        f"Utworzono nowe konto: {email} z rolą {nazwa_roli}"
    )

    return nowy_uzytkownik, True


# ============================================================
# Trasy
# ============================================================

@bp.route('/microsoft')
def microsoft_login():
    """
    Inicjuje logowanie przez Microsoft.
    Przekierowuje użytkownika do strony logowania Microsoft.
    """
    url = pobierz_url_logowania()
    return redirect(url)


@bp.route('/callback')
def callback():
    """
    Obsługuje powrót z Microsoft po autoryzacji.
    Wymienia kod autoryzacji na token i loguje użytkownika.
    """
    # Sprawdzenie czy Microsoft zwrócił błąd
    if request.args.get('error'):
        blad = request.args.get('error')
        opis = request.args.get('error_description', '')
        current_app.logger.error(f"Błąd callback Microsoft: {blad} - {opis}")
        return render_template(
            'auth/login.html',
            blad='Logowanie nie powiodło się. Spróbuj ponownie.'
        )

    kod = request.args.get('code')
    if not kod:
        return render_template(
            'auth/login.html',
            blad='Brak kodu autoryzacji. Spróbuj ponownie.'
        )

    # Wymiana kodu na token
    token = pobierz_token_z_kodu(kod)
    if not token:
        return render_template(
            'auth/login.html',
            blad='Nie udało się pobrać tokenu. Spróbuj ponownie.'
        )

    # Pobranie danych użytkownika z Microsoft Graph
    dane_ms = pobierz_dane_uzytkownika(token)
    if not dane_ms:
        return render_template(
            'auth/login.html',
            blad='Nie udało się pobrać danych użytkownika.'
        )

    # Znajdź lub utwórz użytkownika
    uzytkownik, czy_nowy = _znajdz_lub_utworz_uzytkownika(dane_ms)

    if uzytkownik is None:
        return render_template(
            'auth/login.html',
            blad='Brak dostępu. Twoja domena email nie jest autoryzowana.'
        )

    if not uzytkownik.jest_aktywny:
        return render_template(
            'auth/login.html',
            blad='Twoje konto oczekuje na zatwierdzenie przez administratora.'
        )

    # Zalogowanie użytkownika przez Flask-Login
    login_user(uzytkownik)
    session['dane_ms'] = dane_ms

    current_app.logger.info(
        f"Zalogowano użytkownika: {uzytkownik.email} "
        f"({'nowe konto' if czy_nowy else 'istniejące konto'})"
    )

    # Przekierowanie do dashboardu
    return redirect(url_for('dashboard.index'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania i logowanie lokalne."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Podaj email i hasło.', 'danger')
            return render_template('auth/login.html', email=email)

        uzytkownik = Uzytkownik.query.filter_by(email=email).first()
        if not uzytkownik or uzytkownik.auth_provider != 'local':
            flash('Nieprawidłowy email lub hasło.', 'danger')
            return render_template('auth/login.html', email=email)

        if not check_password_hash(uzytkownik.haslo_hash, password):
            flash('Nieprawidłowy email lub hasło.', 'danger')
            return render_template('auth/login.html', email=email)

        if not uzytkownik.jest_aktywny:
            flash('Twoje konto oczekuje na aktywację.', 'danger')
            return render_template('auth/login.html', email=email)

        login_user(uzytkownik)
        current_app.logger.info(f'Zalogowano użytkownika lokalnego: {uzytkownik.email}')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Rejestracja użytkownika lokalnego do testów."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    role_list = Rola.query.order_by(Rola.nazwa).all()

    if request.method == 'POST':
        imie = request.form.get('imie', '').strip()
        nazwisko = request.form.get('nazwisko', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        selected_role = request.form.get('role', '')

        if not (imie and nazwisko and email and password and confirm_password and selected_role):
            flash('Wszystkie pola są wymagane.', 'danger')
            return render_template('auth/register.html', roles=role_list)

        if password != confirm_password:
            flash('Hasła muszą być takie same.', 'danger')
            return render_template('auth/register.html', roles=role_list)

        if Uzytkownik.query.filter_by(email=email).first():
            flash('Użytkownik o tym emailu już istnieje.', 'danger')
            return render_template('auth/register.html', roles=role_list)

        rola = Rola.query.filter_by(nazwa=selected_role).first()
        if not rola:
            flash('Wybrana rola jest nieprawidłowa.', 'danger')
            return render_template('auth/register.html', roles=role_list)

        nowy_uzytkownik = Uzytkownik(
            imie=imie,
            nazwisko=nazwisko,
            email=email,
            haslo_hash=generate_password_hash(password),
            auth_provider='local',
            rola_id=rola.id,
            wymaga_zatwierdzenia=False,
            jest_aktywny=True
        )
        db.session.add(nowy_uzytkownik)
        db.session.commit()

        flash('Konto testowe zostało utworzone. Zaloguj się.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', roles=role_list)


@bp.route('/logout')
@login_required
def logout():
    """Wylogowuje użytkownika i czyści sesję."""
    email = current_user.email
    logout_user()
    session.clear()

    current_app.logger.info(f"Wylogowano użytkownika: {email}")

    # Przekierowanie do strony wylogowania Microsoft
    tenant = current_app.config['MICROSOFT_TENANT_ID']
    post_logout = url_for('auth.login', _external=True)
    ms_logout_url = (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={post_logout}"
    )
    return redirect(ms_logout_url)
