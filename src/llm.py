"""
llm.py — Client Claude API : text-to-SQL structuré, auto-correction, analyse.

Choix de conception :
- Le modèle répond en JSON STRUCTURÉ (intention, raisonnement, hypothèses, sql, graphique,
  confiance) : le raisonnement précède le SQL dans le schéma de sortie, ce qui force le
  modèle à décider avant d'écrire — et donne à l'UI de quoi afficher la traçabilité.
- Le system prompt est assemblé au runtime : template + schéma live de la base + couche
  sémantique rendue depuis src/semantic_layer.py. Une seule source de vérité par KPI.
- Prompt caching (cache_control ephemeral) sur le system prompt : le bloc statique
  (~3 000 tokens) n'est facturé pleinement qu'une fois toutes les 5 minutes.
- Le pré-remplissage de la réponse assistant par "{" verrouille la sortie JSON sans
  avoir besoin d'un mode JSON dédié.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional

import anthropic

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MODEL = os.environ.get("SUPPLYCHAINGPT_MODEL", "claude-sonnet-4-20250514")

_client_instance: Optional[anthropic.Anthropic] = None


def _client() -> anthropic.Anthropic:
    """Client paresseux : le module s'importe (tests, docs) sans ANTHROPIC_API_KEY."""
    global _client_instance
    if _client_instance is None:
        _client_instance = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY dans l'environnement
    return _client_instance


@dataclass
class AnalyseLLM:
    """Réponse structurée du modèle — le contrat défini dans prompts/system_prompt.md."""
    intention: str                      # "sql" | "clarification" | "hors_perimetre"
    raisonnement: str = ""
    hypotheses: List[str] = field(default_factory=list)
    sql: Optional[str] = None
    graphique: dict = field(default_factory=dict)
    confiance: float = 0.0
    message: Optional[str] = None
    brut: str = ""                      # réponse brute, pour la trace de débogage


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_system_prompt(schema_context: str) -> str:
    """Assemble le system prompt : template + schéma live + couche sémantique."""
    from src.semantic_layer import render_for_prompt
    template = _load_prompt("system_prompt.md")
    return (
        template
        .replace("<<DATE_DU_JOUR>>", date.today().isoformat())
        .replace("<<SCHEMA>>", schema_context)
        .replace("<<COUCHE_SEMANTIQUE>>", render_for_prompt())
    )


def _parse_json_response(text: str) -> AnalyseLLM:
    """Parse la réponse JSON, avec repêchage si le modèle a bavardé autour."""
    candidate = text.strip()
    if not candidate.startswith("{"):
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            raise ValueError(f"Réponse non-JSON du modèle : {text[:200]}")
        candidate = match.group(0)
    data = json.loads(candidate)
    return AnalyseLLM(
        intention=data.get("intention", "sql"),
        raisonnement=data.get("raisonnement", ""),
        hypotheses=data.get("hypotheses") or [],
        sql=data.get("sql"),
        graphique=data.get("graphique") or {},
        confiance=float(data.get("confiance", 0.0)),
        message=data.get("message"),
        brut=text,
    )


def _call(system_prompt: str, user_content: str, max_tokens: int = 1500) -> AnalyseLLM:
    """Appel structuré : system prompt caché + réponse pré-remplie par '{'."""
    response = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": "{"},   # verrouille la sortie JSON
        ],
    )
    return _parse_json_response("{" + response.content[0].text)


def question_to_analyse(question: str, schema_context: str) -> AnalyseLLM:
    """Question FR → analyse structurée (intention + SQL + spec graphique)."""
    return _call(build_system_prompt(schema_context), f"Question : {question}")


def fix_sql(question: str, bad_sql: str, error_msg: str,
            schema_context: str, tentative: int) -> AnalyseLLM:
    """Boucle d'auto-correction : même contrat de sortie, prompt de débogage dédié."""
    system_prompt = build_system_prompt(schema_context) + "\n\n---\n\n" + _load_prompt("fix_prompt.md")
    user_content = (
        f"Question d'origine : {question}\n\n"
        f"Requête en échec (tentative n°{tentative}) :\n{bad_sql}\n\n"
        f"Erreur SQLite exacte :\n{error_msg}"
    )
    return _call(system_prompt, user_content)


def explain_result(question: str, sql: str, result_preview: str, result_stats: str) -> str:
    """Commentaire d'analyste (constat → signal → action), voir prompts/explain_prompt.md."""
    response = _client().messages.create(
        model=MODEL,
        max_tokens=500,
        system=_load_prompt("explain_prompt.md"),
        messages=[{
            "role": "user",
            "content": (
                f"Question posée : {question}\n"
                f"SQL exécuté : {sql}\n"
                f"Extrait du résultat :\n{result_preview}\n"
                f"Statistiques : {result_stats}"
            ),
        }],
    )
    return response.content[0].text.strip()
