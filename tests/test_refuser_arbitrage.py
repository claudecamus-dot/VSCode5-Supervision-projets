"""Tests de refuser_arbitrage.py — le pendant déterministe du bouton « Invalider »
du wiki (Actions correctives). Exercé en subprocess, chemins surchargés par env,
jamais le vrai arbitrages.json."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "supervision" / "refuser_arbitrage.py"
# Le VRAI arbitrages.json n'est JAMAIS ecrit : on en copie les octets dans tmp_path pour
# reproduire une troncature sur un contenu realiste.
REEL = Path(__file__).resolve().parents[1] / ".claude" / "supervision" / "arbitrages.json"


def _charger_module():
    """Charge refuser_arbitrage.py par chemin (executable autonome, pas un package)."""
    spec = importlib.util.spec_from_file_location("refuser_arbitrage_test", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    sys.modules["refuser_arbitrage_test"] = module
    spec.loader.exec_module(module)
    return module


def _run(tmp_path, args):
    env = dict(
        os.environ,
        AGENT_SUPERVISION_ARBITRAGES=str(tmp_path / "arbitrages.json"),
        AGENT_SUPERVISION_SKIP_SCAN="1",
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env=env, capture_output=True, text=True, timeout=30,
    )


class TestRefuserArbitrage:
    def test_sans_fichier_existant_le_cree(self, tmp_path):
        result = _run(tmp_path, ["VSCode :: revue-increment — test"])
        assert result.returncode == 0
        data = json.loads((tmp_path / "arbitrages.json").read_text(encoding="utf-8"))
        assert len(data["arbitrages"]) == 1
        entry = data["arbitrages"][0]
        assert entry["cible"] == "VSCode :: revue-increment — test"
        assert entry["decision"].startswith("REFUSÉ :")
        assert "sans raison précisée" in entry["decision"]

    def test_avec_raison_explicite(self, tmp_path):
        result = _run(tmp_path, ["famille:linter", "peu de code, hors périmètre"])
        assert result.returncode == 0
        data = json.loads((tmp_path / "arbitrages.json").read_text(encoding="utf-8"))
        assert data["arbitrages"][0]["decision"] == "REFUSÉ : peu de code, hors périmètre"

    def test_append_ne_jamais_ecraser(self, tmp_path):
        p = tmp_path / "arbitrages.json"
        p.write_text(json.dumps({"arbitrages": [
            {"cible": "existant", "date": "2026-01-01", "decision": "ACCEPTÉ"}
        ]}), encoding="utf-8")
        _run(tmp_path, ["nouvelle-cible"])
        data = json.loads(p.read_text(encoding="utf-8"))
        assert len(data["arbitrages"]) == 2
        assert data["arbitrages"][0]["cible"] == "existant"
        assert data["arbitrages"][1]["cible"] == "nouvelle-cible"

    def test_cible_vide_rejetee(self, tmp_path):
        result = _run(tmp_path, [""])
        assert result.returncode == 1
        assert not (tmp_path / "arbitrages.json").exists()

    def test_sans_argument_rejete(self, tmp_path):
        result = _run(tmp_path, [])
        assert result.returncode == 1

    def test_fichier_illisible_abandonne_sans_rien_ecrire(self, tmp_path):
        """Corruption != absence. Le fichier reel (94 arbitrages, ~108 Ko) tronque a
        400 o etait silencieusement remplace par un fichier a UNE entree, exit 0 :
        la memoire d'arbitrage du projet (R4) disparaissait sans un mot."""
        p = tmp_path / "arbitrages.json"
        tronque = REEL.read_bytes()[:400]          # copie du vrai fichier, jamais le vrai
        p.write_bytes(tronque)
        result = _run(tmp_path, ["cible-apres-corruption"])
        assert result.returncode != 0, (
            "un arbitrages.json illisible doit faire ABANDONNER, pas repartir de zero")
        assert p.read_bytes() == tronque, "rien ne doit avoir ete ecrit"
        assert not (tmp_path / "arbitrages.json.tmp").exists()
        message = (result.stdout + result.stderr).lower()
        assert "illisible" in message or "abandon" in message, (
            f"le refus doit etre explicite, sortie : {result.stdout + result.stderr!r}")

    def test_json_valide_mais_de_mauvaise_forme_abandonne(self, tmp_path):
        p = tmp_path / "arbitrages.json"
        p.write_text('["pas un objet"]', encoding="utf-8")
        result = _run(tmp_path, ["cible"])
        assert result.returncode != 0
        assert p.read_text(encoding="utf-8") == '["pas un objet"]'
        message = (result.stdout + result.stderr).lower()
        assert "illisible" in message or "abandon" in message, (
            "refus explicite attendu, pas un traceback : "
            f"{result.stdout + result.stderr!r}")

    def test_ecriture_atomique_une_coupure_ne_tronque_pas(self, tmp_path, monkeypatch):
        """Meme motif que canon/log_run.solder : temporaire + os.replace. Un "w" direct
        sur les 108 Ko du fichier reel le tronque si l'ecriture est interrompue."""
        ra = _charger_module()
        p = tmp_path / "arbitrages.json"
        avant = json.dumps({"arbitrages": [
            {"cible": "existant", "date": "2026-01-01", "decision": "ACCEPTE"}]},
            ensure_ascii=False, indent=2)
        p.write_text(avant, encoding="utf-8")
        ra.ARBITRAGES_PATH = str(p)

        def dump_qui_casse(*a, **k):
            raise RuntimeError("coupure simulee pendant l'ecriture")

        monkeypatch.setattr(ra.json, "dump", dump_qui_casse)
        with pytest.raises(RuntimeError):
            ra.main(["cible-pendant-coupure"])
        assert p.read_text(encoding="utf-8") == avant, (
            "une ecriture interrompue ne doit jamais tronquer arbitrages.json")
