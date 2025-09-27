from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import psycopg2
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
from flask import abort
# near your app setup
logging.basicConfig(level=logging.DEBUG)

app = Flask(_name_)
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

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/adminlogin')
def adminlogin():
    return render_template('adminlogin.html')

@app.route("/manage_users")
def manage_users():
    return render_template("manage_users.html")  

@app.route("/application_approval")
def application_approval():
    return render_template("application_approval.html") 

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
                # prefer name, fallback to contact_person
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
    data = request.get_json()
    athlete_name = data.get("athlete_name")
    age = data.get("age")
    gender = data.get("gender")
    sport = data.get("sport")
    location = data.get("location")
    application_type = data.get("application_type")
    achievements = data.get("achievements")
    motivation = data.get("motivation")
    goals = data.get("goals")
    supporting_docs = data.get("supporting_docs")

    if not athlete_name or not sport or not application_type:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO applications (
                athlete_name, age, gender, sport, location,
                application_type, achievements, motivation, goals,
                supporting_docs, status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pending')
        """, (athlete_name, age, gender, sport, location, application_type,
              achievements, motivation, goals, supporting_docs))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Application submitted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



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


from psycopg2.extras import RealDictCursor
from datetime import datetime

@app.route("/profile")
def profile_page():
    if "email" not in session or "user_type" not in session:
        return redirect(url_for("login_page"))

    email = session["email"]
    user_type = session["user_type"]
    display_name = session.get("display_name", email.split("@")[0])
    avatar_url = session.get("avatar_url") or f"https://avatars.dicebear.com/api/identicon/{display_name}.svg?scale=85"

    conn = get_db_connection()
    # use RealDictCursor to make mapping rows -> dicts easier
    cur = conn.cursor(cursor_factory=RealDictCursor)
    user = {}

    try:
        if user_type == "athlete":
            # get athlete personal data
            cur.execute("""
                SELECT full_name, age, gender, sport, achievements, ranking, experience_years, contact_number, location
                FROM athletes
                WHERE email = %s
            """, (email,))
            athlete_row = cur.fetchone()
            if athlete_row:
                user = {
                    "full_name": athlete_row["full_name"],
                    "age": athlete_row["age"],
                    "gender": athlete_row["gender"],
                    "sport": athlete_row["sport"],
                    "achievements": athlete_row["achievements"],
                    "ranking": athlete_row["ranking"],
                    "experience_years": athlete_row["experience_years"],
                    "contact_number": athlete_row["contact_number"],
                    "location": athlete_row["location"],
                }
            # fallback display name if full_name not present
            athlete_name = user.get("full_name") or display_name

            # fetch ALL applications for this athlete (newest first)
            cur.execute("""
                SELECT id, athlete_name, application_type, sport, location, status, submission_date,
                       achievements, motivation, goals, supporting_docs
                FROM applications
                WHERE athlete_name = %s
                ORDER BY submission_date DESC
            """, (athlete_name,))
            apps = cur.fetchall()
            # apps will be a list of RealDictRow (dict-like). Keep as list to pass into template.
            applications = apps or []

        elif user_type == "coach":
            # coach personal data
            cur.execute("""
                SELECT full_name, specialization, certifications, experience_years, contact_number, location
                FROM coaches
                WHERE email = %s
            """, (email,))
            row = cur.fetchone()
            if row:
                user = {
                    "full_name": row["full_name"],
                    "specialization": row["specialization"],
                    "certifications": row["certifications"],
                    "experience_years": row["experience_years"],
                    "contact_number": row["contact_number"],
                    "location": row["location"],
                }

            # attempt to find any applications that reference this coach (best-effort)
            coach_name = user.get("full_name") or display_name
            cur.execute("""
                SELECT id, athlete_name, application_type, sport, location, status, submission_date,
                       achievements, motivation, goals, supporting_docs
                FROM applications
                WHERE application_type ILIKE 'Coach' AND (supporting_docs ILIKE %s OR motivation ILIKE %s)
                ORDER BY submission_date DESC
                LIMIT 0
            """, (f"%{coach_name}%", f"%{coach_name}%"))  # default: empty resultset; adjust as needed
            applications = cur.fetchall() or []

        elif user_type == "sponsor":
            # sponsor personal data
            cur.execute("""
                SELECT name, contact_person, sport, contact_number, location
                FROM sponsors
                WHERE email = %s
            """, (email,))
            row = cur.fetchone()
            if row:
                user = {
                    "name": row["name"],
                    "contact_person": row["contact_person"],
                    "sport": row["sport"],
                    "contact_number": row["contact_number"],
                    "location": row["location"],
                }

            # attempt to find sponsor-related applications (best-effort)
            sponsor_name = user.get("name") or user.get("contact_person") or display_name
            cur.execute("""
                SELECT id, athlete_name, application_type, sport, location, status, submission_date,
                       achievements, motivation, goals, supporting_docs
                FROM applications
                WHERE application_type ILIKE 'Sponsor' AND (supporting_docs ILIKE %s OR goals ILIKE %s)
                ORDER BY submission_date DESC
                LIMIT 0
            """, (f"%{sponsor_name}%", f"%{sponsor_name}%"))
            applications = cur.fetchall() or []

        else:
            # unknown user type -> no applications
            applications = []

    finally:
        cur.close()
        conn.close()

    # render the template with the applications list
    return render_template(
        "profile.html",
        user=user,
        user_role=user_type,
        display_name=display_name,
        avatar_url=avatar_url,
        applications=applications
    )



@app.route("/update_profile/coach", methods=["POST"])
def update_profile_coach():
    if "email" not in session or session.get("user_type") != "coach":
        return redirect(url_for("login_page"))

    email = session["email"]
    full_name = request.form.get("full_name")
    specialization = request.form.get("specialization")
    certifications = request.form.get("certifications")
    experience_years = request.form.get("experience_years")
    contact_number = request.form.get("contact_number")
    location = request.form.get("location")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE coaches
            SET full_name=%s,
                specialization=%s,
                certifications=%s,
                experience_years=%s,
                contact_number=%s,
                location=%s
            WHERE email=%s
        """, (full_name, specialization, certifications, experience_years, contact_number, location, email))
        conn.commit()
    except Exception as e:
        logging.exception("Error updating coach profile")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("profile_page"))


@app.route("/update_profile/sponsor", methods=["POST"])
def update_profile_sponsor():
    if "email" not in session or session.get("user_type") != "sponsor":
        return redirect(url_for("login_page"))

    email = session["email"]
    name = request.form.get("name")
    contact_person = request.form.get("contact_person")
    sport = request.form.get("sport")
    contact_number = request.form.get("contact_number")
    location = request.form.get("location")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE sponsors
            SET name=%s,
                contact_person=%s,
                sport=%s,
                contact_number=%s,
                location=%s
            WHERE email=%s
        """, (name, contact_person, sport, contact_number, location, email))
        conn.commit()
    except Exception as e:
        logging.exception("Error updating sponsor profile")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("profile_page"))


@app.route("/get_users")
def get_users():
    user_type = request.args.get("type")  # athlete, coach, sponsor

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if user_type == "athlete":
            cur.execute("SELECT id, full_name, email FROM athletes")
            rows = cur.fetchall()
            users = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]

        elif user_type == "coach":
            cur.execute("SELECT id, full_name, email FROM coaches")
            rows = cur.fetchall()
            users = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]

        elif user_type == "sponsor":
            cur.execute("SELECT id, name, email FROM sponsors")
            rows = cur.fetchall()
            users = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]

        else:
            users = []

    except Exception as e:
        print("Error fetching users:", e)
        users = []

    finally:
        cur.close()
        conn.close()

    return jsonify(users)

@app.route("/delete_user/<user_type>/<int:user_id>", methods=["DELETE"])
def delete_user(user_type, user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if user_type == "athlete":
            cur.execute("DELETE FROM athletes WHERE id=%s", (user_id,))
        elif user_type == "coach":
            cur.execute("DELETE FROM coaches WHERE id=%s", (user_id,))
        elif user_type == "sponsor":
            cur.execute("DELETE FROM sponsors WHERE id=%s", (user_id,))
        else:
            return jsonify({"success": False, "message": "Invalid user type"}), 400

        conn.commit()
        return jsonify({"success": True})

    except Exception as e:
        print("Delete error:", e)
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()

@app.route('/get_pending_applications')
def get_pending_applications():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM applications WHERE status='Pending'")
    apps = cur.fetchall()
    # Convert to JSON-friendly dict list
    keys = [desc[0] for desc in cur.description]
    result = [dict(zip(keys, row)) for row in apps]
    return jsonify(result)

@app.route('/update_application_status/<int:app_id>', methods=['POST'])
def update_application_status(app_id):
    data = request.get_json()
    status = data['status']
    app_type = data.get('type', None)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE applications SET status=%s WHERE id=%s", (status, app_id))
    conn.commit()

    # Optional: if approved, make it visible to coaches/sponsors
    if status == 'Forwarded' and app_type:
        table_name = 'coaches' if app_type=='Coach' else 'sponsors'
        # Insert into another table or notify them as needed

    return jsonify({"success": True})


if _name_ == "_main_":
    app.run(debug=True)