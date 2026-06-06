# 📦 SupplyChainGPT

![Python](https://img.shields.io/badge/Python-3.9-blue)
![SQLite](https://img.shields.io/badge/SQLite-3-lightgrey)
![Claude API](https://img.shields.io/badge/Claude-API-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)

Text-to-SQL assistant for French retail supply chain analysis. Ask questions in French, get SQL + results + visualization — powered by Anthropic Claude API.

---

## Demo

```
👤 "Quels sont les 10 fournisseurs avec le pire taux de service ce mois ?"

🤖 SQL généré :
    SELECT f.nom AS Fournisseur,
           ROUND(SUM(lc.qte_livree)*100.0/SUM(lc.qte_commandee), 1) AS ts_pct
    FROM lignes_commande lc
    JOIN commandes c ON lc.commande_id = c.id
    JOIN fournisseurs f ON c.fournisseur_id = f.id
    WHERE c.date_commande >= date('now', 'start of month')
    GROUP BY f.nom ORDER BY ts_pct ASC LIMIT 10

📊 Bar chart + résultat tabulaire
💬 "Brossard et Henkel affichent les taux de service les plus bas (<90%),
    principalement liés à des problèmes de transport."
```

---

## Features

- Natural language → SQL via Claude API (claude-sonnet)
- French retail supply chain vocabulary (taux de service, rupture, SLOB, points perdus...)
- Auto-correction loop: if SQL fails, Claude fixes it automatically
- Auto-visualization: bar chart generated from result shape
- Natural language explanation of results
- READ-ONLY safety: no INSERT/UPDATE/DELETE ever executed
- 10-query regression test suite
- Realistic seed data: 25 French suppliers, 6 warehouses, ~500 products, 90 days of orders

---

## Architecture

```
Question FR
    │
    ▼
Claude API (text-to-SQL)
    │
    ▼
SQL Validator (READ-ONLY check)
    │
    ▼
SQLite (supply_chain.db)
    │
    ├─► DataFrame + Plotly chart
    │
    └─► Claude API (natural language explanation)
```

---

## Stack

| Component | Tech |
|---|---|
| Database | SQLite (6-table star schema) |
| LLM | Claude API — claude-sonnet |
| Interface | Streamlit |
| Data viz | Plotly + Pandas |
| Language | Python 3.9 |

---

## Installation

```bash
git clone https://github.com/casanostro/supply-chain-gpt
cd supply-chain-gpt

# Install dependencies (Windows + proxy)
pip install -r requirements.txt --user \
  --trusted-host pypi.org \
  --trusted-host files.pythonhosted.org \
  --trusted-host pypi.python.org

# Set your API key
set ANTHROPIC_API_KEY=your_key_here   # Windows
export ANTHROPIC_API_KEY=your_key_here  # Linux/Mac

# Generate the database
python data/seed_data.py

# Launch
streamlit run dashboard/app.py
```

---

## Database Schema

```sql
fournisseurs   -- 25 French suppliers (Coca-Cola, Danone, P&G, Red Bull...)
entrepots      -- 6 Île-de-France warehouses
produits       -- ~500 products (EAN, GESCOM code, category, supplier)
commandes      -- 90 days of orders with delivery status
lignes_commande -- Order lines with qte_commandee / qte_livree
stocks         -- Daily snapshots with flag_rupture, flag_slob, couverture_jours
```

---

## Example queries

```
"Quels fournisseurs ont un taux de service < 95% ce mois ?"
"Quel entrepôt a le plus de produits en rupture aujourd'hui ?"
"Montre-moi les produits SLOB avec leur valeur de stock"
"Combien de commandes en retard cette semaine ?"
"Top 5 des catégories avec le plus de points perdus"
"Évolution du taux de service semaine par semaine sur 4 semaines"
```

---

## Project structure

```
supply-chain-gpt/
├── CLAUDE.md                      # Claude Code context (schema, patterns, conventions)
├── .claude/
│   ├── agents/sql-expert.md       # Specialized text-to-SQL subagent
│   └── commands/                  # /ask, /add-table, /test-prompt
├── data/
│   ├── seed_data.py               # Realistic data generator
│   └── supply_chain.db            # Generated SQLite database
├── src/
│   ├── db.py                      # Safe SQLite connection + schema extraction
│   └── llm.py                     # Claude API calls (SQL gen, explain, fix)
├── prompts/
│   └── system_prompt.md           # Text-to-SQL system prompt with few-shots
├── dashboard/
│   └── app.py                     # Streamlit interface
├── tests/
│   └── test_queries.json          # 10-query regression suite
└── requirements.txt
```

---

## Roadmap

- [ ] Streamlit Cloud deployment
- [ ] Snowflake connector (production-grade adapter for real DWH)
- [ ] Voice input (whisper → question → SQL)
- [ ] Export results to Excel with one click
- [ ] Multi-turn conversation (maintain context across questions)

---

## Author

Adrien Tripon — Business Analyst Supply Chain Performance  
[linkedin.com/in/adrien-tripon](https://linkedin.com/in/adrien-tripon)
