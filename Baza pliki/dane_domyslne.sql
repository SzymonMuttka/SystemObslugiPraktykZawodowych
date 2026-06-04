INSERT INTO efekt_uczenia (numer, opis) VALUES
    (1,  'Ma wiedzę na temat sposobu realizacji zadań inżynierskich dotyczących informatyki z zachowaniem standardów i norm technicznych'),
    (2,  'Zna technologie, narzędzia, metody, techniki oraz sprzęt stosowane w informatyce'),
    (3,  'Zna ekonomiczne, prawne skutki własnych działań podejmowanych w ramach praktyki oraz ograniczenia wynikające z prawa autorskiego i kodeksu pracy'),
    (4,  'Zna zasady bezpieczeństwa pracy i ergonomii w zawodzie informatyka'),
    (5,  'Pozyskuje informacje odnośnie technologii, metod, technik, sprzętu wymaganego do realizacji powierzonego zadania'),
    (6,  'W oparciu o kontakty ze środowiskiem inżynierskim zakładu potrafi podnieść swoje kompetencje'),
    (7,  'Opracowuje dokumentację dotyczącą realizacji podejmowanych zadań w ramach praktyki'),
    (8,  'Potrafi zidentyfikować problem informatyczny występujący w zakładzie pracy'),
    (9,  'Potrafi rozwiązać rzeczywiste zadanie inżynierskie z zakresu działalności informatycznej zakładu pracy'),
    (10, 'Pracuje w zespole zajmującym się zawodowo branżą IT'),
    (11, 'Przestrzega zasad etyki zawodowej i zgodnie z tymi zasadami korzysta z wiedzy i pomocy doświadczonych kolegów'),
    (12, 'Kontaktując się z osobami spoza branży potrafi zarówno pozyskać od nich niezbędne informacje'),
    (13, 'Dostrzega w praktyce tempo deaktualizacji wiedzy informatycznej oraz skutki działalności informatyków');
	
INSERT INTO pytanie_ankiety (numer, tresc_pytania) VALUES
    (1,  'Poznałam/poznałem zasady funkcjonowania instytucji, w której odbywałam/odbywałem praktyki zawodowe.'),
    (2,  'Poznałam/poznałem strukturę oraz regulamin organizacyjny instytucji, w której odbywałam/odbywałem praktyki zawodowe.'),
    (3,  'Praktyki zawodowe umożliwiły mi pełną realizację ramowego programu praktyk zawodowych przewidzianego w ramach mojego kierunku studiów.'),
    (4,  'Podczas praktyk zawodowych zwracano uwagę na przestrzeganie zasad etyki i tajemnicy zawodowej.'),
    (5,  'Podczas praktyk miałam/miałem możliwość praktycznego zastosowania wiedzy teoretycznej zdobytej na zajęciach.'),
    (6,  'Praktyki zawodowe przyczyniły się do pogłębienia mojej wiedzy i umiejętności zdobytych w trakcie studiów.'),
    (7,  'Mogłem liczyć na wsparcie merytoryczne Opiekuna zakładowego praktyk.'),
    (8,  'Mogłem liczyć na wsparcie merytoryczne Opiekuna uczelnianego praktyk.'),
    (9,  'Opiekun zakładowy odpowiedzialny za praktyki zawodowe w miejscu ich odbywania potrafił prawidłowo zorganizować ich przebieg.'),
    (10, 'Podczas praktyk zawodowych miałam/miałem możliwość pozyskiwania materiałów niezbędnych do przygotowania mojej pracy dyplomowej.'),
    (11, 'Praktyki zawodowe rozwinęły moje umiejętności skutecznego komunikowania się w sytuacjach zawodowych i pracy w zespole.'),
    (12, 'Praktyki zawodowe nauczyły mnie samodzielności i odpowiedzialności podczas wykonywania pracy.'),
    (13, 'Liczba godzin realizowana w ramach praktyk zawodowych jest wystarczająca.'),
    (14, 'Czy po zakończeniu praktyki zawodowej chciałaby/chciałby Pani/Pan współpracować z instytucją, w której Pani/Pan zrealizowała/zrealizował praktykę?');
	
INSERT INTO role (nazwa) VALUES
    ('student'),
    ('opiekun_uczelniany'),
    ('opiekun_firmowy'),
    ('dziekanat'),
    ('dyrektor'),
    ('czlonek_komisji');
	
INSERT INTO typ_dokumentu (id, kod, nazwa, sciezka, kolejnosc) VALUES
    (1,  'ZAL_1',  'Porozumienie w sprawie praktyk studenckich',        'standard',        2),
    (2,  'ZAL_2',  'Program praktyki zawodowej',                        'standard',        3),
    (3,  'ZAL_2A', 'Program i harmonogram praktyki zawodowej',          'standard',        4),
    (4,  'ZAL_3',  'Karta praktyki zawodowej',                          'standard',        5),
    (5,  'ZAL_4',  'Potwierdzenie uzyskania efektów uczenia się',       'standard',        7),
    (6,  'ZAL_4A', 'Potwierdzenie efektów na podstawie zatrudnienia',   'alternative',     2),
    (7,  'ZAL_4B', 'Wniosek o zaliczenie na podstawie zatrudnienia',    'alternative',     1),
    (8,  'ZAL_5',  'Kwestionariusz ankiety',                            'standard',        10),
    (9,  'ZAL_6',  'Dziennik praktyki zawodowej',                       'standard',        6),
    (10, 'ZAL_7',  'Sprawozdanie z praktyki zawodowej',                 'standard',        8),
    (11, 'ZAL_7A', 'Sprawozdanie z praktyki na podstawie zatrudnienia', 'alternative',     3),
    (12, 'ZAL_8',  'Protokół zaliczenia praktyki zawodowej',            'both',            9),
    (13, 'ZAL_9',  'Oświadczenie instytucji o przyjęciu studenta',      'standard',        1);