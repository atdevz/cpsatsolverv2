import pandas as pd
import json
import os
import re
from collections import defaultdict
from datetime import datetime
import argparse

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_CSV = os.path.join(BASE_DIR, "planning_brut.csv")
DEFAULT_OUTPUT_JSON = os.path.join(BASE_DIR, "04_daily_needs_DEBUG.json")

class NeedExtractorDebug:
    def __init__(self, input_csv_path=DEFAULT_INPUT_CSV, output_json_path=DEFAULT_OUTPUT_JSON):
        self.input_csv = input_csv_path
        self.output_json = output_json_path
        self.daily_counts = defaultdict(lambda: defaultdict(int))

    def is_date(self, text):
        """Vérifie si un texte ressemble à une date."""
        text = str(text).strip()
        # Patterns : JJ/MM/AA, JJ/MM/AAAA, AAAA-MM-JJ
        patterns = [
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", # 01/12/25
            r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"    # 2025-12-01
        ]
        for p in patterns:
            if re.match(p, text):
                return True
        return False

    def run(self):
        print(f"\n--- DÉBUT DU DIAGNOSTIC ---", flush=True)
        print(f"Fichier cible : {self.input_csv}", flush=True)

        if not os.path.exists(self.input_csv):
            print(f"ERREUR FATALE : Le fichier {self.input_csv} n'est pas trouvé.", flush=True)
            return

        # 1. Lecture brute pour trouver la ligne des dates
        print("1. Recherche de la ligne des dates...", flush=True)
        df_raw = pd.read_csv(self.input_csv, header=None, dtype=str, sep=None, engine='python')
        
        date_row_index = -1
        for idx, row in df_raw.iterrows():
            # Compte combien de cellules ressemblent à des dates sur cette ligne
            date_count = sum(1 for cell in row if self.is_date(cell))
            print(f"   Ligne {idx} : {list(row.values)[:4]}... -> {date_count} dates trouvées.", flush=True)
            
            if date_count > 5: # Si plus de 5 dates sur la ligne, c'est la bonne !
                date_row_index = idx
                print(f"   >>> TROUVÉ ! Les dates sont à la ligne {idx}.", flush=True)
                break
        
        if date_row_index == -1:
            print("ERREUR : Impossible de trouver une ligne contenant des dates (JJ/MM/AA).", flush=True)
            print("Vérifiez que votre Excel contient bien des vraies dates (ex: 01/12/2025).", flush=True)
            return

        # 2. Rechargement propre avec la bonne ligne d'en-tête
        print(f"\n2. Extraction des shifts à partir de la ligne {date_row_index}...", flush=True)
        df = pd.read_csv(self.input_csv, header=date_row_index, dtype=str, sep=None, engine='python')
        
        valid_days = 0
        for col in df.columns:
            # Tentative de parsing de date
            try:
                date_obj = pd.to_datetime(col, dayfirst=True, errors='coerce')
                if pd.isna(date_obj): continue
                
                date_str = date_obj.strftime("%Y-%m-%d")
                
                # Extraction des shifts
                shifts = df[col].dropna()
                count = 0
                for s in shifts:
                    s = str(s).strip()
                    if s.upper() not in ["OFF", "RH", "NAN", ""]:
                        self.daily_counts[date_str][s] += 1
                        count += 1
                
                if count > 0: valid_days += 1
                
            except: pass

        print(f"   -> {valid_days} jours avec des shifts trouvés.", flush=True)

        # 3. Export
        final_list = []
        for d, shifts in self.daily_counts.items():
            for s, c in shifts.items():
                final_list.append({"date_str": d, "shift_id": s, "count": c})
        
        if self.output_json:
            with open(self.output_json, 'w', encoding='utf-8') as f:
                json.dump(final_list, f, indent=4)
                
            print(f"\n3. Résultat :", flush=True)
            print(f"   Fichier généré : {self.output_json}", flush=True)
            print(f"   Nombre d'entrées : {len(final_list)}", flush=True)
            
            if len(final_list) == 0:
                print("   ATTENTION : Le fichier est vide. Vos colonnes de shifts semblent vides ou illisibles.", flush=True)
            else:
                print("   SUCCÈS ! Copiez le contenu de ce fichier DEBUG vers votre vrai fichier daily_needs.", flush=True)
        else:
            print(json.dumps(final_list, indent=4), flush=True) # Print to stdout for web app
            print("\n--- FIN DU DIAGNOSTIC (JSON imprimé sur stdout) ---", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrait les besoins quotidiens d'un fichier CSV de planning.")
    parser.add_argument("--csv_path", default=DEFAULT_INPUT_CSV, help="Chemin vers le fichier CSV de planning (ex: tool/planning_brut.csv).")
    parser.add_argument("--output_json_path", default=None, help="Chemin vers le fichier JSON de sortie. Si non spécifié, imprime sur stdout.")

    args = parser.parse_args()

    extractor = NeedExtractorDebug(input_csv_path=args.csv_path, output_json_path=args.output_json_path)
    extractor.run()
