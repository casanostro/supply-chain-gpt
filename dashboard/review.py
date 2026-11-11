"""Présentation de la revue de service, sans appel à un fournisseur d'IA."""

import streamlit as st

from src.service_review import (
    SERVICE_SQL, recovery_scenario, review_dates, service_review, warehouse_options,
)


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def render():
    st.title("Revue de service fournisseurs")
    dates = review_dates()
    if dates is None:
        st.info("Aucune réception clôturée disponible.")
        return
    first, last = dates
    warehouses = warehouse_options()
    with st.sidebar:
        st.subheader("Périmètre")
        end = st.date_input("Fin de période", value=last, min_value=first, max_value=last)
        days = st.selectbox("Fenêtre d’analyse", [7, 28, 90], format_func=lambda n: f"{n} jours")
        warehouse = st.selectbox("Entrepôt", [None, *warehouses],
                                 format_func=lambda i: warehouses.get(i, "Tous les entrepôts"))
    suppliers, detail, params = service_review(end, days, warehouse)
    st.caption(f"{params['debut']} au {params['fin']} · {warehouses.get(warehouse, 'Tous les entrepôts')} "
               "· Réceptions clôturées · Données fictives")
    if suppliers.empty:
        st.info("Aucune quantité réceptionnée exploitable sur ce périmètre.")
        return

    ordered = int(suppliers["commande"].sum())
    served = int(suppliers["servi"].sum())
    rate = 100 * served / ordered
    c1, c2, c3 = st.columns(3)
    c1.metric("Taux de service pondéré", number(rate, 2) + " %")
    c2.metric("Unités manquantes", number(ordered - served))
    c3.metric("Unités commandées", number(ordered))

    total_gap = ordered - served
    if total_gap:
        lead = suppliers.iloc[0]
        share = 100 * lead.manquant / total_gap
        st.info(f"**{lead.nom}** concentre **{number(lead.manquant)} unités manquantes**, "
                f"soit {number(share, 1)} % du manquant et {number(lead.perte_points, 2)} point de service sur ce périmètre.")

    ranking, investigation = st.columns([3, 2])
    with ranking:
        st.subheader("Priorité de relance")
        labels = {"fournisseur": "Code", "nom": "Fournisseur", "commande": "Commandé (u)",
                  "servi": "Servi (u)", "manquant": "Manquant (u)", "service_pct": "Service (%)",
                  "perte_points": "Perte (pts)"}
        table = suppliers.rename(columns=labels)
        st.dataframe(table[["Fournisseur", "Manquant (u)", "Service (%)", "Perte (pts)"]].round(2),
                     hide_index=True, width="stretch", height=350)
        st.download_button(
            "Exporter le classement (CSV)",
            table.to_csv(index=False, sep=";", decimal=",", float_format="%.4f").encode("utf-8-sig"),
            file_name=f"service_{params['debut']}_{params['fin']}_{warehouse or 'reseau'}.csv",
            mime="text/csv",
        )

    with investigation:
        st.subheader("Détail fournisseur")
        names = suppliers.set_index("fournisseur")["nom"].to_dict()
        supplier = st.selectbox("Examiner un fournisseur", list(names), format_func=names.get)
        gaps = detail.loc[(detail["fournisseur"] == supplier) & (detail["manquant"] > 0),
                          ["motif", "manquant"]].sort_values("manquant", ascending=False)
        if gaps.empty:
            st.success("Toutes les unités éligibles de ce fournisseur ont été servies.")
        else:
            st.dataframe(gaps.rename(columns={"motif": "Motif enregistré", "manquant": "Manquant (u)"}),
                         hide_index=True, width="stretch")
            pct = st.slider("Part du manquant fournisseur récupérée (%)", 0, 100, 50, 5)
            units, simulated = recovery_scenario(ordered, served, int(gaps["manquant"].sum()), pct)
            st.metric("Service simulé du périmètre", number(simulated, 2) + " %",
                      delta=f"+{number(simulated - rate, 2)} pt")
            st.caption(f"Hypothèse de {number(units)} unités récupérées à volume commandé constant.")

    with st.expander("Vérifier la définition et le SQL"):
        st.write("Période inclusive sur la date réelle de réception. Statuts livrée et partielle. "
                 "Chaque ligne doit avoir une commande positive et une quantité livrée connue et positive ou nulle. "
                 "La quantité servie est plafonnée au commandé sur chaque ligne. "
                 "Service = 100 × servi / commandé. Perte en points = 100 × manquant fournisseur / commandé du périmètre.")
        st.json(params)
        st.code(SERVICE_SQL, language="sql")
