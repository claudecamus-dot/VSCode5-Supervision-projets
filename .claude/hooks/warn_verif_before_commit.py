r"""PreToolUse hook (Bash/PowerShell) — soft, NON-blocking reminder that warns
when hub code (scripts/, tests/, .claude/supervision/, .claude/orchestration/,
.claude/dispositif/, .claude/hooks/) is about to be committed without a real
verification having run in the current session.

Provenance : porté de VSCode2 (constat superviseur #1, 2026-07-21) vers les 4 autres
projets de la flotte le 2026-07-24 — mais jamais câblé sur ce hub lui-même. Trouvé
par son propre diagnostic agent-supervisor (finding pratique-revue, 2026-07-24) :
« VScode5 a propagé warn_verif_before_commit + revue-fraîche à toute la flotte mais
ne les a jamais adoptés sur lui-même ». Dernier projet à le recevoir, ironiquement.

Conception (identique aux 5 autres copies, seule la zone/les signaux changent) :
- **Non bloquant** : `systemMessage` + `additionalContext`, sans `permissionDecision`.
- **Ciblé le code du dispositif**, PAS docs/wiki/ (régénéré par le scan) : l'y inclure
  noierait le signal sous des commits de doc auto-générée.
- **Détection = vraie exécution d'outil** (pytest, py_compile, régénération du wiki),
  pas une simple mention — parse le transcript de session.
- **Fail-open partout** : toute erreur rend la main sans avertir.

Le tokenizer shell robuste est réutilisé de `guard_destructive_git.py` (même
répertoire) ; si l'import échoue, dégradation en silence.
"""
import json
import os
import re
import shlex
import subprocess
import sys

try:  # réutilise le tokenizer éprouvé du guard voisin ; sinon, dégrade en silence
    from guard_destructive_git import _strip_heredocs, _segments
except Exception:  # pragma: no cover - fail-open
    _strip_heredocs = None
    _segments = None

# Zone sous vérification : le code du dispositif (hors docs/wiki, régénéré par le
# scan — l'y inclure noierait le signal sous des commits de doc auto-générée).
_WATCHED_PREFIXES = (
    "scripts/", "tests/", ".claude/supervision/", ".claude/orchestration/",
    ".claude/dispositif/", ".claude/hooks/",
)

# Signaux d'une vraie exécution de vérif dans la session (commandes Bash). Adapté à
# VScode5 (Python/pytest + régénération du wiki, cf. table de vérifs du CLAUDE.md).
_VERIF_BASH = ("pytest", "-m pytest", "py_compile", "scan_projets.py")
_VERIF_SKILL = ()  # pas de skill de revue dédiée sur ce hub — la table CLAUDE.md fait foi

_GIT_OPTS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")


def _git_commit_flags(segment):
    """-> liste des tokens d'un `git commit` réel, ou None si le segment n'en est pas un."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        return None  # quotes déséquilibrées, substitution… — on ne devine pas
    if not tokens:
        return None
    start = 0
    while start < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[start]):
        start += 1  # saute les affectations VAR=value en tête
    if start >= len(tokens) or tokens[start].lower() != "git":
        return None
    rest = tokens[start + 1:]
    # Sous-commande = premier token non-option (en sautant -C/-c <val> globaux).
    i = 0
    sub = None
    while i < len(rest):
        t = rest[i]
        if t.startswith("-"):
            i += 2 if t in _GIT_OPTS_WITH_VALUE else 1
            continue
        sub = t
        break
    if sub != "commit":
        return None
    if "--dry-run" in rest:
        return None  # ne crée pas de commit
    return rest


def _staged_watched(cwd, commit_flags):
    """Fichiers surveillés qui seront réellement commités, ou None si indéterminable."""
    def _run(args):
        try:
            r = subprocess.run(
                ["git"] + args, cwd=cwd or None,
                capture_output=True, text=True, timeout=8,
            )
        except Exception:
            return None
        if r.returncode != 0:
            return None
        return [ln.strip().replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()]

    files = _run(["diff", "--cached", "--name-only"])
    if files is None:
        return None
    # `git commit -a/--all` valide aussi les modifs de fichiers suivis non stagés :
    # les ajouter, sinon on manquerait le périmètre réel du commit.
    if any(f in ("-a", "--all") for f in commit_flags):
        unstaged = _run(["diff", "--name-only"])
        if unstaged:
            files = list(dict.fromkeys(files + unstaged))
    return [f for f in files if f.startswith(_WATCHED_PREFIXES)]


def _iter_tool_uses(obj):
    msg = obj.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if not isinstance(content, list):
        return
    for blk in content:
        if isinstance(blk, dict) and blk.get("type") == "tool_use":
            yield blk


def _verif_ran(transcript_path):
    """True si une vraie exécution de vérif est présente dans le transcript de session."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
    try:
        with open(transcript_path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue  # préfiltre octet bon marché (cf. scan_transcripts.py)
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                for blk in _iter_tool_uses(obj):
                    name = blk.get("name")
                    inp = blk.get("input") or {}
                    if name == "Bash":
                        cmd = (inp.get("command") or "").lower()
                        if any(k in cmd for k in _VERIF_BASH):
                            return True
                    elif name == "Skill":
                        if (inp.get("skill") or "").lower() in _VERIF_SKILL:
                            return True
    except Exception:
        return False
    return False


_WARNING = (
    "⚠️ Vérif non détectée dans cette session : du code du dispositif (scripts/, "
    "tests/, .claude/supervision/, .claude/orchestration/, .claude/dispositif/, "
    ".claude/hooks/) est sur le point d'être commité sans trace de `pytest` ni de "
    "régénération du wiki (`scan_projets.py`). Lancer la vérif RÉELLE avant de "
    "committer, ou confirmer que c'est volontaire. "
    "(Garde-fou projet non bloquant — finding pratique-revue du 2026-07-24.)"
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    strip = _strip_heredocs or (lambda s: s)
    segs = _segments(cmd) if _segments else [cmd]
    try:
        cmd = strip(cmd)
        segs = _segments(cmd) if _segments else [cmd]
    except Exception:
        return  # fail-open

    commit_flags = None
    for seg in segs:
        commit_flags = _git_commit_flags(seg)
        if commit_flags is not None:
            break
    if commit_flags is None:
        return  # pas un git commit

    watched = _staged_watched(data.get("cwd"), commit_flags)
    if not watched:
        return  # rien sous les zones surveillées dans ce commit (ou git indéterminable)

    if _verif_ran(data.get("transcript_path")):
        return  # une vérif réelle a tourné cette session — pas de rappel

    print(json.dumps({
        "systemMessage": _WARNING,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": _WARNING,
        },
    }))


if __name__ == "__main__":
    main()
