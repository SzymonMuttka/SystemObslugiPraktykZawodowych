-- Daty w ZAL_3 (skierowanie) niezgodne z datami w tabeli praktyka
SELECT d.id AS dokument_id,
       u.imie || ' ' || u.nazwisko AS student,
       p.data_rozpoczecia AS data_w_praktyce,
       dd_od.wartosc AS data_w_zal3_od,
       p.data_zakonczenia AS koniec_w_praktyce,
       dd_do.wartosc AS data_w_zal3_do
FROM dokument d
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
    AND td.kod = 'ZAL_3'
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
LEFT JOIN dane_dokumentu dd_od ON dd_od.dokument_id = d.id
    AND dd_od.klucz = 'data_rozpoczecia'
LEFT JOIN dane_dokumentu dd_do ON dd_do.dokument_id = d.id
    AND dd_do.klucz = 'data_zakonczenia'
WHERE dd_od.wartosc <> p.data_rozpoczecia
   OR dd_do.wartosc <> p.data_zakonczenia;
-- Oczekiwany rezultat: brak rekordów