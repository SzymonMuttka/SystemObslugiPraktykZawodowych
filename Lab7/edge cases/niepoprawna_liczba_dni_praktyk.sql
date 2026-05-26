-- Wykrycie praktyk z liczbą dni inną niż 120
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       p.liczba_dni_roboczych
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
WHERE p.liczba_dni_roboczych <> 120
   OR p.liczba_dni_roboczych IS NULL;
-- Oczekiwany rezultat: brak rekordów