"""Tests des garde-fous d'ECRITURE du dispositif, pour des defauts REPRODUITS
(revue 2026-08-31) :

Correctif 2 -- guard_destructive_git.py se contournait par la forme d'invocation
native de Windows : le test `lower[start] != "git"` exigeait le token litteral
`git`, donc `git.exe push --force`, `/usr/bin/git push --force`,
`(git push --force)` et `eval "git push --force"` passaient sans deny.

Correctif 3 -- log_usage.py ne reconfigurait pas stdin en UTF-8 : sur une console
Windows (cp1252) un quart du journal d'usage est parti en mojibake (57 lignes sur
233 mesurees), et un UnicodeDecodeError (sous-classe de ValueError) etait avale
par le `except` -- invocation perdue en silence, etage 1 qui sous-compte.

Correctif 4 -- canon/log_run.py ne validait pas `resultat` a l'append alors que
`--solde` le fait : `"succes"` accentue ou `"nimportequoi"` passaient en exit 0 et
faussaient ensuite le taux de reussite.

Correctif 5 -- canon/log_run.py --solde plantait en TypeError sur un run dont
`demande` vaut null, precisement dans la branche qui doit lister les candidats.

Aucun test ne touche aux fichiers reels du depot (arbitrages.json, usage.jsonl,
runs.jsonl) : tout passe par tmp_path ou une variable d'environnement.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
GUARD = RACINE / ".claude" / "hooks" / "guard_destructive_git.py"
LOG_USAGE = RACINE / ".claude" / "supervision" / "log_usage.py"
LOG_RUN_CANON = RACINE / ".claude" / "dispositif" / "canon" / "log_run.py"


def _charger(chemin: Path, nom: str):
    spec = importlib.util.spec_from_file_location(nom, str(chemin))
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


# --- Correctif 2 : reconnaissance du binaire git dans le hook PreToolUse -------------
def _rejouer_hook(commande: str) -> str:
    """Rejoue le hook avec un payload PreToolUse REEL et rend sa sortie brute."""
    payload = json.dumps({
        "session_id": "test", "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": commande},
    })
    r = subprocess.run([sys.executable, str(GUARD)], input=payload,
                       capture_output=True, text=True, timeout=30)
    return r.stdout


def _deny(commande: str) -> bool:
    sortie = _rejouer_hook(commande)
    if not sortie.strip():
        return False
    return json.loads(sortie)["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestGuardGitFormesDInvocation:
    """Les 5 formes verifiees par l'orchestrateur : 1 bloquee, 4 qui passaient."""

    @pytest.mark.parametrize("commande", [
        "git push --force",                 # forme deja bloquee (non-regression)
        "git.exe push --force",             # invocation native Windows
        "/usr/bin/git push --force",        # chemin absolu POSIX
        r'"C:\Program Files\Git\bin\git.exe" push --force',  # chemin absolu Windows (quote)
        'bash -c "git push --force"',       # wrapper -c
        "(git push --force)",               # sous-shell / groupement
        'eval "git push --force"',          # eval
    ])
    def test_push_force_bloque(self, commande):
        assert _deny(commande), f"non bloque : {commande!r}"

    @pytest.mark.parametrize("commande", [
        "git reset --hard",
        "git.exe reset --hard",
        "(git reset --hard HEAD~1)",
    ])
    def test_reset_hard_bloque(self, commande):
        assert _deny(commande), f"non bloque : {commande!r}"

    @pytest.mark.parametrize("commande", [
        "git push --force-with-lease",
        "git status",
        "echo 'git push --force'",
        "gitk --all",                      # binaire dont le nom COMMENCE par git
        "mygit push --force",              # binaire dont le nom FINIT par git
        "git commit -m \"documente git push --force\"",
    ])
    def test_non_bloque(self, commande):
        assert not _deny(commande), f"faux positif : {commande!r}"


# --- Correctif 3 : log_usage.py doit lire stdin en UTF-8 ----------------------------
def _rejouer_log_usage(tmp_path, payload_octets: bytes):
    """Rejoue le hook PostToolUse avec un payload BRUT (octets), journal isole."""
    journal = tmp_path / "usage.jsonl"
    env = dict(os.environ, AGENT_SUPERVISION_USAGE=str(journal))
    env.pop("PYTHONIOENCODING", None)   # on veut le comportement par defaut de la machine
    env.pop("PYTHONUTF8", None)
    r = subprocess.run([sys.executable, str(LOG_USAGE)], input=payload_octets,
                       capture_output=True, env=env, timeout=30)
    return r, journal


class TestLogUsageEncodage:
    """57 lignes sur 233 du journal reel contiennent « Ã » ou « â€ » : stdin etait lu
    dans l'encodage local (cp1252 sous Windows) au lieu d'UTF-8."""

    def test_accents_journalises_intacts(self, tmp_path):
        payload = json.dumps({
            "tool_name": "Skill",
            "session_id": "s1",
            "tool_input": {"skill": "revue-increment",
                           "description": "évolution flotte — étape n°1 « clé »"},
        }, ensure_ascii=False).encode("utf-8")
        r, journal = _rejouer_log_usage(tmp_path, payload)
        assert r.returncode == 0
        entree = json.loads(journal.read_text(encoding="utf-8").strip())
        assert entree["description"] == "évolution flotte — étape n°1 « clé »", (
            "mojibake : stdin n'est pas lu en UTF-8")
        assert "Ã" not in journal.read_text(encoding="utf-8")

    def test_bom_powershell_ne_casse_pas_le_parsing(self, tmp_path):
        payload = ("\ufeff" + json.dumps({
            "tool_name": "Agent", "session_id": "s2",
            "tool_input": {"subagent_type": "agent-supervisor", "description": "diagnostic"},
        })).encode("utf-8")
        r, journal = _rejouer_log_usage(tmp_path, payload)
        assert r.returncode == 0
        assert journal.exists(), (
            "un BOM PowerShell ne doit pas faire perdre l'invocation "
            f"(stderr : {r.stderr.decode('utf-8', 'replace')!r})")

    def test_payload_non_decodable_signale_sans_bloquer(self, tmp_path):
        r, journal = _rejouer_log_usage(tmp_path, b'{"tool_name": "Skill", "x": "\xff\xfe\xff"}')
        assert r.returncode == 0, "le hook ne doit JAMAIS bloquer l'outil"
        assert r.stderr.strip(), (
            "une invocation perdue doit se voir : sans message, l'etage 1 sous-compte "
            "en silence")


# --- Correctifs 4 et 5 : canon/log_run.py -------------------------------------------
@pytest.fixture
def log_run(tmp_path, monkeypatch):
    """Module canon charge par chemin, RUNS_PATH redirige vers un journal jetable."""
    lr = _charger(LOG_RUN_CANON, "lr_garde_fous")
    monkeypatch.setattr(lr, "RUNS_PATH", str(tmp_path / "runs.jsonl"))
    return lr


def _lignes(lr):
    with open(lr.RUNS_PATH, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


class TestLogRunResultatValideALAppend:
    """`--solde` valide `resultat`, l'append ne le validait pas : « succès » accentue
    (faute de frappe naturelle en francais) et « nimportequoi » passaient en exit 0,
    faussaient le taux de reussite et echappaient au controle en-attente-validation."""

    @pytest.mark.parametrize("resultat", ["succès", "nimportequoi", "SUCCES", "ok", ""])
    def test_resultat_invalide_refuse_sans_ecrire(self, log_run, resultat, capsys):
        charge = json.dumps({"demande": "x", "qualification": "orchestre",
                             "resultat": resultat}, ensure_ascii=False)
        code = log_run.main([charge])
        sortie = capsys.readouterr().out
        assert code != 0, f"resultat {resultat!r} accepte : {sortie!r}"
        assert "resultat" in sortie.lower()
        assert not os.path.exists(log_run.RUNS_PATH), "un run refuse ne doit rien ecrire"

    @pytest.mark.parametrize("resultat", [
        "en-cours", "succes", "en-attente-validation", "partiel", "echec"])
    def test_resultats_valides_acceptes(self, log_run, resultat):
        code = log_run.main([json.dumps(
            {"demande": "x", "qualification": "orchestre", "resultat": resultat})])
        assert code == 0
        assert _lignes(log_run)[0]["resultat"] == resultat

    def test_resultat_absent_toujours_accepte(self, log_run):
        """Comportement actuel conserve : l'orchestrateur peut ouvrir un run sans champ."""
        assert log_run.main(['{"demande": "x", "qualification": "orchestre"}']) == 0
        assert _lignes(log_run)[0]["demande"] == "x"


class TestSolderPrefixeAmbiguAvecDemandeNulle:
    """La branche « il en faut exactement 1 » doit LISTER les candidats pour
    desambiguiser — elle plantait en TypeError des qu'un run portait demande: null."""

    def test_liste_les_candidats_sans_planter(self, log_run, capsys):
        with open(log_run.RUNS_PATH, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-07-24T10:00:00", "demande": None,
                                 "qualification": "orchestre",
                                 "resultat": "en-attente-validation"}) + "\n")
            fh.write(json.dumps({"ts": "2026-07-24T11:30:00", "demande": "run lisible",
                                 "qualification": "orchestre",
                                 "resultat": "en-attente-validation"}) + "\n")
        code = log_run.solder(["2026-07-24T", "succes", "note"])
        sortie = capsys.readouterr().out
        assert code == 1
        assert "2 run(s)" in sortie
        assert "2026-07-24T10:00:00" in sortie and "run lisible" in sortie
        assert all(r["resultat"] == "en-attente-validation" for r in _lignes(log_run))
