import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

DB_DIR = '/opt/render/project/src/database' if os.path.exists('/opt/render') else 'database'
DB_PATH = os.path.join(DB_DIR, 'mwea_rice.db')

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS farmers (farmer_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL, location TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS deliveries (delivery_id INTEGER PRIMARY KEY AUTOINCREMENT, farmer_id INTEGER, delivery_date TEXT NOT NULL, bags_delivered INTEGER NOT NULL, price_per_bag REAL NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS loans (loan_id INTEGER PRIMARY KEY AUTOINCREMENT, farmer_id INTEGER, principal_borrowed REAL NOT NULL, annual_rate REAL NOT NULL, borrowed_date TEXT NOT NULL, service_type TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS control_dates (id INTEGER PRIMARY KEY AUTOINCREMENT, gov_release_date TEXT NOT NULL, sacco_disburse_date TEXT NOT NULL)''')
    cursor.execute("SELECT COUNT(*) FROM control_dates")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO control_dates (gov_release_date, sacco_disburse_date) VALUES ('2026-05-15', '2026-09-20')")
    conn.commit()
    conn.close()

init_db()

def calculate_days(s, e):
    try: 
        return max(0, (datetime.strptime(e, "%Y-%m-%d") - datetime.strptime(s, "%Y-%m-%d")).days)
    except: 
        return 0

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    dates = conn.execute('SELECT * FROM control_dates LIMIT 1').fetchone()
    farmers = conn.execute('SELECT * FROM farmers').fetchall()
    dashboard_data = []
    for f in farmers:
        dels = conn.execute('SELECT * FROM deliveries WHERE farmer_id = ?', (f['farmer_id'],)).fetchall()
        gross = sum(d['bags_delivered'] * d['price_per_bag'] for d in dels)
        bags = sum(d['bags_delivered'] for d in dels)
        
        loans = conn.execute('SELECT * FROM loans WHERE farmer_id = ?', (f['farmer_id'],)).fetchall()
        deduct, interest = 0, 0
        for l in loans:
            days = calculate_days(l['borrowed_date'], dates['gov_release_date'])
            li = l['principal_borrowed'] * (l['annual_rate'] / 100) * (days / 365)
            interest += li
            deduct += (l['principal_borrowed'] + li)
            
        dashboard_data.append({
            'id': f['farmer_id'], 'name': f['name'], 'phone': f['phone'], 'location': f['location'],
            'bags': bags, 'gross': gross, 'deductions': deduct, 'interest': interest, 'net': gross - deduct,
            'delay': calculate_days(dates['gov_release_date'], dates['sacco_disburse_date'])
        })
    conn.close()
    return render_template('dashboard.html', farmers=dashboard_data, dates=dates)

@app.route('/update-dates', methods=['POST'])
def update_dates():
    conn = get_db_connection()
    conn.execute('UPDATE control_dates SET gov_release_date = ?, sacco_disburse_date = ? WHERE id = 1', (request.form['gov_release_date'], request.form['sacco_disburse_date']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add-farmer', methods=['POST'])
def add_farmer():
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO farmers (name, phone, location) VALUES (?, ?, ?)', (request.form['name'], request.form['phone'], request.form['location']))
        conn.commit()
    except: pass
    conn.close()
    return redirect(url_for('index'))

@app.route('/add-delivery', methods=['POST'])
def add_delivery():
    conn = get_db_connection()
    conn.execute('INSERT INTO deliveries (farmer_id, delivery_date, bags_delivered, price_per_bag) VALUES (?, ?, ?, ?)', (request.form['farmer_id'], request.form['delivery_date'], request.form['bags_delivered'], request.form['price_per_bag']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add-loan', methods=['POST'])
def add_loan():
    conn = get_db_connection()
    conn.execute('INSERT INTO loans (farmer_id, principal_borrowed, annual_rate, borrowed_date, service_type) VALUES (?, ?, ?, ?, ?)', (request.form['farmer_id'], request.form['principal_borrowed'], request.form['annual_rate'], request.form['borrowed_date'], request.form['service_type']))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
