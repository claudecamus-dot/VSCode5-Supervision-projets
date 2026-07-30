"""Non-régression du finding wiki:finitions-lisibilite (diagnostic 2026-07-29).

`tronque()` remplace les troncatures brutes `txt[:n]` du wiki (audits, écarts de
pratique) qui coupaient en plein mot (« un process PowerShell par r ») sans le
signaler — le lecteur croyait lire la phrase entière. Le texte complet reste
accessible via l'attribut title= posé à l'appelant.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class TestTronque:
    def test_texte_court_inchange(self):
        assert scan.tronque("un process réel", 70) == "un process réel"

    def test_texte_vide_ou_none(self):
        assert scan.tronque("", 70) == ""
        assert scan.tronque(None, 70) == ""

    def test_coupe_a_la_frontiere_de_mot(self):
        # espace trouvé au-delà de 60 % de la limite -> coupe reculée au mot entier.
        txt = "un process PowerShell par requete, sans jamais fermer le descripteur"
        res = scan.tronque(txt, 30)
        assert res == "un process PowerShell par…"
        assert "requ" not in res  # jamais de mot coupé en plein milieu

    def test_espace_trop_tot_replie_sur_la_coupe_brute(self):
        # espace trouvé avant 60 % de la limite -> pas assez de gain, coupe brute gardée.
        txt = "un process PowerShell par requete, sans jamais fermer le descripteur"
        res = scan.tronque(txt, 20)
        assert res == "un process PowerShel…"

    def test_mot_unique_trop_long_coupe_quand_meme(self):
        # Aucun espace dans les 60% -> repli sur la coupe brute (pas de mot à sauver).
        txt = "a" * 100
        res = scan.tronque(txt, 20)
        assert res == "a" * 20 + "…"

    def test_ponctuation_de_fin_retiree_avant_ellipse(self):
        txt = "premier point, deuxième point, troisième"
        res = scan.tronque(txt, 15)
        assert res.endswith("…")
        assert not res.startswith(" ")
        assert res[-2] not in " ,;:.—-"
