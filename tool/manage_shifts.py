import pandas as pd
import os
import re
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "planning_brut.csv")

class ShiftEditor:
    def __init__(self):
        self.df = None
        self.header_row_idx = 0
        self.date_map = {} # Pour lier "2025-12-01" -> "01/12/25" (Nom de la colonne)

    def load(self):
        """Charge le CSV et indexe les colonnes dates."""
        if not os.path.exists(CSV_PATH):
            print("ERREUR : Fichier introuvable.")
            return False

        # 1. Trouver la ligne des en-têtes (comme dans extract_needs)
        try:
            df_raw = pd.read_csv(CSV_PATH, header=None, dtype=str, sep=None, engine='python')
        except:
            print("Erreur de lecture du fichier.")
            return False

        for idx, row in df_raw.iterrows():
            # On cherche une ligne avec > 5 dates
            dates_found = sum(1 for cell in row if self._is_date(cell))
            if dates_found > 5:
                self.header_row_idx = idx
                break
        
        # 2. Charger le DataFrame propre
        self.df = pd.read_csv(CSV_PATH, header=self.header_row_idx, dtype=str, sep=None, engine='python')
        
        # 3. Créer la carte des dates
        print(f"--- Chargement du planning ---")
        for col in self.df.columns:
            try:
                d_obj = pd.to_datetime(col, dayfirst=True, errors='coerce')
                if not pd.isna(d_obj):
                    std_date = d_obj.strftime("%Y-%m-%d") # Clé standard: 2025-12-01
                    self.date_map[std_date] = col         # Valeur réelle: 01/12/25
            except: pass
        
        print(f"Planning chargé : {len(self.date_map)} jours identifiés.")
        return True

    def _is_date(self, text):
        text = str(text).strip()
        return bool(re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text))

    def add_shift(self, date_str, shift_code):
        """Ajoute un shift à la fin de la liste pour ce jour."""
        if date_str not in self.date_map:
            print(f"[ERREUR] Date inconnue dans le fichier : {date_str}")
            return

        col_name = self.date_map[date_str]
        shift_code = shift_code.upper()

        # Récupérer la colonne
        series = self.df[col_name]
        
        # Trouver le premier index vide (NaN ou string vide)
        empty_indices = series[series.isna() | (series == "")].index.tolist()
        
        if empty_indices:
            target_idx = empty_indices[0]
            self.df.at[target_idx, col_name] = shift_code
        else:
            # Si la colonne est pleine, on ajoute une nouvelle ligne à tout le tableau
            new_idx = len(self.df)
            self.df.loc[new_idx] = "" # Crée ligne vide
            self.df.at[new_idx, col_name] = shift_code
            
        print(f"  [+] Ajouté : {shift_code} le {date_str}")

    def remove_shift(self, date_str, shift_code):
        """Supprime UN shift (le premier trouvé) et tasse la colonne."""
        if date_str not in self.date_map:
            print(f"[ERREUR] Date inconnue : {date_str}")
            return

        col_name = self.date_map[date_str]
        shift_code = shift_code.upper()
        
        # Trouver les lignes qui contiennent ce shift
        mask = self.df[col_name] == shift_code
        indices = self.df[mask].index.tolist()
        
        if not indices:
            print(f"  [!] Impossible de supprimer {shift_code} le {date_str} : Non trouvé.")
            return

        # On supprime le premier trouvé
        target_idx = indices[0]
        self.df.at[target_idx, col_name] = None # On met vide
        
        # OPTIONNEL : "Tasser" la colonne pour ne pas laisser de trou
        # On prend toutes les valeurs non-vides de la colonne
        values = self.df[col_name].dropna().tolist()
        # On efface la colonne
        self.df[col_name] = None
        # On remplit avec la liste tassée
        for i, val in enumerate(values):
            self.df.at[i, col_name] = val

        print(f"  [-] Supprimé : {shift_code} le {date_str}")

    def save(self):
        """Sauvegarde le CSV."""
        try:
            self.df.to_csv(CSV_PATH, index=False, sep=',')
            print(f"--- Sauvegarde réussie dans {CSV_PATH} ---")
        except PermissionError:
            print("ERREUR CRITIQUE : Fermez le fichier Excel avant de lancer le script !")

# ==========================================
#              UTILISATION
# ==========================================
if __name__ == "__main__":
    editor = ShiftEditor()
    
    if editor.load():
        
        # --- ZONE D'ÉDITION ---
        
        # 1. AJOUTER DES SHIFTS (Date AAAA-MM-JJ, Code Shift)
        editor.add_shift("2025-12-01", "RENFORT-NUIT")
        editor.add_shift("2025-12-01", "LEAD-MATIN")
        
        # 2. SUPPRIMER DES SHIFTS
        editor.remove_shift("2025-12-02", "A10-GS") # Supprime un A10-GS du 2 déc

        # 3. SAUVEGARDER
        editor.save()