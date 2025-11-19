from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import data_manager
import os
import pandas as pd
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key' # Replace with a strong secret key

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model (for demonstration purposes, using a simple in-memory user)
class User(UserMixin):
    def __init__(self, id):
        self.id = id

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) # In a real app, load user from a database

    return User(user_id) # In a real app, load user from a database

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # For demonstration: simple hardcoded credentials
        if username == 'admin' and password == 'admin':
            user = User(1) # Create a user object
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

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

@app.route('/planning_report')
@login_required
def planning_report_page():
    report_path = os.path.join(app.root_path, os.pardir, 'data', 'output', 'planning_report_final.txt')
    report_content = "Rapport non disponible." # Default message
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            report_content = f.read()
    return render_template('planning_report.html', report_content=report_content)

@app.route('/planning_view/<string:planning_type>')
@login_required
def planning_view_page(planning_type):
    file_name = f'planning_{planning_type}.csv'
    planning_path = os.path.join(app.root_path, os.pardir, 'data', 'output', file_name)
    planning_content = "Planification non disponible." # Default message
    
    if os.path.exists(planning_path):
        try:
            df = pd.read_csv(planning_path)
            # Convert DataFrame to HTML table
            planning_content = df.to_html(classes='table table-striped table-bordered planning-table', index=False)
        except Exception as e:
            planning_content = f"Erreur lors du chargement du fichier: {str(e)}"
    
    return render_template('planning_view.html', planning_content=planning_content, planning_type=planning_type.capitalize())

@app.route('/run_solver')
@login_required
def run_solver_page():
    return render_template('run_solver.html')

@app.route('/api/run_solver', methods=['GET'])
@login_required
def api_run_solver():
    print("API /api/run_solver called.", flush=True)
    def generate():
        print("Generator function 'generate' entered.", flush=True)
        main_script_path = os.path.join(app.root_path, os.pardir, 'main.py')
        try:
            print(f"Attempting to run solver script: {main_script_path}", flush=True)
            # Use encoding directly instead of text=True for explicit control and remove bufsize
            process = subprocess.Popen(['python', main_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='latin-1')
            print("subprocess.Popen successful.", flush=True)

            # Stream stdout
            for line in iter(process.stdout.readline, ''):
                print(f"Stdout: {line.strip()}", flush=True)
                yield f"data: {line.strip()}\n\n"

            # Stream stderr (if any, after stdout is exhausted or if stdout is empty)
            stderr_output = []
            for line in iter(process.stderr.readline, ''):
                print(f"Stderr: {line.strip()}", flush=True)
                stderr_output.append(line.strip())
                yield f"data: {line.strip()}\n\n"

            process.wait() # Wait for the process to terminate

            if process.returncode != 0:
                error_message = f"ERROR: Le script du solveur s'est terminé avec le code {process.returncode}."
                if stderr_output:
                    error_message += f" Messages d'erreur: {' '.join(stderr_output)}"
                print(error_message, flush=True) # Log to Flask's console
                yield f"data: \n{error_message}\n\n"
            else:
                print("Le script du solveur a terminé avec succès.", flush=True) # Log to Flask's console
                yield f"data: \nLe script du solveur a terminé avec succès.\n\n"
        except Exception as e:
            error_message = f"ERROR: Une exception s'est produite lors du lancement du solveur : {str(e)}"
            print(error_message, flush=True) # Log to Flask's console
            yield f"data: \n{error_message}\n\n"

    return Response(generate(), mimetype='text/event-stream')

# API Endpoints
@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings_api():
    if request.method == 'GET':
        settings = data_manager.get_settings()
        return jsonify(settings)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_settings(data)
        return jsonify({"message": "Settings data updated successfully!"})

@app.route('/api/employees', methods=['GET', 'POST'])
@login_required
def employees_api():
    if request.method == 'GET':
        employees = data_manager.get_employees()
        return jsonify(employees)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_employees(data)
        return jsonify({"message": "Employees data updated successfully!"})

@app.route('/api/fonctions', methods=['GET', 'POST'])
@login_required
def fonctions_api():
    if request.method == 'GET':
        fonctions = data_manager.get_fonctions()
        return jsonify(fonctions)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_fonctions(data)
        return jsonify({"message": "Fonctions data updated successfully!"})

@app.route('/api/shifts_master', methods=['GET', 'POST'])
@login_required
def shifts_master_api():
    if request.method == 'GET':
        shifts_master = data_manager.get_shifts_master()
        return jsonify(shifts_master)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_shifts_master(data)
        return jsonify({"message": "Shifts master data updated successfully!"})

@app.route('/api/daily_needs', methods=['GET', 'POST'])
@login_required
def daily_needs_api():
    if request.method == 'GET':
        daily_needs = data_manager.get_daily_needs()
        return jsonify(daily_needs)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_daily_needs(data)
        return jsonify({"message": "Daily needs data updated successfully!"})

@app.route('/api/groups', methods=['GET', 'POST'])
@login_required
def groups_api():
    if request.method == 'GET':
        groups = data_manager.get_groups()
        return jsonify(groups)
    elif request.method == 'POST':
        data = request.get_json()
        data_manager.save_groups(data)
        return jsonify({"message": "Groups data updated successfully!"})

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
        
        # Actual Excel processing logic
        try:
            xls = pd.ExcelFile(filepath)
            messages = []

            # Process Employees
            if 'Employees' in xls.sheet_names:
                df_employees = pd.read_excel(filepath, sheet_name='Employees')
                employees_data = df_employees.to_dict(orient='records')
                # Ensure 'fonctions' is treated as a list of strings
                for emp in employees_data:
                    if 'fonctions' in emp and isinstance(emp['fonctions'], str):
                        emp['fonctions'] = [f.strip() for f in emp['fonctions'].split(',') if f.strip()]
                    else:
                        emp['fonctions'] = []
                    if 'constraints' in emp and isinstance(emp['constraints'], str):
                        try:
                            emp['constraints'] = json.loads(emp['constraints'])
                        except json.JSONDecodeError:
                            print(f"WARNING: Could not parse constraints for employee {emp.get('id', '')}: {emp['constraints']}")
                            emp['constraints'] = []
                    else:
                        emp['constraints'] = []

                data_manager.save_employees(employees_data)
                messages.append('Employees data updated from Excel.')

            # Process Functions
            if 'Functions' in xls.sheet_names:
                df_functions = pd.read_excel(filepath, sheet_name='Functions')
                functions_data = {"functions": df_functions.to_dict(orient='records')}
                # Ensure 'qualifications' are lists of strings
                for func in functions_data['functions']:
                    if 'qualifications' in func and isinstance(func['qualifications'], str):
                        func['qualifications'] = [q.strip() for q in func['qualifications'].split(',') if q.strip()]
                    else:
                        func['qualifications'] = []
                data_manager.save_fonctions(functions_data)
                messages.append('Functions data updated from Excel.')
            
            # Process Shifts Master
            if 'Shifts' in xls.sheet_names:
                df_shifts = pd.read_excel(filepath, sheet_name='Shifts')
                shifts_data = {row['id']: row.to_dict() for index, row in df_shifts.iterrows()}
                data_manager.save_shifts_master(shifts_data)
                messages.append('Shifts master data updated from Excel.')

            # Process Daily Needs
            if 'Daily Needs' in xls.sheet_names:
                df_daily_needs = pd.read_excel(filepath, sheet_name='Daily Needs')
                daily_needs_data = df_daily_needs.to_dict(orient='records')
                data_manager.save_daily_needs(daily_needs_data)
                messages.append('Daily needs data updated from Excel.')

            # Process Groups
            if 'Groups' in xls.sheet_names:
                df_groups = pd.read_excel(filepath, sheet_name='Groups')
                # Assuming Groups sheet has columns like 'Group Name' and 'Employee ID'
                # And we need to aggregate employee IDs per group
                groups_dict = {}
                for index, row in df_groups.iterrows():
                    group_name = str(row['group_name']).strip() # Assuming 'group_name' column
                    employee_id = str(row['employee_id']).strip() # Assuming 'employee_id' column
                    if group_name not in groups_dict:
                        groups_dict[group_name] = []
                    if employee_id: # Only add if employee_id is not empty
                        groups_dict[group_name].append(employee_id)
                data_manager.save_groups(groups_dict)
                messages.append('Groups data updated from Excel.')

            os.remove(filepath) # Clean up the uploaded file

            if not messages:
                messages.append("No recognized sheets (Employees, Functions, Shifts, Daily Needs, Groups) found or processed in the Excel file.")
            
            return jsonify({"message": " ".join(messages)}), 200
        except Exception as e:
            print(f"Error during Excel processing: {e}")
            return jsonify({"error": f"Error processing Excel file: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
