"""
seed_data.py — Génère la BDD SQLite supply chain avec données fictives réalistes
Usage : python data/seed_data.py
"""

import argparse
from contextlib import closing
import sqlite3
import random
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

DB_PATH = Path(__file__).parent / "supply_chain.db"

FOURNISSEURS = [
    ("F001", "Coca-Cola France", "France", "Boissons"),
    ("F002", "Danone", "France", "Produits frais"),
    ("F003", "Nestlé France", "France", "Epicerie"),
    ("F004", "Unilever France", "France", "DPH"),
    ("F005", "P&G France", "France", "DPH"),
    ("F006", "Red Bull France", "Autriche", "Boissons"),
    ("F007", "Brossard", "France", "Epicerie"),
    ("F008", "Bonduelle", "France", "Conserves"),
    ("F009", "Fleury Michon", "France", "Charcuterie"),
    ("F010", "Bel", "France", "Produits frais"),
    ("F011", "Herta", "France", "Charcuterie"),
    ("F012", "Heineken France", "Pays-Bas", "Boissons"),
    ("F013", "Mars France", "USA", "Confiserie"),
    ("F014", "Ferrero France", "Italie", "Confiserie"),
    ("F015", "Mondelez France", "USA", "Biscuits"),
    ("F016", "Panzani", "France", "Epicerie"),
    ("F017", "Lustucru", "France", "Epicerie"),
    ("F018", "Président", "France", "Produits frais"),
    ("F019", "Yoplait", "France", "Produits frais"),
    ("F020", "Schweppes", "UK", "Boissons"),
    ("F021", "Henkel France", "Allemagne", "DPH"),
    ("F022", "Colgate-Palmolive", "USA", "DPH"),
    ("F023", "Lavazza", "Italie", "Café"),
    ("F024", "Jacobs Douwe Egberts", "Pays-Bas", "Café"),
    ("F025", "William Saurin", "France", "Conserves"),
]

ENTREPOTS = [
    ("E001", "Vitry", "Vitry-sur-Seine", "Île-de-France", 8000),
    ("E002", "Wissous", "Wissous", "Île-de-France", 6000),
    ("E003", "Combs", "Combs-la-Ville", "Île-de-France", 7500),
    ("E004", "Gennevilliers", "Gennevilliers", "Île-de-France", 5000),
    ("E005", "Torcy", "Torcy", "Île-de-France", 4500),
    ("E006", "Nanterre", "Nanterre", "Île-de-France", 3000),
]

PRODUITS_TEMPLATES = [
    ("Coca-Cola 50cl", "Boissons", "Soda", 0.5, 0.42),
    ("Coca-Cola 1.5L", "Boissons", "Soda", 1.5, 0.85),
    ("Eau minérale 1.5L", "Boissons", "Eau", 1.5, 0.22),
    ("Yaourt nature 4x125g", "Produits frais", "Yaourt", 0.5, 0.85),
    ("Emmental râpé 200g", "Produits frais", "Fromage", 0.2, 1.45),
    ("Jambon blanc 4 tranches", "Charcuterie", "Jambon", 0.14, 1.95),
    ("Pâtes 500g", "Epicerie", "Pâtes", 0.5, 0.65),
    ("Riz 1kg", "Epicerie", "Riz", 1.0, 0.89),
    ("Biscuits LU 200g", "Biscuits", "Biscuits", 0.2, 1.25),
    ("Café moulu 250g", "Café", "Café", 0.25, 2.85),
    ("Liquide vaisselle 500ml", "DPH", "Entretien", 0.5, 1.15),
    ("Shampoing 300ml", "DPH", "Hygiène", 0.3, 2.35),
    ("Tomates pelées 400g", "Conserves", "Conserves", 0.4, 0.75),
    ("Red Bull 25cl", "Boissons", "Energy", 0.25, 0.98),
    ("Chocolat noir 200g", "Confiserie", "Chocolat", 0.2, 1.55),
]


def create_schema(conn):
    c = conn.cursor()
    c.executescript("""
    DROP TABLE IF EXISTS stocks;
    DROP TABLE IF EXISTS lignes_commande;
    DROP TABLE IF EXISTS commandes;
    DROP TABLE IF EXISTS produits;
    DROP TABLE IF EXISTS entrepots;
    DROP TABLE IF EXISTS fournisseurs;

    CREATE TABLE fournisseurs (
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        nom TEXT NOT NULL,
        pays TEXT,
        categorie TEXT,
        contact_email TEXT
    );

    CREATE TABLE entrepots (
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        nom TEXT NOT NULL,
        ville TEXT,
        region TEXT,
        capacite_palettes INTEGER
    );

    CREATE TABLE produits (
        id INTEGER PRIMARY KEY,
        ean TEXT UNIQUE NOT NULL,
        code_gescom TEXT UNIQUE NOT NULL,
        libelle TEXT NOT NULL,
        categorie TEXT,
        sous_categorie TEXT,
        fournisseur_id INTEGER REFERENCES fournisseurs(id),
        poids_kg REAL,
        prix_achat_ht REAL,
        unite_commande INTEGER DEFAULT 6
    );

    CREATE TABLE commandes (
        id INTEGER PRIMARY KEY,
        numero TEXT UNIQUE NOT NULL,
        fournisseur_id INTEGER REFERENCES fournisseurs(id),
        entrepot_id INTEGER REFERENCES entrepots(id),
        date_commande TEXT NOT NULL,
        date_livraison_prevue TEXT,
        date_livraison_reelle TEXT,
        statut TEXT CHECK(statut IN ('en_cours','livree','partielle','annulee')),
        nb_lignes INTEGER,
        nb_colis_commandes INTEGER,
        nb_colis_livres INTEGER
    );

    CREATE TABLE lignes_commande (
        id INTEGER PRIMARY KEY,
        commande_id INTEGER REFERENCES commandes(id),
        produit_id INTEGER REFERENCES produits(id),
        qte_commandee INTEGER NOT NULL,
        qte_livree INTEGER,
        motif_ecart TEXT,
        prix_unitaire_ht REAL
    );

    CREATE TABLE stocks (
        id INTEGER PRIMARY KEY,
        produit_id INTEGER REFERENCES produits(id),
        entrepot_id INTEGER REFERENCES entrepots(id),
        date_snapshot TEXT NOT NULL,
        stock_physique INTEGER,
        stock_disponible INTEGER,
        couverture_jours REAL,
        flag_rupture INTEGER DEFAULT 0,
        flag_slob INTEGER DEFAULT 0
    );
    """)
    conn.commit()


def seed(conn, as_of=None):
    today = as_of or date.today()
    rng = random.Random(42)
    c = conn.cursor()

    # Fournisseurs
    for i, (code, nom, pays, cat) in enumerate(FOURNISSEURS, 1):
        c.execute(
            "INSERT INTO fournisseurs VALUES (?,?,?,?,?,?)",
            (i, code, nom, pays, cat, f"contact@{nom.lower().replace(' ', '')}.fr")
        )

    # Entrepôts
    for i, (code, nom, ville, region, cap) in enumerate(ENTREPOTS, 1):
        c.execute("INSERT INTO entrepots VALUES (?,?,?,?,?,?)",
                  (i, code, nom, ville, region, cap))

    # Produits (~375 = 15 templates × 25 fournisseurs)
    prod_id = 1
    for frn_id, (_, nom_frn, _, cat_frn) in enumerate(FOURNISSEURS, 1):
        templates = [row for row in PRODUITS_TEMPLATES if row[1] == cat_frn]
        for variant in range(1, 16):
            libelle, cat, sous_cat, poids, prix = rng.choice(templates)
            ean = f"340{prod_id:010d}"
            code_g = f"{prod_id:05d}"
            c.execute("INSERT INTO produits VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (prod_id, ean, code_g, f"{libelle} - {nom_frn} - réf. {variant:02d}",
                       cat, sous_cat, frn_id, poids, prix, 6))
            prod_id += 1

    nb_produits = prod_id - 1

    # Commandes (90 jours)
    cmd_id = 1
    lc_id = 1
    motifs = ["rupture_fournisseur", "transport", "qualite", "annulation_partielle", None, None, None]

    for day_offset in range(90, 0, -1):
        date_cmd = today - timedelta(days=day_offset)
        for entrepot_id in range(1, 7):
            nb_commandes_jour = rng.randint(3, 8)
            for _ in range(nb_commandes_jour):
                frn_id = rng.randint(1, 25)
                # 15 références par fournisseur, livrées par cartons de 6 unités.
                produits = rng.sample(range((frn_id - 1) * 15 + 1, frn_id * 15 + 1),
                                      k=rng.randint(5, 15))
                frn_ts_base = {6: 0.88, 7: 0.87, 21: 0.89}.get(frn_id, rng.uniform(0.94, 0.99))
                transit = rng.choices([2, 3, 4, 5, 7], weights=[30, 35, 20, 10, 5])[0]
                retard = rng.choices([0, 1, 2], weights=[70, 20, 10])[0]
                prevue = date_cmd + timedelta(days=transit)
                reelle = prevue + timedelta(days=retard)
                recue = reelle <= today
                lignes = []
                nb_colis_cmd = 0
                nb_colis_livres = 0
                for produit in produits:
                    colis = rng.randint(1, 20)
                    nb_colis_cmd += colis
                    livres = sum(rng.random() < frn_ts_base for _ in range(colis)) if recue else 0
                    nb_colis_livres += livres
                    motif = rng.choice(motifs) if recue and livres < colis else None
                    lignes.append((lc_id, cmd_id, produit, colis * 6, livres * 6 if recue else None,
                                   motif, round(rng.uniform(0.3, 5.0), 2)))
                    lc_id += 1

                statut = "en_cours"
                if recue:
                    statut = "livree" if nb_colis_livres == nb_colis_cmd else "partielle"
                c.execute("INSERT INTO commandes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (cmd_id, f"CMD{cmd_id:06d}", frn_id, entrepot_id, date_cmd.isoformat(),
                           prevue.isoformat(), reelle.isoformat() if recue else None, statut,
                           len(lignes), nb_colis_cmd, nb_colis_livres if recue else None))
                c.executemany("INSERT INTO lignes_commande VALUES (?,?,?,?,?,?,?)", lignes)
                cmd_id += 1

    # Stocks (snapshots J, J-7 et J-30)
    stock_id = 1
    for snap_offset in [0, 7, 30]:
        date_snap = (today - timedelta(days=snap_offset)).strftime("%Y-%m-%d")
        for prod_id_s in range(1, nb_produits + 1):
            for entrepot_id in range(1, 7):
                if rng.random() < 0.7:
                    stock_phys = rng.randint(0, 500)
                    stock_dispo = max(0, stock_phys - rng.randint(0, 20))
                    couverture = round(rng.uniform(0, 120), 1) if stock_phys > 0 else 0
                    flag_rupt = 1 if stock_dispo == 0 else 0
                    flag_slob = 1 if couverture > 90 else 0
                    c.execute("INSERT INTO stocks VALUES (?,?,?,?,?,?,?,?,?)",
                              (stock_id, prod_id_s, entrepot_id, date_snap,
                               stock_phys, stock_dispo, couverture, flag_rupt, flag_slob))
                    stock_id += 1

    conn.commit()
    return cmd_id - 1, lc_id - 1, stock_id - 1, nb_produits


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Génère la base SQLite de démonstration.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(), metavar="YYYY-MM-DD",
                        help="Date de référence des données fictives (par défaut : aujourd’hui).")
    args = parser.parse_args()
    print(f"Génération de la BDD : {DB_PATH}")
    with TemporaryDirectory(dir=DB_PATH.parent) as tmp:
        generated = Path(tmp) / DB_PATH.name
        with closing(sqlite3.connect(generated)) as conn:
            create_schema(conn)
            nb_cmd, nb_lc, nb_stocks, nb_prod = seed(conn, args.as_of)
        generated.replace(DB_PATH)
    print(f"✓ {len(FOURNISSEURS)} fournisseurs")
    print(f"✓ {len(ENTREPOTS)} entrepôts")
    print(f"✓ {nb_prod} produits")
    print(f"✓ {nb_cmd} commandes · {nb_lc} lignes")
    print(f"✓ {nb_stocks} snapshots stocks")
    print(f"BDD prête : {DB_PATH}")
