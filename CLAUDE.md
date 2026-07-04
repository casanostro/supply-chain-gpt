# SupplyChainGPT — Text-to-SQL pour la Supply Chain Retail

## Projet
App Streamlit qui transforme des questions en français ("Quels fournisseurs ont le plus de ruptures ce mois ?") en requêtes SQL, exécute sur une BDD SQLite supply chain, et affiche résultat + SQL + visualisation auto.

## Stack
- Python 3.9 (contrainte poste Windows)
- SQLite (BDD locale, portable, démontrable)
- Anthropic Claude API (claude-sonnet-4-20250514) pour le text-to-SQL
- Streamlit pour l'interface
- Pandas + Plotly pour la data viz
- openpyxl pour les exports Excel

## Schéma BDD (6 tables)

```sql
-- Référentiels
fournisseurs(id, code, nom, pays, categorie, contact_email)
entrepots(id, code, nom, ville, region, capacite_palettes)
produits(id, ean, code_gescom, libelle, categorie, sous_categorie,
         fournisseur_id, poids_kg, prix_achat_ht, unite_commande)

-- Transactionnel
commandes(id, numero, fournisseur_id, entrepot_id, date_commande,
          date_livraison_prevue, date_livraison_reelle, statut,
          nb_lignes, nb_colis_commandes, nb_colis_livres)

lignes_commande(id, commande_id, produit_id, qte_commandee,
                qte_livree, motif_ecart, prix_unitaire_ht)

stocks(id, produit_id, entrepot_id, date_snapshot, stock_physique,
       stock_disponible, couverture_jours, flag_rupture, flag_slob)
```

## KPIs supply chain clés
- **Taux de Service (TS)** = qte_livree / qte_commandee * 100  (objectif ≥ 97%)
- **Taux de Rupture** = nb produits flag_rupture / nb produits total * 100  (objectif ≤ 3%)
- **Couverture stock** = stock_physique / (sorties_12m / 365)  (SLOB si > 90 jours)
- **Points perdus** = qte_commandee - qte_livree (en colis ou en CA)

## Vocabulaire retail FR → SQL
| Terme métier | Champ SQL |
|---|---|
| taux de service | SUM(qte_livree) / SUM(qte_commandee) * 100 |
| rupture | flag_rupture = 1 OR stock_disponible = 0 |
| entrepôt / dépôt | entrepots.nom |
| fournisseur | fournisseurs.nom |
| SLOB / stock dormant | flag_slob = 1 OR couverture_jours > 90 |
| colis commandés | nb_colis_commandes |
| écart livraison | qte_commandee - qte_livree |
| retard | date_livraison_reelle > date_livraison_prevue |

## Patterns SQL fréquents

```sql
-- Taux de service par fournisseur
SELECT f.nom, ROUND(SUM(lc.qte_livree)*100.0/SUM(lc.qte_commandee), 1) AS ts_pct
FROM lignes_commande lc
JOIN commandes c ON lc.commande_id = c.id
JOIN fournisseurs f ON c.fournisseur_id = f.id
WHERE c.date_commande >= date('now', '-30 days')
GROUP BY f.nom ORDER BY ts_pct ASC;

-- Stock à risque SLOB
SELECT p.libelle, e.nom AS entrepot,
       s.stock_physique, s.couverture_jours
FROM stocks s
JOIN produits p ON s.produit_id = p.id
JOIN entrepots e ON s.entrepot_id = e.id
WHERE s.flag_slob = 1 AND s.date_snapshot = (SELECT MAX(date_snapshot) FROM stocks)
ORDER BY s.couverture_jours DESC;
```

## Conventions
- Toujours READ-ONLY : validation 4 couches dans `src/sql_validator.py` (lexicale, mode=ro,
  authorizer, dry-run EXPLAIN) — ne jamais l'affaiblir
- Les formules de KPI vivent UNIQUEMENT dans `src/semantic_layer.py` : le system prompt est
  assemblé au runtime par `build_system_prompt()` — ne pas dupliquer une formule dans
  `prompts/system_prompt.md`
- Limiter les résultats à 100 lignes par défaut (LIMIT 100)
- Arrondir les pourcentages à 1 décimale, NULLIF sur tout dénominateur
- Dates en ISO 8601 (YYYY-MM-DD)
- En cas d'erreur SQL → boucle d'auto-correction (`prompts/fix_prompt.md`), 2 tentatives max
- Alias SQL en français métier (`taux_service_pct`, pas `svc_rate`)

## Pièges connus de cette base (à vérifier dans toute requête)
- `stocks` est une table de snapshots multi-dates : toute question au présent exige
  `date_snapshot = (SELECT MAX(date_snapshot) FROM stocks)`
- Fan-out : ne jamais agréger un champ d'entête de `commandes` (nb_colis_*) après une
  jointure sur `lignes_commande`
- `qte_livree IS NULL` = commande en cours, à exclure des taux de service et points perdus

## Vérification après toute modification
```bash
python -m unittest tests.test_offline      # 19 tests sans API
python tests/run_evals.py --golden         # SQL de référence vs base
python tests/run_evals.py                  # évals complètes (exige ANTHROPIC_API_KEY)
```

## Commandes Claude Code
```bash
claude                          # Ouvre le projet avec CLAUDE.md en contexte
/ask "Top 5 ruptures par entrepôt"     # question métier → SQL testé + analyse
/add-table "ventes magasins"           # étend seed + couche sémantique + évals
/test-prompt                           # relance les évals après retouche de prompt
```
