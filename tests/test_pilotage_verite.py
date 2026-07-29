"""Vérité du bandeau de pilotage (P1 de la revue UX 2026-07-29) : le bandeau
annonçait « Rien en attente d'arbitrage — système sain » pendant que l'onglet
Actions correctives listait 18 pratiques en écart sur 5 projets, parce que les
deux comptaient séparément. Le bandeau et l'onglet doivent désormais dériver
de la MÊME fonction — ces tests verrouillent l'écart mesuré et corrigé."""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _projet(nom, niveau_test="ok", niveau_deploiement="ok", findings=None):
    pratiques = {cle: {"niveau": "ok", "detail": ""} for cle, _ in scan.DIM_DET}
    pratiques["test_technique"]["niveau"] = niveau_test
    return {
        "nom": nom, "existe": True, "alerte": None,
        "pratiques": pratiques,
        "audit": {"dimensions": {}},
        "findings": findings or [],
        "runs_en_attente": [],
        "last_scan": None, "diag_date": None, "dernier_commit": None,
    }


class TestEcartsDuProjet:
    def test_dimension_moyenne_comptee(self):
        p = _projet("X", niveau_test="moyen")
        ecarts = scan.ecarts_du_projet(p)
        assert any(cle == "test_technique" for _, _, _, cle in ecarts)

    def test_dimension_ok_non_comptee(self):
        p = _projet("X")
        assert scan.ecarts_du_projet(p) == []

    def test_dimension_audit_degradee_comptee(self):
        p = _projet("X")
        p["audit"] = {"dimensions": {"robustesse": {"niveau": "moyen", "synthese": "x"}}}
        ecarts = scan.ecarts_du_projet(p)
        assert any(cle == "robustesse" for _, _, _, cle in ecarts)


class TestCompteEcarts:
    def test_projet_sans_ecart_absent_du_resume(self):
        assert scan.compte_ecarts([_projet("X")]) == []

    def test_projet_avec_ecart_present(self):
        resume = scan.compte_ecarts([_projet("X", niveau_test="moyen")])
        assert resume == [{"projet": "X", "n_total": 1, "n_critique": 0}]

    def test_niveau_absent_compte_critique(self):
        resume = scan.compte_ecarts([_projet("X", niveau_test="absent")])
        assert resume[0]["n_critique"] == 1

    def test_findings_comptes_et_toujours_critiques(self):
        p = _projet("X", findings=[{"titre": "f1"}, {"titre": "f2"}])
        resume = scan.compte_ecarts([p])
        assert resume[0] == {"projet": "X", "n_total": 2, "n_critique": 2}

    def test_tri_du_plus_critique_au_moins_critique(self):
        projets = [
            _projet("Peu", niveau_test="moyen"),
            _projet("Beaucoup", niveau_test="absent", findings=[{"titre": "f"}]),
        ]
        resume = scan.compte_ecarts(projets)
        assert [r["projet"] for r in resume] == ["Beaucoup", "Peu"]

    def test_projet_inexistant_ignore(self):
        assert scan.compte_ecarts([{"existe": False}]) == []


class TestBandeauCoherentAvecCorrectifs:
    """Le test qui aurait attrapé P1 : le bandeau doit refléter les mêmes
    projets/compteurs que l'onglet Actions correctives, pas un sous-ensemble."""

    def _veille_vide(self):
        return {"derniere_veille": "2026-07-29T00:00:00", "entrees": []}

    def test_pilotage_sain_quand_aucun_ecart(self):
        import datetime as dt
        pil = scan.compute_pilotage([_projet("X")], self._veille_vide(), dt.datetime.now())
        assert pil["nb_ecarts"] == 0 and pil["ecarts"] == []

    def test_pilotage_reflete_les_ecarts_reels(self):
        import datetime as dt
        projets = [_projet("X", niveau_test="moyen"),
                   _projet("Y", niveau_test="absent", findings=[{"titre": "f"}])]
        pil = scan.compute_pilotage(projets, self._veille_vide(), dt.datetime.now())
        assert pil["nb_ecarts"] == 3  # 1 (X) + 1 dimension + 1 finding (Y)
        assert {r["projet"] for r in pil["ecarts"]} == {"X", "Y"}

class TestPageLivree:
    """Sur la vraie page régénérée : si des écarts existent, le bandeau ne peut
    pas afficher « système sain » — c'est exactement P1 de la revue UX."""

    def test_coherence_bandeau_vs_correctifs_sur_wiki_reel(self):
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        i = page.find('id="pane-correctifs"')
        j = page.find('id="pane-exports"')
        onglet_correctifs = page[i:j] if i >= 0 and j > i else ""
        y_a_t_il_des_ecarts = "pratique(s) en écart" in onglet_correctifs
        if y_a_t_il_des_ecarts:
            assert "Rien en attente d'arbitrage" not in page[:page.find('id="pane-projets"')], (
                "le bandeau annonce système sain alors que Actions correctives "
                "liste des écarts — régression du bug P1")
        assert "pratiques en écart" in page.split('id="pane-projets"')[0], \
            "le compteur de pratiques en écart est absent du bandeau"
