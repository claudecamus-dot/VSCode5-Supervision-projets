"""Ruptures A et B de la réflexion « approche disruptive » (arbitrées le 2026-07-31).

Ce que la mesure avait établi : sur 242 jobs enregistrés depuis les boutons du site,
241 étaient des artefacts de tests — le site est un rapport que personne n'interroge,
le poste de pilotage réel est la conversation. D'où :

  * **A** — la page commence par RÉPONDRE (ce qui a cassé, ce qui attend une décision,
    ce qui a bougé) au lieu d'exposer sa structure ;
  * **B** — un hook SessionStart local (`point_du_jour.py`) apporte « ce qui attend
    votre décision » dans le canal réellement utilisé, la conversation.

Les invariants gardés ici : la réponse dit la vérité des données (elle est DÉRIVÉE,
jamais rédigée), le silence est un message explicite (pas une absence), et le hook
reste court et en ASCII strict (une console cp1252 lève UnicodeDecodeError sur tout
caractère hors table — incident du 2026-07-29).
"""

import importlib.util
import os
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

HOOK = os.path.join(HUB, ".claude", "hooks", "point_du_jour.py")

PIL_CALME = {"en_alerte": [], "retards": [], "nb_findings": 0,
             "runs_a_solder": [], "tendances": None}
VEILLE_CALME = {"entrees": []}


class TestReponseDuJour:
    def test_le_calme_est_dit_pas_omis(self):
        h = scan.render_reponse_du_jour(PIL_CALME, VEILLE_CALME)
        assert "Rien ne vous attend" in h
        assert "reponse-calme" in h

    def test_un_projet_en_alerte_est_nomme(self):
        """Un chiffre ne se traite pas ; un nom, si."""
        pil = dict(PIL_CALME, en_alerte=[{"nom": "VSCode2"}])
        h = scan.render_reponse_du_jour(pil, VEILLE_CALME)
        assert "VSCode2" in h and "rj-casse" in h

    def test_ce_qui_attend_une_decision_est_compte(self):
        pil = dict(PIL_CALME, nb_findings=2, runs_a_solder=["a", "b", "c"])
        veille = {"entrees": [{"statut": "etudie"}, {"statut": "nouveau"},
                              {"statut": "adopte"}]}
        h = scan.render_reponse_du_jour(pil, veille)
        assert "<b>2</b> finding(s)" in h
        assert "<b>2</b> trouvaille(s)" in h  # adopte exclu
        assert "<b>3</b> run(s)" in h

    def test_chaque_constat_porte_un_lien_vers_un_onglet_reel(self):
        pil = dict(PIL_CALME, en_alerte=[{"nom": "VSCode2"}], nb_findings=1)
        h = scan.render_reponse_du_jour(pil, VEILLE_CALME)
        import re
        cibles = re.findall(r'data-goto="(\w+)"', h)
        assert cibles, "un constat sans lien n'est qu'une notification de plus"
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        for c in cibles:
            assert f'id="pane-{c}"' in page, f"lien vers un onglet inexistant : {c}"

    def test_ce_qui_a_bouge_n_apparait_que_si_ca_a_bouge(self):
        sans = scan.render_reponse_du_jour(dict(PIL_CALME, en_alerte=[{"nom": "X"}]), VEILLE_CALME)
        assert "rj-bouge" not in sans
        avec = scan.render_reponse_du_jour(
            dict(PIL_CALME, en_alerte=[{"nom": "X"}],
                 tendances={"deltas": {"nb_findings": 2}}), VEILLE_CALME)
        assert "rj-bouge" in avec and "2 findings en plus" in avec

    def test_la_reponse_precede_les_chiffres_dans_la_page_livree(self):
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        i, j = page.find('class="reponse-jour'), page.find('class="pilotage"')
        assert 0 < i < j, "la réponse doit se lire AVANT le bandeau de chiffres"

    def test_le_js_navigue_vers_l_onglet(self):
        js = open(os.path.join(HUB, "docs", "wiki_app.js"), encoding="utf-8").read()
        assert "data-goto" in js and "closest" in js


class TestCroisementCanonique:
    """Le croisement findings/arbitrages du hook DÉLÈGUE à `finding_arbitre()` du
    scan — il ne le réimplémente pas.

    La première version recodait ce croisement de tête : cible-contre-cible, sans
    catégorie ni re_challenge. La revue fraîche du 2026-07-31 a reproduit deux faux
    négatifs — les deux classes de bugs que le canon avait DÉJÀ payées et corrigées
    (friction cible-suppression 2026-07-21 ; constat prio 5 du 2026-07-28, trois
    constats sur quatre masqués). Un faux négatif ici est silencieux : le hook dit
    « rien ne vous attend » sur un finding qui attend — le pire mode de défaillance
    pour un point du jour.
    """

    def _pdj(self, tmp_path, findings, arbitrages, genere="2026-07-30"):
        import importlib.util, json
        spec = importlib.util.spec_from_file_location(
            "pdj_test", os.path.join(HUB, ".claude", "hooks", "point_du_jour.py"))
        pdj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdj)
        d = tmp_path / "diag.json"
        d.write_text(json.dumps({"genere": genere, "findings": findings}), encoding="utf-8")
        a = tmp_path / "arb.json"
        a.write_text(json.dumps({"arbitrages": arbitrages}), encoding="utf-8")
        pdj.DIAGNOSTIC, pdj.ARBITRAGES = str(d), str(a)
        return pdj

    def test_un_arbitrage_d_une_autre_categorie_ne_ferme_pas(self, tmp_path):
        pdj = self._pdj(tmp_path,
                        [{"cible": "skill-y", "categorie": "verification-manquante"}],
                        [{"cible": "skill-y", "categories": ["agent-mort"],
                          "date": "2026-07-29"}])
        assert pdj.findings_non_arbitres() == ["skill-y"]

    def test_re_challenge_prime_sur_un_arbitrage_anterieur(self, tmp_path):
        pdj = self._pdj(tmp_path,
                        [{"cible": "skill-x", "categorie": "ko-repete", "re_challenge": True}],
                        [{"cible": "skill-x", "categories": ["ko-repete"],
                          "date": "2026-07-20"}])
        assert pdj.findings_non_arbitres() == ["skill-x"]

    def test_un_arbitrage_posterieur_referme_le_re_challenge(self, tmp_path):
        pdj = self._pdj(tmp_path,
                        [{"cible": "skill-x", "categorie": "ko-repete", "re_challenge": True}],
                        [{"cible": "skill-x", "categories": ["ko-repete"],
                          "date": "2026-07-31"}])
        assert pdj.findings_non_arbitres() == []

    def test_findings_malforme_degrade_proprement(self, tmp_path):
        """`findings` non-liste (JSON édité à la main) : liste vide, pas d'exception
        rattrapée in extremis par le __main__ — la dégradation doit être propre."""
        import importlib.util, json
        spec = importlib.util.spec_from_file_location(
            "pdj_test2", os.path.join(HUB, ".claude", "hooks", "point_du_jour.py"))
        pdj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdj)
        d = tmp_path / "diag.json"
        d.write_text(json.dumps({"findings": "pas-une-liste"}), encoding="utf-8")
        pdj.DIAGNOSTIC = str(d)
        assert pdj.findings_non_arbitres() == []


class TestPointDuJour:
    """Le hook s'exécute pour de vrai — un hook qui casse bloque toutes les sessions."""

    def _run(self):
        return subprocess.run(
            [sys.executable, HOOK], capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace")

    def test_sort_en_zero_et_parle(self):
        out = self._run()
        assert out.returncode == 0, out.stderr[:300]
        assert "Point du jour" in out.stdout

    def test_stdout_ascii_strict(self):
        """Une console cp1252 lève UnicodeDecodeError sur tout caractère hors table
        quand un test capture ce flux en subprocess (incident 2026-07-29)."""
        out = self._run()
        out.stdout.encode("ascii")  # lève si non-ASCII

    def test_reste_court(self):
        """Au-delà de 4 lignes, le point du jour redevient le mur qu'on cesse de
        lire — la maladie qu'il est censé soigner."""
        lignes = [l for l in self._run().stdout.splitlines() if l.strip()]
        assert len(lignes) <= 4, lignes

    def test_est_branche_sur_sessionstart(self):
        import json
        with open(os.path.join(HUB, ".claude", "settings.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        cmds = [h.get("command", "") for bloc in d["hooks"]["SessionStart"]
                for h in bloc["hooks"]]
        assert any("point_du_jour" in c for c in cmds), cmds
