---
name: test-prompt
description: Exécute la suite de tests text-to-SQL de SupplyChainGPT (tests/test_queries.json) contre le pipeline llm.py + db.py et rapporte les questions dont le SQL généré ne contient pas les fragments attendus. Utiliser quand l'utilisateur tape /test-prompt pour valider que le system_prompt.md produit toujours du SQL correct après une modification du prompt ou du schéma.
---

# /test-prompt — Valider le pipeline text-to-SQL

Rejoue chaque cas de `tests/test_queries.json` contre `question_to_sql()` et vérifie que le SQL généré contient les fragments listés dans `sql_attendu_contient`.

## Étapes

1. Lire `tests/test_queries.json`.
2. Pour chaque cas :
   - Appeler `src/db.py::get_schema_context()` pour le schéma courant.
   - Appeler `src/llm.py::question_to_sql(question, schema_context)`.
   - Vérifier (insensible à la casse) que chaque chaîne de `sql_attendu_contient` apparaît dans le SQL généré.
   - Optionnel : exécuter le SQL via `run_query()` pour vérifier qu'il s'exécute sans erreur SQLite.
3. Rapporter un tableau : id du cas, pass/fail, fragments manquants, SQL généré.
4. Si un cas échoue, ne pas modifier `sql_attendu_contient` pour le faire passer — investiguer si `prompts/system_prompt.md` ou le vocabulaire FR → SQL du `CLAUDE.md` doit être ajusté.

## Quand l'utiliser

- Après toute modification de `prompts/system_prompt.md`.
- Après un `/add-table` (schéma changé → risque de régression sur les questions existantes).
- Avant un déploiement ou une démo client.
