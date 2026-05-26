-- Próba wykrycia duplikatów numerów albumu
SELECT numer_albumu, COUNT(*) AS liczba
FROM uzytkownik
WHERE numer_albumu IS NOT NULL
GROUP BY numer_albumu
HAVING COUNT(*) > 1;
-- Oczekiwany rezultat: brak rekordów
-- Zabezpieczenie: kolumna numer_albumu ma UNIQUE