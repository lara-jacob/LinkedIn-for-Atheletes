from flask import Flask, request, jsonify, render_template
import psycopg2
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="sporture",
        user="postgres",
        password="12345",
        port=5432
    )
    return conn

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")

@app.route("/application")
def application_page():
    return render_template("application.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    user_type = data.get("type")

    if not email or not password or not user_type:
        return jsonify({"success": False, "message": "Missing fields"}), 400

    hashed_password = generate_password_hash(password)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 🔍 Check all 3 tables before inserting
        cur.execute("""
            SELECT email FROM athletes WHERE email=%s
            UNION
            SELECT email FROM coaches WHERE email=%s
            UNION
            SELECT email FROM sponsors WHERE email=%s
        """, (email, email, email))
        exists = cur.fetchone()

        if exists:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Email already registered!"}), 400

        # ✅ Insert into the selected table
        if user_type.lower() == "athletes":
            cur.execute("INSERT INTO athletes (email, password) VALUES (%s, %s)", (email, hashed_password))
        elif user_type.lower() == "coach":
            cur.execute("INSERT INTO coaches (email, password) VALUES (%s, %s)", (email, hashed_password))
        elif user_type.lower() == "sponsor":
            cur.execute("INSERT INTO sponsors (email, password) VALUES (%s, %s)", (email, hashed_password))
        else:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Invalid user type"}), 400

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Registration successful!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


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

        # Check Athlete
        cur.execute("SELECT password FROM athletes WHERE email=%s", (email,))
        result = cur.fetchone()
        if result:
            stored_password = result[0]
            user_type = "athlete"

        # Check Coach
        if not stored_password:
            cur.execute("SELECT password FROM coaches WHERE email=%s", (email,))
            result = cur.fetchone()
            if result:
                stored_password = result[0]
                user_type = "coach"

        # Check Sponsor
        if not stored_password:
            cur.execute("SELECT password FROM sponsors WHERE email=%s", (email,))
            result = cur.fetchone()
            if result:
                stored_password = result[0]
                user_type = "sponsor"

        cur.close()
        conn.close()

        # ✅ If you stored hashed passwords
        if stored_password and check_password_hash(stored_password, password):
            return jsonify({
                "success": True,
                "message": "Login successful",
                "type": user_type,
                "redirect": "/dashboard"
            })

        return jsonify({"success": False, "message": "Invalid credentials"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    


    # Submit new application (athlete)
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



if __name__ == "__main__":
    app.run(debug=True)
