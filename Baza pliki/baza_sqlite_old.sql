-- ============================================================
-- UŻYTKOWNICY I ROLE
-- ============================================================

CREATE TABLE role (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL UNIQUE
    -- 'student', 'opiekun_uczelniany', 'opiekun_firmowy',
    -- 'dziekanat', 'dyrektor', 'czlonek_komisji'
);

CREATE TABLE uzytkownik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imie TEXT NOT NULL,
    nazwisko TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    haslo_hash TEXT NOT NULL,
    rola_id INTEGER NOT NULL REFERENCES role(id),
    numer_albumu TEXT UNIQUE,         -- tylko student
    specjalnosc TEXT,                 -- tylko student
    forma_studiow TEXT,               -- tylko student: 'stacjonarne' / 'niestacjonarne'
    rok_akademicki TEXT,              -- tylko student: np. '2024/2025'
    telefon TEXT,                     -- tylko opiekun_firmowy
    stanowisko TEXT,                  -- tylko opiekun_firmowy
    firma_id INTEGER REFERENCES firma(id), -- tylko opiekun_firmowy
    jest_aktywny INTEGER NOT NULL DEFAULT 1,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- FIRMY
-- ============================================================

CREATE TABLE firma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    adres TEXT NOT NULL,
    miasto TEXT NOT NULL,
    osoba_upowazzona_imie_nazwisko TEXT,
    osoba_upowazzona_stanowisko TEXT,
    jest_aktywna INTEGER NOT NULL DEFAULT 1,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- PRAKTYKI
-- ============================================================

CREATE TABLE praktyka (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    firma_id INTEGER NOT NULL REFERENCES firma(id),
    opiekun_firmowy_id INTEGER REFERENCES uzytkownik(id),
    opiekun_uczelniany_id INTEGER REFERENCES uzytkownik(id),
    sciezka TEXT NOT NULL,            -- 'standard' / 'alternative'
    status TEXT NOT NULL DEFAULT 'pending',
    -- 'pending', 'active', 'completed', 'rejected'
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
    rola_tworzaca TEXT NOT NULL,
    kolejnosc INTEGER NOT NULL
);

CREATE TABLE dokument (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    praktyka_id INTEGER NOT NULL REFERENCES praktyka(id),
    typ_dokumentu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    utworzony_przez INTEGER NOT NULL REFERENCES uzytkownik(id),
    status TEXT NOT NULL DEFAULT 'draft',
    -- 'draft', 'in_progress', 'awaiting_signature',
    -- 'awaiting_review', 'returned', 'completed', 'archived'
    aktualny_etap INTEGER NOT NULL DEFAULT 1,
    jest_usuniety INTEGER NOT NULL DEFAULT 0,
    jest_anonimowy INTEGER NOT NULL DEFAULT 0, -- tylko ZAL_5
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- ZALEŻNOŚCI MIĘDZY DOKUMENTAMI
-- ============================================================

CREATE TABLE zaleznosc_dokumentow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ_dokumentu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    wymaga_typu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    wymagany_status TEXT NOT NULL DEFAULT 'completed'
    -- 'created', 'completed'
);

-- ============================================================
-- UPRAWNIENIA DO DOKUMENTÓW
-- ============================================================

CREATE TABLE uprawnienie_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ_dokumentu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    rola_id INTEGER NOT NULL REFERENCES role(id),
    moze_tworzyc INTEGER NOT NULL DEFAULT 0,
    moze_edytowac INTEGER NOT NULL DEFAULT 0,
    moze_przegladac INTEGER NOT NULL DEFAULT 0,
    moze_podpisywac INTEGER NOT NULL DEFAULT 0,
    moze_pobierac INTEGER NOT NULL DEFAULT 0,
    moze_usuwac INTEGER NOT NULL DEFAULT 0,
    moze_odsylac INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- DOSTĘP UŻYTKOWNIKA DO KONKRETNEGO DOKUMENTU
-- ============================================================

CREATE TABLE dostep_do_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    uzytkownik_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    moze_edytowac INTEGER NOT NULL DEFAULT 0,
    moze_przegladac INTEGER NOT NULL DEFAULT 0,
    moze_podpisywac INTEGER NOT NULL DEFAULT 0,
    moze_pobierac INTEGER NOT NULL DEFAULT 0,
    przyznano TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dokument_id, uzytkownik_id)
);

-- ============================================================
-- POLA DOKUMENTÓW
-- ============================================================

CREATE TABLE pole_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    typ_dokumentu_id INTEGER NOT NULL REFERENCES typ_dokumentu(id),
    klucz_pola TEXT NOT NULL,
    etykieta TEXT NOT NULL,
    typ_pola TEXT NOT NULL,
    -- 'text', 'date', 'select', 'checkbox',
    -- 'textarea', 'number', 'signature'
    jest_prefillowane INTEGER NOT NULL DEFAULT 0,
    zrodlo_prefilla TEXT,
    -- 'konto_studenta', 'zal_1', 'zal_2a' itd.
    wypelniane_przez_role TEXT,
    jest_wymagane INTEGER NOT NULL DEFAULT 1,
    etap INTEGER NOT NULL DEFAULT 1,
    kolejnosc INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE wartosc_pola_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    pole_id INTEGER NOT NULL REFERENCES pole_dokumentu(id),
    wartosc TEXT,
    wypelnione_przez INTEGER REFERENCES uzytkownik(id),
    wypelniono TEXT DEFAULT (datetime('now')),
    UNIQUE(dokument_id, pole_id)
);

-- ============================================================
-- PODPISY
-- ============================================================

CREATE TABLE podpis_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    uzytkownik_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    rola_id INTEGER NOT NULL REFERENCES role(id),
    etap INTEGER NOT NULL,
    kolejnosc_podpisu INTEGER NOT NULL,
    podpisano TEXT DEFAULT (datetime('now')),
    jest_podpisany INTEGER NOT NULL DEFAULT 0,
    UNIQUE(dokument_id, uzytkownik_id, etap)
);

-- ============================================================
-- HISTORIA DOKUMENTU
-- ============================================================

CREATE TABLE historia_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    uzytkownik_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    akcja TEXT NOT NULL,
    -- 'created', 'edited', 'signed', 'returned',
    -- 'stage_changed', 'completed', 'archived', 'deleted'
    stary_status TEXT,
    nowy_status TEXT,
    stary_etap INTEGER,
    nowy_etap INTEGER,
    komentarz TEXT,
    utworzono TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- PLIKI
-- ============================================================

CREATE TABLE plik_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    typ_pliku TEXT NOT NULL,          -- 'docx' / 'pdf'
    sciezka_pliku TEXT NOT NULL,
    rozmiar_pliku INTEGER,
    wygenerowano_przez INTEGER REFERENCES uzytkownik(id),
    wygenerowano TEXT NOT NULL DEFAULT (datetime('now')),
    jest_aktualny INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- ZAŁĄCZNIKI DO DOKUMENTÓW
-- ============================================================

CREATE TABLE zalacznik_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    przeslany_przez INTEGER NOT NULL REFERENCES uzytkownik(id),
    nazwa_pliku TEXT NOT NULL,
    sciezka_pliku TEXT NOT NULL,
    rozmiar_pliku INTEGER,
    opis TEXT,
    przeslano TEXT NOT NULL DEFAULT (datetime('now')),
    jest_usuniety INTEGER NOT NULL DEFAULT 0
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
    numery_efektow TEXT NOT NULL,
    nadzorujacy_id INTEGER REFERENCES uzytkownik(id),
    jest_podpisany INTEGER NOT NULL DEFAULT 0,
    podpisano TEXT,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    zaktualizowano TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dokument_id, numer_dnia)
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
    brakujace_elementy TEXT,          -- tylko ZAL_4A przy 'partial'
    ocenione_przez INTEGER REFERENCES uzytkownik(id),
    oceniono TEXT,
    UNIQUE(dokument_id, efekt_id)
);

-- ============================================================
-- OCENY (ZAL_3 i ZAL_8)
-- ============================================================

CREATE TABLE ocena_dokumentu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    typ_oceny TEXT NOT NULL,
    -- ZAL_3: 'parametric_company', 'descriptive_company',
    --        'parametric_university', 'descriptive_university',
    --        'report'
    -- ZAL_8: 'E', 'S', 'U', 'Z', 'K'
    wartosc_oceny TEXT,
    ocenione_przez INTEGER REFERENCES uzytkownik(id),
    oceniono TEXT,
    UNIQUE(dokument_id, typ_oceny)
);

-- ============================================================
-- PYTANIA KOMISJI (ZAL_8)
-- ============================================================

CREATE TABLE pytanie_komisji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    numer_pytania INTEGER NOT NULL,
    tresc_pytania TEXT NOT NULL,
    UNIQUE(dokument_id, numer_pytania)
);

CREATE TABLE ocena_pytania_komisji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pytanie_id INTEGER NOT NULL REFERENCES pytanie_komisji(id),
    czlonek_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    wartosc_oceny INTEGER NOT NULL,
    oceniono TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(pytanie_id, czlonek_id)
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
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    pytanie_id INTEGER NOT NULL REFERENCES pytanie_ankiety(id),
    odpowiedz TEXT NOT NULL,
    -- 'zdecydowanie_tak', 'raczej_tak', 'trudno_powiedziec',
    -- 'raczej_nie', 'zdecydowanie_nie'
    UNIQUE(dokument_id, pytanie_id)
    -- brak uzytkownik_id - anonimowość
);

CREATE TABLE komentarz_ankiety (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    tresc TEXT
    -- brak uzytkownik_id - anonimowość
);

-- ============================================================
-- SKŁAD KOMISJI (ZAL_8)
-- ============================================================

CREATE TABLE czlonek_komisji (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dokument_id INTEGER NOT NULL REFERENCES dokument(id),
    uzytkownik_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    rola_w_komisji TEXT NOT NULL,
    -- 'przewodniczacy', 'opiekun_uczelniany', 'czlonek'
    UNIQUE(dokument_id, uzytkownik_id)
);

-- ============================================================
-- SESJE UŻYTKOWNIKÓW
-- ============================================================

CREATE TABLE sesja_uzytkownika (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uzytkownik_id INTEGER NOT NULL REFERENCES uzytkownik(id),
    token_sesji TEXT NOT NULL UNIQUE,
    utworzono TEXT NOT NULL DEFAULT (datetime('now')),
    wygasa TEXT NOT NULL,
    jest_aktywna INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- INDEKSY
-- ============================================================

CREATE INDEX idx_dokument_praktyka ON dokument(praktyka_id);
CREATE INDEX idx_dokument_typ ON dokument(typ_dokumentu_id);
CREATE INDEX idx_dokument_status ON dokument(status);
CREATE INDEX idx_historia_dokument ON historia_dokumentu(dokument_id);
CREATE INDEX idx_historia_uzytkownik ON historia_dokumentu(uzytkownik_id);
CREATE INDEX idx_wpis_dziennika_dokument ON wpis_dziennika(dokument_id);
CREATE INDEX idx_dostep_uzytkownik ON dostep_do_dokumentu(uzytkownik_id);
CREATE INDEX idx_podpis_dokument ON podpis_dokumentu(dokument_id);
CREATE INDEX idx_praktyka_student ON praktyka(student_id);
CREATE INDEX idx_praktyka_firma ON praktyka(firma_id);
CREATE INDEX idx_uzytkownik_rola ON uzytkownik(rola_id);
CREATE INDEX idx_uzytkownik_firma ON uzytkownik(firma_id);