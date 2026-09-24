from datetime import datetime
import os

from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_

from tournaments import (
    db,
    Tournament,
    Player,
    Wallet,
    TokenTransaction,
    User,
    UserTournamentRegistration,
    AdminAccount
)


# =========================
# FLASK APP
# =========================

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql://",
            1
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tournament.db"


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

db.init_app(app)


# =========================
# DATABASE INITIALIZATION
# =========================

with app.app_context():

    db.create_all()

    # Agar admin account pehle se nahi hai
    # to default admin create hoga.
    admin = AdminAccount.query.filter_by(
        username="admin"
    ).first()

    if admin is None:

        admin = AdminAccount(
            username="admin",
            password_hash=generate_password_hash("1234")
        )

        db.session.add(admin)
        db.session.commit()


# =========================
# HELPER FUNCTIONS
# =========================

def is_admin_logged_in():
    return bool(session.get("admin_id"))


def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id
    )


# =========================
# HOME
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


# =========================================================
# PLAYER SIGNUP
# =========================================================

@app.route("/api/auth/signup", methods=["POST"])
def signup():

    data = request.get_json() or {}

    username = str(
        data.get("username", "")
    ).strip().lower()

    email = str(
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    confirm_password = str(
        data.get("confirm_password", "")
    )

    uid = str(
        data.get("uid", "")
    ).strip()


    # -------------------------
    # BASIC VALIDATION
    # -------------------------

    if not username:
        return jsonify({
            "success": False,
            "message": "Username required."
        }), 400


    if not email:
        return jsonify({
            "success": False,
            "message": "Email required."
        }), 400


    if not password:
        return jsonify({
            "success": False,
            "message": "Password required."
        }), 400


    if not confirm_password:
        return jsonify({
            "success": False,
            "message": "Confirm password required."
        }), 400


    if not uid:
        return jsonify({
            "success": False,
            "message": "Free Fire UID required."
        }), 400


    if len(username) < 3:
        return jsonify({
            "success": False,
            "message": "Username minimum 3 characters ka hona chahiye."
        }), 400


    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password minimum 6 characters ka hona chahiye."
        }), 400


    if password != confirm_password:
        return jsonify({
            "success": False,
            "message": "Passwords match nahi kar rahe."
        }), 400


    # -------------------------
    # DUPLICATE USERNAME
    # -------------------------

    existing_username = User.query.filter_by(
        username=username
    ).first()

    if existing_username:

        return jsonify({
            "success": False,
            "message": "Ye username already registered hai."
        }), 400


    # -------------------------
    # DUPLICATE EMAIL
    # -------------------------

    existing_email = User.query.filter_by(
        email=email
    ).first()

    if existing_email:

        return jsonify({
            "success": False,
            "message": "Ye email already registered hai."
        }), 400


    # -------------------------
    # DUPLICATE FREE FIRE UID
    # -------------------------

    existing_uid = User.query.filter_by(
        uid=uid
    ).first()

    if existing_uid:

        return jsonify({
            "success": False,
            "message": "Ye Free Fire UID already kisi account me registered hai."
        }), 400


    # -------------------------
    # CREATE USER
    # -------------------------

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        uid=uid
    )

    db.session.add(user)

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Account create nahi ho paya."
        }), 500


    # Automatically login
    session["user_id"] = user.id
    session["username"] = user.username


    return jsonify({
        "success": True,
        "message": "Account successfully create ho gaya.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "uid": user.uid
        }
    })


# =========================================================
# PLAYER LOGIN
# =========================================================

@app.route("/api/auth/login", methods=["POST"])
def login():

    data = request.get_json() or {}

    identifier = str(
        data.get("identifier", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )


    if not identifier or not password:

        return jsonify({
            "success": False,
            "message": "Username/email aur password required hai."
        }), 400


    user = User.query.filter(
        or_(
            User.username == identifier,
            User.email == identifier
        )
    ).first()


    if user is None:

        return jsonify({
            "success": False,
            "message": "Account nahi mila."
        }), 401


    if not check_password_hash(
        user.password_hash,
        password
    ):

        return jsonify({
            "success": False,
            "message": "Password galat hai."
        }), 401


    session["user_id"] = user.id
    session["username"] = user.username


    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "uid": user.uid
        }
    })


# =========================================================
# PLAYER LOGOUT
# =========================================================

@app.route("/api/auth/logout", methods=["POST"])
def logout():

    session.pop("user_id", None)
    session.pop("username", None)

    return jsonify({
        "success": True,
        "message": "Logout successful."
    })


# =========================================================
# CURRENT PLAYER ACCOUNT
# =========================================================

@app.route("/api/auth/me", methods=["GET"])
def current_account():

    user = get_current_user()

    if user is None:

        return jsonify({
            "success": False,
            "logged_in": False
        })


    return jsonify({
        "success": True,
        "logged_in": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "uid": user.uid
        }
    })


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin-login", methods=["POST"])
def admin_login():

    data = request.get_json() or {}

    username = str(
        data.get("username", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )


    if not username or not password:

        return jsonify({
            "success": False,
            "message": "Username aur password required hai."
        }), 400


    admin = AdminAccount.query.filter_by(
        username=username
    ).first()


    if admin is None:

        return jsonify({
            "success": False,
            "message": "Admin account nahi mila."
        }), 401


    if not check_password_hash(
        admin.password_hash,
        password
    ):

        return jsonify({
            "success": False,
            "message": "Admin password galat hai."
        }), 401


    session["admin_id"] = admin.id
    session["admin_username"] = admin.username


    return jsonify({
        "success": True,
        "message": "Admin login successful."
    })


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin_id", None)
    session.pop("admin_username", None)

    return redirect("/admin")


# =========================================================
# ADMIN CHANGE PASSWORD
# =========================================================

@app.route("/api/admin/change-password", methods=["POST"])
def change_admin_password():

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    data = request.get_json() or {}

    current_password = str(
        data.get("current_password", "")
    )

    new_password = str(
        data.get("new_password", "")
    )

    confirm_password = str(
        data.get("confirm_password", "")
    )


    if not current_password:

        return jsonify({
            "success": False,
            "message": "Current password required."
        }), 400


    if not new_password:

        return jsonify({
            "success": False,
            "message": "New password required."
        }), 400


    if new_password != confirm_password:

        return jsonify({
            "success": False,
            "message": "New passwords match nahi kar rahe."
        }), 400


    if len(new_password) < 6:

        return jsonify({
            "success": False,
            "message": "New password minimum 6 characters ka hona chahiye."
        }), 400


    admin = db.session.get(
        AdminAccount,
        session["admin_id"]
    )


    if admin is None:

        session.pop("admin_id", None)

        return jsonify({
            "success": False,
            "message": "Admin account nahi mila."
        }), 401


    # Old password verify
    if not check_password_hash(
        admin.password_hash,
        current_password
    ):

        return jsonify({
            "success": False,
            "message": "Current password galat hai."
        }), 400


    # New password save
    admin.password_hash = generate_password_hash(
        new_password
    )

    db.session.commit()


    return jsonify({
        "success": True,
        "message": "Admin password successfully change ho gaya."
    })


# =========================================================
# GET ALL TOURNAMENTS
# =========================================================

@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():

    tournaments = Tournament.query.order_by(
        Tournament.id.desc()
    ).all()


    user = get_current_user()


    result = []


    for tournament in tournaments:

        registered = False


        if user:

            existing_registration = UserTournamentRegistration.query.filter_by(
                user_id=user.id,
                tournament_id=tournament.id
            ).first()


            if existing_registration:

                registered = True


        result.append({

            "id": tournament.id,

            "name": tournament.name,

            "entry_fee": tournament.entry_fee,

            "max_players": tournament.max_players,

            "kill_reward": tournament.kill_reward,

            "first_prize": tournament.first_prize,

            "date_time": tournament.date_time,

            "registered": registered
        })


    return jsonify(result)


# =========================================================
# CREATE TOURNAMENT
# =========================================================

@app.route("/api/tournaments", methods=["POST"])
def create_tournament():

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    data = request.get_json() or {}


    name = str(
        data.get("name", "")
    ).strip()

    date_time = str(
        data.get("date_time", "")
    ).strip()


    try:

        entry_fee = int(
            data.get("entry_fee", 0)
        )

        max_players = int(
            data.get("max_players", 0)
        )

        kill_reward = int(
            data.get("kill_reward", 0)
        )

        first_prize = int(
            data.get("first_prize", 0)
        )

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message": "Numeric values galat hain."
        }), 400


    if not name:

        return jsonify({
            "success": False,
            "message": "Tournament name required."
        }), 400


    if not date_time:

        return jsonify({
            "success": False,
            "message": "Tournament date/time required."
        }), 400


    if entry_fee < 0:

        return jsonify({
            "success": False,
            "message": "Entry fee negative nahi ho sakti."
        }), 400


    if max_players <= 0:

        return jsonify({
            "success": False,
            "message": "Max players 0 se zyada hona chahiye."
        }), 400


    if kill_reward < 0 or first_prize < 0:

        return jsonify({
            "success": False,
            "message": "Prize negative nahi ho sakta."
        }), 400


    tournament = Tournament(

        name=name,

        entry_fee=entry_fee,

        max_players=max_players,

        kill_reward=kill_reward,

        first_prize=first_prize,

        date_time=date_time
    )


    db.session.add(tournament)
    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tournament successfully create ho gaya.",

        "tournament": {
            "id": tournament.id,
            "name": tournament.name,
            "entry_fee": tournament.entry_fee,
            "max_players": tournament.max_players,
            "kill_reward": tournament.kill_reward,
            "first_prize": tournament.first_prize,
            "date_time": tournament.date_time
        }
    })


# =========================================================
# DELETE TOURNAMENT
# =========================================================

@app.route("/api/tournaments/<int:tournament_id>", methods=["DELETE"])
def delete_tournament(tournament_id):

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    tournament = db.session.get(
        Tournament,
        tournament_id
    )


    if tournament is None:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404


    # Pehle user registrations delete
    UserTournamentRegistration.query.filter_by(
        tournament_id=tournament_id
    ).delete(
        synchronize_session=False
    )


    # Phir players delete
    Player.query.filter_by(
        tournament_id=tournament_id
    ).delete(
        synchronize_session=False
    )


    # Finally tournament delete
    db.session.delete(tournament)

    db.session.commit()


    return jsonify({
        "success": True,
        "message": "Tournament successfully delete ho gaya."
    })


# =========================================================
# REGISTER PLAYER
# =========================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/players",
    methods=["POST"]
)
def register_player(tournament_id):

    # Login required
    user = get_current_user()


    if user is None:

        return jsonify({
            "success": False,
            "message": "Pehle login karo."
        }), 401


    tournament = db.session.get(
        Tournament,
        tournament_id
    )


    if tournament is None:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404


    # -------------------------
    # DATE CHECK
    # -------------------------

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


    data = request.get_json() or {}


    name = str(
        data.get("name", "")
    ).strip()


    requested_uid = str(
        data.get("uid", "")
    ).strip()


    if not name:

        return jsonify({
            "success": False,
            "message": "Player name required."
        }), 400


    # Account ka UID hi use hoga.
    # Koi dusra UID submit nahi kar sakta.

    if requested_uid and requested_uid != user.uid:

        return jsonify({
            "success": False,
            "message": "Aap sirf apne account wale Free Fire UID se register kar sakte ho."
        }), 400


    uid = user.uid


    # -------------------------
    # SAME ACCOUNT CHECK
    # -------------------------

    already_registered = UserTournamentRegistration.query.filter_by(

        user_id=user.id,

        tournament_id=tournament_id

    ).first()


    if already_registered:

        return jsonify({
            "success": False,
            "message": "Aap is tournament me already registered ho."
        }), 400


    # -------------------------
    # SAME UID CHECK
    # -------------------------

    existing_player = Player.query.filter_by(

        tournament_id=tournament_id,

        uid=uid

    ).first()


    if existing_player:

        return jsonify({
            "success": False,
            "message": "Ye UID is tournament ka slot already book kar chuki hai."
        }), 400


    # -------------------------
    # MAX PLAYERS CHECK
    # -------------------------

    current_players = Player.query.filter_by(
        tournament_id=tournament_id
    ).count()


    if current_players >= tournament.max_players:

        return jsonify({
            "success": False,
            "message": "Tournament ke saare slots full ho gaye hain."
        }), 400


    # -------------------------
    # CREATE PLAYER
    # -------------------------

    player = Player(

        name=name,

        uid=uid,

        kills=0,

        position=0,

        tournament_id=tournament_id
    )


    db.session.add(player)

    db.session.flush()


    # -------------------------
    # CREATE USER REGISTRATION
    # -------------------------

    registration = UserTournamentRegistration(

        user_id=user.id,

        tournament_id=tournament_id,

        player_id=player.id
    )


    db.session.add(registration)

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tournament registration successful.",

        "player": {

            "id": player.id,

            "name": player.name,

            "uid": player.uid,

            "tournament_id": player.tournament_id
        }
    })


# =========================================================
# WALLET - GET BALANCE
# =========================================================

@app.route("/api/wallet/<uid>", methods=["GET"])
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


# =========================================================
# ADMIN WALLET ADD
# =========================================================

@app.route(
    "/api/admin/wallet/add",
    methods=["POST"]
)
def add_wallet_tokens():

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    data = request.get_json() or {}


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
            "message": "Token amount invalid."
        }), 400


    if not uid:

        return jsonify({
            "success": False,
            "message": "UID required."
        }), 400


    if amount <= 0:

        return jsonify({
            "success": False,
            "message": "Amount 0 se zyada hona chahiye."
        }), 400


    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()


    if wallet is None:

        wallet = Wallet(
            player_uid=uid,
            balance=0
        )

        db.session.add(wallet)


    wallet.balance += amount


    transaction = TokenTransaction(

        player_uid=uid,

        amount=amount,

        transaction_type="ADD",

        description="Admin added tokens"
    )


    db.session.add(transaction)

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tokens successfully added.",

        "uid": uid,

        "balance": wallet.balance
    })


# =========================================================
# ADMIN WALLET REMOVE
# =========================================================

@app.route(
    "/api/admin/wallet/remove",
    methods=["POST"]
)
def remove_wallet_tokens():

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    data = request.get_json() or {}


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
            "message": "Token amount invalid."
        }), 400


    if not uid:

        return jsonify({
            "success": False,
            "message": "UID required."
        }), 400


    if amount <= 0:

        return jsonify({
            "success": False,
            "message": "Amount 0 se zyada hona chahiye."
        }), 400


    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()


    if wallet is None:

        return jsonify({

            "success": False,

            "message": "Wallet nahi mila."
        }), 404


    if wallet.balance < amount:

        return jsonify({

            "success": False,

            "message": "Wallet me enough tokens nahi hain."
        }), 400


    wallet.balance -= amount


    transaction = TokenTransaction(

        player_uid=uid,

        amount=-amount,

        transaction_type="REMOVE",

        description="Admin removed tokens"
    )


    db.session.add(transaction)

    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Tokens successfully removed.",

        "uid": uid,

        "balance": wallet.balance
    })


# =========================================================
# WALLET TRANSACTIONS
# =========================================================

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

            "transaction_type": transaction.transaction_type,

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


# =========================================================
# UPDATE PLAYER RESULT
# =========================================================

@app.route(
    "/api/players/<int:player_id>",
    methods=["PUT"]
)
def update_player(player_id):

    if not is_admin_logged_in():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401


    player = db.session.get(
        Player,
        player_id
    )


    if player is None:

        return jsonify({
            "success": False,
            "message": "Player nahi mila."
        }), 404


    data = request.get_json() or {}


    try:

        kills = int(
            data.get("kills", player.kills)
        )

        position = int(
            data.get("position", player.position)
        )

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message": "Kills/position invalid hai."
        }), 400


    if kills < 0:

        kills = 0


    if position < 0:

        position = 0


    player.kills = kills
    player.position = position


    db.session.commit()


    return jsonify({

        "success": True,

        "message": "Player result updated.",

        "player": {

            "id": player.id,

            "name": player.name,

            "uid": player.uid,

            "kills": player.kills,

            "position": player.position,

            "tournament_id": player.tournament_id
        }
    })


# =========================================================
# GET PLAYERS OF TOURNAMENT
# =========================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/players",
    methods=["GET"]
)
def get_tournament_players(tournament_id):

    tournament = db.session.get(
        Tournament,
        tournament_id
    )


    if tournament is None:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404


    players = Player.query.filter_by(

        tournament_id=tournament_id

    ).order_by(

        Player.position.asc(),

        Player.kills.desc()

    ).all()


    result = []


    for player in players:

        result.append({

            "id": player.id,

            "name": player.name,

            "uid": player.uid,

            "kills": player.kills,

            "position": player.position,

            "tournament_id": player.tournament_id
        })


    return jsonify({

        "success": True,

        "tournament_id": tournament_id,

        "players": result
    })


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )
