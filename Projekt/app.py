from flask import Flask, render_template, request, redirect, url_for
import os, json

app = Flask(__name__)

def load_efekty():
    if os.path.exists("efekty_praktyki.json"):
        with open("efekty_praktyki.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_efekty(data):
    with open("efekty_praktyki.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_dziennik():
    if os.path.exists("dziennik_praktyki.json"):
        with open("dziennik_praktyki.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_dziennik(data):
    with open("dziennik_praktyki.json", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/efekty-uczenia")
def efekty_uczenia():
    return render_template("efekty-uczenia.html")

@app.route("/zapisz-efekty", methods=['POST'])
def zapisz_efekty():
    indeks = request.form.get("indeks")

    nowe_dane = {
        "indeks": indeks,
        "imie_nazw": request.form.get("imie_nazw"),
        "specjalnosc": request.form.get("specjalnosc"),
        "godziny": request.form.get("godziny"),
        "efekty": {}
    }

    for i in range(1, 14):
        key = f"efekt{str(i).zfill(2)}"
        nowe_dane["efekty"][str(i)] = request.form.get(key) == "true"

    nowe_dane["opinia"] = request.form.get("opinia")

    data = load_efekty()
    found = False

    for i, rekord in enumerate(data):
        if rekord.get("indeks") == indeks:
            data[i] = nowe_dane
            found = True
            app.logger.info(f"Zaktualizowano wpis dla indeksu: {indeks}")
            break

    if not found:
        data.append(nowe_dane)
        app.logger.info(f"Dodano nowy wpis dla indeksu: {indeks}")

    save_efekty(data)
    return redirect(url_for("index"))

@app.route("/dziennik")
def dziennik():
    return render_template("dziennik.html")

@app.route("/zapisz-dziennik", methods=['POST'])
def zapisz_dziennik():
    indeks = request.form.get("indeks")
    wykaz_zal_temp = request.form.get('wykaz_zal', '')

    nowe_dane = {
        "indeks": indeks,
        "imie_nazw": request.form.get("imie_nazw"),
        "specjalnosc": request.form.get("specjalnosc"),
        "rok_ak": request.form.get("rok_ak"),
        "miejsce_praktyk": request.form.get("miejsce_praktyk"),
        "data_rozp": request.form.get("data_rozp"),
        "data_zak": request.form.get("data_zak"),
        "wykaz_zal": sorted([w.strip() for w in wykaz_zal_temp.split(',') if w.strip()])
    }

    dni = request.form.getlist("dzien[]")
    daty = request.form.getlist("data[]")
    opisy = request.form.getlist("opis[]")
    efekty = request.form.getlist("efekty[]")

    nowy_dziennik = {}

    for d, data, opis, efekt in zip(dni, daty, opisy, efekty):
        if d.strip().isdigit():
            nowy_dziennik[int(d)] = {
                "dzien": d,
                "data": data,
                "opis": opis,
                "efekty": efekt
            }

    data = load_dziennik()
    found = False

    for i, rekord in enumerate(data):
        if rekord.get("indeks") == indeks:
            found = True

            stary_dziennik = {
                int(wpis["dzien"]): wpis
                for wpis in rekord.get("dziennik", [])
            }

            stary_dziennik.update(nowy_dziennik)

            posortowany = [
                stary_dziennik[k]
                for k in sorted(stary_dziennik.keys())
            ]

            nowe_dane["dziennik"] = posortowany
            data[i] = nowe_dane

            app.logger.info(f"Zmergowano dziennik dla indeksu: {indeks}")
            break

    if not found:
        posortowany = [
            nowy_dziennik[k]
            for k in sorted(nowy_dziennik.keys())
        ]

        nowe_dane["dziennik"] = posortowany
        data.append(nowe_dane)

        app.logger.info(f"Dodano nowy dziennik dla indeksu: {indeks}")

    save_dziennik(data)
    return redirect(url_for("index"))