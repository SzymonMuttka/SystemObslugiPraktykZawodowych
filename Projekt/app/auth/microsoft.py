import msal
from flask import current_app, session


def _build_msal_app(cache=None):
    """Tworzy instancję aplikacji MSAL."""
    return msal.ConfidentialClientApplication(
        current_app.config['MICROSOFT_CLIENT_ID'],
        authority=current_app.config['MICROSOFT_AUTHORITY'],
        client_credential=current_app.config['MICROSOFT_CLIENT_SECRET'],
        token_cache=cache
    )


def _load_cache():
    """Ładuje cache tokenów MSAL.

    Uwaga: nie zapisujemy token cache w cookie sesyjnym, ponieważ
    może to przekroczyć limit ciasteczka przeglądarki.
    """
    return msal.SerializableTokenCache()


def _save_cache(cache):
    """Nie zapisujemy cache tokenów w sesji Flask."""
    pass


def pobierz_url_logowania():
    """
    Generuje URL do strony logowania Microsoft.
    Zwraca URL do przekierowania użytkownika.
    """
    app = _build_msal_app()
    url = app.get_authorization_request_url(
        scopes=current_app.config['MICROSOFT_SCOPES'],
        redirect_uri=current_app.config['MICROSOFT_REDIRECT_URI']
    )
    return url


def pobierz_token_z_kodu(kod_autoryzacji):
    """
    Wymienia kod autoryzacji na token dostępu.
    Zwraca słownik z tokenem lub None w przypadku błędu.
    """
    cache = _load_cache()
    app = _build_msal_app(cache=cache)

    wynik = app.acquire_token_by_authorization_code(
        kod_autoryzacji,
        scopes=current_app.config['MICROSOFT_SCOPES'],
        redirect_uri=current_app.config['MICROSOFT_REDIRECT_URI']
    )

    if 'error' in wynik:
        current_app.logger.error(
            f"Błąd OAuth Microsoft: {wynik.get('error')} - "
            f"{wynik.get('error_description')}"
        )
        return None

    _save_cache(cache)
    return wynik


def pobierz_dane_uzytkownika(token):
    """
    Pobiera dane użytkownika z Microsoft Graph API.
    Zwraca słownik z danymi użytkownika lub None.
    """
    import requests

    naglowki = {'Authorization': f"Bearer {token['access_token']}"}
    odpowiedz = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers=naglowki
    )

    if odpowiedz.status_code != 200:
        current_app.logger.error(
            f"Błąd Graph API: {odpowiedz.status_code} - {odpowiedz.text}"
        )
        return None

    dane = odpowiedz.json()

    # Normalizacja danych z Microsoft Graph
    return {
        'external_id': dane.get('id'),
        'email': dane.get('mail') or dane.get('userPrincipalName'),
        'imie': dane.get('givenName', ''),
        'nazwisko': dane.get('surname', ''),
        'tenant': token.get('id_token_claims', {}).get('tid'),
    }
