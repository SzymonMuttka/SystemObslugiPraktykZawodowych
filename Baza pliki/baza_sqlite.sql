-- ============================================================
-- UŻYTKOWNICY I ROLE
-- ============================================================

CREATE TABLE role (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL UNIQUE
    -- 'student', 'opiekun_uczelniany', 'opiekun_firmowy',
    -- 'dziekanat', 'dyrektor', 'czlonek_komisji'
);

CREATE TABLE firma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    adres TEXT NOT NULL,
    miasto TEXT NOT NULL,
    osoba_upowazniona_imie_nazwisko TEXT,
    osoba_upowazniona_stanowisko TEXT,
    jest_aktywna INTEGER NOT NULL DEFAULT 1,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE uzytkownik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imie TEXT NOT NULL,
    nazwisko TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    haslo_hash TEXT NOT NULL,
    rola_id INTEGER NOT NULL REFERENCES role(id),
    numer_albumu TEXT UNIQUE,
    specjalnosc TEXT,
    forma_studiow TEXT,
    rok_akademicki TEXT,
    telefon TEXT,
    stanowisko TEXT,
    firma_id INTEGER REFERENCES firma(id),
    jest_aktywny INTEGER NOT NULL DEFAULT 1,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now')),
	auth_provider TEXT DEFAULT 'microsoft',
	external_id TEXT UNIQUE,
	wymaga_zatwierdzenia INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- PRAKTYKI
-- ============================================================

CREATE TABLE praktyka (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    firma_id INTEGER REFERENCES firma(id),
    opiekun_firmowy_id INTEGER REFERENCES uzytkownik(id),
    opiekun_uczelniany_id INTEGER REFERENCES uzytkownik(id),
    sciezka TEXT NOT NULL,
    -- 'standard' / 'alternative'
    status TEXT NOT NULL DEFAULT 'pending',
    -- 'pending', 'active', 'completed', 'rejected'
	aktualny_etap INTEGER NOT NULL DEFAULT 0,
    data_rozpoczecia TEXT,
    data_zakonczenia TEXT,
    liczba_dni_roboczych INTEGER DEFAULT 120,
    liczba_godzin INTEGER DEFAULT 960,
    rok_akademicki TEXT,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- DOKUMENTY
-- ============================================================

CREATE TABLE typ_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kod TEXT NOT NULL UNIQUE,
    -- 'ZAL_1', 'ZAL_2', 'ZAL_2A', 'ZAL_3', 'ZAL_4',
    -- 'ZAL_4A', 'ZAL_4B', 'ZAL_5', 'ZAL_6', 'ZAL_7',
    -- 'ZAL_7A', 'ZAL_8', 'ZAL_9'
    nazwa TEXT NOT NULL,
    opis TEXT,
    sciezka TEXT NOT NULL DEFAULT 'both',
    -- 'standard', 'alternative', 'both'
    kolejnosc INTEGER NOT NULL
);

CREATE TABLE dokument (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    praktyka_id INTEGER NOT NULL REFERENCES praktyka(id),
    typ_dokumentu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    utworzony_przez INTEGER NOT NULL REFERENCES uzytkownik(id),
    status TEXT NOT NULL DEFAULT 'draft',
    -- 'draft', 'in_progress', 'awaiting_signature', 'awaiting_approval', 'completed', 'rejected'
	-- 'doc3_step1', 'doc3_step2', 'doc3_step3', 'doc3_step4'
	ostatni_edytor TEXT,
    jest_usuniety INTEGER NOT NULL DEFAULT 0,
    jest_anonimowy INTEGER NOT NULL DEFAULT 0,
    -- tylko ZAL_5
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE udostepniony_dokument (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	udostepniajacy INTEGER NOT NULL REFERENCES uzytkownik(id),
	dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	adresat INTEGER REFERENCES uzytkownik(id),
	rola_id INTEGER NOT NULL REFERENCES rola(id),
	moze_podgladac INTEGER NOT NULL,
	moze_edytowac INTEGER NOT NULL,
	moze_podpisac INTEGER NOT NULL,
	moze_akceptowac INTEGER NOT NULL
);

CREATE TABLE dokument_podpis (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	podpisujacy_id INTEGER REFERENCES uzytkownik(id),
	czy_podpisany INTEGER NOT NULL,
	podpisano TEXT DEFAULT (datetime('now'))
);

CREATE TABLE dokument_akceptacja (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	akceptujacy_id INTEGER REFERENCES uzytkownik(id),
	czy_zaakceptowany INTEGER NOT NULL,
	zaakceptowano TEXT DEFAULT (datetime('now'))
);

CREATE TABLE dokument_pobranie (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	pobierajacy_id INTEGER REFERENCES uzytkownik(id),
	data_pobrania TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- DANE DOKUMENTÓW
-- (wartości pól specyficznych dla danego dokumentu
--  nieobsługiwanych przez dedykowane tabele)
-- ============================================================

CREATE TABLE dane_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    klucz TEXT NOT NULL,
    -- np. 'uzasadnienie', 'charakterystyka_miejsca',
    -- 'opis_wykonywanych_prac', 'wiedza_i_umiejetnosci'
    wartosc TEXT,
    wypelnione_przez INTEGER REFERENCES uzytkownik(id),
    wypelniono TEXT DEFAULT (datetime('now')),
    UNIQUE(dokument_id, klucz)
);

-- ============================================================
-- WPISY DZIENNIKA (ZAL_6)
-- ============================================================

CREATE TABLE wpis_dziennika (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    numer_dnia INTEGER NOT NULL,
    data_wpisu TEXT NOT NULL,
    opis_prac TEXT NOT NULL,
    uwagi_opiekuna TEXT,
    jest_podpisany INTEGER NOT NULL DEFAULT 0,
    podpisano TEXT,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dokument_id, numer_dnia)
);

CREATE TABLE wpis_efekt (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	numer_dnia INTEGER NOT NULL,
	nr_efektu INTEGER NOT NULL,
	UNIQUE(dokument_id, numer_dnia, nr_efektu)
);

-- ============================================================
-- EFEKTY UCZENIA SIĘ (ZAL_4 i ZAL_4A)
-- ============================================================

CREATE TABLE efekt_uczenia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numer INTEGER NOT NULL UNIQUE,
    opis TEXT NOT NULL
);

CREATE TABLE efekt_uczenia_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    efekt_id INTEGER NOT NULL REFERENCES efekt_uczenia(id),
    status TEXT,
    -- ZAL_4: 'achieved' / 'not_achieved'
    -- ZAL_4A: 'achieved' / 'partial' / 'not_achieved'
    ocenione_przez INTEGER REFERENCES uzytkownik(id),
    oceniono TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dokument_id, efekt_id)
);

-- ============================================================
-- PROGRAM I HARMONOGRAM PRAKTYKI (ZAL_2A)
-- ============================================================

CREATE TABLE program_harmonogram_praktyki (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	dokument_id INTEGER NOT NULL REFERENCES dokument(id),
	numer INTEGER NOT NULL,
	ppz_dzial TEXT NOT NULL,
	hpz_dzial TEXT,
	hpz_dni INTEGER,
	UNIQUE(dokument_id, numer)
);

-- ============================================================
-- PYTANIA KOMISJI (ZAL_8)
-- ============================================================

CREATE TABLE pytanie_komisji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    numer_pytania INTEGER NOT NULL,
    -- 1, 2, 3
    tresc_pytania TEXT NOT NULL,
    wartosc_oceny INTEGER NOT NULL,
    -- ocena 2-5
    oceniono TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dokument_id, numer_pytania)
);

-- ============================================================
-- ANKIETA (ZAL_5)
-- ============================================================

CREATE TABLE pytanie_ankiety (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numer INTEGER NOT NULL UNIQUE,
    tresc_pytania TEXT NOT NULL
);

CREATE TABLE odpowiedz_ankiety (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pytanie_id INTEGER NOT NULL REFERENCES pytanie_ankiety(id),
    odpowiedz TEXT NOT NULL,
    -- 'zdecydowanie_tak', 'raczej_tak', 'trudno_powiedziec',
    -- 'raczej_nie', 'zdecydowanie_nie'
    -- brak uzytkownik_id - anonimowość
);

CREATE TABLE ankieta_dane (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	uwagi TEXT,
	rok_akademicki TEXT,
	specjalnosc TEXT,
	forma_studiow TEXT,
	semestr INTEGER,
	liczba_godzin INTEGER
);

-- ============================================================
-- INDEKSY
-- ============================================================

CREATE INDEX idx_dokument_praktyka ON dokument(praktyka_id);
CREATE INDEX idx_dokument_typ ON dokument(typ_dokumentu_id);
CREATE INDEX idx_dokument_status ON dokument(status);
CREATE INDEX idx_wpis_dziennika_dokument ON wpis_dziennika(dokument_id);
CREATE INDEX idx_dostep_uzytkownik ON dostep_do_dokumentu(uzytkownik_id);
CREATE INDEX idx_praktyka_student ON praktyka(student_id);
CREATE INDEX idx_praktyka_firma ON praktyka(firma_id);
CREATE INDEX idx_uzytkownik_rola ON uzytkownik(rola_id);
CREATE INDEX idx_uzytkownik_firma ON uzytkownik(firma_id);