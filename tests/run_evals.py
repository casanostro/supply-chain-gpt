"""
run_evals.py — Harnais d'évaluation du text-to-SQL.

Deux modes :
  python tests/run_evals.py --golden   # OFFLINE : vérifie que chaque SQL de référence
                                       # s'exécute sur la base (garde-fou anti-régression
                                       # du schéma et du jeu de données)
  python tests/run_evals.py            # ONLINE : appelle Claude sur chaque question et note

Notation d'un cas (mode online) :
  1. intention   — le modèle a-t-il choisi sql / clarification / hors_perimetre comme attendu ?
  2. motifs      — le SQL généré contient-il les constructions clés (regex) ?
  3. exécution   — le SQL s'exécute-t-il sans erreur ?
  4. équivalence — le RÉSULTAT est-il identique à celui du SQL de référence ?
                   (comparaison d'ensembles de lignes, insensible à l'ordre, aux noms de
                   colonnes et aux arrondis — le standard "execution accuracy" du text-to-SQL :
                   deux SQL différents qui donnent le même résultat sont tous deux corrects)

Sortie : tableau par cas + score global, code retour ≠ 0 si un cas échoue (utilisable en CI).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd  # noqa: E402
from src.db import run_query, get_schema_context  # noqa: E402

CASES_PATH = Path(__file__).parent / "test_queries.json"


def _normalise(df: pd.DataFrame) -> Set[Tuple]:
    """Résultat → ensemble de tuples comparables : ordre des lignes ignoré,
    noms de colonnes ignorés, flottants arrondis à 1 décimale."""
    rows = set()
    for row in df.itertuples(index=False):
        rows.add(tuple(
            round(v, 1) if isinstance(v, float) else v
            for v in row
        ))
    return rows


def _execution_match(sql_teste: str, sql_golden: str) -> Tuple[bool, str]:
    try:
        df_test = run_query(sql_teste)
    except Exception as e:
        return False, f"exécution KO : {e}"
    df_gold = run_query(sql_golden)
    if _normalise(df_test) == _normalise(df_gold):
        return True, f"résultats identiques ({len(df_gold)} lignes)"
    return False, (f"résultats différents : {len(df_test)} lignes vs "
                   f"{len(df_gold)} attendues")


def eval_golden() -> int:
    """Mode offline : chaque SQL de référence doit tourner sur la base."""
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    echecs = 0
    for case in cases:
        golden = case.get("sql_golden")
        if not golden:
            print(f"  ⏭  {case['id']:<24} (comportement — pas de SQL de référence)")
            continue
        try:
            df = run_query(golden)
            print(f"  ✅ {case['id']:<24} {len(df)} lignes")
        except Exception as e:
            echecs += 1
            print(f"  ❌ {case['id']:<24} {e}")
    print(f"\n{'✅ SQL de référence : tous valides' if not echecs else f'❌ {echecs} échec(s)'}")
    return echecs


def eval_online() -> int:
    """Mode online : appelle Claude et note chaque cas sur 4 critères."""
    from src.llm import question_to_analyse  # import tardif : exige ANTHROPIC_API_KEY

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    schema = get_schema_context()
    total, reussis = 0, 0
    lignes_rapport: List[str] = []

    for case in cases:
        total += 1
        analyse = question_to_analyse(case["question"], schema)
        criteres: List[str] = []
        ok = True

        # 1. intention
        attendue = case.get("intention_attendue", "sql")
        if analyse.intention == attendue:
            criteres.append("intention ✅")
        else:
            criteres.append(f"intention ❌ ({analyse.intention} ≠ {attendue})")
            ok = False

        if attendue == "sql" and analyse.intention == "sql" and analyse.sql:
            # 2. motifs
            manquants = [m for m in case.get("motifs_sql", [])
                         if not re.search(m, analyse.sql, re.IGNORECASE)]
            if manquants:
                criteres.append(f"motifs ❌ (absents : {', '.join(manquants)})")
                ok = False
            else:
                criteres.append("motifs ✅")

            # 3 + 4. exécution & équivalence
            if case.get("sql_golden"):
                match, detail = _execution_match(analyse.sql, case["sql_golden"])
                criteres.append(f"équivalence {'✅' if match else '❌'} ({detail})")
                ok = ok and match

        statut = "✅" if ok else "❌"
        reussis += ok
        lignes_rapport.append(f"  {statut} [{case.get('niveau', '?'):<12}] "
                              f"{case['id']:<24} {' | '.join(criteres)}")

    print("\n".join(lignes_rapport))
    print(f"\nScore : {reussis}/{total} ({reussis * 100 // max(total, 1)} %)")
    return total - reussis


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évaluation du text-to-SQL SupplyChainGPT")
    parser.add_argument("--golden", action="store_true",
                        help="mode offline : valide uniquement les SQL de référence")
    args = parser.parse_args()

    print("═" * 70)
    if args.golden:
        print("Mode GOLDEN (offline) — validation des SQL de référence\n")
        sys.exit(1 if eval_golden() else 0)
    print("Mode ONLINE — évaluation de Claude sur les questions du jeu de tests\n")
    sys.exit(1 if eval_online() else 0)
