from flask import Flask, render_template, request, redirect, url_for
import json, os

app = Flask(__name__)

DATA_FILE = 'cv_database.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/edytuj_tabele")
def edytuj_tabele():
    kandydaci = load_data()
    return render_template("edytuj_tabele.html", kandydaci=kandydaci)

@app.route("/aktualizuj-wszystko", methods=['POST'])
def aktualizuj_wszystko():
    names = request.form.getlist('fullname[]')
    emails = request.form.getlist('email[]')

    # Tworzenie nowej struktury danych
    nowe_dane = [{"fullname" : n, "email": e} for n, e in zip(names, emails) if n.strip()]
    save_data(nowe_dane)
    return redirect(url_for('index'))