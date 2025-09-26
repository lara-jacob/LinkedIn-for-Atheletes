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
        password="1234",
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
        if user_type.lower() == "athlete":
            cur.execute("""
                INSERT INTO athletes (email, password) 
                VALUES (%s, %s)
            """, (email, hashed_password))

        elif user_type.lower() == "coach":
            cur.execute("""
                INSERT INTO coaches (email, password) 
                VALUES (%s, %s)
            """, (email, hashed_password))

        elif user_type.lower() == "sponsor":
            cur.execute("""
                INSERT INTO sponsors (email, password) 
                VALUES (%s, %s)
            """, (email, hashed_password))

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


if __name__ == "__main__":
    app.run(debug=True)
