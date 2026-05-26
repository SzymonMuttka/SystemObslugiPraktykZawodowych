-- Wszystkie dokumenty danej praktyki powinny należeć do tego samego studenta
SELECT d.id AS dokument_id,
       td.kod,
       p.student_id AS student_w_praktyce,
       d.utworzony_przez AS tworca_dokumentu
FROM dokument d
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON d.utworzony_przez = u.id
JOIN role r ON u.rola_id = r.id
    AND r.nazwa = 'student'
WHERE d.utworzony_przez <> p.student_id;
-- Oczekiwany rezultat: brak rekordów