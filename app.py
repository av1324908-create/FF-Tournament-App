from flask import Flask, render_template, request, jsonify, session, redirect
from tournaments import db, Tournament, Player

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tournament.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "change-this-secret-key"

db.init_app(app)

with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin-login", methods=["POST"])
def admin_login():
    data = request.json

    if data.get("username") == "admin" and data.get("password") == "1234":
        session["admin"] = True
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Wrong username or password"}), 401


@app.route("/admin-logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")


@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():
    tournaments = Tournament.query.all()
    result = []

    for t in tournaments:
        players = Player.query.filter_by(tournament_id=t.id).all()

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


@app.route("/api/tournaments", methods=["POST"])
def add_tournament():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Admin login required"}), 403

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

    return jsonify({"success": True, "tournament": {"id": tournament.id}})


@app.route("/api/tournaments/<int:tournament_id>/players", methods=["POST"])
def add_player(tournament_id):
    data = request.json

    tournament = db.session.get(Tournament, tournament_id)

    if tournament is None:
        return jsonify({"success": False, "message": "Tournament not found"}), 404

    count = Player.query.filter_by(tournament_id=tournament_id).count()

    if count >= tournament.max_players:
        return jsonify({"success": False, "message": "Tournament full"}), 400

    player = Player(
        name=data["name"],
        uid=data["uid"],
        tournament_id=tournament_id
    )

    db.session.add(player)
    db.session.commit()

    return jsonify({"success": True, "player": {"id": player.id}})


if __name__ == "__main__":
    app.run(debug=True)