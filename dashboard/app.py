"""
app.py — Interface Streamlit SupplyChainGPT
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_schema_context, run_query
from src.llm import question_to_sql, explain_result, fix_sql

st.set_page_config(
    page_title="SupplyChainGPT",
    page_icon="📦",
    layout="wide"
)

st.title("📦 SupplyChainGPT")
st.caption("Interroge ta base supply chain en français — propulsé par Claude API")

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
        if st.button(s, use_container_width=True):
            st.session_state["question"] = s

    st.divider()
    st.header("Historique")
    if "history" not in st.session_state:
        st.session_state["history"] = []
    for h in st.session_state["history"][-5:][::-1]:
        st.caption(f"• {h[:60]}…" if len(h) > 60 else f"• {h}")

question = st.text_input(
    "Pose ta question en français",
    value=st.session_state.get("question", ""),
    placeholder="Ex : Quels fournisseurs ont un taux de service < 95% ce mois ?",
    key="question"
)

if st.button("Analyser ▶", type="primary") and question:
    with st.spinner("Génération SQL en cours…"):
        schema = get_schema_context()
        sql = question_to_sql(question, schema)

    with st.expander("SQL généré", expanded=False):
        st.code(sql, language="sql")

    with st.spinner("Exécution…"):
        try:
            df = run_query(sql)
        except Exception as e:
            st.warning(f"Erreur SQL — tentative de correction automatique…\n`{e}`")
            sql = fix_sql(sql, str(e), schema)
            try:
                df = run_query(sql)
                st.success("Requête corrigée automatiquement.")
            except Exception as e2:
                st.error(f"Échec après correction : {e2}")
                st.stop()

    st.dataframe(df, use_container_width=True)

    # Auto-viz
    if len(df) > 0 and len(df.columns) >= 2:
        num_cols = df.select_dtypes("number").columns.tolist()
        str_cols = df.select_dtypes("object").columns.tolist()
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
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

    with st.spinner("Analyse…"):
        preview = df.head(5).to_string(index=False)
        explication = explain_result(question, sql, preview)
    st.info(explication)

    if question not in st.session_state["history"]:
        st.session_state["history"].append(question)
