import pandas as pd
import json
import os
import sys
from collections import defaultdict
import datetime

# Add the web_app directory to the Python path to import data_manager
current_dir = os.path.dirname(__file__)
web_app_dir = os.path.join(current_dir, "..", "web_app")
sys.path.append(web_app_dir)

import data_manager # Import from web_app.data_manager
import reporter # Import reporter to use generate_text_report

def parse_planning_csv(csv_path: str, employees_data_path: str) -> pd.DataFrame:
    """
    Parses the planning CSV file into a DataFrame with dates as index and employee IDs as columns.
    Assumes the order of employees in the CSV matches the order in the employees JSON.
    """
    with open(employees_data_path, 'r') as f:
        employees_data = json.load(f)
    
    employee_id_to_name = {emp['id']: emp['name'] for emp in employees_data}
    employee_name_to_id = {emp['name']: emp['id'] for emp in employees_data}

    planning_df = pd.read_csv(csv_path, header=None)

    # The first row contains dates, starting from the second column
    dates_str = planning_df.iloc[0, 1:].tolist()
    dates = [pd.to_datetime(d, format='%Y-%m-%d') for d in dates_str]

    # The first column (from the second row) contains employee names
    employee_names_in_planning_csv = planning_df.iloc[1:, 0].astype(str).tolist()
    
    # Convert employee names from CSV to their IDs using the mapping
    employee_ids_in_planning = []
    missing_employees_in_json = []
    for name in employee_names_in_planning_csv:
        if name in employee_name_to_id:
            employee_ids_in_planning.append(employee_name_to_id[name])
        else:
            missing_employees_in_json.append(name)

    if missing_employees_in_json:
        raise ValueError(f"The following employee names from the planning CSV are not found in {employees_data_path}: {', '.join(missing_employees_in_json)}. "
                         "Please ensure all employees in the CSV are defined in the employees JSON with matching names.")

    # The actual planning data starts from the second row, second column
    planning_grid = planning_df.iloc[1:, 1:]
    planning_grid.columns = dates
    planning_grid.index = employee_ids_in_planning

    return planning_grid


def load_all_data():
    """
    Loads all necessary data (employees, functions, shifts, daily needs, groups, settings)
    using the data_manager from the web_app.
    """
    employees = data_manager.get_employees()
    functions = data_manager.get_fonctions()
    shifts_master = data_manager.get_shifts_master()
    daily_needs = data_manager.get_daily_needs()
    groups = data_manager.get_groups()
    settings = data_manager.get_settings()
    
    return {
        "employees": employees,
        "functions": functions,
        "shifts_master": shifts_master,
        "daily_needs": daily_needs,
        "groups": groups,
        "settings": settings
    }


def audit_planning(planning_grid: pd.DataFrame, all_data: dict) -> dict:
    """
    Audits the given planning_grid against business rules and generates report_data.
    """
    report_data = {
        "score": 0,
        "total_uncovered": 0,
        "penalties": [],
        "stats": {},
        "employees_details": {},
        "families_report": {}, # Placeholder
        "qualif_equity_report": {}, # Placeholder
        "status": "Audited"
    }

    employees_data = all_data["employees"]
    # functions_data = all_data["functions"] # Not directly used as qualifications are in employee object
    shifts_master_data = all_data["shifts_master"]
    daily_needs_data = all_data["daily_needs"]
    settings = all_data["settings"]

    # Helper maps for quick lookups
    employee_qualifications_raw = {emp['id']: emp['qualifications'] for emp in employees_data}
    employee_fonctions_map = {emp['id']: [q for q in emp['qualifications'] if isinstance(q, str) and q.endswith('-F')] for emp in employees_data} # Assuming functions end with '-F'
    
    functions_map = all_data["functions"]
    
    # Map qualifications (shift_ids) to their corresponding functions.
    qualification_to_function = {}
    for func_id, qualif_list in functions_map.items():
        for qualif_shift_id in qualif_list:
            qualification_to_function[qualif_shift_id] = func_id

    # Convert daily_needs_data to a more accessible format: {date: {shift_id: count}}
    daily_needs_map = defaultdict(lambda: defaultdict(int))
    for need in daily_needs_data:
        date = pd.to_datetime(need['date_str']).date()
        daily_needs_map[date][need['shift_id']] = need['count']

    # Define common non-shift indicators
    non_shift_indicators = ["OFF", "VACATION", "HOLIDAY", "INSI", "FIXED_OFF", ""] # Added empty string for empty cells

    # Prepare planning_grid for reporter (convert DataFrame to dict of dicts with employee names)
    employee_id_to_name = {emp['id']: emp['name'] for emp in employees_data}
    
    planning_grid_for_reporter = {}
    for emp_id in planning_grid.index:
        emp_name = employee_id_to_name.get(emp_id, emp_id) # Use name if available, else use ID
        planning_grid_for_reporter[emp_name] = {}
        for date_col in planning_grid.columns:
            planning_grid_for_reporter[emp_name][date_col.strftime('%Y-%m-%d')] = planning_grid.loc[emp_id, date_col]

    # --- 1. Check Daily Needs Coverage ---
    assigned_shifts_count = defaultdict(lambda: defaultdict(int))

    for employee_id in planning_grid.index:
        for date_col in planning_grid.columns:
            shift_id = planning_grid.loc[employee_id, date_col]
            if pd.notna(shift_id) and shift_id not in non_shift_indicators:
                assigned_shifts_count[date_col.date()][shift_id] += 1

    for date, shift_needs in daily_needs_map.items():
        for shift_id, required_count in shift_needs.items():
            assigned_count = assigned_shifts_count[date][shift_id]
            if assigned_count < required_count:
                shortfall = required_count - assigned_count
                report_data["total_uncovered"] += shortfall
                penalty_cost = shortfall * settings["penalties"].get("PER_MISSING_NEED_UNIT", 10000)
                report_data["score"] += penalty_cost
                report_data["penalties"].append({
                    "reason": (f"Unmet daily need for {shift_id} on {date.strftime('%Y-%m-%d')}: "
                               f"required {required_count}, assigned {assigned_count}"),
                    "cost": penalty_cost,
                    "agent": "GLOBAL"
                })

    # --- 2. Check Employee Qualifications ---
    penalty_qualification_mismatch = settings["penalties"].get("PENALTY_QUALIFICATION_MISMATCH", 500)
    
    for employee_id in planning_grid.index:
        employee_direct_quals = {q for q in employee_qualifications_raw.get(employee_id, []) if isinstance(q, str) and not q.endswith('-F')} # Direct shift qualifications
        employee_func_quals = set(employee_fonctions_map.get(employee_id, [])) # Functional qualifications

        for date_col in planning_grid.columns:
            shift_id = planning_grid.loc[employee_id, date_col]
            if pd.notna(shift_id) and shift_id not in non_shift_indicators:
                
                is_qualified = False

                # Check if employee has the direct shift qualification
                if shift_id in employee_direct_quals:
                    is_qualified = True
                else:
                    # If not, check if they have the function qualification for this shift
                    required_function = qualification_to_function.get(shift_id)
                    if required_function and required_function in employee_func_quals:
                        is_qualified = True

                if not is_qualified:
                    penalty_cost = penalty_qualification_mismatch
                    report_data["score"] += penalty_cost
                    report_data["penalties"].append({
                        "reason": (f"Qualification mismatch for employee {employee_id} on {date_col.strftime('%Y-%m-%d')}: "
                                   f"assigned shift {shift_id} but lacks required direct qualification or functional qualification."),
                        "cost": penalty_cost,
                        "agent": employee_id
                    })

    # --- 3. Calculate Employee Details (Days Off, Work Days, Assigned Shifts, Total Hours) ---
    for emp in employees_data:
        emp_id = emp['id']
        emp_name = emp['name']
        
        total_days_off = 0
        work_days = 0
        assigned_shifts_count_per_employee = defaultdict(int)
        total_hours = 0.0

        if emp_id in planning_grid.index: # Ensure employee is in the planning grid
            for date_col in planning_grid.columns:
                shift_id = planning_grid.loc[emp_id, date_col]
                if pd.isna(shift_id) or shift_id in non_shift_indicators:
                    total_days_off += 1
                else:
                    work_days += 1
                    assigned_shifts_count_per_employee[shift_id] += 1
                    
                    # Add shift duration to total hours
                    shift_details = shifts_master_data.get(shift_id)
                    if shift_details:
                        total_hours += shift_details.get("duration_minutes", 0) / 60.0 # Convert minutes to hours

        report_data["employees_details"][emp_name] = {
            "id": emp_id,
            "total_days_off": total_days_off,
            "work_days": work_days,
            "assigned_shifts": dict(assigned_shifts_count_per_employee),
            "total_hours": round(total_hours, 2),
            "name": emp_name,
            "days_off": total_days_off,
            "days_work": work_days,
            "fonctions_breakdown": {} # This would require deeper analysis
        }

    # For now, families_report and qualif_equity_report will be empty or minimal
    report_data["families_report"] = {} # Empty dict to prevent errors if reporter expects it
    report_data["qualif_equity_report"] = [] # Empty list to prevent errors if reporter expects it

    # Basic stats
    all_off_days = [details["total_days_off"] for details in report_data["employees_details"].values()]
    if all_off_days:
        report_data["stats"]["avg_off"] = round(sum(all_off_days) / len(all_off_days), 2)
        report_data["stats"]["min_off"] = min(all_off_days)
        min_off_employee = next((emp_name for emp_name, details in report_data["employees_details"].items() if details["total_days_off"] == min(all_off_days)), "N/A")
        report_data["stats"]["min_off_agent"] = min_off_employee
    else:
        report_data["stats"]["avg_off"] = 0
        report_data["stats"]["min_off"] = 0
        report_data["stats"]["min_off_agent"] = "N/A"
    
    report_data["stats"]["nb_no_weekend"] = 0 # Placeholder

    return report_data

# Example usage (for testing purposes)
if __name__ == "__main__":
    current_dir = os.path.dirname(__file__)
    csv_file = os.path.join(current_dir, "..", "tool", "planning_brut.csv")
    employees_file = os.path.join(current_dir, "..", "data", "input", "01_employees.json")
    output_report_file = os.path.join(current_dir, "..", "data", "output", "Report.txt")
    
    try:
        planning_grid_df = parse_planning_csv(csv_file, employees_file)
        print("Planning Grid loaded successfully.")

        all_data = load_all_data()
        print("\nAll data loaded successfully.")

        audit_report_data = audit_planning(planning_grid_df, all_data)
        print("\nAudit Report Data Generated:")

        text_report = reporter.generate_text_report(audit_report_data, planning_grid_df) # Pass original DataFrame for reporter if it handles conversion internally or if it's meant to be that way

        with open(output_report_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        print(f"Audit report saved to {output_report_file}")

        print(f"Total Score: {audit_report_data['score']}")
        print(f"Total Uncovered Shifts: {audit_report_data['total_uncovered']}")

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
