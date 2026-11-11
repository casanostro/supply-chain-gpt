# SupplyChainGPT

**Quel fournisseur appeler en premier lundi matin ?** SupplyChainGPT classe les fournisseurs selon leur contribution à la perte de service d’un entrepôt ou du réseau. L’approvisionneur peut consulter les motifs enregistrés et simuler l’effet d’une récupération partielle. Cette revue fonctionne localement, sans clé API.

Un second espace permet d’explorer les commandes, les ruptures et le stock dormant en posant des questions en français. Claude propose du SQL, SQLite l’exécute et l’interface affiche la requête utilisée.

## Rejouer la démo

Depuis la racine du projet, dans un environnement Python dédié :

```bash
python -m pip install -r requirements.txt
python data/seed_data.py --as-of 2026-11-09
python -m streamlit run dashboard/app.py
```

Ouvrir **Revue fournisseurs**, conserver **7 jours** et **Tous les entrepôts**. Le générateur remplace la base de démonstration locale. Omettre `--as-of` pour générer des réceptions autour de la date du jour.

### Un cas que l’on peut vérifier

Sur le jeu synthétique de référence, du 3 au 9 novembre 2026 inclus, le réseau a commandé **144 372 unités** et en a reçu **137 580** éligibles au calcul. Le service pondéré atteint **95,30 %**. Tous les chiffres associés aux fournisseurs sont fictifs.

| Fournisseur de démonstration | Service | Unités manquantes | Contribution à la perte réseau |
| --- | ---: | ---: | ---: |
| F006 | 87,20 % | 1 116 | 0,77 pt |
| F021 | 87,43 % | 720 | 0,50 pt |
| F002 | 95,44 % | 360 | 0,25 pt |
| F007 | 87,92 % | 282 | 0,20 pt |

F002 passe devant F007 dans la file de relance malgré un meilleur taux de service. Ouvrir F006. Pour 420 des 1 116 unités manquantes, le motif reste inconnu. Le transport en explique 150 d’après les motifs saisis. Placer le curseur à 50 % modélise la récupération de 558 unités et porte le service du réseau à **95,68 %**, à volume commandé constant. Le classement complet s’exporte en CSV.

### Périmètre métier

- La date de référence est la **date réelle de réception**. Les statuts livrée et partielle sont inclus. Les commandes encore ouvertes relèvent d’une analyse des retards.
- Chaque ligne éligible porte une quantité commandée positive et une quantité livrée connue, positive ou nulle. Le servi est plafonné au commandé par ligne pour éviter qu’une surlivraison compense le manque sur une autre référence.
- Le service pondéré est le rapport entre les totaux servis et commandés. La perte en points d’un fournisseur vaut `100 × unités manquantes du fournisseur / unités commandées du périmètre`. Les pertes s’additionnent jusqu’au complément du taux de service à 100 %.
- Le scénario conserve les volumes commandés et arrondit les unités récupérées à l’entier inférieur. La définition, le SQL paramétré et les bornes du calcul sont visibles à l’écran.

## Questions en français

Définir `ANTHROPIC_API_KEY` dans l’environnement avant de lancer l’application. `ANTHROPIC_MODEL` permet de choisir le modèle disponible sur le compte (par défaut `claude-sonnet-4-6`). Sous PowerShell, utiliser `$env:ANTHROPIC_API_KEY = "..."`. Les dates relatives du chat sont évaluées à la date du jour.

La question et le schéma sont transmis à l’API Anthropic. Pour le commentaire, elle reçoit aussi le SQL et les cinq premières lignes du résultat. En cas d’erreur SQL, le modèle dispose d’une tentative de correction. L’écran expose la dernière requête exécutée. La revue fournisseurs utilise exclusivement le calcul SQL local.

## Architecture et vérification

| Composant | Rôle |
| --- | --- |
| `data/seed_data.py` | Base de démonstration avec 25 fournisseurs, 6 entrepôts, 375 références, 90 jours de commandes et 3 dates de stock |
| `src/service_review.py` | Agrégation des lignes de réception, contribution réseau, motifs et simulation |
| `src/db.py` | Ouverture SQLite en lecture seule, contrôle des opérations, tables et fonctions autorisées pour le SQL généré, plafond de 100 lignes et interruption des calculs longs |
| `src/llm.py`, `prompts/system_prompt.md` | Génération, correction et commentaire des requêtes libres |
| `dashboard/` | Application Streamlit, filtres, export et inspection du SQL |
| `tests/test_service.py` | Données de référence calculées à la main, contrôles SQLite, cohérence du générateur et parcours Streamlit hors ligne |
| `tests/test_queries.json` | Corpus de dix questions pour les futures évaluations du modèle |

```bash
python -m unittest discover -s tests -v
```

Les tests du parcours conversationnel simulent les réponses API. La justesse du modèle sur des questions libres reste à mesurer séparément.

## Vers un pilote entreprise

Commencer avec un approvisionneur, un entrepôt et un export de réceptions pseudonymisé. Réconcilier les volumes et le taux avec le reporting de référence, puis chronométrer la préparation de la revue sur les mêmes semaines avec les deux méthodes. Suivre aussi les relances réellement décidées à partir du classement.

L’intégration à un DWH, l’authentification d’entreprise, les droits par entrepôt et la journalisation des accès restent à construire avant un usage partagé avec des données client.

**Adrien Tripon** · Supply Chain & AI · [LinkedIn](https://linkedin.com/in/adrien-tripon)
