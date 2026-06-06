"""
llm.py — Appels Claude API pour le text-to-SQL et l'explication des résultats
"""

import os
import anthropic
from pathlib import Path

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def question_to_sql(question: str, schema_context: str) -> str:
    """Transforme une question en français en requête SQL."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Schéma disponible :\n{schema_context}\n\nQuestion : {question}\n\nRéponds UNIQUEMENT avec la requête SQL, sans explication ni markdown."
        }]
    )
    sql = response.content[0].text.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def explain_result(question: str, sql: str, result_preview: str) -> str:
    """Génère une explication en langage naturel du résultat."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                f"Question posée : {question}\n"
                f"SQL exécuté : {sql}\n"
                f"Résultat (extrait) :\n{result_preview}\n\n"
                "Explique ce résultat en 2-3 phrases, en français, de façon concise et orientée action supply chain."
            )
        }]
    )
    return response.content[0].text.strip()


def fix_sql(bad_sql: str, error_msg: str, schema_context: str) -> str:
    """Corrige une requête SQL en erreur."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Schéma :\n{schema_context}\n\n"
                f"Cette requête SQL a échoué :\n{bad_sql}\n\n"
                f"Erreur : {error_msg}\n\n"
                "Corrige la requête. Réponds UNIQUEMENT avec le SQL corrigé."
            )
        }]
    )
    sql = response.content[0].text.strip()
    return sql.replace("```sql", "").replace("```", "").strip()
