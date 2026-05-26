-- Dokumenty oznaczone jako completed bez wszystkich wymaganych podpisów
SELECT d.id AS dokument_id,
       td.kod,
       u.imie || ' ' || u.nazwisko AS student,
       COUNT(ps.id) AS liczba_podpisow,
       SUM(ps.jest_podpisany) AS zlozonych_podpisow
FROM dokument d
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
LEFT JOIN podpis_dokumentu ps ON ps.dokument_id = d.id
WHERE d.status = 'completed'
GROUP BY d.id, td.kod, u.imie, u.nazwisko
HAVING COUNT(ps.id) <> SUM(ps.jest_podpisany);
-- Oczekiwany rezultat: brak rekordów