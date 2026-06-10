# SystemObslugiPraktykZawodowych

## Zawartość repozytorium:
Foldery Lab 1-8 posiadają pliki wymagane w instrukcji do danego laboratorium, któe nie wchodzą bezpośrednio w skłąd projektu.

Folder 'Baza pliki' posiada plik tworzący bazę, przykładowe dane oraz obraz .png i dokument .pdf struktury bazy.

Folder 'Mermaid/workflows' zawiera cykl życia każdego załącznika w formie .png i .svg a także kod użyty do wytworzenia tego schematu.

Folder 'Załączniki' posiada załączniki, które uzupełniane są w ramach praktyk, jako .docx lub .jpg.

Folder Projekt zawiera aplikację Flask Systemu Obsługi Praktyk Zawodowych.

## Instalacja
1. Będąc w folderze głównym (SystemObslugiPraktykZawodowych), w konsoli w pisz 'cd Projekt'
2. Następnie, wpisz 'python -m venv venv', a potem 'venv\Scripts\activate'
3. Zainstaluj wymagane biblioteki poleceniem 'pip install -r requirements.txt'
4. Uruchom projekt poleceniem 'python run.py' i przejdź pod adres 'http://localhost:5000/auth/login'