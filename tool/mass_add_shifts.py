import pandas as pd
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "planning_brut.csv")

# Mapping des jours
JOURS_SEMAINE = {
    "LUNDI": 0, "MARDI": 1, "MERCREDI": 2, "JEUDI": 3, 
    "VENDREDI": 4, "SAMEDI": 5, "DIMANCHE": 6
}

class MassShiftManager:
    def __init__(self):
        self.df = None
        self.header_row_idx = 0
        self.date_map = {} 

    def load(self):
        if not os.path.exists(CSV_PATH):
            print("ERREUR : Fichier planning_brut.csv introuvable.")
            return False

        try:
            # 1. Détection en-tête
            df_raw = pd.read_csv(CSV_PATH, header=None, dtype=str, sep=None, engine='python')
            for idx, row in df_raw.iterrows():
                dates_found = sum(1 for cell in row if self._is_date(cell))
                if dates_found > 5:
                    self.header_row_idx = idx
                    break
            
            # 2. Chargement
            self.df = pd.read_csv(CSV_PATH, header=self.header_row_idx, dtype=str, sep=None, engine='python')
            
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

    # --- FONCTIONS DE MASSE (CORRIGÉES) ---

    def add_every_day(self, *shift_codes):
        """
        Ajoute une liste de shifts pour TOUS les jours du mois.
        Usage: manager.add_every_day("A", "B", "C")
        """
        for code in shift_codes:
            count = 0
            for date_str in self.date_map:
                self._add_single_shift(date_str, code)
                count += 1
            print(f"  [GLOBAL] Ajouté '{code}' sur {count} jours.")

    def add_weekly(self, jour_nom, *shift_codes):
        """
        Ajoute une liste de shifts pour un jour spécifique.
        Usage: manager.add_weekly("LUNDI", "A", "B")
        """
        jour_nom = jour_nom.upper().strip()
        if jour_nom not in JOURS_SEMAINE:
            print(f"ERREUR : Jour '{jour_nom}' inconnu.")
            return

        target_weekday = JOURS_SEMAINE[jour_nom]
        
        for code in shift_codes:
            count = 0
            for date_str in self.date_map:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt.weekday() == target_weekday:
                    self._add_single_shift(date_str, code)
                    count += 1
            print(f"  [HEBDO]  Ajouté '{code}' tous les {jour_nom} ({count} fois).")

    def save(self):
        try:
            self.df.to_csv(CSV_PATH, index=False, sep=',')
            print(f"--- Sauvegarde réussie dans planning_brut.csv ---")
        except PermissionError:
            print("ERREUR CRITIQUE : Fermez le fichier Excel avant de lancer le script !")

# ==========================================
#           ZONE DE CONFIGURATION
# ==========================================
if __name__ == "__main__":
    manager = MassShiftManager()
    
    if manager.load():
        
        # C'est ici que vous mettez vos shifts (séparés par des virgules)
        # Cela fonctionnera maintenant !
        #manager.add_every_day("G01-GS", "G02-GS", "G03-GS", "G04-GS", "ISA1-GS", "ISA2")
        manager.add_weekly("SAMEDI", "ISA3-GS")
        manager.add_weekly("DIMANCHE", "ISA3-GS")        
        # Exemple pour ajouter plusieurs shifts le lundi
        # manager.add_weekly("SAMEDI", "ISA3-GS")
        # manager.add_weekly("DIMANCHE", "ISA3-GS")
        manager.save()