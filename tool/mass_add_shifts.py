import pandas as pd
import os
import re
from datetime import datetime, timedelta
import argparse

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "planning_brut.csv")

# Mapping des jours
JOURS_SEMAINE = {
    "LUNDI": 0, "MARDI": 1, "MERCREDI": 2, "JEUDI": 3, 
    "VENDREDI": 4, "SAMEDI": 5, "DIMANCHE": 6
}

class MassShiftManager:
    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        self.df = None
        self.header_row_idx = 0
        self.date_map = {} 

    def load(self):
        if not os.path.exists(self.csv_path):
            print(f"ERREUR : Fichier {self.csv_path} introuvable.")
            return False

        try:
            # 1. Détection en-tête
            df_raw = pd.read_csv(self.csv_path, header=None, dtype=str, sep=None, engine='python')
            for idx, row in df_raw.iterrows():
                dates_found = sum(1 for cell in row if self._is_date(cell))
                if dates_found > 5:
                    self.header_row_idx = idx
                    break
            
            # 2. Chargement
            self.df = pd.read_csv(self.csv_path, header=self.header_row_idx, dtype=str, sep=None, engine='python')
            
            # 3. Mapping dates
            for col in self.df.columns:
                try:
                    d_obj = pd.to_datetime(col, dayfirst=True, errors='coerce')
                    if not pd.isna(d_obj):
                        self.date_map[d_obj.strftime("%Y-%m-%d")] = col
                except: pass
            
            print(f"Planning chargé : {len(self.date_map)} jours identifiés.")
            return True
        except Exception as e:
            print(f"Erreur chargement : {e}")
            return False

    def _is_date(self, text):
        return bool(re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", str(text).strip()))

    def _add_single_shift(self, date_str, shift_code):
        col_name = self.date_map[date_str]
        series = self.df[col_name]
        
        # Cherche le premier trou vide
        empty_indices = series[series.isna() | (series == "")].index.tolist()
        
        if empty_indices:
            self.df.at[empty_indices[0], col_name] = shift_code
        else:
            # Crée nouvelle ligne
            new_idx = len(self.df)
            self.df.loc[new_idx] = ""
            self.df.at[new_idx, col_name] = shift_code

    def add_shift_for_month(self, shift_code, count_per_day, year_month):
        try:
            year, month = map(int, year_month.split('-'))
            start_date = datetime(year, month, 1)
            # Calculate the last day of the month
            end_date = datetime(year, month, 1) + timedelta(days=31)
            end_date = end_date.replace(day=1) - timedelta(days=1)
            
            current_date = start_date
            total_added = 0

            while current_date <= end_date:
                date_str_formatted = current_date.strftime("%Y-%m-%d")
                if date_str_formatted in self.date_map:
                    for _ in range(count_per_day):
                        self._add_single_shift(date_str_formatted, shift_code)
                        total_added += 1
                current_date += timedelta(days=1)
            print(f"[MASS ADD] Ajouté '{shift_code}' {count_per_day} fois par jour pour {year_month}. Total: {total_added} shifts.")
        except Exception as e:
            print(f"ERREUR lors de l'ajout en masse de shifts : {e}")

    def save(self):
        try:
            self.df.to_csv(self.csv_path, index=False, sep=',')
            print(f"--- Sauvegarde réussie dans {self.csv_path} ---")
        except PermissionError:
            print("ERREUR CRITIQUE : Fermez le fichier Excel avant de lancer le script !")

# ==========================================
#           ZONE DE CONFIGURATION
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gérer les shifts en masse dans le fichier planning_brut.csv.")
    parser.add_argument("--action", required=True, choices=["add_month"], help="Action à effectuer (add_month).")
    parser.add_argument("--shift_id", help="ID du shift à ajouter (ex: A10-GS).")
    parser.add_argument("--count", type=int, default=1, help="Nombre de fois où ajouter le shift par jour.")
    parser.add_argument("--month", help="Mois au format YYYY-MM pour l'ajout en masse.")

    args = parser.parse_args()

    manager = MassShiftManager()
    
    if manager.load():
        if args.action == "add_month":
            if not args.shift_id or not args.month:
                print("ERREUR : --shift_id et --month sont requis pour l'action add_month.")
            else:
                manager.add_shift_for_month(args.shift_id, args.count, args.month)
        manager.save()
