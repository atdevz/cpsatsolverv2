import json
import os

# Assuming data_manager.py is in web_app/
# And JSON files are in data/input/ relative to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'input')

EMPLOYEES_FILE = os.path.join(DATA_DIR, '01_employees.json')
FONCTIONS_FILE = os.path.join(DATA_DIR, '02_fonctions.json')
SHIFTS_MASTER_FILE = os.path.join(DATA_DIR, '03_shifts_master.json')
DAILY_NEEDS_FILE = os.path.join(DATA_DIR, '04_daily_needs.json')
GROUPS_FILE = os.path.join(DATA_DIR, '05_groups.json')
SETTINGS_FILE = os.path.join(BASE_DIR, 'config', 'settings.json')

def load_json_file(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_settings():
    return load_json_file(SETTINGS_FILE)

def save_settings(settings_data):
    save_json_file(SETTINGS_FILE, settings_data)

def get_employees():
    return load_json_file(EMPLOYEES_FILE)

def save_employees(employees_data):
    # Transformer les données pour que 'fonctions' soit stocké comme 'qualifications'
    # pour la compatibilité avec data_loader.py
    transformed_employees_data = []
    for emp in employees_data:
        transformed_emp = emp.copy()
        if "fonctions" in transformed_emp:
            # Copier la liste des fonctions sous la clé 'qualifications'
            transformed_emp["qualifications"] = transformed_emp["fonctions"]
            # Supprimer la clé 'fonctions' si elle ne doit pas être persistée séparément
            del transformed_emp["fonctions"]
        transformed_employees_data.append(transformed_emp)
    
    save_json_file(EMPLOYEES_FILE, transformed_employees_data)

def get_fonctions():
    return load_json_file(FONCTIONS_FILE)

def save_fonctions(fonctions_data):
    save_json_file(FONCTIONS_FILE, fonctions_data)

def get_shifts_master():
    return load_json_file(SHIFTS_MASTER_FILE)

def save_shifts_master(shifts_master_data):
    save_json_file(SHIFTS_MASTER_FILE, shifts_master_data)

def get_daily_needs():
    return load_json_file(DAILY_NEEDS_FILE)

def save_daily_needs(daily_needs_data):
    save_json_file(DAILY_NEEDS_FILE, daily_needs_data)

def get_groups():
    return load_json_file(GROUPS_FILE)

def save_groups(groups_data):
    save_json_file(GROUPS_FILE, groups_data)
