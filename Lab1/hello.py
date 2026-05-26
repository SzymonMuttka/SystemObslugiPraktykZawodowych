from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def hello_world():
    return render_template("index.html")


@app.route("/zainteresowania")
def zainteresowania():
    return render_template("zainteresowania.html")


@app.route("/kontakt")
def kontakt():
    return render_template("kontakt.html")