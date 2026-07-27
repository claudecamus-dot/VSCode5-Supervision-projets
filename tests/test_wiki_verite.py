"""Non-régression du finding wiki-verite (diagnostic 2026-07-27).

Deux défauts corrigés, chacun verrouillé ici :
  1. wiki.html régénéré par scan_projets.py avait PERDU les marqueurs
     TODO-AGENTS-HTML lors de la refonte à onglets — scan_transcripts.py ne
     pouvait plus injecter le bloc agents (signalé par le hook à chaque session).
  2. Le répertoire craft affichait des cellules figées contredites par la table
     mesurée de la même page (CI « 1/6 », « aucun linter Python », VSCode2 en >=).
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _projet(nom, detail):
    return {"nom": nom, "existe": True,
            "pratiques": {"pratiques_rules": {"niveau": "moyen", "detail": detail}}}


class TestBlocAgentsHtml:
    def test_sans_ancien_html_pose_les_marqueurs(self):
        bloc = scan.bloc_agents_html(None)
        assert bloc.startswith(scan.AGENTS_HTML_START)
        assert bloc.endswith(scan.AGENTS_HTML_END)

    def test_preserve_le_bloc_injecte_par_scan_transcripts(self):
        # scan_transcripts remplace entre marqueurs ; la régénération de la page
        # ne doit pas perdre ce contenu.
        injecte = (scan.AGENTS_HTML_START + " — bloc généré -->"
                   "<section>données agents réelles</section>" + scan.AGENTS_HTML_END)
        ancien = "<html><body>" + injecte + "</body></html>"
        assert scan.bloc_agents_html(ancien) == injecte

    def test_ancien_html_sans_marqueurs_revient_au_placeholder(self):
        bloc = scan.bloc_agents_html("<html><body>page sans bloc</body></html>")
        assert scan.AGENTS_HTML_START in bloc and bloc.endswith(scan.AGENTS_HTML_END)

    def test_marqueurs_identiques_a_ceux_de_scan_transcripts(self):
        # Le contrat entre les deux scripts : les mêmes chaînes exactes.
        canon = open(os.path.join(HUB, ".claude", "dispositif", "canon",
                                  "scan_transcripts.py"), encoding="utf-8").read()
        assert 'HTML_MARK_START = "' + scan.AGENTS_HTML_START + '"' in canon
        assert "TODO-AGENTS-HTML:END" in scan.AGENTS_HTML_END

    def test_render_html_emet_les_marqueurs(self):
        # La page régénérée doit toujours contenir les deux marqueurs.
        assert scan.AGENTS_HTML_START in scan.bloc_agents_html(None)


class TestCraftEffectives:
    def test_ci_et_linter_derives_de_la_mesure(self):
        existants = [
            _projet("A", "linter, CI, CLAUDE.md (69 l), conventions"),
            _projet("B", "linter, CLAUDE.md (149 l)"),
            _projet("C", "CLAUDE.md (107 l)"),
        ]
        craft = {c["nom"]: c for c in scan.craft_effectives(existants)}
        ci = craft["Intégration continue"]
        assert "A" in ci["flotte"] and "(1/3)" in ci["flotte"]
        assert ci["statut"] == "moyen"
        linter = craft["Analyse statique / linter"]
        assert "A" in linter["flotte"] and "B" in linter["flotte"]
        assert "(2/3)" in linter["flotte"]

    def test_aucun_projet_outille_donne_absent(self):
        existants = [_projet("A", "CLAUDE.md (10 l)")]
        craft = {c["nom"]: c for c in scan.craft_effectives(existants)}
        assert craft["Intégration continue"]["statut"] == "absent"
        assert "Aucune CI" in craft["Intégration continue"]["flotte"]

    def test_tous_outilles_donne_ok(self):
        existants = [_projet("A", "linter, CI"), _projet("B", "linter, CI")]
        craft = {c["nom"]: c for c in scan.craft_effectives(existants)}
        assert craft["Intégration continue"]["statut"] == "ok"
        assert craft["Analyse statique / linter"]["statut"] == "ok"

    def test_pas_de_faux_positif_sur_sous_chaine(self):
        # « CI » ne doit pas matcher dans « CLAUDE.md » ni un libellé contenant ci.
        existants = [_projet("A", "conventions, CLAUDE.md (36 l)")]
        craft = {c["nom"]: c for c in scan.craft_effectives(existants)}
        assert craft["Intégration continue"]["statut"] == "absent"

    def test_les_autres_pratiques_sont_inchangees(self):
        existants = [_projet("A", "linter, CI")]
        noms_avant = [c["nom"] for c in scan.CRAFT_PRATIQUES]
        noms_apres = [c["nom"] for c in scan.craft_effectives(existants)]
        assert noms_avant == noms_apres
        deps = next(c for c in scan.craft_effectives(existants)
                    if c["nom"].startswith("Dépendances épinglées"))
        assert "==" in deps["flotte"]  # texte à jour (VSCode2 épinglé, finding fermé)
