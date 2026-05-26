-- Porównanie planowanej liczby dni z ZAL_2A z rzeczywistą liczbą wpisów w ZAL_6
SELECT p.id AS praktyka_id,
       u.imie || ' ' || u.nazwisko AS student,
       COUNT(wd.id) AS wpisy_w_dzienniku,
       p.liczba_dni_roboczych AS wymagana_liczba_dni
FROM praktyka p
JOIN uzytkownik u ON p.student_id = u.id
LEFT JOIN dokument d6 ON d6.praktyka_id = p.id
LEFT JOIN typ_dokumentu td6 ON d6.typ_dokumentu_id = td6.id
    AND td6.kod = 'ZAL_6'
LEFT JOIN wpis_dziennika wd ON wd.dokument_id = d6.id
GROUP BY p.id, u.imie, u.nazwisko, p.liczba_dni_roboczych
HAVING COUNT(wd.id) <> p.liczba_dni_roboczych;
-- Oczekiwany rezultat: brak rekordów