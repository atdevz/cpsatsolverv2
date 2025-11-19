# Fichier: main.py

import json
import sys
import pandas as pd
from datetime import date
from src.data_loader import DataLoader
from src.solver import CpSatSolver
import src.utils as utils
import src.reporter as reporter
from collections import defaultdict
import os

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config/settings.json")
EMPLOYEES_PATH = os.path.join(BASE_DIR, "data/input/01_employees.json")
FONCTIONS_PATH = os.path.join(BASE_DIR, "data/input/02_fonctions.json")
SHIFTS_PATH = os.path.join(BASE_DIR, "data/input/03_shifts_master.json")
NEEDS_PATH = os.path.join(BASE_DIR, "data/input/04_daily_needs.json")
GROUPS_PATH = os.path.join(BASE_DIR, "data/input/05_groups.json")

# Nouveaux noms de fichiers demandés
OUTPUT_CSV_PATH = os.path.join(BASE_DIR, "data/output/Planning.csv")
OUTPUT_REPORT_PATH = os.path.join(BASE_DIR, "data/output/Report.txt")

def run():
    print("--- [1/6] Démarrage du Planificateur ---")
    
    # 1. Chargement
    loader = DataLoader(CONFIG_PATH, EMPLOYEES_PATH, FONCTIONS_PATH, SHIFTS_PATH, NEEDS_PATH, GROUPS_PATH)
    all_data = loader.load_all_data()
    
    print("\n--- [2/6] Vérification des Données ---")
    if not all_data.get('daily_needs'):
        print("ERREUR: Données manquantes (daily_needs vide).")
        sys.exit()
    print("  SUCCÈS: Données OK.")

    print("\n--- [3/6] Analyse des familles et besoins ---")
    print(f"  {len(all_data['employee_families'])} familles d'employés chargées.")
    
    # Calcul des besoins totaux pour info
    total_needs_per_shift = defaultdict(int)
    for need in all_data["daily_needs"]:
        total_needs_per_shift[need.shift_id] += need.count
    all_data["total_needs_per_shift"] = total_needs_per_shift
    print(f"  Volume total de shifts demandés : {sum(total_needs_per_shift.values())}")

    # Ajout manuel de la map des fonctions (nécessaire pour le Solver)
    all_data["fonctions_map"] = loader._load_fonctions()
    
    print("\n--- [4/6] Pré-calcul des contraintes ---")
    # Calcul des 11h de repos et des weekends
    toxic_pairs = utils.calculate_toxic_pairs(all_data["shifts_map"], all_data["config"]["min_rest_hours"])
    all_data["weekends"] = utils.get_weekends_in_range(all_data["date_range"])

    print("\n--- [5/6] Lancement du Solveur (CpSatSolver) ---")
    solver = CpSatSolver(all_data, toxic_pairs)
    solver.create_model() # Construit le modèle
    
    # Résolution unique (plus de refiner)
    planning, report_data = solver.solve()

    print("\n--- [6/6] Sauvegarde des résultats ---")
    if planning:
        try:
            # 1. Sauvegarde du CSV (Planning.csv)
            df = pd.DataFrame.from_dict(planning, orient='index')
            # Tri des colonnes par date
            df = df[sorted(df.columns)] 
            df.to_csv(OUTPUT_CSV_PATH, index_label="Employee")
            print(f"  >> Planning sauvegardé : {OUTPUT_CSV_PATH}")
            
            # 2. Sauvegarde du Rapport (Report.txt)
            if report_data:
                report_text = reporter.generate_text_report(report_data, planning)
                with open(OUTPUT_REPORT_PATH, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                print(f"  >> Rapport sauvegardé  : {OUTPUT_REPORT_PATH}")
                
        except Exception as e:
            print(f"ERREUR CRITIQUE lors de la sauvegarde : {e}")
    else:
        print("\n[FIN] Aucune solution trouvée. Vérifiez vos contraintes.")

if __name__ == "__main__":
    # Création du dossier output s'il n'existe pas
    os.makedirs(os.path.dirname(OUTPUT_CSV_PATH), exist_ok=True)
    run()