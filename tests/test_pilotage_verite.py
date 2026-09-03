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
        assert resume == [{"projet": "X", "n_pratiques": 1, "n_findings": 0,
                           "n_total": 1, "n_critique": 0}]

    def test_niveau_absent_compte_critique(self):
        resume = scan.compte_ecarts([_projet("X", niveau_test="absent")])
        assert resume[0]["n_critique"] == 1

    def test_findings_comptes_et_toujours_critiques(self):
        p = _projet("X", findings=[{"titre": "f1"}, {"titre": "f2"}])
        resume = scan.compte_ecarts([p])
        assert resume[0] == {"projet": "X", "n_pratiques": 0, "n_findings": 2,
                             "n_total": 2, "n_critique": 2}

    def test_pratiques_et_findings_jamais_confondus(self):
        """Le défaut rapporté le 2026-07-29 : VScode5 avait ses 9 dimensions
        vertes et 5 findings ouverts, et le hub annonçait « 5 pratique(s) en
        écart » — une contradiction directe avec l'onglet Pratiques."""
        p = _projet("X", findings=[{"titre": "f"} for _ in range(5)])
        r = scan.compte_ecarts([p])[0]
        assert r["n_pratiques"] == 0 and r["n_findings"] == 5


class TestLibelleEcarts:
    def test_pratiques_seules(self):
        assert scan.libelle_ecarts(3, 0) == "3 pratique(s) en écart"

    def test_findings_seuls_ne_disent_jamais_pratique(self):
        libelle = scan.libelle_ecarts(0, 5)
        assert libelle == "5 finding(s) ouvert(s)"
        assert "pratique" not in libelle

    def test_les_deux_natures_nommees_separement(self):
        assert scan.libelle_ecarts(2, 1) == "2 pratique(s) en écart + 1 finding(s) ouvert(s)"

    def test_rien(self):
        assert scan.libelle_ecarts(0, 0) == "rien à corriger"

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
        assert pil["nb_pratiques_ecart"] == 2   # dimensions seules
        assert pil["nb_findings"] == 1          # findings comptés à part
        assert {r["projet"] for r in pil["ecarts"]} == {"X", "Y"}

    def test_tuiles_ne_gonflent_pas_les_pratiques_avec_les_findings(self):
        """La tuile « pratiques en écart » du bandeau doit compter des
        PRATIQUES : un projet tout vert avec 4 findings n'en apporte aucune."""
        import datetime as dt
        p = _projet("X", findings=[{"titre": "f"} for _ in range(4)])
        pil = scan.compute_pilotage([p], self._veille_vide(), dt.datetime.now())
        assert pil["nb_pratiques_ecart"] == 0
        assert pil["nb_findings"] == 4

class TestPageLivree:
    """Sur la vraie page régénérée : si des écarts existent, le bandeau ne peut
    pas afficher « système sain » — c'est exactement P1 de la revue UX."""

    def test_coherence_bandeau_vs_correctifs_sur_wiki_reel(self):
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        i = page.find('id="pane-correctifs"')
        # Depuis la fusion du 2026-09-03 (11 -> 5 onglets), pane-correctifs est un
        # sous-panneau de l'onglet fusionné 🩹 Arbitrer et n'est plus suivi
        # directement par pane-exports (désormais dans 🗄 Archive) : la borne
        # haute devient le prochain onglet de premier niveau, pane-archive.
        j = page.find('id="pane-archive"')
        onglet_correctifs = page[i:j] if i >= 0 and j > i else ""
        y_a_t_il_des_ecarts = "pratique(s) en écart" in onglet_correctifs
        if y_a_t_il_des_ecarts:
            assert "Rien en attente d'arbitrage" not in page[:page.find('id="pane-projets"')], (
                "le bandeau annonce système sain alors que Actions correctives "
                "liste des écarts — régression du bug P1")
        assert "pratiques en écart" in page.split('id="pane-projets"')[0], \
            "le compteur de pratiques en écart est absent du bandeau"

    def _page(self):
        return open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()

    def test_bandeau_et_onglet_annoncent_le_meme_libelle_par_projet(self):
        """Bandeau et onglet dérivent de la même fonction : ils doivent dire mot
        pour mot la même chose pour chaque projet."""
        import re
        page = self._page()
        bandeau = dict(re.findall(
            r'<li class="ecart">\S+ \[([^\]]+)\] (.+?) — à arbitrer', page))
        onglet = dict(re.findall(
            r'<summary>\S+ <b>([^<]+)</b> — ([^<]+)</summary>', page))
        assert bandeau, "aucune ligne d'écart dans le bandeau — regex ou rendu changé"
        assert bandeau == onglet, (
            "bandeau et onglet Actions correctives divergent : "
            f"{bandeau} != {onglet}")

    def test_aucun_projet_sans_pratique_en_ecart_nannonce_des_pratiques(self):
        """Le défaut rapporté : un projet 100 % vert en pratiques annoncé comme
        portant « N pratique(s) en écart » (c'étaient des findings)."""
        import re
        page = self._page()
        # Borne haute : pane-archive (voir test_coherence_bandeau_vs_correctifs_sur_wiki_reel
        # ci-dessus pour pourquoi ce n'est plus pane-exports depuis le 2026-09-03).
        i, j = page.find('id="pane-correctifs"'), page.find('id="pane-archive"')
        onglet = page[i:j]
        blocs = re.split(r'<details class="correctifs-projet">', onglet)[1:]
        for bloc in blocs:
            m = re.search(r'<b>([^<]+)</b> — ([^<]+)</summary>', bloc)
            assert m, "résumé de projet illisible dans l'onglet correctifs"
            nom, libelle = m.group(1), m.group(2)
            nb_cartes_pratique = bloc.count('badge-nature">pratique<')
            if nb_cartes_pratique == 0:
                assert "pratique(s) en écart" not in libelle, (
                    f"{nom} n'a aucune carte de pratique mais est annoncé "
                    f"« {libelle} » — régression de la confusion pratiques/findings")
            else:
                assert f"{nb_cartes_pratique} pratique(s) en écart" in libelle, (
                    f"{nom} : {nb_cartes_pratique} cartes de pratique mais "
                    f"libellé « {libelle} »")


class TestUnDossierExportNEstPasUnDeck:
    """Un écart affiché doit correspondre à un écart réel.

    Mesuré le 2026-09-01 en traitant la page pilotage : la pratique « design de deck »
    se déclenchait sur la seule PRÉSENCE d'un répertoire `Exports`/`export`. Trois
    projets de livrable `web` — VSCode1, VSCode2 et VScode5 — étaient donc jugés sur
    une discipline de slide, alors qu'aucun des trois répertoires ne contenait un seul
    `.pptx` (0 sur 5 fichiers, 0 sur 13, 0 sur 50). Celui du hub est son kit agentic.

    C'est la faute que le hub reproche à son propre étage 1 — mesurer une présence pour
    un fonctionnement — commise dans le critère qui note les autres.
    """

    def test_un_dossier_export_sans_pptx_ne_compte_pas(self, tmp_path):
        (tmp_path / "export").mkdir()
        (tmp_path / "export" / "kit.py").write_text("# pas un deck", encoding="utf-8")
        assert scan._contient_un_deck(str(tmp_path)) is False

    def test_un_pptx_reel_compte(self, tmp_path):
        (tmp_path / "Exports").mkdir()
        (tmp_path / "Exports" / "restitution.pptx").write_bytes(b"PK\x03\x04")
        assert scan._contient_un_deck(str(tmp_path)) is True

    def test_un_pptx_range_dans_un_sous_dossier_compte(self, tmp_path):
        (tmp_path / "export" / "2026-09").mkdir(parents=True)
        (tmp_path / "export" / "2026-09" / "d.pptx").write_bytes(b"PK\x03\x04")
        assert scan._contient_un_deck(str(tmp_path)) is True

    def test_aucun_dossier_export_ne_plante_pas(self, tmp_path):
        assert scan._contient_un_deck(str(tmp_path)) is False

    def test_le_hub_n_est_pas_juge_sur_une_discipline_de_deck(self):
        """Le cas qui a ouvert le constat : `export/` du hub est le kit agentic."""
        hub = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assert os.path.isdir(os.path.join(hub, "export")), (
            "ce test perd son objet si le hub n'a plus de dossier export/")
        assert scan._contient_un_deck(hub) is False, (
            "le kit agentic du hub est pris pour un dossier de decks")
