from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Rola(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    nazwa = db.Column(db.String(50), unique=True, nullable=False)

    uzytkownicy = db.relationship('Uzytkownik', back_populates='rola')

    def __repr__(self):
        return f'<Rola {self.nazwa}>'


class Uzytkownik(UserMixin, db.Model):
    __tablename__ = 'uzytkownik'

    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String(100), nullable=False)
    nazwisko = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    haslo_hash = db.Column(db.String(255), nullable=False, default='oauth')

    # Dane OAuth
    auth_provider = db.Column(db.String(50), default='microsoft')
    external_id = db.Column(db.String(255), unique=True)

    # Powiązanie z rolą
    rola_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    rola = db.relationship('Rola', back_populates='uzytkownicy')

    # Dane studenta
    numer_albumu = db.Column(db.String(20), unique=True)
    specjalnosc = db.Column(db.String(255))
    forma_studiow = db.Column(db.String(20))
    rok_akademicki = db.Column(db.String(9))

    # Dane opiekuna firmowego
    telefon = db.Column(db.String(20))
    stanowisko = db.Column(db.String(255))
    firma_id = db.Column(db.Integer, db.ForeignKey('firma.id'))
    firma = db.relationship('Firma', back_populates='uzytkownicy')

    jest_aktywny = db.Column(db.Boolean, default=True)
    wymaga_zatwierdzenia = db.Column(db.Boolean, default=False)

    utworzono = db.Column(
        db.DateTime, nullable=False,
        server_default=db.func.now()
    )
    zaktualizowano = db.Column(
        db.DateTime, nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    # --------------------------------------------------------
    # Flask-Login: wymagane właściwości i metody
    # --------------------------------------------------------

    @property
    def is_active(self):
        return self.jest_aktywny

    @property
    def pelne_imie(self):
        return f'{self.imie} {self.nazwisko}'

    def ma_role(self, *role):
        """Sprawdza czy użytkownik ma jedną z podanych ról."""
        return self.rola.nazwa in role

    def ustaw_haslo(self, haslo):
        self.haslo_hash = generate_password_hash(haslo)

    def sprawdz_haslo(self, haslo):
        return check_password_hash(self.haslo_hash, haslo)

    def __repr__(self):
        return f'<Uzytkownik {self.email}>'
