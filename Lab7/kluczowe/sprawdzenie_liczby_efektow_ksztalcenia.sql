-- Dokumenty ZAL_4 i ZAL_4A z niepełną liczbą efektów (wymagane 13)
SELECT d.id AS dokument_id,
       td.kod,
       u.imie || ' ' || u.nazwisko AS student,
       COUNT(eud.efekt_id) AS liczba_efektow
FROM dokument d
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
LEFT JOIN efekt_uczenia_dokumentu eud ON eud.dokument_id = d.id
WHERE td.kod IN ('ZAL_4', 'ZAL_4A')
GROUP BY d.id, td.kod, u.imie, u.nazwisko
HAVING COUNT(eud.efekt_id) <> 13;
-- Oczekiwany rezultat: brak rekordów

-- Efekty bez przypisanej decyzji (status NULL)
SELECT d.id AS dokument_id,
       td.kod,
       u.imie || ' ' || u.nazwisko AS student,
       eu.numer AS numer_efektu
FROM efekt_uczenia_dokumentu eud
JOIN dokument d ON eud.dokument_id = d.id
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
JOIN efekt_uczenia eu ON eud.efekt_id = eu.id
WHERE eud.status IS NULL;
-- Oczekiwany rezultat: brak rekordów