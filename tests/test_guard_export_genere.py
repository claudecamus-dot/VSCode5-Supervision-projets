"""Le refus d'un commit qui abandonne `export/` en dérive.

INCIDENT REPRODUIT ICI (commit `3ddc950`, 2026-09-03). `_raison()` ne déclenchait la
vérification de dérive QUE si un fichier stagé commençait par `export/`. Le cas
réellement dangereux — celui que le docstring du hook revendique fermer — est
l'inverse : committer une SOURCE du kit (ici `.claude/dispositif/canon/
scan_transcripts.py`, colonne 1 du MANIFESTE de `export_agentic.py`) SANS régénérer
`export/`. Dans ce cas, aucun fichier `export/` n'est jamais mis à l'index : le hook
rendait la main en silence, alors que `--check` aurait signalé la dérive. Le kit publié
est resté en retard sur sa source environ 2 heures avant un commit correctif.

Le correctif ajoute une seconde porte d'entrée : toute SOURCE du manifeste stagée
déclenche, elle aussi, la vérification de dérive — sans dupliquer la liste des
sources, lue directement dans `export_agentic.MANIFESTE` (sinon les deux listes
dérivent l'une de l'autre, exactement le défaut que ce hook ferme côté `export/`).

Les deux sondes coûteuses du hook (git diff --cached, `export_agentic.py --check`) sont
surchargées par variable d'environnement — sans cela, ces tests mesureraient l'état du
dépôt à l'instant où ils tournent, pas le comportement du hook.
"""

import json
import os
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(HUB, ".claude", "hooks", "guard_export_genere.py")

# Source réelle du manifeste (colonne 1 de `export_agentic.MANIFESTE`), celle qui a
# effectivement été committée sans régénération le 2026-09-03 — pas un chemin inventé.
SOURCE_REELLE = ".claude/dispositif/canon/scan_transcripts.py"


def _appel(commande="git commit -m x", staged="", derive="0"):
    """Exécute le hook comme le harnais le fait : JSON sur stdin, JSON sur stdout.

    SANS `-X utf8` ni `PYTHONIOENCODING` : le gabarit du kit lance `py "<script>"` tel
    quel — un test qui ajoute ces béquilles exécute un hook que la production
    n'exécute pas (leçon du 2026-09-02 sur `warn_verif_before_commit.py`).
    """
    env = dict(os.environ)
    env["AGENT_SUPERVISION_TEST_STAGED"] = staged
    env["AGENT_SUPERVISION_TEST_DERIVE"] = derive
    charge = json.dumps({"tool_name": "Bash", "tool_input": {"command": commande}})
    r = subprocess.run([sys.executable, HOOK], input=charge, cwd=HUB,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="strict", timeout=30, env=env)
    return r


def _decision(r):
    if not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout).get("hookSpecificOutput", {}).get("permissionDecision")
    except ValueError:
        return None


class TestLaSourceStageeSansExportEstBloquee:
    """Le cas exact de l'incident : aucun fichier `export/` à l'index, une source oui."""

    def test_une_source_du_manifeste_stagee_et_le_kit_en_derive_est_refuse(self):
        r = _appel(staged=SOURCE_REELLE, derive="1")
        assert _decision(r) == "deny", (
            "une source du kit stagee sans export/ ni regeneration doit etre refusee "
            f"(regression de l'incident 3ddc950) ; stdout={r.stdout!r} stderr={r.stderr[:300]!r}")

    def test_le_refus_pointe_vers_la_commande_de_regeneration(self):
        r = _appel(staged=SOURCE_REELLE, derive="1")
        raison = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "export_agentic.py" in raison, raison

    def test_une_source_stagee_mais_le_kit_a_jour_ne_bloque_pas(self):
        """Le hook juge la fraicheur, pas le fait de toucher une source : une source
        committee APRES regeneration (kit a jour) doit passer sans un mot."""
        r = _appel(staged=SOURCE_REELLE, derive="0")
        assert _decision(r) != "deny", r.stdout

    def test_rien_qui_touche_une_source_ou_export_ne_bloque_meme_en_derive(self):
        """Un commit qui ne touche ni une source du kit ni export/ n'a aucune raison
        d'etre bloque par CE garde-fou, meme si le kit est par ailleurs en derive."""
        r = _appel(staged="docs/wiki.html\nREADME.md", derive="1")
        assert _decision(r) != "deny", r.stdout


class TestLeCasDOrigineResteCouvert:
    """Le cas pour lequel le hook a ete construit le 2026-09-01 : une main ecrit
    directement dans export/. Le correctif ne doit pas faire regresser cette porte."""

    def test_un_fichier_export_stage_et_le_kit_en_derive_est_refuse(self):
        r = _appel(staged="export/skills/agent-orchestrator/SKILL.md", derive="1")
        assert _decision(r) == "deny", r.stdout

    def test_un_fichier_export_stage_mais_le_kit_a_jour_ne_bloque_pas(self):
        r = _appel(staged="export/skills/agent-orchestrator/SKILL.md", derive="0")
        assert _decision(r) != "deny", r.stdout


class TestIlNeSeDeclencheQueSurUnCommit:
    def test_un_git_add_ne_declenche_rien_meme_source_stagee_et_en_derive(self):
        r = _appel(commande="git add .", staged=SOURCE_REELLE, derive="1")
        assert _decision(r) != "deny", r.stdout

    def test_une_commande_non_git_ne_declenche_rien(self):
        r = _appel(commande="echo commit", staged=SOURCE_REELLE, derive="1")
        assert _decision(r) != "deny", r.stdout


class TestFailOpen:
    """`PreToolUse` : une exception ici bloquerait un `git commit` legitime."""

    def test_une_entree_malformee_ne_fait_ni_lever_ni_refuser(self):
        env = dict(os.environ, AGENT_SUPERVISION_TEST_STAGED=SOURCE_REELLE,
                   AGENT_SUPERVISION_TEST_DERIVE="1")
        r = subprocess.run([sys.executable, HOOK], input="pas du json", cwd=HUB,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="strict", timeout=30, env=env)
        assert r.returncode == 0, f"exit {r.returncode} : {r.stderr[:400]}"
        assert "Traceback" not in (r.stderr or ""), r.stderr[:400]
        assert _decision(r) != "deny"
