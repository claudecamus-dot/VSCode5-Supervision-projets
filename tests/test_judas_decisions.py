"""Le judas à trois décisions + la jauge du doyen + les verbes poussés au terminal.

Chantier arbitré le 2026-08-31 (option « Judas compté » + « Vous prévenir ailleurs »
de la salle atelier-idées, page « Trois lectures d'un zéro » v3) et finding
`flotte:canon-ecrit-jamais-commite` (b) :

1. La page ne propose plus que les TROIS actions reliées aux décisions que
   l'utilisateur prend vraiment — arbitrer un finding (valider/refuser), arbitrer
   une trouvaille de veille (adopter/écarter), solder un run en attente — chacune
   AFFICHÉE SUR l'objet en attente, jamais en bouton générique. Les autres boutons
   d'action (scan, sync-check, package-check, pdf, deploy, diagnostic, audit,
   remediation, veille, reflexion, deployer-veille) sont retirés du générateur ;
   les salles (« Déclencher », ex-« En débattre ») restent, câblées la veille sur demande utilisateur.
2. `git_etat()` mesure l'ÂGE du doyen non commité : « 20 non commités » ne
   distingue pas une séance en cours d'une dette de 39 jours — « 20 · doyen 39 j »
   tranche d'un coup d'œil (proposition (b) du finding, arbitrée ACCEPTÉE).
3. `point_du_jour.py` pousse des COMMANDES prêtes à taper (applique/refuse,
   adopte/écarte), pas des dénombrements : l'info arrive dans le canal utilisé.

Les fixtures écrivent des journaux/JSON temporaires ; rien ne touche les données
de production (AGENT_SUPERVISION_SKIP_SCAN posé sur les scripts qui régénèrent).
"""

import importlib.util
import json
import os
import subprocess
import time

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _charge(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, os.path.join(HUB, chemin))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = _charge("scan_projets_judas", os.path.join("scripts", "scan_projets.py"))
serve = _charge("serve_wiki_judas", os.path.join("scripts", "serve_wiki.py"))
pdj = _charge("point_du_jour_judas", os.path.join(".claude", "hooks", "point_du_jour.py"))
ecarter = _charge("ecarter_trouvaille_judas",
                  os.path.join(".claude", "supervision", "ecarter_trouvaille.py"))


# --------------------------------------------------------------------------
# 1. Jauge du doyen non commité (finding flotte:canon-ecrit-jamais-commite, b)
# --------------------------------------------------------------------------
class TestDoyenNonCommite:
    def _repo(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True,
                       capture_output=True)
        return tmp_path

    def test_doyen_mesure_sur_fichier_ancien(self, tmp_path):
        repo = self._repo(tmp_path)
        vieux = repo / "vieux.txt"
        vieux.write_text("dette", encoding="utf-8")
        il_y_a_10_j = time.time() - 10 * 86400
        os.utime(vieux, (il_y_a_10_j, il_y_a_10_j))
        etat = scan.git_etat(str(repo))
        assert etat["non_commite"] == 1
        assert etat["doyen_jours"] is not None and etat["doyen_jours"] >= 9, (
            "un fichier non commité vieux de 10 jours doit donner un doyen ~10 j")

    def test_doyen_absent_sur_arbre_propre(self, tmp_path):
        repo = self._repo(tmp_path)
        etat = scan.git_etat(str(repo))
        assert etat["non_commite"] == 0
        assert etat["doyen_jours"] is None

    def test_doyen_fail_open_hors_depot(self, tmp_path):
        etat = scan.git_etat(str(tmp_path / "pas-un-depot"))
        assert etat["doyen_jours"] is None

    def test_doyen_ignore_les_fichiers_supprimes(self, tmp_path):
        """Un fichier en statut D n'a plus de mtime : il ne doit ni planter ni
        fabriquer un doyen fantôme."""
        repo = self._repo(tmp_path)
        f = repo / "efface.txt"
        f.write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c",
                        "user.name=t", "commit", "-qm", "init"], check=True,
                       capture_output=True)
        f.unlink()
        etat = scan.git_etat(str(repo))
        assert etat["non_commite"] == 1
        assert etat["doyen_jours"] is None   # rien de mesurable, pas d'invention

    def test_cellule_arbre_affiche_le_doyen(self):
        html = scan.cellule_arbre(20, 39)
        assert "20 non commités" in html and "doyen 39 j" in html

    def test_cellule_arbre_propre_et_inconnu(self):
        assert "propre" in scan.cellule_arbre(0, None)
        assert scan.cellule_arbre(None, None) == "?"


# --------------------------------------------------------------------------
# 2. Le judas : collecte + rendu des trois décisions
# --------------------------------------------------------------------------
@pytest.fixture
def decisions_fixture(tmp_path, monkeypatch):
    """Un jeu de données minimal : 1 finding ouvert, 1 trouvaille en attente,
    1 run en-attente-validation — via les VRAIS chemins monkeypatchés."""
    diag = tmp_path / "diagnostic.json"
    diag.write_text(json.dumps({
        "generated": "2026-08-30",
        "findings": [{"cible": "flotte:test-judas", "categorie": "pratique-dev",
                      "titre": "Un finding de test"}],
    }), encoding="utf-8")
    veille = tmp_path / "veille.json"
    veille.write_text(json.dumps({
        "derniere_veille": "2026-08-29",
        "entrees": [{"titre": "Trouvaille de test — épatante", "url": "https://x",
                     "statut": "etudie", "date": "2026-07-29",
                     "pertinence": "à décider"}],
    }), encoding="utf-8")
    arb = tmp_path / "arbitrages.json"
    arb.write_text(json.dumps({"arbitrages": []}), encoding="utf-8")
    racine = tmp_path / "hub"
    (racine / ".claude" / "orchestration").mkdir(parents=True)
    (racine / ".claude" / "orchestration" / "runs.jsonl").write_text(
        json.dumps({"ts": "2026-08-31T18:00:00+02:00",
                    "demande": "livrable à valider",
                    "resultat": "en-attente-validation"}) + "\n",
        encoding="utf-8")
    module_pdj = scan.charge_point_du_jour()
    monkeypatch.setattr(module_pdj, "DIAGNOSTIC", str(diag))
    monkeypatch.setattr(module_pdj, "VEILLE", str(veille))
    monkeypatch.setattr(module_pdj, "ARBITRAGES", str(arb))
    monkeypatch.setattr(scan, "ROOT", str(racine))
    return tmp_path


class TestCollecteDecisions:
    def test_collecte_les_trois_familles(self, decisions_fixture):
        dec = scan.collecte_decisions_en_attente()
        assert [f["cible"] for f in dec["findings"]] == ["flotte:test-judas"]
        assert [t["titre"] for t in dec["trouvailles"]] == [
            "Trouvaille de test — épatante"]
        assert [r["ts"] for r in dec["runs"]] == ["2026-08-31T18:00:00+02:00"]

    def test_un_run_solde_ne_compte_plus(self, decisions_fixture, monkeypatch):
        runs = os.path.join(scan.ROOT, ".claude", "orchestration", "runs.jsonl")
        with open(runs, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "t", "demande": "d",
                                 "resultat": "succes"}) + "\n")
        assert scan.collecte_decisions_en_attente()["runs"] == []


class TestRenduJudas:
    def test_chaque_decision_porte_ses_boutons(self, decisions_fixture):
        html = scan.render_decisions_html(scan.collecte_decisions_en_attente())
        assert 'data-action="valider" data-cible="flotte:test-judas"' in html
        assert 'data-action="refuser" data-cible="flotte:test-judas"' in html
        assert 'data-action="adopter"' in html and "Trouvaille de test" in html
        assert 'data-action="ecarter-veille"' in html
        assert ('data-action="solder" data-cible="2026-08-31T18:00:00+02:00"'
                in html)

    def test_vide_est_une_information(self):
        html = scan.render_decisions_html(
            {"findings": [], "trouvailles": [], "runs": []})
        assert "Rien n'attend votre décision" in html

    def test_la_zone_de_rapport_existe(self, decisions_fixture):
        html = scan.render_decisions_html(scan.collecte_decisions_en_attente())
        assert 'id="rapports-decisions"' in html


class TestCoupeDesBoutons:
    """Les boutons d'action génériques ne sont plus GÉNÉRÉS ; les salles restent.
    Assertion sur la source du générateur (même pattern que TestDispositifOriente) :
    le rendu complet exige des fixtures lourdes, la source est l'invariant."""
    SOURCE = open(os.path.join(HUB, "scripts", "scan_projets.py"),
                  encoding="utf-8").read()

    @pytest.mark.parametrize("action", [
        "scan", "sync-check", "package-check", "pdf", "deploy", "diagnostic",
        "audit", "remediation", "veille", "reflexion", "deployer-veille"])
    def test_plus_aucun_bouton_generique(self, action):
        assert f'data-action="{action}"' not in self.SOURCE, (
            f"le bouton {action} devait être retiré du générateur (judas compté)")

    def test_les_salles_restent(self):
        assert "btn-party" in self.SOURCE and 'data-action="party"' in self.SOURCE

    def test_le_judas_est_assemble_dans_la_page(self):
        i = self.SOURCE.find('id="pane-actions"')
        assert i > -1
        assert "render_decisions_html" in self.SOURCE[i:i + 2000], (
            "l'onglet Actions doit rendre le judas (render_decisions_html)")

    def test_les_commandes_terminal_sont_documentees(self):
        """Couper un bouton sans documenter la commande = cacher, pas simplifier."""
        assert "scan_projets.py --no-refresh --pdf" in self.SOURCE


# --------------------------------------------------------------------------
# 3. serve_wiki : les trois nouvelles actions, et rien d'autre ne change
# --------------------------------------------------------------------------
class TestActionsServeur:
    def test_solder_appelle_log_run(self):
        argv = serve.action_solder("2026-08-31T18:00:00+02:00")
        assert "--solde" in argv and "succes" in argv
        assert argv[argv.index("--solde") + 1] == "2026-08-31T18:00:00+02:00"
        assert any(a.endswith("log_run.py") for a in argv)

    def test_solder_refuse_cible_vide(self):
        assert serve.action_solder("") is None
        assert serve.action_solder(None) is None

    def test_ecarter_appelle_le_script(self):
        argv = serve.action_ecarter_veille("Titre X", "raison Y")
        assert any(a.endswith("ecarter_trouvaille.py") for a in argv)
        assert "Titre X" in argv and "raison Y" in argv

    def test_adopter_lance_la_commande_adopte(self, monkeypatch):
        monkeypatch.setattr(serve, "CLAUDE_BIN", "C:/fake/claude.exe")
        argv = serve.action_adopter("Trouvaille Z")
        assert argv[0] == "C:/fake/claude.exe"
        assert any('adopte "Trouvaille Z"' in a for a in argv)

    def test_adopter_sans_binaire_rend_none(self, monkeypatch):
        monkeypatch.setattr(serve, "CLAUDE_BIN", None)
        assert serve.action_adopter("X") is None

    def test_les_trois_sont_dedupliquees_et_periment_les_mesures(self):
        for a in ("solder", "adopter", "ecarter-veille"):
            assert a in serve.ACTIONS_DEDUP_PAR_CIBLE
            assert a in serve.ACTIONS_QUI_PERIMENT_LES_MESURES

    def test_do_post_route_les_trois(self):
        source = open(os.path.join(HUB, "scripts", "serve_wiki.py"),
                      encoding="utf-8").read()
        for a in ("solder", "adopter", "ecarter-veille"):
            assert f'action == "{a}"' in source


# --------------------------------------------------------------------------
# 4. ecarter_trouvaille.py : écarter est un fait, tracé deux fois
# --------------------------------------------------------------------------
@pytest.fixture
def veille_et_arbitrages(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SUPERVISION_SKIP_SCAN", "1")
    veille = tmp_path / "veille.json"
    veille.write_text(json.dumps({"entrees": [
        {"titre": "Dev Browser — l'agent vérifie", "url": "https://g/x",
         "statut": "etudie", "pertinence": "instruit", "date": "2026-07-29"},
    ]}, ensure_ascii=False), encoding="utf-8")
    arb = tmp_path / "arbitrages.json"
    arb.write_text(json.dumps({"arbitrages": []}), encoding="utf-8")
    return str(veille), str(arb)


class TestEcarterTrouvaille:
    def test_ecarte_et_trace_les_deux_ecritures(self, veille_et_arbitrages):
        veille, arb = veille_et_arbitrages
        rc = ecarter.main(["Dev Browser — l'agent vérifie", "pytest suffit"],
                          veille_path=veille, arbitrages_path=arb)
        assert rc == 0
        v = json.load(open(veille, encoding="utf-8"))
        assert v["entrees"][0]["statut"] == "ecarte"
        assert "pytest suffit" in v["entrees"][0]["pertinence"]
        a = json.load(open(arb, encoding="utf-8"))
        assert len(a["arbitrages"]) == 1
        assert a["arbitrages"][0]["cible"].startswith("veille:")
        assert a["arbitrages"][0]["decision"].startswith("ECARTE")

    def test_le_slug_ferme_le_constat_au_point_du_jour(self, veille_et_arbitrages,
                                                       monkeypatch):
        """L'écriture n'a de valeur que si point_du_jour cesse de compter la
        trouvaille — et par la TRACE d'arbitrage (slug matché par
        `_veille_arbitree`), pas seulement par le statut : une re-veille qui
        réécrit l'entrée en `etudie` ne doit pas la faire réapparaître."""
        veille, arb = veille_et_arbitrages
        ecarter.main(["Dev Browser — l'agent vérifie", "raison"],
                     veille_path=veille, arbitrages_path=arb)
        v = json.load(open(veille, encoding="utf-8"))
        v["entrees"][0]["statut"] = "etudie"   # simulateur de re-veille
        with open(veille, "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False)
        monkeypatch.setattr(pdj, "VEILLE", veille)
        monkeypatch.setattr(pdj, "ARBITRAGES", arb)
        assert pdj.trouvailles_ouvertes() == []

    def test_titre_inconnu_ne_touche_rien(self, veille_et_arbitrages):
        veille, arb = veille_et_arbitrages
        avant = open(veille, encoding="utf-8").read()
        rc = ecarter.main(["Titre qui n'existe pas"], veille_path=veille,
                          arbitrages_path=arb)
        assert rc == 1
        assert open(veille, encoding="utf-8").read() == avant

    def test_arbitrages_corrompu_bloque_tout(self, veille_et_arbitrages):
        """Même leçon que refuser_arbitrage : corrompu n'est PAS absent."""
        veille, arb = veille_et_arbitrages
        with open(arb, "w", encoding="utf-8") as fh:
            fh.write("{tronqué")
        avant = open(veille, encoding="utf-8").read()
        rc = ecarter.main(["Dev Browser — l'agent vérifie"], veille_path=veille,
                          arbitrages_path=arb)
        assert rc == 2
        assert open(veille, encoding="utf-8").read() == avant, (
            "veille.json ne doit pas être modifié si l'arbitrage ne peut être tracé")


# --------------------------------------------------------------------------
# 5. point_du_jour : pousser des commandes, pas des dénombrements
# --------------------------------------------------------------------------
@pytest.fixture
def pdj_fixture(tmp_path, monkeypatch):
    diag = tmp_path / "diagnostic.json"
    diag.write_text(json.dumps({
        "generated": "2026-08-30",
        "findings": [{"cible": "flotte:exemple", "categorie": "pratique-dev",
                      "titre": "T"}]}), encoding="utf-8")
    veille = tmp_path / "veille.json"
    veille.write_text(json.dumps({"entrees": [
        {"titre": "Trouvaille très âgée", "url": "https://y",
         "statut": "etudie", "date": "2026-07-01", "pertinence": "p"}]},
        ensure_ascii=False), encoding="utf-8")
    arb = tmp_path / "arbitrages.json"
    arb.write_text(json.dumps({"arbitrages": []}), encoding="utf-8")
    monkeypatch.setattr(pdj, "DIAGNOSTIC", str(diag))
    monkeypatch.setattr(pdj, "VEILLE", str(veille))
    monkeypatch.setattr(pdj, "ARBITRAGES", str(arb))


class TestPointDuJourPousse:
    def test_findings_ouverts_rend_cible_et_titre(self, pdj_fixture):
        ouverts = pdj.findings_ouverts()
        assert ouverts[0]["cible"] == "flotte:exemple"
        assert ouverts[0]["titre"] == "T"

    def test_compat_findings_non_arbitres(self, pdj_fixture):
        assert pdj.findings_non_arbitres() == ["flotte:exemple"]

    def test_la_ligne_finding_porte_le_verbe(self, pdj_fixture, capsys):
        pdj.main()
        out = capsys.readouterr().out
        assert "applique flotte:exemple" in out
        assert "refuse flotte:exemple" in out

    def test_la_ligne_veille_porte_le_verbe_et_le_titre(self, pdj_fixture, capsys):
        pdj.main()
        out = capsys.readouterr().out
        assert 'adopte "' in out and 'ecarte "' in out
        assert "Trouvaille tres agee" in out, "titre plié en ASCII, pas omis"

    def test_stdout_reste_ascii_strict(self, pdj_fixture, capsys):
        """cp1252 lève UnicodeDecodeError sur tout caractère hors table
        (incident 2026-07-29) — les titres accentués doivent être pliés."""
        pdj.main()
        capsys.readouterr().out.encode("ascii")


# --------------------------------------------------------------------------
# 6. Playbook : l'étape terminale de commit chez la cible (finding, a)
# --------------------------------------------------------------------------
class TestPlaybookCommitCible:
    CONTENU = open(os.path.join(HUB, ".claude", "orchestration", "playbooks",
                                "evolution-flotte.md"), encoding="utf-8").read()

    def test_le_message_normalise_est_prescrit(self):
        assert "dispositif:" in self.CONTENU

    def test_le_refus_de_commit_devient_un_arbitrage(self):
        assert "flotte:canon-ecrit-jamais-commite" in self.CONTENU
        assert "échéance" in self.CONTENU or "echeance" in self.CONTENU


# --------------------------------------------------------------------------
# 7. wiki_app.js : le câblage des trois actions et la zone unique
# --------------------------------------------------------------------------
class TestCablageJS:
    JS = open(os.path.join(HUB, "docs", "wiki_app.js"), encoding="utf-8").read()

    def test_les_trois_actions_portent_leur_cible(self):
        for a in ("solder", "adopter", "ecarter-veille"):
            assert f'"{a}"' in self.JS

    def test_adopter_demande_confirmation(self):
        i = self.JS.find('"adopter"')
        assert "confirm(" in self.JS[i:i + 900], (
            "Adopter lance un agent qui applique : confirmation explicite, "
            "même règle que Valider (finding wiki:actions-irreversibles)")

    def test_zone_unique_de_rapports(self):
        assert "rapports-decisions" in self.JS
        for zone in ("rapports-agentic", "rapports-veille", "rapports-correctifs",
                     "rapports-deploiement", "rapports-exports"):
            assert zone not in self.JS, f"zone morte restante : {zone}"


class TestUnArbitrageNEnterreQuUneTrouvaille:
    """Défaut `point_du_jour.py:179-181`, audit technique du 2026-09-01.

    `_veille_arbitree` ferme une trouvaille dès que le slug de l'arbitrage est CONTENU
    dans son texte. Le substring est délibéré et documenté — le slug choisi par
    l'humain n'est pas toujours le nom exact du dépôt (`veille:multi-agent-observability`
    pour `claude-code-hooks-multi-agent-observability`). Mais il devient faux dès que
    deux trouvailles partagent une racine : mesuré sur les données réelles,
    `veille:awesome-claude-code` fermait à la fois `hesreallyhim/awesome-claude-code`
    ET `VoltAgent/awesome-claude-code-subagents` — un arbitrage humain en enterrait
    deux, dont un jamais tranché. 1 slug sur 16.

    La désambiguïsation ne peut pas se faire entrée par entrée : c'est
    `trouvailles_ouvertes()`, qui les voit toutes, qui doit n'attribuer un arbitrage
    ambigu qu'à SA meilleure correspondance — celle dont l'identité est la plus proche
    du slug.
    """

    @staticmethod
    def _pdj():
        import importlib.util
        import os as _os
        hub = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        s = importlib.util.spec_from_file_location(
            "point_du_jour_amb", _os.path.join(hub, ".claude", "hooks", "point_du_jour.py"))
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        return m

    ENTREES = [
        {"statut": "nouveau", "titre": "awesome-claude-code",
         "url": "https://github.com/hesreallyhim/awesome-claude-code"},
        {"statut": "nouveau", "titre": "awesome-claude-code-subagents",
         "url": "https://github.com/VoltAgent/awesome-claude-code-subagents"},
    ]
    ARB = [{"cible": "veille:awesome-claude-code", "date": "2026-08-31",
            "decision": "ECARTE : doublon de notre propre catalogue"}]

    def test_les_deux_trouvailles_ne_sont_pas_fermees_par_un_seul_arbitrage(
            self, tmp_path, monkeypatch):
        import json as _json
        pdj = self._pdj()
        veille = tmp_path / "veille.json"
        veille.write_text(_json.dumps({"entrees": self.ENTREES}), encoding="utf-8")
        arbitrages = tmp_path / "arbitrages.json"
        arbitrages.write_text(_json.dumps({"arbitrages": self.ARB}), encoding="utf-8")
        monkeypatch.setattr(pdj, "VEILLE", str(veille))
        monkeypatch.setattr(pdj, "ARBITRAGES", str(arbitrages))
        ouvertes = pdj.trouvailles_ouvertes()
        assert len(ouvertes) == 1, (
            f"un arbitrage a ferme {2 - len(ouvertes)} trouvaille(s) : "
            f"{[e['titre'] for e in ouvertes]}")

    def test_c_est_la_correspondance_la_plus_proche_qui_est_fermee(
            self, tmp_path, monkeypatch):
        """Fermer la mauvaise des deux serait aussi grave que les fermer toutes :
        l'arbitrage `awesome-claude-code` vise le dépôt de ce nom, pas son voisin
        qui l'a seulement pour préfixe."""
        import json as _json
        pdj = self._pdj()
        veille = tmp_path / "veille.json"
        veille.write_text(_json.dumps({"entrees": self.ENTREES}), encoding="utf-8")
        arbitrages = tmp_path / "arbitrages.json"
        arbitrages.write_text(_json.dumps({"arbitrages": self.ARB}), encoding="utf-8")
        monkeypatch.setattr(pdj, "VEILLE", str(veille))
        monkeypatch.setattr(pdj, "ARBITRAGES", str(arbitrages))
        restantes = [e["titre"] for e in pdj.trouvailles_ouvertes()]
        assert restantes == ["awesome-claude-code-subagents"], (
            f"la mauvaise trouvaille a ete fermee : il reste {restantes}")

    def test_un_slug_sans_ambiguite_ferme_toujours(self, tmp_path, monkeypatch):
        """La désambiguïsation ne doit pas rouvrir des arbitrages nets."""
        import json as _json
        pdj = self._pdj()
        veille = tmp_path / "veille.json"
        veille.write_text(_json.dumps({"entrees": [self.ENTREES[1]]}), encoding="utf-8")
        arbitrages = tmp_path / "arbitrages.json"
        arbitrages.write_text(_json.dumps({"arbitrages": [
            {"cible": "veille:awesome-claude-code-subagents", "date": "2026-08-31",
             "decision": "ADOPTE : catalogue de sous-agents"}]}), encoding="utf-8")
        monkeypatch.setattr(pdj, "VEILLE", str(veille))
        monkeypatch.setattr(pdj, "ARBITRAGES", str(arbitrages))
        assert pdj.trouvailles_ouvertes() == []
