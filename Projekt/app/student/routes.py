from datetime import date, datetime
import json

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app, send_file
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


def save_attachment1_data(form_data, dokument_id=None):
    """Zapis danych załącznika 1 do bazy danych.

    Aktualizuje praktykę opiekunem uczelnianym, tworzy dokument
    lub odtwarza odrzucony dokument i zapisuje dane formularza.
    """
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 1: %s', form_data)

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        opiekun_uczelniany_id = int(form_data.get('reprezentant_uczelni_id')) if form_data.get('reprezentant_uczelni_id') else None
        nr_porozumienia = form_data.get('nr_porozumienia', '').strip()
        data_zawarcia = form_data.get('data_zawarcia', '').strip()
        nazwa_zakladu_pracy = form_data.get('nazwa_zakladu_pracy', '').strip()
        reprezentant_firmy = form_data.get('reprezentant_firmy', '').strip()
        termin_od = form_data.get('termin_od', '').strip()
        termin_do = form_data.get('termin_do', '').strip()
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

        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_1' LIMIT 1")
        ).fetchone()
        typ_id = typ_row[0] if typ_row else None

        if not praktyka_id or not typ_id:
            return False

        if dokument_id:
            existing_doc = db.session.execute(
                text("SELECT status FROM dokument WHERE id=:doc_id AND typ_dokumentu_id=:typ_id"),
                {'doc_id': dokument_id, 'typ_id': typ_id}
            ).fetchone()
            if not existing_doc or existing_doc[0] != 'rejected':
                return False

            db.session.execute(
                text("UPDATE dokument SET status = 'awaiting_signature', ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {'doc_id': dokument_id, 'ostatni_edytor': current_user.id}
            )
            db.session.execute(
                text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            )
            db.session.execute(
                text("UPDATE dokument_akceptacja SET czy_zaakceptowany = 0, zaakceptowano = NULL WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            )
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 0 "
                    "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'dziekanat')"
                ),
                {'doc_id': dokument_id}
            )
            doc_id = dokument_id
        else:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                    " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'status': 'awaiting_signature',
                    'ostatni_edytor': current_user.id,
                }
            )
            db.session.commit()

            doc_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            doc_id = doc_row[0] if doc_row else None

        if doc_id:
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': doc_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': doc_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': doc_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': doc_id,
                        'adresat': opiekun_firmowy_id,
                        'rola_id': role_ids['opiekun_firmowy'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': doc_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            db.session.commit()

            fields = {
                'nr_porozumienia': nr_porozumienia,
                'data_zawarcia': data_zawarcia,
                'nazwa_zakladu_pracy': nazwa_zakladu_pracy,
                'reprezentant_firmy': reprezentant_firmy,
                'termin_od': termin_od,
                'termin_do': termin_do,
                'wymiar_praktyki': wymiar_praktyki,
                'imie_nazwisko_studenta': form_data.get('imie_nazwisko_studenta', ''),
                'reprezentant_uczelni_id': form_data.get('reprezentant_uczelni_id', ''),
                'dyrektor': form_data.get('dyrektor', ''),
            }

            for key, value in fields.items():
                db.session.execute(
                    text(
                        "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez)"
                        " VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
                    ),
                    {
                        'doc_id': doc_id,
                        'klucz': key,
                        'wartosc': value,
                        'wypelniajacy': current_user.id,
                    }
                )
            db.session.commit()

        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 1: {e}')
        return False


def sign_and_accept_attachment1(dokument_id):
    """Podpisanie i akceptacja załącznika 1 przez dyrektora lub opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT praktyka_id, status, typ_dokumentu_id FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[1] != 'awaiting_signature':
            return False

        role_name = current_user.rola.nazwa
        if role_name not in ('dyrektor', 'opiekun_firmowy'):
            return False

        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano)"
                    " VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        signed_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM dokument_podpis dp "
                "JOIN uzytkownik u ON dp.podpisujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE dp.dokument_id = :doc_id AND dp.czy_podpisany = 1 "
                "AND r.nazwa IN ('dyrektor','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        accepted_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM dokument_akceptacja da "
                "JOIN uzytkownik u ON da.akceptujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE da.dokument_id = :doc_id AND da.czy_zaakceptowany = 1 "
                "AND r.nazwa IN ('dyrektor','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        if signed_count == 2 and accepted_count == 2:
            db.session.execute(
                text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'status': 'completed',
                    'ostatni_edytor': current_user.id,
                }
            )
            update_practice_stage_from_typ(doc_row[0], doc_row[2])
        else:
            db.session.execute(
                text("UPDATE dokument SET ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'ostatni_edytor': current_user.id,
                }
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania i akceptacji załącznika 1: {e}')
        return False


def sign_and_accept_attachment2(dokument_id):
    """Podpisanie i akceptacja załącznika 2 przez dyrektora lub opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT praktyka_id, status, typ_dokumentu_id FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[1] != 'awaiting_signature':
            return False

        role_name = current_user.rola.nazwa
        if role_name not in ('dyrektor', 'opiekun_firmowy'):
            return False

        # zaznacz podpis
        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        # zaznacz akceptację
        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano)"
                    " VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        signed_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM dokument_podpis dp "
                "JOIN uzytkownik u ON dp.podpisujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE dp.dokument_id = :doc_id AND dp.czy_podpisany = 1 "
                "AND r.nazwa IN ('dyrektor','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        accepted_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM dokument_akceptacja da "
                "JOIN uzytkownik u ON da.akceptujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE da.dokument_id = :doc_id AND da.czy_zaakceptowany = 1 "
                "AND r.nazwa IN ('dyrektor','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        if signed_count == 2 and accepted_count == 2:
            db.session.execute(
                text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'status': 'completed',
                    'ostatni_edytor': current_user.id,
                }
            )
            update_practice_stage_from_typ(doc_row[0], doc_row[2])
        else:
            db.session.execute(
                text("UPDATE dokument SET ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'ostatni_edytor': current_user.id,
                }
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania i akceptacji załącznika 2: {e}')
        return False


def reject_attachment1(dokument_id):
    """Odrzucenie załącznika 1 przez dyrektora lub opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[0] != 'awaiting_signature':
            return False

        role_name = current_user.rola.nazwa
        if role_name not in ('dyrektor', 'opiekun_firmowy'):
            return False

        db.session.execute(
            text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
            {
                'doc_id': dokument_id,
                'status': 'rejected',
                'ostatni_edytor': current_user.id,
            }
        )
        db.session.execute(
            text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        )
        db.session.execute(
            text("UPDATE dokument_akceptacja SET czy_zaakceptowany = 0, zaakceptowano = NULL WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 1 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'dziekanat')"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia załącznika 1: {e}')
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
                            {'label': 'Załącznik 7a', 'url': url_for('dashboard.zalacznik_7a', dokument_id=None), 'disabled': not (z4a == 'completed') or (z7a is not None)},
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
                "SELECT d.id, t.kod, d.status, oe.imie || ' ' || oe.nazwisko AS ostatni, d.zaktualizowano, d.praktyka_id, "
                "(SELECT d2.status FROM dokument d2 JOIN typ_dokumentu t2 ON d2.typ_dokumentu_id = t2.id "
                "WHERE d2.praktyka_id = d.praktyka_id AND t2.kod = 'ZAL_6' ORDER BY d2.id DESC LIMIT 1) AS z6_status "
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
                    "SELECT d.id, t.kod, d.status, oe.imie || ' ' || oe.nazwisko AS ostatni, d.zaktualizowano, d.praktyka_id, "
                    "(SELECT d2.status FROM dokument d2 JOIN typ_dokumentu t2 ON d2.typ_dokumentu_id = t2.id "
                    "WHERE d2.praktyka_id = d.praktyka_id AND t2.kod = 'ZAL_6' ORDER BY d2.id DESC LIMIT 1) AS z6_status "
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
                'kod': kod,
                'label': label,
                'status': dr[2] or '',
                'ostatni': dr[3] or '',
                'zaktualizowano': dr[4] or '',
                'z6_status': dr[6] if len(dr) > 6 else None,
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


def record_document_download(dokument_id, pobierajacy_id):
    """Zapisz wpis o pobraniu dokumentu w tabeli dokument_pobranie."""
    from app import db
    from sqlalchemy import text

    try:
        db.session.execute(
            text(
                "INSERT INTO dokument_pobranie (dokument_id, pobierajacy_id) "
                "VALUES (:doc_id, :user_id)"
            ),
            {'doc_id': dokument_id, 'user_id': pobierajacy_id}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Błąd zapisu pobrania dokumentu')


@bp.route('/pobierz-dokument', methods=['GET'])
@login_required
def download_document():
    """Pobierz ukończony dokument jako plik PDF lub DOCX.

    Dla ZAL_1 na Windows otwiera okno zapisu PDF poprzez docx2pdf.
    """
    from app import db
    from sqlalchemy import text
    import os
    dokument_id = request.args.get('dokument_id', type=int)
    file_format = request.args.get('format', 'pdf').lower()
    if file_format not in ('pdf', 'docx'):
        file_format = 'pdf'
    if not dokument_id:
        flash('Brak identyfikatora dokumentu do pobrania.', 'danger')
        return redirect(url_for('dashboard.index'))

    doc_row = db.session.execute(
        text("SELECT d.id, t.kod, d.status FROM dokument d JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id WHERE d.id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row:
        flash('Nie znaleziono dokumentu.', 'danger')
        return redirect(url_for('dashboard.index'))

    status = doc_row[2]
    if status != 'completed':
        flash('Dokument musi być ukończony, aby go pobrać.', 'warning')
        return redirect(url_for('dashboard.index'))

    docs_dir = os.path.normpath(os.path.join(current_app.root_path, '..', 'docs'))
    if not os.path.exists(docs_dir):
        try:
            os.makedirs(docs_dir, exist_ok=True)
        except Exception:
            current_app.logger.exception('Nie można utworzyć katalogu docs')

    filename_docx = f"{doc_row[1]}_{dokument_id}.docx"
    filename_pdf = f"{doc_row[1]}_{dokument_id}.pdf"
    docx_path = os.path.join(docs_dir, filename_docx)
    pdf_path = os.path.join(docs_dir, filename_pdf)

    if file_format == 'pdf' and doc_row[1] == 'ZAL_2':
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            if os.path.exists(docx_path):
                os.remove(docx_path)
        except Exception:
            current_app.logger.exception('Nie udało się usunąć starego pliku ZAL_2 przed regeneracją')

    if doc_row[1] == 'ZAL_6':
        try:
            if os.path.exists(docx_path):
                os.remove(docx_path)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception:
            current_app.logger.exception('Nie udało się usunąć starego pliku ZAL_6 przed regeneracją')

    def convert_docx_to_pdf(input_path, output_path):
        try:
            from docx2pdf import convert as docx2pdf_convert
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pythoncom = None

            try:
                docx2pdf_convert(input_path, output_path)
            finally:
                if pythoncom:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
        except Exception:
            current_app.logger.exception('Błąd konwersji DOCX->PDF')
            raise

    if file_format == 'docx' and os.path.exists(docx_path):
        if doc_row[1] in ('ZAL_1', 'ZAL_2', 'ZAL_3', 'ZAL_4', 'ZAL_6', 'ZAL_7', 'ZAL_9', 'ZAL_2A'):
            record_document_download(dokument_id, current_user.id)
        return send_file(docx_path, as_attachment=True)

    if file_format == 'pdf' and os.path.exists(pdf_path):
        if doc_row[1] in ('ZAL_1', 'ZAL_2', 'ZAL_4', 'ZAL_6', 'ZAL_7', 'ZAL_9', 'ZAL_2A'):
            record_document_download(dokument_id, current_user.id)
        return send_file(pdf_path, as_attachment=True)

    try:
        if file_format == 'pdf' and os.path.exists(docx_path):
            try:
                convert_docx_to_pdf(docx_path, pdf_path)
                if os.path.exists(pdf_path):
                    if doc_row[1] in ('ZAL_1', 'ZAL_2', 'ZAL_3', 'ZAL_4', 'ZAL_6', 'ZAL_7', 'ZAL_9', 'ZAL_2A'):
                        record_document_download(dokument_id, current_user.id)
                    return send_file(pdf_path, as_attachment=True)
            except Exception:
                pass

        # Otherwise generate DOCX from template using docxtpl
        try:
            from docxtpl import DocxTemplate
        except Exception:
            current_app.logger.exception('docxtpl nie jest zainstalowane')
            flash('Brak biblioteki do generowania dokumentów na serwerze.', 'danger')
            return redirect(url_for('dashboard.index'))

        # load document data
        dane = db.session.execute(
            text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchall()
        dokument_data = {row[0]: row[1] or '' for row in dane}

        # reconstruct attachment list for ZAL_6 from saved dane_dokumentu rows
        zalacznik_rows = db.session.execute(
            text("SELECT wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id AND klucz LIKE 'zalacznik_%' ORDER BY klucz"),
            {'doc_id': dokument_id}
        ).fetchall()
        if zalacznik_rows:
            wykaz_zalacznikow = ', '.join([row[0] for row in zalacznik_rows if row[0]])
            dokument_data['wykaz_zalacznikow'] = wykaz_zalacznikow

        # get practice/student/company/opiekun info
        info = db.session.execute(
            text(
                "SELECT p.id, p.student_id, s.imie, s.nazwisko, s.numer_albumu, s.forma_studiow, s.specjalnosc, p.liczba_godzin, p.data_rozpoczecia, p.data_zakonczenia, p.rok_akademicki, p.opiekun_firmowy_id, p.opiekun_uczelniany_id, f.nazwa, f.miasto, f.osoba_upowazniona_imie_nazwisko, f.osoba_upowazniona_stanowisko "
                "FROM dokument d JOIN praktyka p ON d.praktyka_id = p.id "
                "LEFT JOIN uzytkownik s ON p.student_id = s.id "
                "LEFT JOIN firma f ON p.firma_id = f.id "
                "WHERE d.id = :doc_id"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        director_full_name = ''
        if doc_row[1] == 'ZAL_1':
            director = db.session.execute(
                text(
                    "SELECT u.imie, u.nazwisko FROM uzytkownik u "
                    "JOIN role r ON u.rola_id = r.id "
                    "WHERE r.nazwa = 'dyrektor' LIMIT 1"
                )
            ).fetchone()
            if director:
                director_full_name = f"{director[0] or ''} {director[1] or ''}".strip()

            context = {
                'dokument_data': dokument_data,
                'director_full_name': director_full_name,
                'nr_porozumienia': dokument_data.get('nr_porozumienia', ''),
                'data_zawarcia': dokument_data.get('data_zawarcia', ''),
                'reprezentant': {'imie': '', 'nazwisko': ''},
                'student': {'imie': '', 'nazwisko': ''},
            }
        elif doc_row[1] == 'ZAL_2':
            director = db.session.execute(
                text(
                    "SELECT u.imie, u.nazwisko FROM uzytkownik u "
                    "JOIN role r ON u.rola_id = r.id "
                    "WHERE r.nazwa = 'dyrektor' LIMIT 1"
                )
            ).fetchone()
            director_full_name = f"{director[0] or ''} {director[1] or ''}".strip() if director else ''

            context = {
                'dokument_data': dokument_data,
                'director_full_name': director_full_name,
                'imie_nazwisko_studenta': '',
                'nr_albumu': '',
                'termin_od': '',
                'termin_do': '',
                'nazwa_firmy': '',
                'miejscowosc': '',
                'osoba_upowazniona': '',
                'imie_nazwisko_opiekuna_firmowego': '',
                'opiekun_firmowy_full_name': '',
                'telefon_opiekuna_firmowego': '',
                'email_opiekuna_firmowego': '',
                'stanowisko_opiekuna_firmowego': '',
            }
        elif doc_row[1] == 'ZAL_2A':
            director = db.session.execute(
                text(
                    "SELECT u.imie, u.nazwisko FROM uzytkownik u "
                    "JOIN role r ON u.rola_id = r.id "
                    "WHERE r.nazwa = 'dyrektor' LIMIT 1"
                )
            ).fetchone()
            director_full_name = f"{director[0] or ''} {director[1] or ''}".strip() if director else ''

            context = {
                'dokument_data': dokument_data,
                'director_full_name': director_full_name,
                'student': {'imie': '', 'nazwisko': ''},
                'selected_student': {'id': '', 'imie': '', 'nazwisko': '', 'numer_albumu': ''},
                'imie_nazwisko_studenta': '',
                'nr_albumu': '',
                'termin_od': '',
                'termin_do': '',
                'nazwa_firmy': '',
                'miejscowosc': '',
                'osoba_upowazniona': '',
                'imie_nazwisko_opiekuna_firmowego': '',
                'opiekun_firmowy_full_name': '',
                'telefon_opiekuna_firmowego': '',
                'email_opiekuna_firmowego': '',
                'stanowisko_opiekuna_firmowego': '',
                'imie_nazwisko_opiekuna_uczelnianego': '',
                'opiekun_uczelniany_full_name': '',
                'hpz_total_days': dokument_data.get('lacznie_dni', '0'),
                'program_entries': [],
            }
        elif doc_row[1] == 'ZAL_6':
            context = {
                'dokument_data': dokument_data,
                'imie_nazwisko_studenta': '',
                'nr_indeksu': '',
                'nr_albumu': '',
                'specjalnosc': '',
                'rok_akademicki': '',
                'miejsce_praktyki': '',
                'data_rozp': '',
                'data_zak': '',
                'wykaz_zalacznikow': dokument_data.get('wykaz_zalacznikow', ''),
                'opiekun_firmowy': dokument_data.get('opiekun_firmowy', ''),
                'wpisy': [],
            }
        elif doc_row[1] == 'ZAL_4':
            # Build context for Załącznik 4 (Efekty uczenia się)
            context = {
                'dokument_data': dokument_data,
                'role': '',
                'imie_nazwisko_studenta': '',
                'nr_indeksu': '',
                'nr_albumu': '',
                'specjalnosc': '',
                'rok_akademicki': '',
                'ilosc_godzin_praktyk': '',
                'czy_efekt_uzyskany': {},
                'selected_student': {
                    'id': '',
                    'imie': '',
                    'nazwisko': '',
                    'numer_albumu': '',
                    'forma_studiow': '',
                    'specjalnosc': '',
                    'firma_nazwa': '',
                    'termin_od': '',
                    'termin_do': '',
                    'opiekun_uczelniany': '',
                    'opiekun_firmowy': '',
                },
                'efekty': [],
                'opinia_opiekuna_uczelnianego': '',
                'opiekun_firmowy_podpisano': '',
                'data_opinii': '',
                'can_edit_firmowy': False,
                'can_edit_uczelniany': False,
                'dokument': {},
            }
        elif doc_row[1] == 'ZAL_3':
            # Build context for Załącznik 3 (Karta praktyki zawodowej)
            director = db.session.execute(
                text(
                    "SELECT u.imie, u.nazwisko FROM uzytkownik u "
                    "JOIN role r ON u.rola_id = r.id "
                    "WHERE r.nazwa = 'dyrektor' LIMIT 1"
                )
            ).fetchone()
            if director:
                director_full_name = f"{director[0] or ''} {director[1] or ''}".strip()

            context = {
                'dokument_data': dokument_data,
                'director_full_name': dokument_data.get('director_full_name', director_full_name),
                'student': {'imie': '', 'nazwisko': '', 'numer_albumu': ''},
                'selected_student': {
                    'id': '',
                    'imie': '',
                    'nazwisko': '',
                    'numer_albumu': '',
                    'forma_studiow': '',
                    'specjalnosc': '',
                    'firma_nazwa': '',
                    'termin_od': '',
                    'termin_do': '',
                },
                'imie_nazwisko_studenta': '',
                'nr_albumu': '',
                'termin_od': '',
                'termin_do': '',
                'nazwa_firmy': '',
                'miejscowosc': '',
                'osoba_upowazniona': '',
                'nr_porozumienia': dokument_data.get('nr_porozumienia', ''),
                'data_zawarcia': dokument_data.get('data_zawarcia', ''),
                'potwierdzenie_zgloszenia': dokument_data.get('potwierdzenie_zgloszenia', ''),
                'potwierdzenie_szkolenia': dokument_data.get('potwierdzenie_szkolenia', ''),
                'student_practice': {},
            }
        else:
            context = {}
            # basic fields from dane_dokumentu
            context.update(dokument_data)

        if info:
            praktyka_id, student_id, imie, nazwisko, numer_albumu, forma_studiow, specjalnosc, liczba_godzin, data_rozp, data_zak, rok_akademicki, opiekun_id, opiekun_uczelniany_id, firma_nazwa, firma_miasto, osoba_imie_naz, osoba_stan = info
            if doc_row[1] == 'ZAL_1':
                context['student'] = {
                    'imie': imie or '',
                    'nazwisko': nazwisko or '',
                }
                context['dokument_data'].setdefault('termin_od', data_rozp or '')
                context['dokument_data'].setdefault('termin_do', data_zak or '')
                context['dokument_data'].setdefault('nazwa_zakladu_pracy', dokument_data.get('nazwa_zakladu_pracy', ''))
                context['dokument_data'].setdefault('reprezentant_firmy', dokument_data.get('reprezentant_firmy', ''))
                context['dokument_data'].setdefault('wymiar_praktyki', dokument_data.get('wymiar_praktyki', ''))
                rep_id = dokument_data.get('reprezentant_uczelni_id')
                if rep_id:
                    rep_row = db.session.execute(
                        text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                        {'id': rep_id}
                    ).fetchone()
                    if rep_row:
                        context['reprezentant'] = {
                            'imie': rep_row[0] or '',
                            'nazwisko': rep_row[1] or '',
                        }
            else:
                context.setdefault('imie_nazwisko_studenta', f"{imie or ''} {nazwisko or ''}".strip())
                context.setdefault('nr_indeksu', dokument_data.get('nr_indeksu', '') or numer_albumu or '')
                context.setdefault('nr_albumu', numer_albumu or '')
                context.setdefault('miejscowosc', firma_miasto or '')
                context.setdefault('nazwa_firmy', firma_nazwa or '')
                context.setdefault('termin_od', data_rozp or '')
                context.setdefault('termin_do', data_zak or '')
                context.setdefault('specjalnosc', specjalnosc or '')
                context['rok_akademicki'] = context.get('rok_akademicki') or rok_akademicki or ''
                context.setdefault('miejsce_praktyki', firma_nazwa or '')
                context.setdefault('data_rozp', data_rozp or '')
                context.setdefault('data_zak', data_zak or '')
                # Build osoba_upowazniona from firma data if not already in dokument_data
                if osoba_imie_naz or osoba_stan:
                    osoba_upowazniona_str = f"{osoba_imie_naz or ''}, {osoba_stan or ''}".strip(', ')
                    context.setdefault('osoba_upowazniona', osoba_upowazniona_str)
                if opiekun_id:
                    from app.models.uzytkownik import Uzytkownik
                    opiekun = Uzytkownik.query.get(opiekun_id)
                    if opiekun:
                        context['imie_nazwisko_opiekuna_firmowego'] = opiekun.pelne_imie or ''
                        context['opiekun_firmowy_full_name'] = opiekun.pelne_imie or ''
                        context.setdefault('opiekun_firmowy', opiekun.pelne_imie or '')
                        context['opiekun_firmowy_full_name'] = opiekun.pelne_imie or ''
                        context['telefon_opiekuna_firmowego'] = opiekun.telefon or ''
                        context['email_opiekuna_firmowego'] = opiekun.email or ''
                        context['stanowisko_opiekuna_firmowego'] = getattr(opiekun, 'stanowisko', '') or ''

                if opiekun_uczelniany_id:
                    from app.models.uzytkownik import Uzytkownik
                    opiekun_ucz = Uzytkownik.query.get(opiekun_uczelniany_id)
                    if opiekun_ucz:
                        context['imie_nazwisko_opiekuna_uczelnianego'] = opiekun_ucz.pelne_imie or ''
                        context['opiekun_uczelniany_full_name'] = opiekun_ucz.pelne_imie or ''

                if doc_row[1] == 'ZAL_2A':
                    program_rows = db.session.execute(
                        text("SELECT numer, ppz_dzial, hpz_dzial, hpz_dni FROM program_harmonogram_praktyki WHERE dokument_id = :doc_id ORDER BY numer"),
                        {'doc_id': dokument_id}
                    ).fetchall()
                    context['program_entries'] = [
                        {'numer': r[0], 'ppz': r[1] or '', 'hpz': r[2] or '', 'dni': r[3]}
                        for r in program_rows
                    ]
                    context['student'] = {
                        'imie': imie or '',
                        'nazwisko': nazwisko or '',
                        'numer_albumu': numer_albumu or '',
                    }
                    context['selected_student'] = {
                        'id': student_id or '',
                        'imie': imie or '',
                        'nazwisko': nazwisko or '',
                        'numer_albumu': numer_albumu or '',
                        'specjalnosc': specjalnosc or '',
                        'firma_nazwa': firma_nazwa or '',
                        'termin_od': data_rozp or '',
                        'termin_do': data_zak or '',
                    }
                    context.setdefault('imie_nazwisko_studenta', f"{imie or ''} {nazwisko or ''}".strip())
                    context.setdefault('nr_albumu', numer_albumu or '')
                    context.setdefault('termin_od', data_rozp or '')
                    context.setdefault('termin_do', data_zak or '')
                    context.setdefault('nazwa_firmy', firma_nazwa or '')
                    context.setdefault('miejscowosc', firma_miasto or '')
                    if osoba_imie_naz or osoba_stan:
                        osoba_upowazniona_str = f"{osoba_imie_naz or ''}, {osoba_stan or ''}".strip(', ')
                        context.setdefault('osoba_upowazniona', osoba_upowazniona_str)

                if doc_row[1] == 'ZAL_3':
                    # Populate selected_student and student fields for ZAL_3
                    context['student'] = {
                        'imie': imie or '',
                        'nazwisko': nazwisko or '',
                        'numer_albumu': numer_albumu or '',
                    }
                    student_id_str = str(student_id) if student_id is not None else ''
                    selected_student_data = {
                        'id': student_id_str,
                        'imie': imie or '',
                        'nazwisko': nazwisko or '',
                        'numer_albumu': numer_albumu or '',
                        'forma_studiow': forma_studiow or '',
                        'specjalnosc': specjalnosc or '',
                        'firma_nazwa': firma_nazwa or '',
                        'termin_od': data_rozp or '',
                        'termin_do': data_zak or '',
                    }
                    context['selected_student'] = selected_student_data
                    context.setdefault('imie_nazwisko_studenta', f"{imie or ''} {nazwisko or ''}".strip())
                    context.setdefault('nr_albumu', numer_albumu or '')
                    context.setdefault('termin_od', data_rozp or '')
                    context.setdefault('termin_do', data_zak or '')
                    context.setdefault('nazwa_firmy', firma_nazwa or '')
                    context.setdefault('miejscowosc', firma_miasto or '')
                    osoba_upowazniona_str = ''
                    if osoba_imie_naz or osoba_stan:
                        osoba_upowazniona_str = f"{osoba_imie_naz or ''}, {osoba_stan or ''}".strip(', ')
                        context.setdefault('osoba_upowazniona', osoba_upowazniona_str)

                    opiekun_uczelniany_name = ''
                    if opiekun_uczelniany_id:
                        opiekun_uczelniany_row = db.session.execute(
                            text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                            {'id': opiekun_uczelniany_id}
                        ).fetchone()
                        if opiekun_uczelniany_row:
                            opiekun_uczelniany_name = f"{opiekun_uczelniany_row[0] or ''} {opiekun_uczelniany_row[1] or ''}".strip()

                    firmowy_opiekun_name = ''
                    firmowy_stanowisko = ''
                    if opiekun_id:
                        firmowy_row = db.session.execute(
                            text("SELECT imie, nazwisko, stanowisko FROM uzytkownik WHERE id = :id"),
                            {'id': opiekun_id}
                        ).fetchone()
                        if firmowy_row:
                            firmowy_opiekun_name = f"{firmowy_row[0] or ''} {firmowy_row[1] or ''}".strip()
                            firmowy_stanowisko = firmowy_row[2] or ''

                    nr_porozumienia = dokument_data.get('nr_porozumienia', '') or ''
                    data_zawarcia = dokument_data.get('data_zawarcia', '') or ''
                    nazwa_zakladu_pracy = dokument_data.get('nazwa_zakladu_pracy', '') or firma_nazwa or ''
                    termin_od_value = data_rozp or ''
                    termin_do_value = data_zak or ''

                    zal1_doc = None
                    if praktyka_id:
                        zal1_row = db.session.execute(text(
                            "SELECT d.id FROM dokument d "
                            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_1' "
                            "ORDER BY d.id DESC LIMIT 1"
                        ), {'praktyka_id': praktyka_id}).fetchone()
                        if zal1_row:
                            zal1_doc = zal1_row[0]

                    if zal1_doc:
                        zal1_dane = db.session.execute(text(
                            "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"
                        ), {'dokument_id': zal1_doc}).fetchall()
                        for key, value in zal1_dane:
                            if value is None:
                                continue
                            if key == 'nr_porozumienia':
                                nr_porozumienia = value
                            elif key == 'data_zawarcia':
                                data_zawarcia = value
                            elif key == 'nazwa_zakladu_pracy':
                                nazwa_zakladu_pracy = value
                            elif key == 'termin_od':
                                termin_od_value = value
                            elif key == 'termin_do':
                                termin_do_value = value

                    context['student_practice'] = {
                        student_id_str: {
                            'nr_porozumienia': nr_porozumienia,
                            'data_zawarcia': data_zawarcia,
                            'nazwa_zakladu_pracy': nazwa_zakladu_pracy,
                            'uczelniany_opiekun': dokument_data.get('uczelniany_opiekun', '') or opiekun_uczelniany_name,
                            'firmowy_opiekun': dokument_data.get('firmowy_opiekun', '') or firmowy_opiekun_name,
                            'firmowy_stanowisko': dokument_data.get('firmowy_stanowisko', '') or firmowy_stanowisko,
                            'termin_od': termin_od_value,
                            'termin_do': termin_do_value,
                            'osoba_upowazniona': dokument_data.get('osoba_upowazniona', '') or osoba_upowazniona_str,
                            'firma_nazwa': firma_nazwa or '',
                        }
                    }

                if doc_row[1] == 'ZAL_2':
                    context.setdefault('imie_nazwisko_studenta', f"{imie or ''} {nazwisko or ''}".strip())
                    context.setdefault('nr_albumu', numer_albumu or '')
                    context.setdefault('termin_od', data_rozp or '')
                    context.setdefault('termin_do', data_zak or '')
                    context.setdefault('nazwa_firmy', firma_nazwa or '')
                    context.setdefault('miejscowosc', firma_miasto or '')
                    if osoba_imie_naz or osoba_stan:
                        osoba_upowazniona_str = f"{osoba_imie_naz or ''}, {osoba_stan or ''}".strip(', ')
                        context.setdefault('osoba_upowazniona', osoba_upowazniona_str)

            if doc_row[1] == 'ZAL_4':
                # Populate efekt uczenia data for ZAL_4
                context['imie_nazwisko_studenta'] = context.get('imie_nazwisko_studenta') or f"{imie or ''} {nazwisko or ''}".strip()
                context['nr_albumu'] = context.get('nr_albumu') or numer_albumu or ''
                context['nr_indeksu'] = context.get('nr_indeksu') or numer_albumu or ''
                context['specjalnosc'] = context.get('specjalnosc') or specjalnosc or ''
                context['rok_akademicki'] = context.get('rok_akademicki') or rok_akademicki or ''
                
                # Populate selected_student for ZAL_4
                student_id_str = str(student_id) if student_id is not None else ''
                
                # Get opiekun info
                opiekun_uczelniany_name = ''
                opiekun_firmowy_name = ''
                if opiekun_uczelniany_id:
                    opiekun_ucz_row = db.session.execute(
                        text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                        {'id': opiekun_uczelniany_id}
                    ).fetchone()
                    if opiekun_ucz_row:
                        opiekun_uczelniany_name = f"{opiekun_ucz_row[0] or ''} {opiekun_ucz_row[1] or ''}".strip()
                
                if opiekun_id:
                    opiekun_row = db.session.execute(
                        text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                        {'id': opiekun_id}
                    ).fetchone()
                    if opiekun_row:
                        opiekun_firmowy_name = f"{opiekun_row[0] or ''} {opiekun_row[1] or ''}".strip()
                
                context['selected_student'] = {
                    'id': student_id_str,
                    'imie': imie or '',
                    'nazwisko': nazwisko or '',
                    'numer_albumu': numer_albumu or '',
                    'forma_studiow': forma_studiow or '',
                    'specjalnosc': specjalnosc or '',
                    'firma_nazwa': firma_nazwa or '',
                    'termin_od': data_rozp or '',
                    'termin_do': data_zak or '',
                    'opiekun_uczelniany': opiekun_uczelniany_name,
                    'opiekun_firmowy': opiekun_firmowy_name,
                    'opiekun_firmowy_id': opiekun_id or '',
                    'opiekun_uczelniany_id': opiekun_uczelniany_id or '',
                }
                
                # Add additional fields from dokument_data
                context['ilosc_godzin_praktyk'] = dokument_data.get('ilosc_godzin_praktyk', '') or (liczba_godzin if liczba_godzin is not None else '')
                context['opinia_opiekuna_uczelnianego'] = dokument_data.get('opinia_opiekuna_uczelnianego', '')
                
                # Get opiekun_firmowy_podpisano from dokument_podpis table
                opiekun_podpisano = ''
                if dokument_id and opiekun_id:
                    podpis_row = db.session.execute(
                        text(
                            "SELECT podpisano FROM dokument_podpis "
                            "WHERE dokument_id = :doc_id AND podpisujacy_id = :opiekun_id "
                            "ORDER BY id DESC LIMIT 1"
                        ),
                        {'doc_id': dokument_id, 'opiekun_id': opiekun_id}
                    ).fetchone()
                    if podpis_row and podpis_row[0]:
                        # Extract only date part (YYYY-MM-DD HH:MM:SS -> YYYY-MM-DD)
                        opiekun_podpisano = str(podpis_row[0]).split(' ')[0]
                
                context['opiekun_firmowy_podpisano'] = opiekun_podpisano
                
                context['data_opinii'] = dokument_data.get('data_opinii', '')
                context['dokument'] = {'id': dokument_id} if dokument_id else {}

                # Get learning outcomes (efekty uczenia) with their statuses
                efekt_rows = db.session.execute(
                    text(
                        "SELECT eu.numer, eu.opis, eud.status "
                        "FROM efekt_uczenia_dokumentu eud "
                        "JOIN efekt_uczenia eu ON eud.efekt_id = eu.id "
                        "WHERE eud.dokument_id = :doc_id "
                        "ORDER BY eu.numer"
                    ),
                    {'doc_id': dokument_id}
                ).fetchall()
                
                # Map statuses to Polish text
                status_mapping = {
                    'achieved': 'uzyskał/a',
                    'not_achieved': 'nie uzyskał/a',
                    'partial': 'częściowo uzyskał/a'
                }
                
                efekty_list = []
                for index, efekt_row in enumerate(efekt_rows):
                    numer = efekt_row[0]
                    opis = efekt_row[1]
                    status = efekt_row[2]
                    mapped_status = status_mapping.get(status, status or '')
                    # Use 0-based index for czy_efekt_uzyskany array
                    context['czy_efekt_uzyskany'][index] = mapped_status
                    efekty_list.append({
                        'numer': numer,
                        'opis': opis,
                        'status': status
                    })
                context['efekty'] = efekty_list
                context['czy_efekty_uzyskane'] = (
                    'uzyskał/a' if efekty_list and all(e['status'] == 'achieved' for e in efekty_list)
                    else 'nie uzyskał/a'
                )

            if doc_row[1] == 'ZAL_6':

                context['imie_nazwisko_studenta'] = context.get('imie_nazwisko_studenta') or f"{imie or ''} {nazwisko or ''}".strip()
                context['nr_indeksu'] = context.get('nr_indeksu') or dokument_data.get('nr_indeksu', '') or numer_albumu or ''
                context['nr_albumu'] = context.get('nr_albumu') or numer_albumu or ''
                context['specjalnosc'] = context.get('specjalnosc') or specjalnosc or ''
                context['rok_akademicki'] = context.get('rok_akademicki') or dokument_data.get('rok_akademicki', '') or rok_akademicki or ''
                context['miejsce_praktyki'] = context.get('miejsce_praktyki') or firma_nazwa or ''
                context['data_rozp'] = context.get('data_rozp') or data_rozp or ''
                context['data_zak'] = context.get('data_zak') or data_zak or ''
                context['opiekun_firmowy'] = context.get('opiekun_firmowy') or dokument_data.get('opiekun_firmowy', '')

                wpis_rows = db.session.execute(
                    text(
                        "SELECT numer_dnia, data_wpisu, opis_prac FROM wpis_dziennika "
                        "WHERE dokument_id = :doc_id ORDER BY numer_dnia"
                    ),
                    {'doc_id': dokument_id}
                ).fetchall()
                wpisy = []
                for wpis_row in wpis_rows:
                    numer_dnia, data_wpisu, opis_prac = wpis_row
                    efekty_rows = db.session.execute(
                        text(
                            "SELECT nr_efektu FROM wpis_efekt "
                            "WHERE dokument_id = :doc_id AND numer_dnia = :numer ORDER BY nr_efektu"
                        ),
                        {'doc_id': dokument_id, 'numer': numer_dnia}
                    ).fetchall()
                    efekty = [int(r[0]) for r in efekty_rows if r[0] is not None]
                    wpisy.append({
                        'dzien': numer_dnia,
                        'data': data_wpisu or '',
                        'opis': opis_prac or '',
                        'efekty': efekty,
                    })
                context['wpisy'] = wpisy

        if not info and doc_row[1] == 'ZAL_6':
            context['imie_nazwisko_studenta'] = context.get('imie_nazwisko_studenta') or dokument_data.get('imie_nazwisko_studenta', '')
            context['nr_indeksu'] = context.get('nr_indeksu') or dokument_data.get('nr_indeksu', '') or dokument_data.get('nr_albumu', '')
            context['nr_albumu'] = context.get('nr_albumu') or dokument_data.get('nr_albumu', '')
            context['specjalnosc'] = context.get('specjalnosc') or dokument_data.get('specjalnosc', '')
            context['rok_akademicki'] = context.get('rok_akademicki') or dokument_data.get('rok_akademicki', '')
            context['miejsce_praktyki'] = context.get('miejsce_praktyki') or dokument_data.get('miejsce_praktyki', dokument_data.get('nazwa_zakladu_pracy', ''))
            context['data_rozp'] = context.get('data_rozp') or dokument_data.get('data_rozp', dokument_data.get('termin_od', ''))
            context['data_zak'] = context.get('data_zak') or dokument_data.get('data_zak', dokument_data.get('termin_do', ''))
            context['wykaz_zalacznikow'] = context.get('wykaz_zalacznikow') or dokument_data.get('wykaz_zalacznikow', '')
            context.setdefault('wpisy', [])

            # Provide student_practice mapping for templates (used by ZAL_3 macro)
            try:
                context.setdefault('student_practice', {})
                student_id_str = str(student_id) if student_id is not None else ''
                if student_id_str:
                    entry = context['student_practice'].setdefault(student_id_str, {})
                    entry.setdefault('osoba_upowazniona', context.get('osoba_upowazniona', ''))
            except Exception:
                current_app.logger.exception('Błąd budowania student_practice dla szablonu')

        # Render template
        template_name = (
            'Zal_9.docx' if doc_row[1] == 'ZAL_9' else
            'Zal_7.docx' if doc_row[1] == 'ZAL_7' else
            'Zal_1.docx' if doc_row[1] == 'ZAL_1' else
            'Zal_2.docx' if doc_row[1] == 'ZAL_2' else
            'Zal_3.docx' if doc_row[1] == 'ZAL_3' else
            'Zal_4.docx' if doc_row[1] == 'ZAL_4' else
            'Zal_6.docx' if doc_row[1] == 'ZAL_6' else
            'Zal_2a.docx' if doc_row[1] == 'ZAL_2A' else
            None
        )
        if not template_name:
            current_app.logger.error('Nieobsługiwany typ dokumentu do pobrania: %s', doc_row[1])
            flash('Nieobsługiwany typ dokumentu do pobrania.', 'danger')
            return redirect(url_for('dashboard.index'))

        template_path = os.path.join(current_app.root_path, 'docs', template_name)
        if not os.path.exists(template_path):
            template_path = os.path.join(current_app.root_path, 'docs', template_name)

        if not os.path.exists(template_path):
            current_app.logger.error('Brak szablonu %s w app/docs', template_name)
            flash('Szablon dokumentu nie został znaleziony na serwerze.', 'danger')
            return redirect(url_for('dashboard.index'))

        try:
            tpl = DocxTemplate(template_path)
            tpl.render(context)
            tpl.save(docx_path)
        except Exception:
            current_app.logger.exception('Błąd generowania DOCX z szablonu')
            flash('Wystąpił błąd podczas generowania dokumentu.', 'danger')
            return redirect(url_for('dashboard.index'))

        if file_format == 'docx':
            if os.path.exists(docx_path):
                if doc_row[1] in ('ZAL_1', 'ZAL_2', 'ZAL_3', 'ZAL_4', 'ZAL_6', 'ZAL_9', 'ZAL_2A'):
                    record_document_download(dokument_id, current_user.id)
                return send_file(docx_path, as_attachment=True)
        else:
            # Convert generated DOCX to PDF
            try:
                convert_docx_to_pdf(docx_path, pdf_path)
            except Exception:
                pass

            if os.path.exists(pdf_path):
                if doc_row[1] in ('ZAL_1', 'ZAL_2', 'ZAL_4', 'ZAL_6', 'ZAL_9', 'ZAL_2A'):
                    record_document_download(dokument_id, current_user.id)
                return send_file(pdf_path, as_attachment=True)

    except Exception:
        current_app.logger.exception('Błąd podczas przygotowywania pliku do pobrania')

    flash('Nie udało się wygenerować pliku.', 'danger')
    return redirect(url_for('dashboard.index'))


@bp.route('/profil/student', methods=['GET', 'POST'])
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
        'profil/student.html',
        uzytkownik=current_user
    )


@bp.route('/formularz/zalacznik-1', methods=['GET', 'POST'])
@login_required
def zalacznik_1():
    """Formularz załącznika 1 - Porozumienie z zakładem pracy."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')
    selected_student = None
    dokument = None
    dokument_data = {}
    status = None
    editing_allowed = True
    opiekun_prefill = ''

    if current_user.rola.nazwa != 'dziekanat' and not dokument_id:
        flash('Tylko dziekanat może wypełniać załącznik 1.', 'danger')
        return redirect(url_for('dashboard.index'))

    if action_query and dokument_id:
        if action_query == 'sign':
            if current_user.rola.nazwa not in ('dyrektor', 'opiekun_firmowy'):
                flash('Tylko dyrektor lub opiekun firmowy może podpisać i zaakceptować załącznik 1.', 'danger')
            elif sign_and_accept_attachment1(dokument_id):
                flash('Załącznik 1 został podpisany i zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

        elif action_query == 'reject':
            if current_user.rola.nazwa not in ('dyrektor', 'opiekun_firmowy'):
                flash('Tylko dyrektor lub opiekun firmowy może odrzucić załącznik 1.', 'danger')
            elif reject_attachment1(dokument_id):
                flash('Załącznik 1 został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić tego dokumentu.', 'danger')

    if dokument_id:
        doc_row = db.session.execute(
            text(
                "SELECT id, status, praktyka_id FROM dokument "
                "WHERE id = :doc_id AND typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_1')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1], 'praktyka_id': doc_row[2]}
            status = doc_row[1]
            selected_practice_id = selected_practice_id or dokument['praktyka_id']
            editing_allowed = status == 'rejected'

            dane = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane}

            if selected_practice_id and not selected_student:
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
        else:
            flash('Nie znaleziono załącznika 1.', 'danger')
            return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'save':
            if current_user.rola.nazwa != 'dziekanat':
                flash('Tylko dziekanat może zapisać załącznik 1.', 'danger')
                return redirect(url_for('dashboard.index'))

            if dokument_id and status != 'rejected':
                flash('Ten dokument nie może być edytowany.', 'danger')
                return redirect(url_for('dashboard.index'))

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
                'dyrektor': request.form.get('dyrektor'),
            }

            if save_attachment1_data(form_data, dokument_id):
                flash('Dane załącznika 1 zostały zapisane.', 'success')
                return redirect(url_for('dashboard.index'))

            flash('Wystąpił problem podczas zapisu formularza.', 'danger')

        elif action == 'sign' and dokument_id:
            if current_user.rola.nazwa not in ('dyrektor', 'opiekun_firmowy'):
                flash('Tylko dyrektor lub opiekun firmowy może podpisać i zaakceptować załącznik 1.', 'danger')
            elif sign_and_accept_attachment1(dokument_id):
                flash('Załącznik 1 został podpisany i zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

        elif action == 'reject' and dokument_id:
            if current_user.rola.nazwa not in ('dyrektor', 'opiekun_firmowy'):
                flash('Tylko dyrektor lub opiekun firmowy może odrzucić załącznik 1.', 'danger')
            elif reject_attachment1(dokument_id):
                flash('Załącznik 1 został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić tego dokumentu.', 'danger')

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

    director_user = Uzytkownik.query.join(Rola).filter(Rola.nazwa == 'dyrektor').first()
    director_full_name = ''
    if director_user:
        director_full_name = f"{director_user.imie or ''} {director_user.nazwisko or ''}".strip()

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

    nr_porozumienia = dokument_data.get('nr_porozumienia', generate_agreement_number())
    data_zawarcia = dokument_data.get('data_zawarcia', date.today().isoformat())

    return render_template(
        'forms/zalacznik_1.html',
        nr_porozumienia=nr_porozumienia,
        data_zawarcia=data_zawarcia,
        studenci=studenci,
        reprezentanci_uczelni=reprezentanci_uczelni,
        student_practice=student_practice,
        student_practice_json=json.dumps(student_practice),
        selected_student=selected_student,
        dokument=dokument,
        dokument_data=dokument_data,
        editing_allowed=editing_allowed,
        opiekun_prefill=opiekun_prefill,
        director_full_name=director_full_name,
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

        # Utwórz dokument w statusie awaiting_signature (po wypełnieniu przez dziekanat)
        db.session.execute(
            text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
            ),
            {
                'praktyka_id': praktyka_id,
                'typ_id': typ_id,
                'utworzony_przez': current_user.id,
                'status': 'awaiting_signature',
                'ostatni_edytor': current_user.id,
            }
        )

        db.session.commit()

        doc_row = db.session.execute(
            text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        dokument_id = doc_row[0] if doc_row else None

        if dokument_id:
            # Utwórz wpisy udostępnionego dokumentu — na etapie oczekiwania nikt nie może edytować
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            # student: tylko podgląd
            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            # dziekanat: po utworzeniu nie edytuje już dokumentu
            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            # opiekun uczelniany: podgląd
            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            # opiekun firmowy: może podpisać i zaakceptować
            if opiekun_firmowy_id and role_ids.get('opiekun_firmowy'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_firmowy_id,
                        'rola_id': role_ids['opiekun_firmowy'],
                    }
                )

            # dyrektor: może podpisać i zaakceptować
            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            # Utwórz wstępne wpisy dokument_podpis dla oczekiwanych podpisujących (0)
            if role_ids.get('dyrektor'):
                db.session.execute(
                    text("INSERT OR IGNORE INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) VALUES (:doc_id, (SELECT id FROM uzytkownik WHERE rola_id = :rola_id LIMIT 1), 0)"),
                    {'doc_id': dokument_id, 'rola_id': role_ids['dyrektor']}
                )
            if opiekun_firmowy_id:
                db.session.execute(
                    text("INSERT OR IGNORE INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) VALUES (:doc_id, :podpisujacy_id, 0)"),
                    {'doc_id': dokument_id, 'podpisujacy_id': opiekun_firmowy_id}
                )

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
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')
    selected_student = None
    dokument = None
    dokument_data = {}

    # Uprawnienia tworzenia: tylko dziekanat może tworzyć nowy dokument
    if current_user.rola.nazwa != 'dziekanat' and not dokument_id:
        flash('Tylko dziekanat może utworzyć załącznik 2.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Obsługa akcji podpisania (GET linki z dashboard)
    if action_query and dokument_id:
        if action_query == 'sign':
            if current_user.rola.nazwa not in ('dyrektor', 'opiekun_firmowy'):
                flash('Tylko dyrektor lub opiekun firmowy może podpisać i zaakceptować załącznik 2.', 'danger')
            elif sign_and_accept_attachment2(dokument_id):
                flash('Załącznik 2 został podpisany i zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

    if request.method == 'POST':
        # tworzenie dokumentu (dziekanat)
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

    director_user = Uzytkownik.query.join(Rola).filter(Rola.nazwa == 'dyrektor').first()
    director_full_name = f"{director_user.imie or ''} {director_user.nazwisko or ''}".strip() if director_user else ''
    opiekun_firmowy_full_name = ''

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, p.opiekun_firmowy_id "
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
            opiekun_id = student_row[4]
            if opiekun_id:
                opiekun_row = db.session.execute(
                    text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                    {'id': opiekun_id}
                ).fetchone()
                if opiekun_row:
                    opiekun_firmowy_full_name = f"{opiekun_row[0] or ''} {opiekun_row[1] or ''}".strip()

    # Jeśli podano dokument_id — pobierz dokument do podglądu (bez możliwości edycji)
    if dokument_id:
        doc_row = db.session.execute(
            text(
                "SELECT id, status, praktyka_id FROM dokument "
                "WHERE id = :doc_id AND typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_2')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1], 'praktyka_id': doc_row[2]}
            dane = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane}
            # Pobierz dane studenta powiązanego z praktyką, aby poprawnie wyświetlić sekcję 'Dane studenta'
            try:
                praktik_row = db.session.execute(
                    text(
                        "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                        "FROM praktyka p JOIN uzytkownik u ON p.student_id = u.id "
                        "WHERE p.id = :praktyka_id"
                    ),
                    {'praktyka_id': dokument['praktyka_id']}
                ).fetchone()
                if praktik_row:
                    selected_student = {
                        'id': praktik_row[0],
                        'imie': praktik_row[1] or '',
                        'nazwisko': praktik_row[2] or '',
                        'numer_albumu': praktik_row[3] or '',
                    }
                    # Ensure dokument_data carries student_id for template compatibility
                    dokument_data.setdefault('student_id', str(selected_student['id']))
            except Exception:
                current_app.logger.exception('Błąd pobierania danych studenta dla załącznika 2')
        else:
            flash('Nie znaleziono załącznika 2.', 'danger')
            return redirect(url_for('dashboard.index'))

    rola_student = Rola.query.filter_by(nazwa='student').first()
    studenci = []
    if not selected_student and rola_student:
        studenci = (
            Uzytkownik.query
            .filter_by(rola_id=rola_student.id, jest_aktywny=True)
            .order_by(Uzytkownik.numer_albumu)
            .all()
        )

    # GET: pokaż ekran potwierdzenia utworzenia dokumentu lub podgląd istniejącego
    return render_template(
        'forms/zalacznik_2.html',
        studenci=studenci,
        selected_student=selected_student,
        dokument=dokument,
        dokument_data=dokument_data,
        director_full_name=director_full_name,
        opiekun_firmowy_full_name=opiekun_firmowy_full_name,
    )


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
        nr_indeksu = form_data.get('nr_indeksu')
        data_uzgodnienia = form_data.get('data_uzgodnienia') or date.today().isoformat()

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

        # Sprawdź czy dokument już istnieje
        existing = db.session.execute(
            text("SELECT id, status FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()

        dokument_id = existing[0] if existing else None
        dokument_status = existing[1] if existing else None

        # Jeśli dokument nie istnieje: tworzy go dziekanat w statusie in_progress
        if not dokument_id:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                    " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'status': 'in_progress',
                    'ostatni_edytor': current_user.id,
                }
            )
            db.session.commit()

            document_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            dokument_id = document_row[0] if document_row else None

            if current_user.rola.nazwa == 'dziekanat' and dokument_id:
                role_rows = db.session.execute(
                    text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','opiekun_firmowy','dyrektor')")
                ).fetchall()
                role_ids = {row[0]: row[1] for row in role_rows}

                if student_id and role_ids.get('student'):
                    db.session.execute(
                        text(
                            "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                            "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                            "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                            "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                            "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                            " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                        ),
                        {
                            'udostepniajacy': current_user.id,
                            'dokument_id': dokument_id,
                            'rola_id': role_ids['dyrektor'],
                        }
                    )

        # If updating existing document
        if dokument_id:
            # If current user is opiekun_firmowy -> allow edits when in_progress or rejected
            if current_user.rola.nazwa == 'opiekun_firmowy' and dokument_status in (None, 'in_progress', 'rejected'):
                # remove old program entries
                db.session.execute(text("DELETE FROM program_harmonogram_praktyki WHERE dokument_id = :doc_id"), {'doc_id': dokument_id})
                # insert new program/harmonogram rows
                for idx in range(13):
                    numer = idx + 1
                    ppz_value = ppz_dzial[idx].strip() if idx < len(ppz_dzial) else ''
                    hpz_value = hpz_dzial[idx].strip() if idx < len(hpz_dzial) else ''
                    hpz_value_days = hpz_dni[idx].strip() if idx < len(hpz_dni) else ''
                    # jeśli brak wartości lub 0 -> zapisz NULL w bazie (None w SQLAlchemy)
                    if str(hpz_value_days).isdigit():
                        val = int(hpz_value_days)
                        hpz_days = val if val > 0 else None
                    else:
                        hpz_days = None

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

                # zapisz dane dokumentu (nr indeksu i łączna liczba dni)
                db.session.execute(text("DELETE FROM dane_dokumentu WHERE dokument_id = :doc_id"), {'doc_id': dokument_id})
                if nr_indeksu:
                    db.session.execute(text("INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, 'nr_indeksu', :val, :wypelniajacy)"), {'doc_id': dokument_id, 'val': nr_indeksu, 'wypelniajacy': current_user.id})
                hpz_total_days_value = form_data.get('hpz_total_days')
                if hpz_total_days_value is not None:
                    db.session.execute(
                        text("INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, 'lacznie_dni', :val, :wypelniajacy)"),
                        {'doc_id': dokument_id, 'val': hpz_total_days_value, 'wypelniajacy': current_user.id}
                    )

                # sprawdź kompletność programowego i harmonogramu:
                # - wszystkie wiersze programu (ppz_dzial) muszą być wypełnione
                # - w harmonogramie każdy wpis hpz_dzial musi mieć odpowiadającą liczbę dni i odwrotnie
                # - suma dni hpz_dni musi wynosić co najmniej 120
                complete = True
                for idx in range(len(ppz_dzial)):
                    ppz_value = ppz_dzial[idx].strip()
                    if not ppz_value:
                        complete = False
                        break

                current_app.logger.debug('PPZ count=%s, HPZ count=%s', len(ppz_dzial), len(hpz_dni))
                current_app.logger.debug('HPZ dni raw: %s', hpz_dni)
                total_hpz_days = 0
                if complete:
                    for idx in range(13):
                        hpz_value = hpz_dzial[idx].strip() if idx < len(hpz_dzial) else ''
                        hpz_value_days = hpz_dni[idx].strip() if idx < len(hpz_dni) else ''
                        # Treat '0' or non-digit as no value for days
                        hpz_num = int(hpz_value_days) if hpz_value_days.isdigit() else None
                        has_hpz_text = bool(hpz_value)
                        has_hpz_days = (hpz_num is not None and hpz_num > 0)
                        # If one side present and the other not -> incomplete
                        if has_hpz_text != has_hpz_days:
                            complete = False
                            break
                        if has_hpz_days:
                            total_hpz_days += hpz_num

                    current_app.logger.debug('Computed total_hpz_days=%s before threshold check', total_hpz_days)
                    if complete and total_hpz_days < 120:
                        complete = False
                    current_app.logger.debug('Completeness after checks: %s', complete)

                if complete:
                    # zamknij edycję i przejdź do awaiting_signature
                    db.session.execute(text("UPDATE dokument SET status = 'awaiting_signature', ostatni_edytor = :ostatni WHERE id = :doc_id"), {'ostatni': current_user.id, 'doc_id': dokument_id})
                    # zablokuj edycję opiekuna firmowego
                    db.session.execute(text("UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"), {'doc_id': dokument_id})
                    # utwórz wpisy podpisów i akceptacji dla oczekiwanych osób
                    # student podpis
                    if student_id:
                        result = db.session.execute(
                            text(
                                "UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL "
                                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
                            ),
                            {'doc_id': dokument_id, 'podpisujacy_id': student_id}
                        )
                        if result.rowcount == 0:
                            db.session.execute(
                                text(
                                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                                    "VALUES (:doc_id, :podpisujacy_id, 0)"
                                ),
                                {'doc_id': dokument_id, 'podpisujacy_id': student_id}
                            )
                    # opiekun uczelniany
                    if opiekun_uczelniany_id:
                        result = db.session.execute(
                            text(
                                "UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL "
                                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
                            ),
                            {'doc_id': dokument_id, 'podpisujacy_id': opiekun_uczelniany_id}
                        )
                        if result.rowcount == 0:
                            db.session.execute(
                                text(
                                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                                    "VALUES (:doc_id, :podpisujacy_id, 0)"
                                ),
                                {'doc_id': dokument_id, 'podpisujacy_id': opiekun_uczelniany_id}
                            )
                        result = db.session.execute(
                            text(
                                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 0, zaakceptowano = NULL "
                                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
                            ),
                            {'doc_id': dokument_id, 'akceptujacy_id': opiekun_uczelniany_id}
                        )
                        if result.rowcount == 0:
                            db.session.execute(
                                text(
                                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany) "
                                    "VALUES (:doc_id, :akceptujacy_id, 0)"
                                ),
                                {'doc_id': dokument_id, 'akceptujacy_id': opiekun_uczelniany_id}
                            )
                    # opiekun firmowy
                    if opiekun_firmowy_id:
                        result = db.session.execute(
                            text(
                                "UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL "
                                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
                            ),
                            {'doc_id': dokument_id, 'podpisujacy_id': opiekun_firmowy_id}
                        )
                        if result.rowcount == 0:
                            db.session.execute(
                                text(
                                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                                    "VALUES (:doc_id, :podpisujacy_id, 0)"
                                ),
                                {'doc_id': dokument_id, 'podpisujacy_id': opiekun_firmowy_id}
                            )
                        result = db.session.execute(
                            text(
                                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 0, zaakceptowano = NULL "
                                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
                            ),
                            {'doc_id': dokument_id, 'akceptujacy_id': opiekun_firmowy_id}
                        )
                        if result.rowcount == 0:
                            db.session.execute(
                                text(
                                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany) "
                                    "VALUES (:doc_id, :akceptujacy_id, 0)"
                                ),
                                {'doc_id': dokument_id, 'akceptujacy_id': opiekun_firmowy_id}
                            )

                    # usuń ewentualne duplikaty
                    db.session.execute(
                        text(
                            "DELETE FROM dokument_podpis "
                            "WHERE dokument_id = :doc_id "
                            "AND id NOT IN (SELECT MIN(id) FROM dokument_podpis WHERE dokument_id = :doc_id GROUP BY podpisujacy_id)"
                        ),
                        {'doc_id': dokument_id}
                    )
                    db.session.execute(
                        text(
                            "DELETE FROM dokument_akceptacja "
                            "WHERE dokument_id = :doc_id "
                            "AND id NOT IN (SELECT MIN(id) FROM dokument_akceptacja WHERE dokument_id = :doc_id GROUP BY akceptujacy_id)"
                        ),
                        {'doc_id': dokument_id}
                    )
                else:
                    # tylko aktualizuj ostatniego edytora
                    db.session.execute(text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"), {'ostatni': current_user.id, 'doc_id': dokument_id})

            elif current_user.rola.nazwa == 'dziekanat':
                # dziekanat może tylko utworzyć dokument i zapisać podstawowe dane przy tworzeniu
                db.session.execute(text("DELETE FROM dane_dokumentu WHERE dokument_id = :doc_id"), {'doc_id': dokument_id})
                if nr_indeksu:
                    db.session.execute(text("INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc) VALUES (:doc_id, 'nr_indeksu', :val)"), {'doc_id': dokument_id, 'val': nr_indeksu})
                db.session.execute(text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"), {'ostatni': current_user.id, 'doc_id': dokument_id})
            else:
                # brak uprawnień do zapisu
                return False

            db.session.commit()
            return True

        return False
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 2a: {e}')
        return False


def sign_and_accept_attachment2a(dokument_id):
    """Podpisanie i (dla uprawnionych) akceptacja załącznika 2a."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT praktyka_id, status, typ_dokumentu_id FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[1] != 'awaiting_signature':
            return False

        role_name = current_user.rola.nazwa
        if role_name not in ('student', 'opiekun_uczelniany', 'opiekun_firmowy'):
            return False

        # student only signs
        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        # opiekun_uczelniany and opiekun_firmowy also accept
        if role_name in ('opiekun_uczelniany', 'opiekun_firmowy'):
            result = db.session.execute(
                text(
                    "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                    "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )
            if result.rowcount == 0:
                db.session.execute(
                    text(
                        "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano)"
                        " VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                    ),
                    {
                        'doc_id': dokument_id,
                        'akceptujacy_id': current_user.id,
                        'zaakceptowano': datetime.now(),
                    }
                )

        signed_count = db.session.execute(
            text(
                "SELECT COUNT(DISTINCT dp.podpisujacy_id) FROM dokument_podpis dp "
                "JOIN uzytkownik u ON dp.podpisujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE dp.dokument_id = :doc_id AND dp.czy_podpisany = 1 "
                "AND r.nazwa IN ('student','opiekun_uczelniany','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        accepted_count = db.session.execute(
            text(
                "SELECT COUNT(DISTINCT da.akceptujacy_id) FROM dokument_akceptacja da "
                "JOIN uzytkownik u ON da.akceptujacy_id = u.id "
                "JOIN role r ON u.rola_id = r.id "
                "WHERE da.dokument_id = :doc_id AND da.czy_zaakceptowany = 1 "
                "AND r.nazwa IN ('opiekun_uczelniany','opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        if signed_count >= 3 and accepted_count >= 2:
            db.session.execute(
                text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'status': 'completed',
                    'ostatni_edytor': current_user.id,
                }
            )
            db.session.execute(
                text("INSERT OR IGNORE INTO dane_dokumentu (dokument_id, klucz, wartosc) VALUES (:doc_id, 'data_uzgodnienia', :val)"),
                {'doc_id': dokument_id, 'val': date.today().isoformat()}
            )
            update_practice_stage_from_typ(doc_row[0], doc_row[2])
        else:
            db.session.execute(
                text("UPDATE dokument SET ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                {
                    'doc_id': dokument_id,
                    'ostatni_edytor': current_user.id,
                }
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania i akceptacji załącznika 2a: {e}')
        return False


def reject_attachment2a(dokument_id):
    """Odrzucenie załącznika 2a przez opiekuna uczelnianego lub opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[0] != 'awaiting_signature':
            return False

        role_name = current_user.rola.nazwa
        if role_name not in ('opiekun_uczelniany', 'opiekun_firmowy'):
            return False

        db.session.execute(
            text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
            {
                'doc_id': dokument_id,
                'status': 'rejected',
                'ostatni_edytor': current_user.id,
            }
        )
        db.session.execute(
            text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        )
        db.session.execute(
            text("UPDATE dokument_akceptacja SET czy_zaakceptowany = 0, zaakceptowano = NULL WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        )
        # przywróć możliwość edycji opiekunowi firmowemu
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 1 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia załącznika 2a: {e}')
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
    dokument = None
    # default fallbacks for prefilled opiekun (avoid NameError and provide id for template)
    opiekun_prefill = ''
    opiekun_prefill_id = None
    # default fallback for prefilled opiekun (avoids NameError when no practice selected)
    opiekun_prefill = ''
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')

    # obsługa akcji podpisania/odrzucenia
    if action_query and dokument_id:
        if action_query == 'sign':
            if current_user.rola.nazwa not in ('student', 'opiekun_uczelniany', 'opiekun_firmowy'):
                flash('Nie masz uprawnień do podpisania tego dokumentu.', 'danger')
            elif sign_and_accept_attachment2a(dokument_id):
                flash('Dokument został podpisany/zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

        elif action_query == 'reject':
            if current_user.rola.nazwa not in ('opiekun_uczelniany', 'opiekun_firmowy'):
                flash('Nie masz uprawnień do odrzucenia tego dokumentu.', 'danger')
            elif reject_attachment2a(dokument_id):
                flash('Dokument został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić tego dokumentu.', 'danger')

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
                'hpz_total_days': request.form.get('hpz_total_days', '0'),
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
                'hpz_total_days': request.form.get('hpz_total_days', '0'),
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
    director_full_name = ''
    opiekun_firmowy_full_name = ''
    opiekun_uczelniany_full_name = ''

    # Pobierz listę studentów i ostatnie dane praktyki (do autouzupełniania)
    from app.models.uzytkownik import Uzytkownik, Rola
    from app import db
    from sqlalchemy import text

    director_user = Uzytkownik.query.join(Rola).filter(Rola.nazwa == 'dyrektor').first()
    if director_user:
        director_full_name = f"{director_user.imie or ''} {director_user.nazwisko or ''}".strip()

    if dokument_id and not selected_practice_id:
        existing_doc = db.session.execute(
            text(
                "SELECT praktyka_id, status FROM dokument "
                "WHERE id = :doc_id AND typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_2A')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()
        if existing_doc:
            selected_practice_id = existing_doc[0]
            dokument = {'id': dokument_id, 'status': existing_doc[1]}

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
                "up.imie || ' ' || up.nazwisko AS reprezentant_firmy, p.data_rozpoczecia, p.data_zakonczenia, "
                "p.opiekun_firmowy_id, p.opiekun_uczelniany_id "
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
            opiekun_firmowy_id = student_row[9]
            opiekun_uczelniany_id = student_row[10]
            if opiekun_firmowy_id:
                opiekun_row = db.session.execute(
                    text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                    {'id': opiekun_firmowy_id}
                ).fetchone()
                if opiekun_row:
                    opiekun_firmowy_full_name = f"{opiekun_row[0] or ''} {opiekun_row[1] or ''}".strip()
            if opiekun_uczelniany_id:
                opiekun_uczelniany_row = db.session.execute(
                    text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                    {'id': opiekun_uczelniany_id}
                ).fetchone()
                if opiekun_uczelniany_row:
                    opiekun_uczelniany_full_name = f"{opiekun_uczelniany_row[0] or ''} {opiekun_uczelniany_row[1] or ''}".strip()

    # jeśli dokument został utworzony wcześniej, pobierz jego dane i wpisy programu
    dokument = None
    dokument_data = {}
    program_entries = []
    editing_allowed = False
    if selected_practice_id:
        doc_row = db.session.execute(
            text("SELECT id, status FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_2A') ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1]}
            dokument_id = dokument['id']
            # pobierz dane dokumentu
            dane = db.session.execute(text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"), {'doc_id': dokument_id}).fetchall()
            dokument_data = {r[0]: r[1] for r in dane}
            # pobierz wpisy programu/harmonogramu
            rows = db.session.execute(text("SELECT numer, ppz_dzial, hpz_dzial, hpz_dni FROM program_harmonogram_praktyki WHERE dokument_id = :doc_id ORDER BY numer"), {'doc_id': dokument_id}).fetchall()
            program_entries = [{'numer': r[0], 'ppz': r[1] or '', 'hpz': r[2] or '', 'dni': r[3] or 0} for r in rows]
            # ustal uprawnienia edycji: opiekun_firmowy może edytować gdy status in_progress lub rejected
            if current_user.rola.nazwa == 'opiekun_firmowy' and dokument['status'] in ('in_progress', 'rejected'):
                editing_allowed = True

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
        dokument=dokument,
        dokument_data=dokument_data,
        program_entries=program_entries,
        editing_allowed=editing_allowed,
        director_full_name=director_full_name,
        opiekun_firmowy_full_name=opiekun_firmowy_full_name,
        opiekun_uczelniany_full_name=opiekun_uczelniany_full_name,
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

        if current_user.rola.nazwa != 'dziekanat':
            current_app.logger.error('Tylko dziekanat może tworzyć załącznik 3.')
            return False

        existing = db.session.execute(
            text(
                "SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id ORDER BY id DESC LIMIT 1"
            ),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        if existing:
            current_app.logger.error('Załącznik 3 już istnieje dla tej praktyki.')
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
                'status': 'awaiting_signature',
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
                    " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 0)"
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
                    " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 1, 0)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )

        db.session.commit()


        # Dziekanat tworzy dokument, lecz nie powinien nadpisywać danych formularza
        if current_user.rola.nazwa != 'dziekanat':
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


def sign_attachment3_by_dyrektor(dokument_id):
    """Podpisanie załącznika 3 przez dyrektora Instytutu."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()
        if not doc_row or doc_row[0] != 'awaiting_signature':
            return False

        if current_user.rola.nazwa != 'dyrektor':
            return False

        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'doc3_step1', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_podpisac = 0 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'dyrektor')"
            ),
            {'doc_id': dokument_id}
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania załącznika 3 przez dyrektora: {e}')
        return False


def sign_attachment3_by_opiekun_firmowy(dokument_id, action):
    """Potwierdzenie zgłoszenia i szkolenia przez opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    if action not in ('confirm_registration', 'confirm_training'):
        return False

    try:
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()
        if not doc_row or doc_row[0] != 'doc3_step1':
            return False

        if current_user.rola.nazwa != 'opiekun_firmowy':
            return False

        key = 'potwierdzenie_zgloszenia' if action == 'confirm_registration' else 'potwierdzenie_szkolenia'
        db.session.execute(
            text(
                "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc) "
                "VALUES (:doc_id, :klucz, :wartosc)"
            ),
            {
                'doc_id': dokument_id,
                'klucz': key,
                'wartosc': date.today().isoformat(),
            }
        )

        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        confirmed_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM dane_dokumentu "
                "WHERE dokument_id = :doc_id AND klucz IN ('potwierdzenie_zgloszenia', 'potwierdzenie_szkolenia')"
            ),
            {'doc_id': dokument_id}
        ).scalar()

        if confirmed_count == 2:
            db.session.execute(
                text(
                    "UPDATE dokument SET status = 'doc3_step2', ostatni_edytor = :ostatni WHERE id = :doc_id"
                ),
                {'doc_id': dokument_id, 'ostatni': current_user.id}
            )
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_podpisac = 0 "
                    "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
                ),
                {'doc_id': dokument_id}
            )
        else:
            db.session.execute(
                text(
                    "UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"
                ),
                {'doc_id': dokument_id, 'ostatni': current_user.id}
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd potwierdzenia załącznika 3 przez opiekuna firmowego: {e}')
        return False


def is_related_attachment6_completed_for_zalacznik_3(dokument_id):
    from app import db
    from sqlalchemy import text

    row = db.session.execute(
        text(
            "SELECT d6.status FROM dokument d3 "
            "JOIN praktyka p ON d3.praktyka_id = p.id "
            "JOIN dokument d6 ON d6.praktyka_id = p.id "
            "JOIN typ_dokumentu t6 ON d6.typ_dokumentu_id = t6.id "
            "WHERE d3.id = :doc_id AND t6.kod = 'ZAL_6' "
            "ORDER BY d6.id DESC LIMIT 1"
        ),
        {'doc_id': dokument_id}
    ).fetchone()
    return bool(row and row[0] == 'completed')


def update_attachment3_by_opiekun_firmowy(dokument_id, form_data):
    from app import db
    from sqlalchemy import text

    if current_user.rola.nazwa != 'opiekun_firmowy':
        return False

    doc_row = db.session.execute(
        text("SELECT status FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row or doc_row[0] != 'doc3_step2':
        return False

    if not is_related_attachment6_completed_for_zalacznik_3(dokument_id):
        return False

    dane_map = {
        'miejscowość': form_data.get('miejscowosc', ''),
        'data_kier': form_data.get('data_podpisu_firmowego', ''),
        'uwagi_kier': form_data.get('uwagi', ''),
        'ocena_przebiegu_of': form_data.get('ocena_przebiegu_1', ''),
        'ocena_opisowa_of': form_data.get('ocena_opisowa_1', ''),
        'data_przebiegu_of': form_data.get('data_przebiegu_1', ''),
    }

    try:
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
            text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd aktualizacji załącznika 3 przez opiekuna firmowego: {e}')
        return False


def sign_and_accept_attachment3_by_opiekun_firmowy(dokument_id):
    from app import db
    from sqlalchemy import text

    if current_user.rola.nazwa != 'opiekun_firmowy':
        return False

    doc_row = db.session.execute(
        text("SELECT status FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row or doc_row[0] != 'doc3_step2':
        return False

    if not is_related_attachment6_completed_for_zalacznik_3(dokument_id):
        return False

    try:
        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano) "
                    "VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'doc3_step3', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu i akceptacji załącznika 3 przez opiekuna firmowego: {e}')
        return False


def update_attachment3_by_opiekun_uczelniany(dokument_id, form_data):
    from app import db
    from sqlalchemy import text

    if current_user.rola.nazwa != 'opiekun_uczelniany':
        return False

    doc_row = db.session.execute(
        text("SELECT praktyka_id, status FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row:
        return False
    
    # Nie pozwalaj edytować jeśli dokument jest już ukończony
    if doc_row[1] == 'completed':
        return False

    praktyka_id = doc_row[0]
    
    # Sprawdzenie czy ZAL_7 jest completed
    zal7_row = db.session.execute(
        text(
            "SELECT d.status FROM dokument d "
            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_7' "
            "ORDER BY d.id DESC LIMIT 1"
        ),
        {'praktyka_id': praktyka_id}
    ).fetchone()
    if not zal7_row or zal7_row[0] != 'completed':
        return False

    dane_map = {
        'ocena_sprawozdania': form_data.get('ocena_sprawozdania', ''),
    }

    try:
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
            text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd aktualizacji załącznika 3 przez opiekuna uczelnianego: {e}')
        return False


def sign_and_accept_attachment3_by_opiekun_uczelniany(dokument_id):
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    if current_user.rola.nazwa != 'opiekun_uczelniany':
        return False

    doc_row = db.session.execute(
        text("SELECT praktyka_id FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row:
        return False

    praktyka_id = doc_row[0]
    
    # Sprawdzenie czy ZAL_7 jest completed
    zal7_row = db.session.execute(
        text(
            "SELECT d.status FROM dokument d "
            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_7' "
            "ORDER BY d.id DESC LIMIT 1"
        ),
        {'praktyka_id': praktyka_id}
    ).fetchone()
    if not zal7_row or zal7_row[0] != 'completed':
        return False

    try:
        # Wpisz bieżącą datę w pole 'data_sprawozdania'
        data_dzisiaj = datetime.now().date().isoformat()
        db.session.execute(
            text(
                "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                "VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
            ),
            {
                'doc_id': dokument_id,
                'klucz': 'data_sprawozdania',
                'wartosc': data_dzisiaj,
                'wypelniajacy': current_user.id,
            }
        )
        
        # Zmień status dokumentu na 'completed'
        db.session.execute(
            text(
                "UPDATE dokument SET status = 'completed', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        
        # Zmień aktualny_etap praktyki na 8
        db.session.execute(
            text(
                "UPDATE praktyka SET aktualny_etap = 8 WHERE id = :praktyka_id"
            ),
            {'praktyka_id': praktyka_id}
        )
        
        # Zarejestruj akceptację
        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano) "
                    "VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu i akceptacji załącznika 3 przez opiekuna uczelnianego: {e}')
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
    dokument = None
    dokument_data = {}
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')

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

        zal1_document_row = db.session.execute(text(
            "SELECT d.id FROM dokument d "
            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_1' "
            "ORDER BY d.id DESC LIMIT 1"
        ), {'praktyka_id': praktyka_id}).fetchone()
        if zal1_document_row:
            zal1_dokument_id = zal1_document_row[0]
            data_rows = db.session.execute(text(
                "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"
            ), {'dokument_id': zal1_dokument_id}).fetchall()
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

    if dokument_id:
        document_row = db.session.execute(
            text("SELECT praktyka_id, status FROM dokument WHERE id = :dokument_id"),
            {'dokument_id': dokument_id}
        ).fetchone()
        if document_row:
            selected_practice_id = document_row[0]
            dokument = {
                'id': dokument_id,
                'status': document_row[1],
            }
            data_rows = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"),
                {'dokument_id': dokument_id}
            ).fetchall()
            dokument_data = {key: value or '' for key, value in data_rows}

    if action_query and dokument_id:
        if action_query == 'sign' and sign_attachment3_by_dyrektor(dokument_id):
            flash('Załącznik 3 został podpisany przez dyrektora.', 'success')
            return redirect(url_for('dashboard.index'))
        if action_query == 'sign_accept' and sign_and_accept_attachment3_by_opiekun_firmowy(dokument_id):
            flash('Załącznik 3 został podpisany i zaakceptowany.', 'success')
            return redirect(url_for('dashboard.index'))
        if action_query == 'sign_accept' and sign_and_accept_attachment3_by_opiekun_uczelniany(dokument_id):
            flash('Załącznik 3 został podpisany i zaakceptowany przez opiekuna uczelnianego.', 'success')
            return redirect(url_for('dashboard.index'))
        if action_query in ('confirm_registration', 'confirm_training') and sign_attachment3_by_opiekun_firmowy(dokument_id, action_query):
            flash('Potwierdzenie zostało zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

    if selected_practice_id:
        existing_doc = db.session.execute(
            text(
                "SELECT d.id, d.status FROM dokument d "
                "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_3' "
                "ORDER BY d.id DESC LIMIT 1"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if existing_doc and not dokument:
            dokument_id = existing_doc[0]
            dokument = {
                'id': existing_doc[0],
                'status': existing_doc[1],
            }
            data_rows = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"),
                {'dokument_id': dokument_id}
            ).fetchall()
            dokument_data = {key: value for key, value in data_rows}
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

    zalacznik_6_completed = False
    firmowy_can_edit = False
    uczelniany_can_edit = False
    if dokument:
        zal6_row = db.session.execute(
            text(
                "SELECT d6.status FROM dokument d3 "
                "JOIN praktyka p ON d3.praktyka_id = p.id "
                "JOIN dokument d6 ON d6.praktyka_id = p.id "
                "JOIN typ_dokumentu t6 ON d6.typ_dokumentu_id = t6.id "
                "WHERE d3.id = :doc_id AND t6.kod = 'ZAL_6' "
                "ORDER BY d6.id DESC LIMIT 1"
            ),
            {'doc_id': dokument['id']}
        ).fetchone()
        zalacznik_6_completed = bool(zal6_row and zal6_row[0] == 'completed')
        firmowy_can_edit = role == 'opiekun_firmowy' and zalacznik_6_completed and dokument['status'] == 'doc3_step2'
        
        # Opiekun uczelniany może edytować pole "Ocena sprawozdania z praktyki" gdy ZAL_7 jest completed
        zal7_row = db.session.execute(
            text(
                "SELECT d7.status FROM dokument d3 "
                "JOIN praktyka p ON d3.praktyka_id = p.id "
                "JOIN dokument d7 ON d7.praktyka_id = p.id "
                "JOIN typ_dokumentu t7 ON d7.typ_dokumentu_id = t7.id "
                "WHERE d3.id = :doc_id AND t7.kod = 'ZAL_7' "
                "ORDER BY d7.id DESC LIMIT 1"
            ),
            {'doc_id': dokument['id']}
        ).fetchone()
        zal7_completed = bool(zal7_row and zal7_row[0] == 'completed')
        uczelniany_can_edit = role == 'opiekun_uczelniany' and zal7_completed

    director_full_name = ''
    director_user = Uzytkownik.query.join(Rola).filter(Rola.nazwa == 'dyrektor').first()
    if director_user:
        director_full_name = f"{director_user.imie or ''} {director_user.nazwisko or ''}".strip()

    if request.method == 'POST':
        if current_user.rola.nazwa == 'dziekanat':
            if dokument:
                flash('Załącznik 3 już istnieje i nie można go ponownie utworzyć.', 'danger')
                return redirect(url_for('dashboard.index'))

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
                flash('Załącznik 3 został utworzony.', 'success')
                return redirect(url_for('dashboard.index'))
            flash('Wystąpił problem podczas zapisu formularza.', 'danger')
        elif current_user.rola.nazwa == 'opiekun_firmowy' and dokument and firmowy_can_edit:
            saved = update_attachment3_by_opiekun_firmowy(dokument_id, request.form)
            if saved:
                flash('Dane załącznika 3 zostały zapisane.', 'success')
                return redirect(url_for('dashboard.index'))
            flash('Wystąpił problem podczas zapisu formularza.', 'danger')
        elif current_user.rola.nazwa == 'opiekun_uczelniany' and dokument and uczelniany_can_edit:
            saved = update_attachment3_by_opiekun_uczelniany(dokument_id, request.form)
            if saved:
                flash('Dane załącznika 3 zostały zapisane.', 'success')
                return redirect(url_for('dashboard.index'))
            flash('Wystąpił problem podczas zapisu formularza.', 'danger')
        else:
            flash('Nie masz uprawnień do edycji tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

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
        dokument=dokument,
        dokument_data=dokument_data,
        firmowy_can_edit=firmowy_can_edit,
        uczelniany_can_edit=uczelniany_can_edit,
        zalacznik_6_completed=zalacznik_6_completed,
        director_full_name=director_full_name,
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

        existing = db.session.execute(
            text("SELECT id, status FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id ORDER BY id DESC LIMIT 1"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()

        if not existing:
            if current_user.rola.nazwa != 'dziekanat':
                current_app.logger.error('Tylko dziekanat może tworzyć załącznik 4.')
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
                    'status': 'in_progress',
                    'ostatni_edytor': current_user.id,
                }
            )
            db.session.commit()

            dokument_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            dokument_id = dokument_row[0] if dokument_row else None
            if not dokument_id:
                current_app.logger.error('Nie udało się pobrać dokumentu po utworzeniu załącznika 4.')
                return False

            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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

        dokument_id = existing[0]
        dokument_status = existing[1]

        if current_user.rola.nazwa == 'opiekun_firmowy' and dokument_status in ('in_progress', 'rejected'):
            effect_statuses = form_data.getlist('efekt_uzyskany[]')
            effect_rows = db.session.execute(text("SELECT id FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()
            for idx, row in enumerate(effect_rows):
                efekt_id = row[0]
                status = 'achieved' if idx < len(effect_statuses) and str(effect_statuses[idx]) == '1' else 'not_achieved'
                db.session.execute(
                    text(
                        "INSERT OR REPLACE INTO efekt_uczenia_dokumentu (dokument_id, efekt_id, status, ocenione_przez) "
                        "VALUES (:doc_id, :efekt_id, :status, :ocenione_przez)"
                    ),
                    {
                        'doc_id': dokument_id,
                        'efekt_id': efekt_id,
                        'status': status,
                        'ocenione_przez': current_user.id,
                    }
                )

            if dokument_status == 'rejected':
                db.session.execute(text("UPDATE dokument SET status = 'in_progress' WHERE id = :doc_id"), {'doc_id': dokument_id})
            db.session.execute(text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"), {'doc_id': dokument_id, 'ostatni': current_user.id})
            db.session.commit()
            return True

        if current_user.rola.nazwa == 'opiekun_uczelniany' and dokument_status == 'awaiting_approval':
            dane_map = {
                'opinia_opiekuna_uczelnianego': form_data.get('opinia_opiekuna_uczelnianego', ''),
                'data_opinii': form_data.get('data_opinii', ''),
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
            db.session.execute(text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"), {'doc_id': dokument_id, 'ostatni': current_user.id})
            db.session.commit()
            return True

        current_app.logger.error('Brak uprawnień do zapisu załącznika 4 lub dokument ma niezgodny status.')
        return False
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 4: {e}')
        return False


def sign_and_accept_attachment4_by_opiekun_firmowy(dokument_id):
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    if current_user.rola.nazwa != 'opiekun_firmowy':
        return False

    doc_row = db.session.execute(
        text("SELECT status FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row or doc_row[0] not in ('in_progress', 'rejected'):
        return False

    try:
        if doc_row[0] == 'rejected':
            db.session.execute(
                text("UPDATE dokument SET status = 'in_progress' WHERE id = :doc_id"),
                {'doc_id': dokument_id}
            )

        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano) "
                    "VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano) "
                    "VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        db.session.execute(
            text("UPDATE dokument SET status = 'awaiting_approval', ostatni_edytor = :ostatni WHERE id = :doc_id"),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 1, moze_podpisac = 1, moze_akceptowac = 1 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_uczelniany')"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu i akceptacji załącznika 4 przez opiekuna firmowego: {e}')
        return False


def sign_and_accept_attachment4_by_opiekun_uczelniany(dokument_id):
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    if current_user.rola.nazwa != 'opiekun_uczelniany':
        return False

    doc_row = db.session.execute(
        text("SELECT praktyka_id, status FROM dokument WHERE id = :doc_id"),
        {'doc_id': dokument_id}
    ).fetchone()
    if not doc_row or doc_row[1] != 'awaiting_approval':
        return False

    praktyka_id = doc_row[0]

    try:
        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano) "
                    "VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )
        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano) "
                    "VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        db.session.execute(
            text("UPDATE dokument SET status = 'completed', ostatni_edytor = :ostatni WHERE id = :doc_id"),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 "
                "WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_uczelniany')"
            ),
            {'doc_id': dokument_id}
        )
        db.session.execute(
            text("UPDATE praktyka SET aktualny_etap = 7 WHERE id = :praktyka_id"),
            {'praktyka_id': praktyka_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu i akceptacji załącznika 4 przez opiekuna uczelnianego: {e}')
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
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action', type=str)
    selected_student = None
    dokument = None
    dokument_data = {}
    efekty = []
    can_edit_firmowy = False
    can_edit_uczelniany = False
    can_sign_firmowy = False
    can_sign_uczelniany = False
    can_create = False

    if dokument_id and not selected_practice_id:
        practice_row = db.session.execute(
            text("SELECT praktyka_id FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()
        if practice_row:
            selected_practice_id = practice_row[0]

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
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc, p.liczba_godzin, "
                "of.imie AS firm_imie, of.nazwisko AS firm_nazwisko, "
                "ou.imie AS ucz_imie, ou.nazwisko AS ucz_nazwisko "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "LEFT JOIN uzytkownik of ON p.opiekun_firmowy_id = of.id "
                "LEFT JOIN uzytkownik ou ON p.opiekun_uczelniany_id = ou.id "
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
                'liczba_godzin': student_row[5] if len(student_row) > 5 and student_row[5] is not None else '',
                'opiekun_firmowy': f"{student_row[6] or ''} {student_row[7] or ''}".strip(),
                'opiekun_uczelniany': f"{student_row[8] or ''} {student_row[9] or ''}".strip(),
            }

        doc_row = db.session.execute(
            text(
                "SELECT d.id, d.status FROM dokument d "
                "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
                "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_4' "
                "ORDER BY d.id DESC LIMIT 1"
            ),
            {'praktyka_id': selected_practice_id}
        ).fetchone()
        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1]}
            dokument_id = dokument['id']
            dane_rows = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane_rows}
            podpis_firmowy_row = db.session.execute(
                text(
                    "SELECT dp.podpisano FROM dokument_podpis dp "
                    "JOIN uzytkownik u ON dp.podpisujacy_id = u.id "
                    "JOIN role r ON u.rola_id = r.id "
                    "WHERE dp.dokument_id = :doc_id AND r.nazwa = 'opiekun_firmowy' AND dp.czy_podpisany = 1 "
                    "ORDER BY dp.id DESC LIMIT 1"
                ),
                {'doc_id': dokument_id}
            ).fetchone()
            podpis_firmowy_date = podpis_firmowy_row[0] if podpis_firmowy_row else ''
            if isinstance(podpis_firmowy_date, datetime):
                podpis_firmowy_date = podpis_firmowy_date.isoformat()
            dokument_data['opiekun_firmowy_podpisano'] = podpis_firmowy_date or ''
            efekty_rows = db.session.execute(
                text(
                    "SELECT e.id, e.numer, e.opis, COALESCE(ed.status, 'not_achieved') "
                    "FROM efekt_uczenia e "
                    "LEFT JOIN efekt_uczenia_dokumentu ed ON e.id = ed.efekt_id AND ed.dokument_id = :doc_id "
                    "ORDER BY e.numer LIMIT 13"
                ),
                {'doc_id': dokument_id}
            ).fetchall()
        else:
            efekty_rows = db.session.execute(text("SELECT id, numer, opis FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()
    else:
        efekty_rows = db.session.execute(text("SELECT id, numer, opis FROM efekt_uczenia ORDER BY numer LIMIT 13")).fetchall()

    efekty = [
        {'id': r[0], 'numer': r[1], 'opis': r[2], 'status': r[3] if len(r) > 3 else 'not_achieved'}
        for r in efekty_rows
    ]

    document_permission = None
    if dokument and dokument_id:
        document_permission = db.session.execute(
            text(
                "SELECT moze_edytowac, moze_podpisac, moze_akceptowac "
                "FROM udostepniony_dokument "
                "WHERE dokument_id = :doc_id AND adresat = :user_id"
            ),
            {'doc_id': dokument_id, 'user_id': current_user.id}
        ).fetchone()

    has_edit_permission = document_permission and document_permission[0] == 1
    has_sign_permission = document_permission and document_permission[2] == 1

    can_create = role == 'dziekanat' and dokument is None and selected_practice_id
    can_edit_firmowy = (
        role == 'opiekun_firmowy' and dokument and dokument['status'] in ('in_progress', 'rejected') and has_edit_permission
    )
    can_edit_uczelniany = (
        role == 'opiekun_uczelniany' and dokument and dokument['status'] == 'awaiting_approval' and has_edit_permission
    )
    can_sign_firmowy = (
        role == 'opiekun_firmowy' and dokument and dokument['status'] in ('in_progress', 'rejected') and has_sign_permission
    )
    can_sign_uczelniany = (
        role == 'opiekun_uczelniany' and dokument and dokument['status'] == 'awaiting_approval' and has_sign_permission
    )

    if action_query == 'sign_accept' and dokument_id:
        if can_sign_firmowy and sign_and_accept_attachment4_by_opiekun_firmowy(dokument_id):
            flash('Załącznik 4 został podpisany i zaakceptowany przez opiekuna firmowego.', 'success')
            return redirect(url_for('dashboard.index'))
        if can_sign_uczelniany and sign_and_accept_attachment4_by_opiekun_uczelniany(dokument_id):
            flash('Załącznik 4 został podpisany i zaakceptowany przez opiekuna uczelnianego.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Nie można podpisać i zaakceptować załącznika 4.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_firmowy', 'opiekun_uczelniany']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = request.form

        if role == 'dziekanat' and not dokument:
            saved = save_attachment4_data(form_data)
        elif can_edit_firmowy:
            saved = save_attachment4_data(form_data)
        elif can_edit_uczelniany:
            saved = save_attachment4_data(form_data)
        else:
            flash('Nie masz uprawnień do edycji tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if saved:
            flash('Dane załącznika 4 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': f"{selected_student['imie']} {selected_student['nazwisko']}" if selected_student else '',
        'specjalnosc': selected_student['specjalnosc'] if selected_student else '',
        'ilosc_godzin_praktyk': selected_student['liczba_godzin'] if selected_student else '',
        'nr_indeksu': selected_student['numer_albumu'] if selected_student else '',
        'opinia_opiekuna_uczelnianego': dokument_data.get('opinia_opiekuna_uczelnianego', ''),
        'data_opinii': dokument_data.get('data_opinii', date.today().isoformat()),
        'opiekun_firmowy_podpisano': dokument_data.get('opiekun_firmowy_podpisano', ''),
    }

    return render_template(
        'forms/zalacznik_4.html',
        role=role,
        studenci=studenci,
        selected_student=selected_student,
        dokument=dokument,
        dokument_data=dokument_data,
        efekty=efekty,
        can_create=can_create,
        can_edit_firmowy=can_edit_firmowy,
        can_edit_uczelniany=can_edit_uczelniany,
        can_sign_firmowy=can_sign_firmowy,
        can_sign_uczelniany=can_sign_uczelniany,
        **prefilled
    )


def save_attachment4a_data(form_data, role='dziekanat', dokument_id=None, current_status=None):
    from app import db
    from sqlalchemy import text

    try:
        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None

        if not student_id:
            current_app.logger.error('Brak wybranego studenta przy zapisie załącznika 4a.')
            return False

        praktyka_row = db.session.execute(
            text(
                "SELECT id, opiekun_uczelniany_id FROM praktyka WHERE student_id = :student_id AND sciezka = 'alternative' ORDER BY id DESC LIMIT 1"
            ),
            {'student_id': student_id}
        ).fetchone()

        if not praktyka_row:
            current_app.logger.error('Nie znaleziono praktyki dla studenta %s', student_id)
            return False

        praktyka_id = praktyka_row[0]
        opiekun_uczelniany_id = praktyka_row[1] if len(praktyka_row) > 1 else None

        typ_row = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4A' LIMIT 1")
        ).fetchone()

        if not typ_row:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_4A')
            return False

        typ_id = typ_row[0]

        if role == 'dziekanat':
            if dokument_id:
                return False
            status = 'in_progress'
        elif role == 'czlonek_komisji':
            if not dokument_id:
                return False
            dokument_row = db.session.execute(
                text("SELECT id, status FROM dokument WHERE id = :dokument_id AND typ_dokumentu_id = :typ_id"),
                {'dokument_id': dokument_id, 'typ_id': typ_id}
            ).fetchone()
            if not dokument_row or dokument_row[1] != 'in_progress':
                return False
            status = 'awaiting_approval'
        else:
            return False

        db.session.execute(
            text(
                "UPDATE praktyka SET liczba_godzin = :liczba_godzin, zaktualizowano = datetime('now') WHERE id = :praktyka_id"
            ),
            {
                'liczba_godzin': int(form_data.get('ilosc_godzin_praktyk') or 0),
                'praktyka_id': praktyka_id
            }
        )

        if dokument_id:
            db.session.execute(
                text(
                    "UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor, zaktualizowano = datetime('now') WHERE id = :dokument_id"
                ),
                {
                    'status': status,
                    'ostatni_edytor': current_user.id,
                    'dokument_id': dokument_id
                }
            )
        else:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor) "
                    "VALUES (:praktyka_id, :typ_id, :uzytkownik_id, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'uzytkownik_id': current_user.id,
                    'status': status,
                    'ostatni_edytor': current_user.id
                }
            )
            dokument_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()

        if not dokument_id:
            return False

        efekt_rows = db.session.execute(
            text("SELECT id FROM efekt_uczenia ORDER BY numer LIMIT 13")
        ).fetchall()

        status_map = {'0': 'not_achieved', '1': 'partial', '2': 'achieved'}
        efekty_values = form_data.get('efekt_uzyskany', [])

        for idx, row in enumerate(efekt_rows):
            efekt_id = row[0]
            value = efekty_values[idx] if idx < len(efekty_values) else '0'
            efekt_status = status_map.get(value, 'not_achieved')

            istnieje = db.session.execute(
                text("SELECT id FROM efekt_uczenia_dokumentu WHERE dokument_id = :doc_id AND efekt_id = :efekt_id"),
                {'doc_id': dokument_id, 'efekt_id': efekt_id}
            ).fetchone()

            if istnieje:
                db.session.execute(
                    text("UPDATE efekt_uczenia_dokumentu SET status = :status, ocenione_przez = :ocenione_przez WHERE id = :id"),
                    {
                        'status': efekt_status,
                        'ocenione_przez': current_user.id,
                        'id': istnieje[0]
                    }
                )
            else:
                db.session.execute(
                    text(
                        "INSERT INTO efekt_uczenia_dokumentu (dokument_id, efekt_id, status, ocenione_przez) "
                        "VALUES (:doc_id, :efekt_id, :status, :ocenione_przez)"
                    ),
                    {
                        'doc_id': dokument_id,
                        'efekt_id': efekt_id,
                        'status': efekt_status,
                        'ocenione_przez': current_user.id
                    }
                )

        istnieje = db.session.execute(
            text("SELECT id FROM dane_dokumentu WHERE dokument_id = :doc_id AND klucz = 'data_wyniku_komisji'"),
            {'doc_id': dokument_id}
        ).fetchone()

        if istnieje:
            db.session.execute(
                text("UPDATE dane_dokumentu SET wartosc = :wartosc, wypelnione_przez = :user_id WHERE id = :id"),
                {
                    'wartosc': form_data.get('data_wyniku_komisji'),
                    'user_id': current_user.id,
                    'id': istnieje[0]
                }
            )
        else:
            db.session.execute(
                text(
                    "INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                    "VALUES (:doc_id, 'data_wyniku_komisji', :wartosc, :user_id)"
                ),
                {
                    'doc_id': dokument_id,
                    'wartosc': form_data.get('data_wyniku_komisji'),
                    'user_id': current_user.id
                }
            )

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','dyrektor','czlonek_komisji')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if role == 'dziekanat':
            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )

        elif role == 'czlonek_komisji':
            if role_ids.get('czlonek_komisji'):
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 1, moze_akceptowac = 1 "
                        "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )

            if role_ids.get('student'):
                db.session.execute(
                    text("UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :dokument_id AND rola_id = :rola_id"),
                    {'dokument_id': dokument_id, 'rola_id': role_ids['student']}
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text("UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :dokument_id AND rola_id = :rola_id"),
                    {'dokument_id': dokument_id, 'rola_id': role_ids['dziekanat']}
                )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        return False


def sign_and_accept_attachment4a_by_commission(dokument_id):
    from app import db
    from sqlalchemy import text

    try:
        typ_id = db.session.execute(text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4A' LIMIT 1")).scalar()
        dokument_row = db.session.execute(
            text("SELECT id, status, praktyka_id FROM dokument WHERE id = :dokument_id AND typ_dokumentu_id = :typ_id"),
            {'dokument_id': dokument_id, 'typ_id': typ_id}
        ).fetchone()

        if not dokument_row or dokument_row[1] != 'awaiting_approval':
            return False

        praktyka_id = dokument_row[2]

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'completed', ostatni_edytor = :user_id, zaktualizowano = datetime('now') WHERE id = :dokument_id"
            ),
            {'user_id': current_user.id, 'dokument_id': dokument_id}
        )

        update_practice_stage_from_typ(praktyka_id, typ_id)

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','czlonek_komisji','dziekanat','dyrektor','opiekun_uczelniany')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        db.session.execute(
            text("UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 WHERE dokument_id = :dokument_id"),
            {'dokument_id': dokument_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania i akceptacji załącznika 4a przez komisję: {e}')
        return False


@bp.route('/formularz/zalacznik-4a', methods=['GET', 'POST'])
@login_required
def zalacznik_4a():
    """Formularz załącznika 4a - Potwierdzenie uzyskania efektów uczenia się."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')
    selected_practice_id = request.args.get('selected_praktyka_id', type=int)

    dokument = None
    dokument_data = {}
    selected_student = None
    can_create = False
    can_edit = False
    can_sign_accept = False

    if dokument_id:
        typ_id = db.session.execute(text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4A' LIMIT 1")).scalar()
        dokument_row = db.session.execute(
            text(
                "SELECT d.id, d.status, d.praktyka_id, p.student_id "
                "FROM dokument d JOIN praktyka p ON p.id = d.praktyka_id "
                "WHERE d.id = :dokument_id AND d.typ_dokumentu_id = :typ_id"
            ),
            {'dokument_id': dokument_id, 'typ_id': typ_id}
        ).fetchone()
        if dokument_row:
            dokument = {'id': dokument_row[0], 'status': dokument_row[1], 'praktyka_id': dokument_row[2], 'student_id': dokument_row[3]}

    if action_query and dokument:
        if action_query == 'sign_accept':
            if role != 'czlonek_komisji':
                flash('Tylko członek komisji może podpisać i zaakceptować ten dokument.', 'danger')
            elif dokument['status'] != 'awaiting_approval':
                flash('Dokument nie jest w stanie oczekującym na podpis i akceptację.', 'danger')
            elif sign_and_accept_attachment4a_by_commission(dokument['id']):
                flash('Dokument został podpisany i zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać i zaakceptować dokumentu.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        if role not in ['dziekanat', 'czlonek_komisji']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        status = dokument['status'] if dokument else None
        if role == 'dziekanat':
            can_create = dokument is None
        elif role == 'czlonek_komisji':
            can_edit = dokument is not None and status == 'in_progress'

        if not (can_create or can_edit):
            flash('Nie masz uprawnień do zapisania tego dokumentu w tym stanie.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'student_id': request.form.get('student_id'),
            'nr_indeksu': request.form.get('nr_indeksu'),
            'ilosc_godzin_praktyk': request.form.get('ilosc_godzin_praktyk'),
            'efekt_uzyskany': request.form.getlist('efekt_uzyskany[]'),
            'data_wyniku_komisji': request.form.get('data_wyniku_komisji'),
        }

        saved = save_attachment4a_data(form_data, role=role, dokument_id=dokument['id'] if dokument else None, current_status=status)
        if saved:
            flash('Dane załącznika 4a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')
        return redirect(url_for('dashboard.index'))

    if dokument:
        student_row = db.session.execute(
            text("SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc FROM uzytkownik u WHERE u.id = :student_id"),
            {'student_id': dokument['student_id']}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': dokument['student_id'],
                'imie': student_row[0] or '',
                'nazwisko': student_row[1] or '',
                'numer_albumu': student_row[2] or '',
                'specjalnosc': student_row[3] or '',
            }

        dane_rows = db.session.execute(
            text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"),
            {'dokument_id': dokument['id']}
        ).fetchall()
        dokument_data = {row[0]: row[1] for row in dane_rows}

        efekty_doc_rows = db.session.execute(
            text(
                "SELECT e.id, e.numer, e.opis, eud.status FROM efekt_uczenia e "
                "LEFT JOIN efekt_uczenia_dokumentu eud ON eud.efekt_id = e.id AND eud.dokument_id = :dokument_id "
                "ORDER BY e.numer LIMIT 13"
            ),
            {'dokument_id': dokument['id']}
        ).fetchall()
    else:
        if selected_practice_id:
            student_row = db.session.execute(
                text(
                    "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc "
                    "FROM praktyka p JOIN uzytkownik u ON p.student_id = u.id WHERE p.id = :praktyka_id"
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

        efekty_doc_rows = db.session.execute(
            text("SELECT id, numer, opis, NULL FROM efekt_uczenia ORDER BY numer LIMIT 13")
        ).fetchall()

    efekty = [
        {'id': r[0], 'numer': r[1], 'opis': r[2] if len(r) > 2 else '', 'status': r[3] if len(r) > 3 else None}
        for r in efekty_doc_rows
    ]

    can_create = (role == 'dziekanat' and not dokument)
    can_edit = (role == 'czlonek_komisji' and dokument and dokument['status'] == 'in_progress')
    can_sign_accept = (role == 'czlonek_komisji' and dokument and dokument['status'] == 'awaiting_approval')

    prefilled = {
        'dokument_id': dokument['id'] if dokument else '',
        'imie_nazwisko_studenta': f"{selected_student['imie']} {selected_student['nazwisko']}" if selected_student else '',
        'specjalnosc': selected_student['specjalnosc'] if selected_student else '',
        'student_id': selected_student['id'] if selected_student else '',
        'ilosc_godzin_praktyk': dokument_data.get('ilosc_godzin_praktyk', ''),
        'nr_indeksu': selected_student['numer_albumu'] if selected_student else '',
        'data_wyniku_komisji': dokument_data.get('data_wyniku_komisji', date.today().isoformat()),
        'can_create': can_create,
        'can_edit': can_edit,
        'can_sign_accept': can_sign_accept,
        'is_completed': dokument and dokument['status'] == 'completed',
    }

    return render_template(
        'forms/zalacznik_4a.html',
        role=role,
        selected_student=selected_student,
        efekty=efekty,
        **prefilled
    )


def save_attachment4b_data(form_data, role='student', dokument_id=None, current_status=None):
    from app import db
    from sqlalchemy import text

    try:
        opiekun_uczelniany_id = int(form_data.get('opiekun_uczelniany_id')) if form_data.get('opiekun_uczelniany_id') else None

        typ_dokumentu_id = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B' LIMIT 1")
        ).scalar()
        if not typ_dokumentu_id:
            current_app.logger.error('Nie znaleziono typu dokumentu ZAL_4B.')
            return False

        dokument_row = None
        praktyka_id = None
        if dokument_id:
            dokument_row = db.session.execute(
                text(
                    "SELECT id, status, praktyka_id FROM dokument "
                    "WHERE id = :dokument_id AND typ_dokumentu_id = :typ_dokumentu_id"
                ),
                {
                    'dokument_id': dokument_id,
                    'typ_dokumentu_id': typ_dokumentu_id,
                }
            ).fetchone()
            if not dokument_row:
                return False
            praktyka_id = dokument_row[2]

        if role == 'student':
            if dokument_id and dokument_row[1] not in ('rejected', 'in_progress'):
                return False
            status = 'in_progress'
        elif role == 'czlonek_komisji':
            if not dokument_id or dokument_row[1] != 'in_progress':
                return False
            status = 'awaiting_signature'
        elif role == 'dyrektor':
            if not dokument_id or dokument_row[1] != 'awaiting_approval':
                return False
            status = 'awaiting_approval'
        else:
            return False

        if not praktyka_id:
            student_id = current_user.id
            praktyka = db.session.execute(
                text(
                    "SELECT id FROM praktyka WHERE student_id = :student_id AND sciezka = 'alternative' ORDER BY id DESC LIMIT 1"
                ),
                {'student_id': student_id}
            ).fetchone()

            if praktyka:
                praktyka_id = praktyka[0]
                db.session.execute(
                    text(
                        "UPDATE praktyka SET status = 'active', zaktualizowano = datetime('now') WHERE id = :id"
                    ),
                    {'id': praktyka_id}
                )
            else:
                rok_akademicki = f"{date.today().year - 1}/{date.today().year}"
                db.session.execute(
                    text(
                        "INSERT INTO praktyka (student_id, firma_id, opiekun_firmowy_id, opiekun_uczelniany_id, sciezka, status, "
                        "liczba_dni_roboczych, liczba_godzin, rok_akademicki) "
                        "VALUES (:student_id, NULL, NULL, :opiekun_uczelniany_id, 'alternative', 'active', NULL, NULL, :rok_akademicki)"
                    ),
                    {
                        'student_id': current_user.id,
                        'opiekun_uczelniany_id': opiekun_uczelniany_id,
                        'rok_akademicki': rok_akademicki,
                    }
                )
                praktyka_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()

        if opiekun_uczelniany_id and praktyka_id:
            db.session.execute(
                text("UPDATE praktyka SET opiekun_uczelniany_id = :opiekun_id WHERE id = :id"),
                {
                    'opiekun_id': opiekun_uczelniany_id,
                    'id': praktyka_id,
                }
            )

        if dokument_id:
            db.session.execute(
                text(
                    "UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor, zaktualizowano = datetime('now') "
                    "WHERE id = :dokument_id"
                ),
                {
                    'status': status,
                    'ostatni_edytor': current_user.id,
                    'dokument_id': dokument_id,
                }
            )
        else:
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor) "
                    "VALUES (:praktyka_id, :typ_dokumentu_id, :uzytkownik_id, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_dokumentu_id': typ_dokumentu_id,
                    'uzytkownik_id': current_user.id,
                    'status': status,
                    'ostatni_edytor': current_user.id,
                }
            )
            dokument_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()

        if not dokument_id:
            return False

        role_rows = db.session.execute(
            text(
                "SELECT nazwa, id FROM role WHERE nazwa IN ('student','czlonek_komisji','dyrektor','opiekun_uczelniany','dziekanat')"
            )
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if role == 'student':
            if role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': current_user.id,
                        'rola_id': role_ids['student'],
                    }
                )
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podgladac = 1, moze_podpisac = 0, moze_akceptowac = 0 "
                        "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['student'],
                    }
                )

            if role_ids.get('czlonek_komisji'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 1, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 1, moze_podpisac = 1, moze_akceptowac = 0 "
                        "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )

            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 "
                        "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
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
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            db.session.execute(
                text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :dokument_id"),
                {'dokument_id': dokument_id}
            )

        elif role == 'czlonek_komisji':
            if role_ids.get('czlonek_komisji'):
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podgladac = 1, moze_podpisac = 1, moze_akceptowac = 0 "
                        "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['czlonek_komisji'],
                    }
                )

            if role_ids.get('student'):
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['student'],
                    }
                )

            db.session.execute(
                text(
                    "INSERT OR IGNORE INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                    "VALUES (:dokument_id, :user_id, 0)"
                ),
                {
                    'dokument_id': dokument_id,
                    'user_id': current_user.id,
                }
            )
            db.session.execute(
                text(
                    "UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL "
                    "WHERE dokument_id = :dokument_id AND podpisujacy_id = :user_id"
                ),
                {
                    'dokument_id': dokument_id,
                    'user_id': current_user.id,
                }
            )

        elif role == 'dyrektor':
            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                        "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 1, 1)"
                    ),
                    {
                        'udostepniajacy': current_user.id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

        section_fields = {
            'student': {
                'uzasadnienie': form_data.get('uzasadnienie'),
                'data_uzasadnienia': form_data.get('data_uzasadnienia'),
            },
            'czlonek_komisji': {
                'opinia_komisji': form_data.get('opinia_komisji'),
                'data_opinii_komisji': form_data.get('data_opinii_komisji'),
            },
            'dyrektor': {
                'decyzja_dyrektora': form_data.get('decyzja_dyrektora'),
                'efekty_do_zaliczenia': form_data.get('efekty_do_zaliczenia'),
                'data_decyzji_dyrektora': form_data.get('data_decyzji_dyrektora'),
            },
        }

        fields = section_fields.get(role, {})
        for klucz, wartosc in fields.items():
            istnieje = db.session.execute(
                text(
                    "SELECT id FROM dane_dokumentu WHERE dokument_id = :dokument_id AND klucz = :klucz"
                ),
                {
                    'dokument_id': dokument_id,
                    'klucz': klucz,
                }
            ).fetchone()

            if istnieje:
                db.session.execute(
                    text(
                        "UPDATE dane_dokumentu SET wartosc = :wartosc WHERE id = :id"
                    ),
                    {
                        'wartosc': wartosc,
                        'id': istnieje[0],
                    }
                )
            else:
                db.session.execute(
                    text(
                        "INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                        "VALUES (:dokument_id, :klucz, :wartosc, :uzytkownik_id)"
                    ),
                    {
                        'dokument_id': dokument_id,
                        'klucz': klucz,
                        'wartosc': wartosc,
                        'uzytkownik_id': current_user.id,
                    }
                )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        return False


def get_attachment4b_document(dokument_id=None, practice_id=None, student_id=None):
    from app import db
    from sqlalchemy import text

    query = (
        "SELECT d.id, d.status, d.praktyka_id, p.student_id "
        "FROM dokument d "
        "JOIN praktyka p ON p.id = d.praktyka_id "
        "WHERE d.typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B')"
    )
    params = {}
    if dokument_id:
        query += " AND d.id = :dokument_id"
        params['dokument_id'] = dokument_id
    elif practice_id:
        query += " AND d.praktyka_id = :practice_id"
        params['practice_id'] = practice_id
    elif student_id:
        query += " AND d.praktyka_id = (SELECT id FROM praktyka WHERE student_id = :student_id AND sciezka = 'alternative' ORDER BY id DESC LIMIT 1)"
        params['student_id'] = student_id
    else:
        return None

    row = db.session.execute(text(query), params).fetchone()
    if not row:
        return None
    return {'id': row[0], 'status': row[1], 'praktyka_id': row[2], 'student_id': row[3]}


def sign_attachment4b_by_commission(dokument_id):
    from app import db
    from sqlalchemy import text

    try:
        typ_dokumentu_id = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B' LIMIT 1")
        ).scalar()
        row = db.session.execute(
            text(
                "SELECT id, status FROM dokument WHERE id = :dokument_id AND typ_dokumentu_id = :typ_dokumentu_id"
            ),
            {'dokument_id': dokument_id, 'typ_dokumentu_id': typ_dokumentu_id}
        ).fetchone()
        if not row or row[1] != 'awaiting_signature':
            return False

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'awaiting_approval', ostatni_edytor = :user_id, zaktualizowano = datetime('now') WHERE id = :dokument_id"
            ),
            {'user_id': current_user.id, 'dokument_id': dokument_id}
        )

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','czlonek_komisji','dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        if role_ids.get('czlonek_komisji'):
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['czlonek_komisji']}
            )

        if role_ids.get('student'):
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 0 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['student']}
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                    "VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 1, 1, 1)"
                ),
                {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'rola_id': role_ids['dyrektor'],
                }
            )
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 1, moze_podpisac = 1, moze_akceptowac = 1 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['dyrektor']}
            )

        db.session.execute(
            text(
                "INSERT OR IGNORE INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                "VALUES (:dokument_id, :user_id, 1)"
            ),
            {'dokument_id': dokument_id, 'user_id': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = datetime('now') "
                "WHERE dokument_id = :dokument_id AND podpisujacy_id = :user_id"
            ),
            {'dokument_id': dokument_id, 'user_id': current_user.id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania załącznika 4b przez członka komisji: {e}')
        return False


def accept_attachment4b_by_director(dokument_id):
    from app import db
    from sqlalchemy import text

    try:
        typ_dokumentu_id = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B' LIMIT 1")
        ).scalar()
        row = db.session.execute(
            text(
                "SELECT id, status, praktyka_id FROM dokument WHERE id = :dokument_id AND typ_dokumentu_id = :typ_dokumentu_id"
            ),
            {'dokument_id': dokument_id, 'typ_dokumentu_id': typ_dokumentu_id}
        ).fetchone()
        if not row or row[1] != 'awaiting_approval':
            return False

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'completed', ostatni_edytor = :user_id, zaktualizowano = datetime('now') "
                "WHERE id = :dokument_id"
            ),
            {'user_id': current_user.id, 'dokument_id': dokument_id}
        )

        db.session.execute(
            text(
                "INSERT OR IGNORE INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany) "
                "VALUES (:dokument_id, :user_id, 1)"
            ),
            {'dokument_id': dokument_id, 'user_id': current_user.id}
        )
        db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = datetime('now') "
                "WHERE dokument_id = :dokument_id AND akceptujacy_id = :user_id"
            ),
            {'dokument_id': dokument_id, 'user_id': current_user.id}
        )

        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 "
                "WHERE dokument_id = :dokument_id"
            ),
            {'dokument_id': dokument_id}
        )

        update_practice_stage_from_typ(row[2], typ_dokumentu_id)

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd akceptacji załącznika 4b przez dyrektora: {e}')
        return False


def reject_attachment4b_by_director(dokument_id):
    from app import db
    from sqlalchemy import text

    try:
        typ_dokumentu_id = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_4B' LIMIT 1")
        ).scalar()
        row = db.session.execute(
            text(
                "SELECT id, status FROM dokument WHERE id = :dokument_id AND typ_dokumentu_id = :typ_dokumentu_id"
            ),
            {'dokument_id': dokument_id, 'typ_dokumentu_id': typ_dokumentu_id}
        ).fetchone()
        if not row or row[1] != 'awaiting_approval':
            return False

        role_rows = db.session.execute(
            text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','czlonek_komisji','dyrektor')")
        ).fetchall()
        role_ids = {row[0]: row[1] for row in role_rows}

        db.session.execute(
            text(
                "UPDATE dokument SET status = 'rejected', ostatni_edytor = :user_id, zaktualizowano = datetime('now') "
                "WHERE id = :dokument_id"
            ),
            {'user_id': current_user.id, 'dokument_id': dokument_id}
        )

        if role_ids.get('student'):
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 1, moze_podgladac = 1 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['student']}
            )

        if role_ids.get('czlonek_komisji'):
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['czlonek_komisji']}
            )

        if role_ids.get('dyrektor'):
            db.session.execute(
                text(
                    "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0, moze_akceptowac = 0 "
                    "WHERE dokument_id = :dokument_id AND rola_id = :rola_id"
                ),
                {'dokument_id': dokument_id, 'rola_id': role_ids['dyrektor']}
            )

        db.session.execute(
            text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :dokument_id"),
            {'dokument_id': dokument_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia załącznika 4b przez dyrektora: {e}')
        return False


@bp.route('/formularz/zalacznik-4b', methods=['GET', 'POST'])
@login_required
def zalacznik_4b():
    """Formularz załącznika 4b - Wniosek o zaliczenie efektów uczenia się."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')
    selected_praktyka_id = request.args.get('selected_praktyka_id', type=int)

    dokument = None
    dokument_data = {}
    student_data = None
    selected_opiekun_uczelniany_id = ''
    can_save = False
    can_sign = False
    can_accept = False
    can_reject = False

    if dokument_id:
        dokument = get_attachment4b_document(dokument_id=dokument_id)
    elif role == 'student':
        dokument = get_attachment4b_document(student_id=current_user.id)
    elif selected_praktyka_id:
        dokument = get_attachment4b_document(practice_id=selected_praktyka_id)

    if action_query and dokument:
        if action_query == 'sign':
            if role != 'czlonek_komisji':
                flash('Tylko członek komisji może podpisać ten dokument.', 'danger')
            elif dokument['status'] != 'awaiting_signature':
                flash('Dokument nie jest w stanie oczekującym na podpis komisji.', 'danger')
            elif sign_attachment4b_by_commission(dokument['id']):
                flash('Dokument został podpisany przez komisję.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać dokumentu.', 'danger')

        elif action_query == 'accept':
            if role != 'dyrektor':
                flash('Tylko dyrektor instytutu może podpisać i zaakceptować ten dokument.', 'danger')
            elif dokument['status'] != 'awaiting_approval':
                flash('Dokument nie jest w stanie oczekującym na akceptację.', 'danger')
            elif accept_attachment4b_by_director(dokument['id']):
                flash('Dokument został podpisany i zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można zaakceptować dokumentu.', 'danger')

        elif action_query == 'reject':
            if role != 'dyrektor':
                flash('Tylko dyrektor instytutu może odrzucić ten dokument.', 'danger')
            elif dokument['status'] != 'awaiting_approval':
                flash('Dokument nie jest w stanie oczekującym na akceptację.', 'danger')
            elif reject_attachment4b_by_director(dokument['id']):
                flash('Dokument został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić dokumentu.', 'danger')

        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        if role not in ['student', 'czlonek_komisji', 'dyrektor']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        status = dokument['status'] if dokument else None
        if role == 'student':
            can_save = dokument is None or status == 'rejected'
        elif role == 'czlonek_komisji':
            can_save = dokument is not None and status == 'in_progress'
        elif role == 'dyrektor':
            can_save = dokument is not None and status == 'awaiting_approval'

        if not can_save:
            flash('Nie masz uprawnień do zapisania tego dokumentu w tym stanie.', 'danger')
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

        saved = save_attachment4b_data(form_data, role=role, dokument_id=dokument['id'] if dokument else None, current_status=status)
        if saved:
            flash('Dane załącznika 4b zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')
        return redirect(url_for('dashboard.index'))

    if dokument:
        student_data = db.session.execute(
            text(
                "SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc "
                "FROM uzytkownik u WHERE u.id = :student_id"
            ),
            {'student_id': dokument['student_id']}
        ).fetchone()

        dane_rows = db.session.execute(
            text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :dokument_id"),
            {'dokument_id': dokument['id']}
        ).fetchall()
        dokument_data = {row[0]: row[1] for row in dane_rows}

        praktyka_row = db.session.execute(
            text("SELECT opiekun_uczelniany_id FROM praktyka WHERE id = :praktyka_id"),
            {'praktyka_id': dokument['praktyka_id']}
        ).fetchone()
        selected_opiekun_uczelniany_id = praktyka_row[0] if praktyka_row else ''
    else:
        student_data = db.session.execute(
            text(
                "SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc "
                "FROM uzytkownik u WHERE u.id = :student_id"
            ),
            {'student_id': current_user.id}
        ).fetchone()

    can_save = False
    if dokument:
        if role == 'student' and dokument['status'] == 'rejected':
            can_save = True
        elif role == 'czlonek_komisji' and dokument['status'] == 'in_progress':
            can_save = True
        elif role == 'dyrektor' and dokument['status'] == 'awaiting_approval':
            can_save = True
    elif role == 'student':
        can_save = True

    can_sign = dokument and role == 'czlonek_komisji' and dokument['status'] == 'awaiting_signature'
    can_accept = dokument and role == 'dyrektor' and dokument['status'] == 'awaiting_approval'
    can_reject = can_accept

    imie_nazwisko_studenta = ''
    nr_indeksu = ''
    specjalnosc = ''
    if student_data:
        imie_nazwisko_studenta = f"{student_data[0]} {student_data[1]}"
        nr_indeksu = student_data[2] or ''
        specjalnosc = student_data[3] or ''

    prefilled = {
        'dokument_id': dokument['id'] if dokument else '',
        'status': dokument['status'] if dokument else '',
        'imie_nazwisko_studenta': imie_nazwisko_studenta,
        'specjalnosc': specjalnosc,
        'nr_indeksu': nr_indeksu,
        'data_zlozenia': date.today().isoformat(),
        'uzasadnienie': dokument_data.get('uzasadnienie', ''),
        'data_uzasadnienia': dokument_data.get('data_uzasadnienia', date.today().isoformat()),
        'opinia_komisji': dokument_data.get('opinia_komisji', ''),
        'data_opinii_komisji': dokument_data.get('data_opinii_komisji', date.today().isoformat()),
        'decyzja_dyrektora': dokument_data.get('decyzja_dyrektora', ''),
        'data_decyzji_dyrektora': dokument_data.get('data_decyzji_dyrektora', date.today().isoformat()),
        'efekty_do_zaliczenia': dokument_data.get('efekty_do_zaliczenia', ''),
        'selected_opiekun_uczelniany_id': selected_opiekun_uczelniany_id or '',
        'can_save': can_save,
        'can_sign': can_sign,
        'can_accept': can_accept,
        'can_reject': can_reject,
    }

    rola_opiekun_uczelniany = Rola.query.filter_by(nazwa='opiekun_uczelniany').first()
    opiekunowie_uczelni = (
        Uzytkownik.query
        .filter_by(rola_id=rola_opiekun_uczelniany.id, jest_aktywny=True)
        .order_by(Uzytkownik.nazwisko, Uzytkownik.imie)
        .all()
    ) if rola_opiekun_uczelniany else []

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
                'status': 'in_progress',
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

        db.session.execute(
            text(
                "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"
            ),
            {
                'doc_id': dokument_id,
                'klucz': 'wykaz_zalacznikow',
                'wartosc': wykaz,
                'wypelniajacy': current_user.id,
            }
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 6: {e}')
        return False


def sign_attachment6_row(dokument_id, numer_dnia):
    """Podpis pojedynczego wiersza w dzienniku praktyki przez opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        if current_user.rola.nazwa != 'opiekun_firmowy':
            return False

        # Check if the row exists and doesn't have comments
        row = db.session.execute(
            text("SELECT uwagi_opiekuna, jest_podpisany FROM wpis_dziennika WHERE dokument_id = :doc_id AND numer_dnia = :numer"),
            {'doc_id': dokument_id, 'numer': numer_dnia}
        ).fetchone()

        if not row:
            return False

        uwagi_opiekuna = row[0]
        jest_podpisany = row[1]

        # Cannot sign if already signed
        if jest_podpisany:
            return False

        # Cannot sign if there are comments
        if uwagi_opiekuna and uwagi_opiekuna.strip():
            return False

        # Sign the row
        db.session.execute(
            text(
                "UPDATE wpis_dziennika SET jest_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND numer_dnia = :numer"
            ),
            {
                'doc_id': dokument_id,
                'numer': numer_dnia,
                'podpisano': datetime.now().isoformat(),
            }
        )

        # Check if all rows are signed and document has >= 120 days
        total_rows = db.session.execute(
            text("SELECT COUNT(*) FROM wpis_dziennika WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        ).scalar()

        signed_rows = db.session.execute(
            text("SELECT COUNT(*) FROM wpis_dziennika WHERE dokument_id = :doc_id AND jest_podpisany = 1"),
            {'doc_id': dokument_id}
        ).scalar()

        # If all rows signed and >= 120 days, transition to awaiting_signature
        if total_rows >= 120 and signed_rows == total_rows:
            db.session.execute(
                text("UPDATE dokument SET status = 'awaiting_signature', ostatni_edytor = :ostatni WHERE id = :doc_id"),
                {'doc_id': dokument_id, 'ostatni': current_user.id}
            )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu wiersza załącznika 6: {e}')
        return False


def sign_all_attachment6_rows(dokument_id):
    """Podpisz wszystkie możliwe wiersze załącznika 6 dla opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        if current_user.rola.nazwa != 'opiekun_firmowy':
            return False

        rows = db.session.execute(
            text(
                "SELECT numer_dnia, uwagi_opiekuna, jest_podpisany "
                "FROM wpis_dziennika WHERE dokument_id = :doc_id ORDER BY numer_dnia"
            ),
            {'doc_id': dokument_id}
        ).fetchall()

        signed_any = False
        for numer_dnia, uwagi_opiekuna, jest_podpisany in rows:
            if jest_podpisany:
                continue
            if uwagi_opiekuna and uwagi_opiekuna.strip():
                continue
            db.session.execute(
                text(
                    "UPDATE wpis_dziennika SET jest_podpisany = 1, podpisano = :podpisano "
                    "WHERE dokument_id = :doc_id AND numer_dnia = :numer"
                ),
                {
                    'doc_id': dokument_id,
                    'numer': numer_dnia,
                    'podpisano': datetime.now().isoformat(),
                }
            )
            signed_any = True

        if not signed_any:
            return False

        total_rows = db.session.execute(
            text("SELECT COUNT(*) FROM wpis_dziennika WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        ).scalar()
        signed_rows = db.session.execute(
            text("SELECT COUNT(*) FROM wpis_dziennika WHERE dokument_id = :doc_id AND jest_podpisany = 1"),
            {'doc_id': dokument_id}
        ).scalar()

        if total_rows >= 120 and signed_rows == total_rows:
            db.session.execute(
                text("UPDATE dokument SET status = 'awaiting_signature', ostatni_edytor = :ostatni WHERE id = :doc_id"),
                {'doc_id': dokument_id, 'ostatni': current_user.id}
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu wszystkich wierszy załącznika 6: {e}')
        return False


def sign_and_accept_attachment6(dokument_id):
    """Podpisanie i zaakceptowanie całego załącznika 6 przez opiekuna firmowego."""
    from app import db
    from sqlalchemy import text

    try:
        if current_user.rola.nazwa != 'opiekun_firmowy':
            return False

        # Check document status - must be awaiting_signature
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[0] != 'awaiting_signature':
            return False

        # Add signature entry
        result = db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
                "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            }
        )

        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano)"
                    " VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
                ),
                {
                    'doc_id': dokument_id,
                    'podpisujacy_id': current_user.id,
                    'podpisano': datetime.now(),
                }
            )

        # Add acceptance entry
        result = db.session.execute(
            text(
                "UPDATE dokument_akceptacja SET czy_zaakceptowany = 1, zaakceptowano = :zaakceptowano "
                "WHERE dokument_id = :doc_id AND akceptujacy_id = :akceptujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now(),
            }
        )

        if result.rowcount == 0:
            db.session.execute(
                text(
                    "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano)"
                    " VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
                ),
                {
                    'doc_id': dokument_id,
                    'akceptujacy_id': current_user.id,
                    'zaakceptowano': datetime.now(),
                }
            )

        # Update document status to completed
        db.session.execute(
            text("UPDATE dokument SET status = 'completed', ostatni_edytor = :ostatni WHERE id = :doc_id"),
            {'doc_id': dokument_id, 'ostatni': current_user.id}
        )

        # Revoke editing and signing rights for all roles
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0 WHERE dokument_id = :doc_id"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisu i akceptacji załącznika 6: {e}')
        return False


@bp.route('/formularz/zalacznik-6', methods=['GET', 'POST'])
@login_required
def zalacznik_6():
    """Formularz załącznika 6 - Dziennik praktyki zawodowej."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa
    dokument_id = request.args.get('dokument_id', type=int)
    action = request.args.get('action', type=str)

    # Handle signing actions
    if action == 'sign_row':
        numer_dnia = request.args.get('numer_dnia', type=int)
        if dokument_id and numer_dnia:
            if sign_attachment6_row(dokument_id, numer_dnia):
                flash('Wiersz został podpisany.', 'success')
            else:
                flash('Nie udało się podpisać wiersza.', 'danger')
        return redirect(url_for('dashboard.zalacznik_6', dokument_id=dokument_id))

    if action == 'sign_all':
        if dokument_id:
            if sign_all_attachment6_rows(dokument_id):
                flash('Wszystkie możliwe dni zostały podpisane.', 'success')
            else:
                flash('Nie udało się podpisać żadnego dnia. Upewnij się, że dni nie są już podpisane i nie zawierają uwag.', 'danger')
        return redirect(url_for('dashboard.zalacznik_6', dokument_id=dokument_id))

    if action == 'sign_accept':
        if dokument_id:
            if sign_and_accept_attachment6(dokument_id):
                flash('Dokument został podpisany i zaakceptowany.', 'success')
            else:
                flash('Nie udało się podpisać dokumentu.', 'danger')
        return redirect(url_for('dashboard.zalacznik_6', dokument_id=dokument_id))

    # Load existing document if dokument_id provided
    dokument = None
    document_status = None
    wpisy = []
    allow_edit = False

    # Allow students to edit new documents (when dokument_id is None)
    if not dokument_id and role == 'student':
        allow_edit = True

    if dokument_id:
        doc_row = db.session.execute(
            text("SELECT status, praktyka_id FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if doc_row:
            document_status = doc_row[0]
            dokument_praktyka_id = doc_row[1] if len(doc_row) > 1 else None
            # Allow student to edit only if status is 'in_progress'
            # Allow opiekun_firmowy to edit notes in 'in_progress' status
            allow_edit = (role == 'student' and document_status == 'in_progress') or \
                         (role == 'opiekun_firmowy' and document_status == 'in_progress')

            # Load wpis_dziennika rows
            wpisy = db.session.execute(
                text(
                    "SELECT id, numer_dnia, data_wpisu, opis_prac, uwagi_opiekuna, jest_podpisany, podpisano "
                    "FROM wpis_dziennika WHERE dokument_id = :doc_id ORDER BY numer_dnia"
                ),
                {'doc_id': dokument_id}
            ).fetchall()

            # Load efekty for each row
            wpisy_with_efekty = []
            for wpis in wpisy:
                wpis_id, numer_dnia, data_wpisu, opis_prac, uwagi_opiekuna, jest_podpisany, podpisano = wpis
                efekty_rows = db.session.execute(
                    text("SELECT nr_efektu FROM wpis_efekt WHERE dokument_id = :doc_id AND numer_dnia = :numer ORDER BY nr_efektu"),
                    {'doc_id': dokument_id, 'numer': numer_dnia}
                ).fetchall()
                efekty = [str(e[0]) for e in efekty_rows]
                wpisy_with_efekty.append({
                    'id': wpis_id,
                    'numer_dnia': numer_dnia,
                    'data_wpisu': data_wpisu,
                    'opis_prac': opis_prac,
                    'uwagi_opiekuna': uwagi_opiekuna or '',
                    'jest_podpisany': jest_podpisany,
                    'podpisano': podpisano,
                    'efekty': efekty,
                })
            wpisy = wpisy_with_efekty

    # Handle POST (save/update rows)
    if request.method == 'POST':
        if role not in ['student', 'opiekun_firmowy']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        # If dokument_id is None and student is creating, create the document first
        if not dokument_id and role == 'student':
            try:
                student_id = current_user.id
                praktyka_row = db.session.execute(
                    text("SELECT id, opiekun_firmowy_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
                    {'student_id': student_id}
                ).fetchone()
                praktyka_id = praktyka_row[0] if praktyka_row else None
                opiekun_firmowy_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
                if not praktyka_id:
                    flash('Nie znaleziono praktyki dla studenta.', 'danger')
                    return redirect(url_for('dashboard.index'))

                typ_row = db.session.execute(
                    text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_6' LIMIT 1")
                ).fetchone()
                typ_id = typ_row[0] if typ_row else None
                if not typ_id:
                    flash('Nie znaleziono typu dokumentu ZAL_6.', 'danger')
                    return redirect(url_for('dashboard.index'))

                # Create document
                db.session.execute(
                    text(
                        "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                        " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                    ),
                    {
                        'praktyka_id': praktyka_id,
                        'typ_id': typ_id,
                        'utworzony_przez': current_user.id,
                        'status': 'in_progress',
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
                    flash('Nie udało się utworzyć dokumentu.', 'danger')
                    return redirect(url_for('dashboard.index'))

                # Create udostepniony_dokument entries
                role_rows = db.session.execute(
                    text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor')")
                ).fetchall()
                role_ids = {row[0]: row[1] for row in role_rows}

                if role_ids.get('student'):
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

                db.session.commit()
                allow_edit = True

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Błąd utworzenia dokumentu ZAL_6: {e}')
                flash('Błąd podczas tworzenia dokumentu.', 'danger')
                return redirect(url_for('dashboard.index'))

        if not allow_edit:
            flash('Nie masz uprawnień do edycji tego dokumentu.', 'danger')
            return redirect(url_for('dashboard.index'))

        # Collect form data
        form_data = {
            'dokument_id': dokument_id,
            'dzien': request.form.getlist('dzien[]'),
            'data': request.form.getlist('data[]'),
            'opis': request.form.getlist('opis[]'),
            'efekty_rows': request.form.getlist('efekty_rows[]'),
            'uwagi': request.form.getlist('uwagi[]'),
        }

        # Update existing or create new rows
        try:
            today = datetime.now().date().isoformat()
            for idx in range(len(form_data['dzien'])):
                try:
                    numer_dnia = int(form_data['dzien'][idx]) if form_data['dzien'][idx] and str(form_data['dzien'][idx]).strip() else (idx + 1)
                except Exception:
                    numer_dnia = idx + 1

                data_wpisu = form_data['data'][idx].strip() if idx < len(form_data['data']) and form_data['data'][idx] else today
                opis_prac = form_data['opis'][idx].strip() if idx < len(form_data['opis']) and form_data['opis'][idx] else ''
                uwagi_opiekuna = form_data['uwagi'][idx].strip() if idx < len(form_data['uwagi']) and form_data['uwagi'][idx] else ''

                # Check if this row is already signed
                existing_row = db.session.execute(
                    text("SELECT jest_podpisany FROM wpis_dziennika WHERE dokument_id = :doc_id AND numer_dnia = :numer"),
                    {'doc_id': dokument_id, 'numer': numer_dnia}
                ).fetchone()

                # If opiekun_firmowy is saving, only update uwagi for unsigned rows
                if role == 'opiekun_firmowy':
                    if existing_row:
                        # Update only uwagi if row exists and is not signed
                        if not existing_row[0]:
                            db.session.execute(
                                text(
                                    "UPDATE wpis_dziennika SET uwagi_opiekuna = :uwagi WHERE dokument_id = :doc_id AND numer_dnia = :numer_dnia"
                                ),
                                {
                                    'doc_id': dokument_id,
                                    'numer_dnia': numer_dnia,
                                    'uwagi': uwagi_opiekuna,
                                }
                            )
                    continue

                # For student: check if row is already signed - if so, skip update
                if existing_row and existing_row[0]:
                    # Row is signed, skip
                    continue

                # Insert or update the row (student can update opis_prac)
                db.session.execute(
                    text(
                        "INSERT OR REPLACE INTO wpis_dziennika (dokument_id, numer_dnia, data_wpisu, opis_prac, uwagi_opiekuna, jest_podpisany) "
                        "VALUES (:doc_id, :numer_dnia, :data_wpisu, :opis_prac, :uwagi, 0)"
                    ),
                    {
                        'doc_id': dokument_id,
                        'numer_dnia': numer_dnia,
                        'data_wpisu': data_wpisu,
                        'opis_prac': opis_prac,
                        'uwagi': uwagi_opiekuna,
                    }
                )

                # Update efekty (only for student)
                db.session.execute(
                    text("DELETE FROM wpis_efekt WHERE dokument_id = :doc_id AND numer_dnia = :numer"),
                    {'doc_id': dokument_id, 'numer': numer_dnia}
                )

                efekty_row = form_data['efekty_rows'][idx] if idx < len(form_data['efekty_rows']) else ''
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
                                "INSERT OR IGNORE INTO wpis_efekt (dokument_id, numer_dnia, nr_efektu) "
                                "VALUES (:doc_id, :numer_dnia, :nr_efektu)"
                            ),
                            {
                                'doc_id': dokument_id,
                                'numer_dnia': numer_dnia,
                                'nr_efektu': numer_efektu,
                            }
                        )

            # Update ostatni_edytor
            db.session.execute(
                text("UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"),
                {'doc_id': dokument_id, 'ostatni': current_user.id}
            )

            db.session.commit()
            flash('Dane załącznika 6 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.zalacznik_6', dokument_id=dokument_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Błąd zapisu załącznika 6: {e}')
            flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # GET - Prepare data for display
    from app import db
    from sqlalchemy import text

    miejsce_praktyki = ''
    data_rozp = ''
    data_zak = ''
    wykaz_zalacznikow = ''

    # Prefer practice linked to document when viewing existing document, otherwise use latest practice for current_user
    prak_id_to_use = None
    if dokument_id and 'dokument_praktyka_id' in locals() and dokument_praktyka_id:
        prak_id_to_use = dokument_praktyka_id
    else:
        prak_id_to_use = None

    if prak_id_to_use:
        practice_row = db.session.execute(
            text(
                "SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc, p.rok_akademicki, f.nazwa AS firma_nazwa, p.data_rozpoczecia, p.data_zakonczenia, uf.imie || ' ' || uf.nazwisko AS firmowy_opiekun "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "LEFT JOIN firma f ON p.firma_id = f.id "
                "LEFT JOIN uzytkownik uf ON p.opiekun_firmowy_id = uf.id "
                "WHERE p.id = :prak_id LIMIT 1"
            ),
            {'prak_id': prak_id_to_use}
        ).fetchone()
    else:
        practice_row = db.session.execute(
            text(
                "SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc, p.rok_akademicki, f.nazwa AS firma_nazwa, p.data_rozpoczecia, p.data_zakonczenia, uf.imie || ' ' || uf.nazwisko AS firmowy_opiekun "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "LEFT JOIN firma f ON p.firma_id = f.id "
                "LEFT JOIN uzytkownik uf ON p.opiekun_firmowy_id = uf.id "
                "WHERE p.student_id = :student_id ORDER BY p.id DESC LIMIT 1"
            ),
            {'student_id': current_user.id}
        ).fetchone()

    if practice_row:
        imie = practice_row[0] or ''
        nazwisko = practice_row[1] or ''
        nr_indeksu = practice_row[2] or ''
        specjalnosc = practice_row[3] or ''
        rok_akademicki = practice_row[4] or ''
        miejsce_praktyki = practice_row[5] or ''
        data_rozp = practice_row[6] or ''
        data_zak = practice_row[7] or ''
        firmowy_opiekun_full_name = practice_row[8] or ''
    else:
        firmowy_opiekun_full_name = ''
        imie = getattr(current_user, 'imie', '') or ''
        nazwisko = getattr(current_user, 'nazwisko', '') or ''
        nr_indeksu = getattr(current_user, 'numer_albumu', '') or ''
        specjalnosc = getattr(current_user, 'specjalnosc', '') or ''
        rok_akademicki = getattr(current_user, 'rok_akademicki', '') or ''

    # Load wykaz_zalacznikow if document exists
    if dokument_id:
        dane_doc = db.session.execute(
            text("SELECT wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id AND klucz LIKE 'zalacznik_%' ORDER BY klucz"),
            {'doc_id': dokument_id}
        ).fetchall()
        if dane_doc:
            wykaz_zalacznikow = ', '.join([row[0] for row in dane_doc if row[0]])

    prefilled = {
        'imie_nazwisko_studenta': f'{imie} {nazwisko}'.strip(),
        'nr_indeksu': nr_indeksu,
        'specjalnosc': specjalnosc,
        'rok_akademicki': rok_akademicki,
        'miejsce_praktyki': miejsce_praktyki,
        'data_rozp': data_rozp,
        'data_zak': data_zak,
        'wykaz_zalacznikow': wykaz_zalacznikow,
        'dokument_id': dokument_id,
        'document_status': document_status,
        'allow_edit': allow_edit,
        'wpisy': wpisy,
        'opiekun_firmowy_full_name': firmowy_opiekun_full_name,
    }

    return render_template(
        'forms/zalacznik_6.html',
        role=role,
        **prefilled
    )



def check_attachment7_complete(form_data):
    """Sprawdzenie czy wszystkie wymagane pola załącznika 7 są wypełnione."""
    required_fields = ['charakterystyka_miejsca', 'opis_i_analiza', 'wiedza_umiejetnosci']
    return all(form_data.get(field, '').strip() for field in required_fields)


def save_attachment7_data(form_data, sign=False):
    """Zapis załącznika 7 (Sprawozdanie z praktyki zawodowej)."""
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 7: %s, sign=%s', form_data, sign)

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

        # Sprawdzenie czy dokument już istnieje
        existing_doc = db.session.execute(
            text("""
                SELECT id, status FROM dokument 
                WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id 
                ORDER BY id DESC LIMIT 1
            """),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()

        if existing_doc:
            dokument_id = existing_doc[0]
            old_status = existing_doc[1]
            # Możemy edytować tylko w statusie 'in_progress' lub 'rejected'
            if old_status not in ['in_progress', 'rejected']:
                current_app.logger.warning('Nie można edytować dokumentu ZAL_7 w statusie %s', old_status)
                return False
        else:
            # Nowy dokument
            is_complete = check_attachment7_complete(form_data)
            status = 'awaiting_approval' if (sign and is_complete) else 'in_progress'
            
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor)"
                    " VALUES (:praktyka_id, :typ_id, :utworzony_przez, :status, :ostatni_edytor)"
                ),
                {
                    'praktyka_id': praktyka_id,
                    'typ_id': typ_id,
                    'utworzony_przez': current_user.id,
                    'status': status,
                    'ostatni_edytor': current_user.id,
                }
            )
            db.session.commit()

            document_row = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).fetchone()
            dokument_id = document_row[0] if document_row else None
            if not dokument_id:
                current_app.logger.error('Nie udało się pobrać dokumentu po zapisie załącznika 7.')
                return False

            # Tworzenie uprawnień
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

        # Aktualizacja danych
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

        # Jeśli student podpisuje i dokument jest kompletny, zaktualizuj status
        if sign and check_attachment7_complete(form_data):
            db.session.execute(
                text("UPDATE dokument SET status='awaiting_approval', ostatni_edytor=:user_id WHERE id=:doc_id"),
                {'doc_id': dokument_id, 'user_id': current_user.id}
            )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 7: {e}')
        return False


def accept_attachment7(dokument_id):
    """Akceptacja załącznika 7 przez opiekuna uczelnianego."""
    from app import db
    from sqlalchemy import text
    from datetime import date

    try:
        # Sprawdzenie uprawnień
        doc_row = db.session.execute(
            text(
                "SELECT d.status, d.praktyka_id FROM dokument d "
                "WHERE d.id=:doc_id AND d.typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row:
            current_app.logger.error('Nie znaleziono ZAL_7 z ID %s', dokument_id)
            return False

        status, praktyka_id = doc_row
        if status != 'awaiting_approval':
            current_app.logger.warning('Nie można zaakceptować ZAL_7 w statusie %s', status)
            return False

        # Aktualizacja statusu
        db.session.execute(
            text("UPDATE dokument SET status='completed', ostatni_edytor=:user_id WHERE id=:doc_id"),
            {'doc_id': dokument_id, 'user_id': current_user.id}
        )

        # Ustawienie daty na koniec
        db.session.execute(
            text(
                "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez)"
                " VALUES (:doc_id, 'data_na_koniec', :data, :user_id)"
            ),
            {'doc_id': dokument_id, 'data': date.today().isoformat(), 'user_id': current_user.id}
        )

        # Aktualizacja praktyki na etap 8 (ZAL_7 completed)
        db.session.execute(
            text("UPDATE praktyka SET aktualny_etap=8 WHERE id=:praktyka_id"),
            {'praktyka_id': praktyka_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd akceptacji ZAL_7: {e}')
        return False


def reject_attachment7(dokument_id):
    """Odrzucenie załącznika 7 przez opiekuna uczelnianego."""
    from app import db
    from sqlalchemy import text

    try:
        # Sprawdzenie statusu
        doc_row = db.session.execute(
            text(
                "SELECT d.status FROM dokument d "
                "WHERE d.id=:doc_id AND d.typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row:
            current_app.logger.error('Nie znaleziono ZAL_7 z ID %s', dokument_id)
            return False

        status = doc_row[0]
        if status != 'awaiting_approval':
            current_app.logger.warning('Nie można odrzucić ZAL_7 w statusie %s', status)
            return False

        # Aktualizacja statusu na rejected
        db.session.execute(
            text("UPDATE dokument SET status='rejected', ostatni_edytor=:user_id WHERE id=:doc_id"),
            {'doc_id': dokument_id, 'user_id': current_user.id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia ZAL_7: {e}')
        return False


@bp.route('/formularz/zalacznik-7', methods=['GET', 'POST'])
@login_required
def zalacznik_7():
    """Formularz załącznika 7 - Sprawozdanie z praktyki zawodowej."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa
    action = request.args.get('action', '')
    dokument_id = request.args.get('dokument_id', type=int)

    # Obsługa akcji approve/reject dla opiekuna uczelnianego
    if action == 'accept' and dokument_id:
        if role != 'opiekun_uczelniany':
            flash('Tylko opiekun uczelniany może zaakceptować załącznik 7.', 'danger')
            return redirect(url_for('dashboard.index'))
        if accept_attachment7(dokument_id):
            flash('Załącznik 7 został zaakceptowany.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Błąd podczas akceptacji załącznika 7.', 'danger')
        return redirect(url_for('dashboard.index'))

    if action == 'reject' and dokument_id:
        if role != 'opiekun_uczelniany':
            flash('Tylko opiekun uczelniany może odrzucić załącznik 7.', 'danger')
            return redirect(url_for('dashboard.index'))
        if reject_attachment7(dokument_id):
            flash('Załącznik 7 został odrzucony.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Błąd podczas odrzucenia załącznika 7.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Pobieranie dokumentu jeśli istnieje
    dokument = None
    dokument_data = {}
    can_edit = False
    can_sign = False

    if dokument_id:
        doc_row = db.session.execute(
            text(
                "SELECT id, status, praktyka_id FROM dokument WHERE id=:id AND typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7')"
            ),
            {'id': dokument_id}
        ).fetchone()
        
        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1]}
            
            # Pobieranie danych dokumentu
            dane_rows = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id=:id"),
                {'id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane_rows}

            # Jeśli dokument jest powiązany z praktyką, pobierz dane studenta i firmy
            try:
                prak_id = doc_row[2] if len(doc_row) > 2 else None
                if prak_id:
                    stud_row = db.session.execute(
                        text(
                            "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc, p.rok_akademicki, f.nazwa "
                            "FROM praktyka p "
                            "JOIN uzytkownik u ON p.student_id = u.id "
                            "LEFT JOIN firma f ON p.firma_id = f.id "
                            "WHERE p.id = :prak_id"
                        ),
                        {'prak_id': prak_id}
                    ).fetchone()
                    if stud_row:
                        student_prefill = {
                            'id': stud_row[0],
                            'imie': stud_row[1] or '',
                            'nazwisko': stud_row[2] or '',
                            'numer_albumu': stud_row[3] or '',
                            'specjalnosc': stud_row[4] or '',
                        }
                        rok_akademicki = stud_row[5] or ''
                        miejsce_praktyki = stud_row[6] or ''
                    else:
                        student_prefill = None
                        rok_akademicki = ''
                        miejsce_praktyki = ''
                else:
                    student_prefill = None
                    rok_akademicki = ''
                    miejsce_praktyki = ''
            except Exception:
                current_app.logger.exception('Błąd pobierania danych studenta/firma dla ZAL_7')
                student_prefill = None
                rok_akademicki = ''
                miejsce_praktyki = ''
            
            # Sprawdzenie uprawnień
            if role == 'student' and dokument['status'] in ['in_progress', 'rejected']:
                can_edit = True
                can_sign = check_attachment7_complete(dokument_data)
    
    # Student może edytować jeśli brak dokumentu (tworzenie) lub dokument jest w statusie edytowalnym
    if role == 'student' and not dokument:
        can_edit = True

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

        sign = 'sign_and_save' in request.form
        saved = save_attachment7_data(form_data, sign=sign)
        if saved:
            if sign:
                flash('Załącznik 7 został podpisany i wysłany do akceptacji.', 'success')
            else:
                flash('Dane załącznika 7 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # Przygotuj prefilled: domyślnie z aktualnie zalogowanego studenta, ale jeśli podglądamy dokument, użyj powiązanego studenta
    if dokument and 'id' in dokument:
        if 'student_prefill' in locals() and student_prefill:
            prefilled_student_name = f"{student_prefill['imie']} {student_prefill['nazwisko']}".strip()
            prefilled_nr = student_prefill.get('numer_albumu', '')
            prefilled_spec = student_prefill.get('specjalnosc', '')
        else:
            # fallback na dane z dokument_data lub aktualnego użytkownika
            prefilled_student_name = dokument_data.get('imie_nazwisko_studenta') or f"{current_user.imie} {current_user.nazwisko}"
            prefilled_nr = dokument_data.get('nr_indeksu') or current_user.numer_albumu or ''
            prefilled_spec = dokument_data.get('specjalnosc') or current_user.specjalnosc or ''

        prefilled = {
            'nr_indeksu': prefilled_nr,
            'imie_nazwisko_studenta': prefilled_student_name,
            'specjalnosc': prefilled_spec,
            'rok_akademicki': dokument_data.get('rok_akademicki', rok_akademicki if 'rok_akademicki' in locals() else ''),
            'miejsce_praktyki': dokument_data.get('miejsce_praktyki', miejsce_praktyki if 'miejsce_praktyki' in locals() else ''),
            'charakterystyka_miejsca': dokument_data.get('charakterystyka_miejsca', ''),
            'opis_i_analiza': dokument_data.get('opis_i_analiza', ''),
            'wiedza_umiejetnosci': dokument_data.get('wiedza_umiejetnosci', ''),
            'data_na_koniec': dokument_data.get('data_na_koniec', date.today().isoformat()),
        }
    else:
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
            'charakterystyka_miejsca': dokument_data.get('charakterystyka_miejsca', ''),
            'opis_i_analiza': dokument_data.get('opis_i_analiza', ''),
            'wiedza_umiejetnosci': dokument_data.get('wiedza_umiejetnosci', ''),
            'data_na_koniec': dokument_data.get('data_na_koniec', date.today().isoformat()),
        }

    return render_template(
        'forms/zalacznik_7.html',
        role=role,
        dokument=dokument,
        can_edit=can_edit,
        can_sign=can_sign,
        **prefilled
    )


def check_attachment7a_complete(form_data):
    """Sprawdzenie czy wszystkie wymagane pola załącznika 7a są wypełnione (bez data_na_koniec)."""
    required_fields = ['charakterystyka_miejsca_pracy', 'opis_i_analiza', 'wiedza_umiejetnosci']
    return all(form_data.get(field, '').strip() for field in required_fields)


def save_attachment7a_data(form_data, sign=False):
    """Zapis załącznika 7a (Sprawozdanie z pracy zawodowej). Student wypełnia i może podpisać."""
    from app import db
    from sqlalchemy import text

    current_app.logger.debug('Zapis załącznika 7a: %s, sign=%s', form_data, sign)

    try:
        student_id = current_user.id
        praktyka_row = db.session.execute(
            text("SELECT id, opiekun_uczelniany_id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
            {'student_id': student_id}
        ).fetchone()
        praktyka_id = praktyka_row[0] if praktyka_row else None
        opiekun_uczelniany_id = praktyka_row[1] if praktyka_row and len(praktyka_row) > 1 else None
        if not praktyka_id:
            current_app.logger.error('Brak praktyki dla studenta %s', student_id)
            return False

        typ_id = db.session.execute(
            text("SELECT id FROM typ_dokumentu WHERE kod='ZAL_7A' LIMIT 1")
        ).scalar()
        if not typ_id:
            current_app.logger.error('Brak typu dokumentu ZAL_7A')
            return False

        # Pobierz lub utwórz dokument
        doc_row = db.session.execute(
            text("SELECT id, status FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id"),
            {'praktyka_id': praktyka_id, 'typ_id': typ_id}
        ).fetchone()
        
        if doc_row:
            dokument_id = doc_row[0]
            current_status = doc_row[1]
            # Sprawdź czy student może edytować
            if current_status not in ['in_progress', 'rejected']:
                current_app.logger.warning('Student nie może edytować ZAL_7a w statusie %s', current_status)
                return False
        else:
            # Utwórz nowy dokument
            db.session.execute(
                text(
                    "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor) "
                    "VALUES (:praktyka_id, :typ_id, :user_id, 'in_progress', :user_id)"
                ),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id, 'user_id': student_id}
            )
            db.session.flush()
            dokument_id = db.session.execute(
                text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                {'praktyka_id': praktyka_id, 'typ_id': typ_id}
            ).scalar()

        # Zapisz dane formularza
        for klucz in ['miejsce_odbycia_praktyki', 'charakterystyka_miejsca_pracy', 'opis_i_analiza', 'wiedza_umiejetnosci']:
            wartosc = form_data.get(klucz, '')
            if wartosc:
                existing = db.session.execute(
                    text("SELECT id FROM dane_dokumentu WHERE dokument_id=:doc_id AND klucz=:klucz"),
                    {'doc_id': dokument_id, 'klucz': klucz}
                ).fetchone()
                if existing:
                    db.session.execute(
                        text("UPDATE dane_dokumentu SET wartosc=:wartosc, wypelnione_przez=:user_id WHERE dokument_id=:doc_id AND klucz=:klucz"),
                        {'wartosc': wartosc, 'user_id': student_id, 'doc_id': dokument_id, 'klucz': klucz}
                    )
                else:
                    db.session.execute(
                        text(
                            "INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
                            "VALUES (:doc_id, :klucz, :wartosc, :user_id)"
                        ),
                        {'doc_id': dokument_id, 'klucz': klucz, 'wartosc': wartosc, 'user_id': student_id}
                    )

        # Jeśli student podpisuje i dokument jest kompletny, zaktualizuj status
        if sign and check_attachment7a_complete(form_data):
            db.session.execute(
                text("UPDATE dokument SET status='awaiting_approval', ostatni_edytor=:user_id WHERE id=:doc_id"),
                {'doc_id': dokument_id, 'user_id': student_id}
            )

        # Przypisz uprawnienia w udostepniony_dokument (tylko dla nowo utworzonych dokumentów)
        if not doc_row:
            role_rows = db.session.execute(
                text("SELECT nazwa, id FROM role WHERE nazwa IN ('student','dziekanat','opiekun_uczelniany','dyrektor')")
            ).fetchall()
            role_ids = {row[0]: row[1] for row in role_rows}

            # Student - może podglądać, edytować, podpisywać
            if student_id and role_ids.get('student'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                    ),
                    {
                        'udostepniajacy': student_id,
                        'dokument_id': dokument_id,
                        'adresat': student_id,
                        'rola_id': role_ids['student'],
                    }
                )

            # Dziekanat - może tylko podglądać
            if role_ids.get('dziekanat'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': student_id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dziekanat'],
                    }
                )

            # Opiekun uczelniany - może podglądać i akceptować
            if opiekun_uczelniany_id and role_ids.get('opiekun_uczelniany'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 0, 1)"
                    ),
                    {
                        'udostepniajacy': student_id,
                        'dokument_id': dokument_id,
                        'adresat': opiekun_uczelniany_id,
                        'rola_id': role_ids['opiekun_uczelniany'],
                    }
                )

            # Dyrektor - może tylko podglądać
            if role_ids.get('dyrektor'):
                db.session.execute(
                    text(
                        "INSERT INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                        " VALUES (:udostepniajacy, :dokument_id, NULL, :rola_id, 1, 0, 0, 0)"
                    ),
                    {
                        'udostepniajacy': student_id,
                        'dokument_id': dokument_id,
                        'rola_id': role_ids['dyrektor'],
                    }
                )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 7a: {e}')
        return False


def accept_attachment7a(dokument_id):
    """Akceptacja załącznika 7a przez opiekuna uczelnianego."""
    from app import db
    from sqlalchemy import text
    from datetime import date

    try:
        doc_row = db.session.execute(
            text(
                "SELECT d.status, d.praktyka_id FROM dokument d "
                "WHERE d.id=:doc_id AND d.typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7A')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row:
            current_app.logger.error('Nie znaleziono ZAL_7A z ID %s', dokument_id)
            return False

        status, praktyka_id = doc_row
        if status != 'awaiting_approval':
            current_app.logger.warning('Nie można zaakceptować ZAL_7A w statusie %s', status)
            return False

        # Aktualizacja statusu
        db.session.execute(
            text("UPDATE dokument SET status='completed', ostatni_edytor=:user_id WHERE id=:doc_id"),
            {'doc_id': dokument_id, 'user_id': current_user.id}
        )

        # Ustawienie daty na koniec
        db.session.execute(
            text(
                "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez)"
                " VALUES (:doc_id, 'data_na_koniec', :data, :user_id)"
            ),
            {'doc_id': dokument_id, 'data': date.today().isoformat(), 'user_id': current_user.id}
        )

        # Aktualizacja praktyki na etap 3 (ZAL_7A completed)
        db.session.execute(
            text("UPDATE praktyka SET aktualny_etap=3 WHERE id=:praktyka_id"),
            {'praktyka_id': praktyka_id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd akceptacji ZAL_7A: {e}')
        return False


def reject_attachment7a(dokument_id):
    """Odrzucenie załącznika 7a przez opiekuna uczelnianego."""
    from app import db
    from sqlalchemy import text

    try:
        doc_row = db.session.execute(
            text(
                "SELECT d.status FROM dokument d "
                "WHERE d.id=:doc_id AND d.typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7A')"
            ),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row:
            current_app.logger.error('Nie znaleziono ZAL_7A z ID %s', dokument_id)
            return False

        status = doc_row[0]
        if status != 'awaiting_approval':
            current_app.logger.warning('Nie można odrzucić ZAL_7A w statusie %s', status)
            return False

        # Aktualizacja statusu na rejected
        db.session.execute(
            text("UPDATE dokument SET status='rejected', ostatni_edytor=:user_id WHERE id=:doc_id"),
            {'doc_id': dokument_id, 'user_id': current_user.id}
        )

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia ZAL_7A: {e}')
        return False


@bp.route('/formularz/zalacznik-7a', methods=['GET', 'POST'])
@login_required
def zalacznik_7a():
    """Formularz załącznika 7a - Sprawozdanie z pracy zawodowej lub działalności gospodarczej."""
    from app import db
    from sqlalchemy import text

    role = current_user.rola.nazwa
    action = request.args.get('action', '')
    dokument_id = request.args.get('dokument_id', type=int)

    # Obsługa akcji accept/reject dla opiekuna uczelnianego
    if action == 'accept' and dokument_id:
        if role != 'opiekun_uczelniany':
            flash('Tylko opiekun uczelniany może zaakceptować załącznik 7a.', 'danger')
            return redirect(url_for('dashboard.index'))
        if accept_attachment7a(dokument_id):
            flash('Załącznik 7a został zaakceptowany.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Błąd podczas akceptacji załącznika 7a.', 'danger')
        return redirect(url_for('dashboard.index'))

    if action == 'reject' and dokument_id:
        if role != 'opiekun_uczelniany':
            flash('Tylko opiekun uczelniany może odrzucić załącznik 7a.', 'danger')
            return redirect(url_for('dashboard.index'))
        if reject_attachment7a(dokument_id):
            flash('Załącznik 7a został odrzucony.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Błąd podczas odrzucenia załącznika 7a.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Pobieranie dokumentu jeśli istnieje
    dokument = None
    dokument_data = {}
    can_edit = False
    can_sign = False
    student_id = current_user.id if role == 'student' else None

    if dokument_id:
        doc_row = db.session.execute(
            text(
                "SELECT d.id, d.status, d.praktyka_id, p.student_id FROM dokument d "
                "JOIN praktyka p ON d.praktyka_id = p.id "
                "WHERE d.id=:id AND d.typ_dokumentu_id=(SELECT id FROM typ_dokumentu WHERE kod='ZAL_7A')"
            ),
            {'id': dokument_id}
        ).fetchone()
        
        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1], 'praktyka_id': doc_row[2], 'student_id': doc_row[3]}
            if role != 'student':
                student_id = doc_row[3]
            
            # Pobieranie danych dokumentu
            dane_rows = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id=:id"),
                {'id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane_rows}
            
            # Sprawdzenie uprawnień
            if role == 'student' and dokument['status'] in ['in_progress', 'rejected']:
                can_edit = True
                can_sign = check_attachment7a_complete(dokument_data)
    
    # Student może edytować jeśli brak dokumentu (tworzenie) lub dokument jest w statusie edytowalnym
    if role == 'student' and not dokument:
        can_edit = True

    if request.method == 'POST':
        if role != 'student':
            flash('Tylko student może zapisać załącznik 7a.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'miejsce_odbycia_praktyki': request.form.get('miejsce_odbycia_praktyki'),
            'charakterystyka_miejsca_pracy': request.form.get('charakterystyka_miejsca_pracy'),
            'opis_i_analiza': request.form.get('opis_i_analiza'),
            'wiedza_umiejetnosci': request.form.get('wiedza_umiejetnosci'),
            'data_na_koniec': request.form.get('data_na_koniec'),
        }

        sign = 'sign_and_save' in request.form
        saved = save_attachment7a_data(form_data, sign=sign)
        if saved:
            if sign:
                flash('Załącznik 7a został podpisany i wysłany do akceptacji.', 'success')
            else:
                flash('Dane załącznika 7a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    # Pobierz dane studenta i praktyki
    if student_id:
        student_row = db.session.execute(
            text(
                "SELECT u.imie, u.nazwisko, u.numer_albumu, u.specjalnosc FROM uzytkownik u WHERE u.id = :student_id"
            ),
            {'student_id': student_id}
        ).fetchone()
    else:
        student_row = None

    praktyka_row = db.session.execute(
        text(
            "SELECT p.rok_akademicki FROM praktyka p WHERE p.student_id = :student_id ORDER BY p.id DESC LIMIT 1"
        ),
        {'student_id': student_id}
    ).fetchone() if student_id else None

    rok_akademicki = praktyka_row[0] if praktyka_row and praktyka_row[0] else ''

    prefilled = {
        'nr_indeksu': student_row[2] if student_row else '',
        'imie_nazwisko_studenta': f"{student_row[0]} {student_row[1]}" if student_row else '',
        'specjalnosc': student_row[3] if student_row else '',
        'rok_akademicki': rok_akademicki,
        'miejsce_odbycia_praktyki': dokument_data.get('miejsce_odbycia_praktyki', ''),
        'charakterystyka_miejsca_pracy': dokument_data.get('charakterystyka_miejsca_pracy', ''),
        'opis_i_analiza': dokument_data.get('opis_i_analiza', ''),
        'wiedza_umiejetnosci': dokument_data.get('wiedza_umiejetnosci', ''),
        'data_na_koniec': dokument_data.get('data_na_koniec', date.today().isoformat()),
    }

    return render_template(
        'forms/zalacznik_7a.html',
        role=role,
        dokument=dokument,
        can_edit=can_edit,
        can_sign=can_sign,
        **prefilled
    )


def save_attachment8_data(form_data):
    """Zapisz załącznik 8 do bazy: dokument, pytanie_komisji, dane_dokumentu."""
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    try:
        def normalized(field, default=''):
            value = form_data.get(field, default)
            if value is None:
                return default
            return value.strip() if isinstance(value, str) else str(value)

        student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
        if not student_id:
            current_app.logger.error('Brak student_id w form_data')
            return False

        # Znajdź praktykę dla studenta
        praktyka_row = db.session.execute(text(
            "SELECT id, sciezka, opiekun_firmowy_id, opiekun_uczelniany_id "
            "FROM praktyka WHERE student_id = :student_id ORDER BY utworzono DESC LIMIT 1"
        ), {'student_id': student_id}).fetchone()
        if not praktyka_row:
            current_app.logger.error('Brak praktyki dla studenta %s', student_id)
            return False

        praktyka_id = praktyka_row[0]
        praktyka_sciezka = praktyka_row[1] if len(praktyka_row) > 1 else None
        opiekun_firmowy_id = praktyka_row[2] if len(praktyka_row) > 2 else None
        opiekun_uczelniany_id = praktyka_row[3] if len(praktyka_row) > 3 else None

        typ_doc_result = db.session.execute(text(
            "SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_8'"
        )).fetchone()
        if not typ_doc_result:
            current_app.logger.error('Brak typu dokumentu ZAL_8')
            return False
        typ_dokumentu_id = typ_doc_result[0]

        existing_doc = db.session.execute(text(
            "SELECT id, status FROM dokument "
            "WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_id "
            "ORDER BY id DESC LIMIT 1"
        ), {'praktyka_id': praktyka_id, 'typ_id': typ_dokumentu_id}).fetchone()

        dokument_id = existing_doc[0] if existing_doc else None
        dokument_status = existing_doc[1] if existing_doc else None

        if dokument_id and dokument_status in ('awaiting_signature', 'completed'):
            current_app.logger.error('Załącznik 8 nie może być edytowany: dokument_id=%s, status=%s', dokument_id, dokument_status)
            return False

        role_name = current_user.rola.nazwa
        if dokument_id and role_name == 'dziekanat':
            current_app.logger.error('Dziekanat nie może edytować istniejącego załącznika 8: dokument_id=%s', dokument_id)
            return False

        # Prefill ZAL_3 data for auto-filled pola
        zal3_data = {}
        zal3_doc = db.session.execute(text(
            "SELECT d.id FROM dokument d "
            "JOIN typ_dokumentu t ON d.typ_dokumentu_id = t.id "
            "WHERE d.praktyka_id = :praktyka_id AND t.kod = 'ZAL_3' "
            "ORDER BY d.id DESC LIMIT 1"
        ), {'praktyka_id': praktyka_id}).fetchone()
        if zal3_doc:
            zal3_rows = db.session.execute(text(
                "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"
            ), {'doc_id': zal3_doc[0]}).fetchall()
            zal3_data = {row[0]: row[1] or '' for row in zal3_rows}

        opiekun_name = ''
        if opiekun_uczelniany_id:
            user_row = db.session.execute(
                text("SELECT imie, nazwisko FROM uzytkownik WHERE id = :id"),
                {'id': opiekun_uczelniany_id}
            ).fetchone()
            if user_row:
                opiekun_name = f"{user_row[0]} {user_row[1]}"

        existing_zal8_data = {}
        if dokument_id:
            existing_rows = db.session.execute(text(
                "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"
            ), {'doc_id': dokument_id}).fetchall()
            existing_zal8_data = {row[0]: row[1] or '' for row in existing_rows}

        # Uzupełnij dane domyślnymi wartościami, jeśli brak w formularzu
        data_zaliczenia = normalized('data_zaliczenia')
        if praktyka_sciezka == 'alternative':
            ocena_sprawozdania_s = normalized('ocena_sprawozdania_s') or existing_zal8_data.get('ocena_sprawozdania_s', '')
            data_oceny_s = normalized('data_oceny_s') or existing_zal8_data.get('data_oceny_s', '')
            ocena_u = normalized('ocena_u') or existing_zal8_data.get('ocena_u', '')
            ocena_z = normalized('ocena_z') or existing_zal8_data.get('ocena_z', '')
        else:
            ocena_sprawozdania_s = normalized('ocena_sprawozdania_s') or zal3_data.get('ocena_sprawozdania', '')
            data_oceny_s = normalized('data_oceny_s') or zal3_data.get('data_sprawozdania', '')
            ocena_u = normalized('ocena_u') or zal3_data.get('ocena_przebiegu_ou', '')
            ocena_z = normalized('ocena_z') or zal3_data.get('ocena_przebiegu_of', '')
        imie_nazwisko_2 = normalized('imie_nazwisko_2') or opiekun_name
        funkcja_2 = normalized('funkcja_2') or ('Uczelniany opiekun praktyki zawodowej' if imie_nazwisko_2 else '')

        if not dokument_id:
            db.session.execute(text(
                "INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, ostatni_edytor) "
                "VALUES (:praktyka_id, :typ_dokumentu_id, :utworzony_przez, 'in_progress', :ostatni_edytor)"
            ), {
                'praktyka_id': praktyka_id,
                'typ_dokumentu_id': typ_dokumentu_id,
                'utworzony_przez': current_user.id,
                'ostatni_edytor': current_user.id,
            })
            db.session.flush()
            dokument_id = db.session.execute(text(
                "SELECT id FROM dokument WHERE praktyka_id = :praktyka_id AND typ_dokumentu_id = :typ_dokumentu_id "
                "ORDER BY id DESC LIMIT 1"
            ), {'praktyka_id': praktyka_id, 'typ_dokumentu_id': typ_dokumentu_id}).fetchone()[0]
        else:
            db.session.execute(text(
                "UPDATE dokument SET ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"
            ), {'ostatni_edytor': current_user.id, 'doc_id': dokument_id})

        role_rows = db.session.execute(text(
            "SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_uczelniany', 'opiekun_firmowy', 'dyrektor', 'czlonek_komisji')"
        )).fetchall()
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
        if role_ids.get('opiekun_uczelniany'):
            add_share(None, role_ids.get('opiekun_uczelniany'), True, True, False, False)
        if role_ids.get('czlonek_komisji'):
            add_share(None, role_ids.get('czlonek_komisji'), True, True, False, False)
        if role_ids.get('opiekun_firmowy'):
            add_share(None, role_ids.get('opiekun_firmowy'), True, False, False, False)
        if role_ids.get('dyrektor'):
            add_share(None, role_ids.get('dyrektor'), True, False, False, False)

        for (adresat, rola_id), perms in shared_entries.items():
            db.session.execute(text(
                "INSERT OR IGNORE INTO udostepniony_dokument "
                "(udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, :moze_podgladac, :moze_edytowac, :moze_podpisac, :moze_akceptowac)"
            ), {
                'udostepniajacy': current_user.id,
                'dokument_id': dokument_id,
                'adresat': adresat,
                'rola_id': rola_id,
                'moze_podgladac': 1 if perms[0] else 0,
                'moze_edytowac': 1 if perms[1] else 0,
                'moze_podpisac': 1 if perms[2] else 0,
                'moze_akceptowac': 1 if perms[3] else 0,
            })

        db.session.execute(text("DELETE FROM pytanie_komisji WHERE dokument_id = :doc_id"), {'doc_id': dokument_id})
        for i in range(1, 4):
            pytanie_text = normalized(f'pytanie_{i}')
            ocena_str = normalized(f'ocena_cz_{i}')
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

        dane_keys = [
            'imie_nazwisko_1', 'funkcja_1', 'imie_nazwisko_2', 'funkcja_2',
            'imie_nazwisko_3', 'funkcja_3', 'imie_nazwisko_4', 'funkcja_4',
            'data_zaliczenia', 'ocena_za_mini_zadania_e', 'ocena_koncowa'
        ]
        for key in dane_keys:
            value = form_data.get(key, '')
            if key == 'ocena_sprawozdania_s':
                value = ocena_sprawozdania_s
            if key == 'data_oceny_s':
                value = data_oceny_s
            if key == 'ocena_u':
                value = ocena_u
            if key == 'ocena_z':
                value = ocena_z
            if key == 'imie_nazwisko_2' and not value:
                value = imie_nazwisko_2
            if key == 'funkcja_2' and not value:
                value = funkcja_2
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

        # Zapisz dodatkowe pola ZAL_8, w tym pola prefilled z ZAL_3
        db.session.execute(text(
            "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
            "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
        ), {
            'dokument_id': dokument_id,
            'klucz': 'ocena_sprawozdania_s',
            'wartosc': ocena_sprawozdania_s,
            'wypelnione_przez': current_user.id,
        })
        db.session.execute(text(
            "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
            "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
        ), {
            'dokument_id': dokument_id,
            'klucz': 'data_oceny_s',
            'wartosc': data_oceny_s,
            'wypelnione_przez': current_user.id,
        })
        db.session.execute(text(
            "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
            "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
        ), {
            'dokument_id': dokument_id,
            'klucz': 'ocena_u',
            'wartosc': ocena_u,
            'wypelnione_przez': current_user.id,
        })
        db.session.execute(text(
            "INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) "
            "VALUES (:dokument_id, :klucz, :wartosc, :wypelnione_przez)"
        ), {
            'dokument_id': dokument_id,
            'klucz': 'ocena_z',
            'wartosc': ocena_z,
            'wypelnione_przez': current_user.id,
        })

        all_required_filled = True
        required_keys = {
            'data_zaliczenia': data_zaliczenia,
            'ocena_sprawozdania_s': ocena_sprawozdania_s,
            'data_oceny_s': data_oceny_s,
            'ocena_u': ocena_u,
            'ocena_z': ocena_z,
            'imie_nazwisko_1': normalized('imie_nazwisko_1'),
            'funkcja_1': normalized('funkcja_1'),
            'imie_nazwisko_2': imie_nazwisko_2,
            'funkcja_2': funkcja_2,
            'imie_nazwisko_3': normalized('imie_nazwisko_3'),
            'funkcja_3': normalized('funkcja_3'),
            'imie_nazwisko_4': normalized('imie_nazwisko_4'),
            'funkcja_4': normalized('funkcja_4'),
            'pytanie_1': normalized('pytanie_1'),
            'pytanie_2': normalized('pytanie_2'),
            'pytanie_3': normalized('pytanie_3'),
            'ocena_cz_1': normalized('ocena_cz_1'),
            'ocena_cz_2': normalized('ocena_cz_2'),
            'ocena_cz_3': normalized('ocena_cz_3'),
            'ocena_za_mini_zadania_e': normalized('ocena_za_mini_zadania_e'),
            'ocena_koncowa': normalized('ocena_koncowa'),
        }
        for value in required_keys.values():
            if not value:
                all_required_filled = False
                break

        if all_required_filled:
            db.session.execute(text(
                "UPDATE dokument SET status = 'awaiting_signature', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ), {'ostatni': current_user.id, 'doc_id': dokument_id})
            db.session.execute(text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :doc_id"
            ), {'doc_id': dokument_id})

            signer_names = [
                ('imie_nazwisko_1', role_ids.get('czlonek_komisji')),
                ('imie_nazwisko_2', role_ids.get('opiekun_uczelniany')),
                ('imie_nazwisko_3', role_ids.get('czlonek_komisji')),
                ('imie_nazwisko_4', role_ids.get('czlonek_komisji')),
            ]
            signer_ids = []
            for field_name, expected_role in signer_names:
                name = normalized(field_name)
                if not name or not expected_role:
                    continue
                user_row = db.session.execute(
                    text("SELECT id, rola_id FROM uzytkownik WHERE imie || ' ' || nazwisko = :name LIMIT 1"),
                    {'name': name}
                ).fetchone()
                if not user_row:
                    continue
                signer_id, signer_role = user_row
                if signer_role != expected_role:
                    continue
                signer_ids.append((signer_id, signer_role))

            signer_ids = list(dict.fromkeys(signer_ids))
            for signer_id, signer_role in signer_ids:
                db.session.execute(text(
                    "INSERT OR IGNORE INTO udostepniony_dokument "
                    "(udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac) "
                    "VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 0, 1, 0)"
                ), {
                    'udostepniajacy': current_user.id,
                    'dokument_id': dokument_id,
                    'adresat': signer_id,
                    'rola_id': signer_role,
                })
                db.session.execute(text(
                    "UPDATE udostepniony_dokument SET moze_podpisac = 1 WHERE dokument_id = :doc_id AND adresat = :adresat"
                ), {'doc_id': dokument_id, 'adresat': signer_id})
                db.session.execute(text(
                    "INSERT OR IGNORE INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) "
                    "VALUES (:doc_id, :podpisujacy_id, 0)"
                ), {
                    'doc_id': dokument_id,
                    'podpisujacy_id': signer_id,
                })
        else:
            db.session.execute(text(
                "UPDATE dokument SET status = 'in_progress', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ), {'ostatni': current_user.id, 'doc_id': dokument_id})

        db.session.commit()
        current_app.logger.info('Załącznik 8 zapisany: dokument_id=%s', dokument_id)
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Błąd przy zapisie załącznika 8: %s', str(e))
        return False


def sign_attachment8(dokument_id):
    """Podpisanie załącznika 8 przez członka komisji lub opiekuna uczelnianego."""
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    try:
        doc_row = db.session.execute(text(
            "SELECT praktyka_id, status FROM dokument WHERE id = :doc_id"
        ), {'doc_id': dokument_id}).fetchone()
        if not doc_row or doc_row[1] != 'awaiting_signature':
            return False

        result = db.session.execute(text(
            "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano "
            "WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
        ), {
            'doc_id': dokument_id,
            'podpisujacy_id': current_user.id,
            'podpisano': datetime.now(),
        })
        if result.rowcount == 0:
            db.session.execute(text(
                "INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany, podpisano) "
                "VALUES (:doc_id, :podpisujacy_id, 1, :podpisano)"
            ), {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now(),
            })

        signed_count = db.session.execute(text(
            "SELECT COUNT(*) FROM dokument_podpis WHERE dokument_id = :doc_id AND czy_podpisany = 1"
        ), {'doc_id': dokument_id}).scalar()
        required_count = db.session.execute(text(
            "SELECT COUNT(*) FROM dokument_podpis WHERE dokument_id = :doc_id"
        ), {'doc_id': dokument_id}).scalar()

        if signed_count == required_count and required_count > 0:
            praktyka_id = doc_row[0]
            db.session.execute(text(
                "UPDATE dokument SET status = 'completed', ostatni_edytor = :ostatni WHERE id = :doc_id"
            ), {'ostatni': current_user.id, 'doc_id': dokument_id})
            db.session.execute(text(
                "UPDATE praktyka SET status = 'completed', aktualny_etap = 9 WHERE id = :praktyka_id"
            ), {'praktyka_id': praktyka_id})
            db.session.execute(text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0, moze_podpisac = 0 WHERE dokument_id = :doc_id"
            ), {'doc_id': dokument_id})
        else:
            db.session.execute(text(
                "UPDATE dokument SET ostatni_edytor = :ostatni WHERE id = :doc_id"
            ), {'ostatni': current_user.id, 'doc_id': dokument_id})

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania załącznika 8: {e}')
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
    opiekun_prefill = ''
    opiekun_prefill_id = None

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

    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action = request.args.get('action', '')

    dokument = None
    can_edit = False
    can_sign = False
    can_create = role == 'dziekanat'
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

    if dokument_id:
        doc_row = db.session.execute(text(
            "SELECT d.id, d.status, d.praktyka_id, p.student_id "
            "FROM dokument d "
            "JOIN praktyka p ON d.praktyka_id = p.id "
            "WHERE d.id = :doc_id AND d.typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod = 'ZAL_8')"
        ), {'doc_id': dokument_id}).fetchone()
        if doc_row:
            dokument = {
                'id': doc_row[0],
                'status': doc_row[1],
                'praktyka_id': doc_row[2],
                'student_id': doc_row[3],
            }
            selected_practice_id = dokument['praktyka_id']
            student_row = db.session.execute(text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ), {'praktyka_id': selected_practice_id}).fetchone()
            if student_row:
                selected_student = {
                    'id': student_row[0],
                    'imie': student_row[1] or '',
                    'nazwisko': student_row[2] or '',
                    'numer_albumu': student_row[3] or '',
                }

            dane_rows = db.session.execute(text(
                "SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"
            ), {'doc_id': dokument_id}).fetchall()
            for key, value in dane_rows:
                prefilled[key] = value or ''

            pytania_rows = db.session.execute(text(
                "SELECT numer_pytania, tresc_pytania, wartosc_oceny FROM pytanie_komisji WHERE dokument_id = :doc_id"
            ), {'doc_id': dokument_id}).fetchall()
            for numer, tresc, wartosc in pytania_rows:
                prefilled[f'pytanie_{numer}'] = tresc or ''
                prefilled[f'ocena_cz_{numer}'] = wartosc or ''

            if dokument['status'] in ('in_progress', 'rejected'):
                can_edit = role in ['opiekun_uczelniany', 'czlonek_komisji']
            if dokument['status'] == 'awaiting_signature':
                signer_row = db.session.execute(text(
                    "SELECT czy_podpisany FROM dokument_podpis WHERE dokument_id = :doc_id AND podpisujacy_id = :user_id"
                ), {'doc_id': dokument_id, 'user_id': current_user.id}).fetchone()
                can_sign = signer_row is not None and signer_row[0] == 0
                can_create = False

    if action == 'sign' and dokument and can_sign:
        if sign_attachment8(dokument['id']):
            flash('Dokument został podpisany.', 'success')
        else:
            flash('Nie udało się podpisać dokumentu.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_uczelniany', 'czlonek_komisji']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if not (can_edit or (role == 'dziekanat' and not dokument)):
            flash('Nie masz uprawnień do edycji tego dokumentu.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'student_id': request.form.get('student_id'),
            'data_zaliczenia': request.form.get('data_zaliczenia', ''),
            'ocena_sprawozdania_s': request.form.get('ocena_sprawozdania_s', ''),
            'data_oceny_s': request.form.get('data_oceny_s', ''),
            'ocena_u': request.form.get('ocena_u', ''),
            'ocena_z': request.form.get('ocena_z', ''),
            'ocena_za_mini_zadania_e': request.form.get('ocena_za_mini_zadania_e', ''),
            'ocena_koncowa': request.form.get('ocena_koncowa', ''),
            'imie_nazwisko_2': request.form.get('imie_nazwisko_2', ''),
            'funkcja_2': request.form.get('funkcja_2', ''),
            'dokument_id': dokument_id,
        }
        for i in range(1, 5):
            form_data[f'imie_nazwisko_{i}'] = request.form.get(f'imie_nazwisko_{i}', '')
            form_data[f'funkcja_{i}'] = request.form.get(f'funkcja_{i}', '')
        for i in range(1, 4):
            form_data[f'pytanie_{i}'] = request.form.get(f'pytanie_{i}', '')
            form_data[f'ocena_cz_{i}'] = request.form.get(f'ocena_cz_{i}', '')

        saved = save_attachment8_data(form_data)
        if saved:
            flash('Dane załącznika 8 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    if selected_practice_id:
        student_row = db.session.execute(
            text(
                "SELECT u.id, u.imie, u.nazwisko, u.numer_albumu "
                "FROM praktyka p "
                "JOIN uzytkownik u ON p.student_id = u.id "
                "WHERE p.id = :praktyka_id"
            ), {'praktyka_id': selected_practice_id}
        ).fetchone()
        if student_row:
            selected_student = {
                'id': student_row[0],
                'imie': student_row[1] or '',
                'nazwisko': student_row[2] or '',
                'numer_albumu': student_row[3] or '',
            }
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

    if selected_student:
        prefilled['imie_nazwisko_studenta'] = f"{selected_student['imie']} {selected_student['nazwisko']}"
        prefilled['nr_indeksu'] = selected_student['numer_albumu']
        prefilled['student_id'] = selected_student['id']

    can_create = role == 'dziekanat' and dokument is None

    return render_template(
        'forms/zalacznik_8.html',
        role=role,
        studenci=studenci,
        student_zal3_json=json.dumps(zal3_data),
        czlonkowie_komisji_json=json.dumps(czlonkowie_komisji),
        komisja_osoby_json=json.dumps(komisja_osoby),
        prefilled_opiekun=opiekun_prefill,
        prefilled_opiekun_id=opiekun_prefill_id,
        dokument=dokument,
        can_edit=can_edit,
        can_sign=can_sign,
        can_create=can_create,
        **prefilled
    )


def save_attachment9_data(form_data):
    """Zapis załącznika 9 (Oświadczenie instytucji w sprawie przyjęcia studenta).
    
    Tworzy dokument ze statusem 'in_progress' i wpis podpisu z czy_podpisano=0.
    Tworzy praktykę ze statusem 'pending' (będzie aktywowana dopiero przy zatwierdzeniu).
    """
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

        if not student_id:
            return False

        # Firma i opiekun firmowy
        firma_id = current_user.firma_id
        opiekun_id = current_user.id

        # Pobierz rok akademicki studenta
        rok_akademicki = None
        student = Uzytkownik.query.get(student_id)
        rok_akademicki = student.rok_akademicki if student else None

        # 1) Sprawdź czy już istnieje dokument ZAL_9 dla tego studenta
        existing_doc = db.session.execute(
            text("""
                SELECT d.id, d.praktyka_id, d.status FROM dokument d
                WHERE d.typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_9')
                AND d.praktyka_id IN (
                    SELECT id FROM praktyka WHERE student_id = :student_id
                )
                ORDER BY d.id DESC LIMIT 1
            """),
            {'student_id': student_id}
        ).fetchone()

        if existing_doc:
            dokument_id = existing_doc[0]
            praktyka_id = existing_doc[1]
            dokument_status = existing_doc[2]

            # Jeśli dokument był odrzucony, przywróć go do ponownej edycji
            if dokument_status == 'rejected':
                db.session.execute(
                    text("UPDATE dokument SET status = 'in_progress', ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                    {'ostatni_edytor': current_user.id, 'doc_id': dokument_id}
                )
                db.session.execute(
                    text(
                        "UPDATE udostepniony_dokument SET moze_edytowac = 1 WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
                    ),
                    {'doc_id': dokument_id}
                )
            else:
                db.session.execute(
                    text("UPDATE dokument SET ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
                    {'ostatni_edytor': current_user.id, 'doc_id': dokument_id}
                )
        else:
            # Utwórz nową praktykę ze statusem 'pending' (zostanie aktywowana przy zatwierdzeniu)
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
            db.session.flush()

            # Pobierz ID nowo utworzonej praktyki
            praktyka_row = db.session.execute(
                text("SELECT id FROM praktyka WHERE student_id=:student_id ORDER BY id DESC LIMIT 1"),
                {'student_id': student_id}
            ).fetchone()
            praktyka_id = praktyka_row[0] if praktyka_row else None

            # 2) Utwórz dokument ze statusem 'in_progress'
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
                        'status': 'in_progress',
                        'ostatni_edytor': current_user.id
                    }
                )
                db.session.flush()

                doc_row = db.session.execute(
                    text("SELECT id FROM dokument WHERE praktyka_id=:praktyka_id AND typ_dokumentu_id=:typ_id ORDER BY id DESC LIMIT 1"),
                    {'praktyka_id': praktyka_id, 'typ_id': typ_id}
                ).fetchone()
                dokument_id = doc_row[0] if doc_row else None

                # 3) Utwórz wpis w dokument_podpis z czy_podpisano=0
                if dokument_id:
                    db.session.execute(
                        text("INSERT INTO dokument_podpis (dokument_id, podpisujacy_id, czy_podpisany) VALUES (:doc_id, :podpisujacy_id, 0)"),
                        {'doc_id': dokument_id, 'podpisujacy_id': current_user.id}
                    )

                    # 4) Utwórz wpisy w `dane_dokumentu` (miejscowosc, data)
                    db.session.execute(
                        text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                        {'doc_id': dokument_id, 'klucz': 'miejscowosc', 'wartosc': miejscowosc, 'wypelniajacy': current_user.id}
                    )
                    db.session.execute(
                        text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                        {'doc_id': dokument_id, 'klucz': 'data', 'wartosc': data_pola, 'wypelniajacy': current_user.id}
                    )

                    # 5) Udostępnij dokument
                    role_rows = db.session.execute(
                        text("SELECT nazwa, id FROM role WHERE nazwa IN ('student', 'dziekanat', 'opiekun_firmowy', 'dyrektor')")
                    ).fetchall()
                    role_ids = {row[0]: row[1] for row in role_rows}

                    if student_id and role_ids.get('student'):
                        db.session.execute(
                            text(
                                "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                                "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                                "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
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
                                "INSERT OR IGNORE INTO udostepniony_dokument (udostepniajacy, dokument_id, adresat, rola_id, moze_podgladac, moze_edytowac, moze_podpisac, moze_akceptowac)"
                                " VALUES (:udostepniajacy, :dokument_id, :adresat, :rola_id, 1, 1, 1, 0)"
                            ),
                            {
                                'udostepniajacy': current_user.id,
                                'dokument_id': dokument_id,
                                'adresat': current_user.id,
                                'rola_id': role_ids['opiekun_firmowy'],
                            }
                        )

        # 6) Zaktualizuj dane dokumentu jeśli już istniał
        if dokument_id:
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'miejscowosc', 'wartosc': miejscowosc, 'wypelniajacy': current_user.id}
            )
            db.session.execute(
                text("INSERT OR REPLACE INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES (:doc_id, :klucz, :wartosc, :wypelniajacy)"),
                {'doc_id': dokument_id, 'klucz': 'data', 'wartosc': data_pola, 'wypelniajacy': current_user.id}
            )

        # 7) Zaktualizuj nazwę firmy i numer telefonu opiekuna firmowego
        if firma_id:
            firma = Firma.query.get(firma_id)
            if firma and nazwa_firmy:
                firma.nazwa = nazwa_firmy
            if telefon_opiekuna:
                current_user.telefon = telefon_opiekuna

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd zapisu załącznika 9: {e}')
        return False


def sign_attachment9(dokument_id):
    """Podpisanie załącznika 9 przez opiekuna firmowego.
    
    Zmienia status na 'awaiting_approval' i dodaje podpis.
    """
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    try:
        # Sprawdź uprawnienia
        doc_row = db.session.execute(
            text("SELECT praktyka_id, status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[1] not in ('in_progress', 'rejected'):
            return False

        # Przywróć odrzucony dokument do ponownej edycji, jeśli to konieczne
        if doc_row[1] == 'rejected':
            db.session.execute(
                text("UPDATE dokument SET status = 'in_progress' WHERE id = :doc_id"),
                {'doc_id': dokument_id}
            )

        # Zaktualizuj podpis
        db.session.execute(
            text(
                "UPDATE dokument_podpis SET czy_podpisany = 1, podpisano = :podpisano WHERE dokument_id = :doc_id AND podpisujacy_id = :podpisujacy_id"
            ),
            {
                'doc_id': dokument_id,
                'podpisujacy_id': current_user.id,
                'podpisano': datetime.now()
            }
        )

        # Zmień status dokumentu
        db.session.execute(
            text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
            {
                'doc_id': dokument_id,
                'status': 'awaiting_approval',
                'ostatni_edytor': current_user.id
            }
        )

        # Zabraniaj edycji opiekunowi firmowemu
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 0 WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd podpisania załącznika 9: {e}')
        return False


def accept_attachment9(dokument_id):
    """Zaakceptowanie załącznika 9 przez dziekanat.
    
    Zmienia status na 'completed', tworzy wpis w praktyka i dokument_akceptacja.
    """
    from app import db
    from sqlalchemy import text
    from datetime import datetime

    try:
        # Sprawdź status
        doc_row = db.session.execute(
            text("SELECT praktyka_id, status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[1] != 'awaiting_approval':
            return False

        praktyka_id = doc_row[0]

        # Dodaj akceptację
        db.session.execute(
            text(
                "INSERT INTO dokument_akceptacja (dokument_id, akceptujacy_id, czy_zaakceptowany, zaakceptowano) VALUES (:doc_id, :akceptujacy_id, 1, :zaakceptowano)"
            ),
            {
                'doc_id': dokument_id,
                'akceptujacy_id': current_user.id,
                'zaakceptowano': datetime.now()
            }
        )

        # Zmień status dokumentu na 'completed'
        db.session.execute(
            text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
            {
                'doc_id': dokument_id,
                'status': 'completed',
                'ostatni_edytor': current_user.id
            }
        )

        # Zaktualizuj status praktyki na 'active' i aktualny etap na 1
        db.session.execute(
            text("UPDATE praktyka SET status = :status, aktualny_etap = 1 WHERE id = :praktyka_id"),
            {
                'praktyka_id': praktyka_id,
                'status': 'active'
            }
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd akceptacji załącznika 9: {e}')
        return False


def reject_attachment9(dokument_id):
    """Odrzucenie załącznika 9 przez dziekanat.
    
    Zmienia status na 'rejected', pozwala opiekunowi na edycję,
    resetuje podpis na czy_podpisano=0.
    """
    from app import db
    from sqlalchemy import text

    try:
        # Sprawdź status
        doc_row = db.session.execute(
            text("SELECT status FROM dokument WHERE id = :doc_id"),
            {'doc_id': dokument_id}
        ).fetchone()

        if not doc_row or doc_row[0] != 'awaiting_approval':
            return False

        # Zmień status dokumentu na 'rejected'
        db.session.execute(
            text("UPDATE dokument SET status = :status, ostatni_edytor = :ostatni_edytor WHERE id = :doc_id"),
            {
                'doc_id': dokument_id,
                'status': 'rejected',
                'ostatni_edytor': current_user.id
            }
        )

        # Resetuj podpis (jeśli istnieje)
        db.session.execute(
            text("UPDATE dokument_podpis SET czy_podpisany = 0, podpisano = NULL WHERE dokument_id = :doc_id"),
            {'doc_id': dokument_id}
        )

        # Pozwól opiekunowi na edycję
        db.session.execute(
            text(
                "UPDATE udostepniony_dokument SET moze_edytowac = 1 WHERE dokument_id = :doc_id AND rola_id = (SELECT id FROM role WHERE nazwa = 'opiekun_firmowy')"
            ),
            {'doc_id': dokument_id}
        )

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Błąd odrzucenia załącznika 9: {e}')
        return False


@bp.route('/formularz/zalacznik-9', methods=['GET', 'POST'])
@login_required
def zalacznik_9():
    """Formularz załącznika 9 - Oświadczenie instytucji w sprawie przyjęcia studenta."""
    from app import db
    from sqlalchemy import text
    from app.models.uzytkownik import Uzytkownik, Rola

    role = current_user.rola.nazwa
    # Pobierz dokument_id z GET lub POST
    dokument_id = request.args.get('dokument_id', type=int) or request.form.get('dokument_id', type=int)
    action_query = request.args.get('action')  # Akcja z query string (np. sign, accept, reject)
    dokument = None
    dokument_data = {}
    status = None
    czy_podpisany = False
    czy_zaakceptowany = False

    # Obsługa akcji z query string (GET requests z dashboardu)
    if action_query and dokument_id:
        if action_query == 'sign':
            if role != 'opiekun_firmowy':
                flash('Tylko opiekun firmowy może podpisać załącznik 9.', 'danger')
            elif sign_attachment9(dokument_id):
                flash('Załącznik 9 został podpisany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

        elif action_query == 'accept':
            if role != 'dziekanat':
                flash('Tylko dziekanat może zaakceptować załącznik 9.', 'danger')
            elif accept_attachment9(dokument_id):
                flash('Załącznik 9 został zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można zaakceptować tego dokumentu.', 'danger')

        elif action_query == 'reject':
            if role != 'dziekanat':
                flash('Tylko dziekanat może odrzucić załącznik 9.', 'danger')
            elif reject_attachment9(dokument_id):
                flash('Załącznik 9 został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić tego dokumentu.', 'danger')

    # Jeśli edytujemy istniejący dokument
    if dokument_id:
        doc_row = db.session.execute(
            text("SELECT id, status FROM dokument WHERE id = :doc_id AND typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_9')"),
            {'doc_id': dokument_id}
        ).fetchone()

        if doc_row:
            dokument = {'id': doc_row[0], 'status': doc_row[1]}
            status = doc_row[1]

            # Pobierz dane dokumentu
            dane = db.session.execute(
                text("SELECT klucz, wartosc FROM dane_dokumentu WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchall()
            dokument_data = {row[0]: row[1] for row in dane}

            # Sprawdź podpis
            podpis_row = db.session.execute(
                text("SELECT czy_podpisany FROM dokument_podpis WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchone()
            czy_podpisany = podpis_row[0] if podpis_row else False

            # Sprawdź akceptację
            akcept_row = db.session.execute(
                text("SELECT czy_zaakceptowany FROM dokument_akceptacja WHERE dokument_id = :doc_id"),
                {'doc_id': dokument_id}
            ).fetchone()
            czy_zaakceptowany = akcept_row[0] if akcept_row else False

            # Pobierz dodatkowe dane powiązane z dokumentem, aby poprawnie wyświetlić widok completed
            dokument_info = db.session.execute(
                text(
                    "SELECT p.student_id, s.imie, s.nazwisko, s.numer_albumu, "
                    "p.data_rozpoczecia, p.data_zakonczenia, p.opiekun_firmowy_id, "
                    "f.nazwa AS firma_nazwa, f.miasto AS firma_miasto, "
                    "f.osoba_upowazniona_imie_nazwisko, f.osoba_upowazniona_stanowisko "
                    "FROM dokument d "
                    "JOIN praktyka p ON d.praktyka_id = p.id "
                    "LEFT JOIN uzytkownik s ON p.student_id = s.id "
                    "LEFT JOIN firma f ON p.firma_id = f.id "
                    "WHERE d.id = :doc_id"
                ),
                {'doc_id': dokument_id}
            ).fetchone()

            if dokument_info:
                student_id, student_imie, student_nazwisko, student_numer, termin_od_val, termin_do_val, opiekun_firmowy_id, firma_nazwa_val, firma_miasto_val, osoba_upowazniona_imie_nazwisko, osoba_upowazniona_stanowisko = dokument_info
                dokument_data['student_id'] = student_id
                dokument_data['imie_nazwisko_studenta'] = f"{student_imie or ''} {student_nazwisko or ''}".strip()
                dokument_data['nr_albumu'] = student_numer or dokument_data.get('nr_albumu', '')
                dokument_data['termin_od'] = termin_od_val or dokument_data.get('termin_od', '')
                dokument_data['termin_do'] = termin_do_val or dokument_data.get('termin_do', '')
                dokument_data['nazwa_firmy'] = firma_nazwa_val or dokument_data.get('nazwa_firmy', '')
                dokument_data['miejscowosc'] = firma_miasto_val or dokument_data.get('miejscowosc', '')
                dokument_data['osoba_upowazniona'] = (
                    f"{osoba_upowazniona_imie_nazwisko}, {osoba_upowazniona_stanowisko}".strip(', ') 
                    if osoba_upowazniona_imie_nazwisko or osoba_upowazniona_stanowisko else dokument_data.get('osoba_upowazniona', '')
                )

                if opiekun_firmowy_id:
                    opiekun = Uzytkownik.query.get(opiekun_firmowy_id)
                    if opiekun:
                        dokument_data['imie_nazwisko_opiekuna_firmowego'] = opiekun.pelne_imie or dokument_data.get('imie_nazwisko_opiekuna_firmowego', '')
                        dokument_data['telefon_opiekuna_firmowego'] = opiekun.telefon or dokument_data.get('telefon_opiekuna_firmowego', '')
                        dokument_data['email_opiekuna_firmowego'] = opiekun.email or dokument_data.get('email_opiekuna_firmowego', '')
                        dokument_data['stanowisko_opiekuna_firmowego'] = opiekun.stanowisko or dokument_data.get('stanowisko_opiekuna_firmowego', '')

    # Obsługa POST dla różnych akcji
    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'sign' and dokument_id:
            if role != 'opiekun_firmowy':
                flash('Tylko opiekun firmowy może podpisać załącznik 9.', 'danger')
            elif sign_attachment9(dokument_id):
                flash('Załącznik 9 został podpisany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można podpisać tego dokumentu.', 'danger')

        elif action == 'accept' and dokument_id:
            if role != 'dziekanat':
                flash('Tylko dziekanat może zaakceptować załącznik 9.', 'danger')
            elif accept_attachment9(dokument_id):
                flash('Załącznik 9 został zaakceptowany.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można zaakceptować tego dokumentu.', 'danger')

        elif action == 'reject' and dokument_id:
            if role != 'dziekanat':
                flash('Tylko dziekanat może odrzucić załącznik 9.', 'danger')
            elif reject_attachment9(dokument_id):
                flash('Załącznik 9 został odrzucony.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Nie można odrzucić tego dokumentu.', 'danger')

        elif action == 'save':
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

            if save_attachment9_data(form_data):
                flash('Dane załącznika 9 zostały zapisane.', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Wystąpił problem podczas zapisu formularza.', 'danger')

        elif action == 'save_and_sign':
            if role != 'opiekun_firmowy':
                flash('Tylko opiekun firmowy może zapisać i podpisać załącznik 9.', 'danger')
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

            if save_attachment9_data(form_data):
                # Pobierz ID nowo utworzonego dokumentu
                student_id = int(form_data.get('student_id')) if form_data.get('student_id') else None
                if student_id:
                    doc_row = db.session.execute(
                        text("""
                            SELECT d.id FROM dokument d
                            JOIN praktyka p ON d.praktyka_id = p.id
                            WHERE p.student_id = :student_id
                            AND d.typ_dokumentu_id = (SELECT id FROM typ_dokumentu WHERE kod='ZAL_9')
                            ORDER BY d.id DESC LIMIT 1
                        """),
                        {'student_id': student_id}
                    ).fetchone()
                    new_doc_id = doc_row[0] if doc_row else None
                    if new_doc_id and sign_attachment9(new_doc_id):
                        flash('Załącznik 9 został zapisany i podpisany.', 'success')
                        return redirect(url_for('dashboard.index'))
            flash('Wystąpił problem podczas zapisu i podpisu formularza.', 'danger')

    # Pobranie listy aktywnych studentów posortowanych po numerze albumu
    rola_student = Rola.query.filter_by(nazwa='student').first()
    if rola_student:
        studenci_query = Uzytkownik.query.filter_by(rola_id=rola_student.id, jest_aktywny=True)

        if role == 'opiekun_firmowy':
            assigned_student_ids = [row[0] for row in db.session.execute(
                text("SELECT student_id FROM praktyka WHERE student_id IS NOT NULL")
            ).fetchall()]
            if assigned_student_ids:
                studenci_query = studenci_query.filter(~Uzytkownik.id.in_(assigned_student_ids))

        studenci = studenci_query.order_by(Uzytkownik.numer_albumu).all()
    else:
        studenci = []

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

    # Załaduj dane dokumentu jeśli go edytujemy
    prefilled = {
        'imie_nazwisko_studenta': '',
        'wybrany_student_id': None,
        'miejscowosc': dokument_data.get('miejscowosc', miasto_firmy),
        'data': dokument_data.get('data', date.today().isoformat()),
        'nazwa_firmy': nazwa_firmy,
        'termin_od': '',
        'termin_do': '',
        'nr_albumu': '',
        'imie_nazwisko_opiekuna_firmowego': current_user.pelne_imie,
        'telefon_opiekuna_firmowego': current_user.telefon or '',
        'email_opiekuna_firmowego': current_user.email or '',
        'stanowisko_opiekuna_firmowego': getattr(current_user, 'stanowisko', '') or '',
        'osoba_upowazniona': osoba_upowazniona,
    }

    # Użyj wartości zapisanych w dokumencie podczas odczytu, jeśli są obecne.
    prefilled.update({k: v for k, v in dokument_data.items() if v is not None})

    return render_template(
        'forms/zalacznik_9.html',
        role=role,
        studenci=studenci,
        dokument=dokument,
        status=status,
        czy_podpisany=czy_podpisany,
        czy_zaakceptowany=czy_zaakceptowany,
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