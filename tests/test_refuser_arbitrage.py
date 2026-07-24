"""Tests de refuser_arbitrage.py — le pendant déterministe du bouton « Invalider »
du wiki (Actions correctives). Exercé en subprocess, chemins surchargés par env,
jamais le vrai arbitrages.json."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude" / "supervision" / "refuser_arbitrage.py"


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

    def test_fichier_corrompu_repart_propre(self, tmp_path):
        p = tmp_path / "arbitrages.json"
        p.write_text("{ pas du json valide", encoding="utf-8")
        result = _run(tmp_path, ["cible-apres-corruption"])
        assert result.returncode == 0
        data = json.loads(p.read_text(encoding="utf-8"))
        assert len(data["arbitrages"]) == 1
