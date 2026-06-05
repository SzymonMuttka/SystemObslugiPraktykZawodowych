from datetime import date
import json

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from sqlalchemy import text

bp = Blueprint('dashboard', __name__)


def generate_agreement_number():
    """Generuje numer porozumienia w formacie POR-000X."""
    from app import db
    from sqlalchemy import text

    #count = db.session.query(func.count(Dokument.id)).filter(Dokument.typ_dokumentu_id == 1).scalar()
    count = db.session.execute(
        text("SELECT COUNT(typ_dokumentu_id) FROM dokument WHERE typ_dokumentu_id = 1")
        ).scalar()

    next_number = count + 1

    return f"POR-{next_number:04d}"


def update_practice_stage_from_typ(praktyka_id, typ_id):
    from app import db
    from sqlalchemy import text

    db.session.execute(
        text(
            "UPDATE praktyka "
            "SET aktualny_etap = (SELECT kolejnosc FROM typ_dokumentu WHERE id = :typ_id) "
            "WHERE id = :praktyka_id"
        ),
        {'typ_id': typ_id, 'praktyka_id': praktyka_id}
    )


def save_attachment1_data(form_data):
    """Zapis danych załącznika 1 do bazy danych.

    Aktualizuje praktykę opiekunem uczelnianym, tworzy dokument
    i zapisuje dane dokumentu jako pola formularza.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 1: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        opiekun_uczelniany_id = int(form_data.get('reprezentant_uczelni_id')) if form_data.get('reprezentant_uczelni_id') else None
        nr_porozumienia = form_data.get('nr_porozumienia', '').strip()
        data_zawarcia = form_data.get('data_zawarcia', '').strip()
        wymiar_praktyki = form_data.get('wymiar_praktyki', '').strip()

        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 1.')
            return False

        # 1) Aktualizuj praktykę studenta opiekunem uczelnianym
        praktyka = db.session.execute(
            text("SELECT id, opiekun_firmowy_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()

        praktyka_id = praktyka[0] if praktyka else None
        opiekun_firmowy_id = praktyka[1] if praktyka and len(praktyka) > 1 else None
        if praktyka_id and opiekun_uczelniany_id:
            db.session.execute(
                text("UPDATE praktyka SET opiekun_uczelniany_id=:opiekun_id WHERE id=:praktyka_id"),
                {'opiekun_id': opiekun_uczelniany_id, 'praktyka_id': praktyka_id}
            )
            db.session.commit()

        # 2) Utwórz wpis w tabeli dokument powiązany z załącznikiem 1
        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_1' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None

        dokument_id = None
        if praktyka_id and typ_id:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                    " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'status': 'completed',
                    'ostatni_edytor': current_user.id,
                }
            )
            update_practice_stage_from_typ(praktyka_id, typ_id)
            db.session.commit()

            doc_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            dokument_id = doc_row[0] if doc_row else None

        # 3) Utwórz wpisy udostępnionego dokumentu
        if dokument_id:
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_firmowy_id,
                        'rola_id': role_ids['opiekun_firmowy'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            db.session.commit()

        # 4) Utwórz trzy wpisy w tabeli dane_dokumentu
        if dokument_id:
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'nr_porozumienia', 'wartosc': nr_porozumienia, 'wypelniajacy': current_user.id}
            )
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'data_zawarcia', 'wartosc': data_zawarcia, 'wypelniajacy': current_user.id}
            )
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'wymiar_praktyki', 'wartosc': wymiar_praktyki, 'wypelniajacy': current_user.id}
            )
            db.session.commit()

        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 1: {e}')
        return False


@bp.route('/dashboard')
@login_required
def index():
    """Główna strona dashboardu po zalogowaniu."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    practice_rows = []
    selected_practice = None
    available_documents = []
    my_documents = []

    if role == 'student':
        practice_row = db.session.execute(
            text(
                "SELECT id, sciezka, status, aktualny_etap "
                "FROM praktyka WHERE student_id = :student_id ORDER BY id DESC LIMIT 1"
            ),
            {'student_id': current_user.id}
        ).fetchone()
        if practice_row:
            selected_practice = {
                'id': practice_row[0],
                'sciezka': practice_row[1] or '',
                'status': practice_row[2] or '',
                'aktualny_etap': practice_row[3],
            }

        # helper to get last document status for a practice and document code
        def get_doc_status(prak_id, kod):
            if not prak_id:
                return None
            row = db.session.execute(text(
                "SELECT d.status FROM dokument d JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                "WHERE d.praktyka_id = :prak_id AND t.kod = :kod ORDER BY d.id DESC LIMIT 1"
            ), {'prak_id': prak_id, 'kod': kod}).fetchone()
            return row[0] if row else None

        prak_id = selected_practice['id'] if selected_practice else None

        if not selected_practice:
            # No practice: 4b enabled, 7a disabled
            available_documents = [
                {'label': 'Załącznik 4b', 'url': url_for('dashboard.zalacznik_4b'), 'disabled': False},
                {'label': 'Załącznik 7a', 'url': url_for('dashboard.zalacznik_7a'), 'disabled': True, 'reason': 'Brak przypisanej praktyki'},
            ]
        elif selected_practice['sciezka'] == 'alternative':
            # 4b enabled only if not already created; 7a enabled only if ZAL_4A completed and not already created
            z4b_status = get_doc_status(prak_id, 'ZAL_4B')
            z4a_status = get_doc_status(prak_id, 'ZAL_4A')
            z7a_status = get_doc_status(prak_id, 'ZAL_7A')
            available_documents = [
                {
                    'label': 'Załącznik 4b',
                    'url': url_for('dashboard.zalacznik_4b', selected_praktyka_id=prak_id),
                    'disabled': z4b_status is not None,
                    'reason': 'Załącznik już utworzony' if z4b_status is not None else None,
                },
                {
                    'label': 'Załącznik 7a',
                    'url': url_for('dashboard.zalacznik_7a', selected_praktyka_id=prak_id),
                    'disabled': not (z4a_status == 'completed') or (z7a_status is not None),
                    'reason': ('Wymagany: ZAL_4A ukończony' if z4a_status != 'completed' else 'Załącznik już utworzony'),
                },
            ]
        else:
            # standard path: conditions based on other documents
            z3_status = get_doc_status(prak_id, 'ZAL_3')
            z6_status = get_doc_status(prak_id, 'ZAL_6')
            z8_status = get_doc_status(prak_id, 'ZAL_8')
            z5_status = get_doc_status(prak_id, 'ZAL_5')
            z7_status = get_doc_status(prak_id, 'ZAL_7')

            # Załącznik 6: requires ZAL_3 status 'doc3_step2'
            can_create_6 = (z3_status == 'doc3_step2') and (z6_status is None)
            # Załącznik 7: requires ZAL_6 completed
            can_create_7 = (z6_status == 'completed') and (z7_status is None)
            # Załącznik 5: requires ZAL_8 completed and praktyka nie jest już na etapie 10
            can_create_5 = (z8_status == 'completed') and (z5_status is None) and (selected_practice.get('aktualny_etap') != 10)

            available_documents = [
                {
                    'label': 'Załącznik 5',
                    'url': url_for('dashboard.zalacznik_5', selected_praktyka_id=prak_id),
                    'disabled': not can_create_5,
                    'reason': ('Załącznik 5 został już utworzony, dziękujemy za wypełnienie ankiety' if selected_practice.get('aktualny_etap') == 10 else 'Wymagany: ZAL_8 ukończony lub już utworzony'),
                },
                {'label': 'Załącznik 6', 'url': url_for('dashboard.zalacznik_6', selected_praktyka_id=prak_id), 'disabled': not can_create_6, 'reason': 'Wymagany: ZAL_3 na etapie doc3_step2 lub już utworzony'},
                {'label': 'Załącznik 7', 'url': url_for('dashboard.zalacznik_7', selected_praktyka_id=prak_id), 'disabled': not can_create_7, 'reason': 'Wymagany: ZAL_6 ukończony lub już utworzony'},
            ]

    elif role in ['dziekanat', 'opiekun_firmowy', 'opiekun_uczelniany', 'dyrektor', 'czlonek_komisji']:
        query = (
            "SELECT p.id, u.imie || ' ' || u.nazwisko AS student_name, u.numer_albumu, p.status, p.sciezka "
            "FROM praktyka p "
            "JOIN uzytkownik u ON p.student_id = u.id "
            "WHERE p.id IN (SELECT MAX(id) FROM praktyka GROUP BY student_id)"
        )
        params = {}
        if role == 'opiekun_firmowy':
            query += ' AND p.opiekun_firmowy_id = :user_id'
            params['user_id'] = current_user.id
        elif role == 'opiekun_uczelniany':
            query += ' AND p.opiekun_uczelniany_id = :user_id'
            params['user_id'] = current_user.id

        rows = db.session.execute(text(query), params).fetchall()
        for row in rows:
            practice_rows.append({
                'id': row[0],
                'student_name': row[1],
                'numer_albumu': row[2],
                'status': row[3] or '',
                'sciezka': row[4] or '',
            })

        if role == 'opiekun_firmowy':
            available_documents = [
                {'label': 'Załącznik 9', 'url': url_for('dashboard.zalacznik_9')},
            ]

        if selected_practice_id:
            selected_row = next((r for r in practice_rows if r['id'] == selected_practice_id), None)
            if selected_row:
                selected_practice = selected_row
                if role == 'dziekanat':
                    # helper to get last document status for a practice and document code
                    def get_doc_status(prak_id, kod):
                        row = db.session.execute(text(
                            "SELECT d.status FROM dokument d JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                            "WHERE d.praktyka_id = :prak_id AND t.kod = :kod ORDER BY d.id DESC LIMIT 1"
                        ), {'prak_id': selected_practice_id, 'kod': kod}).fetchone()
                        return row[0] if row else None

                    if selected_practice['sciezka'] == 'standard':
                        # compute statuses
                        z9 = get_doc_status(selected_practice_id, 'ZAL_9')
                        z1 = get_doc_status(selected_practice_id, 'ZAL_1')
                        z2 = get_doc_status(selected_practice_id, 'ZAL_2')
                        z2a = get_doc_status(selected_practice_id, 'ZAL_2A')
                        z3 = get_doc_status(selected_practice_id, 'ZAL_3')
                        z6 = get_doc_status(selected_practice_id, 'ZAL_6')
                        z4 = get_doc_status(selected_practice_id, 'ZAL_4')
                        z7 = get_doc_status(selected_practice_id, 'ZAL_7')
                        z8 = get_doc_status(selected_practice_id, 'ZAL_8')

                        available_documents = [
                            {'label': 'Załącznik 1', 'url': url_for('dashboard.zalacznik_1', selected_praktyka_id=selected_practice_id), 'disabled': not (z9 == 'completed') or (z1 is not None)},
                            {'label': 'Załącznik 2', 'url': url_for('dashboard.zalacznik_2', selected_praktyka_id=selected_practice_id), 'disabled': not (z1 == 'completed') or (z2 is not None)},
                            {'label': 'Załącznik 2a', 'url': url_for('dashboard.zalacznik_2a', selected_praktyka_id=selected_practice_id), 'disabled': not (z2 == 'completed') or (z2a is not None)},
                            {'label': 'Załącznik 3', 'url': url_for('dashboard.zalacznik_3', selected_praktyka_id=selected_practice_id), 'disabled': not (z2a == 'completed') or (z3 is not None)},
                            {'label': 'Załącznik 4', 'url': url_for('dashboard.zalacznik_4', selected_praktyka_id=selected_practice_id), 'disabled': not (z6 == 'completed') or (z4 is not None)},
                            {'label': 'Załącznik 8', 'url': url_for('dashboard.zalacznik_8', selected_praktyka_id=selected_practice_id), 'disabled': not ((z7 == 'completed') and (z3 == 'completed') and (z4 == 'completed')) or (z8 is not None), 'reason': ('Zablokowane' if z8 is not None else 'Wymagany: ZAL_7, ZAL_3 i ZAL_4 ukończone')},
                        ]
                    elif selected_practice['sciezka'] == 'alternative':
                        z4b = get_doc_status(selected_practice_id, 'ZAL_4B')
                        z4a = get_doc_status(selected_practice_id, 'ZAL_4A')
                        z7a = get_doc_status(selected_practice_id, 'ZAL_7A')

                        available_documents = [
                            {'label': 'Załącznik 4a', 'url': url_for('dashboard.zalacznik_4a', selected_praktyka_id=selected_practice_id), 'disabled': not (z4b == 'completed') or (z4a is not None)},
                            {'label': 'Załącznik 8', 'url': url_for('dashboard.zalacznik_8', selected_praktyka_id=selected_practice_id), 'disabled': not (z7a == 'completed') or (get_doc_status(selected_practice_id, 'ZAL_8') is not None)},
                        ]
                elif role == 'opiekun_firmowy':
                    available_documents = [
                        {'label': 'Załącznik 9', 'url': url_for('dashboard.zalacznik_9')},
                    ]

    # Pobierz dokumenty utworzone przez użytkownika lub udostępnione mu
    try:
        docs_params = {'user_id': current_user.id, 'rola_id': current_user.rola_id}
        # dla roli student pokaż wszystkie dokumenty utworzone/udostępnione bez filtrowania po praktyce
        if role == 'student':
            docs_query = (
                "SELECT d.id, t.kod, d.status, oe.imie || ' ' || oe.nazwisko AS ostatni, d.zaktualizowano "
                "FROM dokument d "
                "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                "LEFT JOIN uzytkownik oe ON d.ostatni_edytor = oe.id "
                "WHERE (d.utworzony_przez = :user_id OR EXISTS(SELECT 1 FROM udostepniony_dokument ud WHERE ud.dokument_id = d.id "
                "AND (ud.adresat = :user_id OR (ud.rola_id = :rola_id AND ud.adresat IS NULL)))) "
            )
            docs_rows = db.session.execute(text(docs_query), docs_params).fetchall()
        else:
            # dla innych ról pokaż dokumenty tylko jeśli wybrano praktykę
            docs_rows = []
            if selected_practice_id:
                docs_query = (
                    "SELECT d.id, t.kod, d.status, oe.imie || ' ' || oe.nazwisko AS ostatni, d.zaktualizowano "
                    "FROM dokument d "
                    "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                    "LEFT JOIN uzytkownik oe ON d.ostatni_edytor = oe.id "
                    "WHERE d.praktyka_id = :selected_practice_id AND (d.utworzony_przez = :user_id OR EXISTS(SELECT 1 FROM udostepniony_dokument ud WHERE ud.dokument_id = d.id "
                    "AND (ud.udostepniajacy = :user_id OR ud.adresat = :user_id OR ud.rola_id = :rola_id))) "
                )
                docs_params['selected_practice_id'] = selected_practice_id
                docs_rows = db.session.execute(text(docs_query), docs_params).fetchall()

        for dr in docs_rows:
            kod = dr[1] or ''
            label = kod.replace('ZAL_', 'Załącznik ') if kod.startswith('ZAL_') else kod
            my_documents.append({
                'id': dr[0],
                'label': label,
                'status': dr[2] or '',
                'ostatni': dr[3] or '',
                'zaktualizowano': dr[4] or '',
            })
    except Exception:
        current_app.logger.exception('Błąd pobierania dokumentów użytkownika')

    show_create_nav = role not in ['opiekun_uczelniany', 'dyrektor']
    show_practice_selection = role in ['dziekanat', 'opiekun_firmowy', 'opiekun_uczelniany', 'dyrektor', 'czlonek_komisji']
    show_company_edit = role == 'opiekun_firmowy'

    return render_template(
        'dashboard/index.html',
        uzytkownik=current_user,
        practice_rows=practice_rows,
        selected_practice=selected_practice,
        available_documents=available_documents,
        my_documents=my_documents,
        show_create_nav=show_create_nav,
        show_practice_selection=show_practice_selection,
        show_company_edit=show_company_edit,
    )


@bp.route('/profil/studenta', methods=['GET', 'POST'])
@login_required
def profil_studenta():
    """
    Strona uzupełniania danych studenta.
    Wymagane po zalogowaniu, jeśli konto studenta nie ma kompletnych danych.
    """
    from app import db
    from app.models.uzytkownik import Uzytkownik

    if current_user.rola.nazwa != 'student':
        flash('Tylko student może edytować swoje dane studenta.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        numer_albumu = request.form.get('numer_albumu', '').strip()
        specjalnosc = request.form.get('specjalnosc', '').strip()
        forma_studiow = request.form.get('forma_studiow', '').strip()
        rok_akademicki = request.form.get('rok_akademicki', '').strip()
        telefon = request.form.get('telefon', '').strip()

        if not numer_albumu or not specjalnosc or not forma_studiow or not rok_akademicki:
            flash('Numer albumu, specjalność, forma studiów i rok akademicki są wymagane.', 'danger')
        else:
            duplicate = Uzytkownik.query.filter(
                Uzytkownik.numer_albumu == numer_albumu,
                Uzytkownik.id != current_user.id
            ).first()
            if duplicate:
                flash('Podany numer albumu jest już używany przez innego studenta.', 'danger')
            else:
                try:
                    current_user.numer_albumu = numer_albumu
                    current_user.specjalnosc = specjalnosc
                    current_user.forma_studiow = forma_studiow
                    current_user.rok_akademicki = rok_akademicki
                    current_user.telefon = telefon

                    db.session.commit()
                    flash('Dane studenta zostały zapisane.', 'success')
                    return redirect(url_for('dashboard.index'))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f'Błąd zapisu danych studenta: {e}')
                    flash('Wystąpił błąd podczas zapisu. Spróbuj ponownie.', 'danger')

    return render_template(
        'profil/studenta.html',
        uzytkownik=current_user
    )


@bp.route('/formularz/zalacznik-1', methods=['GET', 'POST'])
@login_required
def zalacznik_1():
    """Formularz załącznika 1 - Porozumienie z zakładem pracy."""
    if current_user.rola.nazwa != 'dziekanat':
        flash('Tylko dziekanat może wypełniać załącznik 1.', 'danger')
        return redirect(url_for('dashboard.index'))

    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    if request.method == 'POST':
        form_data = {
            'nr_porozumienia': request.form.get('nr_porozumienia'),
            'data_zawarcia': request.form.get('data_zawarcia'),
            'nazwa_zakladu_pracy': request.form.get('nazwa_zakladu_pracy'),
            'reprezentant_uczelni_id': request.form.get('reprezentant_uczelni_id'),
            'reprezentant_firmy': request.form.get('reprezentant_firmy'),
            'imie_nazwisko_studenta': request.form.get('imie_nazwisko_studenta'),
            'student_id': request.form.get('student_id'),
            'termin_od': request.form.get('termin_od'),
            'termin_do': request.form.get('termin_do'),
            'wymiar_praktyki': request.form.get('wymiar_praktyki'),
        }

        saved = save_attachment1_data(form_data)
        if saved:
            flash('Dane załącznika 1 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    role_uczelni = Rola.query.filter_by(nazwa='opiekun_uczelniany').all()
    role_ids = [r.id for r in role_uczelni]
    reprezentanci_uczelni = (
        Uzytkownik.query
        .filter(Uzytkownik.rola_id.in_(role_ids), Uzytkownik.jest_aktywny == True)
        .order_by(Uzytkownik.nazwisko, Uzytkownik.imie)
        .all()
    ) if role_ids else []

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
            }
        # Pobierz opiekuna uczelnianego z wybranej praktyki aby móc prefillować pole
        opiekun_prefill = ''
        opiekun_row = db.session.execute(
            text("SELECT opiekun_uczelniany_id FROM praktyka WHERE id = :praktyka_id"),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if opiekun_row and opiekun_row[0]:
            op_id = opiekun_row[0]
            user_row = db.session.execute(
                text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                {'id': op_id}
            ).fetchone()
            if user_row:
                opiekun_prefill = f"{user_row[0]} {user_row[1]}"

    practice_rows = db.session.execute(text(
        "SELECT p.student_id, f.nazwa AS firma_nazwa, u.imie || ' ' || u.nazwisko AS reprezentant_firmy, p.data_rozpoczecia, p.data_zakonczenia "
        "FROM praktyka p "
        "JOIN firma f ON p.firma_id = f.id "
        "JOIN uzytkownik u ON p.opiekun_firmowy_id = u.id "
        "WHERE p.id IN (SELECT MAX(id) FROM praktyka GROUP BY student_id)"
    )).fetchall()

    student_practice = {}
    for row in practice_rows:
        student_practice[row[0]] = {
            'firma_nazwa': row[1] or '',
            'reprezentant_firmy': row[2] or '',
            'termin_od': row[3] or '',
            'termin_do': row[4] or ''
        }

    nr_porozumienia = generate_agreement_number()
    data_zawarcia = date.today().isoformat()

    return render_template(
        'forms/zalacznik_1.html',
        nr_porozumienia=nr_porozumienia,
        data_zawarcia=data_zawarcia,
        studenci=studenci,
        reprezentanci_uczelni=reprezentanci_uczelni,
        student_practice=student_practice,
        student_practice_json=json.dumps(student_practice),
        selected_student=selected_student,
    )


def save_attachment2_data(form_data):
    """Zapis załącznika 2 (Program praktyki zawodowej).

    Tworzy wpis w tabeli `dokument` powiązany z praktyką studenta,
    używając typu dokumentu ZAL_2 i ustawiając etap na 3.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Utworzono załącznik 2 (Program praktyki zawodowej): %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 2.')
            return False

        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_firmowy_id, opiekun_uczelniany_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_firmowy_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        opiekun_uczelniany_id = praktyka_row[2] if praktyka_row and len(praktyka_row) > 2 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 2.', student_id)
            return False

        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_2' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_2 przy zapisie załącznika 2.')
            return False

        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )

        doc_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = doc_row[0] if doc_row else None

        if dokument_id:
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_firmowy_id,
                        'rola_id': role_ids['opiekun_firmowy'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 2: {e}')
        return False


@bp.route('/formularz/zalacznik-2', methods=['GET', 'POST'])
@login_required
def zalacznik_2():
    """Formularz załącznika 2 - Program praktyki zawodowej.

    Tworzenie dokumentu: tylko rola `dziekanat` ma prawo tworzyć.
    Inni użytkownicy mogą jedynie przeglądać istniejące dokumenty
    (widok przeglądowy niezaimplementowany tutaj).
    """
    # Uprawnienia tworzenia
    if current_user.rola.nazwa != 'dziekanat':
        flash('Tylko dziekanat może utworzyć załącznik 2.', 'danger')
        return redirect(url_for('dashboard.index'))

    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    if request.method == 'POST':
        form_data = {
            'student_id': request.form.get('student_id')
        }
        saved = save_attachment2_data(form_data)
        if saved:
            flash('Załącznik 2 został utworzony.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas tworzenia dokumentu.', 'danger')

    from app.models.uzytkownik import Uzytkownik, Rola
    from app import db

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
            }

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = []
    if not selected_student and rola_student:
        studenci = (
            Uzytkownik.query
            .filter_by(rola_id=rola_student.id, jest_aktywny=True)
            .order_by(Uzytkownik.numer_albumu)
            .all()
        )

    # GET: pokaż ekran potwierdzenia utworzenia dokumentu
    return render_template('forms/zalacznik_2.html', studenci=studenci, selected_student=selected_student)


def save_attachment2a_data(form_data):
    """Zapis załącznika 2a (Program i harmonogram praktyki).

    Tworzy dokument i wpisy programu/harmonogramu dla 13 pozycji.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 2a: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        ppz_dzial = form_data.get('ppz_dzial', [])
        hpz_dzial = form_data.get('hpz_dzial', [])
        hpz_dni = form_data.get('hpz_dni', [])

        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 2a.')
            return False

        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_uczelniany_id, opiekun_firmowy_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_uczelniany_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        opiekun_firmowy_id = praktyka_row[2] if praktyka_row and len(praktyka_row) > 2 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 2a.', student_id)
            return False

        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_2A' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_2A przy zapisie załącznika 2a.')
            return False

        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )
        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()

        document_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = document_row[0] if document_row else None
        if not dokument_id:
            current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 2a.')
            return False

        for idx in range(13):
            numer = idx + 1
            ppz_value = ppz_dzial[idx].strip() if idx < len(ppz_dzial) else ''
            hpz_value = hpz_dzial[idx].strip() if idx < len(hpz_dzial) else ''
            hpz_value_days = hpz_dni[idx].strip() if idx < len(hpz_dni) else ''
            hpz_days = int(hpz_value_days) if hpz_value_days.isdigit() else 0

            db.session.execute(
                text(
                    "INSERT INTO program_harmonogram_praktyki (dokument_id, numer, ppz_dzial, hpz_dzial, hpz_dni)"
                    " VALUES (:dokument_id, :numer, :ppz, :hpz, :dni)"
                ),
                {
                    'dokument_id': dokument_id,
                    'numer': numer,
                    'ppz': ppz_value,
                    'hpz': hpz_value,
                    'dni': hpz_days,
                }
            )

        # Utwórz wpisy udostępnionego dokumentu
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_firmowy_id,
                    'rola_id': role_ids['opiekun_firmowy'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 2a: {e}')
        return False


@bp.route('/formularz/zalacznik-2a', methods=['GET', 'POST'])
@login_required
def zalacznik_2a():
    """Formularz załącznika 2a - Program i harmonogram praktyki zawodowej."""
    # Dokument tworzy: dziekanat (numer indeksu)
    # Edytowalne pola przez opiekuna firmowego: przykladowe_prace, dzial_komorka, planowana_liczba_dni

    role = current_user.rola.nazwa
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None
    # default fallbacks for prefilled opiekun (avoid NameError and provide id for template)
    opiekun_prefill = ''
    opiekun_prefill_id = None
    # default fallback for prefilled opiekun (avoids NameError when no practice selected)
    opiekun_prefill = ''

    # Tworzenie dokumentu tylko przez dziekanat
    if request.method == 'POST':
        if role == 'dziekanat':
            form_data = {
                'student_id': request.form.get('student_id'),
                'nr_indeksu': request.form.get('nr_indeksu'),
                'data_uzgodnienia': request.form.get('data_uzgodnienia') or date.today().isoformat(),
                'ppz_dzial': request.form.getlist('ppz_dzial[]'),
                'hpz_dzial': request.form.getlist('hpz_dzial[]'),
                'hpz_dni': request.form.getlist('hpz_dni[]'),
            }
        elif role == 'opiekun_firmowy':
            form_data = {
                'student_id': request.form.get('student_id'),
                'przykladowe_prace': request.form.get('przykladowe_prace'),
                'dzial_komorka': request.form.get('dzial_komorka'),
                'planowana_liczba_dni': request.form.get('planowana_liczba_dni'),
                'data_uzgodnienia': request.form.get('data_uzgodnienia') or date.today().isoformat(),
                'ppz_dzial': request.form.getlist('ppz_dzial[]'),
                'hpz_dzial': request.form.getlist('hpz_dzial[]'),
                'hpz_dni': request.form.getlist('hpz_dni[]'),
            }
        else:
            flash('Nie masz uprawnień do edycji tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        saved = save_attachment2a_data(form_data)
        if saved:
            flash('Dane załącznika 2a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # Przygotowanie pól prefilled (jeśli dostępne)
    # TODO: pobrać rzeczywiste dane z bazy (załącznik 1 / dane studenta)
    data_uzgodnienia = date.today().isoformat()
    imie_nazwisko_studenta = ''
    specjalnosc = ''
    miejsce_praktyki = ''
    termin_od = ''
    termin_do = ''

    # Pobierz listę studentów i ostatnie dane praktyki (do autouzupełniania)
    from app.models.uzytkownik import Uzytkownik, Rola
    from app import db
    from sqlalchemy import text

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc, f.nazwa AS firma_nazwa, "
                "up.imie || ' ' || up.nazwisko AS reprezentant_firmy, p.data_rozpoczecia, p.data_zakonczenia "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "LEFT JOIN firma f ON p.firma_id = f.id "
                "LEFT JOIN uzytkownik up ON p.opiekun_firmowy_id = up.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
                'specjalnosc': student_row[4] or '',
                'firma_nazwa': student_row[5] or '',
                'reprezentant_firmy': student_row[6] or '',
                'termin_od': student_row[7] or '',
                'termin_do': student_row[8] or '',
            }

    practice_rows = db.session.execute(text(
        "SELECT p.student_id, f.nazwa AS firma_nazwa, u.imie || ' ' || u.nazwisko AS reprezentant_firmy, p.data_rozpoczecia, p.data_zakonczenia "
        "FROM praktyka p "
        "JOIN firma f ON p.firma_id = f.id "
        "JOIN uzytkownik u ON p.opiekun_firmowy_id = u.id "
        "WHERE p.id IN (SELECT MAX(id) FROM praktyka GROUP BY student_id)"
    )).fetchall()

    student_practice = {}
    for row in practice_rows:
        student_practice[row[0]] = {
            'firma_nazwa': row[1] or '',
            'reprezentant_firmy': row[2] or '',
            'termin_od': row[3] or '',
            'termin_do': row[4] or ''
        }

    # Pobierz maksymalnie 13 efektów uczenia
    from app import db
    from sqlalchemy import text
    efekty_rows = db.session.execute(text("SELECT id, numer, opis FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()
    efekty = [{'id': r[0], 'numer': r[1], 'opis': r[2]} for r in efekty_rows]

    return render_template(
        'forms/zalacznik_2a.html',
        data_uzgodnienia=data_uzgodnienia,
        imie_nazwisko_studenta=imie_nazwisko_studenta,
        specjalnosc=specjalnosc,
        miejsce_praktyki=miejsce_praktyki,
        termin_od=termin_od,
        termin_do=termin_do,
        studenci=studenci,
        student_practice=student_practice,
        student_practice_json=json.dumps(student_practice),
        selected_student=selected_student,
        efekty=efekty,
    )


def save_attachment3_data(form_data):
    """Zapis załącznika 3 (Karta praktyki zawodowej).

    Tworzy dokument na etapie 5, zapisuje dane dokumentu i zmienia status praktyki.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 3: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 3.')
            return False

        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_uczelniany_id, opiekun_firmowy_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_uczelniany_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        opiekun_firmowy_id = praktyka_row[2] if praktyka_row and len(praktyka_row) > 2 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 3.', student_id)
            return False

        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_3' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_3 przy zapisie załącznika 3.')
            return False

        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )
        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()

        document_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = document_row[0] if document_row else None
        if not dokument_id:
            current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 3.')
            return False

        # Utwórz wpisy udostępnionego dokumentu
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_firmowy_id,
                    'rola_id': role_ids['opiekun_firmowy'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        db.session.commit()


        dane_map = {
            'miejscowość': form_data.get('miejscowosc', ''),
            'data_kier': form_data.get('data_podpisu_firmowego', ''),
            'uwagi_kier': form_data.get('uwagi', ''),
            'ocena_przebiegu_of': form_data.get('ocena_przebiegu_1', ''),
            'ocena_opisowa_of': form_data.get('ocena_opisowa_1', ''),
            'data_przebiegu_of': form_data.get('data_przebiegu_1', ''),
            'ocena_przebiegu_ou': form_data.get('ocena_przebiegu_2', ''),
            'ocena_opisowa_ou': form_data.get('ocena_opisowa_2', ''),
            'data_przebiegu_ou': form_data.get('data_przebiegu_2', ''),
            'ocena_sprawozdania': form_data.get('ocena_sprawozdania', ''),
            'data_sprawozdania': form_data.get('data_sprawozdania', ''),
        }

        for klucz, wartosc in dane_map.items():
            db.session.execute(
                text(
                    "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                    "VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
                ),
                {
                    'doc_id': dokument_id,
                    'klucz': klucz,
                    'wartosc': wartosc,
                    'wypelniajacy': current_user.id,
                }
            )

        db.session.execute(
            text("UPDATE praktyka SET status='active' WHERE id=:praktyka_id"),
            {'praktyka_id': praktyka_id}
        )
        db.session.commit()

        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 3: {e}')
        return False


@bp.route('/formularz/zalacznik-3', methods=['GET', 'POST'])
@login_required
def zalacznik_3():
    """Formularz załącznika 3 - Karta praktyki zawodowej."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    practice_rows = db.session.execute(text(
        "SELECT p.student_id, p.id AS praktyka_id, f.nazwa AS firma_nazwa, "
        "uf.imie || ' ' || uf.nazwisko AS firmowy_opiekun, uf.stanowisko AS firmowy_stanowisko, "
        "uu.imie || ' ' || uu.nazwisko AS uczelniany_opiekun, p.data_rozpoczecia, p.data_zakonczenia "
        "FROM praktyka p "
        "JOIN firma f ON p.firma_id = f.id "
        "LEFT JOIN uzytkownik uf ON p.opiekun_firmowy_id = uf.id "
        "LEFT JOIN uzytkownik uu ON p.opiekun_uczelniany_id = uu.id "
        "WHERE p.id IN (SELECT MAX(id) FROM praktyka GROUP BY student_id)"
    )).fetchall()

    student_practice = {}
    for row in practice_rows:
        student_id, praktyka_id, firma_nazwa, firmowy_opiekun, firmowy_stanowisko, uczelniany_opiekun, termin_od, termin_do = row
        nr_porozumienia = ''
        data_zawarcia = ''
        nazwa_zakladu_pracy = firma_nazwa or ''
        termin_od_value = termin_od or ''
        termin_do_value = termin_do or ''

        document_row = db.session.execute(text(
            "SELECT d.id FROM dokument d "
            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_1' "
            "ORDER BY d.id DESC LIMIT 1"
        ), {'praktyka_id': praktyka_id}).fetchone()
        if document_row:
            dokument_id = document_row[0]
            data_rows = db.session.execute(text(
                "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"
            ), {'dokument_id': dokument_id}).fetchall()
            for key, value in data_rows:
                if key == 'nr_porozumienia':
                    nr_porozumienia = value or nr_porozumienia
                elif key == 'data_zawarcia':
                    data_zawarcia = value or data_zawarcia
                elif key == 'nazwa_zakladu_pracy':
                    nazwa_zakladu_pracy = value or nazwa_zakladu_pracy
                elif key == 'termin_od':
                    termin_od_value = value or termin_od_value
                elif key == 'termin_do':
                    termin_do_value = value or termin_do_value

        student_practice[student_id] = {
            'firma_nazwa': firma_nazwa or '',
            'firmowy_opiekun': firmowy_opiekun or '',
            'firmowy_stanowisko': firmowy_stanowisko or '',
            'uczelniany_opiekun': uczelniany_opiekun or '',
            'nr_porozumienia': nr_porozumienia,
            'data_zawarcia': data_zawarcia,
            'nazwa_zakladu_pracy': nazwa_zakladu_pracy,
            'termin_od': termin_od_value,
            'termin_do': termin_do_value,
        }

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.forma_studiow, u.specjalnosc "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
                'forma_studiow': student_row[4] or '',
                'specjalnosc': student_row[5] or '',
            }

    if request.method == 'POST':
        form_data = {
            'status': 'updated_by_' + role,
            'student_id': request.form.get('student_id'),
            'nr_indeksu': request.form.get('nr_indeksu'),
            'data_potwierdzenia_1': request.form.get('data_potwierdzenia_1'),
            'data_potwierdzenia_2': request.form.get('data_potwierdzenia_2'),
            'uwagi': request.form.get('uwagi'),
            'miejscowosc': request.form.get('miejscowosc'),
            'data_podpisu_firmowego': request.form.get('data_podpisu_firmowego'),
            'ocena_przebiegu_1': request.form.get('ocena_przebiegu_1'),
            'ocena_opisowa_1': request.form.get('ocena_opisowa_1'),
            'data_przebiegu_1': request.form.get('data_przebiegu_1'),
            'ocena_przebiegu_2': request.form.get('ocena_przebiegu_2'),
            'ocena_opisowa_2': request.form.get('ocena_opisowa_2'),
            'data_przebiegu_2': request.form.get('data_przebiegu_2'),
            'ocena_sprawozdania': request.form.get('ocena_sprawozdania'),
            'data_sprawozdania': request.form.get('data_sprawozdania'),
        }

        saved = save_attachment3_data(form_data)
        if saved:
            flash('Dane załącznika 3 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # TODO: pobrać rzeczywiste dane prefilled z bazy na podstawie numeru indeksu / załącznika 1
    prefilled = {
        'nr_porozumienia': 'POR-0001',
        'data_zawarcia': date.today().isoformat(),
        'nazwa_zakladu_pracy': 'Przykładowy Zakład',
        'imie_nazwisko_studenta': '',
        'forma_studiow': '',
        'specjalnosc': '',
        'uczelniany_opiekun': '',
        'firmowy_opiekun': '',
        'firmowy_stanowisko': '',
        'termin_od': '',
        'termin_do': '',
        'rok_akademicki': '',
    }

    return render_template(
        'forms/zalacznik_3.html',
        role=role,
        studenci=studenci,
        student_practice=student_practice,
        selected_student=selected_student,
        **prefilled
    )


def save_attachment4_data(form_data):
    """Zapis załącznika 4 (Potwierdzenie efektów uczenia się)."""
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 4: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 4.')
            return False

        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_firmowy_id, opiekun_uczelniany_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_firmowy_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        opiekun_uczelniany_id = praktyka_row[2] if praktyka_row and len(praktyka_row) > 2 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 4.', student_id)
            return False

        typ_row = db.session.execute(text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_4' LIMIT 1")).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_4 przy zapisie załącznika 4.')
            return False

        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )
        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()

        dokument_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = dokument_row[0] if dokument_row else None
        if not dokument_id:
            current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 4.')
            return False

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_firmowy_id,
                    'rola_id': role_ids['opiekun_firmowy'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        efekty_values = form_data.get('efekt_uzyskany', []) or []
        oceniono = '1' if form_data.get('opinia_opiekuna_uczelnianego', '').strip() else '0'

        efekt_rows = db.session.execute(text("SELECT id FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()
        for idx, row in enumerate(efekt_rows):
            efekt_id = row[0]
            uzyskany_value = efekty_values[idx] if idx < len(efekty_values) else '0'
            status = 'achieved' if str(uzyskany_value) == '1' else 'not_achieved'

            db.session.execute(
                text(
                    "INSERT OR REPLACE INTO efekt_uczenia_dokumentu (dokument_id, efekt_id, status, ocenione_przez)"
                    " VALUES (:doc_id, :efekt_id, :status, :ocenione_przez)"
                ),
                {
                    'doc_id': dokument_id,
                    'efekt_id': efekt_id,
                    'status': status,
                    'ocenione_przez': opiekun_firmowy_id,
                }
            )

        dane_map = {
            'opinia_opiekuna_uczelnianego': form_data.get('opinia_opiekuna_uczelnianego', ''),
            'data_opinii': form_data.get('data_opinii', ''),
        }

        for klucz, wartosc in dane_map.items():
            db.session.execute(
                text(
                    "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez)"
                    " VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
                ),
                {
                    'doc_id': dokument_id,
                    'klucz': klucz,
                    'wartosc': wartosc,
                    'wypelniajacy': current_user.id,
                }
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 4: {e}')
        return False


@bp.route('/formularz/zalacznik-4', methods=['GET', 'POST'])
@login_required
def zalacznik_4():
    """Formularz załącznika 4 - Potwierdzenie efektów uczenia się."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
                'specjalnosc': student_row[4] or '',
            }

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_firmowy', 'opiekun_uczelniany']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'student_id': request.form.get('student_id'),
            'nr_indeksu': request.form.get('nr_indeksu'),
            'efekt_uzyskany': request.form.getlist('efekt_uzyskany[]'),
            'opinia_opiekuna_uczelnianego': request.form.get('opinia_opiekuna_uczelnianego'),
            'data_opinii': request.form.get('data_opinii'),
        }

        saved = save_attachment4_data(form_data)
        if saved:
            flash('Dane załącznika 4 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': f"{selected_student['imie']} {selected_student['nazwisko']}" if selected_student else '',
        'specjalnosc': selected_student['specjalnosc'] if selected_student else '',
        'ilosc_godzin_praktyk': '',
        'nr_indeksu': selected_student['numer_albumu'] if selected_student else '',
        'opinia_opiekuna_uczelnianego': '',
        'data_opinii': date.today().isoformat(),
    }

    # Pobierz maksymalnie 13 efektów uczenia
    efekty_rows = db.session.execute(text("SELECT id, numer, opis FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()
    efekty = [{'id': r[0], 'numer': r[1], 'opis': r[2]} for r in efekty_rows]

    return render_template(
        'forms/zalacznik_4.html',
        role=role,
        studenci=studenci,
        selected_student=selected_student,
        efekty=efekty,
        **prefilled
    )


def save_attachment4a_data(form_data):
    from app import db
    from sqlalchemy import text

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None

        if not student_id:
            current_app.logger.error(
                'Brak wybranego studenta przy zapisie załącznika 4a.'
            )
            return False

        praktyka_row = db.session.execute(
            text("""
                SELECT id, opiekun_uczelniany_id FROM praktyka WHERE student_id = :student_id ORDER BY id DESC LIMIT 1
            """),
            {'student_id': student_id}
        ).fetchone()

        if not praktyka_row:
            current_app.logger.error(
                'Nie znaleziono praktyki dla studenta %s',
                student_id
            )
            return False

        praktyka_id = praktyka_row[0]
        opiekun_uczelniany_id = praktyka_row[1] if len(praktyka_row) > 1 else None

        # aktualizacja liczby godzin
        db.session.execute(
            text("""
                UPDATE praktyka SET liczba_godzin = :liczba_godzin, zaktualizowano = datetime('now') WHERE id = :praktyka_id
            """),
            {
                'liczba_godzin': int(form_data.get('ilosc_godzin_praktyk') or 0),
                'praktyka_id': praktyka_id
            }
        )

        typ_row = db.session.execute(
            text("""
                SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4A' LIMIT 1
            """)
        ).fetchone()

        if not typ_row:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_4A')
            return False

        typ_id = typ_row[0]

        dokument_row = db.session.execute(
            text("""
                SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id LIMIT 1
            """),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id
            }
        ).fetchone()

        if dokument_row:
            dokument_id = dokument_row[0]

            db.session.execute(
                text("""
                    UPDATE dokument SET status = 'completed', aktualny_etap = 2, zaktualizowano = datetime('now') WHERE id = :id
                """),
                {'id': dokument_id}
            )
            update_practice_stage_from_typ(praktyka_id, typ_id)
        else:
            db.session.execute(
                text("""
                    INSERT INTO dokument ( praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor )
                    VALUES ( :praktyka_id, :typ_id, :uzytkownik_id, 'completed', :ostatni_edytor )
                """),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'uzytkownik_id': current_user.id,
                    'ostatni_edytor': current_user.id
                }
            )
            update_practice_stage_from_typ(praktyka_id, typ_id)
            dokument_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()

        efekt_rows = db.session.execute(
            text("""
                SELECT id FROM efekt_uczenia ORDER BY numer LIMIT 13
            """)
        ).fetchall()

        status_map = {
            '0': 'not_achieved',
            '1': 'partial',
            '2': 'achieved'
        }

        efekty_values = form_data.get('efekt_uzyskany', [])

        for idx, row in enumerate(efekt_rows):

            efekt_id = row[0]

            value = (
                efekty_values[idx]
                if idx < len(efekty_values)
                else '0'
            )

            status = status_map.get(value, 'not_achieved')

            istnieje = db.session.execute(
                text("""
                    SELECT id FROM efekt_uczenia_dokumentu WHERE dokument_id = :doc_id AND efekt_id = :efekt_id
                """),
                {
                    'doc_id': dokument_id,
                    'efekt_id': efekt_id
                }
            ).fetchone()

            if istnieje:
                db.session.execute(
                    text("""
                        UPDATE efekt_uczenia_dokumentu SET status, ocenione_przez = :ocenione_przez = :status WHERE id = :id
                    """),
                    {
                        'status': status,
                        'ocenione_przez': current_user.id,
                        'id': istnieje[0]
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO efekt_uczenia_dokumentu ( dokument_id, efekt_id, status, ocenione_przez )
                        VALUES ( :doc_id, :efekt_id, :status, :ocenione_przez )
                    """),
                    {
                        'doc_id': dokument_id,
                        'efekt_id': efekt_id,
                        'status': status,
                        'ocenione_przez': current_user.id
                    }
                )

        istnieje = db.session.execute(
            text("""
                SELECT id FROM dane_dokumentu WHERE dokument_id = :doc_id AND klucz = 'data_wyniku_komisji'
            """),
            {'doc_id': dokument_id}
        ).fetchone()

        if istnieje:
            db.session.execute(
                text("""
                    UPDATE dane_dokumentu SET wartosc = :wartosc, wypelnione_przez = :user_id WHERE id = :id
                """),
                {
                    'wartosc': form_data.get(
                        'data_wyniku_komisji'
                    ),
                    'user_id': current_user.id,
                    'id': istnieje[0]
                }
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO dane_dokumentu ( dokument_id, klucz, wartosc, wypelnione_przez )
                    VALUES ( :doc_id, 'data_wyniku_komisji', :wartosc, :user_id )
                """),
                {
                    'doc_id': dokument_id,
                    'wartosc': form_data.get(
                        'data_wyniku_komisji'
                    ),
                    'user_id': current_user.id
                }
            )

        # Utwórz wpisy udostępnionego dokumentu
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','dyrektor','czlonek_komisji')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        if role_ids.get('czlonek_komisji'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['czlonek_komisji'],
                }
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        return False


@bp.route('/formularz/zalacznik-4a', methods=['GET', 'POST'])
@login_required
def zalacznik_4a():
    """Formularz załącznika 4a - Potwierdzenie uzyskania efektów uczenia się."""
    if current_user.rola.nazwa != 'dziekanat':
        flash('Tylko dziekanat może wypełniać załącznik 4a.', 'danger')
        return redirect(url_for('dashboard.index'))

    from app.models.uzytkownik import Uzytkownik, Rola
    from app import db
    from sqlalchemy import text

    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    if request.method == 'POST':
        form_data = {
            'student_id': request.form.get('student_id'),
            'nr_indeksu': request.form.get('nr_indeksu'),
            'ilosc_godzin_praktyk': request.form.get('ilosc_godzin_praktyk'),
            'efekt_uzyskany': request.form.getlist('efekt_uzyskany[]'),
            'data_wyniku_komisji': request.form.get('data_wyniku_komisji'),
        }

        saved = save_attachment4a_data(form_data)
        if saved:
            flash('Dane załącznika 4a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')
    
    # Pobierz studenta z wybranej praktyki
    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
                'specjalnosc': student_row[4] or '',
            }
    
    efekty_rows = db.session.execute(
        text("""
            SELECT id, numer, opis
            FROM efekt_uczenia
            ORDER BY numer
        """)
    ).fetchall()

    efekty = [
        {
            'id': r[0],
            'numer': r[1],
            'opis': r[2]
        }
        for r in efekty_rows
    ]

    prefilled = {
        'imie_nazwisko_studenta': '',
        'specjalnosc': selected_student['specjalnosc'] if selected_student else '',
        'ilosc_godzin_praktyk': '',
        'nr_indeksu': selected_student['numer_albumu'] if selected_student else '',
        'wynik_komisji': '',
        'data_wyniku_komisji': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_4a.html',
        role=current_user.rola.nazwa,
        studenci=[],
        selected_student=selected_student,
        efekty=efekty,
        **prefilled
    )


def save_attachment4b_data(form_data):
    from app import db
    from sqlalchemy import text

    try:
        student_id = current_user.id
        opiekun_uczelniany_id = int(form_data.get('opiekun_uczelniany_id')) if form_data.get('opiekun_uczelniany_id') else None

        rok_akademicki = f"{date.today().year - 1}/{date.today().year}"

        # praktyka
        praktyka = db.session.execute(
            text("""
                SELECT id FROM praktyka WHERE student_id = :student_id AND sciezka = 'alternative' LIMIT 1
            """),
            {"student_id": student_id}
        ).fetchone()

        if praktyka:
            praktyka_id = praktyka[0]

            db.session.execute(
                text("""
                    UPDATE praktyka SET status = 'active', zaktualizowano = datetime('now')
                        WHERE id = :id
                """),
                {"id": praktyka_id}
            )
            if opiekun_uczelniany_id:
                db.session.execute(
                    text("""
                        UPDATE praktyka SET opiekun_uczelniany_id = :opiekun_id WHERE id = :id
                    """),
                    {
                        "opiekun_id": opiekun_uczelniany_id,
                        "id": praktyka_id
                    }
                )
        else:
            db.session.execute(
                text("""
                    INSERT INTO praktyka ( student_id, firma_id, opiekun_firmowy_id, opiekun_uczelniany_id, sciezka, status,
                        liczba_dni_roboczych, liczba_godzin, rok_akademicki
                    )
                    VALUES ( :student_id, NULL, NULL, :opiekun_uczelniany_id, 'alternative', 'active', NULL, NULL, :rok_akademicki )
                """),
                {
                    "student_id": student_id,
                    "opiekun_uczelniany_id": opiekun_uczelniany_id,
                    "rok_akademicki": rok_akademicki
                }
            )

            praktyka_id = db.session.execute(
                text("SELECT last_insert_rowid()")
            ).scalar()

        # typ dokumentu
        typ_dokumentu_id = db.session.execute(
            text("""
                SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B'
            """)
        ).scalar()

        # dokument
        dokument = db.session.execute(
            text("""
                SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_dokumentu_id LIMIT 1
            """),
            {
                "praktyka_id": praktyka_id,
                "typ_dokumentu_id": typ_dokumentu_id
            }
        ).fetchone()

        if dokument:
            dokument_id = dokument[0]

            db.session.execute(
                text("""
                    UPDATE dokument SET status = 'completed', aktualny_etap = 1, zaktualizowano = datetime('now') WHERE id = :id
                """),
                {"id": dokument_id}
            )
            update_practice_stage_from_typ(praktyka_id, typ_dokumentu_id)
        else:
            db.session.execute(
                text("""
                    INSERT INTO dokument ( praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor )
                    VALUES ( :praktyka_id, :typ_dokumentu_id, :uzytkownik_id, 'completed', :ostatni_edytor )
                """),
                {
                    "praktyka_id": praktyka_id,
                    "typ_dokumentu_id": typ_dokumentu_id,
                    "uzytkownik_id": current_user.id,
                    'ostatni_edytor': current_user.id
                }
            )
            update_practice_stage_from_typ(praktyka_id, typ_dokumentu_id)

            dokument_id = db.session.execute(
                text("SELECT last_insert_rowid()")
            ).scalar()

        if dokument_id:
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','dyrektor','czlonek_komisji')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            if role_ids.get('czlonek_komisji'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )

        pola = {
            'uzasadnienie': form_data.get('uzasadnienie'),
            'data_uzasadnienia': form_data.get('data_uzasadnienia'),
            'opinia_komisji': form_data.get('opinia_komisji'),
            'data_opinii_komisji': form_data.get('data_opinii_komisji'),
            'decyzja_dyrektora': form_data.get('decyzja_dyrektora'),
            'efekty_do_zaliczenia': form_data.get('efekty_do_zaliczenia'),
            'data_decyzji_dyrektora': form_data.get('data_decyzji_dyrektora')
        }

        for klucz, wartosc in pola.items():

            istnieje = db.session.execute(
                text("""
                    SELECT id FROM dane_dokumentu WHERE dokument_id = :dokument_id AND klucz = :klucz
                """),
                {
                    "dokument_id": dokument_id,
                    "klucz": klucz
                }
            ).fetchone()

            if istnieje:
                db.session.execute(
                    text("""
                        UPDATE dane_dokumentu SET wartosc = :wartosc WHERE id = :id
                    """),
                    {
                        "wartosc": wartosc,
                        "id": istnieje[0]
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO dane_dokumentu ( dokument_id, klucz, wartosc, wypelnione_przez )
                        VALUES ( :dokument_id, :klucz, :wartosc, :uzytkownik_id )
                    """),
                    {
                        "dokument_id": dokument_id,
                        "klucz": klucz,
                        "wartosc": wartosc,
                        "uzytkownik_id": current_user.id
                    }
                )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        return False


@bp.route('/formularz/zalacznik-4b', methods=['GET', 'POST'])
@login_required
def zalacznik_4b():
    """Formularz załącznika 4b - Wniosek o zaliczenie efektów uczenia się."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['student', 'czlonek_komisji', 'dyrektor']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'opiekun_uczelniany_id': request.form.get('opiekun_uczelniany_id'),
            'uzasadnienie': request.form.get('uzasadnienie'),
            'data_uzasadnienia': request.form.get('data_uzasadnienia'),
            'opinia_komisji': request.form.get('opinia_komisji'),
            'data_opinii_komisji': request.form.get('data_opinii_komisji'),
            'decyzja_dyrektora': request.form.get('decyzja_dyrektora'),
            'efekty_do_zaliczenia': request.form.get('efekty_do_zaliczenia'),
            'data_decyzji_dyrektora': request.form.get('data_decyzji_dyrektora'),
        }

        saved = save_attachment4b_data(form_data)
        if saved:
            flash('Dane załącznika 4b zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    student_data = db.session.execute(
        text("""
            SELECT
                u.imie,
                u.nazwisko,
                u.numer_albumu,
                u.specjalnosc
            FROM uzytkownik u
            WHERE u.id = :student_id
        """),
        {"student_id": current_user.id}
    ).fetchone()

    from app.models.uzytkownik import Uzytkownik, Rola

    rola_opiekun_uczelniany = Rola.query.filter_by(nazwa='opiekun_uczelniany').first()
    opiekunowie_uczelni = (
        Uzytkownik.query
        .filter_by(rola_id=rola_opiekun_uczelniany.id, jest_aktywny=True)
        .order_by(Uzytkownik.nazwisko, Uzytkownik.imie)
        .all()
    ) if rola_opiekun_uczelniany else []

    imie_nazwisko_studenta = ''
    nr_indeksu = ''
    specjalnosc = ''

    if student_data:
        imie_nazwisko_studenta = f"{student_data[0]} {student_data[1]}"
        nr_indeksu = student_data[2] or ''
        specjalnosc = student_data[3] or ''

    prefilled = {
        'imie_nazwisko_studenta': imie_nazwisko_studenta,
        'specjalnosc': specjalnosc,
        'nr_indeksu': nr_indeksu,
        'data_zlozenia': date.today().isoformat(),
        'uzasadnienie': '',
        'data_uzasadnienia': date.today().isoformat(),
        'opinia_komisji': '',
        'data_opinii_komisji': date.today().isoformat(),
        'decyzja_dyrektora': '',
        'data_decyzji_dyrektora': date.today().isoformat(),
        'selected_opiekun_uczelniany_id': '',
    }

    return render_template(
        'forms/zalacznik_4b.html',
        role=role,
        opiekunowie_uczelni=opiekunowie_uczelni,
        **prefilled
    )


def save_attachment5_data(form_data):
    """Zapis załącznika 5 (Kwestionariusz ankiety).

    Tworzy wpis w tabeli ankieta_dane oraz 14 wpisów w tabeli odpowiedz_ankiety.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 5: %s', form_data)

    try:
        student_id = current_user.id

        # Pobierz praktykę studenta
        praktyka_row = db.session.execute(
            text("SELECT id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 5.', student_id)
            return False

        # Znajdź typ dokumentu ZAL_5
        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_5' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_5 przy zapisie załącznika 5.')
            return False

        # Pobierz pytania ankiety
        pytania_rows = db.session.execute(
            text("SELECT id FROM pytanie_ankiety ORDER BY numer LIMIT 14")
        ).fetchall()

        # Pobierz odpowiedzi z formularza
        odpowiedzi = form_data.get('odpowiedz', []) or []
        if not isinstance(odpowiedzi, list):
            odpowiedzi = [odpowiedzi]

        # Wstaw 14 wpisów do odpowiedz_ankiety
        for idx, pytanie_row in enumerate(pytania_rows):
            pytanie_id = pytanie_row[0]
            wartosc = odpowiedzi[idx] if idx < len(odpowiedzi) else ''

            db.session.execute(
                text(
                    "INSERT INTO odpowiedz_ankiety (pytanie_id, odpowiedz)"
                    " VALUES (:pytanie_id, :wartosc)"
                ),
                {
                    'pytanie_id': pytanie_id,
                    'wartosc': wartosc,
                }
            )

        # Dane studenta i uwagi do ankieta_dane
        dodatkowe_uwagi = form_data.get('dodatkowe_uwagi', '') or ''
        rok_akademicki = form_data.get('rok_akademicki', '') or ''
        specjalnosc = form_data.get('specjalnosc', '') or ''
        forma_studiow = form_data.get('forma_studiow', '') or ''
        semestr = form_data.get('semestr', '') or ''
        liczba_godzin = form_data.get('liczba_godzin', '') or ''

        # Wstaw wpis do ankieta_dane
        db.session.execute(
            text(
                "INSERT INTO ankieta_dane (uwagi, rok_akademicki, specjalnosc, forma_studiow, semestr, liczba_godzin)"
                " VALUES (:uwagi, :rok, :specjalnosc, :forma, :semestr, :godziny)"
            ),
            {
                'uwagi': dodatkowe_uwagi,
                'rok': rok_akademicki,
                'specjalnosc': specjalnosc,
                'forma': forma_studiow,
                'semestr': semestr,
                'godziny': liczba_godzin,
            }
        )

        # Zaktualizuj etap praktyki
        if typ_id:
            update_practice_stage_from_typ(praktyka_id, typ_id)
        else:
            # Jeśli typ nie istnieje, zaktualizuj bezpośrednio na etap 10
            db.session.execute(
                text("UPDATE praktyka SET aktualny_etap = 10 WHERE id = :praktyka_id"),
                {'praktyka_id': praktyka_id}
            )

        db.session.commit()
        current_app.logger.info('Dane załącznika 5 zapisane.')
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 5: {e}')
        return False


@bp.route('/formularz/zalacznik-5', methods=['GET', 'POST'])
@login_required
def zalacznik_5():
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role != 'student':
            flash('Tylko student może zapisać ankietę.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'odpowiedz': request.form.getlist('odpowiedz[]'),
            'dodatkowe_uwagi': request.form.get('dodatkowe_uwagi'),
            'rok_akademicki': request.form.get('rok_akademicki'),
            'specjalnosc': request.form.get('specjalnosc'),
            'forma_studiow': request.form.get('forma_studiow'),
            'semestr': request.form.get('semestr'),
            'liczba_godzin': request.form.get('liczba_godzin'),
        }

        saved = save_attachment5_data(form_data)
        if saved:
            flash('Dane załącznika 5 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    student_data = db.session.execute(
        text("""
            SELECT p.rok_akademicki,
                u.specjalnosc,
                u.forma_studiow,
                p.liczba_godzin
            FROM praktyka p
            JOIN uzytkownik u ON p.student_id = u.id
            WHERE p.student_id = :student_id
            ORDER BY p.id DESC
            LIMIT 1
        """),
        {"student_id": current_user.id}
    ).fetchone()

    rok_akademicki = student_data[0] if student_data else ''
    specjalnosc = student_data[1] if student_data else ''
    forma_studiow = student_data[2] if student_data else ''
    liczba_godzin = student_data[3] if student_data else ''

    prefilled = {
        'rok_akademicki': rok_akademicki,
        'specjalnosc': specjalnosc,
        'forma_studiow': forma_studiow,
        'semestr': '7',
        'ilosc_godzin_praktyki': liczba_godzin,
        'odpowiedz': '',
        'dodatkowe_uwagi': '',
    }

    pytania_rows = db.session.execute(
        text(
            "SELECT id, numer, tresc_pytania "
            "FROM pytanie_ankiety "
            "ORDER BY numer LIMIT 14"
        )
    ).fetchall()

    pytania = [
        {'id': r[0], 'numer': r[1], 'tresc_pytania': r[2]}
        for r in pytania_rows
    ]

    return render_template(
        'forms/zalacznik_5.html',
        role=role,
        pytania=pytania,
        **prefilled
    )


def save_attachment6_data(form_data):
    """Zapis załącznika 6 (Dziennik praktyki zawodowej).

    Tworzy dokument (etap 6), wpisy w `wpis_dziennika` oraz wpisy w `dane_dokumentu`
    dla listy załączników i uwag opiekuna.
    """
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    current_app.logger.debug('Zapis załącznika 6: %s', form_data)

    try:
        # Determine student_id: if current user is student, use that, else require it in form_data
        student_id = None
        if current_user.rola.nazwa == 'student':
            student_id = current_user.id
        else:
            # try to read from form (if provided)
            student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None

        if not student_id:
            current_app.logger.error('Brak id studenta przy zapisie załącznika 6.')
            return False

        # find latest practice for student
        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_firmowy_id, opiekun_uczelniany_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_firmowy_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        opiekun_uczelniany_id = praktyka_row[2] if praktyka_row and len(praktyka_row) > 2 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 6.', student_id)
            return False

        # find document type id for ZAL_6
        typ_row = db.session.execute(text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_6' LIMIT 1")).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_6 przy zapisie załącznika 6.')
            return False

        # create dokument
        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )
        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()

        document_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = document_row[0] if document_row else None
        if not dokument_id:
            current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 6.')
            return False

        # udostępniony_dokument entries
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_firmowy_id,
                    'rola_id': role_ids['opiekun_firmowy'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        # Insert journal entries (wpis_dziennika) for each provided row
        dzien = form_data.get('dzien', []) or []
        data_list = form_data.get('data', []) or []
        opis_list = form_data.get('opis', []) or []
        efekty_rows = form_data.get('efekty_rows', []) or []
        efekty_list = form_data.get('efekty', []) or []
        uwagi_list = form_data.get('uwagi', []) or []

        today = datetime.now().date().isoformat()
        for idx in range(len(dzien)):
            try:
                numer_dnia = int(dzien[idx]) if dzien[idx] is not None and str(dzien[idx]).strip() != '' else (idx + 1)
            except Exception:
                numer_dnia = idx + 1
            data_wpisu = data_list[idx].strip() if idx < len(data_list) and data_list[idx] else today
            opis_prac = opis_list[idx].strip() if idx < len(opis_list) and opis_list[idx] else ''
            uwagi_opiekuna = uwagi_list[idx].strip() if idx < len(uwagi_list) and uwagi_list[idx] else ''

            db.session.execute(
                text(
                    "INSERT INTO wpis_dziennika (dokument_id, numer_dnia, data_wpisu, opis_prac, uwagi_opiekuna, jest_podpisany)"
                    " VALUES (:dokument_id, :numer_dnia, :data_wpisu, :opis_prac, :uwagi_opiekuna, :jest_podpisany)"
                ),
                {
                    'dokument_id': dokument_id,
                    'numer_dnia': numer_dnia,
                    'data_wpisu': data_wpisu,
                    'opis_prac': opis_prac,
                    'uwagi_opiekuna': uwagi_opiekuna,
                    'jest_podpisany': 0,
                }
            )

            # insert each selected effect separately into wpis_efekt
            efekty_row = efekty_rows[idx] if idx < len(efekty_rows) else ''
            if not efekty_row and idx < len(efekty_list):
                efekty_row = efekty_list[idx]

            if efekty_row:
                for efekt in str(efekty_row).split(','):
                    efekt_value = efekt.strip()
                    if not efekt_value:
                        continue
                    try:
                        numer_efektu = int(efekt_value)
                    except ValueError:
                        continue
                    db.session.execute(
                        text(
                            "INSERT OR IGNORE INTO wpis_efekt (dokument_id, numer_dnia, nr_efektu)"
                            " VALUES (:dokument_id, :numer_dnia, :nr_efektu)"
                        ),
                        {
                            'dokument_id': dokument_id,
                            'numer_dnia': numer_dnia,
                            'nr_efektu': numer_efektu,
                        }
                    )

        # Insert dane_dokumentu entries for attachments
        wykaz = form_data.get('wykaz_zalacznikow', '') or ''
        wykaz_items = [s.strip() for s in wykaz.split(',') if s.strip()]
        for i, item in enumerate(wykaz_items, start=1):
            key = f'zalacznik_{i}'
            db.session.execute(
                text(
                    "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
                ),
                {
                    'doc_id': dokument_id,
                    'klucz': key,
                    'wartosc': item,
                    'wypelniajacy': current_user.id,
                }
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 6: {e}')
        return False


@bp.route('/formularz/zalacznik-6', methods=['GET', 'POST'])
@login_required
def zalacznik_6():
    """Formularz załącznika 6 - Dziennik praktyki zawodowej."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['student', 'opiekun_firmowy']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if role == 'student':
            form_data = {
                'wykaz_zalacznikow': request.form.get('wykaz_zalacznikow'),
                'dzien': request.form.getlist('dzien[]'),
                'data': request.form.getlist('data[]'),
                'opis': request.form.getlist('opis[]'),
                'efekty': request.form.getlist('efekty[]'),
                'efekty_rows': request.form.getlist('efekty_rows[]'),
                'uwagi': request.form.getlist('uwagi[]'),
            }
        else:
            form_data = {
                'wykaz_zalacznikow': request.form.get('wykaz_zalacznikow'),
                'dzien': request.form.getlist('dzien[]'),
                'data': request.form.getlist('data[]'),
                'opis': request.form.getlist('opis[]'),
                'efekty': request.form.getlist('efekty[]'),
                'efekty_rows': request.form.getlist('efekty_rows[]'),
                'uwagi': request.form.getlist('uwagi[]'),
            }

        saved = save_attachment6_data(form_data)
        if saved:
            flash('Dane załącznika 6 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    from app import db
    from sqlalchemy import text

    miejsce_praktyki = ''
    data_rozp = ''
    data_zak = ''

    practice_row = db.session.execute(
        text(
            "SELECT f.nazwa AS firma_nazwa, p.data_rozpoczecia, p.data_zakonczenia "
            "FROM praktyka p "
            "JOIN firma f ON p.firma_id = f.id "
            "WHERE p.student_id = :student_id ORDER BY p.id DESC LIMIT 1"
        ),
        {'student_id': current_user.id}
    ).fetchone()
    if practice_row:
        miejsce_praktyki = practice_row[0] or ''
        data_rozp = practice_row[1] or ''
        data_zak = practice_row[2] or ''

    prefilled = {
        'imie_nazwisko_studenta': f'{current_user.imie} {current_user.nazwisko}' if getattr(current_user, 'imie', None) and getattr(current_user, 'nazwisko', None) else '',
        'nr_indeksu': getattr(current_user, 'numer_albumu', '') or '',
        'specjalnosc': getattr(current_user, 'specjalnosc', '') or '',
        'rok_akademicki': getattr(current_user, 'rok_akademicki', '') or '',
        'miejsce_praktyki': miejsce_praktyki,
        'data_rozp': data_rozp,
        'data_zak': data_zak,
        'wykaz_zalacznikow': '',
        'uwagi_opiekuna_firmowego': '',
        'dzien': [''],
        'data': [''],
        'opis': [''],
        'efekty': [''],
    }

    return render_template(
        'forms/zalacznik_6.html',
        role=role,
        **prefilled
    )


def save_attachment7_data(form_data):
    """Zapis załącznika 7 (Sprawozdanie z praktyki zawodowej)."""
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 7: %s', form_data)

    try:
        student_id = current_user.id
        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_uczelniany_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_uczelniany_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        if not praktyka_id:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s przy zapisie załącznika 7.', student_id)
            return False

        typ_row = db.session.execute(text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_7' LIMIT 1")).fetchone()
        typ_id = typ_row[0] if typ_row else None
        if not typ_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_7 przy zapisie załącznika 7.')
            return False

        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'completed',
                'ostatni_edytor': current_user.id,
            }
        )
        update_practice_stage_from_typ(praktyka_id, typ_id)
        db.session.commit()

        document_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = document_row[0] if document_row else None
        if not dokument_id:
            current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 7.')
            return False

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        dane_map = {
            'charakterystyka_miejsca': form_data.get('charakterystyka_miejsca', ''),
            'opis_i_analiza': form_data.get('opis_i_analiza', ''),
            'wiedza_umiejetnosci': form_data.get('wiedza_umiejetnosci', ''),
            'data_na_koniec': form_data.get('data_na_koniec', ''),
        }

        for klucz, wartosc in dane_map.items():
            db.session.execute(
                text(
                    "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez)"
                    " VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
                ),
                {
                    'doc_id': dokument_id,
                    'klucz': klucz,
                    'wartosc': wartosc,
                    'wypelniajacy': current_user.id,
                }
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 7: {e}')
        return False


@bp.route('/formularz/zalacznik-7', methods=['GET', 'POST'])
@login_required
def zalacznik_7():
    """Formularz załącznika 7 - Sprawozdanie z praktyki zawodowej."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role != 'student':
            flash('Tylko student może zapisać załącznik 7.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'charakterystyka_miejsca': request.form.get('charakterystyka_miejsca'),
            'opis_i_analiza': request.form.get('opis_i_analiza'),
            'wiedza_umiejetnosci': request.form.get('wiedza_umiejetnosci'),
            'data_na_koniec': request.form.get('data_na_koniec'),
        }

        saved = save_attachment7_data(form_data)
        if saved:
            flash('Dane załącznika 7 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    student_id = current_user.id
    praktyka_row = db.session.execute(
        text(
            "SELECT p.rok_akademicki, f.nazwa AS firma_nazwa "
            "FROM praktyka p "
            "LEFT JOIN firma f ON p.firma_id = f.id "
            "WHERE p.student_id = :student_id "
            "ORDER BY p.id DESC LIMIT 1"
        ),
        {'student_id': student_id}
    ).fetchone()

    rok_akademicki = praktyka_row[0] if praktyka_row and praktyka_row[0] else ''
    miejsce_praktyki = praktyka_row[1] if praktyka_row and praktyka_row[1] else ''

    prefilled = {
        'nr_indeksu': current_user.numer_albumu or '',
        'imie_nazwisko_studenta': f"{current_user.imie} {current_user.nazwisko}",
        'specjalnosc': current_user.specjalnosc or '',
        'rok_akademicki': rok_akademicki,
        'miejsce_praktyki': miejsce_praktyki,
        'charakterystyka_miejsca': '',
        'opis_i_analiza': '',
        'wiedza_umiejetnosci': '',
        'data_na_koniec': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_7.html',
        role=role,
        **prefilled
    )


def save_attachment7a_data(form_data):
    """Zapis załącznika 7a (Sprawozdanie z pracy zawodowej)."""
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 7a: %s', form_data)

    try:
        student_id = current_user.id

        praktyka_row = db.session.execute(
            text("""
                SELECT id, opiekun_uczelniany_id FROM praktyka WHERE student_id = :student_id ORDER BY id DESC LIMIT 1
            """),
            {'student_id': student_id}
        ).fetchone()

        if not praktyka_row:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s', student_id)
            return False

        praktyka_id = praktyka_row[0]
        opiekun_uczelniany_id = praktyka_row[1] if len(praktyka_row) > 1 else None

        typ_row = db.session.execute(
            text("""
                SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_7A' LIMIT 1
            """)
        ).fetchone()

        if not typ_row:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_7A.')
            return False

        typ_id = typ_row[0]

        dokument_row = db.session.execute(
            text("""
                SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id LIMIT 1
            """),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id
            }
        ).fetchone()

        if dokument_row:
            dokument_id = dokument_row[0]

            db.session.execute(
                text("""
                    UPDATE dokument SET status = 'completed', aktualny_etap = 3, zaktualizowano = datetime('now') WHERE id = :id
                """),
                {'id': dokument_id}
            )
            update_practice_stage_from_typ(praktyka_id, typ_id)
        else:
            db.session.execute(
                text("""
                    INSERT INTO dokument ( praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor )
                    VALUES ( :praktyka_id, :typ_id, :utworzony_przez, 'completed', :ostatni_edytor )
                """),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'ostatni_edytor': current_user.id
                }
            )
            update_practice_stage_from_typ(praktyka_id, typ_id)

            db.session.commit()

            dokument_id = db.session.execute(
                text("""
                    SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id ORDER BY id DESC LIMIT 1
                """),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id
                }
            ).scalar()

        dane_map = {
            'miejsce_odbycia_praktyki':
                form_data.get(
                    'miejsce_odbycia_praktyki',
                    ''
                ),
            'charakterystyka_miejsca_pracy':
                form_data.get(
                    'charakterystyka_miejsca_pracy',
                    ''
                ),
            'opis_i_analiza':
                form_data.get(
                    'opis_i_analiza',
                    ''
                ),
            'wiedza_umiejetnosci':
                form_data.get(
                    'wiedza_umiejetnosci',
                    ''
                ),
            'data_na_koniec':
                form_data.get(
                    'data_na_koniec',
                    ''
                ),
        }

        for klucz, wartosc in dane_map.items():

            istnieje = db.session.execute(
                text("""
                    SELECT id FROM dane_dokumentu WHERE dokument_id = :doc_id AND klucz = :klucz
                """),
                {
                    'doc_id': dokument_id,
                    'klucz': klucz
                }
            ).fetchone()

            if istnieje:
                db.session.execute(
                    text("""
                        UPDATE dane_dokumentu SET wartosc = :wartosc, wypelnione_przez = :user_id WHERE id = :id
                    """),
                    {
                        'wartosc': wartosc,
                        'user_id': current_user.id,
                        'id': istnieje[0]
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO dane_dokumentu ( dokument_id, klucz, wartosc, wypelnione_przez )
                        VALUES ( :doc_id, :klucz, :wartosc, :user_id )
                    """),
                    {
                        'doc_id': dokument_id,
                        'klucz': klucz,
                        'wartosc': wartosc,
                        'user_id': current_user.id
                    }
                )

        # Utwórz wpisy udostępnionego dokumentu
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if student_id and role_ids.get('student'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': student_id,
                    'rola_id': role_ids['student'],
                }
            )

        if role_ids.get('dziekanat'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dziekanat'],
                }
            )

        if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': opiekun_uczelniany_id,
                    'rola_id': role_ids['opiekun_uczelniany'],
                }
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f'Błąd zapisu załącznika 7a: {e}'
        )
        return False


@bp.route('/formularz/zalacznik-7a', methods=['GET', 'POST'])
@login_required
def zalacznik_7a():
    """Formularz załącznika 7a - Sprawozdanie z pracy zawodowej lub działalności gospodarczej."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa

    student_id = current_user.id

    praktyka_row = db.session.execute(
        text(
            "SELECT p.rok_akademicki "
            "FROM praktyka p "
            "WHERE p.student_id = :student_id "
            "ORDER BY p.id DESC LIMIT 1"
        ),
        {'student_id': student_id}
    ).fetchone()

    rok_akademicki = (
        praktyka_row[0]
        if praktyka_row and praktyka_row[0]
        else ''
    )

    if request.method == 'POST':
        if role not in ['student', 'opiekun_uczelniany']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if role == 'student':
            form_data = {
                'miejsce_odbycia_praktyki': request.form.get('miejsce_odbycia_praktyki'),
                'charakterystyka_miejsca_pracy': request.form.get('charakterystyka_miejsca_pracy'),
                'opis_i_analiza': request.form.get('opis_i_analiza'),
                'wiedza_umiejetnosci': request.form.get('wiedza_umiejetnosci'),
                'data_na_koniec': request.form.get('data_na_koniec'),
            }
        else:
            form_data = {
                'data_na_koniec_uczelnianego': request.form.get('data_na_koniec_uczelnianego'),
            }

        saved = save_attachment7a_data(form_data)
        if saved:
            flash('Dane załącznika 7a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'nr_indeksu': current_user.numer_albumu or '',
        'imie_nazwisko_studenta': f"{current_user.imie} {current_user.nazwisko}",
        'specjalnosc': current_user.specjalnosc or '',
        'rok_akademicki': rok_akademicki,

        # pozostaje ręcznie wypełniane
        'miejsce_odbycia_praktyki': '',

        'charakterystyka_miejsca_pracy': '',
        'opis_i_analiza': '',
        'wiedza_umiejetnosci': '',
        'data_na_koniec': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_7a.html',
        role=role,
        **prefilled
    )


def save_attachment8_data(form_data):
    """Zapisz załącznik 8 do bazy: dokument, pytanie_komisji, dane_dokumentu."""
    from app import db
    from sqlalchemy import text

    try:
        student_id = form_data.get('student_id')
        if not student_id:
            current_app.logger.error('Brak student_id w form_data')
            return False

        # Znajdź praktykę dla studenta (pobierz również pole sciezka i opiekunów)
        praktyka_result = db.session.execute(text(
            "SELECT id, sciezka, opiekun_firmowy_id, opiekun_uczelniany_id "
            "FROM praktyka WHERE student_id = :student_id ORDER BY utworzono DESC LIMIT 1"
        ), {'student_id': student_id}).fetchone()
        if not praktyka_result:
            current_app.logger.error('Brak praktyki dla studenta %s', student_id)
            return False
        praktyka_id = praktyka_result[0]
        praktyka_sciezka = praktyka_result[1] if len(praktyka_result) > 1 else None
        opiekun_firmowy_id = praktyka_result[2] if len(praktyka_result) > 2 else None
        opiekun_uczelniany_id = praktyka_result[3] if len(praktyka_result) > 3 else None

        # Znajdź typ dokumentu ZAL_8
        typ_doc_result = db.session.execute(text(
            "SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_8'"
        )).fetchone()
        if not typ_doc_result:
            current_app.logger.error('Brak typu dokumentu ZAL_8')
            return False
        typ_dokumentu_id = typ_doc_result[0]

        # Utwórz dokument
        doc_insert = text(
            "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor) "
            "VALUES (:praktyka_id, :typ_dokumentu_id, :utworzony_przez, 'completed', :ostatni_edytor)"
        )
        db.session.execute(doc_insert, {
            'praktyka_id': praktyka_id,
            'typ_dokumentu_id': typ_dokumentu_id,
            'utworzony_przez': current_user.id,
            'ostatni_edytor': current_user.id,
        })
        update_practice_stage_from_typ(praktyka_id, typ_dokumentu_id)
        db.session.commit()

        # Pobierz ID nowo utworzonego dokumentu
        doc_id_result = db.session.execute(text(
            "SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_dokumentu_id "
            "ORDER BY utworzono DESC LIMIT 1"
        ), {'praktyka_id': praktyka_id, 'typ_dokumentu_id': typ_dokumentu_id}).fetchone()
        dokument_id = doc_id_result[0]

        # Wstaw wpisy do udostepniony_dokument
        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor', 'czlonek_komisji')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}
        shared_entries = {}

        def add_share(adresat, rola_id, can_view, can_edit, can_sign, can_approve):
            if rola_id is None:
                return
            key = (adresat, rola_id)
            prev = shared_entries.get(key, (False, False, False, False))
            shared_entries[key] = (
                prev[0] or can_view,
                prev[1] or can_edit,
                prev[2] or can_sign,
                prev[3] or can_approve,
            )

        add_share(student_id, role_ids.get('student'), True, False, False, False)
        add_share(None, role_ids.get('dziekanat'), True, False, False, False)
        if praktyka_sciezka and str(praktyka_sciezka).lower() == 'alternative':
            add_share(opiekun_uczelniany_id, role_ids.get('opiekun_uczelniany'), True, True, False, False)
        else:
            add_share(opiekun_uczelniany_id, role_ids.get('opiekun_uczelniany'), True, False, False, False)
        if not (praktyka_sciezka and str(praktyka_sciezka).lower() == 'alternative'):
            add_share(opiekun_firmowy_id, role_ids.get('opiekun_firmowy'), True, False, False, False)
        add_share(None, role_ids.get('dyrektor'), True, False, False, False)

        committee_names = [
            form_data.get('imie_nazwisko_1', ''),
            form_data.get('imie_nazwisko_3', ''),
            form_data.get('imie_nazwisko_4', ''),
        ]

        for name in committee_names:
            if not name:
                continue
            user_row = db.session.execute(
                text("SELECT id, rola_id FROM uzytkownik WHERE imie || ' ' || nazwisko = :name LIMIT 1"),
                {'name': name}
            ).fetchone()
            if not user_row:
                continue

            user_id, user_rola_id = user_row
            if user_rola_id == role_ids.get('czlonek_komisji'):
                add_share(user_id, role_ids['czlonek_komisji'], True, True, True, True)
            elif user_rola_id == role_ids.get('opiekun_uczelniany'):
                if praktyka_sciezka and str(praktyka_sciezka).lower() == 'alternative':
                    add_share(user_id, role_ids['opiekun_uczelniany'], True, True, False, False)
                else:
                    add_share(user_id, role_ids['opiekun_uczelniany'], True, False, False, False)

        # Wstaw wpisy do udostepniony_dokument
        for (adresat, rola_id), perms in shared_entries.items():
            db.session.execute(
                text(
                    "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                    "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, :moze_podgladac, :moze_edytowac, :moze_podpisac, :moze_akceptowac)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': adresat,
                    'rola_id': rola_id,
                    'moze_podgladac': 1 if perms[0] else 0,
                    'moze_edytowac': 1 if perms[1] else 0,
                    'moze_podpisac': 1 if perms[2] else 0,
                    'moze_akceptowac': 1 if perms[3] else 0,
                }
            )

        # Wstaw wpisy do pytanie_komisji (3 pytania)
        for i in range(1, 4):
            pytanie_text = form_data.get(f'pytanie_{i}', '')
            ocena_str = form_data.get(f'ocena_cz_{i}', '')
            if pytanie_text and ocena_str:
                try:
                    ocena_val = int(float(ocena_str))
                except (ValueError, TypeError):
                    ocena_val = 0

                db.session.execute(text(
                    "INSERT INTO pytanie_komisji (dokument_id, numer_pytania, tresc_pytania, wartosc_oceny) "
                    "VALUES (:dokument_id, :numer, :tresc, :ocena)"
                ), {
                    'dokument_id': dokument_id,
                    'numer': i,
                    'tresc': pytanie_text,
                    'ocena': ocena_val,
                })

        # Wstaw wpisy do dane_dokumentu
        dane_keys = [
            'imie_nazwisko_1', 'funkcja_1', 'imie_nazwisko_2', 'funkcja_2',
            'imie_nazwisko_3', 'funkcja_3', 'imie_nazwisko_4', 'funkcja_4',
            'data_zaliczenia', 'ocena_za_mini_zadania_e', 'ocena_koncowa'
        ]
        for key in dane_keys:
            value = form_data.get(key, '')
            if value:
                db.session.execute(text(
                    "INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                    "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
                ), {
                    'dokument_id': dokument_id,
                    'klucz': key,
                    'wartosc': value,
                    'wypelnione_przez': current_user.id,
                })

        # If this practice uses the alternative path, persist additional grade fields
        if praktyka_sciezka and str(praktyka_sciezka).lower() == 'alternative':
            alt_keys = ['ocena_sprawozdania_s', 'data_oceny_s', 'ocena_u', 'ocena_z']
            for key in alt_keys:
                value = form_data.get(key, '')
                if value:
                    db.session.execute(text(
                        "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                        "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
                    ), {
                        'dokument_id': dokument_id,
                        'klucz': key,
                        'wartosc': value,
                        'wypelnione_przez': current_user.id,
                    })

        db.session.execute(
            text("UPDATE praktyka SET status='completed' WHERE id=:praktyka_id"),
            {'praktyka_id': praktyka_id}
        )

        db.session.commit()
        current_app.logger.info('Załącznik 8 zapisany: dokument_id=%s', dokument_id)
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Błąd przy zapisie załącznika 8: %s', str(e))
        return False


@bp.route('/formularz/zalacznik-8', methods=['GET', 'POST'])
@login_required
def zalacznik_8():
    """Formularz załącznika 8 - Protokół zaliczenia praktyki zawodowej."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    selected_student = None

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
            }
        # Pobierz opiekuna uczelnianego z wybranej praktyki (jeśli istnieje)
        op_row = db.session.execute(
            text("SELECT opiekun_uczelniany_id FROM praktyka WHERE id = :praktyka_id"),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if op_row and op_row[0]:
            op_id = op_row[0]
            opiekun_prefill_id = op_id
            user_row = db.session.execute(
                text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                {'id': op_id}
            ).fetchone()
            if user_row:
                opiekun_prefill = f"{user_row[0]} {user_row[1]}"

    zal3_rows = db.session.execute(text(
        "SELECT p.student_id, p.opiekun_uczelniany_id, dd.klucz, dd.wartosc "
        "FROM dokument d "
        "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
        "JOIN praktyka p ON d.praktyka_id = p.id "
        "JOIN dane_dokumentu dd ON dd.dokument_id = d.id "
        "WHERE t.kod = 'ZAL_3' "
        "AND d.id IN ("
        "  SELECT MAX(d2.id) FROM dokument d2 "
        "  JOIN typ_dokumentu t2 ON d2.typ_dokumentu_id = t2.id "
        "  WHERE t2.kod = 'ZAL_3' AND d2.praktyka_id = d.praktyka_id "
        "  GROUP BY d2.praktyka_id)"
    )).fetchall()
    zal3_data = {}
    for student_id, opiekun_id, key, value in zal3_rows:
        student_key = str(student_id)
        if student_key not in zal3_data:
            zal3_data[student_key] = {'opiekun_id': opiekun_id}
        zal3_data[student_key][key] = value or ''

    # Pobierz opiekunów uczelnianych i członków komisji
    opiekunowie = {}
    czlonkowie_komisji = {}
    
    # Opiekunowie uczelnialni
    for row in db.session.execute(text("SELECT u.id, u.imie, u.nazwisko FROM uzytkownik u JOIN role r ON u.rola_id = r.id WHERE r.nazwa='opiekun_uczelniany'")).fetchall():
        opiekunowie[str(row[0])] = {'imie_nazwisko': f"{row[1]} {row[2]}", 'funkcja': 'Uczelniany opiekun praktyki zawodowej', 'rola': 'opiekun_uczelniany'}
    
    # Członkowie komisji - dla pozycji 1 (Przewodniczący)
    for row in db.session.execute(text("SELECT u.id, u.imie, u.nazwisko FROM uzytkownik u JOIN role r ON u.rola_id = r.id WHERE r.nazwa='czlonek_komisji'")).fetchall():
        czlonkowie_komisji[str(row[0])] = {'imie_nazwisko': f"{row[1]} {row[2]}", 'funkcja': 'Przewodniczący Komisji', 'rola': 'czlonek_komisji'}
    
    # Członkowie komisji - dla pozycji 3, 4
    czlonkowie_komisji_pos34 = {}
    for row in db.session.execute(text("SELECT u.id, u.imie, u.nazwisko FROM uzytkownik u JOIN role r ON u.rola_id = r.id WHERE r.nazwa='czlonek_komisji'")).fetchall():
        czlonkowie_komisji_pos34[str(row[0])] = {'imie_nazwisko': f"{row[1]} {row[2]}", 'funkcja': 'Członek Komisji', 'rola': 'czlonek_komisji'}
    
    # Dla pozycji 3, 4 - mogą być wybierani zarówno członkowie komisji jak i opiekunowie
    komisja_osoby = {**opiekunowie, **czlonkowie_komisji_pos34}

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_uczelniany', 'czlonek_komisji']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {}
        form_data['student_id'] = request.form.get('student_id')
        form_data['data_zaliczenia'] = request.form.get('data_zaliczenia')
        form_data['ocena_sprawozdania_s'] = request.form.get('ocena_sprawozdania_s')
        form_data['data_oceny_s'] = request.form.get('data_oceny_s')
        form_data['ocena_za_mini_zadania_e'] = request.form.get('ocena_za_mini_zadania_e')
        form_data['ocena_koncowa'] = request.form.get('ocena_koncowa')

        # Skład komisji
        for i in range(1, 5):
            form_data[f'imie_nazwisko_{i}'] = request.form.get(f'imie_nazwisko_{i}')
            form_data[f'funkcja_{i}'] = request.form.get(f'funkcja_{i}')

        # Pytania i oceny
        for i in range(1, 4):
            form_data[f'pytanie_{i}'] = request.form.get(f'pytanie_{i}')
            form_data[f'ocena_cz_{i}'] = request.form.get(f'ocena_cz_{i}')

        saved = save_attachment8_data(form_data)
        if saved:
            flash('Dane załącznika 8 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'nr_indeksu': '',
        'imie_nazwisko_studenta': '',
        'student_id': '',
        'specjalnosc': '',
        'rok_akademicki': '',
        'miejsce_praktyki': '',
        'okres_praktyki': '',
        'nr_albumu': '',
        'ocena_sprawozdania_s': '',
        'data_oceny_s': date.today().isoformat(),
        'ocena_u': '',
        'ocena_z': '',
        'data_zaliczenia': date.today().isoformat(),
        'sklad_komisji': '',
        'pytania': '',
        'oceny_czastkowe': '',
        'ocena_za_mini_zadania_e': '',
        'ocena_koncowa': '',
    }

    if selected_student:
        prefilled['imie_nazwisko_studenta'] = f"{selected_student['imie']} {selected_student['nazwisko']}"
        prefilled['nr_indeksu'] = selected_student['numer_albumu']
        prefilled['student_id'] = selected_student['id']

    return render_template(
        'forms/zalacznik_8.html',
        role=role,
        studenci=studenci,
        student_zal3_json=json.dumps(zal3_data),
        czlonkowie_komisji_json=json.dumps(czlonkowie_komisji),
        komisja_osoby_json=json.dumps(komisja_osoby),
        prefilled_opiekun=opiekun_prefill,
        prefilled_opiekun_id=opiekun_prefill_id,
        **prefilled
    )


def save_attachment9_data(form_data):
    """Szkielet zapisu załącznika 9 (Oświadczenie instytucji w sprawie przyjęcia studenta)."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik
    from app.models.firma import Firma

    current_app.logger.debug('Zapis załącznika 9: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        nazwa_firmy = form_data.get('nazwa_firmy', '').strip()
        telefon_opiekuna = form_data.get('telefon_opiekuna_firmowego', '').strip()
        miejscowosc = form_data.get('miejscowosc', '').strip()
        data_pola = form_data.get('data', '').strip()
        termin_od = form_data.get('termin_od')
        termin_do = form_data.get('termin_do')

        # Firma i opiekun firmowy
        firma_id = current_user.firma_id
        opiekun_id = current_user.id

        # Pobierz rok akademicki studenta
        rok_akademicki = None
        if student_id:
            student = Uzytkownik.query.get(student_id)
            rok_akademicki = student.rok_akademicki if student else None

        # 1) Utwórz wpis w tabeli `praktyka`
        ins_praktyka = text(
            "INSERT INTO praktyka (student_id, firma_id, opiekun_firmowy_id, sciezka, status, data_rozpoczecia, data_zakonczenia, rok_akademicki)"
            " VALUES (:student_id, :firma_id, :opiekun_id, :sciezka, :status, :data_rozp, :data_zak, :rok)"
        )
        db.session.execute(ins_praktyka, {
            'student_id': student_id,
            'firma_id': firma_id,
            'opiekun_id': opiekun_id,
            'sciezka': 'standard',
            'status': 'pending',
            'data_rozp': termin_od,
            'data_zak': termin_do,
            'rok': rok_akademicki,
        })
        db.session.commit()

        # pobierz id właśnie utworzonej praktyki
        praktyka_row = db.session.execute(
            text("SELECT id FROM praktyka WHERE student_id=:student_id AND firma_id=:firma_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id, 'firma_id': firma_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None

        # 2) Utwórz wpis w tabeli `dokument` powiązany z załącznikiem 9
        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_9' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None

        dokument_id = None
        if praktyka_id and typ_id:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                    " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'status': 'completed',
                    'ostatni_edytor': current_user.id
                }
            )
            db.session.commit()
            doc_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            dokument_id = doc_row[0] if doc_row else None

        # 3) Utwórz dwa wpisy w `dane_dokumentu` (miejscowosc, data)
        if dokument_id:
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'miejscowosc', 'wartosc': miejscowosc, 'wypelniajacy': current_user.id}
            )
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'data', 'wartosc': data_pola, 'wypelniajacy': current_user.id}
            )

            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_firmowy', 'dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            if role_ids.get('opiekun_firmowy'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': current_user.id,
                        'rola_id': role_ids['opiekun_firmowy'],
                    }
                )

            db.session.commit()

        # 4) Zaktualizuj nazwę firmy i numer telefonu opiekuna firmowego
        if firma_id:
            firma = Firma.query.get(firma_id)
            if firma and nazwa_firmy:
                firma.nazwa = nazwa_firmy
            # aktualizujemy telefon opiekuna (current_user)
            if telefon_opiekuna:
                current_user.telefon = telefon_opiekuna
            db.session.commit()

        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 9: {e}')
        return False


@bp.route('/formularz/zalacznik-9', methods=['GET', 'POST'])
@login_required
def zalacznik_9():
    """Formularz załącznika 9 - Oświadczenie instytucji w sprawie przyjęcia studenta."""
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role != 'opiekun_firmowy':
            flash('Tylko opiekun firmowy może zapisać załącznik 9.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'student_id': request.form.get('student_id'),
            'miejscowosc': request.form.get('miejscowosc'),
            'data': request.form.get('data'),
            'nazwa_firmy': request.form.get('nazwa_firmy'),
            'termin_od': request.form.get('termin_od'),
            'termin_do': request.form.get('termin_do'),
            'nr_albumu': request.form.get('nr_albumu'),
            'imie_nazwisko_opiekuna_firmowego': request.form.get('imie_nazwisko_opiekuna_firmowego'),
            'telefon_opiekuna_firmowego': request.form.get('telefon_opiekuna_firmowego'),
            'email_opiekuna_firmowego': request.form.get('email_opiekuna_firmowego'),
            'osoba_upowazniona': request.form.get('osoba_upowazniona'),
        }

        saved = save_attachment9_data(form_data)
        if saved:
            flash('Dane załącznika 9 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # Pobranie listy aktywnych studentów posortowanych po numerze albumu
    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = (
        Uzytkownik.query
        .filter_by(rola_id=rola_student.id, jest_aktywny=True)
        .order_by(Uzytkownik.numer_albumu)
        .all()
    ) if rola_student else []

    firma = getattr(current_user, 'firma', None)
    nazwa_firmy = firma.nazwa if firma else ''
    osoba_upowazniona = ''
    miasto_firmy = firma.miasto if firma and firma.miasto else ''
    if firma:
        if firma.osoba_upowazniona_imie_nazwisko and firma.osoba_upowazniona_stanowisko:
            osoba_upowazniona = f'{firma.osoba_upowazniona_imie_nazwisko}, {firma.osoba_upowazniona_stanowisko}'
        elif firma.osoba_upowazniona_imie_nazwisko:
            osoba_upowazniona = firma.osoba_upowazniona_imie_nazwisko
        elif firma.osoba_upowazniona_stanowisko:
            osoba_upowazniona = firma.osoba_upowazniona_stanowisko

    prefilled = {
        'imie_nazwisko_studenta': '',
        'wybrany_student_id': None,
        'miejscowosc': miasto_firmy,
        'data': date.today().isoformat(),
        'nazwa_firmy': nazwa_firmy,
        'termin_od': '',
        'termin_do': '',
        'nr_albumu': '',
        'imie_nazwisko_opiekuna_firmowego': current_user.pelne_imie,
        'telefon_opiekuna_firmowego': current_user.telefon or '',
        'email_opiekuna_firmowego': current_user.email or '',
        'osoba_upowazniona': osoba_upowazniona,
    }

    return render_template(
        'forms/zalacznik_9.html',
        role=role,
        studenci=studenci,
        **prefilled
    )


@bp.route('/profil/firma', methods=['GET', 'POST'])
@login_required
def profil_firmy():
    """
    Strona uzupełniania danych firmy przez opiekuna firmowego.
    Dostępna zaraz po rejestracji — opiekun widzi baner z prośbą
    o uzupełnienie danych jeśli firma nie jest jeszcze kompletna.
    """
    from app import db
    from app.models.firma import Firma

    if current_user.rola.nazwa != 'opiekun_firmowy':
        flash('Tylko opiekun firmowy może edytować dane firmy.', 'danger')
        return redirect(url_for('dashboard.index'))

    firma = Firma.query.get(current_user.firma_id) if current_user.firma_id else None

    if request.method == 'POST':
        nazwa          = request.form.get('nazwa', '').strip()
        adres          = request.form.get('adres', '').strip()
        miasto         = request.form.get('miasto', '').strip()
        osoba_imie_naz = request.form.get('osoba_upowazniona_imie_nazwisko', '').strip()
        osoba_stan     = request.form.get('osoba_upowazniona_stanowisko', '').strip()

        if not nazwa or not adres or not miasto:
            flash('Nazwa, adres i miasto są wymagane.', 'danger')
        else:
            try:
                if firma:
                    # Aktualizacja istniejącej firmy
                    firma.nazwa                          = nazwa
                    firma.adres                          = adres
                    firma.miasto                         = miasto
                    firma.osoba_upowazniona_imie_nazwisko = osoba_imie_naz
                    firma.osoba_upowazniona_stanowisko    = osoba_stan
                else:
                    # Utworzenie nowej firmy i przypisanie do użytkownika
                    firma = Firma(
                        nazwa=nazwa,
                        adres=adres,
                        miasto=miasto,
                        osoba_upowazniona_imie_nazwisko=osoba_imie_naz,
                        osoba_upowazniona_stanowisko=osoba_stan
                    )
                    db.session.add(firma)
                    db.session.flush()
                    current_user.firma_id = firma.id

                # Aktualizacja danych osobowych opiekuna
                current_user.telefon    = request.form.get('telefon', '').strip()
                current_user.stanowisko = request.form.get('stanowisko', '').strip()

                db.session.commit()
                flash('Dane firmy zostały zapisane.', 'success')
                return redirect(url_for('dashboard.index'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Błąd zapisu danych firmy: {e}')
                flash('Wystąpił błąd podczas zapisu. Spróbuj ponownie.', 'danger')

    return render_template(
        'profil/firma.html',
        firma=firma,
        uzytkownik=current_user
    )