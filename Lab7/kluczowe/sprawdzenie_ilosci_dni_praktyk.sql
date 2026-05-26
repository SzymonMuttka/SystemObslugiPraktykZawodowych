-- Praktyki z niepoprawną liczbą dni roboczych
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       p.liczba_dni_roboczych
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
WHERE p.liczba_dni_roboczych <> 120;
-- Oczekiwany rezultat: brak rekordów

-- Sprawdzenie sumy dni w harmonogramie ZAL_2A
SELECT d.id AS dokument_id,
       u.imie || ' ' || u.nazwisko AS student,
       SUM(CAST(dd.wartosc AS INTEGER)) AS suma_dni
FROM dokument d
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
JOIN dane_dokumentu dd ON dd.dokument_id = d.id
    AND dd.klucz = 'planowana_liczba_dni'
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
    AND td.kod = 'ZAL_2A'
GROUP BY d.id, u.imie, u.nazwisko
HAVING SUM(CAST(dd.wartosc AS INTEGER)) <> 120;
-- Oczekiwany rezultat: brak rekordów