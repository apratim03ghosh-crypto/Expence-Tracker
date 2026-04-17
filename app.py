from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'super_secret_hackathon_key'


# ================= DATABASE =================

def init_db():
    with sqlite3.connect('tracker.db') as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                budget REAL DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT NOT NULL,
                cost REAL NOT NULL,
                created_at DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()


init_db()


# ================= HOME =================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    username = session['username']

    with sqlite3.connect('tracker.db') as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT budget FROM users WHERE id = ?', (user_id,))
        budget = cursor.fetchone()[0]

        cursor.execute('SELECT item_name, cost FROM expenses WHERE user_id = ?', (user_id,))
        expenses = cursor.fetchall()

    total_spent = sum(item[1] for item in expenses)
    remaining = budget - total_spent

    progress = 0
    if budget > 0:
        progress = min((total_spent / budget) * 100, 100)

    return render_template(
        'index.html',
        username=username,
        budget=budget,
        total=total_spent,
        remaining=remaining,
        progress=progress,
        expenses=expenses
    )


# ================= ADD EXPENSE =================

@app.route('/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return jsonify({'status': 'error'}), 401

    data = request.get_json()
    item = data.get('item_name')
    cost = data.get('cost')

    if item and cost:
        with sqlite3.connect('tracker.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO expenses (user_id, item_name, cost)
                VALUES (?, ?, ?)
            ''', (session['user_id'], item, float(cost)))
            conn.commit()

        return jsonify({'status': 'success'})

    return jsonify({'status': 'error'}), 400


# ================= SET BUDGET =================

@app.route('/set_budget', methods=['POST'])
def set_budget():
    if 'user_id' not in session:
        return jsonify({'status': 'error'}), 401

    data = request.get_json()
    new_budget = float(data.get('budget', 0))

    with sqlite3.connect('tracker.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET budget = ? WHERE id = ?',
            (new_budget, session['user_id'])
        )
        conn.commit()

    return jsonify({'status': 'success'})


# ================= RESET =================

@app.route('/reset', methods=['POST'])
def reset():
    if 'user_id' not in session:
        return jsonify({'status': 'error'}), 401

    with sqlite3.connect('tracker.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE user_id = ?', (session['user_id'],))
        cursor.execute('UPDATE users SET budget = 0 WHERE id = ?', (session['user_id'],))
        conn.commit()

    return jsonify({'status': 'success'})


# ================= DAILY GRAPH DATA =================

@app.route('/daily_expenses')
def daily_expenses():
    if 'user_id' not in session:
        return jsonify({'days': [], 'amounts': []})

    user_id = session['user_id']
    current_month = datetime.now().strftime('%Y-%m')

    with sqlite3.connect('tracker.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT created_at, SUM(cost)
            FROM expenses
            WHERE user_id = ? AND created_at LIKE ?
            GROUP BY created_at
        ''', (user_id, current_month + '%'))

        rows = cursor.fetchall()

    daily_data = defaultdict(float)

    for date, amount in rows:
        day = int(date.split('-')[2])
        daily_data[day] = amount

    days = list(range(1, 32))
    amounts = [daily_data.get(day, 0) for day in days]

    return jsonify({'days': days, 'amounts': amounts})


# ================= AUTH =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect('tracker.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('index'))
            else:
                error = "Invalid username or password."

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = generate_password_hash(password)

        try:
            with sqlite3.connect('tracker.db') as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, hashed)
                )
                conn.commit()

            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = "Username already taken."

    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)