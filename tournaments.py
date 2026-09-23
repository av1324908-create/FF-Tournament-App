from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# =========================
# TOURNAMENT
# =========================

class Tournament(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    entry_fee = db.Column(
        db.Integer,
        default=0
    )

    max_players = db.Column(
        db.Integer,
        default=0
    )

    kill_reward = db.Column(
        db.Integer,
        default=0
    )

    first_prize = db.Column(
        db.Integer,
        default=0
    )

    date_time = db.Column(
        db.String(50)
    )


# =========================
# PLAYER ACCOUNT
# =========================

class Player(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    uid = db.Column(
        db.String(50),
        nullable=False
    )

    kills = db.Column(
        db.Integer,
        default=0
    )

    position = db.Column(
        db.Integer,
        default=0
    )

    tournament_id = db.Column(
        db.Integer,
        db.ForeignKey("tournament.id"),
        nullable=False
    )


# =========================
# PLAYER WALLET
# =========================

class Wallet(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    player_uid = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    balance = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================
# TOKEN TRANSACTION
# =========================

class TokenTransaction(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    player_uid = db.Column(
        db.String(50),
        nullable=False
    )

    amount = db.Column(
        db.Integer,
        nullable=False
    )

    transaction_type = db.Column(
        db.String(30),
        nullable=False
    )

    description = db.Column(
        db.String(200)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
