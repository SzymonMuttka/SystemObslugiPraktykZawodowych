from app import db


class Firma(db.Model):
    __tablename__ = 'firma'

    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(255), nullable=False)
    adres = db.Column(db.String(255), nullable=False)
    miasto = db.Column(db.String(100), nullable=False)
    osoba_upowazniona_imie_nazwisko = db.Column(db.String(255))
    osoba_upowazniona_stanowisko = db.Column(db.String(255))
    jest_aktywna = db.Column(db.Boolean, default=True)
    utworzono = db.Column(db.DateTime, server_default=db.func.now())
    zaktualizowano = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    uzytkownicy = db.relationship('Uzytkownik', back_populates='firma')

    def __repr__(self):
        return f'<Firma {self.nazwa}>'
