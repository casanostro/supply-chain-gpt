"""
semantic_layer.py — Couche sémantique : la source de vérité unique des KPIs supply chain.

Chaque métrique est définie UNE SEULE FOIS ici, avec :
  - sa définition métier (celle qu'un Demand Planner ou un Resp. Appro reconnaît)
  - sa formule SQL canonique
  - ses synonymes (le vocabulaire réel des équipes terrain)
  - ses pièges connus (ce qui fait qu'un LLM — ou un stagiaire — se trompe)

Cette couche est ensuite rendue en Markdown et injectée dans le system prompt :
le prompt ne contient donc jamais de définition dupliquée ou obsolète.
Modifier une métrique ici met à jour le prompt, la doc et les évals d'un coup.
"""

from typing import Dict, List, Optional

METRIQUES: List[Dict] = [
    {
        "nom": "Taux de Service (TS)",
        "synonymes": ["taux de service", "TS", "service rate", "taux de livraison"],
        "definition": "Part des quantités commandées effectivement livrées. Objectif métier : ≥ 97 %.",
        "sql": "ROUND(SUM(lc.qte_livree) * 100.0 / NULLIF(SUM(lc.qte_commandee), 0), 1)",
        "grain": "lignes_commande (JAMAIS au niveau colis : nb_colis_livres est un agrégat entête, moins fiable)",
        "pieges": [
            "Exclure les lignes non encore livrées : qte_livree IS NOT NULL (commandes en_cours).",
            "NULLIF au dénominateur : une division par zéro ne doit jamais remonter à l'utilisateur.",
            "Ne PAS moyenner des taux par ligne (AVG de ratios) : toujours SUM/SUM.",
        ],
    },
    {
        "nom": "Taux de Rupture",
        "synonymes": ["rupture", "en rupture", "ruptures", "produits en rupture", "taux de rupture"],
        "definition": "Part des couples produit × entrepôt sans stock disponible. Objectif métier : ≤ 3 %.",
        "sql": "flag_rupture = 1  -- au dernier snapshot uniquement",
        "grain": "stocks, au snapshot le plus récent",
        "pieges": [
            "La table stocks contient PLUSIEURS snapshots datés : sans filtre "
            "s.date_snapshot = (SELECT MAX(date_snapshot) FROM stocks), on compte 3x trop de ruptures.",
            "flag_rupture = 1 équivaut à stock_disponible = 0 ; ne pas cumuler les deux conditions avec OR "
            "sur des snapshots différents.",
        ],
    },
    {
        "nom": "SLOB (Slow moving & Obsolete)",
        "synonymes": ["SLOB", "stock dormant", "stock mort", "surstock", "rossignols"],
        "definition": "Stock dont la couverture dépasse 90 jours de ventes. Se valorise en € d'achat.",
        "sql": "flag_slob = 1  -- ou couverture_jours > 90, au dernier snapshot",
        "grain": "stocks, au snapshot le plus récent",
        "pieges": [
            "Valorisation = SUM(s.stock_physique * p.prix_achat_ht) — jamais le prix de vente (inconnu ici).",
            "Toujours filtrer sur le dernier snapshot, comme pour les ruptures.",
        ],
    },
    {
        "nom": "Points Perdus",
        "synonymes": ["points perdus", "colis manquants", "manquants", "écart de livraison", "pertes"],
        "definition": "Volume commandé non livré : la mesure directe de ce que la rupture coûte en volume. "
                      "En valeur : multiplier par prix_unitaire_ht.",
        "sql": "SUM(lc.qte_commandee - COALESCE(lc.qte_livree, 0))",
        "grain": "lignes_commande livrées ou partielles",
        "pieges": [
            "COALESCE(qte_livree, 0) uniquement sur les commandes soldées ; exclure les en_cours "
            "(sinon on compte comme perdu ce qui n'est pas encore arrivé).",
        ],
    },
    {
        "nom": "Couverture de stock",
        "synonymes": ["couverture", "jours de stock", "DIO", "jours de couverture"],
        "definition": "Nombre de jours de ventes que le stock actuel permet de tenir. Pré-calculée dans stocks.couverture_jours.",
        "sql": "s.couverture_jours",
        "grain": "stocks, au snapshot le plus récent",
        "pieges": [
            "Ne PAS recalculer la couverture à partir des commandes : le champ pré-calculé fait foi.",
            "couverture_jours = 0 avec stock_physique = 0 signifie rupture, pas rotation infinie.",
        ],
    },
    {
        "nom": "Taux de Retard",
        "synonymes": ["retard", "en retard", "retards de livraison", "ponctualité", "OTIF (partiel)"],
        "definition": "Part des commandes livrées après la date prévue.",
        "sql": "SUM(CASE WHEN c.date_livraison_reelle > c.date_livraison_prevue THEN 1 ELSE 0 END) * 100.0 "
               "/ NULLIF(COUNT(*), 0)",
        "grain": "commandes avec date_livraison_reelle non nulle",
        "pieges": [
            "date_livraison_reelle IS NULL = commande en cours, pas en retard : l'exclure du dénominateur.",
            "Comparaison de dates ISO 8601 : la comparaison lexicale SQLite est correcte, pas besoin de julianday() "
            "sauf pour calculer un NOMBRE de jours de retard.",
        ],
    },
]

# Expressions temporelles FR → SQL (SQLite) — le vrai vocabulaire des questions terrain
PERIODES: List[Dict] = [
    {"expr": "ce mois / ce mois-ci", "sql": "c.date_commande >= date('now', 'start of month')"},
    {"expr": "le mois dernier", "sql": "c.date_commande >= date('now', 'start of month', '-1 month') "
                                       "AND c.date_commande < date('now', 'start of month')"},
    {"expr": "cette semaine / les 7 derniers jours", "sql": "c.date_commande >= date('now', '-7 days')"},
    {"expr": "les 30 derniers jours", "sql": "c.date_commande >= date('now', '-30 days')"},
    {"expr": "aujourd'hui (stocks)", "sql": "s.date_snapshot = (SELECT MAX(date_snapshot) FROM stocks)"},
    {"expr": "semaine par semaine", "sql": "GROUP BY strftime('%Y-W%W', c.date_commande)"},
]


def render_for_prompt() -> str:
    """Rend la couche sémantique en Markdown, prête à être injectée dans le system prompt."""
    parts = ["## Métriques officielles (source de vérité — ne jamais improviser une autre formule)\n"]
    for m in METRIQUES:
        parts.append(f"### {m['nom']}")
        parts.append(f"- **Synonymes entendus** : {', '.join(m['synonymes'])}")
        parts.append(f"- **Définition** : {m['definition']}")
        parts.append(f"- **Formule SQL canonique** : `{m['sql']}`")
        parts.append(f"- **Grain de calcul** : {m['grain']}")
        for piege in m["pieges"]:
            parts.append(f"- ⚠️ {piege}")
        parts.append("")

    parts.append("## Expressions temporelles → SQL\n")
    parts.append("| Expression | Traduction SQLite |")
    parts.append("|---|---|")
    for p in PERIODES:
        parts.append(f"| {p['expr']} | `{p['sql']}` |")
    return "\n".join(parts)


def find_metric(term: str) -> Optional[Dict]:
    """Retrouve une métrique à partir d'un terme métier (pour la doc et les évals)."""
    term_low = term.lower().strip()
    for m in METRIQUES:
        if term_low == m["nom"].lower() or any(term_low == s.lower() for s in m["synonymes"]):
            return m
    return None
