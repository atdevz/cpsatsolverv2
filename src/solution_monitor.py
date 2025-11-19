# Fichier: src/solution_monitor.py

from ortools.sat.python import cp_model

class SolutionMonitor(cp_model.CpSolverSolutionCallback):
    """
    Un "espion" qui surveille le processus de résolution et affiche chaque
    nouvelle solution trouvée par le solveur.
    """
    def __init__(self, objective_var):
        """
        Initialise le moniteur.
        
        Args:
            objective_var: La variable d'objectif du modèle (la somme des pénalités)
                           pour pouvoir afficher le score.
        """
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0
        self.__objective_var = objective_var

    def on_solution_callback(self):
        """
        Cette méthode est appelée automatiquement par le solveur chaque fois
        qu'une nouvelle solution (généralement meilleure) est trouvée.
        """
        current_objective = self.ObjectiveValue()
        print(f"  -> Nouvelle solution  (N°{self.__solution_count}) | Score : {current_objective:.2f}")
        self.__solution_count += 1

    def solution_count(self):
        """Retourne le nombre total de solutions trouvées."""
        return self.__solution_count
