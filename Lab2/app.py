from flask import Flask, render_template, request, jsonify, make_response
from datetime import datetime
import json, os

app = Flask(__name__)

class Wiadomosc:
    def __init__(self, imie, wiadomosc):
        self.imie = imie
        self.wiadomosc = wiadomosc

    def drukuj(self):
        return (f"Witaj { self.imie }! Twoja wiadomosc: { self.wiadomosc }")

class Kandydat:
    def __init__(self, fullname, email, github, position, skills, experience, id=0):
        self.id = id
        self.fullname = fullname
        self.email = email
        self.github = github
        self.position = position
        self.skills = skills
        self.experience = experience

    def to_dict(self):
        return {
            "id": self.id,
            "fullname": self.fullname,
            "email": self.email,
            "github": self.github,
            "position": self.position,
            "skills": self.skills,
            "experience": self.experience
        }

    def get_experience_level(self):
        length = len(self.experience or "")

        if length < 50:
            return "Junior"
        elif length < 100:
            return "Mid"
        else:
            return "Senior"

@app.route("/")
def hello_world():
    return render_template("index.html")


@app.route("/zainteresowania")
def zainteresowania():
    return render_template("zainteresowania.html")

@app.route('/api/kontakt', methods=['POST'])
def api_kontakt():
    # Pobieranie danych
    dane = {
        "imie": request.form.get('imie_uzytkownika'),
        "wiadomosc": request.form.get('tresc'),
        "status": "odebrano",
        "liczba_znakow": len(request.form.get('tresc', '')),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Logowanie faktu wygenerowania JSONa
    app.logger.info(f"Wygenerowano odpowiedź JSON dla {dane['imie']}")

    return jsonify(dane)

@app.route('/kontakt', methods=['GET', 'POST'])
def kontakt():
    if request.method=='POST':
        # Pobranie danych po kluczu z atrybutu 'name'
        imie = request.form.get('imie_uzytkownika')
        wiadomosc = request.form.get('tresc')

        wiad = Wiadomosc(imie, wiadomosc)
        app.logger.info((f'Utworzono obiekt Wiadomosc dla: {imie}, o tresci: {wiadomosc}'))

        return wiad.drukuj()

    return render_template('kontakt.html')

@app.route("/generator", methods=['GET', 'POST'])
def generator():
    if request.method == 'POST':
        # 1. Pobieranie danych
        skills_temp = request.form.get('skills', '')
        skills = sorted([s.strip().upper() for s in skills_temp.split(',') if s.strip()])

        kandydat = Kandydat(
            fullname=request.form.get('fullname'),
            email=request.form.get('email'),
            github=request.form.get('github'),
            position=request.form.get('position'),
            skills=skills,
            experience=request.form.get('experience')
        )

        if len(kandydat.fullname.strip().split()) < 2:
            app.logger.error(f'Niepoprawne fullname: {kandydat.fullname}')
            return "Błąd: podaj imię i nazwisko (min. 2 wyrazy)"

        if '@' not in kandydat.email:
            app.logger.error(f'Niepoprawny email: {kandydat.email}')
            return "Błąd: niepoprawny adres email (brak @)"

        if not kandydat.github.startswith("https://github.com/"):
            app.logger.error(f'Niepoprawny link GitHub: {kandydat.github}')
            return "Błąd: link GitHub musi zaczynać się od https://github.com/"

        # 2. Odczyt i dopisanie do pliku JSON
        file_path = 'cv_database.json'
        data = []
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        if data:
            kandydat.id = max(item.get("id", 0) for item in data) + 1
        else:
            kandydat.id = 1

        found = False

        for i, cv in enumerate(data):
            if cv.get("email") == kandydat.email:
                kandydat.id = cv.get("id")
                data[i] = kandydat.to_dict()
                found = True

                app.logger.info(f'Zaktualizowano CV dla email: {kandydat.email}')
                break

        if not found:
            data.append(kandydat.to_dict())
            app.logger.info(f'Dodano nowe CV dla email: {kandydat.email}')

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return render_template('szablon_cv.html', cv=kandydat)
    
    return render_template('formularz_cv.html')

@app.route('/admin/cv')
def admin_cv():
    file_path = 'cv_database.json'
    data = []

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    return render_template('admin_cv.html', cvs=data)

@app.route('/pobierz_cv', methods=['POST'])
def pobierz_cv():
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    github = request.form.get('github')
    position = request.form.get('position')
    skills = request.form.get('skills', '').split(',')
    experience = request.form.get('experience')

    # Formatowanie tekstu CV
    cv_text = f"""==============================
CV - {fullname}
==============================

Stanowisko: {position}

Email: {email}
GitHub: {github}

Umiejętności:
- """ + "\n- ".join(skill.strip() for skill in skills) + f"""

Doświadczenie:
{experience}
"""

    # Tworzenie odpowiedzi
    response = make_response(cv_text)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=cv_{fullname.replace(" ", "_")}.txt'

    return response