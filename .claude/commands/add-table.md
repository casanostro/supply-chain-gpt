---
description: Ajouter une nouvelle table au schéma (seed + couche sémantique + évals)
argument-hint: "ventes magasins"
allowed-tools: Read, Edit, Write, Bash(python:*)
---

L'utilisateur veut ajouter au schéma : **$ARGUMENTS**

Une table n'existe pas tant qu'elle n'est pas dans les QUATRE endroits suivants — traite-les dans l'ordre :

1. **`data/seed_data.py`** — CREATE TABLE + génération de données réalistes pour le retail
   français (volumes cohérents avec l'existant, clés étrangères valides, `random.seed(42)` respecté).
2. **`src/semantic_layer.py`** — si la table introduit de nouveaux KPIs, ajoute-les à
   `METRIQUES` avec synonymes métier ET pièges connus. Le system prompt les récupérera
   automatiquement : ne modifie PAS `prompts/system_prompt.md` à la main pour ça.
3. **`CLAUDE.md`** — mets à jour la section « Schéma BDD ».
4. **`tests/test_queries.json`** — ajoute au moins 2 cas d'éval : un facile et un piège
   spécifique à cette table, chacun avec son `sql_golden`.

Termine par la vérification complète :
```bash
python data/seed_data.py && python -m unittest tests.test_offline && python tests/run_evals.py --golden
```
