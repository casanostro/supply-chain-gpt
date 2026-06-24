# Bibliothèque de skills

Ce document recense tous les skills disponibles dans les sessions Claude Code de ce projet : les skills globaux (fournis par l'environnement Claude Code, hors dépôt) et les skills projet (créés dans `.claude/skills/`, versionnés avec le code).

## Skills projet (`.claude/skills/`)

Créés pour ce dépôt, référencés dans `CLAUDE.md` :

| Commande | Fichier | Usage |
|---|---|---|
| `/ask "<question>"` | `.claude/skills/ask/SKILL.md` | Teste une question FR → SQL en dehors de l'UI Streamlit |
| `/add-table "<nom>"` | `.claude/skills/add-table/SKILL.md` | Ajoute une table au schéma BDD et propage le contexte au LLM |
| `/test-prompt` | `.claude/skills/test-prompt/SKILL.md` | Rejoue `tests/test_queries.json` contre le pipeline text-to-SQL |

## Skills globaux (environnement Claude Code, hors dépôt)

Disponibles dans toute session sur cette machine, indépendamment du projet :

| Skill | Usage |
|---|---|
| `session-start-hook` | Créer des hooks `SessionStart` pour Claude Code on the web (installer deps, lancer tests/linters au démarrage) |
| `update-config` | Configurer `settings.json` (permissions, hooks, env vars) |
| `keybindings-help` | Personnaliser les raccourcis clavier (`~/.claude/keybindings.json`) |
| `verify` | Lancer l'app et observer le comportement réel pour vérifier qu'un changement fonctionne |
| `code-review` | Revue du diff courant (bugs, simplification, efficacité), avec options `--comment` / `--fix` |
| `simplify` | Nettoyage qualité du code modifié (réutilisation, simplification, efficacité) sans chercher de bugs |
| `fewer-permission-prompts` | Scanner les transcripts pour allowlister les commandes Bash/MCP fréquentes |
| `loop` | Exécuter un prompt/slash command à intervalle régulier (ex. `/loop 5m /test-prompt`) |
| `claude-api` | Référence API Claude / SDK Anthropic (modèles, pricing, tool use, caching...) |
| `run` | Lancer et piloter l'app pour voir un changement fonctionner (CLI, serveur, navigateur...) |
| `init` | Initialiser un `CLAUDE.md` avec la documentation du codebase |
| `review` | Revue d'une pull request GitHub |
| `security-review` | Revue de sécurité des changements en attente sur la branche courante |

Ces skills globaux ne sont pas stockés dans ce dépôt — ils vivent dans la configuration Claude Code de l'environnement (`~/.claude/skills`). Ils restent disponibles ici à titre de référence pour savoir lesquels invoquer pendant le développement de SupplyChainGPT.

## Ajouter un nouveau skill projet

1. Créer `.claude/skills/<nom>/SKILL.md` avec un frontmatter `name` + `description`.
2. Documenter les étapes précises (fichiers à lire/modifier, conventions du `CLAUDE.md` à respecter).
3. Ajouter une ligne dans le tableau "Skills projet" ci-dessus.
