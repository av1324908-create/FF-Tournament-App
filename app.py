from datetime import datetime
import os

from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, text

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

    # Existing database me rules column automatically add karega.
    try:

        inspector = db.inspect(db.engine)

        tables = inspector.get_table_names()

        if "tournament" in tables:

            columns = [
                column["name"]
                for column in inspector.get_columns("tournament")
            ]

            if "rules" not in columns:

                with db.engine.begin() as connection:

                    connection.execute(
                        text(
                            "ALTER TABLE tournament "
                            "ADD COLUMN rules TEXT DEFAULT ''"
                        )
                    )

                print("Tournament rules column added successfully.")

    except Exception as error:

        print(
            "Tournament rules schema check failed:",
            error
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

    return bool(
        session.get("admin_id")
    )


def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# ADMIN PAGE
# =========================================================

@app.route("/admin")
def admin():

    return render_template(
        "admin.html"
    )


# =========================================================
# PLAYER SIGNUP
# =========================================================

@app.route(
    "/api/auth/signup",
    methods=["POST"]
)
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
            "message": (
                "Username minimum 3 characters "
                "ka hona chahiye."
            )
        }), 400


    if len(password) < 6:

        return jsonify({
            "success": False,
            "message": (
                "Password minimum 6 characters "
                "ka hona chahiye."
            )
        }), 400


    if password != confirm_password:

        return jsonify({
            "success": False,
            "message": (
                "Passwords match nahi kar rahe."
            )
        }), 400


    if User.query.filter_by(
        username=username
    ).first():

        return jsonify({
            "success": False,
            "message": (
                "Ye username already registered hai."
            )
        }), 400


    if User.query.filter_by(
        email=email
    ).first():

        return jsonify({
            "success": False,
            "message": (
                "Ye email already registered hai."
            )
        }), 400


    if User.query.filter_by(
        uid=uid
    ).first():

        return jsonify({
            "success": False,
            "message": (
                "Ye Free Fire UID already "
                "kisi account me registered hai."
            )
        }), 400


    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(
            password
        ),
        uid=uid
    )

    db.session.add(user)


    try:

        db.session.commit()

    except
