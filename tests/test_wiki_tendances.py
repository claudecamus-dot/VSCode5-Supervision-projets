"""Non-régression de l'incrément 5 (Tendances) de
docs/reflexions/ameliorations-supervision.md (2026-07-23), resté 7 jours sans
suite et reversé en finding wiki:tendances-wiki du diagnostic 2026-07-30.

HISTORY_PATH est monkeypatché vers un fichier jetable — jamais le vrai
docs/wiki/history/snapshots.jsonl de production.
"""

import importlib.util
import json
import os

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


@pytest.fixture
def history(tmp_path, monkeypatch):
    chemin = tmp_path / "history" / "snapshots.jsonl"
    monkeypatch.setattr(scan, "HISTORY_PATH", str(chemin))
    return chemin


class TestSnapshot:
    def test_absent_rend_none_sans_planter(self, history):
        assert scan.charger_dernier_snapshot() is None

    def test_fichier_corrompu_rend_none_sans_planter(self, history):
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text("pas du json\n", encoding="utf-8")
        assert scan.charger_dernier_snapshot() is None

    def test_ecrit_puis_relit_la_derniere_ligne(self, history):
        scan.ecrire_snapshot({"ts": "t1", "nb_findings": 3})
        scan.ecrire_snapshot({"ts": "t2", "nb_findings": 5})
        assert scan.charger_dernier_snapshot() == {"ts": "t2", "nb_findings": 5}
        # une ligne par appel, jamais réécrit en place
        assert len(history.read_text(encoding="utf-8").strip().splitlines()) == 2

    def test_snapshot_actuel_capture_les_compteurs_et_les_alertes(self):
        projects = [
            {"existe": True, "nom": "VSCode1", "alerte": None},
            {"existe": True, "nom": "VSCode2", "alerte": "majeur"},
            {"existe": False, "nom": "Fantome", "alerte": "critique"},
        ]
        pil = {"nb_projets": 2, "en_alerte": [projects[1]], "nb_pratiques_ecart": 4,
               "nb_findings": 5, "runs_a_solder": [], "retards": ["x"]}
        snap = scan.snapshot_actuel(projects, pil, "2026-07-30 10:00")
        assert snap["alertes"] == {"VSCode1": None, "VSCode2": "majeur"}
        assert snap["nb_findings"] == 5
        assert snap["nb_retards"] == 1


class TestDeltas:
    def test_sans_precedent_rend_none(self):
        assert scan.calcule_tendances({"nb_findings": 5}, None) is None

    def test_calcule_les_deltas_signes(self):
        precedent = {"ts": "hier", "nb_en_alerte": 1, "nb_pratiques_ecart": 4,
                     "nb_findings": 5, "nb_runs_a_solder": 0, "nb_retards": 2,
                     "alertes": {}}
        actuel = {"nb_en_alerte": 2, "nb_pratiques_ecart": 4, "nb_findings": 3,
                  "nb_runs_a_solder": 1, "nb_retards": 0, "alertes": {}}
        tend = scan.calcule_tendances(actuel, precedent)
        assert tend["depuis"] == "hier"
        assert tend["deltas"] == {"nb_en_alerte": 1, "nb_pratiques_ecart": 0,
                                   "nb_findings": -2, "nb_runs_a_solder": 1,
                                   "nb_retards": -2}

    def test_detecte_les_transitions_d_alerte(self):
        # l'exemple même de la réflexion d'origine : « alerte VSCode2 critique->majeur »
        precedent = {"ts": "hier", "nb_en_alerte": 0, "nb_pratiques_ecart": 0,
                     "nb_findings": 0, "nb_runs_a_solder": 0, "nb_retards": 0,
                     "alertes": {"VSCode2": "critique", "VSCode1": None}}
        actuel = {"nb_en_alerte": 0, "nb_pratiques_ecart": 0, "nb_findings": 0,
                  "nb_runs_a_solder": 0, "nb_retards": 0,
                  "alertes": {"VSCode2": "majeur", "VSCode1": None}}
        tend = scan.calcule_tendances(actuel, precedent)
        assert tend["transitions"] == [("VSCode2", "critique", "majeur")]

    def test_projet_nouvellement_scanne_n_est_pas_une_fausse_transition(self):
        precedent = {"ts": "hier", "nb_en_alerte": 0, "nb_pratiques_ecart": 0,
                     "nb_findings": 0, "nb_runs_a_solder": 0, "nb_retards": 0,
                     "alertes": {}}
        actuel = {"nb_en_alerte": 0, "nb_pratiques_ecart": 0, "nb_findings": 0,
                  "nb_runs_a_solder": 0, "nb_retards": 0,
                  "alertes": {"VSCode6": None}}
        # None -> None (jamais alerté avant, jamais alerté après) : pas de transition
        tend = scan.calcule_tendances(actuel, precedent)
        assert tend["transitions"] == []


class TestRenduDelta:
    def test_zero_ou_none_rend_vide(self):
        assert scan.rendu_delta(0) == ""
        assert scan.rendu_delta(None) == ""

    def test_positif_rend_hausse(self):
        assert "delta-hausse" in scan.rendu_delta(3)
        assert "▲3" in scan.rendu_delta(3)

    def test_negatif_rend_baisse_en_valeur_absolue(self):
        assert "delta-baisse" in scan.rendu_delta(-2)
        assert "▼2" in scan.rendu_delta(-2)
