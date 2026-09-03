"""Onglet Tutoriel du wiki (demande utilisateur 2026-07-29) : le glossaire des
concepts du dispositif doit être présent dans la page livrée — bouton d'onglet,
pane, et chaque concept clé défini."""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

CONCEPTS_CLES = ["Agent", "Sous-agent", "Skill", "Rules (CLAUDE.md)", "Hook",
                 "Playbook", "Orchestrateur", "Superviseur (étages 1 et 2)",
                 "Finding", "Arbitrage", "Run (journal)", "Canon + sync",
                 "Veille agentic"]


class TestRenderTutoriel:
    def test_tous_les_concepts_cles_definis(self):
        html = scan.render_tutoriel_html()
        for concept in CONCEPTS_CLES:
            assert f"<h4>{concept}</h4>" in html, f"concept absent du tutoriel : {concept}"

    def test_chaque_concept_a_un_exemple_reel(self):
        # Le contrat du glossaire : jamais une définition hors-sol, toujours
        # l'incarnation dans CE dispositif (« Ici : … »).
        html = scan.render_tutoriel_html()
        assert html.count("Ici :") == sum(len(c) for _, c in scan.TUTORIEL_CONCEPTS)


class TestPageLivree:
    def test_onglet_et_pane_presents(self):
        # Depuis la fusion du 2026-09-03 (11 -> 5 onglets primaires), Tutoriel n'est
        # plus un bouton `data-pane="tutoriel"` de la barre principale : c'est un
        # sous-panneau de l'onglet 🗄 Archive, atteint par une ancre du sommaire
        # interne (id="tab-tutoriel" href="#pane-tutoriel"), pas par un bouton
        # `nav.tabs`. Ce que ce test garde : le point d'entrée existe ET pointe
        # réellement vers le panneau.
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        assert 'id="tab-tutoriel"' in page, "point d'entrée vers Tutoriel absent"
        assert 'href="#pane-tutoriel"' in page, "le point d'entrée ne pointe plus vers le pane Tutoriel"
        assert 'id="pane-tutoriel"' in page, "pane Tutoriel absent"
        assert "<h4>Sous-agent</h4>" in page
