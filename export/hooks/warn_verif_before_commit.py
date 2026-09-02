r"""PreToolUse hook (Bash/PowerShell) — soft, NON-blocking reminder that warns
when a project's watched code paths are about to be committed without a real
verification having run in the current session.

Provenance : proposition du constat #1 du superviseur d'agents (étage 2),
arbitrée puis appliquée le 2026-07-21. Le diagnostic (voir
`docs/wiki/technical/agents-supervision.md`) montrait que la vérif réelle de
fin d'incrément était systématiquement sautée : `revue-increment` n=0 sur 14
sessions, `pptx-verify` figé à 1 usage, alors que du code continuait d'être
commité. Le rappel SessionStart passif (`remind_revue_increment.py`) ne
suffit pas — rien n'oblige à le suivre. Ce hook déplace le rappel AU BON
INSTANT : le commit.

Conception (delta assumé vs. la proposition brute) :
- **Non bloquant** : émet un `systemMessage` (visible utilisateur) + un
  `additionalContext` (visible modèle si supporté), SANS `permissionDecision`.
  Le commit passe — on avertit, on ne bloque pas (cf. guard_destructive_git.py,
  lui, bloque : ce sont deux niveaux de sévérité volontairement distincts).
- **Zone surveillée et preuves de vérif CONFIGURABLES par projet**, pas
  figées dans le code (voir bloc « Configuration par projet » plus bas).
  Historique du défaut corrigé le 2026-09-02 (revue de sécurité du
  2026-09-01, finding « le kit publié embarque les chemins surveillés d'un
  AUTRE projet ») : ce fichier est la SOURCE que le hub de supervision publie
  dans le kit agentic installé par cinq dépôts
  (`export_agentic.GENERIQUE` pointe `~/Documents/VSCode3/.claude/hooks`).
  Avant correction, `_WATCHED_PREFIXES`/`_VERIF_BASH` étaient des tuples
  fixes adaptés à VSCode3 (`docs/cadrage-ppt/`, `pytest`) le 2026-07-24, sans
  que ce docstring ni le message utilisateur (encore `app/**`, `npm test` —
  canal VSCode1) ne soient mis à jour. Un dépôt tiers installant le kit
  héritait donc soit d'un garde-fou muet (mauvais périmètre : `docs/cadrage-ppt/`
  n'existe pas chez lui), soit — s'il adaptait les constantes sans lire ce
  fichier en entier — d'un message qui pointe vers la mauvaise commande.
- **Détection de trace de vérif = vraie exécution d'outil**, pas une simple
  mention : on parse le transcript de la session (tool_use Bash/PowerShell
  correspondant à `_VERIF_BASH` / Skill correspondant à `_VERIF_SKILL`),
  même structure que scan_transcripts.py — sinon toute session qui *parle*
  de vérif se faux-négativerait.
- **Fail-open partout** : toute erreur (parsing, git indisponible, transcript
  illisible, import, configuration de projet illisible/malformée) rend la
  main SANS avertir. Un bug ici ne doit jamais ajouter de friction ni
  bloquer un commit.

Le tokenizer shell robuste (heredocs, segments quote-safe) est réutilisé de
`guard_destructive_git.py` (même répertoire) pour ne pas diverger d'un second
parseur du même problème ; si l'import échoue, dégradation en silence.
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

# --- Configuration par projet ------------------------------------------------
# Mécanisme retenu : un fichier JSON optionnel, `warn_verif_before_commit.json`,
# à la racine `.claude/` du dépôt CIBLE (celui où le hook s'exécute) — pas une
# auto-détection de `app/` vs `src/` vs `docs/...`, qui devinerait le périmètre
# applicatif d'un dépôt inconnu plutôt que de le lire explicitement. Le chemin
# est dérivé de l'emplacement de CE fichier (`<repo>/.claude/hooks/…`), jamais
# du `cwd` transmis par l'outil : un commit lancé depuis un sous-dossier ne
# doit pas faire manquer la configuration du dépôt.
#
# Absente, illisible ou JSON malformée : repli intégral sur un canal générique
# (fail-open) — jamais une erreur, jamais un hook silencieux par construction.
# Une config partielle (un seul champ renseigné) ne complète que les champs
# manquants avec ce même repli, plutôt que de tout invalider.
_CONFIG_FILENAME = "warn_verif_before_commit.json"

# Repli générique : le canal historique de ce hook avant son adaptation à
# VSCode3 (VSCode1, 2026-07-21). Il n'a plus vocation à décrire UN projet —
# seulement à garantir qu'un dépôt sans configuration obtient un déclencheur
# non vide plutôt qu'un hook silencieux par défaut.
_DEFAULT_WATCHED_PREFIXES = ("app/",)
_DEFAULT_VERIF_BASH = ("npm test", "pytest", "-m pytest")
_DEFAULT_VERIF_SKILL = ("revue-increment",)


def _config_path():
    """`<repo>/.claude/warn_verif_before_commit.json`, dérivé de l'emplacement
    de ce fichier (`<repo>/.claude/hooks/…`) — jamais du cwd du commit."""
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(hooks_dir), _CONFIG_FILENAME)


def _as_str_tuple(value, default):
    """Liste JSON -> tuple de chaines non vides, ou `default` si `value` n'est
    pas une liste exploitable (absente, mauvais type, vide)."""
    if not isinstance(value, list):
        return default
    cleaned = tuple(v for v in value if isinstance(v, str) and v)
    return cleaned or default


def _load_config():
    """(watched_prefixes, verif_bash, verif_skill) effectifs pour ce dépôt.

    Fail-open champ par champ : un fichier absent, illisible ou dont le JSON
    est invalide retombe entièrement sur le repli générique ; une config
    présente mais partielle complète uniquement les champs manquants.
    """
    watched, verif_bash, verif_skill = (
        _DEFAULT_WATCHED_PREFIXES, _DEFAULT_VERIF_BASH, _DEFAULT_VERIF_SKILL,
    )
    try:
        with open(_config_path(), encoding="utf-8") as fh:
            cfg = json.load(fh)
        if isinstance(cfg, dict):
            watched = _as_str_tuple(cfg.get("watched_prefixes"), watched)
            verif_bash = _as_str_tuple(cfg.get("verif_bash"), verif_bash)
            verif_skill = _as_str_tuple(cfg.get("verif_skill"), verif_skill)
    except Exception:
        pass  # absente / JSON invalide / illisible... — repli générique, jamais d'erreur
    return watched, verif_bash, verif_skill


# Périmètre et preuves EFFECTIFS de ce dépôt : lus une fois au chargement du
# hook (chaque commit relance ce script comme process neuf, donc pas besoin
# de rechargement à chaud). Sur VSCode3, la configuration posée à côté
# (`.claude/warn_verif_before_commit.json`) restitue exactement le périmètre
# historique — docs/cadrage-ppt/, pytest/test_generate_deck,
# pptx-verify/revue-increment — le comportement observable ne change pas.
_WATCHED_PREFIXES, _VERIF_BASH, _VERIF_SKILL = _load_config()

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
    """Fichiers surveillés (`_WATCHED_PREFIXES`, configurable par projet) qui
    seront réellement commités, ou None si indéterminable."""
    def _run(args):
        try:
            r = subprocess.run(
                ["git"] + args, cwd=cwd or None,
                capture_output=True, text=True, timeout=8,
                encoding="utf-8", errors="replace",
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
                    # PowerShell est le shell PRIMAIRE de cet environnement : ne
                    # reconnaitre que Bash rendait le garde-fou aveugle a la majorite
                    # des verifications reellement lancees (faux negatif constate en
                    # production, run 2026-08-31T21:59). Les deux outils exposent la
                    # commande sous la meme cle `input.command`.
                    if name in ("Bash", "PowerShell"):
                        cmd = (inp.get("command") or "").lower()
                        if any(k in cmd for k in _VERIF_BASH):
                            return True
                    elif name == "Skill":
                        if (inp.get("skill") or "").lower() in _VERIF_SKILL:
                            return True
    except Exception:
        return False
    return False


def _matched_prefixes(files, prefixes):
    """Sous-ensemble de `prefixes` réellement responsable du déclenchement, dans
    l'ordre de déclaration — pour nommer dans le message CE qui a matché, pas
    la configuration entière du projet."""
    return [p for p in prefixes if any(f.startswith(p) for f in files)]


def _build_warning(prefixes, verif_bash, verif_skill):
    """Message dérivé des constantes RÉELLES (config du dépôt cible) reçues en
    paramètre — jamais d'un canal figé en dur indépendant d'elles. Voir le
    docstring du module pour l'historique du défaut que ceci corrige."""
    zones = ", ".join(f"`{p}`" for p in prefixes) if prefixes else "le périmètre surveillé"
    preuves = []
    if verif_bash:
        preuves.append(" / ".join(f"`{c}`" for c in verif_bash))
    if verif_skill:
        preuves.append("skill " + " ou ".join(f"`{s}`" for s in verif_skill))
    preuves_txt = " ou ".join(preuves) if preuves else "une vérif réelle"
    return (
        "⚠️ Vérif de fin d'incrément non détectée dans cette session : des "
        f"fichiers sous {zones} sont sur le point d'être commités sans trace "
        f"d'une exécution réelle de {preuves_txt}. Lancer la vérif RÉELLE avant "
        "de committer ce périmètre, ou confirmer que c'est volontaire. "
        "(Garde-fou projet non bloquant — périmètre configurable via "
        f"`.claude/{_CONFIG_FILENAME}`.)"
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
        return  # rien sous le périmètre surveillé dans ce commit (ou git indéterminable) — silence

    if _verif_ran(data.get("transcript_path")):
        return  # une vérif réelle a tourné cette session — pas de rappel

    warning = _build_warning(_matched_prefixes(watched, _WATCHED_PREFIXES), _VERIF_BASH, _VERIF_SKILL)
    print(json.dumps({
        "systemMessage": warning,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": warning,
        },
    }))


if __name__ == "__main__":
    main()
