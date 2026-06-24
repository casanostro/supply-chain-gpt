---
name: add-table
description: Ajoute une nouvelle table au schéma SupplyChainGPT (seed_data.py, db.py, CLAUDE.md, system_prompt.md). Utiliser quand l'utilisateur tape /add-table "<nom de table>" pour étendre la BDD supply chain avec une nouvelle entité métier (ex. "ventes magasins", "retours fournisseurs").
---

# /add-table — Étendre le schéma BDD

Ajoute une table au schéma SQLite et propage son contexte au LLM, en respectant les conventions du projet (READ-ONLY, FR → SQL, dates ISO).

## Étapes

1. Clarifier avec l'utilisateur les colonnes de la nouvelle table si elles ne sont pas explicites (clé primaire `id`, FK vers les tables référentielles existantes — `fournisseurs`, `entrepots`, `produits` — quand pertinent).
2. Ajouter la définition `CREATE TABLE` et les données de test dans `data/seed_data.py`.
3. Vérifier que `src/db.py::get_schema_context()` n'a pas besoin de modification (il lit `sqlite_master` dynamiquement — normalement aucun changement requis).
4. Mettre à jour `CLAUDE.md` :
   - Ajouter la table dans la section "Schéma BDD".
   - Ajouter au "Vocabulaire retail FR → SQL" si la table introduit de nouveaux termes métier.
5. Mettre à jour `prompts/system_prompt.md` si le prompt système référence explicitement la liste des tables.
6. Régénérer la BDD locale (`python data/seed_data.py`) et tester une question `/ask` qui utilise la nouvelle table.
7. Ajouter un ou deux cas dans `tests/test_queries.json` couvrant la nouvelle table.

## Contraintes à respecter

- Aucune table ne doit permettre d'écriture depuis l'app (le moteur reste SELECT/WITH only, voir `src/db.py::run_query`).
- Garder les noms de colonnes en français/snake_case cohérents avec le schéma existant (`date_*`, `qte_*`, `flag_*`).
