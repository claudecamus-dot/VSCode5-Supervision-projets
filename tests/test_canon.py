"""Tests de non-régression du CANON du dispositif de supervision.

Le canon (`.claude/dispositif/canon/`) est propagé aux 6 projets par
`sync_dispositif.py` : un bug du canon se propage donc partout. Ces tests couvrent
le chemin critique partagé — la dette « chemin critique sans test » du re-audit VScode5
(2026-07-24), amplifiée par le partage. Ils testent la SOURCE (le canon), pas les copies.

Lancer : py -m pytest tests/ -q   (depuis la racine du hub)
"""

import datetime as dt
import importlib.util
import os

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(HUB, ".claude", "dispositif", "canon")
DISPOSITIF = os.path.join(HUB, ".claude", "dispositif")


def _load(nom, chemin):
    """Charge un module depuis un fichier (les modules du canon ne sont pas un package)."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


log_run = _load("canon_log_run", os.path.join(CANON, "log_run.py"))
scan = _load("canon_scan_transcripts", os.path.join(CANON, "scan_transcripts.py"))
sync = _load("dispositif_sync", os.path.join(DISPOSITIF, "sync_dispositif.py"))


# --- finding_arbitre : enrichissement B (arbitrage par catégorie, ex-VSCode3) --------
class TestFindingArbitre:
    def test_sans_arbitrage_pas_ferme(self):
        f = {"cible": "famille:linter", "categorie": "pratique-dev"}
        assert scan.finding_arbitre(f, []) is False
        assert scan.finding_arbitre(f, None) is False

    def test_arbitrage_sans_categories_ferme_tout(self):
        # rétro-compatibilité : un arbitrage historique (sans champ categories) ferme tout
        f = {"cible": "famille:linter", "categorie": "pratique-dev"}
        arbs = [{"cible": "famille:linter", "decision": "ACCEPTE"}]
        assert scan.finding_arbitre(f, arbs) is True

    def test_categorie_couverte_ferme(self):
        f = {"cible": "revue-increment", "categorie": "verification-manquante"}
        arbs = [{"cible": "revue-increment", "categories": ["verification-manquante"]}]
        assert scan.finding_arbitre(f, arbs) is True

    def test_categorie_non_couverte_ne_ferme_pas(self):
        # le cœur de l'enrichissement : un arbitrage de routage ne masque plus un
        # constat de qualité sur la même cible
        f = {"cible": "ppt-designer", "categorie": "verification-manquante"}
        arbs = [{"cible": "ppt-designer", "categories": ["agent-mort"]}]
        assert scan.finding_arbitre(f, arbs) is False

    def test_cible_differente_ne_ferme_pas(self):
        f = {"cible": "famille:linter", "categorie": "pratique-dev"}
        arbs = [{"cible": "famille:revue-code"}]
        assert scan.finding_arbitre(f, arbs) is False

    def test_finding_sans_cible_faux(self):
        assert scan.finding_arbitre({"categorie": "x"}, [{"cible": "x"}]) is False


# --- categories_inconnues : arrivée par le rapatriement du 2026-07-28 (améliorations
# nées dans VSCode2). Le contrôle a crié « hors vocabulaire » dès le premier scan du hub
# sur les 5 catégories `pratique-*`, absentes de sa liste — un garde-fou qui hurle à tort
# finit ignoré. Ces tests verrouillent le miroir avec write_diagnostic.py.
class TestCategoriesConnues:
    def test_miroir_de_write_diagnostic(self):
        wd = _load(
            "canon_write_diagnostic",
            os.path.join(os.path.dirname(CANON), "..", "supervision", "write_diagnostic.py"),
        )
        assert set(scan.CATEGORIES_CONNUES) == set(wd.CATEGORIES), (
            "toute catégorie écrivable dans un diagnostic doit être fermable par un arbitrage"
        )

    def test_categories_du_volet_2_acceptees(self):
        arbs = [{"cible": "VScode5", "categories": ["pratique-test", "pratique-produit"]}]
        assert scan.categories_inconnues(arbs) == []

    def test_faute_de_frappe_signalee(self):
        arbs = [{"cible": "x", "categories": ["verification_manquante"]}]
        assert scan.categories_inconnues(arbs) == ["verification_manquante"]


# --- agents_apparus : finding agents:types-non-charges-en-session (2026-07-30) -------
# Le registre des types d'agents est chargé au DÉMARRAGE de session : un sous-agent
# écrit en cours de séance n'est pas adressable tout de suite, et rien ne disait quand
# il le devenait. Le hook l'annonce désormais — donc il doit annoncer JUSTE.
class TestAgentsApparus:
    @pytest.fixture(autouse=True)
    def _repo_isole(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scan, "REPO", str(tmp_path))
        self.repo = tmp_path
        self.agents = tmp_path / ".claude" / "agents"

    def _poser(self, *noms):
        self.agents.mkdir(parents=True, exist_ok=True)
        for n in noms:
            (self.agents / f"{n}.md").write_text("---\nname: x\n---\n", encoding="utf-8")

    def test_premier_passage_enregistre_sans_rien_annoncer(self):
        """Sinon TOUS les agents déjà en place seraient annoncés comme neufs au
        premier démarrage suivant la mise à jour du hook."""
        self._poser("bmad-revue", "veille-agentic")
        state = {}
        assert scan.agents_apparus(state) == []
        assert state["agents_connus"] == ["bmad-revue", "veille-agentic"]

    def test_annonce_uniquement_le_nouveau(self):
        self._poser("bmad-revue", "veille-agentic")
        state = {"agents_connus": ["bmad-revue"]}
        assert scan.agents_apparus(state) == ["veille-agentic"]

    def test_rien_de_neuf_ne_dit_rien(self):
        self._poser("bmad-revue")
        state = {"agents_connus": ["bmad-revue"]}
        assert scan.agents_apparus(state) == []

    def test_un_agent_supprime_disparait_de_l_etat_sans_etre_annonce(self):
        self._poser("bmad-revue")
        state = {"agents_connus": ["bmad-revue", "agent-retire"]}
        assert scan.agents_apparus(state) == []
        assert state["agents_connus"] == ["bmad-revue"]

    def test_dossier_absent_fail_open(self):
        """Ce script ne bloque JAMAIS un démarrage de session : pas de dossier
        .claude/agents (cas de la majorité des projets) = aucune annonce, aucune erreur."""
        state = {}
        assert scan.agents_apparus(state) == []
        assert state["agents_connus"] == []


# --- non_invocation_skills : enrichissement A (ex-VSCode1) — a cassé DEUX fois la
# suite (VSCode2 puis VSCode3, même jour, même fix) faute d'un test dédié. Comble
# l'angle mort exact : finding_arbitre (ci-dessus) était testée, celle-ci non.
class TestNonInvocationSkills:
    @pytest.fixture(autouse=True)
    def _repo_isole(self, tmp_path, monkeypatch):
        """REPO et le cache mémoïsé _agents_text pointent vers un dépôt jetable —
        jamais le vrai hub, jamais de collision avec les vraies skills du poste."""
        monkeypatch.setattr(scan, "REPO", str(tmp_path))
        monkeypatch.setattr(scan, "_AGENTS_TEXT", None)
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "faux-home"))
        self.repo = tmp_path

    def _skill_avec_scripts(self, nom):
        d = self.repo / ".claude" / "skills" / nom / "scripts"
        d.mkdir(parents=True)
        (d / "outil.py").write_text("# lib", encoding="utf-8")

    def _agent_citant(self, contenu):
        d = self.repo / ".claude" / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "sous-agent.md").write_text(contenu, encoding="utf-8")

    def test_skill_avec_scripts_exclue_de_jamais_utilises(self):
        self._skill_avec_scripts("pptx-framed-image")
        out = scan.non_invocation_skills({"pptx-framed-image": "projet"})
        assert out == {"pptx-framed-image"}

    def test_skill_citee_par_chemin_dans_un_agent_exclue(self):
        self._agent_citant("Skills you rely on: skills/ppt-designer pour le rendu.")
        out = scan.non_invocation_skills({"ppt-designer": "projet"})
        assert out == {"ppt-designer"}

    def test_skill_sans_scripts_ni_citation_reste_jamais_utilisee(self):
        # LE CAS QUI A CASSÉ EN PRODUCTION : une skill "bibliothèque de référence"
        # ordinaire (pas de scripts/, jamais citée par chemin) doit rester un vrai
        # "jamais utilisé" — ne pas la faire disparaître par excès de prudence.
        out = scan.non_invocation_skills({"priority-matrix": "projet"})
        assert out == set()

    def test_simple_mention_du_nom_sans_chemin_ne_suffit_pas(self):
        # Le docstring de la fonction met en garde explicitement contre ce piège :
        # un skill juste *nommé* en prose (sans "skills/" devant) reste jamais-utilisé.
        self._agent_citant("Ce sous-agent travaille dans le sillage de agent-orchestrator.")
        out = scan.non_invocation_skills({"agent-orchestrator": "projet"})
        assert out == set()

    def test_famille_bmad_toujours_ignoree(self):
        # Même avec scripts/ ET une citation par chemin, une skill BMAD est sautée —
        # son tri suit une logique séparée (famille:BMAD dans arbitrages.json).
        self._skill_avec_scripts("bmad-quelconque")
        self._agent_citant("skills/bmad-quelconque")
        out = scan.non_invocation_skills({"bmad-quelconque": "BMAD"})
        assert out == set()

    def test_regex_ne_deborde_pas_sur_un_nom_prefixe(self):
        # "skills/priority-matrix-v2" ne doit PAS faire matcher "priority-matrix" —
        # la frontière (?![\\w-]) de la regex existe précisément pour ça.
        self._agent_citant("Voir skills/priority-matrix-v2 pour la v2.")
        out = scan.non_invocation_skills({"priority-matrix": "projet"})
        assert out == set()

    def test_plusieurs_skills_mixtes(self):
        self._skill_avec_scripts("slide-text-polish")
        self._agent_citant("skills/ppt-designer est la voie unique deck.")
        out = scan.non_invocation_skills({
            "slide-text-polish": "projet",
            "ppt-designer": "projet",
            "deck-design-library": "projet",
        })
        assert out == {"slide-text-polish", "ppt-designer"}


# --- skills_reference.json : déclaration par ARBITRAGE (finding agent-mort 2026-07-27)
# Une skill réellement utilisée mais invisible du compteur (consommée par lecture
# depuis les projets cibles, ou exécutée inline comme veille-agentic) passait pour
# « jamais utilisée ». La déclaration arbitrée la bascule en bibliothèque/référence.
class TestSkillsReferenceDeclares:
    @pytest.fixture(autouse=True)
    def _repo_isole(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scan, "REPO", str(tmp_path))
        monkeypatch.setattr(scan, "_AGENTS_TEXT", None)
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "faux-home"))
        self.repo = tmp_path

    def _declare(self, contenu):
        d = self.repo / ".claude" / "supervision"
        d.mkdir(parents=True, exist_ok=True)
        (d / "skills_reference.json").write_text(contenu, encoding="utf-8")

    def test_skill_declaree_bascule_en_reference(self):
        # LE CAS DU FINDING : veille-agentic a tourné (artefact veille.json daté)
        # mais n=0 au compteur — déclarée, elle sort de « jamais utilisées ».
        self._declare('{"skills": ["veille-agentic"]}')
        out = scan.non_invocation_skills({"veille-agentic": "projet"})
        assert out == {"veille-agentic"}

    def test_liste_nue_acceptee(self):
        self._declare('["deck-design-library"]')
        out = scan.non_invocation_skills({"deck-design-library": "global"})
        assert out == {"deck-design-library"}

    def test_fichier_absent_fail_open(self):
        assert scan.skills_reference_declares() == set()
        out = scan.non_invocation_skills({"veille-agentic": "projet"})
        assert out == set()

    def test_json_invalide_fail_open(self):
        self._declare("{pas du json")
        assert scan.skills_reference_declares() == set()

    def test_declaration_ne_couvre_pas_les_bmad(self):
        # La famille BMAD garde sa logique de tri séparée, déclaration ou pas.
        self._declare('{"skills": ["bmad-quelconque"]}')
        out = scan.non_invocation_skills({"bmad-quelconque": "BMAD"})
        assert out == set()

    def test_skill_non_declaree_reste_jamais_utilisee(self):
        self._declare('{"skills": ["veille-agentic"]}')
        out = scan.non_invocation_skills({"priority-matrix": "projet"})
        assert out == set()


# --- log_run : garde-fou de validation utilisateur ----------------------------------
class TestAvertissementValidation:
    def test_livrable_utilisateur_succes_sans_validation_avertit(self, capsys):
        log_run.avertir_validation_utilisateur(
            {"resultat": "succes", "demande": "export du deck", "notes": ""})
        assert "AVERTISSEMENT" in capsys.readouterr().out

    def test_avec_mention_validation_silencieux(self, capsys):
        log_run.avertir_validation_utilisateur(
            {"resultat": "succes", "demande": "export du deck",
             "notes": "valide par l'utilisateur"})
        assert capsys.readouterr().out == ""

    def test_non_succes_silencieux(self, capsys):
        log_run.avertir_validation_utilisateur(
            {"resultat": "en-attente-validation", "demande": "export du deck"})
        assert capsys.readouterr().out == ""

    def test_sans_livrable_utilisateur_silencieux(self, capsys):
        log_run.avertir_validation_utilisateur(
            {"resultat": "succes", "demande": "refacto interne", "notes": ""})
        assert capsys.readouterr().out == ""


class TestRunsASolder:
    """Visibilité des runs en-attente-validation (constat interaction VSCode2
    2026-07-29 : 2 runs oubliés 4 j et 1 j, soldés seulement sur relance)."""

    def _run(self, ts, resultat="en-attente-validation"):
        return {"ts": ts, "resultat": resultat, "demande": "livrable X"}

    def test_run_vieux_est_signale_avec_son_age(self):
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        ouverts = scan.runs_a_solder(
            [self._run("2026-07-27T12:00:00+00:00")], maintenant)
        assert len(ouverts) == 1 and ouverts[0]["heures"] == 48

    def test_run_recent_sous_le_seuil_ignore(self):
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        assert scan.runs_a_solder([self._run("2026-07-29T06:00:00+00:00")], maintenant) == []

    def test_seuls_les_en_attente_comptent(self):
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        runs = [self._run("2026-07-20T12:00:00+00:00", "succes"),
                self._run("2026-07-20T12:00:00+00:00", "en-cours")]
        assert scan.runs_a_solder(runs, maintenant) == []

    def test_tries_du_plus_vieux_au_plus_recent(self):
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        ouverts = scan.runs_a_solder([self._run("2026-07-28T00:00:00+00:00"),
                                      self._run("2026-07-25T00:00:00+00:00")], maintenant)
        assert [o["heures"] for o in ouverts] == [108, 36]

    def test_ts_illisible_ignore_sans_casser(self):
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        assert scan.runs_a_solder([self._run("pas une date")], maintenant) == []

    def test_demande_hors_cp1252_rendue_imprimable(self):
        # Le journal RÉEL porte déjà un U+FFFD (mojibake hérité) : sans garde, la
        # ligne imprimée casserait stdout capturé en cp1252 par les tests des
        # projets cibles — l'incident même que ce signal documente.
        maintenant = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.UTC)
        run = {"ts": "2026-07-25T12:00:00+00:00", "resultat": "en-attente-validation",
               "demande": "Cadrage produit � why — livrable é"}
        ouverts = scan.runs_a_solder([run], maintenant)
        assert len(ouverts) == 1
        ouverts[0]["demande"].encode("cp1252")  # ne doit jamais lever
        assert "�" not in ouverts[0]["demande"]


class TestArbreSale:
    """Reliquat non commité affiché au démarrage (constat ko-repete VSCode2
    2026-07-29 : séance close sur du code produit jamais commité)."""

    def test_les_donnees_generees_du_scan_sont_exclues(self, monkeypatch):
        sortie = (" M docs/wiki/index.md\n"
                  " M .claude/supervision/state.json\n"
                  " M .claude/orchestration/runs.jsonl\n"
                  " M app/services/extract.py\n"
                  "?? tests/test_neuf.py\n")

        class _Res:
            returncode = 0
            stdout = sortie

        monkeypatch.setattr(scan.subprocess, "run", lambda *a, **k: _Res())
        assert scan.arbre_sale() == ["app/services/extract.py", "tests/test_neuf.py"]

    def test_git_en_echec_ne_leve_rien(self, monkeypatch):
        class _Res:
            returncode = 128
            stdout = ""

        monkeypatch.setattr(scan.subprocess, "run", lambda *a, **k: _Res())
        assert scan.arbre_sale() == []

    def test_git_absent_fail_open(self, monkeypatch):
        def _boom(*a, **k):
            raise OSError("git introuvable")

        monkeypatch.setattr(scan.subprocess, "run", _boom)
        assert scan.arbre_sale() == []

    def test_chemin_accentue_reste_imprimable_en_cp1252(self, monkeypatch):
        class _Res:
            returncode = 0
            stdout = " M app/données/été.py\n"

        monkeypatch.setattr(scan.subprocess, "run", lambda *a, **k: _Res())
        for chemin in scan.arbre_sale():
            chemin.encode("cp1252")  # ne doit jamais lever


class TestAvertissementRevueIncrement:
    """Finding playbook:evolution-flotte 2026-07-29 : un run orchestré 'succes'
    doit porter une étape terminale revue-increment (ou sa trace dans notes)."""

    def test_succes_orchestre_sans_revue_avertit(self, capsys):
        log_run.avertir_revue_increment(
            {"resultat": "succes", "qualification": "orchestre",
             "plan": [{"etape": "modification", "agent": "session"}], "notes": ""})
        assert "revue-increment" in capsys.readouterr().out

    def test_etape_revue_au_plan_silencieux(self, capsys):
        log_run.avertir_revue_increment(
            {"resultat": "succes", "qualification": "orchestre",
             "plan": [{"etape": "modification", "agent": "session"},
                      {"etape": "revue-increment terminale", "agent": "skill revue-increment"}],
             "notes": ""})
        assert capsys.readouterr().out == ""

    def test_trace_dans_notes_silencieux(self, capsys):
        # Revue de campagne : un seul passage couvre plusieurs runs de la séance.
        log_run.avertir_revue_increment(
            {"resultat": "succes", "qualification": "orchestre", "plan": [],
             "notes": "revue-increment de campagne jouee en fin de seance"})
        assert capsys.readouterr().out == ""

    def test_non_succes_silencieux(self, capsys):
        log_run.avertir_revue_increment(
            {"resultat": "en-cours", "qualification": "orchestre", "plan": []})
        assert capsys.readouterr().out == ""

    def test_direct_signale_silencieux(self, capsys):
        log_run.avertir_revue_increment(
            {"resultat": "succes", "qualification": "direct-signale", "plan": []})
        assert capsys.readouterr().out == ""


# --- log_run : append (main) et requalification (--solde) ----------------------------
@pytest.fixture
def runs_tmp(tmp_path, monkeypatch):
    """Redirige RUNS_PATH du module vers un journal jetable."""
    p = tmp_path / "runs.jsonl"
    monkeypatch.setattr(log_run, "RUNS_PATH", str(p))
    return p


def _lignes(p):
    import json
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


class TestLogRunMain:
    def test_append_run_valide(self, runs_tmp):
        code = log_run.main(['{"demande": "x", "qualification": "orchestre"}'])
        assert code == 0
        runs = _lignes(runs_tmp)
        assert len(runs) == 1 and runs[0]["demande"] == "x"
        assert "ts" in runs[0]  # ts ajouté d'office

    def test_champ_requis_manquant_rejete(self, runs_tmp):
        assert log_run.main(['{"demande": "x"}']) == 1
        assert not runs_tmp.exists()

    def test_qualification_invalide_rejete(self, runs_tmp):
        assert log_run.main(['{"demande": "x", "qualification": "n_importe_quoi"}']) == 1


class TestSolder:
    def _seed(self, p):
        p.write_text(
            '{"ts": "2026-07-24T10:00:00", "demande": "a", "qualification": "orchestre", "resultat": "en-attente-validation"}\n'
            '{"ts": "2026-07-24T11:30:00", "demande": "b", "qualification": "orchestre", "resultat": "en-attente-validation"}\n',
            encoding="utf-8")

    def test_solde_requalifie_le_bon_run(self, runs_tmp):
        self._seed(runs_tmp)
        code = log_run.solder(["2026-07-24T10", "succes", "OK"])
        assert code == 0
        runs = _lignes(runs_tmp)
        cible = next(r for r in runs if r["ts"].startswith("2026-07-24T10"))
        autre = next(r for r in runs if r["ts"].startswith("2026-07-24T11"))
        assert cible["resultat"] == "succes" and "solde" in cible["notes"] and "OK" in cible["notes"]
        assert autre["resultat"] == "en-attente-validation"  # l'autre run intact

    def test_prefixe_ambigu_rejete_sans_ecrire(self, runs_tmp):
        self._seed(runs_tmp)
        assert log_run.solder(["2026-07-24T", "succes"]) == 1  # matche les 2
        assert all(r["resultat"] == "en-attente-validation" for r in _lignes(runs_tmp))

    def test_prefixe_absent_rejete(self, runs_tmp):
        self._seed(runs_tmp)
        assert log_run.solder(["1999-01-01", "succes"]) == 1

    def test_resultat_invalide_rejete(self, runs_tmp):
        self._seed(runs_tmp)
        assert log_run.solder(["2026-07-24T10", "pas_un_statut"]) == 1


# --- sync_dispositif : en-tête généré et normalisation -------------------------------
class TestSuitesCibles:
    """Rappel des suites à rejouer après un sync (incident sync-canon
    2026-07-29 : le canon synchronise les SCRIPTS, jamais les tests locaux —
    un sync « 12/12 à jour » ne dit rien de leur santé)."""

    def test_detecte_les_tests_qui_exercent_un_script_du_canon(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_orchestration.py").write_text(
            "from log_run import main\n", encoding="utf-8")
        (tmp_path / "tests" / "test_metier.py").write_text(
            "def test_rien(): pass\n", encoding="utf-8")
        assert sync.suites_cibles(str(tmp_path)) == ["tests/test_orchestration.py"]

    def test_projet_sans_repertoire_tests(self, tmp_path):
        assert sync.suites_cibles(str(tmp_path)) == []

    def test_seuls_les_fichiers_test_sont_lus(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "conftest.py").write_text(
            "import scan_transcripts\n", encoding="utf-8")
        assert sync.suites_cibles(str(tmp_path)) == []

    def test_rappel_silencieux_si_aucune_suite(self, tmp_path, capsys):
        sync.rappel_suites_cibles([{"nom": "X", "chemin": str(tmp_path)}])
        assert capsys.readouterr().out == ""

    def test_rappel_liste_la_commande_par_projet(self, tmp_path, capsys):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text(
            "import scan_transcripts\n", encoding="utf-8")
        sync.rappel_suites_cibles([{"nom": "X", "chemin": str(tmp_path)}])
        sortie = capsys.readouterr().out
        assert "REJOUER" in sortie and "pytest tests/test_a.py" in sortie


class TestSyncHelpers:
    def test_build_content_porte_len_tete(self):
        contenu = sync.build_content("log_run.py")
        assert "GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT" in contenu
        assert "log_run.py" in contenu

    def test_strip_header_round_trip(self):
        # strip_header(build_content) doit rendre EXACTEMENT le corps du canon
        corps_canon = sync.read_lf(os.path.join(CANON, "log_run.py"))
        assert sync.strip_header(sync.build_content("log_run.py")) == corps_canon

    def test_strip_header_sans_en_tete_inchange(self):
        texte = "print('hello')\n"
        assert sync.strip_header(texte) == texte

    def test_read_lf_normalise_crlf(self, tmp_path):
        p = tmp_path / "f.py"
        p.write_bytes(b"a\r\nb\r\nc")
        assert sync.read_lf(str(p)) == "a\nb\nc"
