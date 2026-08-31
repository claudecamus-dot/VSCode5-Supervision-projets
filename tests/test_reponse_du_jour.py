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


class TestTrouvaillesArbitrees:
    """Correctif majeur 2 (campagne 2026-08-31) : `trouvailles_en_attente()` filtrait
    uniquement sur `statut in (nouveau, etudie)` de veille.json, sans jamais consulter
    `arbitrages.json`. Vérifié sur le journal réel : 3 des 4 trouvailles annoncées
    « en attente de votre décision » portaient déjà une décision tracée dans
    arbitrages.json (cible `veille:<slug>`) — jamais reportée dans veille.json, faute
    de mécanisme d'écriture retour. Le hook re-nagguait donc une décision déjà prise.

    veille.json ne porte pas de champ `cible` (contrairement aux findings du
    diagnostic, que `finding_arbitre()` ferme dessus) : le rapprochement se fait par
    le slug de la cible `veille:<slug>` contre l'URL/titre de la trouvaille -- seule
    information stable qu'elle porte. Le test couvre le cas où le slug choisi par
    l'arbitrage est plus court que le nom du dépôt (ex. `veille:multi-agent-observability`
    face à un dépôt `disler/claude-code-hooks-multi-agent-observability`), pas
    seulement l'égalité stricte.
    """

    def _pdj(self, tmp_path, entrees, arbitrages):
        import importlib.util, json
        spec = importlib.util.spec_from_file_location(
            "pdj_veille_test", os.path.join(HUB, ".claude", "hooks", "point_du_jour.py"))
        pdj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pdj)
        v = tmp_path / "veille.json"
        v.write_text(json.dumps({"entrees": entrees}), encoding="utf-8")
        a = tmp_path / "arb.json"
        a.write_text(json.dumps({"arbitrages": arbitrages}), encoding="utf-8")
        pdj.VEILLE, pdj.ARBITRAGES = str(v), str(a)
        return pdj

    def test_cas_reel_4_trouvailles_2_closes_2_annoncees(self, tmp_path):
        """Le cas mesuré sur les fichiers réels le 2026-08-31 : 4 trouvailles au statut
        etudie, 3 portent un arbitrage -- mais celui de `dev-browser` dit lui-meme
        « ADOPTION CIBLEE EN ATTENTE ». Seules les 2 decisions conclusives ferment leur
        trouvaille ; il en reste donc 2 annoncees, dont la seule attente reelle du lot.
        Compter 1 ici serait juste par accident et faux sur le fond."""
        entrees = [
            {"titre": "microsoft/hve-core — skill PowerPoint pilotee par YAML",
             "url": "https://github.com/microsoft/hve-core", "statut": "etudie",
             "date": "2026-07-23"},
            {"titre": "disler/claude-code-hooks-multi-agent-observability — observabilite",
             "url": "https://github.com/disler/claude-code-hooks-multi-agent-observability",
             "statut": "etudie", "date": "2026-07-23"},
            {"titre": "sawyerhood/dev-browser — verifie son travail dans un navigateur",
             "url": "https://github.com/sawyerhood/dev-browser", "statut": "etudie",
             "date": "2026-07-29"},
            {"titre": "org/genuinely-open-tool — jamais instruite",
             "url": "https://github.com/org/genuinely-open-tool", "statut": "etudie",
             "date": "2026-07-29"},
        ]
        arbitrages = [
            {"cible": "veille:hve-core", "date": "2026-07-31",
             "decision": "INSTRUIT, MIGRATION ECARTEE"},
            {"cible": "veille:multi-agent-observability", "date": "2026-07-31",
             "decision": "INSTRUIT, PAS ADOPTE"},
            {"cible": "veille:dev-browser", "date": "2026-07-31",
             "decision": "INSTRUIT, ADOPTION CIBLEE EN ATTENTE"},
        ]
        pdj = self._pdj(tmp_path, entrees, arbitrages)
        n, age = pdj.trouvailles_en_attente()
        assert n == 2, "2 decisions conclusives ferment ; le « EN ATTENTE » reste ouvert"
        assert age == pdj._age_jours("2026-07-29")

    def test_un_arbitrage_qui_dit_en_attente_ne_ferme_pas_la_trouvaille(self, tmp_path):
        """Le contre-exemple mesure le 2026-08-31 sur arbitrages.json reel.

        `veille:dev-browser` porte la decision « INSTRUIT, ADOPTION CIBLEE EN ATTENTE » :
        l'arbitrage EXISTE, mais il dit de lui-meme que la decision n'est pas prise. La
        fermer sur la seule presence de l'arbitrage enterre la seule attente reelle --
        c'est-a-dire exactement le defaut que le finding `veille:decision-non-reinjectee`
        reprochait au hook, reproduit par l'autre bout.

        Ce n'est pas du grattage de prose : « EN ATTENTE » est une convention explicite
        du champ `decision`, au meme titre que ACCEPTE / ECARTE / INSTRUIT.
        """
        entrees = [{"titre": "sawyerhood/dev-browser — verifie son travail",
                    "url": "https://github.com/sawyerhood/dev-browser",
                    "statut": "etudie", "date": "2026-07-29"}]
        arbitrages = [{"cible": "veille:dev-browser", "date": "2026-07-31",
                       "decision": "INSTRUIT, ADOPTION CIBLEE EN ATTENTE (statut etudie)"}]
        pdj = self._pdj(tmp_path, entrees, arbitrages)
        n, _age = pdj.trouvailles_en_attente()
        assert n == 1, "un arbitrage qui se declare EN ATTENTE ne clot pas la question"

    def test_en_attente_dans_le_CORPS_de_la_decision_ne_rouvre_pas(self, tmp_path):
        """Le pendant du test precedent, mesure sur le fichier reel le 2026-08-31.

        Les decisions de `veille:multi-agent-observability` et `veille:hve-core` sont
        conclusives (« INSTRUIT, PAS ADOPTE », « MIGRATION ECARTEE ») mais leur PROSE
        contient « en attente » a propos d'autre chose. Chercher le marqueur dans tout
        le texte rouvrait les deux : le verdict se lit dans la TETE de la decision
        (avant le premier « : »), la ou la convention du fichier le place.
        """
        entrees = [{"titre": "disler/claude-code-hooks-multi-agent-observability",
                    "url": "https://github.com/disler/claude-code-hooks-multi-agent-observability",
                    "statut": "etudie", "date": "2026-07-23"}]
        arbitrages = [{"cible": "veille:multi-agent-observability", "date": "2026-07-31",
                       "decision": "INSTRUIT, PAS ADOPTE (statut etudie) : le repo est "
                                   "dormant, et la refonte annoncee reste en attente "
                                   "chez son auteur."}]
        pdj = self._pdj(tmp_path, entrees, arbitrages)
        assert pdj.trouvailles_en_attente() == (0, None), (
            "un « en attente » dans le corps de la decision ne doit pas rouvrir un verdict conclusif")

    def test_slug_arbitrage_plus_court_que_le_depot_ferme_quand_meme(self, tmp_path):
        """`veille:multi-agent-observability` doit fermer une trouvaille dont le depot
        s'appelle `claude-code-hooks-multi-agent-observability` : le slug humain choisi
        pour l'arbitrage n'est pas force d'etre le nom exact du depot."""
        entrees = [{"titre": "disler/claude-code-hooks-multi-agent-observability",
                    "url": "https://github.com/disler/claude-code-hooks-multi-agent-observability",
                    "statut": "etudie", "date": "2026-07-23"}]
        arbitrages = [{"cible": "veille:multi-agent-observability", "date": "2026-07-31",
                       "decision": "INSTRUIT, PAS ADOPTE"}]
        pdj = self._pdj(tmp_path, entrees, arbitrages)
        assert pdj.trouvailles_en_attente() == (0, None)

    def test_sans_arbitrage_correspondant_reste_en_attente(self, tmp_path):
        entrees = [{"titre": "org/tool — jamais instruite",
                    "url": "https://github.com/org/tool", "statut": "etudie",
                    "date": "2026-07-29"}]
        pdj = self._pdj(tmp_path, entrees, [])
        n, age = pdj.trouvailles_en_attente()
        assert n == 1

    def test_arbitrage_sur_une_autre_trouvaille_ne_ferme_pas_celle_ci(self, tmp_path):
        """Un arbitrage `veille:hve-core` ne doit pas fermer une trouvaille sans
        rapport lexical -- pas de fermeture par simple presence d'UN arbitrage
        `veille:` quelconque dans le fichier."""
        entrees = [{"titre": "org/tool-sans-rapport — jamais instruite",
                    "url": "https://github.com/org/tool-sans-rapport", "statut": "etudie",
                    "date": "2026-07-29"}]
        arbitrages = [{"cible": "veille:hve-core", "date": "2026-07-31",
                       "decision": "INSTRUIT, MIGRATION ECARTEE"}]
        pdj = self._pdj(tmp_path, entrees, arbitrages)
        n, _ = pdj.trouvailles_en_attente()
        assert n == 1

    def test_statut_adopte_ou_ecarte_toujours_ignore(self, tmp_path):
        """Non-regression : le filtre sur le statut reste la premiere passe."""
        entrees = [{"titre": "org/tool — deja tranchee", "url": "https://github.com/org/tool",
                    "statut": "adopte", "date": "2026-07-01"}]
        pdj = self._pdj(tmp_path, entrees, [])
        assert pdj.trouvailles_en_attente() == (0, None)


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
