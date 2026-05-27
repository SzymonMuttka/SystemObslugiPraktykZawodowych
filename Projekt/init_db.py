"""
Skrypt inicjalizujący bazę danych.
Tworzy tabele na podstawie pliku baza_sqlite.sql
i wypełnia słownikowe dane (role).

Uruchomienie:
    python init_db.py
    python init_db.py --sql sciezka/do/pliku.sql
"""
import sqlite3
import os
import sys


SCIEZKA_SQL = 'baza_sqlite.sql'
SCIEZKA_DB = 'instance/praktyki.db'

ROLE = [
    'student',
    'opiekun_uczelniany',
    'opiekun_firmowy',
    'dziekanat',
    'dyrektor',
    'czlonek_komisji',
]


def init_db(sciezka_sql=SCIEZKA_SQL, sciezka_db=SCIEZKA_DB):
    # Sprawdzenie czy plik SQL istnieje
    if not os.path.exists(sciezka_sql):
        print(f"Błąd: nie znaleziono pliku {sciezka_sql}")
        print("Podaj ścieżkę jako argument: python init_db.py --sql sciezka/do/pliku.sql")
        sys.exit(1)

    # Utworzenie katalogu instance jeśli nie istnieje
    os.makedirs(os.path.dirname(sciezka_db), exist_ok=True)

    # Połączenie z bazą i wykonanie skryptu SQL
    conn = sqlite3.connect(sciezka_db)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        with open(sciezka_sql, 'r', encoding='utf-8') as f:
            skrypt = f.read()

        conn.executescript(skrypt)
        print(f"Tabele utworzone z pliku: {sciezka_sql}")

        # Wypełnienie ról jeśli tabela jest pusta
        kursor = conn.cursor()
        for nazwa in ROLE:
            kursor.execute(
                "SELECT id FROM role WHERE nazwa = ?", (nazwa,)
            )
            if not kursor.fetchone():
                kursor.execute(
                    "INSERT INTO role (nazwa) VALUES (?)", (nazwa,)
                )
                print(f"  Dodano rolę: {nazwa}")
            else:
                print(f"  Rola już istnieje: {nazwa}")

        conn.commit()
        print(f"Inicjalizacja zakończona. Baza: {sciezka_db}")

    except sqlite3.Error as e:
        print(f"Błąd SQLite: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    # Opcjonalny argument --sql pozwala podać inną ścieżkę do pliku SQL
    sql = SCIEZKA_SQL
    if '--sql' in sys.argv:
        idx = sys.argv.index('--sql')
        if idx + 1 < len(sys.argv):
            sql = sys.argv[idx + 1]

    init_db(sciezka_sql=sql)
