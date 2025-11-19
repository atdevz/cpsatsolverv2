from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import data_manager
import os
import pandas as pd
import subprocess
import sys
import json
import re
from collections import OrderedDict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key' 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) 

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin':
            user = User(1)
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ROUTES ---

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/qualifications')
@login_required
def qualifications_page():
    return render_template('qualifications.html')

@app.route('/shifts')
@login_required
def shifts_page():
    return render_template('shifts.html')

@app.route('/daily_needs')
@login_required
def daily_needs_page():
    return render_template('daily_needs.html')

@app.route('/upload')
@login_required
def upload_page():
    return render_template('upload.html')

@app.route('/groups')
@login_required
def groups_page():
    return render_template('groups.html')

@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html')

@app.route('/tools')
@login_required
def tools_page():
    return render_template('tools.html')

@app.route('/run_solver')
@login_required
def run_solver_page():
    return render_template('run_solver.html')

@app.route('/planning_report')
@login_required
def planning_report_page():
    report_path = os.path.join(app.root_path, os.pardir, 'data', 'output', 'Report.txt')
    report_content = "Rapport non disponible. Veuillez lancer le solveur."
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            report_content = f.read()
    return render_template('planning_report.html', report_content=report_content)

@app.route('/planning_view/<string:planning_type>')
@login_required
def planning_view_page(planning_type):
    file_name = 'Planning.csv'
    planning_path = os.path.join(app.root_path, os.pardir, 'data', 'output', file_name)
    
    # Structures par défaut
    dates_meta = []  # Liste de { 'col': '2025-12-01', 'short': '01', 'is_weekend': True }
    grouped_data = OrderedDict() # { 'Groupe A': [ {row}, {row} ] }

    if os.path.exists(planning_path):
        try:
            df = pd.read_csv(planning_path)
            
            # 1. Identifier les colonnes dates et construire les métadonnées
            name_col = None
            for col in df.columns:
                # On cherche la colonne "Employee" ou "Nom"
                if col.lower() in ['employee', 'employé', 'nom', 'name']:
                    name_col = col
                    continue
                
                # On tente de parser les autres comme des dates
                try:
                    date_obj = pd.to_datetime(col)
                    is_we = date_obj.weekday() >= 5
                    dates_meta.append({
                        'original_col': col,
                        'short_name': date_obj.strftime("%d"), # "01"
                        'is_weekend': is_we
                    })
                except:
                    pass # Colonne ignorée si pas une date

            # 2. Charger les groupes pour le mapping
            groups_data = data_manager.get_groups() # {'Groupe A': ['E01',...]}
            employees_data = data_manager.get_employees() # [{'id':'E01', 'name':'Toto'}]
            
            # Map Nom -> Groupe
            id_to_group = {}
            for g_name, members in groups_data.items():
                for emp_id in members:
                    id_to_group[emp_id] = g_name
            
            name_to_group = {}
            for emp in employees_data:
                grp = id_to_group.get(emp['id'], "11. Autres")
                name_to_group[emp['name']] = grp

            # 3. Organiser les données par groupe
            # On convertit le DF en liste de dicts pour faciliter le tri
            records = df.to_dict(orient='records')
            
            # On pré-remplit grouped_data avec l'ordre des groupes défini dans groups_data
            for g_name in sorted(groups_data.keys()):
                grouped_data[g_name] = []
            grouped_data["11. Autres"] = []

            for row in records:
                agent_name = row.get(name_col, "Inconnu")
                group = name_to_group.get(agent_name, "11. Autres")
                
                # Si le groupe n'existe pas dans la structure (ex: nouveau groupe), on l'ajoute
                if group not in grouped_data:
                    grouped_data[group] = []
                
                grouped_data[group].append(row)

            # Nettoyage des groupes vides
            grouped_data = {k: v for k, v in grouped_data.items() if v}
            
        except Exception as e:
            print(f"Erreur processing planning: {e}")

    return render_template('planning_view.html', 
                           planning_type=planning_type.capitalize(),
                           grouped_data=grouped_data,
                           dates_meta=dates_meta,
                           name_col="Employee") # Nom générique pour l'affichage

# --- API ENDPOINTS ---

@app.route('/api/run_solver', methods=['GET'])
@login_required
def api_run_solver():
    print("API /api/run_solver called.", flush=True)
    def generate():
        main_script_path = os.path.join(app.root_path, os.pardir, 'main.py')
        try:
            print(f"Attempting to run solver script: {main_script_path}", flush=True)
            process = subprocess.Popen(
                [sys.executable, '-u', main_script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                encoding='latin-1' 
            )

            for line in iter(process.stdout.readline, ''):
                print(f"Stdout: {line.strip()}", flush=True)
                yield f"data: {line.strip()}\n\n"

            stderr_output = []
            for line in iter(process.stderr.readline, ''):
                print(f"Stderr: {line.strip()}", flush=True)
                stderr_output.append(line.strip())
                yield f"data: {line.strip()}\n\n"

            process.wait()

            if process.returncode != 0:
                error_msg = f"ERROR: Code de retour {process.returncode}."
                if stderr_output: error_msg += f" {str(stderr_output)}"
                yield f"data: \n{error_msg}\n\n"
            else:
                yield f"data: \nLe script du solveur a terminé avec succès.\n\n"
        except Exception as e:
            yield f"data: \nERROR: Exception: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/tool/manage_shift_master', methods=['GET'])
@login_required
def api_manage_shift_master():
    def generate_msg(msg, status="SUCCESS"):
        yield f"data: [Manage Shifts] {status}: {msg}\n\n"

    action = request.args.get('action')
    shift_id = request.args.get('shift_id')
    duration = request.args.get('duration', type=int)
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    if not shift_id:
        return Response(generate_msg("Shift ID required.", "ERROR"), mimetype='text/event-stream')

    shifts_master = data_manager.get_shifts_master()

    if action == 'add_update':
        if not duration or not start_time or not end_time:
            return Response(generate_msg("Missing fields for add/update.", "ERROR"), mimetype='text/event-stream')
        
        if not re.fullmatch(r'^([01]\d|2[0-3]):([0-5]\d)$', start_time):
             return Response(generate_msg("Invalid start_time format (HH:MM).", "ERROR"), mimetype='text/event-stream')

        shifts_master[shift_id] = {
            "id": shift_id,
            "name": shift_id, 
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration
        }
        data_manager.save_shifts_master(shifts_master)
        return Response(generate_msg(f"Shift {shift_id} saved."), mimetype='text/event-stream')

    elif action == 'delete':
        if shift_id in shifts_master:
            del shifts_master[shift_id]
            data_manager.save_shifts_master(shifts_master)
            return Response(generate_msg(f"Shift {shift_id} deleted."), mimetype='text/event-stream')
        else:
            return Response(generate_msg(f"Shift {shift_id} not found.", "ERROR"), mimetype='text/event-stream')

    return Response(generate_msg("Invalid action.", "ERROR"), mimetype='text/event-stream')

@app.route('/api/tool/extract_needs', methods=['GET'])
@login_required
def api_extract_needs():
    csv_path = request.args.get('csv_path')
    def generate():
        tool_script_path = os.path.join(app.root_path, os.pardir, 'tool', 'extract_needs.py')
        command = [sys.executable, '-u', tool_script_path]
        if csv_path:
            command.extend(['--csv_path', csv_path])
        command.extend(['--output_json_path', '']) 
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='latin-1')
            for line in iter(process.stdout.readline, ''):
                yield f"data: {line.strip()}\n\n"
            
            stderr_output = []
            for line in iter(process.stderr.readline, ''):
                stderr_output.append(line.strip())
                yield f"data: {line.strip()}\n\n"

            process.wait()
            if process.returncode == 0:
                yield "data: \nExtract Needs finished successfully.\n\n"
            else:
                yield f"data: \nERROR: Code {process.returncode}. {stderr_output}\n\n"
        except Exception as e:
            yield f"data: \nERROR: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

# --- DATA API ---

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_settings())
    elif request.method == 'POST':
        data_manager.save_settings(request.get_json())
        return jsonify({"message": "Settings updated!"})

@app.route('/api/employees', methods=['GET', 'POST'])
@login_required
def employees_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_employees())
    elif request.method == 'POST':
        data_manager.save_employees(request.get_json())
        return jsonify({"message": "Employees updated!"})

@app.route('/api/fonctions', methods=['GET', 'POST'])
@login_required
def fonctions_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_fonctions())
    elif request.method == 'POST':
        data_manager.save_fonctions(request.get_json())
        return jsonify({"message": "Fonctions updated!"})

@app.route('/api/shifts_master', methods=['GET', 'POST'])
@login_required
def shifts_master_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_shifts_master())
    elif request.method == 'POST':
        data_manager.save_shifts_master(request.get_json())
        return jsonify({"message": "Shifts master updated!"})

@app.route('/api/daily_needs', methods=['GET', 'POST'])
@login_required
def daily_needs_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_daily_needs())
    elif request.method == 'POST':
        data_manager.save_daily_needs(request.get_json())
        return jsonify({"message": "Daily needs updated!"})

@app.route('/api/groups', methods=['GET', 'POST'])
@login_required
def groups_api():
    if request.method == 'GET':
        return jsonify(data_manager.get_groups())
    elif request.method == 'POST':
        data_manager.save_groups(request.get_json())
        return jsonify({"message": "Groups updated!"})

@app.route('/api/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'excel_file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['excel_file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            xls = pd.ExcelFile(filepath)
            messages = []
            
            if 'Employees' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Employees')
                data = df.to_dict(orient='records')
                for emp in data:
                    if 'fonctions' in emp and isinstance(emp['fonctions'], str):
                        emp['fonctions'] = [f.strip() for f in emp['fonctions'].split(',') if f.strip()]
                    else: emp['fonctions'] = []
                    
                    if 'constraints' in emp and isinstance(emp['constraints'], str):
                        try: emp['constraints'] = json.loads(emp['constraints'])
                        except: emp['constraints'] = []
                    else: emp['constraints'] = []
                data_manager.save_employees(data)
                messages.append('Employees updated.')

            if 'Functions' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Functions')
                data = {"functions": df.to_dict(orient='records')}
                for f in data['functions']:
                    if 'qualifications' in f and isinstance(f['qualifications'], str):
                        f['qualifications'] = [q.strip() for q in f['qualifications'].split(',') if q.strip()]
                    else: f['qualifications'] = []
                data_manager.save_fonctions(data)
                messages.append('Functions updated.')
            
            if 'Shifts' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Shifts')
                data = {row['id']: row.to_dict() for _, row in df.iterrows()}
                data_manager.save_shifts_master(data)
                messages.append('Shifts updated.')

            if 'Daily Needs' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Daily Needs')
                data_manager.save_daily_needs(df.to_dict(orient='records'))
                messages.append('Daily Needs updated.')

            if 'Groups' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Groups')
                groups = {}
                for _, row in df.iterrows():
                    g = str(row['group_name']).strip()
                    e = str(row['employee_id']).strip()
                    if g not in groups: groups[g] = []
                    if e: groups[g].append(e)
                data_manager.save_groups(groups)
                messages.append('Groups updated.')

            os.remove(filepath)
            if not messages: messages.append("No valid sheets found.")
            return jsonify({"message": " ".join(messages)}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)