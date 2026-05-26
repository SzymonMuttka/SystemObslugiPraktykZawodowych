-- Dokumenty ZAL_8 z oceną końcową K przy niekompletnych efektach w ZAL_4
SELECT od.dokument_id,
       u.imie || ' ' || u.nazwisko AS student,
       od.wartosc_oceny AS ocena_k,
       COUNT(eud.efekt_id) AS liczba_efektow
FROM ocena_dokumentu od
JOIN dokument d ON od.dokument_id = d.id
JOIN typ_dokumentu td ON d.typ_dokumentu_id = td.id
    AND td.kod = 'ZAL_8'
JOIN praktyka p ON d.praktyka_id = p.id
JOIN uzytkownik u ON p.student_id = u.id
LEFT JOIN dokument d4 ON d4.praktyka_id = p.id
LEFT JOIN typ_dokumentu td4 ON d4.typ_dokumentu_id = td4.id
    AND td4.kod = 'ZAL_4'
LEFT JOIN efekt_uczenia_dokumentu eud ON eud.dokument_id = d4.id
WHERE od.typ_oceny = 'K'
  AND od.wartosc_oceny >= '3'
GROUP BY od.dokument_id, u.imie, u.nazwisko, od.wartosc_oceny
HAVING COUNT(eud.efekt_id) < 13;
-- Oczekiwany rezultat: brak rekordów