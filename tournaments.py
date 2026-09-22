from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    entry_fee = db.Column(db.Integer, default=0)
    max_players = db.Column(db.Integer, default=0)
    kill_reward = db.Column(db.Integer, default=0)
    first_prize = db.Column(db.Integer, default=0)
    date_time = db.Column(db.String(50))


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    uid = db.Column(db.String(50), nullable=False)
    kills = db.Column(db.Integer, default=0)
    position = db.Column(db.Integer, default=0)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"))