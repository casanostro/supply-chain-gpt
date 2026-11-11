"""
app.py — Interface Streamlit SupplyChainGPT
"""

import streamlit as st
import os
import sqlite3
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import DB_PATH, get_schema_context, run_query
from dashboard.review import render as render_review

st.set_page_config(
    page_title="SupplyChainGPT",
    page_icon="📦",
    layout="wide"
)

st.sidebar.title("SupplyChainGPT")
mode = st.sidebar.radio("Espace de travail", ["Revue fournisseurs", "Questions en français"])
if not DB_PATH.is_file():
    st.info("Génère la base de démonstration avant d’ouvrir l’application.")
    st.code("python data/seed_data.py", language="bash")
    st.stop()

if mode == "Revue fournisseurs":
    render_review()
    st.stop()

st.title("Questions en français")
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.info("Configure ANTHROPIC_API_KEY pour poser une question libre. La revue fournisseurs fonctionne sans clé.")
    st.stop()

from anthropic import APIError
from src.llm import question_to_sql, explain_result, fix_sql
st.caption("Claude reçoit la question, le schéma, le SQL et un extrait de cinq lignes maximum pour commenter les résultats.")

SUGGESTIONS = [
    "Quels sont les 10 fournisseurs avec le pire taux de service ce mois ?",
    "Quel entrepôt a le plus de produits en rupture aujourd'hui ?",
    "Montre-moi les produits SLOB avec leur valeur de stock",
    "Combien de commandes en retard cette semaine ?",
    "Top 5 des catégories avec le plus de points perdus",
]

with st.sidebar:
    st.header("Requêtes suggérées")
    for s in SUGGESTIONS:
        if st.button(s, width="stretch"):
            st.session_state["question"] = s

    st.divider()
    st.header("Historique")
    if "history" not in st.session_state:
        st.session_state["history"] = []
    for h in st.session_state["history"][-5:][::-1]:
        st.caption(f"• {h[:60]}…" if len(h) > 60 else f"• {h}")

question = st.text_input(
    "Pose ta question en français",
    placeholder="Ex : Quels fournisseurs ont un taux de service < 95% ce mois ?",
    key="question"
)

if st.button("Analyser ▶", type="primary") and question:
    with st.spinner("Génération SQL en cours…"):
        schema = get_schema_context()
        try:
            sql = question_to_sql(question, schema)
        except APIError:
            st.error("Claude est indisponible. Vérifie la configuration du modèle et de la clé, puis réessaie.")
            st.stop()

    with st.spinner("Exécution…"):
        try:
            df = run_query(sql)
        except (sqlite3.Error, ValueError) as e:
            st.warning(f"Erreur SQL — tentative de correction automatique…\n`{e}`")
            try:
                sql = fix_sql(sql, str(e), schema)
                df = run_query(sql)
                st.success("Requête corrigée automatiquement.")
            except APIError:
                st.error("Le service de correction est indisponible.")
                st.stop()
            except (sqlite3.Error, ValueError) as e2:
                st.error(f"Échec après correction : {e2}")
                st.stop()

    with st.expander("SQL exécuté"):
        st.code(sql, language="sql")
    st.dataframe(df, width="stretch")
    if len(df) == 100:
        st.caption("Affichage limité à 100 lignes.")

    # Auto-viz
    if len(df) > 0 and len(df.columns) >= 2:
        num_cols = df.select_dtypes("number").columns.tolist()
        str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
        if num_cols and str_cols:
            try:
                fig = px.bar(
                    df.head(20),
                    x=str_cols[0],
                    y=num_cols[0],
                    title=question[:80],
                    color_discrete_sequence=["#E31837"]
                )
                fig.update_layout(xaxis_tickangle=-35)
                st.plotly_chart(fig)
            except Exception:
                pass

    with st.spinner("Analyse…"):
        preview = df.head(5).to_string(index=False)
        try:
            st.info(explain_result(question, sql, preview))
        except APIError:
            st.warning("Le commentaire est indisponible. Les résultats SQL figurent ci-dessus.")

    if question not in st.session_state["history"]:
        st.session_state["history"].append(question)
