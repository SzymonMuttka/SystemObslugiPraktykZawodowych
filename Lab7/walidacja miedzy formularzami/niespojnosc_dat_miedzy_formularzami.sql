-- Wykrycie niespójności dat między wszystkimi dokumentami tej samej praktyki
SELECT p.id AS praktyka_id,
       u.imie || ' ' || u.nazwisko AS student,
       p.data_rozpoczecia AS data_w_praktyce,
       td.kod AS dokument,
       dd.wartosc AS data_w_dokumencie
FROM dane_dokumentu dd
JOIN dokument d ON dd.dokument_id = d.id
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
WHERE dd.klucz = 'data_rozpoczecia'
  AND dd.wartosc <> p.data_rozpoczecia;
-- Oczekiwany rezultat: brak rekordów