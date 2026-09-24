from datetime import datetime
from tournaments import (
    db,
    Tournament,
    Player,
    Wallet,
    TokenTransaction
)
import os


app = Flask(__name__)


# =========================
# DATABASE
# =========================

database_url = os.environ.get("DATABASE_URL")

if database_url:

    if database_url.startswith("postgres://"):

        database_url = database_url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

else:

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///tournament.db"
    )


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# =========================
# SECRET KEY
# =========================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)


db.init_app(app)


# =========================
# CREATE DATABASE TABLES
# =========================

with app.app_context():

    db.create_all()


# =========================
# PUBLIC HOME PAGE
# =========================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================
# ADMIN PAGE
# =========================

@app.route("/admin")
def admin():

    return render_template(
        "admin.html"
    )


# =========================
# ADMIN LOGIN
# =========================

@app.route(
    "/admin-login",
    methods=["POST"]
)
def admin_login():

    data = request.json or {}

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    ).strip()


    if username == "admin" and password == "1234":

        session["admin"] = True

        return jsonify({

            "success": True,

            "message": "Login successful"

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

    session.pop(
        "admin",
        None
    )

    return redirect("/admin")


# ==================================================
# TOURNAMENT APIs
# ==================================================


# =========================
# GET ALL TOURNAMENTS
# =========================

@app.route(
    "/api/tournaments",
    methods=["GET"]
)
def get_tournaments():

    tournaments = Tournament.query.order_by(
        Tournament.id.desc()
    ).all()

    result = []


    for tournament in tournaments:

        players = Player.query.filter_by(
            tournament_id=tournament.id
        ).all()


        result.append({

            "id": tournament.id,

            "name": tournament.name,

            "entry_fee": tournament.entry_fee,

            "max_players": tournament.max_players,

            "kill_reward": tournament.kill_reward,

            "first_prize": tournament.first_prize,

            "date_time": tournament.date_time,

            "players": [

                {

                    "id": player.id,

                    "name": player.name,

                    "uid": player.uid,

                    "kills": player.kills,

                    "position": player.position

                }

                for player in players

            ]

        })


    return jsonify(result)


# =========================
# CREATE TOURNAMENT
# =========================

@app.route(
    "/api/tournaments",
    methods=["POST"]
)
def add_tournament():

    if not session.get("admin"):

        return jsonify({

            "success": False,

            "message": "Admin login required"

        }), 403


    data = request.json or {}


    name = str(
        data.get("name", "")
    ).strip()

    entry_fee = str(
        data.get("entry_fee", "")
    ).strip()

    max_players = str(
        data.get("max_players", "")
    ).strip()

    kill_reward = str(
        data.get("kill_reward", "")
    ).strip()

    first_prize = str(
        data.get("first_prize", "")
    ).strip()

    date_time = str(
        data.get("date_time", "")
    ).strip()


    # =========================
    # VALIDATION
    # =========================

    if not name:

        return jsonify({

            "success": False,

            "message": "Tournament name is required."

        }), 400


    if not entry_fee:

        return jsonify({

            "success": False,

            "message": "Entry fee is required."

        }), 400


    if not max_players:

        return jsonify({

            "success": False,

            "message": "Maximum players is required."

        }), 400


    if not kill_reward:

        return jsonify({

            "success": False,

            "message": "Kill reward is required."

        }), 400


    if not first_prize:

        return jsonify({

            "success": False,

            "message": "1st prize is required."

        }), 400


    if not date_time:

        return jsonify({

            "success": False,

            "message": "Date and time is required."

        }), 400


    # =========================
    # NUMBER VALIDATION
    # =========================

    try:

        entry_fee = int(entry_fee)

        max_players = int(max_players)

        kill_reward = int(kill_reward)

        first_prize = int(first_prize)

    except ValueError:

        return jsonify({

            "success": False,

            "message": (
                "Fee and player values "
                "must be numbers."
            )

        }), 400


    if entry_fee < 0:

        return jsonify({

            "success": False,

            "message": (
                "Entry fee cannot be negative."
            )

        }), 400


    if max_players <= 0:

        return jsonify({

            "success": False,

            "message": (
                "Maximum players must "
                "be greater than 0."
            )

        }), 400


    if kill_reward < 0 or first_prize < 0:

        return jsonify({

            "success": False,

            "message": (
                "Prize values cannot "
                "be negative."
            )

        }), 400


    # =========================
    # CREATE TOURNAMENT
    # =========================

    tournament = Tournament(

        name=name,

        entry_fee=entry_fee,

        max_players=max_players,

        kill_reward=kill_reward,

        first_prize=first_prize,

        date_time=date_time

    )


    db.session.add(
        tournament
    )

    db.session.commit()


    return jsonify({

        "success": True,

        "message": (
            "Tournament created successfully."
        ),

        "tournament": {

            "id": tournament.id,

            "name": tournament.name

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


    # =========================
    # TOURNAMENT CHECK
    # =========================

    tournament = db.session.get(
        Tournament,
        tournament_id
    )


    if tournament is None:

        return jsonify({
            "success": False,
            "message": "Tournament not found."
        }), 404


    # =========================
    # TOURNAMENT DATE CHECK
    # =========================

    try:
        tournament_date = datetime.strptime(
            tournament.date_time,
            "%d/%m/%y %H:%M"
        )
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Tournament date/time is invalid."
        }), 400

    if tournament_date <= datetime.now():
        return jsonify({
            "success": False,
            "message": "Tournament registration is closed."
        }), 400


    # =========================
    # EMPTY FIELD CHECK
    # =========================
    if not name:

        return jsonify({

            "success": False,

            "message": "Please enter your name."

        }), 400


    if not uid:

        return jsonify({

            "success": False,

            "message": (
                "Please enter your Free Fire UID."
            )

        }), 400


    # =========================
    # DUPLICATE UID CHECK
    # =========================

    existing_player = Player.query.filter_by(

        tournament_id=tournament_id,

        uid=uid

    ).first()


    if existing_player:

        return jsonify({

            "success": False,

            "message": (
                "Your ID has already been "
                "registered for this tournament."
            ),

            "registration_id": existing_player.id

        }), 409


    # =========================
    # TOURNAMENT FULL CHECK
    # =========================

    player_count = Player.query.filter_by(

        tournament_id=tournament_id

    ).count()


    if player_count >= tournament.max_players:

        return jsonify({

            "success": False,

            "message": "Tournament is full."

        }), 400


    # =========================
    # CREATE PLAYER
    # =========================

    player = Player(

        name=name,

        uid=uid,

        tournament_id=tournament_id

    )


    db.session.add(
        player
    )

    db.session.commit()


    return jsonify({

        "success": True,

        "message": (
            "Your ID has been registered "
            "successfully! Your slot is booked."
        ),

        "registration_id": player.id,

        "player": {

            "id": player.id,

            "name": player.name,

            "uid": player.uid

        }

    })


# ==================================================
# WALLET APIs
# ==================================================


# =========================
# GET WALLET
# =========================

@app.route(
    "/api/wallet/<uid>",
    methods=["GET"]
)
def get_wallet(uid):

    uid = str(uid).strip()


    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()


    if wallet is None:

        return jsonify({

            "success": True,

            "uid": uid,

            "balance": 0

        })


    return jsonify({

        "success": True,

        "uid": uid,

        "balance": wallet.balance

    })


# =========================
# ADMIN ADD TOKENS
# =========================

@app.route(
    "/api/admin/wallet/add",
    methods=["POST"]
)
def admin_add_tokens():

    if not session.get("admin"):

        return jsonify({

            "success": False,

            "message": "Admin login required"

        }), 403


    data = request.json or {}


    uid = str(
        data.get("uid", "")
    ).strip()


    try:

        amount = int(
            data.get("amount", 0)
        )

    except (ValueError, TypeError):

        return jsonify({

            "success": False,

            "message": "Token amount must be a number."

        }), 400


    if not uid:

        return jsonify({

            "success": False,

            "message": "Player UID is required."

        }), 400


    if amount <= 0:

        return jsonify({

            "success": False,

            "message": (
                "Token amount must be greater than 0."
            )

        }), 400


    # =========================
    # GET OR CREATE WALLET
    # =========================

    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()


    if wallet is None:

        wallet = Wallet(

            player_uid=uid,

            balance=0

        )

        db.session.add(
            wallet
        )


    # =========================
    # ADD TOKENS
    # =========================

    wallet.balance += amount


    transaction = TokenTransaction(

        player_uid=uid,

        amount=amount,

        transaction_type="CREDIT",

        description="Admin token credit"

    )


    db.session.add(
        transaction
    )

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tokens added successfully.",

        "uid": uid,

        "balance": wallet.balance

    })


# =========================
# ADMIN REMOVE TOKENS
# =========================

@app.route(
    "/api/admin/wallet/remove",
    methods=["POST"]
)
def admin_remove_tokens():

    if not session.get("admin"):

        return jsonify({

            "success": False,

            "message": "Admin login required"

        }), 403


    data = request.json or {}


    uid = str(
        data.get("uid", "")
    ).strip()


    try:

        amount = int(
            data.get("amount", 0)
        )

    except (ValueError, TypeError):

        return jsonify({

            "success": False,

            "message": "Token amount must be a number."

        }), 400


    if not uid:

        return jsonify({

            "success": False,

            "message": "Player UID is required."

        }), 400


    if amount <= 0:

        return jsonify({

            "success": False,

            "message": (
                "Token amount must be greater than 0."
            )

        }), 400


    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()


    if wallet is None:

        return jsonify({

            "success": False,

            "message": "Wallet not found."

        }), 404


    if wallet.balance < amount:

        return jsonify({

            "success": False,

            "message": "Insufficient token balance."

        }), 400


    # =========================
    # REMOVE TOKENS
    # =========================

    wallet.balance -= amount


    transaction = TokenTransaction(

        player_uid=uid,

        amount=-amount,

        transaction_type="DEBIT",

        description="Admin token debit"

    )


    db.session.add(
        transaction
    )

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tokens removed successfully.",

        "uid": uid,

        "balance": wallet.balance

    })


# =========================
# TOKEN HISTORY
# =========================

@app.route(
    "/api/wallet/<uid>/transactions",
    methods=["GET"]
)
def wallet_transactions(uid):

    uid = str(uid).strip()


    transactions = TokenTransaction.query.filter_by(

        player_uid=uid

    ).order_by(

        TokenTransaction.id.desc()

    ).all()


    result = []


    for transaction in transactions:

        result.append({

            "id": transaction.id,

            "amount": transaction.amount,

            "type": transaction.transaction_type,

            "description": transaction.description,

            "created_at": (
                transaction.created_at.isoformat()
                if transaction.created_at
                else None
            )

        })


    return jsonify({

        "success": True,

        "uid": uid,

        "transactions": result

    })


# ==================================================
# PLAYER RESULT
# ==================================================


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


    try:

        kills = int(
            data.get("kills", 0)
        )

        position = int(
            data.get("position", 0)
        )

    except (ValueError, TypeError):

        return jsonify({

            "success": False,

            "message": (
                "Kills and position "
                "must be numbers."
            )

        }), 400


    if kills < 0 or position < 0:

        return jsonify({

            "success": False,

            "message": (
                "Kills and position "
                "cannot be negative."
            )

        }), 400


    player.kills = kills

    player.position = position

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Player result updated."

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
