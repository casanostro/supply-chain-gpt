"""Revue fournisseur sur les réceptions clôturées. Les volumes sont en unités."""

from datetime import date, timedelta

import pandas as pd

from src.db import read_connection


SERVICE_SQL = """
SELECT f.code AS fournisseur, f.nom AS nom,
       CASE WHEN l.qte_livree < l.qte_commandee
            THEN COALESCE(NULLIF(TRIM(l.motif_ecart), ''), 'Non renseigné')
       END AS motif,
       SUM(l.qte_commandee) AS commande,
       SUM(MIN(l.qte_livree, l.qte_commandee)) AS servi
FROM lignes_commande AS l
JOIN commandes AS c ON c.id = l.commande_id
JOIN fournisseurs AS f ON f.id = c.fournisseur_id
WHERE c.statut IN ('livree', 'partielle')
  AND c.date_livraison_reelle BETWEEN :debut AND :fin
  AND (:entrepot IS NULL OR c.entrepot_id = :entrepot)
  AND l.qte_commandee > 0 AND l.qte_livree >= 0
GROUP BY f.code, f.nom, motif
ORDER BY f.code, motif
"""


def warehouse_options():
    with read_connection() as conn:
        return dict(conn.execute("SELECT id, nom FROM entrepots ORDER BY nom"))


def review_dates():
    with read_connection() as conn:
        first, last = conn.execute("""
            SELECT MIN(date_livraison_reelle), MAX(date_livraison_reelle)
            FROM commandes
            WHERE statut IN ('livree', 'partielle') AND date_livraison_reelle <= ?
        """, (date.today().isoformat(),)).fetchone()
        if last is None:
            return None
        return date.fromisoformat(first), date.fromisoformat(last)


def service_review(end: date, days: int, warehouse=None):
    if days < 1:
        raise ValueError("La période doit couvrir au moins un jour.")
    start = end - timedelta(days=days - 1)
    params = {"debut": start.isoformat(), "fin": end.isoformat(), "entrepot": warehouse}
    with read_connection() as conn:
        detail = pd.read_sql_query(SERVICE_SQL, conn, params=params)
    detail["manquant"] = detail["commande"] - detail["servi"]
    suppliers = detail.groupby(["fournisseur", "nom"], as_index=False)[
        ["commande", "servi", "manquant"]
    ].sum()
    suppliers["service_pct"] = 100 * suppliers["servi"] / suppliers["commande"]
    suppliers["perte_points"] = 100 * suppliers["manquant"] / suppliers["commande"].sum()
    suppliers = suppliers.sort_values(["manquant", "fournisseur"], ascending=[False, True])
    return suppliers.reset_index(drop=True), detail, params


def recovery_scenario(ordered: int, served: int, supplier_shortfall: int, recovery_pct: int):
    """Apply a recovery assumption to one supplier; keep ordered volume constant."""
    if ordered <= 0 or not 0 <= supplier_shortfall <= ordered - served or served < 0:
        raise ValueError("Volumes de simulation incohérents.")
    if not 0 <= recovery_pct <= 100:
        raise ValueError("Le taux de récupération doit être compris entre 0 et 100.")
    recovered = supplier_shortfall * recovery_pct // 100
    return recovered, 100 * (served + recovered) / ordered
