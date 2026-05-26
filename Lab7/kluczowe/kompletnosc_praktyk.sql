--Kompletność praktyk (do zmiany)
-- Praktyki z brakującymi danymi podstawowymi
SELECT p.id,
       u.imie || ' ' || u.nazwisko AS student,
       CASE WHEN p.student_id IS NULL THEN 'brak studenta' END AS blad_student,
       CASE WHEN p.firma_id IS NULL THEN 'brak firmy' END AS blad_firma,
       CASE WHEN p.data_rozpoczecia IS NULL THEN 'brak daty rozpoczecia' END AS blad_data_od,
       CASE WHEN p.data_zakonczenia IS NULL THEN 'brak daty zakonczenia' END AS blad_data_do,
       CASE WHEN p.opiekun_firmowy_id IS NULL THEN 'brak opiekuna firmowego' END AS blad_op_firm,
       CASE WHEN p.opiekun_uczelniany_id IS NULL THEN 'brak opiekuna uczelnianego' END AS blad_op_ucz
FROM praktyka p
LEFT JOIN uzytkownik u ON p.student_id = u.id
WHERE p.student_id IS NULL
   OR p.firma_id IS NULL
   OR p.data_rozpoczecia IS NULL
   OR p.data_zakonczenia IS NULL
   OR p.opiekun_firmowy_id IS NULL
   OR p.opiekun_uczelniany_id IS NULL;
-- Oczekiwany rezultat: brak rekordów