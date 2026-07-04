"""
db.py — Accès SQLite en lecture seule + extraction du contexte schéma pour le prompt.

Le contexte schéma injecté dans le prompt est enrichi : chaque table est décrite avec
ses colonnes, son nombre de lignes et un échantillon de valeurs pour les colonnes
catégorielles. Un LLM qui VOIT les valeurs réelles ('livree', pas 'delivered')
hallucine beaucoup moins ses filtres WHERE.
"""

import sqlite3
from pathlib import Path
from typing import List

import pandas as pd

from src.sql_validator import validate, ensure_limit, open_readonly, dry_run

DB_PATH = Path(__file__).parent.parent / "data" / "supply_chain.db"

# Colonnes catégorielles dont on échantillonne les valeurs réelles dans le prompt
_SAMPLED_COLUMNS = {
    "commandes": ["statut"],
    "lignes_commande": ["motif_ecart"],
    "fournisseurs": ["categorie", "pays"],
    "produits": ["categorie"],
    "entrepots": ["nom"],
}


def get_schema_context() -> str:
    """Schéma annoté (colonnes + volumétrie + valeurs réelles) pour injection dans le prompt.

    Connexion read-only SANS authorizer : ce code interne de confiance a besoin de
    PRAGMA table_info, que l'authorizer refuse (à juste titre) au SQL venant du LLM.
    """
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in c.fetchall()]

        parts: List[str] = []
        for table in tables:
            c.execute(f"PRAGMA table_info({table})")
            cols = ", ".join(f"{col[1]} {col[2]}" for col in c.fetchall())
            c.execute(f"SELECT COUNT(*) FROM {table}")
            nb = c.fetchone()[0]
            parts.append(f"-- {table}({cols})  · {nb} lignes")

            for col in _SAMPLED_COLUMNS.get(table, []):
                c.execute(
                    f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 8"
                )
                values = ", ".join(repr(r[0]) for r in c.fetchall())
                parts.append(f"--   valeurs {table}.{col} : {values}")
        return "\n".join(parts)
    finally:
        conn.close()


def run_query(sql: str, limit: int = 100) -> pd.DataFrame:
    """Valide (4 couches), puis exécute une requête en lecture seule."""
    sql = validate(sql)
    sql = ensure_limit(sql, limit)
    conn = open_readonly(str(DB_PATH))
    try:
        dry_run(conn, sql)
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()
