from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    entry_fee = db.Column(db.Integer, default=0)
    max_players = db.Column(db.Integer, default=0)
    kill_reward = db.Column(db.Integer, default=0)
    first_prize = db.Column(db.Integer, default=0)
    date_time = db.Column(db.String(50))
    rules = db.Column(db.Text, default="")
    room_id = db.Column(db.String(100), default="")
    room_password = db.Column(db.String(100), default="")

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    uid = db.Column(db.String(50), nullable=False)
    kills = db.Column(db.Integer, default=0)
    position = db.Column(db.Integer, default=0)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    uid = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserTournamentRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_uid = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TokenTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_uid = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
