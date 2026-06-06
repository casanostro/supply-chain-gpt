"""
db.py — Connexion SQLite et exécution sécurisée (READ-ONLY)
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "supply_chain.db"


def get_schema_context() -> str:
    """Retourne le schéma complet de la BDD pour injection dans le prompt."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]

    schema_parts = []
    for table in tables:
        c.execute(f"PRAGMA table_info({table})")
        cols = c.fetchall()
        col_defs = ", ".join(f"{col[1]} {col[2]}" for col in cols)
        schema_parts.append(f"-- {table}({col_defs})")

    conn.close()
    return "\n".join(schema_parts)


def run_query(sql: str, limit: int = 100) -> pd.DataFrame:
    """Exécute une requête SELECT et retourne un DataFrame. Lève une exception si non-SELECT."""
    sql_clean = sql.strip().upper()
    if not sql_clean.startswith("SELECT") and not sql_clean.startswith("WITH"):
        raise ValueError("Seules les requêtes SELECT/WITH sont autorisées.")

    # Injecter LIMIT si absent
    if "LIMIT" not in sql_clean:
        sql = sql.rstrip(";") + f" LIMIT {limit}"

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df
