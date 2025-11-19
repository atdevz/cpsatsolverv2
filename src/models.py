# Fichier: src/models.py

from dataclasses import dataclass, field
from datetime import date
from typing import List, Set, Optional

# Constante pour les calculs de temps (utilisée dans __post_init__)
MINUTES_IN_DAY = 24 * 60 # 1440

# Dictionnaire pour traduire les contraintes textuelles en chiffres (0=Lundi... 6=Dimanche)
DAY_OF_WEEK_MAP = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6
}

@dataclass
class Constraint:
    """
    Représente une contrainte fixe pour un employé,
    traduite depuis le fichier JSON.
    """
    type: str  # ex: "HOLIDAY", "FIXED_OFF", "NOT_WEEKEND"
    
    # Utilisé si type="HOLIDAY"
    date: Optional[date] = None 
    
    # Utilisé si type="FIXED_OFF" (0=Lundi, 1=Mardi...)
    weekday: Optional[int] = None
    
    # Utilisé si type="MAX_HOURS" ou "MAX_SHIFTS_PER_QUALIF"
    value: Optional[int] = None
    
    # Utilisé si type="MAX_SHIFTS_PER_QUALIF"
    qualif: Optional[str] = None


@dataclass
class Shift:
    """
    Représente un shift unique (une "pièce" du puzzle).
    """
    id: str  # ex: "A10-GS"
    start_time_str: str  # ex: "07:45"
    end_time_str: str    # ex: "15:15"
    
    # --- CHAMPS CALCULÉS (Nécessaires pour la règle des 11h) ---
    # init=False : On ne les passe pas à la création, ils sont calculés seuls.
    start_minutes: int = field(init=False)
    end_minutes: int = field(init=False)
    duration_minutes: int = field(init=False)
    
    # On garde tags optionnel pour éviter les erreurs si jamais on veut l'utiliser plus tard
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """
        Calcule les minutes automatiquement après la création de l'objet.
        C'est ici qu'on convertit "07:45" en 465 minutes.
        """
        
        def _time_to_minutes(time_str: str) -> int:
            try:
                if not time_str or ":" not in time_str:
                    print(f"  [Model] ERREUR: Format d'heure invalide pour shift {self.id}: '{time_str}'")
                    return 0
                h, m = map(int, time_str.split(':'))
                return h * 60 + m
            except ValueError:
                print(f"  [Model] ERREUR: Impossible de lire l'heure pour shift {self.id}: '{time_str}'")
                return 0

        # Calcul des minutes (Vital pour utils.calculate_toxic_pairs)
        self.start_minutes = _time_to_minutes(self.start_time_str)
        self.end_minutes = _time_to_minutes(self.end_time_str)
        
        # Gestion du shift de nuit (qui finit le lendemain)
        if self.end_minutes < self.start_minutes:
            self.duration_minutes = (MINUTES_IN_DAY - self.start_minutes) + self.end_minutes
        else:
            self.duration_minutes = self.end_minutes - self.start_minutes


@dataclass
class Employee:
    """
    Représente un employé, avec ses qualifications DÉJÀ TRADUITES.
    """
    id: str
    name: str
    fonctions: Set[str]
    
    # La liste finale des "shift_id" que cet agent peut faire
    qualifications: Set[str] 
    
    # La liste des contraintes fixes parsées
    constraints: List[Constraint]

    def can_do_shift(self, shift_id: str) -> bool:
        """Vérifie si cet employé peut faire un shift donné."""
        return shift_id in self.qualifications


@dataclass
class Need:
    """
    Représente un besoin quotidien pour un shift donné.
    """
    date: date
    shift_id: str
    count: int