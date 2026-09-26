from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, inspect, text

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


# =========================================================
# NOTICE BOARD MODEL
# =========================================================

class Notice(db.Model):
    __tablename__ = "notice"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# =========================================================
# REGISTRATION DETAILS + PRIVATE REDEEM CODES
# =========================================================

class RegistrationDetail(db.Model):
    __tablename__ = "registration_detail"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    tournament_id = db.Column(db.Integer, nullable=False, index=True)
    player_id = db.Column(db.Integer, nullable=False, unique=True, index=True)
    instagram_id = db.Column(db.String(100), nullable=False)
    slot_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PrivateRedeemCode(db.Model):
    __tablename__ = "private_redeem_code"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    code = db.Column(db.String(200), nullable=False, unique=True)
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used = db.Column(db.Boolean, default=False, nullable=False)


# =========================================================
# FLASK APP
# =========================================================

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


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

with app.app_context():

    db.create_all()

    # New registration/redeem tables are created without touching existing data.
    RegistrationDetail.__table__.create(bind=db.engine, checkfirst=True)
    PrivateRedeemCode.__table__.create(bind=db.engine, checkfirst=True)

    # Existing databases ko delete kiye bina new rules column add karo.
    inspector = inspect(db.engine)
    tournament_columns = {
        col["name"] for col in inspector.get_columns("tournament")
    }

    if "rules" not in tournament_columns:
        with db.engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE tournament ADD COLUMN rules TEXT")
            )

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


# =========================================================
# HELPERS
# =========================================================

def is_admin_logged_in():
    return bool(session.get("admin_id"))


def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(User, user_id)


def parse_tournament_datetime(date_string):
    """Tournament date/time ko India time (Asia/Kolkata) me parse karta hai."""
    if not date_string:
        return None

    date_string = str(date_string).strip()

    for fmt in ("%d/%m/%y %H:%M", "%d-%m-%y %H:%M"):
        try:
            naive = datetime.strptime(date_string, fmt)
            return naive.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        except (ValueError, TypeError):
            pass

    return None


def tournament_status(tournament):
    """
    Start se pehle      -> upcoming
    Start se 15 min tak -> live
    15 min ke baad      -> completed
    """
    start_time = parse_tournament_datetime(tournament.date_time)

    if start_time is None:
        return "unknown"

    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    if now < start_time:
        return "upcoming"

    if now < start_time + timedelta(minutes=15):
        return "live"

    return "completed"


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# ADMIN PAGE
# =========================================================

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


    if User.query.filter_by(username=username).first():
        return jsonify({
            "success": False,
            "message": "Ye username already registered hai."
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "Ye email already registered hai."
        }), 400

    if User.query.filter_by(uid=uid).first():
        return jsonify({
            "success": False,
            "message": "Ye Free Fire UID already kisi account me registered hai."
        }), 400


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
# CURRENT PLAYER
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


    if not check_password_hash(
        admin.password_hash,
        current_password
    ):
        return jsonify({
            "success": False,
            "message": "Current password galat hai."
        }), 400


    admin.password_hash = generate_password_hash(
        new_password
    )

    db.session.commit()


    return jsonify({
        "success": True,
        "message": "Admin password successfully change ho gaya."
    })


# =========================================================
# GET TOURNAMENTS
# =========================================================

@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():

    tournaments = Tournament.query.order_by(
        Tournament.id.desc()
    ).all()

    user = get_current_user()
    admin_view = is_admin_logged_in()

    result = []

    for tournament in tournaments:

        registered = False

        if user:
            existing_registration = UserTournamentRegistration.query.filter_by(
                user_id=user.id,
                tournament_id=tournament.id
            ).first()

            registered = existing_registration is not None

        players = Player.query.filter_by(
            tournament_id=tournament.id
        ).order_by(Player.id.asc()).all()

        status = tournament_status(tournament)

        # Admin ko results hamesha milenge.
        # Normal users ko results sirf 15 min ke baad, yani Completed par.
        show_results = admin_view or status == "completed"

        players_data = []
        if show_results:
            for p in players:
                detail = RegistrationDetail.query.filter_by(player_id=p.id).first()
                players_data.append({
                    "id": p.id,
                    "name": p.name,
                    "uid": p.uid,
                    "kills": p.kills or 0,
                    "position": p.position or 0,
                    "instagram_id": detail.instagram_id if detail else "",
                    "slot_number": detail.slot_number if detail else 0
                })

        item = {
            "id": tournament.id,
            "name": tournament.name,
            "entry_fee": tournament.entry_fee,
            "max_players": tournament.max_players,
            "kill_reward": tournament.kill_reward,
            "first_prize": tournament.first_prize,
            "date_time": tournament.date_time,
            "rules": tournament.rules or "",
            "player_count": len(players),
            "available_slots": max(0, int(tournament.max_players or 0) - len(players)),
            "registered": registered,
            "status": status,
            "results_visible": show_results,
            "players": players_data
        }

        # Room details sirf admin ya registered player ko.
        if admin_view or registered:
            item["room_id"] = tournament.room_id or ""
            item["room_password"] = tournament.room_password or ""

        result.append(item)

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

    rules = str(
        data.get("rules", "")
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
        date_time=date_time,
        rules=rules
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
            "date_time": tournament.date_time,
            "rules": tournament.rules or ""
        }
    })



# =========================================================
# EDIT TOURNAMENT
# =========================================================

@app.route("/api/tournaments/<int:tournament_id>", methods=["PUT"])
def edit_tournament(tournament_id):

    if not is_admin_logged_in():
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    tournament = db.session.get(Tournament, tournament_id)

    if tournament is None:
        return jsonify({
            "success": False,
            "message": "Tournament nahi mila."
        }), 404

    # Edit sirf upcoming tournament ka hoga.
    # Live/completed tournament ko edit karke running data disturb nahi hoga.
    if tournament_status(tournament) != "upcoming":
        return jsonify({
            "success": False,
            "message": "Live ya completed tournament edit nahi kiya ja sakta."
        }), 400

    booked_count = Player.query.filter_by(
        tournament_id=tournament_id
    ).count()

    if booked_count >= int(tournament.max_players or 0):
        return jsonify({
            "success": False,
            "message": "Is tournament ke saare slots book ho chuke hain."
        }), 400

    data = request.get_json() or {}

    name = str(data.get("name", "")).strip()
    date_time = str(data.get("date_time", "")).strip()
    rules = str(data.get("rules", "")).strip()

    try:
        entry_fee = int(data.get("entry_fee", 0))
        max_players = int(data.get("max_players", 0))
        kill_reward = int(data.get("kill_reward", 0))
        first_prize = int(data.get("first_prize", 0))
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Numeric values galat hain."
        }), 400

    if not name or not date_time:
        return jsonify({
            "success": False,
            "message": "Tournament name aur date/time required hai."
        }), 400

    if entry_fee < 0 or kill_reward < 0 or first_prize < 0:
        return jsonify({
            "success": False,
            "message": "Entry fee/prize negative nahi ho sakta."
        }), 400

    # Existing booked slots ko kabhi bhi max players se kam nahi karenge.
    if max_players < booked_count:
        return jsonify({
            "success": False,
            "message": f"Already {booked_count} slots booked hain. Max players kam nahi kar sakte."
        }), 400

    if max_players <= 0:
        return jsonify({
            "success": False,
            "message": "Max players 0 se zyada hona chahiye."
        }), 400

    tournament.name = name
    tournament.entry_fee = entry_fee
    tournament.max_players = max_players
    tournament.kill_reward = kill_reward
    tournament.first_prize = first_prize
    tournament.date_time = date_time
    tournament.rules = rules

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Tournament successfully update ho gaya.",
        "tournament": {
            "id": tournament.id,
            "name": tournament.name,
            "entry_fee": tournament.entry_fee,
            "max_players": tournament.max_players,
            "kill_reward": tournament.kill_reward,
            "first_prize": tournament.first_prize,
            "date_time": tournament.date_time,
            "rules": tournament.rules or ""
        }
    })


# =========================================================
# NOTICE BOARD
# =========================================================

@app.route("/api/notices", methods=["GET"])
def get_public_notices():

    notices = Notice.query.filter_by(
        active=True
    ).order_by(
        Notice.id.desc()
    ).all()

    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "created_at": n.created_at.isoformat() if n.created_at else None
        }
        for n in notices
    ])


@app.route("/api/admin/notices", methods=["GET"])
def get_admin_notices():

    if not is_admin_logged_in():
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    notices = Notice.query.order_by(
        Notice.id.desc()
    ).all()

    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "active": n.active,
            "created_at": n.created_at.isoformat() if n.created_at else None
        }
        for n in notices
    ])


@app.route("/api/admin/notices", methods=["POST"])
def create_notice():

    if not is_admin_logged_in():
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    data = request.get_json() or {}

    title = str(data.get("title", "")).strip()
    message = str(data.get("message", "")).strip()
    active = bool(data.get("active", True))

    if not title:
        return jsonify({
            "success": False,
            "message": "Notice title required."
        }), 400

    if not message:
        return jsonify({
            "success": False,
            "message": "Notice message required."
        }), 400

    notice = Notice(
        title=title,
        message=message,
        active=active
    )

    db.session.add(notice)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notice successfully add ho gaya.",
        "notice": {
            "id": notice.id,
            "title": notice.title,
            "message": notice.message,
            "active": notice.active
        }
    })


@app.route("/api/admin/notices/<int:notice_id>", methods=["PUT"])
def update_notice(notice_id):

    if not is_admin_logged_in():
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    notice = db.session.get(Notice, notice_id)

    if notice is None:
        return jsonify({
            "success": False,
            "message": "Notice nahi mila."
        }), 404

    data = request.get_json() or {}

    title = str(data.get("title", notice.title)).strip()
    message = str(data.get("message", notice.message)).strip()
    active = bool(data.get("active", notice.active))

    if not title or not message:
        return jsonify({
            "success": False,
            "message": "Title aur message required hain."
        }), 400

    notice.title = title
    notice.message = message
    notice.active = active

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notice successfully update ho gaya."
    })


@app.route("/api/admin/notices/<int:notice_id>", methods=["DELETE"])
def delete_notice(notice_id):

    if not is_admin_logged_in():
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    notice = db.session.get(Notice, notice_id)

    if notice is None:
        return jsonify({
            "success": False,
            "message": "Notice nahi mila."
        }), 404

    db.session.delete(notice)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Notice delete ho gaya."
    })


# =========================================================
# ADMIN SAVE ROOM DETAILS
# =========================================================

@app.route(
    "/api/admin/tournaments/<int:tournament_id>/room",
    methods=["POST"]
)
def save_room_details(tournament_id):

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

    data = request.get_json() or {}

    tournament.room_id = str(
        data.get("room_id", "")
    ).strip()

    tournament.room_password = str(
        data.get("room_password", "")
    ).strip()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Room details successfully save ho gaye."
    })


# =========================================================
# DELETE TOURNAMENT
# =========================================================

@app.route(
    "/api/tournaments/<int:tournament_id>",
    methods=["DELETE"]
)
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
        "message": "Tournament successfully delete ho gaya."
    })


# =========================================================
# REGISTER PLAYER + TOKEN PAYMENT
# =========================================================

@app.route(
    "/api/tournaments/<int:tournament_id>/players",
    methods=["POST"]
)
def register_player(tournament_id):

    user = get_current_user()
    if user is None:
        return jsonify({"success": False, "message": "Pehle login karo."}), 401

    tournament = db.session.get(Tournament, tournament_id)
    if tournament is None:
        return jsonify({"success": False, "message": "Tournament nahi mila."}), 404

    tournament_date = parse_tournament_datetime(tournament.date_time)
    if tournament_date is None:
        return jsonify({"success": False, "message": "Tournament date/time is invalid."}), 400

    if tournament_date <= datetime.now(ZoneInfo("Asia/Kolkata")):
        return jsonify({"success": False, "message": "Tournament registration is closed."}), 400

    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    requested_uid = str(data.get("uid", "")).strip()
    instagram_id = str(data.get("instagram_id", "")).strip()

    try:
        slot_number = int(data.get("slot_number", 0))
    except (ValueError, TypeError):
        slot_number = 0

    if not name:
        return jsonify({"success": False, "message": "Player name required."}), 400

    if requested_uid and requested_uid != user.uid:
        return jsonify({"success": False, "message": "Sirf apne account wale UID se register kar sakte ho."}), 400

    if not instagram_id:
        return jsonify({"success": False, "message": "Instagram ID required."}), 400

    instagram_id = instagram_id.lstrip("@").strip()
    if not instagram_id:
        return jsonify({"success": False, "message": "Valid Instagram ID required."}), 400

    if slot_number < 1 or slot_number > int(tournament.max_players or 0):
        return jsonify({"success": False, "message": "Valid slot number select karo."}), 400

    user_registration = UserTournamentRegistration.query.filter_by(
        user_id=user.id, tournament_id=tournament_id
    ).first()
    if user_registration:
        return jsonify({"success": False, "message": "Aap is tournament me already registered ho."}), 400

    existing_player = Player.query.filter_by(tournament_id=tournament_id, uid=user.uid).first()
    if existing_player:
        return jsonify({"success": False, "message": "Ye UID is tournament me already registered hai."}), 400

    existing_slot = RegistrationDetail.query.filter_by(
        tournament_id=tournament_id, slot_number=slot_number
    ).first()
    if existing_slot:
        return jsonify({"success": False, "message": f"Slot {slot_number} already booked hai. Dusra slot select karo."}), 400

    current_players = Player.query.filter_by(tournament_id=tournament_id).count()
    if current_players >= int(tournament.max_players or 0):
        return jsonify({"success": False, "message": "Tournament ke saare slots full ho gaye hain."}), 400

    entry_fee = int(tournament.entry_fee or 0)
    wallet = Wallet.query.filter_by(player_uid=user.uid).first()
    current_balance = wallet.balance if wallet is not None else 0

    if current_balance < entry_fee:
        return jsonify({
            "success": False,
            "message": f"Insufficient tokens. Entry fee: {entry_fee}, balance: {current_balance}.",
            "entry_fee": entry_fee,
            "balance": current_balance
        }), 400

    player = Player(
        name=name, uid=user.uid, kills=0, position=0, tournament_id=tournament_id
    )
    db.session.add(player)
    db.session.flush()

    registration = UserTournamentRegistration(
        user_id=user.id, tournament_id=tournament_id, player_id=player.id
    )
    db.session.add(registration)

    detail = RegistrationDetail(
        user_id=user.id,
        tournament_id=tournament_id,
        player_id=player.id,
        instagram_id=instagram_id,
        slot_number=slot_number
    )
    db.session.add(detail)

    if entry_fee > 0:
        if wallet is None:
            db.session.rollback()
            return jsonify({"success": False, "message": "Wallet error. Registration cancel kar di gayi."}), 500
        wallet.balance -= entry_fee
        db.session.add(TokenTransaction(
            player_uid=user.uid,
            amount=-entry_fee,
            transaction_type="TOURNAMENT_ENTRY",
            description=f"Entry fee for tournament: {tournament.name}"
        ))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Registration save nahi ho payi. Tokens deduct nahi hue."}), 500

    return jsonify({
        "success": True,
        "message": f"Registration successful! Slot {slot_number} booked. {entry_fee} tokens deduct hue.",
        "entry_fee": entry_fee,
        "balance": wallet.balance if wallet else 0,
        "player": {
            "id": player.id,
            "name": player.name,
            "uid": player.uid,
            "instagram_id": instagram_id,
            "slot_number": slot_number,
            "tournament_id": tournament_id
        }
    })


# =========================================================
# ADMIN DELETE PLAYER ACCOUNT
# =========================================================

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def delete_player_account(user_id):

    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin login required."}), 401

    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({"success": False, "message": "Player account nahi mila."}), 404

    try:
        # User ke tournament registrations aur unke player entries remove karo.
        registrations = UserTournamentRegistration.query.filter_by(user_id=user.id).all()
        player_ids = [r.player_id for r in registrations if r.player_id]

        if player_ids:
            RegistrationDetail.query.filter(
                RegistrationDetail.player_id.in_(player_ids)
            ).delete(synchronize_session=False)

            Player.query.filter(
                Player.id.in_(player_ids)
            ).delete(synchronize_session=False)

        UserTournamentRegistration.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        PrivateRedeemCode.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        # Wallet/transaction history UID based hai, isliye account delete ke saath
        # wallet aur uski token history bhi remove kar rahe hain.
        TokenTransaction.query.filter_by(player_uid=user.uid).delete(
            synchronize_session=False
        )

        Wallet.query.filter_by(player_uid=user.uid).delete(
            synchronize_session=False
        )

        db.session.delete(user)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Player account successfully delete ho gaya."
        })

    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Account delete karte waqt error aa gaya."
        }), 500


# =========================================================
# PRIVATE REDEEM CODES
# =========================================================

@app.route("/api/my/redeem-codes", methods=["GET"])
def my_redeem_codes():
    user = get_current_user()
    if user is None:
        return jsonify({"success": False, "message": "Login required."}), 401
    codes = PrivateRedeemCode.query.filter_by(user_id=user.id).order_by(PrivateRedeemCode.id.desc()).all()
    return jsonify({
        "success": True,
        "codes": [{
            "id": c.id,
            "code": c.code,
            "message": c.message or "",
            "used": bool(c.used),
            "created_at": c.created_at.isoformat() if c.created_at else None
        } for c in codes]
    })


@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin login required."}), 401
    users = User.query.order_by(User.id.desc()).all()
    return jsonify({
        "success": True,
        "users": [{"id": u.id, "username": u.username, "email": u.email, "uid": u.uid} for u in users]
    })


@app.route("/api/admin/redeem-codes", methods=["GET", "POST"])
def admin_redeem_codes():
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin login required."}), 401

    if request.method == "GET":
        codes = PrivateRedeemCode.query.order_by(PrivateRedeemCode.id.desc()).all()
        result = []
        for c in codes:
            u = db.session.get(User, c.user_id)
            result.append({
                "id": c.id, "user_id": c.user_id,
                "username": u.username if u else "Unknown",
                "uid": u.uid if u else "",
                "code": c.code, "message": c.message or "",
                "used": bool(c.used),
                "created_at": c.created_at.isoformat() if c.created_at else None
            })
        return jsonify({"success": True, "codes": result})

    data = request.get_json() or {}
    try:
        user_id = int(data.get("user_id"))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid player select karo."}), 400

    code = str(data.get("code", "")).strip()
    message = str(data.get("message", "")).strip()
    if not code:
        return jsonify({"success": False, "message": "Redeem code required."}), 400

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"success": False, "message": "Player nahi mila."}), 404

    if PrivateRedeemCode.query.filter_by(code=code).first():
        return jsonify({"success": False, "message": "Ye redeem code already use/assigned hai. Dusra code do."}), 400

    item = PrivateRedeemCode(user_id=user.id, code=code, message=message, used=False)
    db.session.add(item)
    db.session.commit()
    return jsonify({
        "success": True,
        "message": f"Redeem code sirf {user.username} ko send ho gaya.",
        "code": {"id": item.id, "user_id": user.id, "username": user.username, "uid": user.uid, "code": item.code, "message": item.message}
    })


@app.route("/api/admin/redeem-codes/<int:code_id>", methods=["DELETE"])
def delete_redeem_code(code_id):
    if not is_admin_logged_in():
        return jsonify({"success": False, "message": "Admin login required."}), 401
    item = db.session.get(PrivateRedeemCode, code_id)
    if item is None:
        return jsonify({"success": False, "message": "Redeem code nahi mila."}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True, "message": "Redeem code delete ho gaya."})


# =========================================================
# WALLET - GET BALANCE
# =========================================================

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
# GET TOURNAMENT PLAYERS
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
# FRONTEND COMPATIBILITY ROUTES
# =========================================================

@app.route("/api/admin/me", methods=["GET"])
def admin_me():
    if not is_admin_logged_in():
        return jsonify({"success": False, "logged_in": False}), 401
    return jsonify({"success": True, "logged_in": True, "username": session.get("admin_username", "admin")})


@app.route("/api/admin/login", methods=["POST"])
def admin_login_api():
    return admin_login()


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout_api():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    return jsonify({"success": True, "message": "Admin logout successful."})


@app.route("/api/admin/players/<int:player_id>", methods=["PUT"])
def update_player_api(player_id):
    return update_player(player_id)

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
