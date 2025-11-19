# Fichier: src/reporter.py
from collections import defaultdict

def generate_text_report(report_data: dict, planning_grid: dict) -> str:
    """Génère un rapport d'audit détaillé au format texte, avec des tableaux."""
    
    lines = []
    lines.append("=========================================================================")
    lines.append("                       RAPPORT DE PLANIFICATION                      ")
    lines.append("=========================================================================")
    lines.append(f"SCORE DE PÉNALITÉ TOTAL : {int(report_data.get('score', 0))}")
    lines.append(f"SHIFTS NON COUVERTS     : {report_data.get('total_uncovered', 0)}")
    lines.append("")
    
    # --- Section 1 : Pénalités Actives ---
    lines.append("--- [1] ANALYSE DES PÉNALITÉS (Violations des règles molles) ---")
    penalties = report_data.get('penalties', [])
    if not penalties:
        lines.append("  Aucune pénalité majeure détectée. Planning parfait.")
    else:
        sorted_penalties = sorted(penalties, key=lambda x: (x['agent'], x['cost']))
        for p in sorted_penalties:
            lines.append(f"  [COÛT {p['cost']}] {p['agent']} : {p['reason']}")
    lines.append("")

    # --- Section 2 : Statistiques Globales ---
    lines.append("--- [2] STATISTIQUES RH GLOBALES ---")
    stats = report_data.get('stats', {})
    lines.append(f"  Moyenne Jours OFF : {stats.get('avg_off', 0):.1f}")
    lines.append(f"  Min Jours OFF     : {stats.get('min_off', 0)} (Employé: {stats.get('min_off_agent', 'N/A')})")
    lines.append(f"  Agents sans Weekend : {stats.get('nb_no_weekend', 0)}")
    lines.append("")

    # --- NOUVELLE SECTION 3: AUDIT D'ÉQUITÉ PROPORTIONNELLE ---
    lines.append("--- [3] AUDIT D'ÉQUITÉ PAR QUALIFICATION (Shifts partagés) ---")
    qualif_report = report_data.get('qualif_equity_report', {})
    if not qualif_report:
        lines.append("  Aucune qualification partagée n'a été analysée.")
    else:
        lines.append(f"| {'QUALIFICATION':<12} | {'MIN':<3} | {'MAX':<3} | {'ÉCART':<4} | DÉTAIL (Agent:Nb) |")
        lines.append(f"|:{'-'*12}-|:{'-'*3}-|:{'-'*3}-|:{'-'*4}-|:------------------|")
        
        for s_id, q_stats in sorted(qualif_report.items()):
            counts = [s['count'] for s in q_stats]
            if not counts: continue
            min_c, max_c = min(counts), max(counts)
            gap = max_c - min_c
            
            if gap > 1: # N'affiche que les écarts significatifs
                detail_str = ", ".join([f"{s['name'].split(' ')[0]}:{s['count']}" for s in q_stats])
                lines.append(f"| {s_id:<12} | {min_c:<3} | {max_c:<3} | {gap:<4} | {detail_str} |")
    lines.append("")

    # --- NOUVELLE SECTION 4: DÉTAIL PAR FAMILLE MÉTIER ---
    lines.append("--- [4] DÉTAIL PAR EMPLOYÉ (Regroupé par Famille Métier) ---")
    
    emp_details = report_data.get('employees_details', {})
    agents_in_families = set()
    
    header = f"| {'GROUPE':<17} | {'NOM DE L\'AGENT':<25} | {'OFF':<3} | {'TRAVAIL':<7} | {'HEURES':<6} | {'COMPTE PAR FONCTION'} |"
    lines.append(header)
    lines.append(f"|:{'-'*17}-|:{'-'*25}-|:{'-'*3}-|:{'-'*7}-|:{'-'*6}-|:------------------------|")

    families_report = report_data.get('families_report', {})
    
    # Itérer sur le dictionnaire de familles (qui est maintenant ordonné)
    for group_name, family_group in families_report.items():
        if not family_group: continue
        
        lines.append(f"|{'-'*17} | {'-'*25} | {'-'*3} | {'-'*7} | {'-'*6} | {'-'*24} |")

        # Calculer les écarts pour cette famille
        family_hours = [emp_details.get(e.name, {}).get('total_hours', 0) for e in family_group]
        family_off = [emp_details.get(e.name, {}).get('days_off', 0) for e in family_group]
        
        min_h, max_h = (min(family_hours), max(family_hours)) if family_hours else (0, 0)
        min_o, max_o = (min(family_off), max(family_off)) if family_off else (0, 0)
        
        lines.append(f"| {group_name:<17} | {'(ÉQUITÉ GROUPE)':<25} | {max_o - min_o:<3}j | {'':<7} | {max_h - min_h:<6.1f}h | (Écarts Heures/Jours OFF) |")
        lines.append(f"|{'-'*17} | {'-'*25} | {'-'*3} | {'-'*7} | {'-'*6} | {'-'*24} |")

        for agent in sorted(family_group, key=lambda x: x.name):
            agent_name = agent.name
            details = emp_details.get(agent_name)
            if not details: continue
            
            agents_in_families.add(agent_name)
            
            fonc_str = ", ".join([f"{k}:{v}" for k, v in sorted(details["fonctions_breakdown"].items())])
            
            lines.append(
                f"| {'':<17} | {details['name']:<25} | "
                f"{details['days_off']:<3} | {details['days_work']:<7} | "
                f"{details['total_hours']:<6.1f} | {fonc_str} |"
            )

    # Note: Les agents "Autres" seront affichés ici
    
    lines.append("")

    # --- Section 5 : Résumé Journalier ---
    lines.append("--- [5] RÉSUMÉ DE LA COUVERTURE JOURNALIÈRE (Shifts Assignés) ---")
    if not planning_grid:
        lines.append("  Données du planning non disponibles pour l'audit journalier.")
    else:
        daily_totals = defaultdict(lambda: defaultdict(int))
        all_dates = sorted(next(iter(planning_grid.values())).keys())
        
        for emp_name, schedule in planning_grid.items():
            for date_str, assignment in schedule.items():
                if assignment not in ['OFF', 'HOLIDAY', 'FIXED_OFF', 'ERR_NO_SHIFT']:
                    daily_totals[date_str][assignment] += 1
                                
        for date_str in all_dates:
            totals_for_day = daily_totals[date_str]
            if not totals_for_day:
                lines.append(f"  {date_str} : (Aucun shift assigné)")
                continue
            
            summary_list = [f"{count}x {shift}" for shift, count in sorted(totals_for_day.items())]
            lines.append(f"  {date_str} : {', '.join(summary_list)}")
            
    lines.append("")
    lines.append("=========================================================================")
    
    return "\n".join(lines)