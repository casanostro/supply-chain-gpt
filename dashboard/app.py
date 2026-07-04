"""
app.py — Interface Streamlit SupplyChainGPT

Principes UI :
- Bandeau KPI temps réel (SQL direct, sans LLM) : l'app est utile avant la première question.
- Chaque réponse est AUDITABLE : SQL, raisonnement du modèle, hypothèses retenues,
  tentatives de correction et durée sont visibles dans un panneau de trace.
- Le graphique est choisi par le modèle (type/x/y dans sa réponse JSON), pas deviné par l'UI.
- Export Excel en un clic sur chaque résultat.
"""

import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import run_query
from src.pipeline import poser_question

st.set_page_config(page_title="SupplyChainGPT", page_icon="📦", layout="wide")

ACCENT = "#E31837"

st.title("📦 SupplyChainGPT")
st.caption("Interroge ta base supply chain en français — text-to-SQL propulsé par Claude, "
           "validé en lecture seule, traçable de bout en bout.")


# ---------------------------------------------------------------- Bandeau KPI
@st.cache_data(ttl=300)
def kpis_du_jour():
    ts = run_query(
        "SELECT ROUND(SUM(qte_livree)*100.0/NULLIF(SUM(qte_commandee),0),1) AS ts "
        "FROM lignes_commande lc JOIN commandes c ON lc.commande_id = c.id "
        "WHERE c.date_commande >= date('now','-30 days') AND lc.qte_livree IS NOT NULL"
    ).iloc[0, 0]
    ruptures = run_query(
        "SELECT ROUND(SUM(flag_rupture)*100.0/NULLIF(COUNT(*),0),1) AS tx FROM stocks "
        "WHERE date_snapshot = (SELECT MAX(date_snapshot) FROM stocks)"
    ).iloc[0, 0]
    slob = run_query(
        "SELECT ROUND(SUM(s.stock_physique*p.prix_achat_ht),0) AS v FROM stocks s "
        "JOIN produits p ON s.produit_id = p.id WHERE s.flag_slob = 1 "
        "AND s.date_snapshot = (SELECT MAX(date_snapshot) FROM stocks)"
    ).iloc[0, 0]
    retards = run_query(
        "SELECT COUNT(*) FROM commandes WHERE date_livraison_reelle > date_livraison_prevue "
        "AND date_commande >= date('now','-7 days')"
    ).iloc[0, 0]
    return ts, ruptures, slob, retards


try:
    ts, ruptures, slob, retards = kpis_du_jour()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Taux de service 30j", f"{ts} %", delta=f"{round(ts - 97, 1)} pt vs objectif 97 %")
    c2.metric("Taux de rupture", f"{ruptures} %", delta=f"{round(ruptures - 3, 1)} pt vs objectif 3 %",
              delta_color="inverse")
    c3.metric("Valeur SLOB", f"{slob:,.0f} €".replace(",", " "))
    c4.metric("Retards 7j", int(retards))
except Exception:
    st.warning("Base absente — lance `python data/seed_data.py` pour la générer.")

st.divider()

# ---------------------------------------------------------------- Sidebar
SUGGESTIONS = [
    "Quels sont les 10 fournisseurs avec le pire taux de service ce mois ?",
    "Évolution du taux de service semaine par semaine sur 8 semaines, avec la variation",
    "Compare les points perdus de ce mois avec le mois dernier, par fournisseur",
    "Quel entrepôt a le plus de produits en rupture aujourd'hui ?",
    "Montre-moi la valeur du stock SLOB par catégorie",
    "Répartition des motifs d'écart sur les 30 derniers jours",
    "Quels entrepôts saturent ?",
]

with st.sidebar:
    st.header("💡 Questions à essayer")
    for s in SUGGESTIONS:
        if st.button(s, use_container_width=True):
            st.session_state["question_choisie"] = s

    st.divider()
    st.header("🕘 Historique")
    for h in st.session_state.get("history", [])[-8:][::-1]:
        if st.button(f"↩ {h[:55]}…" if len(h) > 55 else f"↩ {h}",
                     key=f"hist_{hash(h)}", use_container_width=True):
            st.session_state["question_choisie"] = h

# ---------------------------------------------------------------- Question
question = st.text_input(
    "Pose ta question en français",
    value=st.session_state.pop("question_choisie", ""),
    placeholder="Ex : Compare les points perdus de ce mois avec le mois dernier",
)

if st.button("Analyser ▶", type="primary") and question:
    with st.spinner("Analyse de la question, génération et validation du SQL…"):
        reponse = poser_question(question)

    analyse = reponse.analyse

    # --- Issues sans SQL : clarification ou hors périmètre
    if reponse.statut == "clarification":
        st.info(f"🤔 **Précision nécessaire** — {reponse.message}")
        st.stop()
    if reponse.statut == "hors_perimetre":
        st.warning(f"🚫 **Hors périmètre** — {reponse.message}")
        st.stop()
    if reponse.statut == "echec":
        st.error("Échec après auto-corrections. Détail des tentatives ci-dessous.")
        for i, t in enumerate(reponse.tentatives, 1):
            st.code(t.sql, language="sql")
            st.caption(f"Tentative {i} — {t.erreur}")
        st.stop()

    # --- Résultat
    df = reponse.df
    st.dataframe(df, use_container_width=True)

    # Graphique piloté par la spec du modèle
    spec = analyse.graphique or {}
    if spec.get("type") not in (None, "none") and len(df) > 0:
        x, y = spec.get("x"), spec.get("y")
        if x in df.columns and y in df.columns:
            builders = {"bar": px.bar, "line": px.line, "scatter": px.scatter, "pie": px.pie}
            builder = builders.get(spec["type"], px.bar)
            if spec["type"] == "pie":
                fig = builder(df.head(20), names=x, values=y, title=spec.get("titre") or "")
            else:
                fig = builder(df.head(50), x=x, y=y, title=spec.get("titre") or "",
                              color_discrete_sequence=[ACCENT])
                fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

    # Analyse en langage naturel
    if reponse.explication:
        st.info(f"💬 {reponse.explication}")

    # Hypothèses retenues par le modèle : l'utilisateur peut corriger le tir
    if analyse.hypotheses:
        st.caption("**Hypothèses retenues** — " + " · ".join(analyse.hypotheses))

    # --- Trace d'audit
    with st.expander(f"🔍 Trace d'exécution — {reponse.duree_s}s, "
                     f"{len(reponse.tentatives)} tentative(s), confiance {analyse.confiance:.0%}"):
        st.markdown(f"**Raisonnement du modèle** : {analyse.raisonnement}")
        for i, t in enumerate(reponse.tentatives, 1):
            st.code(t.sql, language="sql")
            if t.erreur:
                st.caption(f"❌ Tentative {i} : {t.erreur} → auto-correction envoyée à Claude")
            else:
                st.caption(f"✅ Tentative {i} : exécutée ({len(df)} lignes)")

    # --- Export Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Résultat")
        pd.DataFrame({"question": [question], "sql": [reponse.sql_final]}).to_excel(
            writer, index=False, sheet_name="Requête")
    st.download_button("⬇ Exporter en Excel", buffer.getvalue(),
                       file_name="supplychaingpt_resultat.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Historique
    st.session_state.setdefault("history", [])
    if question not in st.session_state["history"]:
        st.session_state["history"].append(question)
