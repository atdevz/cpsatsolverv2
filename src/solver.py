# Fichier: src/solver.py

import json
from datetime import date, timedelta
from typing import List, Dict, Tuple, Set, Any
from ortools.sat.python import cp_model
from src.models import Employee, Shift, Need, Constraint
from src.solution_monitor import SolutionMonitor

# Map des jours de la semaine
DAY_OF_WEEK_MAP = {
    "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, 
    "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6
}

class CpSatSolver:
    
    def __init__(self, data: Dict[str, Any], toxic_pairs: Set[Tuple[str, str]]):
        self.data = data
        self.toxic_pairs = toxic_pairs
        
        self.config = data["config"]
        self.employees = data["employees"]
        self.shifts_map = data["shifts_map"]
        self.daily_needs = data["daily_needs"]
        self.date_range = data["date_range"]
        self.weekends = data["weekends"]
        
        self.all_shift_ids = data["all_shift_ids"]
        self.needed_shifts = data["needed_shifts_lookup"] 
        self.employee_families = data.get("employee_families", {})
        
        # Créer le traducteur inversé pour le rapport
        self.fonctions_map = data.get("fonctions_map", {})
        self.shift_to_fonction_map = {}
        for func_name, qualif_list in self.fonctions_map.items():
            for qualif in qualif_list:
                self.shift_to_fonction_map[qualif] = func_name

        self.model = cp_model.CpModel()
        self.variables = {} 
        self.penalties = [] 

    def create_model(self):
        print("Construction du modèle de contraintes...")
        self._1_create_variables()
        self._2_add_hard_constraints()
        self._3_add_soft_objectives() 
        self._4_define_search_strategy()
        print("Modèle construit.")
        return self.model, self.variables

    def _1_create_variables(self):
        print("  [1/4] Création des variables...")
        assign = {} 
        is_off = {} 
        total_minutes_per_employee = {} 
        total_off_days_per_employee = {} 
        total_shifts_per_fonction = {} 

        for e in self.employees:
            total_minutes_per_employee[e.id] = self.model.NewIntVar(0, 31*1440, f"total_min_{e.id}")
            total_off_days_per_employee[e.id] = self.model.NewIntVar(0, 31, f"total_off_{e.id}")
            
            shifts_minutes_this_month = [] 
            off_days_this_month = []

            # Pour chaque FONCTION de l'employé, initialiser un compteur
            for fonc_id in e.fonctions:
                total_shifts_per_fonction[e.id, fonc_id] = self.model.NewIntVar(0, len(self.date_range), f"total_shifts_{e.id}_{fonc_id}")

            for j in self.date_range:
                var_is_off = self.model.NewBoolVar(f"off_{e.id}_{j.strftime('%d-%m')}")
                is_off[e.id, j] = var_is_off
                off_days_this_month.append(var_is_off)
                
                for s_id in e.qualifications:
                    if s_id in self.shifts_map:
                        var_assign = self.model.NewBoolVar(f"assign_{e.id}_{j.day}_{s_id}")
                        assign[e.id, j, s_id] = var_assign
                        
                        shift_duration = self.shifts_map[s_id].duration_minutes
                        shifts_minutes_this_month.append(var_assign * shift_duration)

            self.model.Add(total_minutes_per_employee[e.id] == sum(shifts_minutes_this_month))
            self.model.Add(total_off_days_per_employee[e.id] == sum(off_days_this_month))

            # Lier le compteur de fonction aux shifts assignés
            for fonc_id in e.fonctions:
                shifts_for_this_fonction = [
                    assign[e.id, j, s_id] 
                    for j in self.date_range 
                    for s_id in self.fonctions_map.get(fonc_id, [])
                    if (e.id, j, s_id) in assign
                ]
                if shifts_for_this_fonction:
                    self.model.Add(total_shifts_per_fonction[e.id, fonc_id] == sum(shifts_for_this_fonction))
                else:
                    self.model.Add(total_shifts_per_fonction[e.id, fonc_id] == 0)


        self.variables = {
            "assign": assign,
            "is_off": is_off,
            "total_minutes_per_employee": total_minutes_per_employee,
            "total_off_days_per_employee": total_off_days_per_employee,
            "total_shifts_per_fonction": total_shifts_per_fonction, 
            "shortfalls": [],
            "shortfall_details": [],
            "penalty_details": []
        }

    def _2_add_hard_constraints(self):
        print("  [2/4] Ajout des règles dures...")
        assign = self.variables["assign"]
        is_off = self.variables["is_off"]
        total_shifts_per_fonction = self.variables["total_shifts_per_fonction"]

        # Règle 1: Unicité
        for e in self.employees:
            for j in self.date_range:
                shifts = [assign[e.id, j, s] for s in e.qualifications if (e.id, j, s) in assign]
                self.model.Add(sum(shifts) + is_off[e.id, j] == 1)

        # Règle 2: Repos 11h
        print("    -> Ajout règle des 11h de repos (Dure)")
        for e in self.employees:
            for j in self.date_range:
                jour_suivant = j + timedelta(days=1)
                if jour_suivant not in self.date_range: continue
                for shift_tard, shift_tot in self.toxic_pairs:
                    if (e.id, j, shift_tard) in assign and (e.id, jour_suivant, shift_tot) in assign:
                        self.model.Add(assign[e.id, j, shift_tard] + assign[e.id, jour_suivant, shift_tot] <= 1)
        
        # Règle 3: Contraintes fixes
        print("    -> Application des contraintes fixes (congés, jours fixes)...")
        for e in self.employees:
            for c in e.constraints: 
                if c.type == "HOLIDAY" and c.date:
                    if c.date in self.date_range:
                        self.model.Add(is_off[e.id, c.date] == 1)
                        
                elif c.type == "FIXED_OFF" and c.weekday is not None:
                    for j in self.date_range:
                        if j.weekday() == c.weekday:
                            self.model.Add(is_off[e.id, j] == 1)
                                
                elif c.type == "MAX_HOURS" and c.value is not None:
                    try:
                        total_minutes_vars = self.variables["total_minutes_per_employee"]
                        max_minutes = int(c.value) * 60
                        self.model.Add(total_minutes_vars[e.id] <= max_minutes)
                    except (ValueError, KeyError):
                        pass

                elif c.type == "MAX_SHIFTS_PER_QUALIF":
                    try:
                        fonction_to_limit = c.qualif 
                        limit_value = int(c.value)
                        if (e.id, fonction_to_limit) in total_shifts_per_fonction:
                            self.model.Add(total_shifts_per_fonction[e.id, fonction_to_limit] <= limit_value)
                    except (KeyError, TypeError, ValueError):
                        pass

        # Règle 4: Interdire shifts non demandés
        print("    -> Ajout règle d'interdiction des shifts non demandés (Dure)")
        for j in self.date_range:
            for s_id in self.all_shift_ids:
                if (j, s_id) not in self.needed_shifts:
                    agents_qui_peuvent_le_faire = [
                        assign[e.id, j, s_id] 
                        for e in self.employees 
                        if (e.id, j, s_id) in assign
                    ]
                    if agents_qui_peuvent_le_faire:
                        self.model.Add(sum(agents_qui_peuvent_le_faire) == 0)

        # Règle 5: Jours OFF minimum pour groupes spécifiques
        print("    -> Ajout règle des jours de repos minimum par groupe")
        total_off_days_vars = self.variables["total_off_days_per_employee"]
        emp_to_group = {emp.id: group_name for group_name, group in self.employee_families.items() for emp in group}
        group_overrides = self.config.get("group_min_off_days", {})

        for e in self.employees:
            group_name = emp_to_group.get(e.id)
            if group_name in group_overrides:
                min_off = group_overrides[group_name]
                if min_off > 0:
                    self.model.Add(total_off_days_vars[e.id] >= min_off)

        # Règle 6: Minimum de shifts BEUA-F pour groupe TRI
        tri_group_members = self.employee_families.get("3. TRI", [])
        for e in tri_group_members:
            fonction_cible = "BEUA-F"
            if (e.id, fonction_cible) in total_shifts_per_fonction:
                self.model.Add(total_shifts_per_fonction[e.id, fonction_cible] >= 4)

        # Règle 7: Règles spécifiques par agent
        print("    -> Application des règles spécifiques par agent (via Config)...")
        specific_rules = self.config.get("specific_agent_rules", [])

        for rule in specific_rules:
            target_ids = rule.get("agent_ids", [])
            target_func = rule.get("target_function")
            min_cnt = rule.get("min_count", 0)
            if not target_func or min_cnt <= 0: continue

            for e_id in target_ids:
                if (e_id, target_func) in total_shifts_per_fonction:
                    self.model.Add(total_shifts_per_fonction[e_id, target_func] >= min_cnt)

    def _3_add_soft_objectives(self):
        print("  [3/4] Ajout des objectifs (pénalités)...")
        is_off = self.variables["is_off"]
        assign = self.variables["assign"]
        total_off_days_vars = self.variables["total_off_days_per_employee"]
        total_shifts_per_fonction = self.variables["total_shifts_per_fonction"]
        
        # --- Objectif 1: Couverture des besoins (10 000 pts) ---
        cost_missing = self.config["penalties"]["PER_MISSING_NEED_UNIT"]
        for need in self.daily_needs:
            if need.date not in self.date_range: continue
            agents_normaux = [assign[e.id, need.date, need.shift_id] for e in self.employees if (e.id, need.date, need.shift_id) in assign]
            total_couv = sum(agents_normaux)
            shortfall = self.model.NewIntVar(0, need.count, f"short_{need.date.day}_{need.shift_id}")
            self.model.Add(total_couv + shortfall >= need.count) 
            self.variables["shortfalls"].append(shortfall)
            self.variables["shortfall_details"].append((need, shortfall))
            self.penalties.append(shortfall * cost_missing)

        # --- Objectif 2: Jours OFF (1 500 pts) ---
        cost_off = self.config["penalties"]["PER_DAY_OFF_MISSING"]
        emp_to_group = {emp.id: group_name for group_name, group in self.employee_families.items() for emp in group}
        group_overrides = self.config.get("group_min_off_days", {})
        global_min_off = self.config.get("min_off_days_per_month", 8)

        for e in self.employees:
            group_name = emp_to_group.get(e.id)
            min_off = group_overrides.get(group_name, global_min_off)
            if group_name in group_overrides and group_overrides[group_name] > 0: continue
            if min_off > 0:
                jours_manquants = self.model.NewIntVar(0, min_off, f"manque_off_{e.id}")
                self.model.Add(total_off_days_vars[e.id] + jours_manquants >= min_off)
                self.penalties.append(jours_manquants * cost_off)
                self.variables["penalty_details"].append(("Jours OFF manquants", e.name, jours_manquants, cost_off))
            
        # --- Objectif 3: Weekend Garanti (500 pts) ---
        cost_we = self.config["penalties"]["NO_WEEKEND_GUARANTEED"]
        for e in self.employees:
            we_reussis_vars = []
            for sam, dim in self.weekends:
                we_ok = self.model.NewBoolVar(f"we_ok_{e.id}_{sam.day}")
                self.model.AddBoolAnd([is_off[e.id, sam], is_off[e.id, dim]]).OnlyEnforceIf(we_ok)
                self.model.Add(we_ok == 0).OnlyEnforceIf(is_off[e.id, sam].Not())
                self.model.Add(we_ok == 0).OnlyEnforceIf(is_off[e.id, dim].Not())
                we_reussis_vars.append(we_ok)

            a_au_moins_un_we = self.model.NewBoolVar(f"a_we_{e.id}")
            self.model.Add(sum(we_reussis_vars) >= 1).OnlyEnforceIf(a_au_moins_un_we)
            self.model.Add(sum(we_reussis_vars) == 0).OnlyEnforceIf(a_au_moins_un_we.Not())
            no_we_var = self.model.NewBoolVar(f"no_we_{e.id}")
            self.model.Add(a_au_moins_un_we == no_we_var.Not())
            self.penalties.append(no_we_var * cost_we)
            self.variables["penalty_details"].append(("Weekend non garanti", e.name, no_we_var, cost_we))

        # --- Objectif 4: Équité du TOTAL des Jours de Travail (PRIORITÉ: 5000 pts) ---
        cost_equity_days = self.config["penalties"].get("PENALTY_INTRA_GROUP_WORK_DAYS_EQUITY_GAP", 5000)
        if cost_equity_days > 0:
            num_days = len(self.date_range)
            for family_name, family_group in self.employee_families.items():
                if len(family_group) > 1:
                    group_work_days_vars = []
                    for e in family_group:
                        total_work_days = self.model.NewIntVar(0, num_days, f"work_days_{e.id}")
                        self.model.Add(total_work_days == num_days - total_off_days_vars[e.id])
                        group_work_days_vars.append(total_work_days)

                    min_wd = self.model.NewIntVar(0, num_days, f"min_wd_{family_name}")
                    max_wd = self.model.NewIntVar(0, num_days, f"max_wd_{family_name}")
                    self.model.AddMinEquality(min_wd, group_work_days_vars)
                    self.model.AddMaxEquality(max_wd, group_work_days_vars)
                    
                    gap = self.model.NewIntVar(0, num_days, f"gap_days_{family_name}")
                    self.model.Add(gap == max_wd - min_wd)
                    self.penalties.append(gap * cost_equity_days)
                    self.variables["penalty_details"].append((f"Écart Total Jours {family_name}", "GROUPE", gap, cost_equity_days))

        # --- Objectif 5: Équité par QUALIFICATION (SECONDAIRE: 500 pts) ---
        cost_equity_shifts = self.config["penalties"].get("PENALTY_INTRA_GROUP_SHIFT_EQUITY_GAP", 500)
        if cost_equity_shifts > 0:
            max_shifts_possible = len(self.date_range)
            for group_name, group_members in self.employee_families.items():
                if len(group_members) < 2: continue
                for func_name in self.fonctions_map.keys():
                    qualified_agents = [e for e in group_members if func_name in e.fonctions]
                    if len(qualified_agents) > 1:
                        counts = []
                        for e in qualified_agents:
                            if (e.id, func_name) in total_shifts_per_fonction:
                                counts.append(total_shifts_per_fonction[e.id, func_name])
                        if counts:
                            min_s = self.model.NewIntVar(0, max_shifts_possible, f"min_s_{group_name}_{func_name}")
                            max_s = self.model.NewIntVar(0, max_shifts_possible, f"max_s_{group_name}_{func_name}")
                            gap_s = self.model.NewIntVar(0, max_shifts_possible, f"gap_s_{group_name}_{func_name}")
                            self.model.AddMinEquality(min_s, counts)
                            self.model.AddMaxEquality(max_s, counts)
                            self.model.Add(gap_s == max_s - min_s)
                            self.penalties.append(gap_s * cost_equity_shifts)
                            self.variables["penalty_details"].append((f"Écart Qualif {func_name} ({group_name})", "GROUPE", gap_s, cost_equity_shifts))

        # --- Objectif 6: Max jours consécutifs (2000 pts) ---
        max_consec = self.config.get("max_consecutive_work_days", 6)
        cost_consec = self.config["penalties"]["PER_CONSECUTIVE_WORK_DAY_VIOLATION"]
        for e in self.employees:
            for i in range(len(self.date_range) - max_consec):
                violation = self.model.NewBoolVar(f"consec_violation_{e.id}_{i}")
                jours_travailles = [is_off[e.id, self.date_range[i+k]].Not() for k in range(max_consec + 1)]
                self.model.Add(sum(jours_travailles) > max_consec).OnlyEnforceIf(violation)
                self.model.Add(sum(jours_travailles) <= max_consec).OnlyEnforceIf(violation.Not())
                self.penalties.append(violation * cost_consec)

        # --- Objectif 7 : HOMOGÉNÉISATION (Éviter les jours OFF isolés) (1000 pts) ---
        # Logique : Si jour J est OFF, alors (J-1) et (J+1) ne doivent pas être TRAVAILLÉS tous les deux.
        # On veut éviter le schéma : TRAVAIL - OFF - TRAVAIL
        cost_isolated = self.config["penalties"].get("PENALTY_ISOLATED_DAY_OFF", 1000)
        if cost_isolated > 0:
            for e in self.employees:
                # On ne peut vérifier que si J a un précédent et un suivant, donc de l'index 1 à N-2
                for i in range(1, len(self.date_range) - 1):
                    isolated_var = self.model.NewBoolVar(f"isolated_off_{e.id}_{i}")
                    
                    # Condition : J est OFF (is_off=1) ET J-1 est Travail (is_off=0) ET J+1 est Travail (is_off=0)
                    self.model.AddBoolAnd([
                        is_off[e.id, self.date_range[i]],           # J est OFF
                        is_off[e.id, self.date_range[i-1]].Not(),   # J-1 est Travail
                        is_off[e.id, self.date_range[i+1]].Not()    # J+1 est Travail
                    ]).OnlyEnforceIf(isolated_var)

                    # Inverse (pour que la variable soit 0 si la condition n'est pas remplie)
                    self.model.AddBoolOr([
                        is_off[e.id, self.date_range[i]].Not(),
                        is_off[e.id, self.date_range[i-1]],
                        is_off[e.id, self.date_range[i+1]]
                    ]).OnlyEnforceIf(isolated_var.Not())

                    self.penalties.append(isolated_var * cost_isolated)
                    # Pas besoin de l'ajouter aux penalty_details pour ne pas polluer le rapport, 
                    # mais cela va guider le solveur vers des blocs de repos (2 jours ou +).

        # --- Objectif Final ---
        objective_var = self.model.NewIntVar(0, 1000000000, "objective")
        self.model.Add(objective_var == sum(self.penalties))
        self.model.Minimize(objective_var)
        self.variables["objective"] = objective_var

    def _4_define_search_strategy(self):
        print("  [4/4] Définition de la stratégie de recherche...")
        assign = self.variables["assign"]
        priority_order = ["CARGO-F", "XRAY-F", "MAILXR-F", "SV-F", "UAGSR-F", "UAGC-F", "UALA-F", "BS-F", "ISA-F", "UACKIN-F"]
        func_to_priority = {func: i for i, func in enumerate(priority_order)}
        
        all_assign_vars = []
        for (e_id, day, s_id), var in assign.items():
            fonction = self.shift_to_fonction_map.get(s_id)
            priority = func_to_priority.get(fonction, 99)
            all_assign_vars.append((priority, var))
            
        all_assign_vars.sort(key=lambda x: x[0])
        sorted_vars = [var for priority, var in all_assign_vars]

        self.model.AddDecisionStrategy(sorted_vars, cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)

    def solve(self):
        print(f"Lancement du solveur ({self.config['solver_time_limit_seconds']}s)...")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config["solver_time_limit_seconds"]
        
        solution_monitor = SolutionMonitor(self.variables["objective"])
        status = solver.Solve(self.model, solution_monitor)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(f"Solution trouvée ! Coût: {solver.ObjectiveValue()}")
            planning = self._process_results(solver)
            report_data = self._collect_report_data(solver)
            return planning, report_data
        else:
            print("Aucune solution trouvée.")
            return None, None

    def _collect_report_data(self, solver):
        data = {
            "score": solver.ObjectiveValue(),
            "total_uncovered": sum(solver.Value(s) for s in self.variables["shortfalls"]),
            "penalties": [],
            "stats": {},
            "employees_details": {},
            "families_report": self.employee_families,
            "qualif_equity_report": {} 
        }
        
        cost_missing = self.config["penalties"]["PER_MISSING_NEED_UNIT"]
        for (need, shortfall_var) in self.variables["shortfall_details"]:
            val = solver.Value(shortfall_var)
            if val > 0:
                data["penalties"].append({
                    "agent": "GLOBAL", 
                    "reason": f"Manque {val} pour {need.shift_id} le {need.date}", 
                    "cost": val * cost_missing
                })

        for (name, context, var, cost) in self.variables["penalty_details"]:
            val = solver.Value(var)
            if val > 0:
                data["penalties"].append({"agent": context, "reason": f"{name} ({val})", "cost": val * cost})

        total_off_days_vars = self.variables["total_off_days_per_employee"]
        total_minutes_vars = self.variables["total_minutes_per_employee"]
        assign = self.variables["assign"]
        is_off = self.variables["is_off"]
        
        days_off_list = []
        for e in self.employees:
            nb_off = solver.Value(total_off_days_vars[e.id])
            nb_shifts = len(self.date_range) - nb_off
            days_off_list.append((nb_off, e.name))
            
            total_hours = round(solver.Value(total_minutes_vars[e.id]) / 60, 1)
            shifts_bk = {}
            funcs_bk = {}
            
            for j in self.date_range:
                if solver.Value(is_off[e.id, j]) == 0:
                    for s_id in e.qualifications:
                        if (e.id, j, s_id) in assign and solver.Value(assign[e.id, j, s_id]) == 1:
                            shifts_bk[s_id] = shifts_bk.get(s_id, 0) + 1
                            fname = self.shift_to_fonction_map.get(s_id, "AUTRE")
                            funcs_bk[fname] = funcs_bk.get(fname, 0) + 1
                            break
            
            data["employees_details"][e.name] = {
                "name": e.name, "days_off": nb_off, "days_work": nb_shifts,
                "total_hours": total_hours, "shifts_breakdown": shifts_bk,
                "fonctions_breakdown": funcs_bk
            }

        days_off_list.sort()
        data["stats"]["avg_off"] = sum(x[0] for x in days_off_list)/len(days_off_list) if days_off_list else 0
        data["stats"]["min_off"] = days_off_list[0][0] if days_off_list else 0
        data["stats"]["min_off_agent"] = days_off_list[0][1] if days_off_list else ""
        
        return data

    def _process_results(self, solver) -> Dict[str, Dict[str, str]]:
        planning = {}
        assign = self.variables["assign"]
        is_off = self.variables["is_off"]

        for e in self.employees:
            planning[e.name] = {}
            for j in self.date_range:
                date_str = j.strftime("%Y-%m-%d")
                if solver.Value(is_off[e.id, j]) == 1:
                    val = "OFF"
                    for c in e.constraints:
                        if c.type == "HOLIDAY" and c.date == j:
                            val = "HOLIDAY"
                            break
                        if c.type == "FIXED_OFF" and c.weekday == j.weekday():
                            val = "FIXED_OFF"
                            break
                    planning[e.name][date_str] = val
                else:
                    main_shift = ""
                    for s_id in e.qualifications:
                        if (e.id, j, s_id) in assign and solver.Value(assign[e.id, j, s_id]) == 1:
                            main_shift = s_id
                            break
                    planning[e.name][date_str] = main_shift if main_shift else "ERR_NO_SHIFT"
        return planning