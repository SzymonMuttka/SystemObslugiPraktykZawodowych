-- ============================================================
-- ROLE
-- ============================================================

INSERT INTO role (nazwa) VALUES
    ('student'),
    ('opiekun_uczelniany'),
    ('opiekun_firmowy'),
    ('dziekanat'),
    ('dyrektor'),
    ('czlonek_komisji');

-- ============================================================
-- FIRMY
-- ============================================================

INSERT INTO firma (nazwa, adres, miasto, osoba_upowazniona_imie_nazwisko, osoba_upowazniona_stanowisko) VALUES
    ('ABC Software Sp. z o.o.', 'ul. Informatyczna 1', 'Elbląg', 'Marek Wiśniewski', 'Prezes Zarządu'),
    ('XYZ Systems S.A.', 'ul. Programistów 15', 'Gdańsk', 'Katarzyna Lewandowska', 'Dyrektor Generalny'),
    ('DevCorp Sp. z o.o.', 'ul. Systemowa 8', 'Olsztyn', 'Tomasz Dąbrowski', 'Kierownik IT');

-- ============================================================
-- UŻYTKOWNICY
-- ============================================================

-- Studenci
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id, numer_albumu, specjalnosc, forma_studiow, rok_akademicki) VALUES
    ('Jan', 'Kowalski', 'jan.kowalski@student.ans-elblag.pl', 'hash1', 1, '123456', 'Aplikacje internetowe', 'stacjonarne', '2025/2026'),
    ('Anna', 'Nowak', 'anna.nowak@student.ans-elblag.pl', 'hash2', 1, '123457', 'Sieci komputerowe', 'stacjonarne', '2025/2026'),
    ('Piotr', 'Wiśniewski', 'piotr.wisniewski@student.ans-elblag.pl', 'hash3', 1, '123458', 'Aplikacje internetowe', 'niestacjonarne', '2025/2026');

-- Opiekunowie uczelniani
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id) VALUES
    ('Krzysztof', 'Brzeski', 'k.brzeski@ans-elblag.pl', 'hash4', 2),
    ('Maria', 'Kowalczyk', 'maria.kowalczyk@ans-elblag.pl', 'hash5', 2);

-- Opiekunowie firmowi
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id, firma_id, telefon, stanowisko) VALUES
    ('Piotr', 'Zielinski', 'p.zielinski@abcsoftware.pl', 'hash6', 3, 1, '500100200', 'Senior Developer'),
    ('Agnieszka', 'Kaminska', 'a.kaminska@xyzsystems.pl', 'hash7', 3, 2, '500100201', 'Team Leader'),
    ('Robert', 'Mazur', 'r.mazur@devcorp.pl', 'hash8', 3, 3, '500100202', 'CTO');

-- Dziekanat
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id) VALUES
    ('Ewa', 'Jabłońska', 'dziekanat@ans-elblag.pl', 'hash9', 4);

-- Dyrektor
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id) VALUES
    ('Stanisław', 'Nowicki', 's.nowicki@ans-elblag.pl', 'hash10', 5);

-- Członkowie komisji
INSERT INTO uzytkownik (imie, nazwisko, email, haslo_hash, rola_id) VALUES
    ('Tomasz', 'Adamski', 't.adamski@ans-elblag.pl', 'hash11', 6),
    ('Zofia', 'Grabowska', 'z.grabowska@ans-elblag.pl', 'hash12', 6);

-- ============================================================
-- TYPY DOKUMENTÓW
-- ============================================================

INSERT INTO typ_dokumentu (kod, nazwa, sciezka, rola_tworzaca, kolejnosc) VALUES
    ('ZAL_9',  'Oświadczenie instytucji o przyjęciu studenta',         'standard',     'opiekun_firmowy',  1),
    ('ZAL_1',  'Porozumienie w sprawie praktyk studenckich',           'standard',     'dziekanat',        2),
    ('ZAL_2',  'Program praktyki zawodowej',                           'both',         'dziekanat',        3),
    ('ZAL_2A', 'Program i harmonogram praktyki zawodowej',             'standard',     'dziekanat',        4),
    ('ZAL_3',  'Karta praktyki zawodowej',                             'standard',     'dziekanat',        5),
    ('ZAL_6',  'Dziennik praktyki zawodowej',                          'standard',     'student',          6),
    ('ZAL_4',  'Potwierdzenie uzyskania efektów uczenia się',          'standard',     'dziekanat',        7),
    ('ZAL_7',  'Sprawozdanie z praktyki zawodowej',                    'standard',     'student',          8),
    ('ZAL_8',  'Protokół zaliczenia praktyki zawodowej',               'both',         'dziekanat',        9),
    ('ZAL_5',  'Kwestionariusz ankiety',                               'both',         'student',          10),
    ('ZAL_4B', 'Wniosek o zaliczenie na podstawie zatrudnienia',       'alternative',  'student',          1),
    ('ZAL_4A', 'Potwierdzenie efektów na podstawie zatrudnienia',      'alternative',  'dziekanat',        2),
    ('ZAL_7A', 'Sprawozdanie z praktyki na podstawie zatrudnienia',    'alternative',  'student',          3);

-- ============================================================
-- PRAKTYKI
-- ============================================================

INSERT INTO praktyka (student_id, firma_id, opiekun_firmowy_id, opiekun_uczelniany_id, sciezka, status, data_rozpoczecia, data_zakonczenia, liczba_dni_roboczych, liczba_godzin, rok_akademicki) VALUES
    -- Student 1 - praktyka standardowa, ukończona
    (1, 1, 6, 4, 'standard', 'completed', '2025-07-01', '2025-12-15', 120, 960, '2025/2026'),
    -- Student 2 - praktyka standardowa, w trakcie
    (2, 2, 7, 5, 'standard', 'active',    '2025-07-01', '2025-12-15', 120, 960, '2025/2026'),
    -- Student 3 - praktyka alternatywna, w trakcie
    (3, 3, 8, 4, 'alternative', 'active', '2025-07-01', '2025-12-15', 120, 960, '2025/2026');

-- ============================================================
-- EFEKTY UCZENIA SIĘ
-- ============================================================

INSERT INTO efekt_uczenia (numer, opis) VALUES
    (1,  'Ma wiedzę na temat sposobu realizacji zadań inżynierskich dotyczących informatyki z zachowaniem standardów i norm technicznych'),
    (2,  'Zna technologie, narzędzia, metody, techniki oraz sprzęt stosowane w informatyce'),
    (3,  'Zna ekonomiczne, prawne skutki własnych działań podejmowanych w ramach praktyki oraz ograniczenia wynikające z prawa autorskiego i kodeksu pracy'),
    (4,  'Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka'),
    (5,  'Pozyskuje informacje odnośnie technologii, metod, technik, sprzętu wymaganego do realizacji powierzonego zadania'),
    (6,  'W oparciu o kontakty ze środowiskiem inżynierskim zakładu potrafi podnieść swoje kompetencje'),
    (7,  'Opracowuje dokumentację dotyczącą realizacji podejmowanych zadań w ramach praktyki'),
    (8,  'Potrafi zidentyfikować problem informatyczny występujący w zakładzie pracy'),
    (9,  'Potrafi rozwiązać rzeczywiste zadanie inżynierskie z zakresu działalności informatycznej zakładu pracy'),
    (10, 'Pracuje w zespole zajmującym się zawodowo branżą IT'),
    (11, 'Przestrzega zasad etyki zawodowej i zgodnie z tymi zasadami korzysta z wiedzy i pomocy doświadczonych kolegów'),
    (12, 'Kontaktując się z osobami spoza branży potrafi zarówno pozyskać od nich niezbędne informacje'),
    (13, 'Dostrzega w praktyce tempo deaktualizacji wiedzy informatycznej oraz skutki działalności informatyków');

-- ============================================================
-- PYTANIA ANKIETY
-- ============================================================

INSERT INTO pytanie_ankiety (numer, tresc_pytania) VALUES
    (1,  'Poznałam/poznałem zasady funkcjonowania instytucji, w której odbywałam/odbywałem praktyki zawodowe.'),
    (2,  'Poznałam/poznałem strukturę oraz regulamin organizacyjny instytucji, w której odbywałam/odbywałem praktyki zawodowe.'),
    (3,  'Praktyki zawodowe umożliwiły mi pełną realizację ramowego programu praktyk zawodowych przewidzianego w ramach mojego kierunku studiów.'),
    (4,  'Podczas praktyk zawodowych zwracano uwagę na przestrzeganie zasad etyki i tajemnicy zawodowej.'),
    (5,  'Podczas praktyk miałam/miałem możliwość praktycznego zastosowania wiedzy teoretycznej zdobytej na zajęciach.'),
    (6,  'Praktyki zawodowe przyczyniły się do pogłębienia mojej wiedzy i umiejętności zdobytych w trakcie studiów.'),
    (7,  'Mogłem liczyć na wsparcie merytoryczne Opiekuna zakładowego praktyk.'),
    (8,  'Mogłem liczyć na wsparcie merytoryczne Opiekuna uczelnianego praktyk.'),
    (9,  'Opiekun zakładowy odpowiedzialny za praktyki zawodowe w miejscu ich odbywania potrafił prawidłowo zorganizować ich przebieg.'),
    (10, 'Podczas praktyk zawodowych miałam/miałem możliwość pozyskiwania materiałów niezbędnych do przygotowania mojej pracy dyplomowej.'),
    (11, 'Praktyki zawodowe rozwinęły moje umiejętności skutecznego komunikowania się w sytuacjach zawodowych i pracy w zespole.'),
    (12, 'Praktyki zawodowe nauczyły mnie samodzielności i odpowiedzialności podczas wykonywania pracy.'),
    (13, 'Liczba godzin realizowana w ramach praktyk zawodowych jest wystarczająca.'),
    (14, 'Czy po zakończeniu praktyki zawodowej chciałaby/chciałby Pani/Pan współpracować z instytucją, w której Pani/Pan zrealizowała/zrealizował praktykę?');

-- ============================================================
-- DOKUMENTY - STUDENT 1 (praktyka ukończona, ścieżka standardowa)
-- ============================================================

INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, aktualny_etap) VALUES
    (1, 1,  6,  'completed', 3),  -- ZAL_9  - id: 1
    (1, 2,  9,  'completed', 1),  -- ZAL_1  - id: 2
    (1, 3,  9,  'completed', 1),  -- ZAL_2  - id: 3
    (1, 4,  9,  'completed', 3),  -- ZAL_2A - id: 4
    (1, 5,  9,  'completed', 4),  -- ZAL_3  - id: 5
    (1, 6,  1,  'completed', 4),  -- ZAL_6  - id: 6
    (1, 7,  9,  'completed', 2),  -- ZAL_4  - id: 7
    (1, 8,  1,  'completed', 3),  -- ZAL_7  - id: 8
    (1, 9,  9,  'completed', 5),  -- ZAL_8  - id: 9
    (1, 10, 1,  'completed', 2);  -- ZAL_5  - id: 10

-- ============================================================
-- DOKUMENTY - STUDENT 2 (praktyka w trakcie, ścieżka standardowa)
-- ============================================================

INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, aktualny_etap) VALUES
    (2, 1,  7,  'completed',    3),  -- ZAL_9  - id: 11
    (2, 2,  9,  'completed',    1),  -- ZAL_1  - id: 12
    (2, 3,  9,  'completed',    1),  -- ZAL_2  - id: 13
    (2, 4,  9,  'completed',    3),  -- ZAL_2A - id: 14
    (2, 5,  9,  'in_progress',  2),  -- ZAL_3  - id: 15
    (2, 6,  2,  'in_progress',  2);  -- ZAL_6  - id: 16

-- ============================================================
-- DOKUMENTY - STUDENT 3 (ścieżka alternatywna)
-- ============================================================

INSERT INTO dokument (praktyka_id, typ_dokumentu_id, utworzony_przez, status, aktualny_etap) VALUES
    (3, 11, 3,  'completed',    3),  -- ZAL_4B - id: 17
    (3, 12, 9,  'completed',    1),  -- ZAL_4A - id: 18
    (3, 13, 3,  'in_progress',  2);  -- ZAL_7A - id: 19

-- ============================================================
-- DANE DOKUMENTÓW
-- ============================================================

-- ZAL_9 studenta 1
INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES
    (1, 'miejscowosc',                  'Elbląg',           6),
    (1, 'nazwa_firmy',                  'ABC Software',     6),
    (1, 'data_rozpoczecia',             '2025-07-01',       6),
    (1, 'data_zakonczenia',             '2025-12-15',       6);

-- ZAL_2A studenta 1 - harmonogram
INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES
    (4, 'dzial_1',              'Programowanie aplikacji webowych',     6),
    (4, 'planowana_liczba_dni', '60',                                   6),
    (4, 'dzial_2',              'Administracja serwerami',              6),
    (4, 'planowana_liczba_dni_2', '60',                                 6);

-- ZAL_3 studenta 1
INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES
    (5, 'data_rozpoczecia',     '2025-07-01',   9),
    (5, 'data_zakonczenia',     '2025-12-15',   9),
    (5, 'uwagi',                'Brak uwag',    6);

-- ZAL_7 studenta 1
INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES
    (8, 'charakterystyka_miejsca',      'ABC Software to firma zajmująca się tworzeniem oprogramowania webowego.',   1),
    (8, 'opis_wykonywanych_prac',       'Uczestniczyłem w tworzeniu aplikacji webowych w technologii Flask.',        1),
    (8, 'wiedza_i_umiejetnosci',        'Nabyłem umiejętności pracy w zespole i tworzenia API REST.',               1);

-- ZAL_4B studenta 3
INSERT INTO dane_dokumentu (dokument_id, klucz, wartosc, wypelnione_przez) VALUES
    (17, 'uzasadnienie',    'Pracuję jako programista w DevCorp od 6 miesięcy na stanowisku Junior Developer.', 3),
    (17, 'liczba_godzin',   '960',  3);

-- ============================================================
-- WPISY DZIENNIKA - STUDENT 1 (120 wpisów, generowane pętlą)
-- ============================================================

INSERT INTO wpis_dziennika (dokument_id, numer_dnia, data_wpisu, opis_prac, numery_efektow, nadzorujacy_id, jest_podpisany, podpisano) VALUES
    (6, 1,   '2025-07-01', 'Szkolenie BHP i zapoznanie z regulaminem firmy',                    '1,4,11',   6, 1, '2025-07-01'),
    (6, 2,   '2025-07-02', 'Zapoznanie z architekturą systemu i narzędziami deweloperskimi',    '1,2,5',    6, 1, '2025-07-02'),
    (6, 3,   '2025-07-03', 'Konfiguracja środowiska programistycznego',                         '2,5',      6, 1, '2025-07-03'),
    (6, 4,   '2025-07-04', 'Implementacja modułu logowania użytkowników',                       '1,2,9',    6, 1, '2025-07-04'),
    (6, 5,   '2025-07-07', 'Testowanie modułu logowania i poprawki błędów',                     '1,7,9',    6, 1, '2025-07-07'),
    (6, 6,   '2025-07-08', 'Tworzenie dokumentacji technicznej modułu logowania',               '7,3',      6, 1, '2025-07-08'),
    (6, 7,   '2025-07-09', 'Implementacja REST API dla modułu użytkowników',                    '2,9,10',   6, 1, '2025-07-09'),
    (6, 8,   '2025-07-10', 'Code review i poprawki po uwagach zespołu',                        '10,11,7',  6, 1, '2025-07-10'),
    (6, 9,   '2025-07-11', 'Implementacja warstwy dostępu do danych',                           '2,9',      6, 1, '2025-07-11'),
    (6, 10,  '2025-07-14', 'Optymalizacja zapytań SQL',                                         '2,8,9',    6, 1, '2025-07-14'),
    (6, 11,  '2025-07-15', 'Implementacja modułu raportów',                                     '1,2,9',    6, 1, '2025-07-15'),
    (6, 12,  '2025-07-16', 'Testy jednostkowe modułu raportów',                                 '7,9',      6, 1, '2025-07-16'),
    (6, 13,  '2025-07-17', 'Przegląd kodu i refaktoryzacja',                                    '10,11',    6, 1, '2025-07-17'),
    (6, 14,  '2025-07-18', 'Implementacja interfejsu użytkownika dashboardu',                   '2,6,9',    6, 1, '2025-07-18'),
    (6, 15,  '2025-07-21', 'Integracja frontendu z backendem',                                  '2,9,10',   6, 1, '2025-07-21'),
    (6, 16,  '2025-07-22', 'Debugowanie błędów integracyjnych',                                 '8,9',      6, 1, '2025-07-22'),
    (6, 17,  '2025-07-23', 'Implementacja powiadomień email',                                   '2,9',      6, 1, '2025-07-23'),
    (6, 18,  '2025-07-24', 'Konfiguracja serwera produkcyjnego',                               '4,5,9',    6, 1, '2025-07-24'),
    (6, 19,  '2025-07-25', 'Wdrożenie aplikacji na serwer testowy',                            '1,9,10',   6, 1, '2025-07-25'),
    (6, 20,  '2025-07-28', 'Testy akceptacyjne z klientem',                                    '6,12,10',  6, 1, '2025-07-28'),
    (6, 21,  '2025-07-29', 'Poprawki po testach akceptacyjnych',                                '8,9',      6, 1, '2025-07-29'),
    (6, 22,  '2025-07-30', 'Dokumentacja wdrożeniowa',                                         '7,3',      6, 1, '2025-07-30'),
    (6, 23,  '2025-07-31', 'Spotkanie zespołu - planowanie sprintu',                           '10,11',    6, 1, '2025-07-31'),
    (6, 24,  '2025-08-01', 'Implementacja modułu eksportu danych',                             '2,9',      6, 1, '2025-08-01'),
    (6, 25,  '2025-08-04', 'Testy modułu eksportu',                                            '7,9',      6, 1, '2025-08-04'),
    (6, 26,  '2025-08-05', 'Implementacja mechanizmu cache',                                   '2,5,9',    6, 1, '2025-08-05'),
    (6, 27,  '2025-08-06', 'Analiza wydajności aplikacji',                                     '8,9,13',   6, 1, '2025-08-06'),
    (6, 28,  '2025-08-07', 'Optymalizacja wydajności',                                         '9,13',     6, 1, '2025-08-07'),
    (6, 29,  '2025-08-08', 'Implementacja logowania błędów',                                   '7,9',      6, 1, '2025-08-08'),
    (6, 30,  '2025-08-11', 'Konfiguracja monitoringu aplikacji',                               '2,5,9',    6, 1, '2025-08-11'),
    (6, 31,  '2025-08-12', 'Szkolenie wewnętrzne z nowych technologii',                       '5,11,13',  6, 1, '2025-08-12'),
    (6, 32,  '2025-08-13', 'Implementacja modułu autoryzacji JWT',                             '2,4,9',    6, 1, '2025-08-13'),
    (6, 33,  '2025-08-14', 'Testy bezpieczeństwa aplikacji',                                   '4,8,9',    6, 1, '2025-08-14'),
    (6, 34,  '2025-08-15', 'Dokumentacja API REST',                                            '7,12',     6, 1, '2025-08-15'),
    (6, 35,  '2025-08-18', 'Implementacja wyszukiwarki pełnotekstowej',                        '2,9',      6, 1, '2025-08-18'),
    (6, 36,  '2025-08-19', 'Testy wyszukiwarki',                                               '7,9',      6, 1, '2025-08-19'),
    (6, 37,  '2025-08-20', 'Refaktoryzacja kodu wyszukiwarki',                                 '1,9',      6, 1, '2025-08-20'),
    (6, 38,  '2025-08-21', 'Implementacja paginacji wyników',                                  '2,9',      6, 1, '2025-08-21'),
    (6, 39,  '2025-08-22', 'Spotkanie z klientem - prezentacja postępów',                     '6,12',     6, 1, '2025-08-22'),
    (6, 40,  '2025-08-25', 'Implementacja modułu statystyk',                                   '2,9,10',   6, 1, '2025-08-25'),
    (6, 41,  '2025-08-26', 'Testy modułu statystyk',                                           '7,9',      6, 1, '2025-08-26'),
    (6, 42,  '2025-08-27', 'Poprawki UX interfejsu statystyk',                                 '6,9',      6, 1, '2025-08-27'),
    (6, 43,  '2025-08-28', 'Code review całego projektu',                                      '1,10,11',  6, 1, '2025-08-28'),
    (6, 44,  '2025-08-29', 'Implementacja modułu zarządzania uprawnieniami',                   '2,4,9',    6, 1, '2025-08-29'),
    (6, 45,  '2025-09-01', 'Testy modułu uprawnień',                                           '4,7,9',    6, 1, '2025-09-01'),
    (6, 46,  '2025-09-02', 'Dokumentacja modułu uprawnień',                                    '7,3',      6, 1, '2025-09-02'),
    (6, 47,  '2025-09-03', 'Implementacja harmonogramu zadań (scheduler)',                     '2,9',      6, 1, '2025-09-03'),
    (6, 48,  '2025-09-04', 'Testy schedulera',                                                 '7,9',      6, 1, '2025-09-04'),
    (6, 49,  '2025-09-05', 'Analiza i naprawa błędów produkcyjnych',                           '8,9',      6, 1, '2025-09-05'),
    (6, 50,  '2025-09-08', 'Implementacja powiadomień push',                                   '2,9,13',   6, 1, '2025-09-08'),
    (6, 51,  '2025-09-09', 'Testy powiadomień push',                                           '7,9',      6, 1, '2025-09-09'),
    (6, 52,  '2025-09-10', 'Optymalizacja bazy danych',                                        '2,8,9',    6, 1, '2025-09-10'),
    (6, 53,  '2025-09-11', 'Migracja danych testowych',                                        '9,10',     6, 1, '2025-09-11'),
    (6, 54,  '2025-09-12', 'Szkolenie z obsługi systemu dla nowych pracowników',               '6,12,11',  6, 1, '2025-09-12'),
    (6, 55,  '2025-09-15', 'Implementacja modułu archiwizacji',                                '2,9',      6, 1, '2025-09-15'),
    (6, 56,  '2025-09-16', 'Testy archiwizacji',                                               '7,9',      6, 1, '2025-09-16'),
    (6, 57,  '2025-09-17', 'Implementacja kopii zapasowych',                                   '4,9',      6, 1, '2025-09-17'),
    (6, 58,  '2025-09-18', 'Dokumentacja procedur backupu',                                    '7,3',      6, 1, '2025-09-18'),
    (6, 59,  '2025-09-19', 'Konfiguracja środowiska produkcyjnego',                            '5,9',      6, 1, '2025-09-19'),
    (6, 60,  '2025-09-22', 'Implementacja mechanizmu rate limiting',                           '2,4,9',    6, 1, '2025-09-22'),
    (6, 61,  '2025-09-23', 'Testy rate limitingu',                                             '4,7,9',    6, 1, '2025-09-23'),
    (6, 62,  '2025-09-24', 'Refaktoryzacja modułów bezpieczeństwa',                            '1,4,9',    6, 1, '2025-09-24'),
    (6, 63,  '2025-09-25', 'Analiza logów systemowych',                                        '8,9,13',   6, 1, '2025-09-25'),
    (6, 64,  '2025-09-26', 'Implementacja dashboardu administracyjnego',                       '2,9',      6, 1, '2025-09-26'),
    (6, 65,  '2025-09-29', 'Testy dashboardu',                                                 '7,9',      6, 1, '2025-09-29'),
    (6, 66,  '2025-09-30', 'Spotkanie z zarządem - raport z postępów',                        '6,12,3',   6, 1, '2025-09-30'),
    (6, 67,  '2025-10-01', 'Implementacja modułu fakturowania',                                '2,3,9',    6, 1, '2025-10-01'),
    (6, 68,  '2025-10-02', 'Testy modułu fakturowania',                                        '3,7,9',    6, 1, '2025-10-02'),
    (6, 69,  '2025-10-03', 'Dokumentacja modułu fakturowania',                                 '7,3',      6, 1, '2025-10-03'),
    (6, 70,  '2025-10-06', 'Implementacja integracji z systemem płatności',                    '2,9,13',   6, 1, '2025-10-06'),
    (6, 71,  '2025-10-07', 'Testy integracji płatności',                                       '7,9',      6, 1, '2025-10-07'),
    (6, 72,  '2025-10-08', 'Poprawki bezpieczeństwa modułu płatności',                        '4,9',      6, 1, '2025-10-08'),
    (6, 73,  '2025-10-09', 'Implementacja modułu wielojęzyczności',                            '2,9',      6, 1, '2025-10-09'),
    (6, 74,  '2025-10-10', 'Tłumaczenia i testy wielojęzyczności',                            '9,12',     6, 1, '2025-10-10'),
    (6, 75,  '2025-10-13', 'Implementacja modułu import/export CSV',                           '2,9',      6, 1, '2025-10-13'),
    (6, 76,  '2025-10-14', 'Testy importu i eksportu danych',                                  '7,9',      6, 1, '2025-10-14'),
    (6, 77,  '2025-10-15', 'Analiza wymagań dla nowego modułu',                                '5,8,12',   6, 1, '2025-10-15'),
    (6, 78,  '2025-10-16', 'Projektowanie architektury nowego modułu',                         '1,5,9',    6, 1, '2025-10-16'),
    (6, 79,  '2025-10-17', 'Implementacja nowego modułu - część pierwsza',                    '2,9',      6, 1, '2025-10-17'),
    (6, 80,  '2025-10-20', 'Implementacja nowego modułu - część druga',                       '2,9',      6, 1, '2025-10-20'),
    (6, 81,  '2025-10-21', 'Testy nowego modułu',                                              '7,9',      6, 1, '2025-10-21'),
    (6, 82,  '2025-10-22', 'Code review nowego modułu',                                        '1,10,11',  6, 1, '2025-10-22'),
    (6, 83,  '2025-10-23', 'Dokumentacja nowego modułu',                                       '7,3',      6, 1, '2025-10-23'),
    (6, 84,  '2025-10-24', 'Wdrożenie nowego modułu na serwer testowy',                       '9,10',     6, 1, '2025-10-24'),
    (6, 85,  '2025-10-27', 'Testy akceptacyjne nowego modułu',                                 '6,9,12',   6, 1, '2025-10-27'),
    (6, 86,  '2025-10-28', 'Poprawki po testach akceptacyjnych',                               '8,9',      6, 1, '2025-10-28'),
    (6, 87,  '2025-10-29', 'Finalne wdrożenie nowego modułu',                                  '9,10',     6, 1, '2025-10-29'),
    (6, 88,  '2025-10-30', 'Analiza wydajności po wdrożeniu',                                  '8,9,13',   6, 1, '2025-10-30'),
    (6, 89,  '2025-10-31', 'Implementacja poprawek wydajnościowych',                           '9,13',     6, 1, '2025-10-31'),
    (6, 90,  '2025-11-03', 'Szkolenie nowych członków zespołu',                                '6,11,12',  6, 1, '2025-11-03'),
    (6, 91,  '2025-11-04', 'Implementacja modułu powiadomień SMS',                             '2,9',      6, 1, '2025-11-04'),
    (6, 92,  '2025-11-05', 'Testy powiadomień SMS',                                            '7,9',      6, 1, '2025-11-05'),
    (6, 93,  '2025-11-06', 'Integracja z zewnętrznym API',                                     '2,5,9',    6, 1, '2025-11-06'),
    (6, 94,  '2025-11-07', 'Testy integracji z zewnętrznym API',                               '7,9',      6, 1, '2025-11-07'),
    (6, 95,  '2025-11-10', 'Analiza bezpieczeństwa całego systemu',                            '4,8,9',    6, 1, '2025-11-10'),
    (6, 96,  '2025-11-12', 'Implementacja poprawek bezpieczeństwa',                            '4,9',      6, 1, '2025-11-12'),
    (6, 97,  '2025-11-13', 'Testy penetracyjne',                                               '4,8,9',    6, 1, '2025-11-13'),
    (6, 98,  '2025-11-14', 'Dokumentacja bezpieczeństwa systemu',                              '4,7,3',    6, 1, '2025-11-14'),
    (6, 99,  '2025-11-17', 'Implementacja modułu audytu',                                      '2,4,9',    6, 1, '2025-11-17'),
    (6, 100, '2025-11-18', 'Testy modułu audytu',                                              '7,9',      6, 1, '2025-11-18'),
    (6, 101, '2025-11-19', 'Finalizacja dokumentacji technicznej',                             '7,3',      6, 1, '2025-11-19'),
    (6, 102, '2025-11-20', 'Przygotowanie prezentacji końcowej projektu',                      '6,12',     6, 1, '2025-11-20'),
    (6, 103, '2025-11-21', 'Prezentacja projektu dla zarządu',                                 '6,12,11',  6, 1, '2025-11-21'),
    (6, 104, '2025-11-24', 'Poprawki po prezentacji',                                          '8,9',      6, 1, '2025-11-24'),
    (6, 105, '2025-11-25', 'Finalne testy regresji',                                           '1,7,9',    6, 1, '2025-11-25'),
    (6, 106, '2025-11-26', 'Wdrożenie produkcyjne systemu',                                    '9,10',     6, 1, '2025-11-26'),
    (6, 107, '2025-11-27', 'Monitoring po wdrożeniu produkcyjnym',                             '8,9,13',   6, 1, '2025-11-27'),
    (6, 108, '2025-11-28', 'Szkolenie użytkowników końcowych',                                 '6,11,12',  6, 1, '2025-11-28'),
    (6, 109, '2025-12-01', 'Wsparcie techniczne po wdrożeniu',                                 '8,9,12',   6, 1, '2025-12-01'),
    (6, 110, '2025-12-02', 'Analiza zgłoszeń od użytkowników',                                 '8,12,13',  6, 1, '2025-12-02'),
    (6, 111, '2025-12-03', 'Implementacja poprawek zgłoszonych przez użytkowników',            '8,9',      6, 1, '2025-12-03'),
    (6, 112, '2025-12-04', 'Testy poprawek',                                                   '7,9',      6, 1, '2025-12-04'),
    (6, 113, '2025-12-05', 'Aktualizacja dokumentacji użytkownika',                            '7,12',     6, 1, '2025-12-05'),
    (6, 114, '2025-12-08', 'Planowanie rozwoju systemu w przyszłości',                         '5,13',     6, 1, '2025-12-08'),
    (6, 115, '2025-12-09', 'Przygotowanie raportu końcowego z praktyki',                       '7,3',      6, 1, '2025-12-09'),
    (6, 116, '2025-12-10', 'Konsultacje z opiekunem uczelnianym',                              '6,11',     6, 1, '2025-12-10'),
    (6, 117, '2025-12-11', 'Finalne porządkowanie repozytorium kodu',                          '1,7',      6, 1, '2025-12-11'),
    (6, 118, '2025-12-12', 'Przekazanie dokumentacji następcy',                                '7,12',     6, 1, '2025-12-12'),
    (6, 119, '2025-12-15', 'Podsumowanie praktyki z opiekunem firmowym',                       '6,11,13',  6, 1, '2025-12-15'),
    (6, 120, '2025-12-15', 'Ostateczne zakończenie praktyki i odbiór dokumentów',              '3,11,13',  6, 1, '2025-12-15');

-- ============================================================
-- EFEKTY UCZENIA SIĘ - STUDENT 1 (ZAL_4, wszystkie 13 efektów)
-- ============================================================

INSERT INTO efekt_uczenia_dokumentu (dokument_id, efekt_id, status, ocenione_przez, oceniono) VALUES
    (7, 1,  'achieved',     6, '2025-12-15'),
    (7, 2,  'achieved',     6, '2025-12-15'),
    (7, 3,  'achieved',     6, '2025-12-15'),
    (7, 4,  'achieved',     6, '2025-12-15'),
    (7, 5,  'achieved',     6, '2025-12-15'),
    (7, 6,  'achieved',     6, '2025-12-15'),
    (7, 7,  'achieved',     6, '2025-12-15'),
    (7, 8,  'achieved',     6, '2025-12-15'),
    (7, 9,  'achieved',     6, '2025-12-15'),
    (7, 10, 'achieved',     6, '2025-12-15'),
    (7, 11, 'achieved',     6, '2025-12-15'),
    (7, 12, 'achieved',     6, '2025-12-15'),
    (7, 13, 'achieved',     6, '2025-12-15');

-- ============================================================
-- EFEKTY UCZENIA SIĘ - STUDENT 3 (ZAL_4A, ścieżka alternatywna)
-- ============================================================

INSERT INTO efekt_uczenia_dokumentu (dokument_id, efekt_id, status, brakujace_elementy, ocenione_przez, oceniono) VALUES
    (18, 1,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 2,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 3,  'partial',     'Brak znajomości prawa autorskiego',    9, '2025-10-01'),
    (18, 4,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 5,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 6,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 7,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 8,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 9,  'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 10, 'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 11, 'achieved',    NULL,                                   9, '2025-10-01'),
    (18, 12, 'partial',     'Brak kontaktu z klientami zewnętrznymi', 9, '2025-10-01'),
    (18, 13, 'achieved',    NULL,                                   9, '2025-10-01');

-- ============================================================
-- OCENY - STUDENT 1 (ZAL_3 i ZAL_8)
-- ============================================================

INSERT INTO ocena_dokumentu (dokument_id, typ_oceny, wartosc_oceny, ocenione_przez, oceniono) VALUES
    -- ZAL_3
    (5, 'parametric_company',       '5',                            6,  '2025-12-15'),
    (5, 'descriptive_company',      'Student wykazał się bardzo dobrą znajomością technologii webowych i pracował samodzielnie.', 6, '2025-12-15'),
    (5, 'parametric_university',    '5',                            4,  '2025-12-16'),
    (5, 'descriptive_university',   'Student zrealizował wszystkie założone efekty kształcenia.',  4,  '2025-12-16'),
    (5, 'report',                   '4',                            4,  '2025-12-16'),
    -- ZAL_8
    (9, 'U',    '5',    4,  '2025-12-17'),
    (9, 'Z',    '5',    6,  '2025-12-17'),
    (9, 'S',    '4',    4,  '2025-12-17'),
    (9, 'E',    '5',    11, '2025-12-17'),
    (9, 'K',    '5',    11, '2025-12-17');

-- ============================================================
-- PYTANIA KOMISJI - STUDENT 1 (ZAL_8, tabela pytanie_komisji)
-- ============================================================

INSERT INTO pytanie_komisji (dokument_id, numer_pytania, tresc_pytania, czlonek_id, wartosc_oceny) VALUES
    (9, 1, 'Opisz architekturę systemu który tworzyłeś podczas praktyki',       11, 5),
    (9, 1, 'Opisz architekturę systemu który tworzyłeś podczas praktyki',       12, 5),
    (9, 2, 'Jakie technologie i narzędzia były stosowane w firmie?',            11, 5),
    (9, 2, 'Jakie technologie i narzędzia były stosowane w firmie?',            12, 4),
    (9, 3, 'Jak radziłeś sobie z problemami napotykanymi podczas praktyki?',    11, 5),
    (9, 3, 'Jak radziłeś sobie z problemami napotykanymi podczas praktyki?',    12, 5);

-- ============================================================
-- SKŁAD KOMISJI - STUDENT 1 (ZAL_8)
-- ============================================================

INSERT INTO czlonek_komisji (dokument_id, uzytkownik_id, rola_w_komisji) VALUES
    (9, 10, 'przewodniczacy'),
    (9, 4,  'opiekun_uczelniany'),
    (9, 11, 'czlonek'),
    (9, 12, 'czlonek');

-- ============================================================
-- PODPISY
-- ============================================================

-- ZAL_9 studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (1, 6,  3, 1, 1, 1, '2025-06-15');

-- ZAL_1 studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (2, 10, 5, 1, 1, 1, '2025-06-20'),
    (2, 6,  3, 1, 2, 1, '2025-06-20');

-- ZAL_2 studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (3, 10, 5, 1, 1, 1, '2025-06-20'),
    (3, 6,  3, 1, 2, 1, '2025-06-20');

-- ZAL_2A studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (4, 6,  3, 1, 1, 1, '2025-06-22'),
    (4, 4,  2, 1, 2, 1, '2025-06-22'),
    (4, 1,  1, 1, 3, 1, '2025-06-22');

-- ZAL_3 studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (5, 10, 5, 1, 1, 1, '2025-06-25'),
    (5, 6,  3, 2, 1, 1, '2025-07-01'),
    (5, 6,  3, 3, 1, 1, '2025-12-15'),
    (5, 6,  3, 4, 1, 1, '2025-12-15'),
    (5, 4,  2, 4, 2, 1, '2025-12-16');

-- ZAL_8 studenta 1
INSERT INTO podpis_dokumentu (dokument_id, uzytkownik_id, rola_id, etap, kolejnosc_podpisu, jest_podpisany, podpisano) VALUES
    (9, 10, 5, 1, 1, 1, '2025-12-17'),
    (9, 11, 6, 1, 2, 1, '2025-12-17'),
    (9, 12, 6, 1, 3, 1, '2025-12-17');

-- ============================================================
-- DOSTĘP DO DOKUMENTÓW
-- ============================================================

-- Student 1 - dostęp do swoich dokumentów
INSERT INTO dostep_do_dokumentu (dokument_id, uzytkownik_id) VALUES
    (1,  1), (2,  1), (3,  1), (4,  1), (5,  1),
    (6,  1), (7,  1), (8,  1), (9,  1), (10, 1);

-- Opiekun firmowy studenta 1
INSERT INTO dostep_do_dokumentu (dokument_id, uzytkownik_id) VALUES
    (1,  6), (2,  6), (3,  6), (4,  6), (5,  6),
    (6,  6), (7,  6), (9,  6);

-- Opiekun uczelniany studenta 1
INSERT INTO dostep_do_dokumentu (dokument_id, uzytkownik_id) VALUES
    (2,  4), (3,  4), (4,  4), (5,  4),
    (7,  4), (8,  4), (9,  4);

-- Dziekanat - dostęp do wszystkich dokumentów
INSERT INTO dostep_do_dokumentu (dokument_id, uzytkownik_id) VALUES
    (1,  9), (2,  9), (3,  9), (4,  9), (5,  9),
    (6,  9), (7,  9), (8,  9), (9,  9), (10, 9),
    (11, 9), (12, 9), (13, 9), (14, 9), (15, 9),
    (16, 9), (17, 9), (18, 9), (19, 9);

-- ============================================================
-- HISTORIA DOKUMENTÓW (wybrane zdarzenia)
-- ============================================================

INSERT INTO historia_dokumentu (dokument_id, uzytkownik_id, akcja, stary_status, nowy_status, stary_etap, nowy_etap, komentarz) VALUES
    (1,  6,  'created',         NULL,           'draft',        NULL, 1, NULL),
    (1,  6,  'signed',          'draft',        'completed',    1,    1, NULL),
    (2,  9,  'created',         NULL,           'draft',        NULL, 1, NULL),
    (2,  10, 'signed',          'draft',        'completed',    1,    1, NULL),
    (5,  9,  'created',         NULL,           'draft',        NULL, 1, NULL),
    (5,  10, 'signed',          'draft',        'in_progress',  1,    2, NULL),
    (5,  6,  'signed',          'in_progress',  'in_progress',  2,    3, NULL),
    (6,  1,  'created',         NULL,           'draft',        NULL, 1, NULL),
    (6,  1,  'stage_changed',   'draft',        'in_progress',  1,    2, NULL),
    (7,  4,  'returned',        'in_progress',  'returned',     1,    1, 'Proszę uzupełnić opisy prac dla efektów 3 i 12'),
    (7,  6,  'edited',          'returned',     'in_progress',  1,    1, NULL),
    (7,  4,  'completed',       'in_progress',  'completed',    1,    2, NULL),
    (8,  4,  'returned',        'in_progress',  'returned',     2,    2, 'Sekcja samooceny wymaga rozszerzenia'),
    (8,  1,  'edited',          'returned',     'in_progress',  2,    2, NULL),
    (9,  9,  'created',         NULL,           'draft',        NULL, 1, NULL),
    (9,  11, 'stage_changed',   'in_progress',  'completed',    4,    5, NULL);

-- ============================================================
-- ANKIETA - STUDENT 1 (ZAL_5, anonimowa)
-- ============================================================

INSERT INTO odpowiedz_ankiety (dokument_id, pytanie_id, odpowiedz) VALUES
    (10, 1,  'zdecydowanie_tak'),
    (10, 2,  'zdecydowanie_tak'),
    (10, 3,  'zdecydowanie_tak'),
    (10, 4,  'zdecydowanie_tak'),
    (10, 5,  'zdecydowanie_tak'),
    (10, 6,  'zdecydowanie_tak'),
    (10, 7,  'zdecydowanie_tak'),
    (10, 8,  'raczej_tak'),
    (10, 9,  'zdecydowanie_tak'),
    (10, 10, 'raczej_tak'),
    (10, 11, 'zdecydowanie_tak'),
    (10, 12, 'zdecydowanie_tak'),
    (10, 13, 'zdecydowanie_tak'),
    (10, 14, 'zdecydowanie_tak');

INSERT INTO komentarz_ankiety (dokument_id, tresc) VALUES
    (10, 'Praktyka była bardzo dobrze zorganizowana. Polecam tę firmę innym studentom.');