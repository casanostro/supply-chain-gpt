"""
sql_validator.py — Validation READ-ONLY en défense en profondeur.

Quatre couches indépendantes ; il faudrait les contourner TOUTES pour écrire en base :
  1. Validation lexicale : une seule instruction, SELECT/WITH uniquement, mots-clés interdits.
  2. Connexion SQLite ouverte en mode=ro (URI) : le moteur lui-même refuse toute écriture.
  3. Authorizer SQLite : chaque opération interne est inspectée, seules les lectures passent.
  4. Dry-run EXPLAIN : la syntaxe est vérifiée sans exécuter la requête réelle.

Aucune de ces couches ne fait confiance au LLM — ni à l'utilisateur.
"""

import re
import sqlite3
from typing import Optional

# Mots-clés qui n'ont AUCUNE raison d'apparaître dans une requête analytique.
# Détection sur mot entier (\b) : "updated_at" ou "created" ne déclenchent pas de faux positif.
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE"
    r"|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

_LIMIT_RE = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)


class SQLValidationError(ValueError):
    """Requête rejetée par le validateur (jamais exécutée)."""


def _strip_literals_and_comments(sql: str) -> str:
    """Neutralise chaînes et commentaires pour que la détection de mots-clés
    ne se déclenche pas sur un libellé produit ('DROP shampoing')."""
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)          # littéraux SQL
    sql = re.sub(r"--[^\n]*", "", sql)                   # commentaires ligne
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)  # commentaires bloc
    return sql


def validate(sql: str) -> str:
    """Couche 1 — validation lexicale. Retourne le SQL nettoyé ou lève SQLValidationError."""
    if not sql or not sql.strip():
        raise SQLValidationError("Requête vide.")

    cleaned = sql.strip().rstrip(";").strip()
    stripped = _strip_literals_and_comments(cleaned)

    if ";" in stripped:
        raise SQLValidationError("Une seule instruction SQL est autorisée (point-virgule interne détecté).")

    first_word = stripped.split(None, 1)[0].upper() if stripped.split() else ""
    if first_word not in ("SELECT", "WITH"):
        raise SQLValidationError(f"Seules les requêtes SELECT/WITH sont autorisées (reçu : {first_word}).")

    match = _FORBIDDEN.search(stripped)
    if match:
        raise SQLValidationError(f"Mot-clé interdit détecté : {match.group(0).upper()}.")

    return cleaned


def ensure_limit(sql: str, limit: int = 100) -> str:
    """Ajoute LIMIT si la requête n'en a pas déjà un (protection UI, pas sécurité)."""
    if _LIMIT_RE.search(sql):
        return sql
    return f"{sql} LIMIT {limit}"


def _authorizer(action: int, arg1: Optional[str], arg2: Optional[str],
                db_name: Optional[str], trigger: Optional[str]) -> int:
    """Couche 3 — authorizer SQLite : n'autorise que les opérations de lecture."""
    _ALLOWED = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        getattr(sqlite3, "SQLITE_FUNCTION", 31),
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),  # CTE récursives
    }
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


def open_readonly(db_path: str) -> sqlite3.Connection:
    """Couches 2 + 3 — connexion en lecture seule avec authorizer armé."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.set_authorizer(_authorizer)
    return conn


def dry_run(conn: sqlite3.Connection, sql: str) -> None:
    """Couche 4 — EXPLAIN compile la requête sans l'exécuter : les colonnes hallucinées
    et les erreurs de syntaxe sont détectées ici, avant tout scan de données."""
    try:
        conn.execute(f"EXPLAIN {sql}")
    except sqlite3.Error as e:
        raise SQLValidationError(f"Requête invalide : {e}") from e
