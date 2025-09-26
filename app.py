from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import psycopg2
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
# near your app setup
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace_this_in_prod")

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="sporture",
        user="postgres",
        password="12345",
        port=5432
    )

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/application")
def application_page():
    return render_template("application.html")

# Register: now accepts optional display name fields (full_name / name / contact_person)
@app.route("/register", methods=["POST"])
def register():
    # accept JSON or form-encoded POSTs
    data = {}
    if request.is_json:
        data = request.get_json() or {}
    else:
        # fallback to form data (HTML forms or fetch with form body)
        data = request.form.to_dict() or {}

        # also accept query-string fallback (rare)
        if not data:
            data = request.args.to_dict() or {}

    logging.debug("Register payload received: %s", data)

    email = (data.get("email") or "").strip()
    password = data.get("password")
    user_type = (data.get("type") or data.get("user_type") or "").strip()
    # accept multiple field names for name
    full_name = data.get("full_name") or data.get("name") or data.get("contact_person")

    if not email or not password or not user_type:
        return jsonify({"success": False, "message": "Missing fields (email, password, type)"}), 400

    hashed_password = generate_password_hash(password)
    ut = user_type.lower().strip()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # check existing emails
        cur.execute("""
            SELECT email FROM athletes WHERE email=%s
            UNION
            SELECT email FROM coaches WHERE email=%s
            UNION
            SELECT email FROM sponsors WHERE email=%s
        """, (email, email, email))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Email already registered!"}), 400

        if ut in ("athlete", "athletes"):
            logging.debug("Inserting athlete: %s / %s", email, full_name)
            cur.execute(
                "INSERT INTO athletes (email, password, full_name) VALUES (%s, %s, %s)",
                (email, hashed_password, full_name)
            )

        elif ut in ("coach", "coaches"):
            logging.debug("Inserting coach: %s / %s", email, full_name)
            cur.execute(
                "INSERT INTO coaches (email, password, full_name) VALUES (%s, %s, %s)",
                (email, hashed_password, full_name)
            )

        elif ut in ("sponsor", "sponsors"):
            logging.debug("Inserting sponsor: %s / %s", email, full_name)
            cur.execute(
                "INSERT INTO sponsors (email, password, name, contact_person) VALUES (%s, %s, %s, %s)",
                (email, hashed_password, full_name, full_name)
            )

        else:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": f"Invalid user type: {user_type}"}), 400

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Registration successful!"})

    except Exception as e:
        logging.exception("Register error")
        return jsonify({"success": False, "message": str(e)}), 500


# Login: read name columns and store display_name in session
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Missing credentials"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        user_type = None
        stored_password = None
        display_name = None

        # athletes: full_name
        cur.execute("SELECT password, full_name FROM athletes WHERE email=%s", (email,))
        row = cur.fetchone()
        if row:
            stored_password, display_name = row[0], row[1]
            user_type = "athlete"

        # coaches: full_name
        if not stored_password:
            cur.execute("SELECT password, full_name FROM coaches WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                stored_password, display_name = row[0], row[1]
                user_type = "coach"

        # sponsors: name (or contact_person)
        if not stored_password:
            cur.execute("SELECT password, name, contact_person FROM sponsors WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                stored_password = row[0]
                # prefer `name`, fallback to contact_person
                display_name = row[1] or row[2]
                user_type = "sponsor"

        cur.close()
        conn.close()

        if stored_password and check_password_hash(stored_password, password):
            # fallback to email if name not present
            display_name = display_name or email.split("@")[0]
            session['email'] = email
            session['user_type'] = user_type
            session['display_name'] = display_name

            return jsonify({
                "success": True,
                "message": "Login successful",
                "type": user_type,
                "display_name": display_name,
                "redirect": "/dashboard"
            })

        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/submit_application", methods=["POST"])
def submit_application():
    # (unchanged from your original)
    data = request.get_json()
    athlete_name = data.get("athlete_name")
    # ... validate and insert ...
    return jsonify({"success": True, "message": "Application submitted (stub)"})


@app.route("/dashboard")
def dashboard_page():
    if "email" not in session or "user_type" not in session:
        return render_template("login.html")

    email = session["email"]
    user_type = session["user_type"]
    display_name = session.get("display_name", email.split("@")[0])

    # fetch profile details if you want more data (optional)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        profile = {}
        role_label = user_type

        if user_type == "athlete":
            cur.execute("SELECT full_name, sport FROM athletes WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                profile = {"full_name": row[0], "sport": row[1]}
                role_label = f"Athlete ({row[1] or ''})"
        elif user_type == "coach":
            cur.execute("SELECT full_name, specialization FROM coaches WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                profile = {"full_name": row[0], "specialization": row[1]}
                role_label = f"Coach ({row[1] or ''})"
        elif user_type == "sponsor":
            cur.execute("SELECT name, sport FROM sponsors WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                profile = {"name": row[0], "sport": row[1]}
                role_label = f"Sponsor ({row[1] or ''})"

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

    # compute profile_pct quickly (optional)
    filled = sum(1 for v in profile.values() if v)
    total = max(len(profile), 1)
    profile_pct = int((filled / total) * 100) if total else 0

    avatar_url = session.get("avatar_url") or f"https://avatars.dicebear.com/api/identicon/{display_name}.svg?scale=85"

    return render_template(
        "dashboard.html",
        profile=profile,
        user_type=user_type,
        display_name=display_name,
        avatar_url=avatar_url,
        role_label=role_label,
        profile_pct=profile_pct
    )


if __name__ == "__main__":
    app.run(debug=True)
