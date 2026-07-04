"""
pipeline.py — Orchestration : question FR → analyse → validation → exécution → réparation.

C'est le seul module que l'UI appelle. Il encapsule :
- la boucle d'auto-correction (2 tentatives max, puis échec honnête plutôt qu'obstination)
- la validation 4 couches AVANT toute exécution
- la trace d'exécution complète (tentatives, timings, hypothèses) que l'UI affiche
  pour que l'utilisateur puisse auditer chaque réponse.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from src.db import get_schema_context, run_query
from src.llm import AnalyseLLM, question_to_analyse, fix_sql, explain_result

MAX_TENTATIVES_FIX = 2


@dataclass
class Tentative:
    sql: str
    erreur: Optional[str] = None


@dataclass
class ReponsePipeline:
    """Tout ce que l'UI a besoin d'afficher — y compris ce qui a raté."""
    statut: str                              # "ok" | "clarification" | "hors_perimetre" | "echec"
    question: str = ""
    analyse: Optional[AnalyseLLM] = None
    df: Optional[pd.DataFrame] = None
    sql_final: Optional[str] = None
    explication: Optional[str] = None
    tentatives: List[Tentative] = field(default_factory=list)
    duree_s: float = 0.0

    @property
    def message(self) -> Optional[str]:
        return self.analyse.message if self.analyse else None


def _stats_resultat(df: pd.DataFrame) -> str:
    """Statistiques compactes du résultat, fournies au prompt d'explication."""
    lignes = [f"{len(df)} lignes"]
    for col in df.select_dtypes("number").columns:
        lignes.append(f"{col}: min={df[col].min()}, max={df[col].max()}")
    return " | ".join(lignes)


def poser_question(question: str, avec_explication: bool = True) -> ReponsePipeline:
    """Point d'entrée unique du pipeline."""
    debut = time.time()
    reponse = ReponsePipeline(statut="echec", question=question)

    schema = get_schema_context()
    analyse = question_to_analyse(question, schema)
    reponse.analyse = analyse

    if analyse.intention in ("clarification", "hors_perimetre"):
        reponse.statut = analyse.intention
        reponse.duree_s = round(time.time() - debut, 2)
        return reponse

    # Boucle exécution / réparation
    sql = analyse.sql or ""
    for tentative in range(1, MAX_TENTATIVES_FIX + 2):
        try:
            df = run_query(sql)
            reponse.tentatives.append(Tentative(sql=sql))
            reponse.df = df
            reponse.sql_final = sql
            reponse.statut = "ok"
            break
        except Exception as e:  # SQLValidationError comprise
            reponse.tentatives.append(Tentative(sql=sql, erreur=str(e)))
            if tentative > MAX_TENTATIVES_FIX:
                break
            correction = fix_sql(question, sql, str(e), schema, tentative)
            if correction.intention != "sql" or not correction.sql:
                reponse.analyse = correction   # le modèle a préféré demander une clarification
                reponse.statut = correction.intention
                break
            # on garde la spec graphique la plus récente
            analyse.graphique = correction.graphique or analyse.graphique
            sql = correction.sql

    if reponse.statut == "ok" and avec_explication and reponse.df is not None and len(reponse.df) > 0:
        preview = reponse.df.head(10).to_string(index=False)
        reponse.explication = explain_result(
            question, reponse.sql_final, preview, _stats_resultat(reponse.df)
        )

    reponse.duree_s = round(time.time() - debut, 2)
    return reponse
