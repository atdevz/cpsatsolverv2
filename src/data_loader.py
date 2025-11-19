# Fichier: src/data_loader.py

import json
from datetime import datetime, timedelta
from typing import List, Dict, Set, Any
from src.models import Employee, Shift, Constraint, Need, DAY_OF_WEEK_MAP
from src.utils import get_date_range_from_needs

class DataLoader:
    def __init__(self, config_path, employees_path, fonctions_path, shifts_path, needs_path, groups_path):
        self.config_path = config_path
        self.employees_path = employees_path
        self.fonctions_path = fonctions_path
        self.shifts_path = shifts_path
        self.needs_path = needs_path
        self.groups_path = groups_path

    def load_all_data(self) -> Dict[str, Any]:
        """
        Méthode principale pour tout charger, valider et retourner un dictionnaire de données.
        """
        print("Chargement des données...")
        
        config = self._load_json(self.config_path)
        shifts_map = self._load_shifts()
        fonctions_map = self._load_fonctions()
        # On charge les données brutes des employés pour la validation
        employees_data = self._load_json(self.employees_path)
        daily_needs = self._load_needs(self.needs_path)

        # --- ÉTAPE DE VALIDATION ---
        is_valid = self._validate_data(shifts_map, fonctions_map, employees_data, daily_needs)
        if not is_valid:
            print("\n  [Loader] ERREUR FATALE: Des incohérences ont été trouvées dans les données. Arrêt du programme.")
            return {}
        # --- FIN DE LA VALIDATION ---

        # Si la validation est OK, on peut construire les objets Employee finaux
        employees = self._build_employees(employees_data, fonctions_map)
        employee_families = self._load_employee_families(employees)
        date_range = get_date_range_from_needs(daily_needs)
        all_shift_ids = self._get_all_shift_ids(shifts_map)
        needed_shifts_lookup = set((need.date, need.shift_id) for need in daily_needs)

        print("Toutes les données sont chargées, traduites et validées.")
        
        return {
            "config": config,
            "shifts_map": shifts_map,
            "employees": employees,
            "daily_needs": daily_needs,
            "date_range": date_range,
            "all_shift_ids": all_shift_ids,
            "needed_shifts_lookup": needed_shifts_lookup,
            "employee_families": employee_families
        }

    def _validate_data(self, shifts_map: Dict, fonctions_map: Dict, employees_data: List[Dict], daily_needs: List[Need]) -> bool:
        """
        Vérifie la cohérence entre les différents fichiers de données.
        """
        print("  [Validation] Démarrage de la vérification des données...")
        errors = []
        
        # 1. Vérifier que les shifts dans les besoins existent
        shift_ids_master = set(shifts_map.keys())
        for need in daily_needs:
            if need.shift_id not in shift_ids_master:
                errors.append(f"  - Le shift '{need.shift_id}' requis le {need.date} n'existe pas dans '03_shifts_master.json'.")

        # 2. Vérifier que les fonctions des employés existent
        fonction_ids_master = set(fonctions_map.keys())
        for emp_data in employees_data:
            for func_item in emp_data.get("qualifications", []):
                # On ne valide que les strings, on ignore les dicts ici
                if isinstance(func_item, str):
                    if func_item not in fonction_ids_master:
                        errors.append(f"  - La fonction '{func_item}' de l'employé '{emp_data['name']}' n'existe pas dans '02_fonctions.json'.")

        # 3. Vérifier que les qualifications (shifts) dans les fonctions existent
        for func_id, qualif_list in fonctions_map.items():
            for shift_id in qualif_list:
                if shift_id not in shift_ids_master:
                    errors.append(f"  - La qualification '{shift_id}' listée dans la fonction '{func_id}' n'existe pas dans '03_shifts_master.json'.")

        if errors:
            print("  [Validation] ERREUR: Des incohérences ont été détectées :")
            for error in errors:
                print(error)
            return False
        
        print("  [Validation] Succès : Les données sont cohérentes.")
        return True

    def _get_all_shift_ids(self, shifts_map: Dict[str, Shift]) -> Set[str]:
        """Récupère simplement la liste de tous les shift_id uniques."""
        return set(shifts_map.keys())

    def _load_json(self, file_path: str) -> Any:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"  [Loader] ERREUR FATALE: Fichier introuvable: {file_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"  [Loader] ERREUR FATALE: Erreur JSON: {file_path}. Détail: {e}")
            return {}

    def _load_shifts(self) -> Dict[str, Shift]:
        shifts_map = {}
        shifts_data = self._load_json(self.shifts_path)
        if not shifts_data: return {}
             
        for shift_data in shifts_data.values():
            if not isinstance(shift_data, dict):
                print(f"AVERTISSEMENT: Élément de shift inattendu (non-dictionnaire) ignoré dans {self.shifts_path}: {shift_data}")
                continue
            if shift_data["id"] not in shifts_map:
                shift = Shift(
                    id=shift_data["id"],
                    start_time_str=shift_data["start_time"],
                    end_time_str=shift_data["end_time"]
                )
                shifts_map[shift.id] = shift
        print(f"  [Loader] Succès : {len(shifts_map)} shifts chargés.")
        return shifts_map

    def _load_fonctions(self) -> Dict[str, List[str]]:
        fonctions_data = self._load_json(self.fonctions_path)
        fonctions_map = {}
        for func in fonctions_data.get("functions", []):
            fonctions_map[func["id"]] = func.get("qualifications", [])
        print(f"  [Loader] Succès : {len(fonctions_map)} fonctions chargées.")
        return fonctions_map

    def _build_employees(self, employees_data: List[Dict], fonctions_map: Dict[str, List[str]]) -> List[Employee]:
        """Construit les objets Employee après la validation."""
        employees = []
        if not employees_data: return []

        for emp_data in employees_data:
            resolved_qualifs = set()
            fonctions_list = []
            
            # --- NOUVELLE LOGIQUE ROBUSTE ---
            # On sépare les qualifications (str) des contraintes (dict)
            potential_constraints = list(emp_data.get("constraints", []))
            for item in emp_data.get("qualifications", []):
                if isinstance(item, str):
                    fonctions_list.append(item)
                elif isinstance(item, dict):
                    # Si on trouve un dict, on le traite comme une contrainte
                    potential_constraints.append(item)
            # --- FIN DE LA NOUVELLE LOGIQUE ---

            for func_name in fonctions_list:
                shifts_for_this_func = fonctions_map.get(func_name, [])
                resolved_qualifs.update(shifts_for_this_func)
            
            parsed_constraints = self._parse_constraints(potential_constraints)

            emp = Employee(
                id=emp_data["id"],
                name=emp_data["name"],
                fonctions=set(fonctions_list),
                qualifications=resolved_qualifs,
                constraints=parsed_constraints
            )
            employees.append(emp)
        print(f"  [Loader] Succès : {len(employees)} employés construits.")
        return employees

    def _parse_constraints(self, constraints_list: List[Any]) -> List[Constraint]:
        parsed = []
        for const_item in constraints_list:
            # --- NOUVELLE LOGIQUE ROBUSTE ---
            if isinstance(const_item, dict):
                # Traiter le cas où la contrainte est déjà un dictionnaire
                try:
                    if const_item.get("type") == "MAX_SHIFTS_PER_QUALIF":
                        parsed.append(Constraint(
                            type="MAX_SHIFTS_PER_QUALIF",
                            qualif=const_item["qualif"],
                            value=int(const_item["value"])
                        ))
                except (KeyError, ValueError):
                     print(f"AVERTISSEMENT: Dictionnaire de contrainte invalide ignoré: {const_item}")
                continue # Passer à l'item suivant
            # --- FIN DE LA NOUVELLE LOGIQUE ---

            # L'ancienne logique pour les chaînes de caractères reste
            const_str = str(const_item)
            if const_str.startswith("HOLIDAY("):
                try:
                    date_str = const_str[8:-1]
                    parsed.append(Constraint(type="HOLIDAY", date=datetime.strptime(date_str, "%Y-%m-%d").date()))
                except ValueError: pass
            elif const_str.startswith("VACATION("):
                try:
                    dates_str = const_str[9:-1].split(',')
                    if len(dates_str) == 2:
                        start_date = datetime.strptime(dates_str[0].strip(), "%Y-%m-%d").date()
                        end_date = datetime.strptime(dates_str[1].strip(), "%Y-%m-%d").date()
                        
                        current_date = start_date
                        while current_date <= end_date:
                            parsed.append(Constraint(type="HOLIDAY", date=current_date))
                            current_date += timedelta(days=1)
                    else:
                        print(f"AVERTISSEMENT: Format VACATION invalide: {const_str}. Attendu VACATION(AAAA-MM-JJ,AAAA-MM-JJ)")
                except ValueError:
                    print(f"AVERTISSEMENT: Date(s) VACATION invalide(s): {const_str}")
            elif const_str.startswith("FIXED_OFF("):
                day_str = const_str[10:-1].upper()
                if day_str in DAY_OF_WEEK_MAP:
                    parsed.append(Constraint(type="FIXED_OFF", weekday=DAY_OF_WEEK_MAP[day_str]))
            elif const_str.startswith("MAX_HOURS("):
                try:
                    value_str = const_str[10:-1]
                    parsed.append(Constraint(type="MAX_HOURS", value=int(value_str)))
                except ValueError:
                    print(f"AVERTISSEMENT: Valeur MAX_HOURS invalide: {const_str}")
            elif const_str.startswith("MAX_SHIFTS_PER_QUALIF("):
                try:
                    parts = const_str[22:-1].split(',')
                    if len(parts) == 2:
                        qualif_id = parts[0].strip()
                        limit_value = int(parts[1].strip())
                        parsed.append(Constraint(type="MAX_SHIFTS_PER_QUALIF", qualif=qualif_id, value=limit_value))
                    else:
                        print(f"AVERTISSEMENT: Format MAX_SHIFTS_PER_QUALIF invalide: {const_str}. Attendu MAX_SHIFTS_PER_QUALIF(QUALIF_ID,VALUE)")
                except ValueError:
                    print(f"AVERTISSEMENT: Valeur MAX_SHIFTS_PER_QUALIF invalide: {const_str}")
            elif const_str == "NOT_WEEKEND":
                parsed.append(Constraint(type="FIXED_OFF", weekday=DAY_OF_WEEK_MAP["SATURDAY"]))
                parsed.append(Constraint(type="FIXED_OFF", weekday=DAY_OF_WEEK_MAP["SUNDAY"]))
        return parsed

    def _load_needs(self, needs_path: str) -> List[Need]:
        needs = []
        try:
            needs_data = self._load_json(needs_path)
            if not needs_data: return []

            for item in needs_data:
                if item["shift_id"] in ["HOL", "OFF", "INSI"]: continue
                try:
                    need_date = datetime.strptime(item["date_str"], "%d/%m/%y").date()
                    needs.append(Need(date=need_date, shift_id=item["shift_id"], count=item["count"]))
                except ValueError:
                    try:
                        need_date = datetime.strptime(item["date_str"], "%Y-%m-%d").date()
                        needs.append(Need(date=need_date, shift_id=item["shift_id"], count=item["count"]))
                    except ValueError:
                         print(f"AVERTISSEMENT: Date inconnue: {item['date_str']}")
            
            print(f"  [Loader] Succès : {len(needs)} besoins chargés.")
            return needs
        except Exception as e:
            print(f"  [Loader] ERREUR FATALE: {e}")
            return []

    def _load_employee_families(self, employees: List[Employee]) -> Dict[str, List[Employee]]:
        families_data = self._load_json(self.groups_path)
        employee_families = {group_name: [] for group_name in families_data.keys()}
        
        # Add an "Autres" group for employees not explicitly listed in any group
        employee_families["11. Autres"] = []

        # Create a lookup for employee objects by ID for efficient mapping
        employee_lookup_by_id = {emp.id: emp for emp in employees}

        all_grouped_employee_ids = set()
        for group_name, member_ids in families_data.items():
            for member_id in member_ids:
                if member_id in employee_lookup_by_id:
                    employee_families[group_name].append(employee_lookup_by_id[member_id])
                    all_grouped_employee_ids.add(member_id)
                else:
                    print(f"AVERTISSEMENT: Employé avec l'ID '{member_id}' listé dans le groupe '{group_name}' mais non trouvé dans les données des employés.")
        
        # Add employees not found in any group to "Autres"
        for emp in employees:
            if emp.id not in all_grouped_employee_ids:
                employee_families["11. Autres"].append(emp)

        # Filter out empty groups
        employee_families = {name: group for name, group in employee_families.items() if group}

        print(f"  [Loader] Succès : {len(employee_families)} familles d'employés chargées.")
        return employee_families
