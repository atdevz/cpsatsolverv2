# Fichier: src/utils.py

import json
from datetime import date, timedelta
from typing import List, Dict, Tuple, Set, Any
from src.models import Shift

# Constante pour les calculs de temps
MINUTES_IN_DAY = 24 * 60 # 1440

def get_date_range_from_needs(needs: List) -> List[date]:
    """
    Trouve le premier et le dernier jour du mois à partir de la liste des besoins.
    """
    if not needs:
        print("  [Utils] AVERTISSEMENT: Aucun besoin chargé, impossible de déterminer la plage de dates.")
        return []
    
    all_dates_set = set(n.date for n in needs)
    if not all_dates_set:
        return []
        
    start_date = min(all_dates_set)
    end_date = max(all_dates_set)
    
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)
        
    print(f"  [Utils] Plage de dates déterminée : {start_date} à {end_date}")
    return date_list

def get_weekends_in_range(date_range: List[date]) -> List[Tuple[date, date]]:
    """
    Trouve tous les couples (Samedi, Dimanche).
    """
    weekends = []
    all_dates_set = set(date_range)

    for day in date_range:
        # 5 = Samedi
        if day.weekday() == 5:
            sunday = day + timedelta(days=1)
            if sunday in all_dates_set:
                weekends.append((day, sunday))
    print(f"  [Utils] Trouvé {len(weekends)} weekends dans le mois.")
    return weekends

def calculate_toxic_pairs(
    shifts_map: Dict[str, Shift], 
    min_rest_hours: int
) -> Set[Tuple[str, str]]:
    """
    Calcule les transitions interdites (11h de repos).
    Retourne un set de tuples (shift_tard, shift_tot).
    """
    print(f"  [Utils] Calcul des transitions de shift interdites (règle de {min_rest_hours}h)...")
    
    toxic_pairs = set()
    min_rest_minutes = min_rest_hours * 60 

    shift_list = list(shifts_map.values())

    for shift_tard in shift_list:
        for shift_tot in shift_list:
            
            # Temps de repos = (Fin Jour J -> Minuit) + (Minuit -> Début Jour J+1)
            rest_day_1 = MINUTES_IN_DAY - shift_tard.end_minutes
            rest_day_2 = shift_tot.start_minutes
            total_rest = rest_day_1 + rest_day_2

            if total_rest < min_rest_minutes:
                toxic_pairs.add((shift_tard.id, shift_tot.id))

    print(f"  [Utils] Trouvé {len(toxic_pairs)} transitions de shift interdites.")
    return toxic_pairs