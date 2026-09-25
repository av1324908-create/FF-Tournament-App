from datetime import datetime
import os

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

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


app = Flask(__name__)

# =========================
# DATABASE
# =========================

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

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///tournament.db"
    )


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

db.init_app(app)


# =========================
# DATABASE INIT
# =========================

with app.app_context():

    db.create_all()

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
# HELPERS
# =========================

def admin_required():

    if not session.get("admin_logged_in"):
        return False

    return True


def current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(User, user_id)


def parse_tournament_date(value):

    if not value:
        return None

    formats = [
        "%d/%m/%y %H:%M",
        "%d-%m-%y %H:%M"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(value, fmt)

        except ValueError:
            pass

    return None


# =========================
# HOME
# =========================

@app.route("/")
def home():

    return render_template("index.html")


@app.route("/admin")
def admin_page():

    return render_template("admin.html")


# =========================
# USER SIGNUP
# =========================

@app.route("/api/auth/signup", methods=["POST"])
def signup():

    data = request.get_json() or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get(
        "confirm_password",
        ""
    )
    uid = data.get("uid", "").strip()

    if not username or not email or not password or not uid:

        return jsonify({
            "success": False,
            "message": "Sabhi fields bharna zaroori hai."
        }), 400

    if len(username) < 3:

        return jsonify({
            "success": False,
            "message": "Username kam se kam 3 characters ka ho."
        }), 400

    if len(password) < 6:

        return jsonify({
            "success": False,
            "message": "Password kam se kam 6 characters ka ho."
        }), 400

    if password != confirm_password:

        return jsonify({
            "success": False,
            "message": "Passwords match nahi kar rahe."
        }), 400

    if User.query.filter_by(
        username=username
    ).first():

        return jsonify({
            "success": False,
            "message": "Username already registered hai."
        }), 400

    if User.query.filter_by(
        email=email
    ).first():

        return jsonify({
            "success": False,
            "message": "Email already registered hai."
        }), 400

    if User.query.filter_by(
        uid=uid
    ).first():

        return jsonify({
            "success": False,
            "message": "Ye Free Fire UID already registered hai."
        }), 400

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        uid=uid
    )

    db.session.add(user)
    db.session.commit()

    session["user_id"] = user.id

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


# =========================
# USER LOGIN
# =========================

@app.route("/api/auth/login", methods=["POST"])
def login():

    data = request.get_json() or {}

    login_value = data.get(
        "login",
        ""
    ).strip()

    password = data.get(
        "password",
        ""
    )

    if not login_value or not password:

        return jsonify({
            "success": False,
            "message": "Username/email aur password bharo."
        }), 400

    user = User.query.filter(
        (User.username == login_value) |
        (User.email == login_value.lower())
    ).first()

    if not user:

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


# =========================
# USER LOGOUT
# =========================

@app.route("/api/auth/logout")
def user_logout():

    session.pop("user_id", None)

    return jsonify({
        "success": True
    })


# =========================
# CURRENT USER
# =========================

@app.route("/api/auth/me")
def auth_me():

    user = current_user()

    if not user:

        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "uid": user.uid
        }
    })


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin-login", methods=["POST"])
def admin_login():

    data = request.get_json() or {}

    username = data.get(
        "username",
        ""
    ).strip()

    password = data.get(
        "password",
        ""
    )

    admin = AdminAccount.query.filter_by(
        username=username
    ).first()

    if not admin:

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
            "message": "Password galat hai."
        }), 401

    session["admin_logged_in"] = True
    session["admin_id"] = admin.id

    return jsonify({
        "success": True,
        "message": "Admin login successful."
    })


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin_logged_in", None)
    session.pop("admin_id", None)

    return jsonify({
        "success": True
    })


# =========================
# CHANGE ADMIN PASSWORD
# =========================

@app.route(
    "/api/admin/change-password",
    methods=["POST"]
)
def change_admin_password():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    data = request.get_json() or {}

    current_password = data.get(
        "current_password",
        ""
    )

    new_password = data.get(
        "new_password",
        ""
    )

    confirm_password = data.get(
        "confirm_password",
        ""
    )

    admin = db.session.get(
        AdminAccount,
        session.get("admin_id")
    )

    if not admin:

        return jsonify({
            "success": False,
            "message": "Admin account nahi mila."
        }), 404

    if not check_password_hash(
        admin.password_hash,
        current_password
    ):

        return jsonify({
            "success": False,
            "message": "Current password galat hai."
        }), 400

    if len(new_password) < 6:

        return jsonify({
            "success": False,
            "message": "New password kam se kam 6 characters ka ho."
        }), 400

    if new_password != confirm_password:

        return jsonify({
            "success": False,
            "message": "New passwords match nahi kar rahe."
        }), 400

    admin.password_hash = generate_password_hash(
        new_password
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Admin password successfully change ho gaya."
    })


# =========================
# GET TOURNAMENTS
# =========================

@app.route("/api/tournaments")
def get_tournaments():

    tournaments = Tournament.query.order_by(
        Tournament.id.desc()
    ).all()

    user = current_user()

    result = []

    for t in tournaments:

        players = Player.query.filter_by(
            tournament_id=t.id
        ).all()

        registered = False

        if user:

            registration = UserTournamentRegistration.query.filter_by(
                user_id=user.id,
                tournament_id=t.id
            ).first()

            if registration:
                registered = True

        result.append({
            "id": t.id,
            "name": t.name,
            "entry_fee": t.entry_fee,
            "max_players": t.max_players,
            "kill_reward": t.kill_reward,
            "first_prize": t.first_prize,
            "date_time": t.date_time,
            "room_id": t.room_id or "",
            "room_password": (
                t.room_password or ""
            ) if registered else "",
            "registered": registered,

            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "uid": p.uid,
                    "kills": p.kills or 0,
                    "position": p.position or 0
                }
                for p in players
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
def create_tournament():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    data = request.get_json() or {}

    tournament = Tournament(

        name=data.get(
            "name",
            ""
        ).strip(),

        entry_fee=int(
            data.get(
                "entry_fee",
                0
            )
        ),

        max_players=int(
            data.get(
                "max_players",
                0
            )
        ),

        kill_reward=int(
            data.get(
                "kill_reward",
                0
            )
        ),

        first_prize=int(
            data.get(
                "first_prize",
                0
            )
        ),

        date_time=data.get(
            "date_time",
            ""
        ).strip(),

        room_id="",

        room_password=""
    )

    if not tournament.name:

        return jsonify({
            "success": False,
            "message": "Tournament name required."
        }), 400

    db.session.add(tournament)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Tournament created.",
        "id": tournament.id
    })


# =========================
# DELETE TOURNAMENT
# =========================

@app.route(
    "/api/tournaments/<int:tournament_id>",
    methods=["DELETE"]
)
def delete_tournament(tournament_id):

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    tournament = db.session.get(
        Tournament,
        tournament_id
    )

    if not tournament:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404

    UserTournamentRegistration.query.filter_by(
        tournament_id=tournament_id
    ).delete(
        synchronize_session=False
    )

    Player.query.filter_by(
        tournament_id=tournament_id
    ).delete(
        synchronize_session=False
    )

    db.session.delete(tournament)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Tournament deleted."
    })


# =========================
# UPDATE ROOM DETAILS
# =========================

@app.route(
    "/api/admin/tournaments/<int:tournament_id>/room",
    methods=["POST"]
)
def update_room(tournament_id):

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    tournament = db.session.get(
        Tournament,
        tournament_id
    )

    if not tournament:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404

    data = request.get_json() or {}

    room_id = data.get(
        "room_id",
        ""
    ).strip()

    room_password = data.get(
        "room_password",
        ""
    ).strip()

    if room_id and not room_password:

        return jsonify({
            "success": False,
            "message": "Room password bhi enter karo."
        }), 400

    if room_password and not room_id:

        return jsonify({
            "success": False,
            "message": "Room ID bhi enter karo."
        }), 400

    tournament.room_id = room_id
    tournament.room_password = room_password

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Room details saved."
    })


# =========================
# GET ROOM DETAILS
# =========================

@app.route(
    "/api/tournaments/<int:tournament_id>/room"
)
def get_room_details(tournament_id):

    user = current_user()

    if not user:

        return jsonify({
            "success": False,
            "message": "Login required."
        }), 401

    tournament = db.session.get(
        Tournament,
        tournament_id
    )

    if not tournament:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404

    registration = UserTournamentRegistration.query.filter_by(
        user_id=user.id,
        tournament_id=tournament_id
    ).first()

    if not registration:

        return jsonify({
            "success": False,
            "message": "Aapne is tournament ko book nahi kiya hai."
        }), 403

    if not tournament.room_id:

        return jsonify({
            "success": True,
            "room_available": False
        })

    return jsonify({
        "success": True,
        "room_available": True,
        "room_id": tournament.room_id,
        "room_password": tournament.room_password
    })


# =========================
# REGISTER PLAYER
# =========================

@app.route(
    "/api/tournaments/<int:tournament_id>/players",
    methods=["POST"]
)
def register_player(tournament_id):

    user = current_user()

    if not user:

        return jsonify({
            "success": False,
            "message": "Tournament join karne ke liye pehle login karo."
        }), 401

    tournament = db.session.get(
        Tournament,
        tournament_id
    )

    if not tournament:

        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404

    tournament_date = parse_tournament_date(
        tournament.date_time
    )

    if not tournament_date:

        return jsonify({
            "success": False,
            "message": "Tournament date/time invalid hai."
        }), 400

    if tournament_date <= datetime.now():

        return jsonify({
            "success": False,
            "message": "Tournament registration is closed."
        }), 400

    data = request.get_json() or {}

    name = data.get(
        "name",
        ""
    ).strip()

    uid = data.get(
        "uid",
        ""
    ).strip()

    if not name:

        return jsonify({
            "success": False,
            "message": "Player name required."
        }), 400

    # Account ka linked UID hi use hoga
    if uid != user.uid:

        return jsonify({
            "success": False,
            "message": "Aap sirf apne account wale UID se register kar sakte ho."
        }), 400

    existing_registration = UserTournamentRegistration.query.filter_by(
        user_id=user.id,
        tournament_id=tournament_id
    ).first()

    if existing_registration:

        return jsonify({
            "success": False,
            "message": "Aap already is tournament mein registered ho."
        }), 400

    existing_uid = Player.query.filter_by(
        tournament_id=tournament_id,
        uid=user.uid
    ).first()

    if existing_uid:

        return jsonify({
            "success": False,
            "message": "Ye UID already is tournament mein registered hai."
        }), 400

    current_players = Player.query.filter_by(
        tournament_id=tournament_id
    ).count()

    if (
        tournament.max_players > 0
        and current_players >= tournament.max_players
    ):

        return jsonify({
            "success": False,
            "message": "Tournament full hai."
        }), 400

    player = Player(
        name=name,
        uid=user.uid,
        tournament_id=tournament_id
    )

    db.session.add(player)
    db.session.flush()

    registration = UserTournamentRegistration(
        user_id=user.id,
        tournament_id=tournament_id,
        player_id=player.id
    )

    db.session.add(registration)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Registration successful!"
    })


# =========================
# GET TOURNAMENT PLAYERS
# =========================

@app.route(
    "/api/tournaments/<int:tournament_id>/players"
)
def tournament_players(tournament_id):

    players = Player.query.filter_by(
        tournament_id=tournament_id
    ).all()

    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "uid": p.uid,
            "kills": p.kills or 0,
            "position": p.position or 0
        }
        for p in players
    ])


# =========================
# UPDATE PLAYER RESULT
# =========================

@app.route(
    "/api/players/<int:player_id>",
    methods=["PUT"]
)
def update_player(player_id):

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    player = db.session.get(
        Player,
        player_id
    )

    if not player:

        return jsonify({
            "success": False,
            "message": "Player nahi mila."
        }), 404

    data = request.get_json() or {}

    try:

        player.kills = int(
            data.get(
                "kills",
                0
            )
        )

        player.position = int(
            data.get(
                "position",
                0
            )
        )

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "message": "Invalid result."
        }), 400

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Player result saved."
    })


# =========================
# WALLET GET
# =========================

@app.route(
    "/api/wallet/<uid>"
)
def get_wallet(uid):

    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()

    if not wallet:

        return jsonify({
            "success": True,
            "balance": 0
        })

    return jsonify({
        "success": True,
        "balance": wallet.balance
    })


# =========================
# ADD WALLET TOKENS
# =========================

@app.route(
    "/api/admin/wallet/add",
    methods=["POST"]
)
def add_wallet():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    data = request.get_json() or {}

    uid = data.get(
        "uid",
        ""
    ).strip()

    try:

        amount = int(
            data.get(
                "amount",
                0
            )
        )

    except (ValueError, TypeError):

        amount = 0

    if not uid or amount <= 0:

        return jsonify({
            "success": False,
            "message": "Valid UID aur amount enter karo."
        }), 400

    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()

    if not wallet:

        wallet = Wallet(
            player_uid=uid,
            balance=0
        )

        db.session.add(wallet)

    wallet.balance += amount

    transaction = TokenTransaction(
        player_uid=uid,
        amount=amount,
        transaction_type="credit",
        description="Admin added tokens"
    )

    db.session.add(transaction)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Tokens added.",
        "balance": wallet.balance
    })


# =========================
# REMOVE WALLET TOKENS
# =========================

@app.route(
    "/api/admin/wallet/remove",
    methods=["POST"]
)
def remove_wallet():

    if not admin_required():

        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    data = request.get_json() or {}

    uid = data.get(
        "uid",
        ""
    ).strip()

    try:

        amount = int(
            data.get(
                "amount",
                0
            )
        )

    except (ValueError, TypeError):

        amount = 0

    if not uid or amount <= 0:

        return jsonify({
            "success": False,
            "message": "Valid UID aur amount enter karo."
        }), 400

    wallet = Wallet.query.filter_by(
        player_uid=uid
    ).first()

    if not wallet:

        return jsonify({
            "success": False,
            "message": "Wallet nahi mila."
        }), 404

    if wallet.balance < amount:

        return jsonify({
            "success": False,
            "message": "Itne tokens available nahi hain."
        }), 400

    wallet.balance -= amount

    transaction = TokenTransaction(
        player_uid=uid,
        amount=amount,
        transaction_type="debit",
        description="Admin removed tokens"
    )

    db.session.add(transaction)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Tokens removed.",
        "balance": wallet.balance
    })


# =========================
# WALLET TRANSACTIONS
# =========================

@app.route(
    "/api/wallet/<uid>/transactions"
)
def wallet_transactions(uid):

    transactions = TokenTransaction.query.filter_by(
        player_uid=uid
    ).order_by(
        TokenTransaction.id.desc()
    ).all()

    return jsonify([
        {
            "id": t.id,
            "amount": t.amount,
            "transaction_type": t.transaction_type,
            "description": t.description,
            "created_at": (
                t.created_at.isoformat()
                if t.created_at
                else None
            )
        }
        for t in transactions
    ])


# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
