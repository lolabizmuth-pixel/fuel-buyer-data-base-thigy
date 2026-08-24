import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "super_secret_fuel_key_change_this_in_production"

FUEL_PRICES = {
    "Petrol": 1.40,
    "Diesel": 1.55,
    "LPG": 0.95
}

def get_db_connection():
    conn = sqlite3.connect("accounts.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY, 
                password TEXT, 
                points INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Fuel Cost & Loyalty Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5" style="max-width: 600px;">
        <div class="card shadow">
            <div class="card-header bg-primary text-white text-center">
                <h3>Fuel Cost & Loyalty Calculator</h3>
            </div>
            <div class="card-body">
                {% with messages = get_flashed_messages(with_categories=true) %}
                  {% if messages %}
                    {% for category, message in messages %}
                      <div class="alert alert-{{ 'danger' if category=='error' else 'success' }}">{{ message }}</div>
                    {% endfor %}
                  {% endif %}
                {% endwith %}

                <div class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom">
                    {% if session.get('username') %}
                        <div>
                            <strong>User:</strong> {{ session['username'] }} <br>
                            <strong>Loyalty Points:</strong> <span class="badge bg-success fs-6">{{ points }}</span>
                        </div>
                        <div>
                            <a href="{{ url_for('redeem') }}" class="btn btn-sm btn-outline-warning">Redeem Points</a>
                            <a href="{{ url_for('logout') }}" class="btn btn-sm btn-outline-danger">Sign Out</a>
                        </div>
                    {% else %}
                        <span class="text-muted">Not logged in</span>
                        <a href="{{ url_for('login') }}" class="btn btn-sm btn-primary">Sign In / Create Account</a>
                    {% endif %}
                </div>

                {% block content %}{% endblock %}
            </div>
        </div>
    </div>
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def index():
    points = 0
    if "username" in session:
        with get_db_connection() as conn:
            user = conn.execute("SELECT points FROM accounts WHERE username=?", (session["username"],)).fetchone()
            if user:
                points = user["points"]

    if request.method == "POST":
        if "username" not in session:
            flash("You must sign in first!", "error")
            return redirect(url_for("index"))

        fuel_type = request.form.get("fuel_type")
        try:
            litres = float(request.form.get("litres", 0))
            paid = float(request.form.get("paid", 0))
        except ValueError:
            flash("Please enter valid numbers for litres and amount paid.", "error")
            return redirect(url_for("index"))

        if fuel_type not in FUEL_PRICES:
            flash("Invalid fuel type selected.", "error")
            return redirect(url_for("index"))

        price_per_litre = FUEL_PRICES[fuel_type]
        total_cost = litres * price_per_litre
        change = paid - total_cost
        
        has_card = "loyalty" in request.form
        points_earned = 0

        if has_card:
            points_earned = int(litres) + int(paid)
            if points_earned > 100:
                points_earned = int(points_earned * 1.10)
            
            points += points_earned
            with get_db_connection() as conn:
                conn.execute("UPDATE accounts SET points=? WHERE username=?", (points, session["username"]))
                conn.commit()

        result_html = f'''
        <div class="alert alert-info">
            <h5>Calculation Results:</h5>
            <hr>
            <p><strong>Fuel Type:</strong> {fuel_type}</p>
            <p><strong>Litres Taken:</strong> {litres:.2f} L</p>
            <p><strong>Total Cost:</strong> £{total_cost:.2f}</p>
            <p><strong>Amount Paid:</strong> £{paid:.2f}</p>
            <p class="fs-5"><strong>Change Due:</strong> £{change:.2f}</p>
            {"<p class='text-success'><strong>Points Earned:</strong> " + str(points_earned) + "<br><strong>New Balance:</strong> " + str(points) + "</p>" if has_card else "<p class='text-muted'>No loyalty card used.</p>"}
        </div>
        <a href="/" class="btn btn-secondary w-100">Calculate Again</a>
        '''
        return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", result_html), points=points)

    form_html = '''
    <form method="POST">
        <div class="mb-3">
            <label class="form-label">Fuel Type:</label>
            <select name="fuel_type" class="form-select">
                {% for fuel in prices %}
                <option value="{{ fuel }}">{{ fuel }} (£{{ "%.2f"|format(prices[fuel]) }}/L)</option>
                {% endfor %}
            </select>
        </div>
        <div class="mb-3">
            <label class="form-label">Litres taken:</label>
            <input type="number" step="0.01" name="litres" class="form-control" required>
        </div>
        <div class="mb-3">
            <label class="form-label">Amount paid (£):</label>
            <input type="number" step="0.01" name="paid" class="form-control" required>
        </div>
        <div class="mb-3 form-check">
            <input type="checkbox" name="loyalty" class="form-check-input" id="loyaltyCheck">
            <label class="form-check-label" for="loyaltyCheck">Use loyalty card</label>
        </div>
        <button type="submit" class="btn btn-success w-100">Calculate Transaction</button>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", form_html), prices=FUEL_PRICES, points=points)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        action = request.form.get("action")

        if not username or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("login"))

        with get_db_connection() as conn:
            user = conn.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()

            if action == "login":
                if user and check_password_hash(user["password"], password):
                    session["username"] = username
                    flash("Welcome back!", "success")
                    return redirect(url_for("index"))
                else:
                    flash("Invalid username or password.", "error")

            elif action == "create":
                if user:
                    flash("Username already exists.", "error")
                else:
                    hashed_pw = generate_password_hash(password)
                    conn.execute("INSERT INTO accounts (username, password, points) VALUES (?, ?, 0)", (username, hashed_pw))
                    conn.commit()
                    session["username"] = username
                    flash("Account created successfully!", "success")
                    return redirect(url_for("index"))

    login_html = '''
    <form method="POST">
        <div class="mb-3">
            <label class="form-label">Username:</label>
            <input type="text" name="username" class="form-control" required>
        </div>
        <div class="mb-3">
            <label class="form-label">Password:</label>
            <input type="password" name="password" class="form-control" required>
        </div>
        <div class="d-flex gap-2">
            <button type="submit" name="action" value="login" class="btn btn-primary flex-fill">Login</button>
            <button type="submit" name="action" value="create" class="btn btn-outline-primary flex-fill">Create Account</button>
        </div>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", login_html), points=0)

@app.route("/redeem", methods=["GET", "POST"])
def redeem():
    if "username" not in session:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        user = conn.execute("SELECT points FROM accounts WHERE username=?", (session["username"],)).fetchone()
        points = user["points"] if user else 0

    if request.method == "POST":
        try:
            pts_to_redeem = int(request.form.get("points", 0))
        except ValueError:
            flash("Please enter a valid round number of points.", "error")
            return redirect(url_for("redeem"))

        if pts_to_redeem <= 0 or pts_to_redeem > points:
            flash("Invalid points quantity or insufficient balance.", "error")
            return redirect(url_for("redeem"))

        discount = pts_to_redeem * 0.01
        new_points = points - pts_to_redeem

        with get_db_connection() as conn:
            conn.execute("UPDATE accounts SET points=? WHERE username=?", (new_points, session["username"]))
            conn.commit()

        flash(f"Successfully redeemed {pts_to_redeem} points! Discount: £{discount:.2f}", "success")
        return redirect(url_for("index"))

    redeem_html = '''
    <form method="POST">
        <p class="text-center">How many points would you like to exchange? <br><small class="text-muted">(1 point = £0.01 discount)</small></p>
        <div class="mb-3">
            <input type="number" name="points" class="form-control text-center fs-4" placeholder="0" min="1" max="{{ points }}" required>
        </div>
        <button type="submit" class="btn btn-warning w-100">Confirm Redemption</button>
        <a href="/" class="btn btn-link w-100 text-center mt-2">Cancel</a>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE.replace("{% block content %}{% endblock %}", redeem_html), points=points)

@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
