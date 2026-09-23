from flask import Flask, render_template, request, jsonify, session, redirect
from tournaments import db, Tournament, Player
import os

app = Flask(__name__)

# =========================
# DATABASE
# =========================

database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Render PostgreSQL
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

else:
    # Local development
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tournament.db"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

db.init_app(app)

with app.app_context():
    db.create_all()


# =========================
# PUBLIC PAGE
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# ADMIN PAGE
# =========================

@app.route("/admin")
def admin():
    return render_template("admin.html")


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin-login", methods=["POST"])
def admin_login():

    data = request.json

    if (
        data.get("username") == "admin"
        and data.get("password") == "1234"
    ):

        session["admin"] = True

        return jsonify({
            "success": True
        })

    return jsonify({
        "success": False,
        "message": "Wrong username or password"
    }), 401


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin", None)

    return redirect("/admin")


# =========================
# GET TOURNAMENTS
# =========================

@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():

    tournaments = Tournament.query.all()

    result = []

    for t in tournaments:

        players = Player.query.filter_by(
            tournament_id=t.id
        ).all()

        result.append({

            "id": t.id,
            "name": t.name,
            "entry_fee": t.entry_fee,
            "max_players": t.max_players,
            "kill_reward": t.kill_reward,
            "first_prize": t.first_prize,
            "date_time": t.date_time,

            "players": [

                {
                    "id": p.id,
                    "name": p.name,
                    "uid": p.uid,
                    "kills": p.kills,
                    "position": p.position
                }

                for p in players
            ]
        })

    return jsonify(result)


# =========================
# CREATE TOURNAMENT
# =========================

@app.route("/api/tournaments", methods=["POST"])
def add_tournament():

    if not session.get("admin"):

        return jsonify({
            "success": False,
            "message": "Admin login required"
        }), 403

    data = request.json

    tournament = Tournament(

        name=data["name"],
        entry_fee=int(data["entry_fee"]),
        max_players=int(data["max_players"]),
        kill_reward=int(data["kill_reward"]),
        first_prize=int(data["first_prize"]),
        date_time=data["date_time"]
    )

    db.session.add(tournament)

    db.session.commit()

    return jsonify({

        "success": True,

        "tournament": {
            "id": tournament.id
        }

    })


# =========================
# REGISTER PLAYER
# =========================

@app.route(
    "/api/tournaments/<int:tournament_id>/players",
    methods=["POST"]
)
def add_player(tournament_id):

    data = request.json or {}

    name = str(
        data.get("name", "")
    ).strip()

    uid = str(
        data.get("uid", "")
    ).strip()


    # Tournament check
    tournament = db.session.get(
        Tournament,
        tournament_id
    )

    if tournament is None:

        return jsonify({

            "success": False,
            "message": "Tournament not found"

        }), 404


    # Empty fields
    if not name or not uid:

        return jsonify({

            "success": False,
            "message": "Please enter your name and Free Fire UID."

        }), 400


    # Duplicate UID
    existing_player = Player.query.filter_by(
        tournament_id=tournament_id,
        uid=uid
    ).first()

    if existing_player:

        return jsonify({

            "success": False,

            "message": (
                "Your ID has already been registered "
                "for this tournament."
            ),

            "registration_id": existing_player.id

        }), 409


    # Tournament full
    count = Player.query.filter_by(
        tournament_id=tournament_id
    ).count()

    if count >= tournament.max_players:

        return jsonify({

            "success": False,
            "message": "Tournament is full."

        }), 400


    # Create player
    player = Player(

        name=name,
        uid=uid,
        tournament_id=tournament_id

    )

    db.session.add(player)

    db.session.commit()


    # Success
    return jsonify({

        "success": True,

        "message": (
            "Your ID has been registered successfully! "
            "Your slot is booked."
        ),

        "registration_id": player.id,

        "player": {

            "id": player.id,
            "name": player.name,
            "uid": player.uid

        }

    })


# =========================
# UPDATE PLAYER RESULT
# =========================

@app.route(
    "/api/players/<int:player_id>",
    methods=["PUT"]
)
def update_player(player_id):

    if not session.get("admin"):

        return jsonify({

            "success": False,
            "message": "Admin login required"

        }), 403


    player = db.session.get(
        Player,
        player_id
    )

    if player is None:

        return jsonify({

            "success": False,
            "message": "Player not found"

        }), 404


    data = request.json or {}

    player.kills = int(
        data.get("kills", 0)
    )

    player.position = int(
        data.get("position", 0)
    )

    db.session.commit()


    return jsonify({

        "success": True,
        "message": "Player result updated"

    })


# =========================
# RUN APP
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
