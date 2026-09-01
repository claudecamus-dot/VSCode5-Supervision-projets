"""Refuse un commit qui embarque un `export/` en dérive — donc une édition manuelle.

Arbitrage utilisateur du 2026-09-01 (« sécurise les fichiers de export », volet
« empêcher l'édition manuelle »).

POURQUOI CE HOOK EXISTE. `export/` est **entièrement généré** par
`.claude/dispositif/export_agentic.py` : une correction faite directement dedans est
perdue à la régénération suivante, **sans un mot**. `--check` sait détecter cette
dérive depuis toujours — mais rien ne l'appelait au moment qui compte, celui du commit.
C'est très exactement ce trou qui a laissé le déploiement servir, sans le dire, un
`agent-orchestrator` de 120 lignes contre 467 au hub (mesuré le 2026-08-31).

POURQUOI IL BLOQUE, là où `warn_verif_before_commit.py` se contente d'avertir. Un
avertissement suppose que quelqu'un le lise et décide ; ici la conséquence est
silencieuse et différée — le travail ne disparaît pas au commit, il disparaît à la
régénération suivante, quand plus personne ne fait le lien. Un signal qu'on ne peut
relier à sa cause n'est pas un signal. Le refus, lui, arrive au bon endroit et porte la
commande qui le lève.

CE QU'IL NE FAIT PAS. Il ne juge pas le contenu d'`export/`, seulement sa **fraîcheur** :
un `export/` régénéré et cohérent passe sans un mot, y compris dans un gros commit. Il
ne regarde que les commandes de commit ; `git status`, `git add`, `git diff` ne
déclenchent rien.

FAIL-OPEN PARTOUT. Toute erreur — stdin illisible, git absent, `--check` qui plante —
rend la main sans bloquer. Un garde-fou de confort qui empêche de travailler quand il
est lui-même en panne coûte plus qu'il ne rapporte.

Les deux sondes coûteuses sont surchargeables par variable d'environnement
(`AGENT_SUPERVISION_TEST_STAGED`, `AGENT_SUPERVISION_TEST_DERIVE`) : sans cela, un test
de ce hook mesurerait l'état du dépôt à l'instant où il tourne, pas le comportement du
hook — la faute que les tests de `test_check_flotte.py` ont déjà value au dispositif.
"""

import json
import os
import re
import subprocess
import sys

HOOKS = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(HOOKS))

# `git commit`, y compris précédé d'options globales (`git -c x=y commit`) et suivi de
# n'importe quels arguments. `git commit-tree` et `git commit-graph` sont d'autres
# commandes : la frontière de mot les exclut.
_COMMIT = re.compile(r"\bgit\b[^\n;&|]*\bcommit\b(?!-)")


def _est_un_commit(commande: str) -> bool:
    return bool(_COMMIT.search(commande or ""))


def _fichiers_indexes() -> list:
    """Ce que le commit s'apprête à embarquer."""
    surcharge = os.environ.get("AGENT_SUPERVISION_TEST_STAGED")
    if surcharge is not None:
        return [l for l in surcharge.splitlines() if l.strip()]
    try:
        out = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=HUB,
                             capture_output=True, text=True, encoding="utf-8",
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [l for l in out.stdout.splitlines() if l.strip()]


def _export_en_derive() -> bool:
    """`export_agentic.py --check` : le kit publié est-il en retard sur ses sources ?"""
    surcharge = os.environ.get("AGENT_SUPERVISION_TEST_DERIVE")
    if surcharge is not None:
        return surcharge == "1"
    script = os.path.join(HUB, ".claude", "dispositif", "export_agentic.py")
    if not os.path.isfile(script):
        return False
    try:
        out = subprocess.run([sys.executable, script, "--check"], cwd=HUB,
                             capture_output=True, text=True, encoding="utf-8",
                             timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode != 0


def _raison() -> str | None:
    if not any(f.replace("\\", "/").startswith("export/") for f in _fichiers_indexes()):
        return None
    if not _export_en_derive():
        return None
    return (
        "Ce commit embarque des fichiers de export/ alors que le kit publie est EN "
        "DERIVE avec ses sources. export/ est entierement genere : ce qui y est ecrit "
        "a la main est perdu, en silence, a la regeneration suivante — c'est le trou "
        "qui a laisse servir un agent-orchestrator de 120 lignes contre 467 au hub. "
        "Corriger la SOURCE dans le hub, puis : py .claude/dispositif/export_agentic.py "
        "et py .claude/dispositif/export_agentic.py --check avant de recommitter."
    )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:  # pragma: no cover - fail-open
        return
    commande = (data.get("tool_input") or {}).get("command") or ""
    if not _est_un_commit(commande):
        return
    try:
        raison = _raison()
    except Exception:  # pragma: no cover - fail-open
        return
    if raison:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": raison,
            }
        }))


if __name__ == "__main__":
    main()
