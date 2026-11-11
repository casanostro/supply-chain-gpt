import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from data.seed_data import create_schema, seed
from src import db
from src.service_review import recovery_scenario, review_dates, service_review


END = date(2024, 1, 10)


class ExampleDatabase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "case with spaces.db"
        override = patch.object(db, "DB_PATH", path)
        override.start()
        self.addCleanup(override.stop)
        with closing(sqlite3.connect(path)) as conn:
            create_schema(conn)
            conn.executemany("INSERT INTO fournisseurs(id, code, nom) VALUES (?,?,?)",
                             [(1, "A", "Alpha"), (2, "B", "Beta")])
            conn.executemany("INSERT INTO entrepots(id, code, nom) VALUES (?,?,?)",
                             [(1, "N", "Nord"), (2, "S", "Sud")])
            # A has the better service rate but contributes the larger shortfall.
            rows = [
                (1, 1, "2024-01-04", "partielle", 100, 80, "transport"),
                (1, 1, "2024-01-10", "partielle", 20, 15, None),
                (1, 1, "2024-01-10", "livree", 5, 10, None),
                (2, 2, "2024-01-09", "partielle", 10, 0, ""),
                (2, 2, "2024-01-03", "partielle", 300, 1, "hors période"),
                (1, 1, "2024-01-10", "annulee", 900, 0, None),
                (1, 1, None, "en_cours", 500, None, None),
                (1, 1, "2024-01-10", "partielle", 400, None, None),
                (1, 1, "2024-01-10", "partielle", 0, 0, None),
                (1, 1, "2024-01-10", "partielle", 50, -1, None),
            ]
            for order, (supplier, site, received, status, qty, served, cause) in enumerate(rows, 1):
                conn.execute("""INSERT INTO commandes(id, numero, fournisseur_id, entrepot_id,
                             date_commande, date_livraison_reelle, statut)
                             VALUES (?, ?, ?, ?, '2023-12-01', ?, ?)""",
                             (order, str(order), supplier, site, received, status))
                conn.execute("""INSERT INTO lignes_commande(commande_id, qte_commandee,
                             qte_livree, motif_ecart) VALUES(?,?,?,?)""", (order, qty, served, cause))
            conn.commit()


class ServiceTests(ExampleDatabase):
    def test_reference_volumes_priority_and_points(self):
        ranked, details, params = service_review(END, 7)
        self.assertEqual(list(ranked.fournisseur), ["A", "B"])
        self.assertEqual(list(ranked.commande), [125, 10])
        self.assertEqual(list(ranked.servi), [100, 0])
        self.assertEqual(list(ranked.service_pct), [80, 0])
        self.assertAlmostEqual(ranked.iloc[0].perte_points, 25 * 100 / 135)
        self.assertAlmostEqual(ranked.perte_points.sum(), 35 * 100 / 135)
        self.assertEqual(details.loc[details.motif == "Non renseigné", "manquant"].sum(), 15)
        self.assertEqual(params, {"debut": "2024-01-04", "fin": "2024-01-10", "entrepot": None})

    def test_warehouse_changes_the_denominator(self):
        ranked, _, _ = service_review(END, 7, 2)
        self.assertEqual(list(ranked.fournisseur), ["B"])
        self.assertEqual(ranked.iloc[0].perte_points, 100)

    def test_empty_window_and_reference_date(self):
        self.assertTrue(service_review(date(2023, 12, 31), 7)[0].empty)
        self.assertEqual(review_dates(), (date(2024, 1, 3), END))

    def test_scenario_uses_whole_units_and_network_volume(self):
        for pct, expected in [(0, 0), (50, 12), (100, 25)]:
            units, rate = recovery_scenario(135, 100, 25, pct)
            self.assertEqual(units, expected)
            self.assertAlmostEqual(rate, 100 * (100 + expected) / 135)
        with self.assertRaises(ValueError):
            recovery_scenario(0, 0, 0, 50)


class QueryTests(ExampleDatabase):
    def test_valid_joins_aggregates_and_ctes(self):
        df = db.run_query("""WITH t AS (SELECT f.code, COUNT(*) AS n FROM fournisseurs f
                          JOIN commandes c ON f.id=c.fournisseur_id GROUP BY f.code)
                          SELECT code FROM t ORDER BY n DESC LIMIT 1""")
        self.assertEqual(df.iloc[0, 0], "A")

    def test_block_writes_and_unapproved_resources(self):
        for statement in ["WITH t AS (SELECT 1) DELETE FROM fournisseurs RETURNING id",
                          "ATTACH DATABASE ':memory:' AS other", "PRAGMA user_version=1",
                          "SELECT load_extension('absent')", "SELECT sql FROM sqlite_master",
                          "SELECT 1; DELETE FROM fournisseurs"]:
            with self.subTest(statement=statement), self.assertRaises(sqlite3.Error):
                db.run_query(statement)
        self.assertEqual(db.run_query("SELECT count(*) FROM fournisseurs").iat[0, 0], 2)
        with db.read_connection() as conn, self.assertRaises(sqlite3.OperationalError):
            conn.execute("DELETE FROM fournisseurs")

    def test_row_cap_even_with_internal_or_negative_limit(self):
        sql = """WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t WHERE n<150)
                 SELECT n FROM (SELECT n FROM t LIMIT -1) LIMIT -1"""
        self.assertEqual(db.run_query(sql).shape, (100, 1))
        self.assertEqual(db.run_query(sql, limit=5).shape, (5, 1))

    def test_expensive_query_interrupted(self):
        with patch.object(db, "QUERY_SECONDS", 0.0), self.assertRaisesRegex(sqlite3.Error, "interrupt"):
            db.run_query("""WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t)
                         SELECT SUM(n) FROM t""")


class AppTests(ExampleDatabase):
    def app(self):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / "dashboard/app.py"))

    def test_review_and_filters_without_api_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            app = self.app().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "74,07 %")
            self.assertEqual(app.metric[3].value, "82,96 %")
            app.slider[0].set_value(100).run()
            self.assertEqual(app.metric[3].value, "92,59 %")
            next(x for x in app.selectbox if x.label == "Entrepôt").set_value(2).run()
            self.assertEqual(app.metric[0].value, "0,00 %")
            app.radio[0].set_value("Questions en français").run()
            self.assertIn("ANTHROPIC_API_KEY", app.info[0].value)
            self.assertFalse(app.exception)

    def test_chat_shows_the_corrected_query(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "offline-test"}), \
             patch("src.llm.question_to_sql", return_value="SELECT bad_column FROM fournisseurs"), \
             patch("src.llm.fix_sql", return_value="SELECT COUNT(*) AS total FROM fournisseurs") as fix, \
             patch("src.llm.explain_result", return_value="Deux fournisseurs.") as explain:
            app = self.app().run()
            app.radio[0].set_value("Questions en français").run()
            app.text_input[0].set_value("Combien de fournisseurs ?")
            next(b for b in app.button if b.label.startswith("Analyser")).click().run()
            self.assertFalse(app.exception)
            fix.assert_called_once()
            self.assertIn("SELECT COUNT(*)", app.code[0].value)
            self.assertEqual(app.dataframe[0].value.iat[0, 0], 2)
            self.assertEqual(explain.call_args.args[1], app.code[0].value)


class DemoDataTests(unittest.TestCase):
    def test_reproducible_seed_and_consistent_receipts(self):
        with closing(sqlite3.connect(":memory:")) as conn:
            create_schema(conn)
            seed(conn, as_of=END)
            def snapshot():
                return conn.execute("""SELECT SUM(qte_commandee), SUM(qte_livree),
                                    COUNT(*), MAX(date_livraison_reelle) FROM lignes_commande l
                                    JOIN commandes c ON c.id=l.commande_id""").fetchone()
            expected = snapshot()
            self.assertEqual(expected[-1], END.isoformat())
            mismatch = conn.execute("""
                SELECT c.id FROM commandes c JOIN lignes_commande l ON l.commande_id=c.id
                JOIN produits p ON p.id=l.produit_id
                GROUP BY c.id HAVING MAX(p.fournisseur_id != c.fournisseur_id)
                OR SUM(l.qte_commandee) != 6*c.nb_colis_commandes
                OR SUM(l.qte_livree) IS NOT (6*c.nb_colis_livres)
            """).fetchall()
            self.assertEqual(mismatch, [])
            create_schema(conn)
            seed(conn, as_of=END)
            self.assertEqual(snapshot(), expected)
