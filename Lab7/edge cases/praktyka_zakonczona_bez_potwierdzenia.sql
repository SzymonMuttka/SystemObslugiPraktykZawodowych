-- Praktyki ze statusem completed bez ukończonego ZAL_3
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       p.status
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
WHERE p.status = 'completed'
  AND NOT EXISTS (
      SELECT 1
      FROM dokument d
      JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
          AND td.kod = 'ZAL_3'
      WHERE d.praktyka_id = p.id
        AND d.status = 'completed'
  );
-- Oczekiwany rezultat: brak rekordów