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

import importlib.util
import json
import os
import re
import subprocess
import sys

HOOKS = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(HOOKS))
EXPORT_AGENTIC = os.path.join(HUB, ".claude", "dispositif", "export_agentic.py")

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


def _sources_manifeste() -> set:
    """Chemins (relatifs au hub, en `/`) des SOURCES du kit — colonne 1 de MANIFESTE
    dans `export_agentic.py`.

    Chargé depuis le script lui-même plutôt que recopié ici : un manifeste dupliqué
    dérive du vrai dès le premier fichier ajouté ou retiré là-bas, exactement la même
    faute que celle que ce hook existe pour fermer côté `export/`. Fail-open : import
    impossible (script absent, erreur de syntaxe) -> ensemble vide, donc aucun blocage
    fondé sur les sources tant que ce chargement échoue.
    """
    try:
        spec = importlib.util.spec_from_file_location("export_agentic_guard", EXPORT_AGENTIC)
        if spec is None or spec.loader is None:
            return set()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:  # pragma: no cover - fail-open
        return set()
    hub_abs = os.path.abspath(HUB)
    sources = set()
    for src, _rel, _dst in getattr(module, "MANIFESTE", []):
        try:
            src_abs = os.path.abspath(src)
            if os.path.commonpath([src_abs, hub_abs]) != hub_abs:
                continue  # hors du hub (ex. GENERIQUE = VSCode3) : jamais stageable ici
            sources.add(os.path.relpath(src_abs, hub_abs).replace(os.sep, "/"))
        except ValueError:
            continue  # chemins sur des lecteurs différents (Windows)
    return sources


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
    fichiers = [f.replace("\\", "/") for f in _fichiers_indexes()]
    # Deux portes d'entree distinctes vers le meme risque : (1) le cas d'origine —
    # une main ecrit directement dans export/, corrige la copie et perd la correction
    # a la regeneration suivante ; (2) le cas reel du 2026-09-03 (commit 3ddc950) — une
    # SOURCE du kit est modifiee et committee SANS regenerer export/, donc aucun fichier
    # export/ n'est jamais mis en index et la premiere porte reste muette. Les deux
    # partagent le meme test de fond : le kit publie est-il EN DERIVE.
    touche_export = any(f.startswith("export/") for f in fichiers)
    touche_source = bool(_sources_manifeste() & set(fichiers))
    if not touche_export and not touche_source:
        return None
    if not _export_en_derive():
        return None
    return (
        "Ce commit touche export/ ou une source de son kit, alors que le kit publie est "
        "EN DERIVE avec ses sources. export/ est entierement genere : une source "
        "modifiee sans regeneration, ou une correction ecrite a la main dans export/, "
        "est perdue en silence — c'est le trou qui a laisse servir un "
        "agent-orchestrator de 120 lignes contre 467 au hub. "
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
