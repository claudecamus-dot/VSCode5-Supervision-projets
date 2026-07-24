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
