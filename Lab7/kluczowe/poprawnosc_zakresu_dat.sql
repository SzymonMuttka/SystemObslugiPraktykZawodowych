-- Praktyki z datą zakończenia wcześniejszą niż rozpoczęcia
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       p.data_rozpoczecia,
       p.data_zakonczenia
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
WHERE p.data_zakonczenia < p.data_rozpoczecia;
-- Oczekiwany rezultat: brak rekordów

-- Wpisy dziennika poza zakresem dat praktyki
SELECT wd.id,
       u.imie || ' ' || u.nazwisko AS student,
       wd.data_wpisu,
       p.data_rozpoczecia,
       p.data_zakonczenia
FROM wpis_dziennika wd
JOIN dokument d ON wd.dokument_id = d.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
WHERE wd.data_wpisu < p.data_rozpoczecia
   OR wd.data_wpisu > p.data_zakonczenia;
-- Oczekiwany rezultat: brak rekordów