"""
test_offline.py — Tests unitaires SANS appel API (validateur, couche sémantique, prompt).

    python -m unittest tests.test_offline -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sql_validator import (  # noqa: E402
    SQLValidationError, validate, ensure_limit, open_readonly, dry_run,
)
from src.semantic_layer import METRIQUES, render_for_prompt, find_metric  # noqa: E402

DB_PATH = Path(__file__).parent.parent / "data" / "supply_chain.db"


class TestValidateurLexical(unittest.TestCase):
    def test_select_simple_accepte(self):
        self.assertTrue(validate("SELECT * FROM produits").startswith("SELECT"))

    def test_cte_acceptee(self):
        self.assertTrue(validate("WITH x AS (SELECT 1) SELECT * FROM x").startswith("WITH"))

    def test_delete_rejete(self):
        with self.assertRaises(SQLValidationError):
            validate("DELETE FROM commandes")

    def test_drop_rejete_meme_en_minuscules(self):
        with self.assertRaises(SQLValidationError):
            validate("drop table stocks")

    def test_multi_instructions_rejetees(self):
        with self.assertRaises(SQLValidationError):
            validate("SELECT 1; DROP TABLE stocks")

    def test_pragma_rejete(self):
        with self.assertRaises(SQLValidationError):
            validate("PRAGMA table_info(stocks)")

    def test_update_camoufle_dans_select_rejete(self):
        with self.assertRaises(SQLValidationError):
            validate("SELECT 1 FROM produits WHERE 1=1 UNION SELECT 2; UPDATE produits SET prix_achat_ht = 0")

    def test_mot_cle_dans_litteral_accepte(self):
        # 'DROP' dans un libellé produit ne doit PAS déclencher de faux positif
        sql = "SELECT * FROM produits WHERE libelle = 'Pastilles DROP delete 200g'"
        self.assertTrue(validate(sql))

    def test_colonne_updated_at_acceptee(self):
        # UPDATE en sous-chaîne d'un identifiant ne doit pas déclencher
        self.assertTrue(validate("SELECT updated_at FROM produits"))

    def test_requete_vide_rejetee(self):
        with self.assertRaises(SQLValidationError):
            validate("   ")

    def test_limit_injecte_si_absent(self):
        self.assertIn("LIMIT 100", ensure_limit("SELECT * FROM produits"))

    def test_limit_existant_preserve(self):
        sql = ensure_limit("SELECT * FROM produits LIMIT 5")
        self.assertEqual(sql.count("LIMIT"), 1)


@unittest.skipUnless(DB_PATH.exists(), "base absente — lancer python data/seed_data.py")
class TestConnexionReadOnly(unittest.TestCase):
    def test_ecriture_refusee_par_le_moteur(self):
        conn = open_readonly(str(DB_PATH))
        with self.assertRaises(Exception):
            conn.execute("CREATE TABLE pwned (x)")
        conn.close()

    def test_dry_run_detecte_colonne_halluccinee(self):
        conn = open_readonly(str(DB_PATH))
        with self.assertRaises(SQLValidationError):
            dry_run(conn, "SELECT colonne_inventee FROM produits")
        conn.close()

    def test_dry_run_accepte_sql_valide(self):
        conn = open_readonly(str(DB_PATH))
        dry_run(conn, "SELECT nom FROM fournisseurs")  # ne doit pas lever
        conn.close()


class TestCoucheSemantique(unittest.TestCase):
    def test_chaque_metrique_est_complete(self):
        for m in METRIQUES:
            for cle in ("nom", "synonymes", "definition", "sql", "grain", "pieges"):
                self.assertIn(cle, m, f"clé '{cle}' manquante pour {m.get('nom')}")

    def test_rendu_prompt_contient_toutes_les_metriques(self):
        rendu = render_for_prompt()
        for m in METRIQUES:
            self.assertIn(m["nom"], rendu)

    def test_recherche_par_synonyme(self):
        self.assertEqual(find_metric("stock dormant")["nom"], "SLOB (Slow moving & Obsolete)")
        self.assertIsNone(find_metric("inexistant"))


@unittest.skipUnless(DB_PATH.exists(), "base absente — lancer python data/seed_data.py")
class TestAssemblagePrompt(unittest.TestCase):
    def test_prompt_assemble_sans_placeholder_restant(self):
        from src.db import get_schema_context
        from src.llm import build_system_prompt
        prompt = build_system_prompt(get_schema_context())
        for placeholder in ("<<SCHEMA>>", "<<COUCHE_SEMANTIQUE>>", "<<DATE_DU_JOUR>>"):
            self.assertNotIn(placeholder, prompt)
        self.assertIn("lignes_commande", prompt)   # schéma injecté
        self.assertIn("Taux de Service", prompt)   # couche sémantique injectée


if __name__ == "__main__":
    unittest.main(verbosity=2)
