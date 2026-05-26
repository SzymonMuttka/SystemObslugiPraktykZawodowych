-- Praktyki bez przypisanego opiekuna uczelnianego lub firmowego
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       CASE WHEN p.opiekun_firmowy_id IS NULL
            THEN 'brak opiekuna firmowego' END AS blad_firmowy,
       CASE WHEN p.opiekun_uczelniany_id IS NULL
            THEN 'brak opiekuna uczelnianego' END AS blad_uczelniany
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
WHERE p.opiekun_firmowy_id IS NULL
   OR p.opiekun_uczelniany_id IS NULL;
-- Oczekiwany rezultat: brak rekordów