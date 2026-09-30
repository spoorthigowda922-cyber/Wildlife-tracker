from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = 'wildlife_tracker_secret'

# ============================================
# DATABASE CONNECTION
# ============================================

def get_db():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'wildlife_db'),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', 'root'),
        port=int(os.environ.get('DB_PORT', 3306))
    )

def query_db(sql, args=(), one=False, commit=False):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, args)
    if commit:
        conn.commit()
        cur.close()
        conn.close()
        return None
    rv = cur.fetchone() if one else cur.fetchall()
    cur.close()
    conn.close()
    return rv

def call_procedure(proc_name):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.callproc(proc_name)
    results = []
    for result in cur.stored_results():
        results.extend(result.fetchall())
    cur.close()
    conn.close()
    return results

# ============================================
# DASHBOARD
# ============================================

@app.route('/')
def dashboard():
    report = call_procedure('get_conservation_report')
    recent_incidents = query_db("""
        SELECT pi.*, h.name as habitat_name, r.full_name as ranger_name
        FROM poaching_incidents pi
        JOIN habitats h ON pi.habitat_id = h.habitat_id
        LEFT JOIN rangers r ON pi.reported_by = r.ranger_id
        ORDER BY pi.created_at DESC LIMIT 5
    """)
    endangered = query_db("SELECT * FROM endangered_animals_view LIMIT 6")
    habitat_summary = query_db("SELECT * FROM habitat_summary_view ORDER BY total_incidents DESC")
    return render_template('dashboard.html',
        report=report,
        recent_incidents=recent_incidents,
        endangered=endangered,
        habitat_summary=habitat_summary
    )

# ============================================
# ANIMALS
# ============================================

@app.route('/animals')
def animals():
    animals = query_db("""
        SELECT a.*, s.common_name as species_name, s.conservation_status,
               h.name as habitat_name
        FROM animals a
        JOIN species s ON a.species_id = s.species_id
        JOIN habitats h ON a.habitat_id = h.habitat_id
        ORDER BY a.animal_id
    """)
    return render_template('animals.html', animals=animals)

@app.route('/animals/add', methods=['GET', 'POST'])
def add_animal():
    if request.method == 'POST':
        query_db("""
            INSERT INTO animals (name, species_id, habitat_id, gender, age_years,
                weight_kg, tag_number, health_status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.form['name'], request.form['species_id'],
            request.form['habitat_id'], request.form['gender'],
            request.form['age_years'], request.form['weight_kg'],
            request.form['tag_number'], request.form['health_status'],
            request.form['notes']
        ), commit=True)
        flash('Animal added successfully!', 'success')
        return redirect(url_for('animals'))
    species = query_db("SELECT * FROM species ORDER BY common_name")
    habitats = query_db("SELECT * FROM habitats ORDER BY name")
    return render_template('add_animal.html', species=species, habitats=habitats)

@app.route('/animals/<int:animal_id>')
def animal_detail(animal_id):
    animal = query_db("""
        SELECT a.*, s.common_name as species_name, s.scientific_name,
               s.conservation_status, h.name as habitat_name
        FROM animals a
        JOIN species s ON a.species_id = s.species_id
        JOIN habitats h ON a.habitat_id = h.habitat_id
        WHERE a.animal_id = %s
    """, (animal_id,), one=True)
    gps_logs = query_db("""
        SELECT * FROM gps_logs WHERE animal_id = %s
        ORDER BY recorded_at DESC LIMIT 20
    """, (animal_id,))
    return render_template('animal_detail.html', animal=animal, gps_logs=gps_logs)

# ============================================
# HABITATS
# ============================================

@app.route('/habitats')
def habitats():
    habitats = query_db("SELECT * FROM habitat_summary_view ORDER BY total_incidents DESC")
    return render_template('habitats.html', habitats=habitats)

@app.route('/habitats/add', methods=['GET', 'POST'])
def add_habitat():
    if request.method == 'POST':
        query_db("""
            INSERT INTO habitats (name, location, area_sqkm, habitat_type, threat_level, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            request.form['name'], request.form['location'],
            request.form['area_sqkm'], request.form['habitat_type'],
            request.form['threat_level'], request.form['latitude'],
            request.form['longitude']
        ), commit=True)
        flash('Habitat added successfully!', 'success')
        return redirect(url_for('habitats'))
    return render_template('add_habitat.html')

# ============================================
# RANGERS
# ============================================

@app.route('/rangers')
def rangers():
    rangers = query_db("""
        SELECT r.*, h.name as habitat_name,
               COUNT(pl.patrol_id) as total_patrols
        FROM rangers r
        LEFT JOIN habitats h ON r.assigned_habitat_id = h.habitat_id
        LEFT JOIN patrol_logs pl ON r.ranger_id = pl.ranger_id
        GROUP BY r.ranger_id, h.name
        ORDER BY r.ranger_id
    """)
    return render_template('rangers.html', rangers=rangers)

@app.route('/rangers/add', methods=['GET', 'POST'])
def add_ranger():
    if request.method == 'POST':
        query_db("""
            INSERT INTO rangers (full_name, badge_number, email, phone, assigned_habitat_id, join_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            request.form['full_name'], request.form['badge_number'],
            request.form['email'], request.form['phone'],
            request.form['assigned_habitat_id'], request.form['join_date'],
            request.form['status']
        ), commit=True)
        flash('Ranger added successfully!', 'success')
        return redirect(url_for('rangers'))
    habitats = query_db("SELECT * FROM habitats ORDER BY name")
    return render_template('add_ranger.html', habitats=habitats)

# ============================================
# POACHING INCIDENTS
# ============================================

@app.route('/incidents')
def incidents():
    incidents = query_db("""
        SELECT pi.*, h.name as habitat_name, r.full_name as ranger_name
        FROM poaching_incidents pi
        JOIN habitats h ON pi.habitat_id = h.habitat_id
        LEFT JOIN rangers r ON pi.reported_by = r.ranger_id
        ORDER BY pi.incident_date DESC
    """)
    return render_template('incidents.html', incidents=incidents)

@app.route('/incidents/add', methods=['GET', 'POST'])
def add_incident():
    if request.method == 'POST':
        query_db("""
            INSERT INTO poaching_incidents
                (habitat_id, reported_by, incident_date, description, severity, status, animals_affected)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            request.form['habitat_id'], request.form['reported_by'],
            request.form['incident_date'], request.form['description'],
            request.form['severity'], request.form['status'],
            request.form['animals_affected']
        ), commit=True)
        flash('Incident reported successfully!', 'success')
        return redirect(url_for('incidents'))
    habitats = query_db("SELECT * FROM habitats ORDER BY name")
    rangers = query_db("SELECT * FROM rangers WHERE status = 'Active' ORDER BY full_name")
    return render_template('add_incident.html', habitats=habitats, rangers=rangers)

# ============================================
# GPS LOGS
# ============================================

@app.route('/gps')
def gps():
    logs = query_db("SELECT * FROM recent_gps_view ORDER BY recorded_at DESC")
    return render_template('gps.html', logs=logs)

@app.route('/gps/add', methods=['GET', 'POST'])
def add_gps():
    if request.method == 'POST':
        query_db("""
            INSERT INTO gps_logs (animal_id, latitude, longitude, altitude_m)
            VALUES (%s, %s, %s, %s)
        """, (
            request.form['animal_id'], request.form['latitude'],
            request.form['longitude'], request.form.get('altitude_m') or None
        ), commit=True)
        flash('GPS log added!', 'success')
        return redirect(url_for('gps'))
    animals = query_db("SELECT animal_id, name, tag_number FROM animals ORDER BY name")
    return render_template('add_gps.html', animals=animals)

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/gps/<int:animal_id>')
def api_gps(animal_id):
    logs = query_db("""
        SELECT latitude, longitude, recorded_at
        FROM gps_logs WHERE animal_id = %s
        ORDER BY recorded_at DESC LIMIT 50
    """, (animal_id,))
    return jsonify([{**r, 'recorded_at': str(r['recorded_at'])} for r in logs])

if __name__ == '__main__':
    app.run(debug=True)
