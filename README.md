# 📦 SupplyChainGPT

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey)
![Claude API](https://img.shields.io/badge/Claude-API-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)
![Tests](https://img.shields.io/badge/tests-19%20offline%20%2B%2013%20evals-brightgreen)

**Text-to-SQL en français métier pour la supply chain retail.** Posez une question comme un
Demand Planner la poserait — « Compare les points perdus de ce mois avec le mois dernier » —
et obtenez le SQL, le résultat, le graphique et l'analyse. Propulsé par Claude, verrouillé en
lecture seule, auditable requête par requête.

---

## Démo

```
👤 "Quels sont les 10 fournisseurs avec le pire taux de service ce mois ?"

🧠 Raisonnement : TS au grain ligne de commande (SUM/SUM), filtre mois calendaire
   courant, lignes livrées uniquement, tri croissant pour avoir les pires.
📌 Hypothèse retenue : "Ce mois" = mois calendaire en cours, pas 30 jours glissants.

🤖 SQL :
    SELECT f.nom AS fournisseur,
           ROUND(SUM(lc.qte_livree)*100.0/NULLIF(SUM(lc.qte_commandee),0), 1) AS taux_service_pct,
           SUM(lc.qte_commandee - COALESCE(lc.qte_livree,0)) AS points_perdus
    FROM lignes_commande lc
    JOIN commandes c ON lc.commande_id = c.id
    JOIN fournisseurs f ON c.fournisseur_id = f.id
    WHERE c.date_commande >= date('now','start of month')
      AND lc.qte_livree IS NOT NULL
    GROUP BY f.nom ORDER BY taux_service_pct ASC LIMIT 10

📊 Bar chart (spec choisie par le modèle) + export Excel
💬 "Deux fournisseurs décrochent nettement sous l'objectif de 97 % : Brossard (87,2 %)
    et Henkel (89,1 %). L'écart est concentré, pas systémique. À traiter en revue
    fournisseur cette semaine, motifs d'écart à l'appui."
```

Et quand la question est mauvaise, l'assistant le dit :

```
👤 "C'est quoi la performance ?"
🤔 "Quelle performance voulez-vous voir : le taux de service fournisseurs,
    le taux de rupture en entrepôt, ou les retards de livraison ?"

👤 "Supprime les commandes annulées de plus de 60 jours"
🚫 "Je suis en lecture seule : je ne modifie jamais la base. Je peux en revanche
    vous LISTER ces commandes pour transmission à l'équipe data."
```

---

## Ce qui distingue ce projet

### 🧠 Des prompts conçus comme du produit — [docs/prompt-engineering.md](docs/prompt-engineering.md)
- **Sortie JSON structurée** où le raisonnement précède le SQL : le modèle décide
  (grain, période, tables) *avant* d'écrire la requête — et l'UI affiche cette trace.
- **Router d'intention** : `sql` / `clarification` / `hors_perimetre`, avec règle dure
  « confiance < 0.6 → poser une question plutôt que deviner ».
- **Hypothèses explicites** : chaque choix d'interprétation (« ce mois » = calendaire)
  est restitué à l'utilisateur, qui peut corriger en une relance.
- **Few-shots anti-pièges** : fenêtrage `LAG()`, comparaison de périodes par agrégation
  conditionnelle, fan-out de jointure, snapshots de stock — les erreurs qui produisent
  des chiffres *plausibles et faux*.
- **Couche sémantique générée** : les formules des KPIs vivent dans
  [`src/semantic_layer.py`](src/semantic_layer.py) (source de vérité unique, testée) et
  sont injectées dans le prompt au runtime. Zéro duplication prompt/doc/code.

### 🔒 Lecture seule en défense en profondeur — [`src/sql_validator.py`](src/sql_validator.py)
Quatre couches indépendantes, aucune ne fait confiance au LLM :
1. validation lexicale (une instruction, SELECT/WITH, mots-clés interdits hors littéraux) ;
2. connexion SQLite ouverte en `mode=ro` : le moteur refuse toute écriture ;
3. authorizer SQLite : chaque opération interne inspectée ;
4. dry-run `EXPLAIN` : colonnes hallucinées détectées avant tout scan.

### 📏 Des évals, pas des démos — [`tests/run_evals.py`](tests/run_evals.py)
Jeu de 13 cas stratifiés (facile → difficile → **piège** → **comportement**), notés sur
l'**équivalence d'exécution** : le résultat du SQL généré est comparé à celui d'un SQL de
référence (insensible à l'ordre, aux alias, aux arrondis). Les cas « comportement » vérifient
que le modèle *refuse* ce qu'il doit refuser. Mode `--golden` offline pour la CI.

### 🔁 Auto-réparation avec diagnostic
En cas d'erreur SQLite, un [prompt de débogage dédié](prompts/fix_prompt.md) diagnostique
(colonne hallucinée → dialecte → ambiguïté → grain) avec deux garde-fous : ne jamais retirer
un filtre pour « faire passer » la requête, et abandonner proprement après 2 tentatives.

---

## Architecture

```
Question FR ──► Claude (system prompt assemblé au runtime)
                  │        template + schéma live (valeurs réelles échantillonnées)
                  │        + couche sémantique rendue depuis semantic_layer.py
                  ▼
        JSON { intention, raisonnement, hypothèses, sql, graphique, confiance }
                  │
      ┌───────────┼──────────────┐
 clarification    │        hors_perimetre
 (1 question      ▼         (refus + alternative)
  fermée)   Validateur 4 couches
                  │
                  ▼
          SQLite (mode=ro) ──erreur──► Claude fix_prompt (max 2) ──┐
                  │ ◄──────────────────── SQL corrigé ◄────────────┘
                  ▼
   DataFrame + graphique (spec du modèle) + export Excel
                  │
                  ▼
     Claude explain_prompt : constat → signal → action
```

---

## Installation

```bash
git clone https://github.com/casanostro/supply-chain-gpt
cd supply-chain-gpt
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...   # Windows : set ANTHROPIC_API_KEY=...

python data/seed_data.py              # génère la base (25 fournisseurs, 375 produits,
                                      #   ~3 000 commandes / 52 000 lignes sur 90 jours)
streamlit run dashboard/app.py
```

### Vérifier sans clé API (offline)

```bash
python -m unittest tests.test_offline -v   # 19 tests : validateur, couche sémantique, prompt
python tests/run_evals.py --golden         # les 10 SQL de référence tournent sur la base
```

### Évaluer le text-to-SQL (online)

```bash
python tests/run_evals.py
# ✅ [facile]  ts_fournisseurs   intention ✅ | motifs ✅ | équivalence ✅ (10 lignes)
# ✅ [piege]   piege_snapshot    intention ✅ | motifs ✅ | équivalence ✅ (1 ligne)
# ✅ [comportement] refus_delete intention ✅
# Score : 13/13 (100 %)
```

---

## Schéma de la base

```sql
fournisseurs    -- 25 fournisseurs FMCG français (Danone, P&G, Red Bull…)
entrepots       -- 6 entrepôts Île-de-France avec capacité palettes
produits        -- 375 produits (EAN, code GESCOM, prix d'achat, fournisseur)
commandes       -- ~3 000 commandes / 90 j (dates prévue vs réelle, statut, colis)
lignes_commande -- ~52 000 lignes (qte commandée vs livrée, motif d'écart)
stocks          -- snapshots datés (dispo, couverture, flags rupture & SLOB)
```

KPIs couverts (formules canoniques dans [`src/semantic_layer.py`](src/semantic_layer.py)) :
**Taux de Service** (obj. ≥ 97 %), **Taux de Rupture** (obj. ≤ 3 %), **SLOB** (> 90 j de
couverture), **Points Perdus**, **Couverture**, **Taux de Retard**.

---

## Intégration Claude Code

Le repo est instrumenté pour le développement avec Claude Code :

| | |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | schéma, vocabulaire retail FR→SQL, conventions |
| [`.claude/agents/sql-expert.md`](.claude/agents/sql-expert.md) | sous-agent SQL qui teste ses requêtes avant de les livrer |
| `/ask "question"` | question métier → SQL + résultat + analyse dans le terminal |
| `/add-table "ventes magasins"` | étend le schéma partout où il vit (seed, sémantique, évals) |
| `/test-prompt` | relance les évals après modification d'un prompt |

---

## Structure

```
supply-chain-gpt/
├── prompts/
│   ├── system_prompt.md        # contrat JSON, procédure de décision, few-shots anti-pièges
│   ├── fix_prompt.md           # arbre de diagnostic pour l'auto-réparation
│   └── explain_prompt.md       # analyse constat → signal → action
├── src/
│   ├── semantic_layer.py       # source de vérité des KPIs (formules, synonymes, pièges)
│   ├── sql_validator.py        # read-only en 4 couches
│   ├── db.py                   # schéma annoté (valeurs réelles) + exécution sécurisée
│   ├── llm.py                  # client Claude : JSON structuré, préfixe {, prompt caching
│   └── pipeline.py             # orchestration + boucle de réparation + trace d'audit
├── dashboard/app.py            # Streamlit : KPIs live, graphique piloté par le modèle,
│                               #   hypothèses affichées, trace, export Excel
├── data/seed_data.py           # générateur de données retail réalistes (seed fixe)
├── tests/
│   ├── test_offline.py         # 19 tests unitaires sans API
│   ├── run_evals.py            # harnais d'éval (équivalence d'exécution)
│   └── test_queries.json       # 13 cas : facile / difficile / piège / comportement
└── docs/prompt-engineering.md  # le POURQUOI de chaque choix de prompt
```

---

## Roadmap

- [ ] Multi-turn : relances contextuelles (« et sur l'entrepôt de Vitry ? »)
- [ ] Connecteur Snowflake (adapter `db.py`, le reste du pipeline est agnostique)
- [ ] Évals continues en CI GitHub Actions (mode `--golden` déjà compatible)
- [ ] Déploiement Streamlit Cloud avec base de démo

---

## Auteur

**Adrien Tripon** — Business Analyst Supply Chain Performance
[linkedin.com/in/adrien-tripon](https://linkedin.com/in/adrien-tripon)
