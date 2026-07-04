---
description: Évaluer le system prompt sur le jeu de tests (mode golden ou online)
allowed-tools: Bash(python:*), Read
---

Évalue la qualité du text-to-SQL après une modification de prompt ou de couche sémantique.

1. D'abord le garde-fou offline (schéma + données + SQL de référence) :
   ```bash
   python tests/run_evals.py --golden
   ```
2. Si `ANTHROPIC_API_KEY` est défini, lance l'éval complète (Claude est noté sur
   intention, motifs SQL et équivalence d'exécution avec le SQL de référence) :
   ```bash
   python tests/run_evals.py
   ```
3. Analyse les échecs par niveau (`facile` → `piege` → `comportement`) :
   - échec sur `piege` = le prompt a perdu un garde-fou (snapshot, fan-out, NULL) →
     vérifie la section « Pièges » de `src/semantic_layer.py` et les few-shots.
   - échec sur `comportement` = la politique d'ambiguïté/refus s'est affaiblie →
     vérifie la section « Politique d'ambiguïté et de refus » du system prompt.
4. Restitue un tableau avant/après si un score précédent est connu dans la conversation.
