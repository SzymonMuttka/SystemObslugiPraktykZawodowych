from datetime import date

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user

bp = Blueprint('dashboard', __name__)


def generate_agreement_number():
    """Generuje tymczasowy numer porozumienia dla załącznika 1.

    TODO: zastąpić rzeczywistą logiką generowania numeru z bazy danych.
    """
    return 'POR-0001'


def save_attachment1_data(form_data):
    """Szkielet zapisu danych załącznika 1 do bazy danych.

    Obecnie zapisujemy tylko log w aplikacji.
    Docelowo należy utworzyć model dokumentu załącznika
i zapisać pola w odpowiednich kolumnach.
    """
    current_app.logger.debug('Zapis załącznika 1: %s', form_data)
    # TODO: w tym miejscu dodać właściwy model i wywołanie db.session.add(...)
    return True


@bp.route('/dashboard')
@login_required
def index():
    """Główna strona dashboardu po zalogowaniu."""
    return render_template(
        'dashboard/index.html',
        uzytkownik=current_user
    )


@bp.route('/formularz/zalacznik-1', methods=['GET', 'POST'])
@login_required
def zalacznik_1():
    """Formularz załącznika 1 - Porozumienie z zakładem pracy."""
    if current_user.rola.nazwa != 'dziekanat':
        flash('Tylko dziekanat może wypełniać załącznik 1.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        form_data = {
            'nr_porozumienia': request.form.get('nr_porozumienia'),
            'data_zawarcia': request.form.get('data_zawarcia'),
            'nazwa_zakladu_pracy': request.form.get('nazwa_zakladu_pracy'),
            'reprezentant_uczelni': request.form.get('reprezentant_uczelni'),
            'reprezentant_firmy': request.form.get('reprezentant_firmy'),
            'imie_nazwisko_studenta': request.form.get('imie_nazwisko_studenta'),
            'termin_od': request.form.get('termin_od'),
            'termin_do': request.form.get('termin_do'),
            'wymiar_praktyki': request.form.get('wymiar_praktyki'),
        }

        saved = save_attachment1_data(form_data)
        if saved:
            flash('Dane załącznika 1 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    nr_porozumienia = generate_agreement_number()
    data_zawarcia = date.today().isoformat()

    return render_template(
        'forms/zalacznik_1.html',
        nr_porozumienia=nr_porozumienia,
        data_zawarcia=data_zawarcia
    )


def save_attachment2_data():
    """Szkielet zapisu załącznika 2 (Program praktyki zawodowej).

    Ten dokument nie wymaga wypełniania pól — tworzy tylko dokument
    przypisany do praktyki. Obecna funkcja jedynie loguje akcję.
    """
    current_app.logger.debug('Utworzono załącznik 2 (Program praktyki zawodowej)')
    # TODO: utworzyć wpis w tabeli `dokument` i powiązania
    return True


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

    if request.method == 'POST':
        # Brak pól do zapisania — tworzymy dokument w bazie (szkielet)
        saved = save_attachment2_data()
        if saved:
            flash('Załącznik 2 został utworzony.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas tworzenia dokumentu.', 'danger')

    # GET: pokaż ekran potwierdzenia utworzenia dokumentu
    return render_template('forms/zalacznik_2.html')


def save_attachment2a_data(form_data):
    """Szkielet zapisu załącznika 2a (Program i harmonogram praktyki).

    Zapisuje otrzymane pola (tymczasowo loguje) — docelowo powinien
    utworzyć/aktualizować rekordy w tabeli `dane_dokumentu` i `dokument`.
    """
    current_app.logger.debug('Zapis załącznika 2a: %s', form_data)
    # TODO: dodać implementację zapisu do bazy
    return True


@bp.route('/formularz/zalacznik-2a', methods=['GET', 'POST'])
@login_required
def zalacznik_2a():
    """Formularz załącznika 2a - Program i harmonogram praktyki zawodowej."""
    # Dokument tworzy: dziekanat (numer indeksu)
    # Edytowalne pola przez opiekuna firmowego: przykladowe_prace, dzial_komorka, planowana_liczba_dni

    role = current_user.rola.nazwa

    # Tworzenie dokumentu tylko przez dziekanat
    if request.method == 'POST':
        if role == 'dziekanat':
            form_data = {
                'nr_indeksu': request.form.get('nr_indeksu')
            }
        elif role == 'opiekun_firmowy':
            form_data = {
                'przykladowe_prace': request.form.get('przykladowe_prace'),
                'dzial_komorka': request.form.get('dzial_komorka'),
                'planowana_liczba_dni': request.form.get('planowana_liczba_dni'),
                'data_uzgodnienia': date.today().isoformat()
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

    return render_template(
        'forms/zalacznik_2a.html',
        data_uzgodnienia=data_uzgodnienia,
        imie_nazwisko_studenta=imie_nazwisko_studenta,
        specjalnosc=specjalnosc,
        miejsce_praktyki=miejsce_praktyki,
        termin_od=termin_od,
        termin_do=termin_do
    )


def save_attachment3_data(form_data):
    """Szkielet zapisu załącznika 3 (Karta praktyki zawodowej)."""
    current_app.logger.debug('Zapis załącznika 3: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i pól
    return True


@bp.route('/formularz/zalacznik-3', methods=['GET', 'POST'])
@login_required
def zalacznik_3():
    """Formularz załącznika 3 - Karta praktyki zawodowej."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        form_data = {
            'status': 'updated_by_' + role,
            'nr_indeksu': request.form.get('nr_indeksu'),
            'data_potwierdzenia_1': request.form.get('data_potwierdzenia_1'),
            'data_potwierdzenia_2': request.form.get('data_potwierdzenia_2'),
            'uwagi': request.form.get('uwagi'),
            'miejscowosc': request.form.get('miejscowosc'),
            'data_podpisu_firmowego': request.form.get('data_podpisu_firmowego'),
            'ocena_przebiegu_1': request.form.get('ocena_przebiegu_1'),
            'data_przebiegu_1': request.form.get('data_przebiegu_1'),
            'ocena_przebiegu_2': request.form.get('ocena_przebiegu_2'),
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
        'termin_od': '',
        'termin_do': '',
        'rok_akademicki': '',
    }

    return render_template(
        'forms/zalacznik_3.html',
        role=role,
        **prefilled
    )


def save_attachment4_data(form_data):
    """Szkielet zapisu załącznika 4 (Potwierdzenie efektów uczenia się)."""
    current_app.logger.debug('Zapis załącznika 4: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i pól
    return True


@bp.route('/formularz/zalacznik-4', methods=['GET', 'POST'])
@login_required
def zalacznik_4():
    """Formularz załącznika 4 - Potwierdzenie efektów uczenia się."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_firmowy', 'opiekun_uczelniany']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'nr_indeksu': request.form.get('nr_indeksu'),
            'uzyskanie_efektu': request.form.get('uzyskanie_efektu'),
            'data_uzyskania': request.form.get('data_uzyskania'),
            'opinia_opiekuna_uczelnianego': request.form.get('opinia_opiekuna_uczelnianego'),
            'data_opinii': request.form.get('data_opinii'),
        }

        saved = save_attachment4_data(form_data)
        if saved:
            flash('Dane załącznika 4 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))

        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': '',
        'specjalnosc': '',
        'ilosc_godzin_praktyk': '',
        'nr_indeksu': '',
        'uzyskanie_efektu': '',
        'data_uzyskania': date.today().isoformat(),
        'opinia_opiekuna_uczelnianego': '',
        'data_opinii': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_4.html',
        role=role,
        **prefilled
    )


def save_attachment4a_data(form_data):
    """Szkielet zapisu załącznika 4a (Potwierdzenie uzyskania efektów)."""
    current_app.logger.debug('Zapis załącznika 4a: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i pól
    return True


@bp.route('/formularz/zalacznik-4a', methods=['GET', 'POST'])
@login_required
def zalacznik_4a():
    """Formularz załącznika 4a - Potwierdzenie uzyskania efektów uczenia się."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['dziekanat', 'czlonek_komisji']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if role == 'dziekanat':
            form_data = {
                'nr_indeksu': request.form.get('nr_indeksu'),
            }
        else:
            form_data = {
                'wynik_komisji': request.form.get('wynik_komisji'),
                'data_wyniku_komisji': request.form.get('data_wyniku_komisji'),
            }

        saved = save_attachment4a_data(form_data)
        if saved:
            flash('Dane załącznika 4a zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': '',
        'specjalnosc': '',
        'ilosc_godzin_praktyk': '',
        'nr_indeksu': '',
        'wynik_komisji': '',
        'data_wyniku_komisji': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_4a.html',
        role=role,
        **prefilled
    )


def save_attachment4b_data(form_data):
    """Szkielet zapisu załącznika 4b (Wniosek o zaliczenie efektów)."""
    current_app.logger.debug('Zapis załącznika 4b: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i pól
    return True


@bp.route('/formularz/zalacznik-4b', methods=['GET', 'POST'])
@login_required
def zalacznik_4b():
    """Formularz załącznika 4b - Wniosek o zaliczenie efektów uczenia się."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['student', 'czlonek_komisji', 'dyrektor']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if role == 'student':
            form_data = {
                'nr_indeksu': request.form.get('nr_indeksu'),
                'data_zlozenia': request.form.get('data_zlozenia'),
                'uzasadnienie': request.form.get('uzasadnienie'),
                'data_uzasadnienia': request.form.get('data_uzasadnienia'),
            }
        elif role == 'czlonek_komisji':
            form_data = {
                'opinia_komisji': request.form.get('opinia_komisji'),
                'data_opinii_komisji': request.form.get('data_opinii_komisji'),
            }
        else:
            form_data = {
                'decyzja_dyrektora': request.form.get('decyzja_dyrektora'),
                'data_decyzji_dyrektora': request.form.get('data_decyzji_dyrektora'),
            }

        saved = save_attachment4b_data(form_data)
        if saved:
            flash('Dane załącznika 4b zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': '',
        'specjalnosc': '',
        'nr_indeksu': '',
        'data_zlozenia': date.today().isoformat(),
        'uzasadnienie': '',
        'data_uzasadnienia': date.today().isoformat(),
        'opinia_komisji': '',
        'data_opinii_komisji': date.today().isoformat(),
        'decyzja_dyrektora': '',
        'data_decyzji_dyrektora': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_4b.html',
        role=role,
        **prefilled
    )


def save_attachment5_data(form_data):
    """Szkielet zapisu załącznika 5 (Kwestionariusz ankiety)."""
    current_app.logger.debug('Zapis załącznika 5: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i pól
    return True


@bp.route('/formularz/zalacznik-5', methods=['GET', 'POST'])
@login_required
def zalacznik_5():
    """Formularz załącznika 5 - Kwestionariusz ankiety."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role != 'student':
            flash('Tylko student może zapisać ankietę.', 'danger')
            return redirect(url_for('dashboard.index'))

        form_data = {
            'odpowiedz': request.form.get('odpowiedz'),
            'dodatkowe_uwagi': request.form.get('dodatkowe_uwagi'),
        }

        saved = save_attachment5_data(form_data)
        if saved:
            flash('Dane załącznika 5 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'rok_akademicki': '',
        'kierunek': '',
        'forma_studiow': '',
        'semestr': '',
        'ilosc_godzin_praktyki': '',
        'odpowiedz': '',
        'dodatkowe_uwagi': '',
    }

    return render_template(
        'forms/zalacznik_5.html',
        role=role,
        **prefilled
    )


def save_attachment6_data(form_data):
    """Szkielet zapisu załącznika 6 (Dziennik praktyki zawodowej)."""
    current_app.logger.debug('Zapis załącznika 6: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu i tabeli dziennika
    return True


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
            }
        else:
            form_data = {
                'uwagi_opiekuna_firmowego': request.form.get('uwagi_opiekuna_firmowego'),
            }

        saved = save_attachment6_data(form_data)
        if saved:
            flash('Dane załącznika 6 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'imie_nazwisko_studenta': '',
        'nr_indeksu': '',
        'specjalnosc': '',
        'rok_akademicki': '',
        'miejsce_praktyki': '',
        'data_rozp': '',
        'data_zak': '',
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
    """Szkielet zapisu załącznika 7 (Sprawozdanie z praktyki zawodowej)."""
    current_app.logger.debug('Zapis załącznika 7: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu sprawozdania
    return True


@bp.route('/formularz/zalacznik-7', methods=['GET', 'POST'])
@login_required
def zalacznik_7():
    """Formularz załącznika 7 - Sprawozdanie z praktyki zawodowej."""
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

    prefilled = {
        'nr_indeksu': '',
        'imie_nazwisko_studenta': '',
        'specjalnosc': '',
        'rok_akademicki': '',
        'miejsce_praktyki': '',
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
    """Szkielet zapisu załącznika 7a (Sprawozdanie z pracy zawodowej)."""
    current_app.logger.debug('Zapis załącznika 7a: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu sprawozdania 7a
    return True


@bp.route('/formularz/zalacznik-7a', methods=['GET', 'POST'])
@login_required
def zalacznik_7a():
    """Formularz załącznika 7a - Sprawozdanie z pracy zawodowej lub działalności gospodarczej."""
    role = current_user.rola.nazwa

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
                'data_na_koniec_studenta': request.form.get('data_na_koniec_studenta'),
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
        'nr_indeksu': '',
        'imie_nazwisko_studenta': '',
        'specjalnosc': '',
        'rok_akademicki': '',
        'miejsce_odbycia_praktyki': '',
        'charakterystyka_miejsca_pracy': '',
        'opis_i_analiza': '',
        'wiedza_umiejetnosci': '',
        'data_na_koniec_studenta': date.today().isoformat(),
        'data_na_koniec_uczelnianego': date.today().isoformat(),
    }

    return render_template(
        'forms/zalacznik_7a.html',
        role=role,
        **prefilled
    )


def save_attachment8_data(form_data):
    """Szkielet zapisu załącznika 8 (Protokół zaliczenia praktyki zawodowej)."""
    current_app.logger.debug('Zapis załącznika 8: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu załącznika 8
    return True


@bp.route('/formularz/zalacznik-8', methods=['GET', 'POST'])
@login_required
def zalacznik_8():
    """Formularz załącznika 8 - Protokół zaliczenia praktyki zawodowej."""
    role = current_user.rola.nazwa

    if request.method == 'POST':
        if role not in ['dziekanat', 'opiekun_uczelniany', 'czlonek_komisji']:
            flash('Nie masz uprawnień do zapisu tego formularza.', 'danger')
            return redirect(url_for('dashboard.index'))

        if role == 'dziekanat':
            form_data = {
                'nr_albumu': request.form.get('nr_albumu'),
            }
        elif role == 'opiekun_uczelniany':
            form_data = {
                'ocena_sprawozdania_s': request.form.get('ocena_sprawozdania_s'),
                'data_oceny_s': request.form.get('data_oceny_s'),
            }
        else:
            form_data = {
                'data_zaliczenia': request.form.get('data_zaliczenia'),
                'sklad_komisji': request.form.get('sklad_komisji'),
                'pytania': request.form.get('pytania'),
                'oceny_czastkowe': request.form.get('oceny_czastkowe'),
                'ocena_za_mini_zadania_e': request.form.get('ocena_za_mini_zadania_e'),
                'ocena_koncowa': request.form.get('ocena_koncowa'),
            }

        saved = save_attachment8_data(form_data)
        if saved:
            flash('Dane załącznika 8 zostały zapisane.', 'success')
            return redirect(url_for('dashboard.index'))
        flash('Wystąpił problem podczas zapisu formularza.', 'danger')

    prefilled = {
        'nr_indeksu': '',
        'imie_nazwisko_studenta': '',
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

    return render_template(
        'forms/zalacznik_8.html',
        role=role,
        **prefilled
    )


def save_attachment9_data(form_data):
    """Szkielet zapisu załącznika 9 (Oświadczenie instytucji w sprawie przyjęcia studenta)."""
    current_app.logger.debug('Zapis załącznika 9: %s', form_data)
    # TODO: dodać implementację zapisu do bazy dla dokumentu załącznika 9
    return True


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
        'miejscowosc': '',
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