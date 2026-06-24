---
name: ask
description: Pose une question en français au moteur text-to-SQL de SupplyChainGPT et affiche le SQL généré, le résultat, et l'explication. Utiliser quand l'utilisateur tape /ask "<question>" pour tester ou déboguer une question métier sans passer par l'UI Streamlit.
---

# /ask — Tester une question text-to-SQL

Exécute le pipeline complet (`src/llm.py` + `src/db.py`) pour une question donnée, en dehors de l'UI Streamlit, afin de déboguer rapidement la génération SQL.

## Étapes

1. Lire `src/db.py::get_schema_context()` pour obtenir le schéma actuel.
2. Appeler `src/llm.py::question_to_sql(question, schema_context)` avec la question fournie en argument.
3. Exécuter le SQL via `src/db.py::run_query(sql)`.
4. Si l'exécution échoue (`sqlite3.OperationalError`), appeler `fix_sql(bad_sql, error_msg, schema_context)` puis ré-essayer une seule fois.
5. Afficher dans l'ordre : la question, le SQL généré, le résultat (DataFrame, max 100 lignes), et l'explication via `explain_result(...)`.

## Notes

- Respecter les conventions du `CLAUDE.md` : READ-ONLY, `LIMIT 100`, pourcentages arrondis à 1 décimale.
- Si `ANTHROPIC_API_KEY` n'est pas définie dans l'environnement, le signaler avant d'appeler `client.messages.create`.
- Utile pour reproduire un bug signalé sur une question précise sans relancer tout Streamlit.
