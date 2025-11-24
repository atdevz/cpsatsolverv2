from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import data_manager
import os
import pandas as pd
import subprocess
import sys
import json
import re
from collections import OrderedDict, defaultdict
from datetime import datetime

# Import auditor and reporter modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..', 'src'))
import auditor
import reporter

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

@app.route('/planning_view')
@app.route('/planning_view/<string:planning_filename>')
@login_required
def planning_view_page(planning_filename='Planning.csv'):
    file_name = planning_filename
    planning_path = os.path.join(app.root_path, os.pardir, 'data', 'output', file_name)
    
    dates_meta = [] 
    grouped_data = OrderedDict()
    daily_shortfalls = {} # { 'col_name': ['A10', 'C20'] }
    no_weekend_agents = set()
    name_col_found = "Employee" # Default, will be updated if file is planning_audited.csv

    if os.path.exists(planning_path):
        try:
            df = pd.read_csv(planning_path)

            if planning_filename == 'planning_audited.csv':
                # For audited planning, the first column (index) is the employee ID
                df.rename(columns={df.columns[0]: 'Employee'}, inplace=True)
                df.set_index('Employee', inplace=True)
                name_col_found = 'Employee'
            else:
                # Original logic for other planning files
                for col in df.columns:
                    if col.lower() in ['employee', 'employé', 'nom', 'name']:
                        name_col_found = col
                        break
            # Placeholder for the rest of the original planning_view_page logic
            # Assuming 'df' is further processed here to populate 'dates_meta', 'grouped_data', etc.
            # For now, we will leave these as their initial empty values.

        except Exception as e:
            app.logger.error(f"Error loading or processing {file_name}: {e}")
            # Optionally, set df to empty or handle the error gracefully for the template
            # For now, we'll let the empty initial values for data variables be passed to the template.
    
    return render_template('planning_view.html', 
                            grouped_data=grouped_data, 
                            dates_meta=dates_meta, 
                            daily_shortfalls=daily_shortfalls, 
                            file_name=file_name, 
                            planning_filename=planning_filename,
                            no_weekend_agents=no_weekend_agents,
                            name_col_found=name_col_found)


# --- API ENDPOINTS ---

@app.route('/api/run_solver', methods=['GET'])
@login_required
def api_run_solver():
    print("API /api/run_solver called.", flush=True)
    def generate():
        main_script_path = os.path.join(app.root_path, os.pardir, 'main.py')
        try:
            process = subprocess.Popen([sys.executable, '-u', main_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='latin-1')
            for line in iter(process.stdout.readline, ''): yield f"data: {line.strip()}\n\n"
            stderr_output = []
            for line in iter(process.stderr.readline, ''): stderr_output.append(line.strip()); yield f"data: {line.strip()}\n\n"
            process.wait()
            if process.returncode != 0: yield f"data: \nERROR: Code {process.returncode}.\n\n"
            else: yield f"data: \nLe script du solveur a terminé avec succès.\n\n"
        except Exception as e: yield f"data: \nERROR: {str(e)}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/tool/manage_shift_master', methods=['GET'])
@login_required
def api_manage_shift_master():
    def generate_msg(msg, status="SUCCESS"): yield f"data: [Manage Shifts] {status}: {msg}\n\n"
    action = request.args.get('action'); shift_id = request.args.get('shift_id')
    duration = request.args.get('duration', type=int); start_time = request.args.get('start_time'); end_time = request.args.get('end_time')
    if not shift_id: return Response(generate_msg("Shift ID req", "ERROR"), mimetype='text/event-stream')
    shifts_master = data_manager.get_shifts_master()
    if action == 'add_update':
        if not duration or not start_time or not end_time: return Response(generate_msg("Missing fields", "ERROR"), mimetype='text/event-stream')
        shifts_master[shift_id] = { "id": shift_id, "name": shift_id, "start_time": start_time, "end_time": end_time, "duration_minutes": duration }
        data_manager.save_shifts_master(shifts_master)
        return Response(generate_msg("Saved"), mimetype='text/event-stream')
    elif action == 'delete':
        if shift_id in shifts_master: del shifts_master[shift_id]; data_manager.save_shifts_master(shifts_master); return Response(generate_msg("Deleted"), mimetype='text/event-stream')
        return Response(generate_msg("Not found", "ERROR"), mimetype='text/event-stream')
    return Response(generate_msg("Invalid", "ERROR"), mimetype='text/event-stream')

@app.route('/api/tool/extract_needs', methods=['GET'])
@login_required
def api_extract_needs():
    csv_path = request.args.get('csv_path')
    def generate():
        tool_script_path = os.path.join(app.root_path, os.pardir, 'tool', 'extract_needs.py')
        command = [sys.executable, '-u', tool_script_path]
        if csv_path: command.extend(['--csv_path', csv_path])
        command.extend(['--output_json_path', '']) 
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='latin-1')
            for line in iter(process.stdout.readline, ''): yield f"data: {line.strip()}\n\n"
            process.wait()
            if process.returncode == 0: yield "data: \nFinished.\n\n"
            else: yield f"data: \nERROR: Code {process.returncode}.\n\n"
        except Exception as e: yield f"data: \nERROR: {str(e)}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings_api():
    if request.method == 'GET': return jsonify(data_manager.get_settings())
    data_manager.save_settings(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/employees', methods=['GET', 'POST'])
@login_required
def employees_api():
    if request.method == 'GET': return jsonify(data_manager.get_employees())
    data_manager.save_employees(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/fonctions', methods=['GET', 'POST'])
@login_required
def fonctions_api():
    if request.method == 'GET': return jsonify(data_manager.get_fonctions())
    data_manager.save_fonctions(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/shifts_master', methods=['GET', 'POST'])
@login_required
def shifts_master_api():
    if request.method == 'GET': return jsonify(data_manager.get_shifts_master())
    data_manager.save_shifts_master(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/daily_needs', methods=['GET', 'POST'])
@login_required
def daily_needs_api():
    if request.method == 'GET': return jsonify(data_manager.get_daily_needs())
    data_manager.save_daily_needs(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/groups', methods=['GET', 'POST'])
@login_required
def groups_api():
    if request.method == 'GET': return jsonify(data_manager.get_groups())
    data_manager.save_groups(request.get_json()); return jsonify({"message": "Updated"})

@app.route('/api/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'excel_file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['excel_file']
    if file.filename == '': return jsonify({"error": "Empty"}), 400
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            xls = pd.ExcelFile(filepath)
            if 'Employees' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Employees')
                data = df.to_dict(orient='records')
                for emp in data:
                    if 'fonctions' in emp and isinstance(emp['fonctions'], str): emp['fonctions'] = [f.strip() for f in emp['fonctions'].split(',') if f.strip()]
                    else: emp['fonctions'] = []
                    if 'constraints' in emp and isinstance(emp['constraints'], str):
                        try: emp['constraints'] = json.loads(emp['constraints'])
                        except: emp['constraints'] = []
                    else: emp['constraints'] = []
                data_manager.save_employees(data)
            if 'Functions' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Functions')
                data = {"functions": df.to_dict(orient='records')}
                for f in data['functions']:
                    if 'qualifications' in f and isinstance(f['qualifications'], str): f['qualifications'] = [q.strip() for q in f['qualifications'].split(',') if q.strip()]
                    else: f['qualifications'] = []
                data_manager.save_fonctions(data)
            if 'Shifts' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Shifts')
                data_manager.save_shifts_master({row['id']: row.to_dict() for _, row in df.iterrows()})
            if 'Daily Needs' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Daily Needs')
                data_manager.save_daily_needs(df.to_dict(orient='records'))
            if 'Groups' in xls.sheet_names:
                df = pd.read_excel(filepath, sheet_name='Groups')
                groups = {}
                for _, row in df.iterrows():
                    g = str(row['group_name']).strip()
                    e = str(row['employee_id']).strip()
                    if g not in groups: groups[g] = []
                    if e: groups[g].append(e)
                data_manager.save_groups(groups)
            os.remove(filepath)
            return jsonify({"message": "Success"}), 200
        except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/upload_planning_csv', methods=['POST'])
@login_required
def upload_planning_csv():
    if 'csv_file' not in request.files:
        flash('No file part')
        return redirect(url_for('upload_page'))
    file = request.files['csv_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('upload_page'))
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            # Load all necessary data
            all_data = auditor.load_all_data()
            
            # Parse the uploaded planning CSV
            # Need to pass the path to employees.json for parsing
            employees_json_path = os.path.join(app.root_path, os.pardir, 'data', 'input', '01_employees.json')
            planning_grid_df = auditor.parse_planning_csv(filepath, employees_json_path)

            # Audit the planning and get report data
            audit_report_data = auditor.audit_planning(planning_grid_df, all_data)
            
            # Generate and save the text report
            report_output_path = os.path.join(app.root_path, os.pardir, 'data', 'output', 'Report.txt')
            text_report = reporter.generate_text_report(audit_report_data, planning_grid_df.to_dict(orient='index')) # Pass as dict of dicts
            with open(report_output_path, 'w', encoding='utf-8') as f:
                f.write(text_report)

            # Save the audited planning grid to a CSV for viewing
            planning_csv_output_path = os.path.join(app.root_path, os.pardir, 'data', 'output', 'planning_audited.csv')
            planning_grid_df.to_csv(planning_csv_output_path, index=True, header=True) # Save with employee IDs as first column and dates as header

            flash('Planning CSV uploaded, audited, and report generated successfully!')
            return redirect(url_for('planning_report_page')) # Redirect to report page
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}')
            return redirect(url_for('upload_page'))
    return redirect(url_for('upload_page'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)