"""Lecture SQLite pour le reporting et les requêtes proposées par le modèle."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from time import monotonic

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "supply_chain.db"
MAX_ROWS = 100
QUERY_SECONDS = 3
TABLES = {"fournisseurs", "entrepots", "produits", "commandes", "lignes_commande", "stocks"}
FUNCTIONS = set("""
    abs avg cast ceil coalesce count cume_dist date datetime dense_rank first_value
    floor group_concat ifnull instr julianday lag last_value lead length like lower
    ltrim max min ntile nullif percent_rank rank replace round row_number rtrim
    strftime substr substring sum time total trim typeof unixepoch upper
""".split())


@contextmanager
def read_connection():
    # mode=ro also prevents a missing database from becoming an empty file.
    with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only = ON")
        yield conn


def get_schema_context() -> str:
    with read_connection() as conn:
        schema = []
        for table in sorted(TABLES):
            columns = conn.execute(f"PRAGMA table_info({table})")
            schema.append(f"-- {table}(" + ", ".join(f"{col[1]} {col[2]}" for col in columns) + ")")
        return "\n".join(schema)


def _authorize(action, arg1, arg2, database, source):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database in ("main", None) and arg1 in TABLES:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and arg2 in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def run_query(sql: str, limit: int = MAX_ROWS) -> pd.DataFrame:
    """Execute one read-only analytical statement with bounded time and result rows."""
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError(f"La limite doit être comprise entre 1 et {MAX_ROWS}.")
    with read_connection() as conn:
        conn.set_authorizer(_authorize)
        deadline = monotonic() + QUERY_SECONDS
        conn.set_progress_handler(lambda: int(monotonic() >= deadline), 1000)
        # execute() rejects multiple statements. fetchmany caps nested or unlimited SQL too.
        try:
            cursor = conn.execute(sql)
        except sqlite3.Warning as exc:
            # Python 3.9 reports stacked statements as Warning, newer drivers as ProgrammingError.
            raise sqlite3.ProgrammingError(str(exc)) from exc
        if cursor.description is None:
            raise ValueError("Une requête de lecture est requise.")
        return pd.DataFrame.from_records(
            cursor.fetchmany(limit), columns=[column[0] for column in cursor.description]
        )
