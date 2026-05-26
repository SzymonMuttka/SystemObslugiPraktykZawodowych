-- Efekty w ZAL_4 bez pokrycia w wpisach dziennika ZAL_6
SELECT eud.efekt_id,
       eu.numer AS numer_efektu,
       u.imie || ' ' || u.nazwisko AS student
FROM efekt_uczenia_dokumentu eud
JOIN dokument d4 ON eud.dokument_id = d4.id
JOIN typ_dokumentu td4 ON d4.typ_dokumentu_id = td4.id
    AND td4.kod = 'ZAL_4'
JOIN praktyka p ON d4.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
JOIN efekt_uczenia eu ON eud.efekt_id = eu.id
WHERE NOT EXISTS (
    SELECT 1
    FROM wpis_dziennika wd
    JOIN dokument d6 ON wd.dokument_id = d6.id
    JOIN typ_dokumentu td6 ON d6.typ_dokumentu_id = td6.id
        AND td6.kod = 'ZAL_6'
    WHERE d6.praktyka_id = p.id
      AND wd.numery_efektow LIKE '%' || eu.numer || '%'
);
-- Oczekiwany rezultat: brak rekordów