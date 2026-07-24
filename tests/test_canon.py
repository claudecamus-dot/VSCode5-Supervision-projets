"""Tests de non-régression du CANON du dispositif de supervision.

Le canon (`.claude/dispositif/canon/`) est propagé aux 6 projets par
`sync_dispositif.py` : un bug du canon se propage donc partout. Ces tests couvrent
le chemin critique partagé — la dette « chemin critique sans test » du re-audit VScode5
(2026-07-24), amplifiée par le partage. Ils testent la SOURCE (le canon), pas les copies.

Lancer : py -m pytest tests/ -q   (depuis la racine du hub)
"""

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
