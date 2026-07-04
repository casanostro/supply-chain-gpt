---
description: Poser une question métier en français et obtenir SQL + résultat + analyse
argument-hint: "Top 5 ruptures par entrepôt"
allowed-tools: Bash(python:*), Read
---

Question métier de l'utilisateur : **$ARGUMENTS**

1. Déroule la procédure de décision de `prompts/system_prompt.md` (périmètre → grain →
   période → fan-out → NULL) en t'appuyant sur les formules canoniques de
   `src/semantic_layer.py`.
2. Écris la requête SQLite (SELECT/WITH uniquement, alias en français métier).
3. Exécute-la via le pipeline sécurisé :
   ```bash
   python -c "import sys; sys.path.insert(0,'.'); from src.db import run_query; print(run_query('''<SQL>''').to_string(index=False))"
   ```
4. Restitue : le SQL, le résultat, puis une analyse en 3 phrases max au format
   **constat → signal → action** (voir `prompts/explain_prompt.md`).
5. Si la question est ambiguë, pose UNE question fermée avant de générer quoi que ce soit.
