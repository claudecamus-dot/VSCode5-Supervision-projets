"""Scanner multi-projets — agrège l'état agentic des projets listés dans projets.json.

Lecture seule sur les projets cibles. Sorties :
  docs/wiki/projets-supervision.md   (markdown, versionné)
  docs/wiki.html                     (page autonome, consultable sans dépendance)

Sections de la page : 1) supervision des projets (tableau + détails repliables),
2) veille agentic (lue depuis .claude/veille/veille.json, alimentée par la skill
`veille-agentic`).

Usage : py scripts/scan_projets.py
"""

from __future__ import annotations

import datetime as dt
import html
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "projets.json")
VEILLE_PATH = os.path.join(ROOT, ".claude", "veille", "veille.json")
OUT_MD = os.path.join(ROOT, "docs", "wiki", "projets-supervision.md")
OUT_HTML = os.path.join(ROOT, "docs", "wiki.html")
EXPORTS_DIR = os.path.join(ROOT, "docs", "wiki", "exports")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Seuils d'alerte sur la priorité des findings des superviseurs locaux (1..5)
PRIO_CRITIQUE = 5
PRIO_MAJEUR = 4

# Seuils de péremption des cadences (jours)
CADENCE_SCAN_J = 3        # scan étage 1 — rafraîchi par ce script, doit rester frais
CADENCE_DIAGNOSTIC_J = 14  # cadence documentée d'agent-supervisor
CADENCE_COMMIT_J = 14      # un projet actif sans commit depuis 14 j interroge
CADENCE_VEILLE_J = 3       # cadence de la skill veille-agentic
RUN_A_SOLDER_H = 48        # un run en-attente-validation plus vieux = à solder


def parse_iso(s):
    """ISO -> datetime naïf local (None si invalide)."""
    try:
        d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if d.tzinfo:
            d = d.astimezone().replace(tzinfo=None)
        return d
    except (ValueError, TypeError):
        return None


def age_str(d, now):
    """Écart humain : « il y a 2 h » / « il y a 3 j »."""
    if d is None:
        return "jamais"
    delta = now - d
    if delta.days >= 1:
        return f"il y a {delta.days} j"
    heures = delta.seconds // 3600
    if heures >= 1:
        return f"il y a {heures} h"
    return f"il y a {max(delta.seconds // 60, 0)} min"


def est_perime(d, seuil_jours, now):
    return d is None or (now - d) > dt.timedelta(days=seuil_jours)


def refresh_local_scans(projets_cfg):
    """Relance le scan étage 1 (déterministe, 0 token) de chaque projet qui en a un,
    pour que l'agrégation porte sur du frais — pas sur le dernier passage local.
    Renvoie {nom: 'rafraichi' | 'absent' | 'echec'}."""
    etats = {}
    for p in projets_cfg:
        script = os.path.join(p["chemin"], ".claude", "supervision", "scan_transcripts.py")
        if not os.path.isfile(script):
            etats[p["nom"]] = "absent"
            continue
        try:
            r = subprocess.run(
                [sys.executable, "-X", "utf8", script],
                cwd=p["chemin"], capture_output=True, timeout=90,
            )
            etats[p["nom"]] = "rafraichi" if r.returncode == 0 else "echec"
        except (OSError, subprocess.TimeoutExpired):
            etats[p["nom"]] = "echec"
    return etats


def read_runs(chemin):
    """Lit runs.jsonl du projet : (compteurs par résultat, liste des en-attente)."""
    path = os.path.join(chemin, ".claude", "orchestration", "runs.jsonl")
    compteurs, en_attente = {}, []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                res = r.get("resultat", "?")
                compteurs[res] = compteurs.get(res, 0) + 1
                if res == "en-attente-validation":
                    en_attente.append(
                        {"ts": r.get("ts"), "demande": (r.get("demande") or "")[:90]}
                    )
    except OSError:
        pass
    return compteurs, en_attente


def git_last_commit(chemin):
    """Date ISO du dernier commit (None si pas un repo / erreur)."""
    try:
        r = subprocess.run(
            ["git", "-C", chemin, "log", "-1", "--format=%cI"],
            capture_output=True, timeout=15, text=True,
        )
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


# --- Étage déterministe : analyse des pratiques (0 token) --------------------
# Ces dossiers ne sont jamais du code projet — exclus des comptes de test.
IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "_bmad",
               ".claude", ".agents", ".opencode", ".pytest_cache", "dist"}
TEST_PATTERNS = (
    re.compile(r"(^|[\\/])test[_-].*\.(py|js)$", re.I),
    re.compile(r".*[_-]test\.(py|js)$", re.I),
    re.compile(r".*\.(test|spec)\.(js|ts)$", re.I),
    re.compile(r".*smoke[_-]?test.*\.(py|js|ps1)$", re.I),
)
# Marqueurs de vérification fonctionnelle réelle (rend/lance un artefact réel).
# Inclut les tests qui montent un VRAI serveur HTTP et le sollicitent en réseau
# (ThreadingHTTPServer + urllib/http.client/httpx/requests) — c'est bien une vérif
# fonctionnelle réelle, pas un mock (cf. tests/test_serve_wiki.py, jusque-là non
# reconnu → VScode5 test-fonct faussement 🔴).
FONCTIONNEL_MARQUEURS = re.compile(
    r"puppeteer|playwright|win32com|comtypes|soffice|libreoffice|"
    r"pymupdf|fitz|Presentation\(|TestClient|smoke|"
    r"HTTPServer|serve_forever|urllib\.request|http\.client|httpx|"
    r"requests\.(get|post|put|delete|request)", re.I)


def _walk_code(chemin, max_files=4000):
    """Itère les fichiers de code projet (hors IGNORE_DIRS)."""
    n = 0
    for root, dirs, files in os.walk(chemin):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            yield os.path.join(root, f)
            n += 1
            if n >= max_files:
                return


def _niveau(ok, moyen):
    return "ok" if ok else ("moyen" if moyen else "absent")


# Pratique Anthropic (Claude Code best practices, adoptée via veille-agentic volet 2,
# 2026-07-24) : un CLAUDE.md trop long fait ignorer les règles importantes — « bloated
# CLAUDE.md files cause Claude to ignore your actual instructions ». Mesure 0 token.
CLAUDE_MD_MAX_LIGNES = 150


def claude_md_lignes(path):
    """Nombre de lignes du CLAUDE.md, ou None s'il n'existe pas / est illisible."""
    txt = read_text(path)
    if txt is None:
        return None
    return txt.count("\n") + (0 if txt.endswith("\n") else 1)


def claude_md_libelle(lignes):
    """Libellé wiki du critère CLAUDE.md : présence + alerte de taille au-delà du seuil."""
    if lignes is None:
        return None
    if lignes > CLAUDE_MD_MAX_LIGNES:
        return f"CLAUDE.md ⚠ {lignes} l (> {CLAUDE_MD_MAX_LIGNES} — élaguer)"
    return "CLAUDE.md"


def analyse_pratiques(chemin, skills, agents, livrable_deck=False):
    """7 dimensions déterministes (test tech, test fonctionnel, revue code,
    revue incrément, design, pratiques+rules, + proxies sécurité). Chaque
    dimension : {niveau: ok|moyen|absent|n/a, detail: str}."""
    tests, fonctionnels, code_py, code_js = [], [], 0, 0
    config_paths = []
    for path in _walk_code(chemin):
        rel = os.path.relpath(path, chemin)
        base = os.path.basename(path)
        if base.endswith(".py"):
            code_py += 1
        elif base.endswith(".js") and "min.js" not in base:
            code_js += 1
        if any(p.search(rel) or p.search(base) for p in TEST_PATTERNS):
            tests.append(rel)
            txt = read_text(path) or ""
            if FONCTIONNEL_MARQUEURS.search(txt):
                fonctionnels.append(rel)
        if base in ("requirements-dev.txt", "requirements.txt", "package.json"):
            config_paths.append(path)

    has_prod_code = (code_py + code_js) > 0
    settings = read_json(os.path.join(chemin, ".claude", "settings.json")) or {}
    settings_txt = json.dumps(settings)

    # 1. Test technique — le code de prod peut vivre sous un sous-dossier
    # (prototype imbriqué type comop-pptx-prototype/) : on cherche la config
    # de coverage partout dans l'arbre, pas seulement à la racine du projet.
    # Marqueurs d'un outil de couverture configuré. `"c8"` est cherché avec ses
    # guillemets (clé de package.json) pour ne pas matcher un substring d'un hash/
    # version — c8 est le coverage réel de VSCode1, jusque-là non reconnu (→ test-tech
    # faussement 🟠 malgré `test:cov` + c8 en devDependencies).
    coverage = any(
        m in (read_text(p) or "")
        for p in config_paths
        for m in ("pytest-cov", "coverage", "nyc", "--cov", '"c8"')
    )
    d_test = {
        "niveau": _niveau(len(tests) >= 3 and coverage,
                          len(tests) >= 1) if has_prod_code else "n/a",
        "detail": f"{len(tests)} fichier(s) de test"
                  + (", coverage configuré" if coverage else ", pas de coverage"),
    }

    # 2. Test fonctionnel / rendu réel
    d_fonct = {
        "niveau": _niveau(len(fonctionnels) >= 2, len(fonctionnels) >= 1),
        "detail": f"{len(fonctionnels)} test(s) à vérification réelle"
                  if fonctionnels else "aucune vérif fonctionnelle réelle détectée",
    }

    # 3. Revue de code
    reviewer = "reviewer" in agents
    warn_hook = os.path.isfile(
        os.path.join(chemin, ".claude", "hooks", "warn_verif_before_commit.py"))
    bmad_cr = "bmad-code-review" in skills
    d_revue_code = {
        "niveau": _niveau(reviewer or warn_hook, bmad_cr),
        "detail": ", ".join(filter(None, [
            "agent reviewer" if reviewer else None,
            "hook pré-commit" if warn_hook else None,
            "bmad-code-review" if bmad_cr else None])) or "aucun dispositif",
    }

    # 4. Revue d'incrément
    ri_skill = "revue-increment" in skills
    ri_hook = "remind_revue_increment" in settings_txt
    d_revue_incr = {
        "niveau": _niveau(ri_skill and ri_hook, ri_skill),
        "detail": ("skill + hook SessionStart" if ri_skill and ri_hook
                   else "skill seule" if ri_skill else "absente"),
    }

    # 5. Pratique de design (pertinente pour les projets qui produisent un deck)
    produit_deck = (livrable_deck
                    or "restitution-ppt" in skills
                    or any(os.path.isdir(os.path.join(chemin, d))
                           for d in ("Exports", "export")))
    design_review = "deck-design-review" in skills
    design_lib = "deck-design-library" in skills
    design_system = "restitution-deck-design" in skills  # skill globale, ~toujours là
    ppt_designer = "ppt-designer" in agents
    d_design = {
        "niveau": ("n/a" if not produit_deck else
                   _niveau(design_review and design_lib,
                           design_lib or ppt_designer)),
        "detail": ("ne produit pas de deck" if not produit_deck else
                   ", ".join(filter(None, [
                       "deck-design-review" if design_review else None,
                       "deck-design-library" if design_lib else None,
                       "ppt-designer" if ppt_designer else None,
                       "design-system" if design_system else None]))
                   or "aucune discipline design"),
    }

    # 5 bis. Documentation
    readme = os.path.isfile(os.path.join(chemin, "README.md"))
    readme_txt = read_text(os.path.join(chemin, "README.md")) or ""
    readme_utile = readme and re.search(
        r"(?i)##?\s*(install|usage|utilisation|démarr|getting started|lancer)", readme_txt)
    wiki_dir = os.path.join(chemin, "docs", "wiki")
    wiki = os.path.isdir(wiki_dir)
    wiki_html = os.path.isfile(os.path.join(chemin, "docs", "wiki.html"))
    claude_md_doc = os.path.isfile(os.path.join(chemin, "CLAUDE.md"))
    doc_score = sum([bool(readme_utile), wiki, claude_md_doc])
    d_doc = {
        "niveau": _niveau(doc_score >= 2 and bool(readme_utile),
                          readme or wiki or claude_md_doc),
        "detail": ", ".join(filter(None, [
            ("README+usage" if readme_utile else "README" if readme else None),
            ("wiki" + ("+html" if wiki_html else "") if wiki else None),
            "CLAUDE.md" if claude_md_doc else None])) or "aucune doc",
    }

    # 5 ter. Pratique produit / cadrage (persona, why, besoins, proposition de valeur)
    cadrage_txt = ""
    for rel in ("docs", "cadrage", "_bmad-output"):
        base = os.path.join(chemin, rel)
        if os.path.isdir(base):
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                for f in files:
                    if f.endswith((".md", ".txt")):
                        cadrage_txt += " " + f.lower()
                        if len(cadrage_txt) < 20000:
                            cadrage_txt += " " + (read_text(os.path.join(root, f)) or "")[:2000].lower()
    # artefacts BMAD de cadrage produit (product-brief, prd, prfaq, personas)
    bmad_produit = any(k in cadrage_txt for k in (
        "product-brief", "product brief", "brief produit"))
    marqueurs = {
        "persona": bool(re.search(r"persona", cadrage_txt)),
        "why": bool(re.search(r"\bwhy\b|pourquoi|raison d'être|problème à résoudre", cadrage_txt)),
        "besoins": bool(re.search(r"besoin|need|pain point|point de douleur", cadrage_txt)),
        "valeur": bool(re.search(r"proposition de valeur|value proposition|valeur (?:client|utilisateur|apportée)", cadrage_txt)),
    }
    prod_score = sum(marqueurs.values()) + (1 if bmad_produit else 0)
    d_produit = {
        "niveau": _niveau(prod_score >= 3, prod_score >= 1),
        "detail": ", ".join(k for k, v in marqueurs.items() if v)
                  + (" + brief BMAD" if bmad_produit else "")
                  or "aucun artefact de cadrage produit détecté",
    }

    # 6. Pratiques + rules
    linter = any(os.path.isfile(os.path.join(chemin, f)) for f in
                 ("eslint.config.js", ".eslintrc.js", ".eslintrc.json",
                  "pyproject.toml", ".flake8", "ruff.toml", ".prettierrc")) or \
        os.path.isfile(os.path.join(chemin, "app", "eslint.config.js"))
    ci = os.path.isdir(os.path.join(chemin, ".github", "workflows"))
    claude_lignes = claude_md_lignes(os.path.join(chemin, "CLAUDE.md"))
    claude_md = claude_lignes is not None
    conventions = os.path.isfile(
        os.path.join(chemin, "docs", "wiki", "technical", "conventions.md"))
    score = sum([linter, ci, claude_md, conventions])
    d_pratiques = {
        "niveau": _niveau(score >= 3, score >= 1),
        "detail": ", ".join(filter(None, [
            "linter" if linter else None, "CI" if ci else None,
            claude_md_libelle(claude_lignes),
            "conventions" if conventions else None])) or "rien de configuré",
    }

    # 6. Proxies sécurité (déterministes — pas un audit, des garde-fous présents)
    gitignore = read_text(os.path.join(chemin, ".gitignore")) or ""
    env_ignore = ".env" in gitignore
    deny_rules = bool((settings.get("permissions") or {}).get("deny"))
    guard_hook = "guard_destructive_git" in settings_txt
    env_committed = os.path.isfile(os.path.join(chemin, ".env")) and not env_ignore
    sec_score = sum([env_ignore, deny_rules, guard_hook])
    d_secu_proxy = {
        "niveau": "absent" if env_committed else _niveau(sec_score >= 2, sec_score >= 1),
        "detail": ("⚠ .env non gitigné" if env_committed else
                   ", ".join(filter(None, [
                       ".env gitigné" if env_ignore else None,
                       "deny rules" if deny_rules else None,
                       "guard git" if guard_hook else None])) or "aucun garde-fou"),
    }

    return {
        "test_technique": d_test,
        "test_fonctionnel": d_fonct,
        "revue_code": d_revue_code,
        "revue_increment": d_revue_incr,
        "design": d_design,
        "documentation": d_doc,
        "cadrage_produit": d_produit,
        "pratiques_rules": d_pratiques,
        "securite_proxy": d_secu_proxy,
    }


def list_dirs(path):
    try:
        return sorted(
            e for e in os.listdir(path) if os.path.isdir(os.path.join(path, e))
        )
    except OSError:
        return []


def list_md(path, exclude=()):
    try:
        return sorted(
            e[:-3]
            for e in os.listdir(path)
            if e.endswith(".md") and e not in exclude
        )
    except OSError:
        return []


def bmad_info(proj_path):
    manifest = read_text(os.path.join(proj_path, "_bmad", "_config", "manifest.yaml"))
    if not manifest:
        return None
    version = None
    m = re.search(r"^installation:\s*\n\s+version:\s*([\w.\-]+)", manifest, re.M)
    if m:
        version = m.group(1)
    modules = re.findall(r"^\s+- name:\s*(\w+)", manifest, re.M)
    return {"version": version, "modules": modules}


def hooks_info(proj_path):
    settings = read_json(os.path.join(proj_path, ".claude", "settings.json"))
    if not settings:
        return []
    return sorted((settings.get("hooks") or {}).keys())


def resolve_livrable(chemin, livrable):
    """Résout le livrable principal du projet en un lien affichable.

    - type "web"  : URL http (site à lancer) ou fichier local relatif (local: true).
    - type "deck" : dernier .pptx (par date de modification) du dossier configuré.
    Retourne {"type", "label", "href"} ou None.
    """
    if not isinstance(livrable, dict):
        return None
    if livrable.get("type") == "web":
        url = livrable.get("url", "")
        if livrable.get("local"):
            path = os.path.join(chemin, url)
            return {
                "type": "web",
                "label": os.path.basename(url),
                "href": "file:///" + path.replace("\\", "/"),
            }
        return {"type": "web", "label": url, "href": url}
    if livrable.get("type") == "deck":
        dossier = os.path.join(chemin, livrable.get("dossier", ""))
        motif = livrable.get("motif", ".pptx").lower()
        exclure = [x.lower() for x in livrable.get("exclure", [])]
        try:
            candidats = [
                os.path.join(dossier, f)
                for f in os.listdir(dossier)
                if f.lower().endswith(motif)
                and not any(x in f.lower() for x in exclure)
            ]
        except OSError:
            candidats = []
        if not candidats:
            return {"type": "deck", "label": "aucun deck trouvé", "href": ""}
        dernier = max(candidats, key=os.path.getmtime)
        return {
            "type": "deck",
            "label": os.path.basename(dernier),
            "href": "file:///" + dernier.replace("\\", "/"),
        }
    return None


def alert_level(findings):
    """Niveau d'alerte d'un projet d'après ses findings : 'critique' | 'majeur' | None."""
    prios = [f["priorite"] for f in findings]
    if any(p >= PRIO_CRITIQUE for p in prios):
        return "critique"
    if any(p >= PRIO_MAJEUR for p in prios):
        return "majeur"
    return None


def scan_project(nom, chemin, description, livrable=None):
    claude = os.path.join(chemin, ".claude")
    skills = list_dirs(os.path.join(claude, "skills"))
    agents = list_md(os.path.join(claude, "agents"))
    playbooks = list_md(
        os.path.join(claude, "orchestration", "playbooks"), exclude=("FORMAT.md",)
    )

    state = read_json(os.path.join(claude, "supervision", "state.json")) or {}
    usage_skills = state.get("skills") or {}
    usage_agents = state.get("subagents") or {}
    last_scan = state.get("last_scan")

    def count(entry):
        return entry.get("n", 0) if isinstance(entry, dict) else 0

    used = sorted(
        ((s, count(usage_skills[s])) for s in usage_skills if count(usage_skills[s]) > 0),
        key=lambda kv: -kv[1],
    )
    used_names = {s for s, _ in used}
    unused = [s for s in skills if s not in used_names]

    diagnostic = read_json(os.path.join(claude, "supervision", "diagnostic.json")) or {}
    diag_date = diagnostic.get("generated")
    runs_compteurs, runs_en_attente = read_runs(chemin)
    # Un finding dont la cible a été arbitrée (arbitrages.json) est clos par
    # décision humaine — même filtre que le scan étage 1 local.
    arbitrages = read_json(os.path.join(claude, "supervision", "arbitrages.json")) or {}
    cibles_arbitrees = {
        a.get("cible")
        for a in arbitrages.get("arbitrages", [])
        if isinstance(a, dict) and a.get("cible") and a.get("decision")
    }
    livrable_resolu = resolve_livrable(chemin, livrable)
    findings = [
        {
            "categorie": f.get("categorie", "?"),
            "priorite": f.get("priorite", 0),
            "cible": f.get("cible", ""),
            "titre": f.get("titre", ""),
        }
        for f in diagnostic.get("findings", [])
        if isinstance(f, dict) and f.get("cible") not in cibles_arbitrees
    ]

    return {
        "nom": nom,
        "chemin": chemin,
        "description": description,
        "existe": os.path.isdir(chemin),
        "livrable": livrable_resolu,
        "skills": skills,
        "agents": agents,
        "playbooks": playbooks,
        "bmad": bmad_info(chemin),
        "hooks": hooks_info(chemin),
        "skills_utilises": used,
        "skills_jamais_utilises": unused,
        "agents_utilises": sorted(
            ((a, count(usage_agents[a])) for a in usage_agents if count(usage_agents[a]) > 0),
            key=lambda kv: -kv[1],
        ),
        "last_scan": last_scan,
        "diag_date": diag_date,
        "runs_compteurs": runs_compteurs,
        "runs_en_attente": runs_en_attente,
        "dernier_commit": git_last_commit(chemin),
        "findings": findings,
        "alerte": alert_level(findings),
        "orchestration": "agent-orchestrator" in skills,
        "supervision": "agent-supervisor" in skills,
        "pratiques": analyse_pratiques(
            chemin, set(skills), set(agents),
            livrable_deck=bool(livrable_resolu and livrable_resolu.get("type") == "deck"),
        ),
        "audit": load_audit(nom),
    }


def load_audit(nom):
    """Audit qualitatif (robustesse/perf/risque/sécurité) écrit par la skill
    audit-technique dans .claude/audits/<nom>.json. None si pas encore audité.
    Format : {date, dimensions: {robustesse|performance|risque_technique|
    securite: {niveau: ok|moyen|critique, synthese: str}}}."""
    data = read_json(os.path.join(ROOT, ".claude", "audits", f"{nom}.json"))
    return data if isinstance(data, dict) else None


def load_deploy_manifest():
    """MANIFEST du package de déploiement (source, destination), lu dynamiquement
    depuis le script lui-même — jamais dupliqué ici, jamais périmé. None si le
    package est absent/en erreur (l'onglet Déploiement s'affiche quand même,
    sans le résumé chiffré)."""
    path = os.path.join(ROOT, ".claude", "dispositif", "package", "deploy_nouveau_projet.py")
    try:
        spec = importlib.util.spec_from_file_location("deploy_nouveau_projet", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.MANIFEST
    except Exception:
        return None


def load_veille():
    """Charge les résultats de veille (skill veille-agentic). Format :
    {"derniere_veille": iso, "entrees": [{"titre", "url", "type", "pertinence",
      "projets_concernes": [...], "date", "statut": "nouveau|etudie|adopte|ecarte"}]}
    """
    data = read_json(VEILLE_PATH)
    if not isinstance(data, dict):
        return {"derniere_veille": None, "entrees": []}
    entrees = [e for e in data.get("entrees", []) if isinstance(e, dict)]
    return {"derniere_veille": data.get("derniere_veille"), "entrees": entrees}


def fmt_count_list(pairs, limit=None):
    items = pairs[:limit] if limit else pairs
    s = ", ".join(f"{n} ({c})" for n, c in items)
    if limit and len(pairs) > limit:
        s += f", … +{len(pairs) - limit}"
    return s or "—"


ALERT_MD = {"critique": "🔴 critique", "majeur": "🟠 majeur", None: "✅"}

# Pastilles des dimensions de pratiques / audit
PASTILLE = {
    "ok": "🟢", "moyen": "🟠", "absent": "🔴", "critique": "🔴",
    "n/a": "⚪", None: "⚪",
}
DIM_DET = [
    ("test_technique", "Test tech."),
    ("test_fonctionnel", "Test fonct."),
    ("revue_code", "Revue code"),
    ("revue_increment", "Revue incr."),
    ("design", "Design"),
    ("documentation", "Doc"),
    ("cadrage_produit", "Cadrage produit"),
    ("pratiques_rules", "Pratiques+rules"),
    ("securite_proxy", "Sécu (proxy)"),
]
DIM_AUDIT = [
    ("robustesse", "Robustesse"),
    ("performance", "Perf."),
    ("risque_technique", "Risque tech."),
    ("securite", "Sécurité"),
]

# --- Catalogue des pratiques supervisées ------------------------------------
# Source de vérité, rendue *repliée* dans le wiki : pour chaque pratique, ce que
# le dispositif mesure, la règle de notation (🟢/🟠/🔴/⚪) telle qu'implémentée
# dans analyse_pratiques()/load_audit(), et le référentiel cible correspondant
# (docs/wiki/technical/criteres-pratiques.md). Éditer ICI quand la règle change —
# le tableau de mesure et ce catalogue restent alors cohérents.
PRAT_CAT_DET = [
    {
        "key": "test_technique", "lib": "Test technique",
        "mesure": "Compte les fichiers de test unitaires/techniques (motifs "
                  "test_*, *_test, *.spec/*.test) et détecte une couverture "
                  "configurée (pytest-cov, coverage, nyc, --cov).",
        "seuils": [("🟢 ok", "≥ 3 fichiers de test ET couverture configurée"),
                   ("🟠 moyen", "≥ 1 fichier de test"),
                   ("🔴 absent", "aucun test alors qu'il y a du code de prod"),
                   ("⚪ n/a", "le projet n'a pas de code applicatif")],
        "ref": "Pyramide de tests + ISO/IEC 25010 (§ 2 du référentiel).",
    },
    {
        "key": "test_fonctionnel", "lib": "Test fonctionnel / rendu réel",
        "mesure": "Parmi les tests, ceux qui vérifient l'artefact RÉEL : "
                  "marqueurs puppeteer, playwright, win32com/comtypes, "
                  "soffice/LibreOffice, pymupdf/fitz, Presentation(, TestClient, smoke.",
        "seuils": [("🟢 ok", "≥ 2 tests à vérification réelle"),
                   ("🟠 moyen", "≥ 1 test à vérification réelle"),
                   ("🔴 absent", "aucune vérif fonctionnelle réelle détectée")],
        "ref": "e2e réels de la pyramide — tester le livrable, pas seulement la "
               "logique (§ 2).",
    },
    {
        "key": "revue_code", "lib": "Revue de code",
        "mesure": "Présence d'un dispositif de revue : agent reviewer dédié OU "
                  "hook pré-commit warn_verif_before_commit.py (fort) ; skill "
                  "bmad-code-review générique (faible).",
        "seuils": [("🟢 ok", "agent reviewer OU hook pré-commit présent"),
                   ("🟠 moyen", "bmad-code-review seul (générique, non forcé)"),
                   ("🔴 absent", "aucun dispositif de revue")],
        "ref": "DORA — revue systématique avant merge/commit (§ 1).",
    },
    {
        "key": "revue_increment", "lib": "Revue d'incrément",
        "mesure": "Skill revue-increment + son hook SessionStart "
                  "(remind_revue_increment) qui la rappelle en cadence.",
        "seuils": [("🟢 ok", "skill + hook SessionStart"),
                   ("🟠 moyen", "skill seule (pas de rappel automatique)"),
                   ("🔴 absent", "pas de revue d'incrément")],
        "ref": "Cadence de revue de fin d'incrément (leçon flotte — diff relu, "
               "exigences recochées).",
    },
    {
        "key": "design", "lib": "Pratique de design (deck)",
        "mesure": "Pour les projets à livrable deck : discipline de design de "
                  "slide — deck-design-review (contrat par slide) + "
                  "deck-design-library ; à défaut agent ppt-designer.",
        "seuils": [("🟢 ok", "deck-design-review ET deck-design-library"),
                   ("🟠 moyen", "deck-design-library OU ppt-designer seul"),
                   ("🔴 absent", "aucune discipline de design"),
                   ("⚪ n/a", "le projet ne produit pas de deck")],
        "ref": "Design par contrat de slide, pas par impression (companion "
               "restitution-deck-design).",
    },
    {
        "key": "documentation", "lib": "Documentation",
        "mesure": "Porte d'entrée et référence : README avec section "
                  "install/usage, wiki (docs/wiki), CLAUDE.md.",
        "seuils": [("🟢 ok", "≥ 2 dispositifs dont un README avec install/usage"),
                   ("🟠 moyen", "au moins un README, wiki ou CLAUDE.md"),
                   ("🔴 absent", "aucune documentation")],
        "ref": "Diátaxis — tutorial / how-to / référence / explication (§ 3).",
    },
    {
        "key": "cadrage_produit", "lib": "Cadrage produit",
        "mesure": "Marqueurs de discovery dans docs/cadrage/_bmad-output : "
                  "persona, why/problème, besoins/pain points, proposition de "
                  "valeur, + artefact product-brief/PRD BMAD.",
        "seuils": [("🟢 ok", "≥ 3 marqueurs de cadrage (ou marqueurs + brief BMAD)"),
                   ("🟠 moyen", "≥ 1 marqueur"),
                   ("🔴 absent", "aucun artefact de cadrage produit")],
        "ref": "4 risques de Cagan + Opportunity Solution Tree de Torres (§ 4).",
    },
    {
        "key": "pratiques_rules", "lib": "Pratiques + rules",
        "mesure": "Outillage projet : linter (ruff/ESLint/flake8/prettier/"
                  "pyproject), CI (.github/workflows), CLAUDE.md, conventions.md.",
        "seuils": [("🟢 ok", "≥ 3 des 4 dispositifs"),
                   ("🟠 moyen", "≥ 1 dispositif"),
                   ("🔴 absent", "rien de configuré")],
        "ref": "DORA capabilities — version control, linter, CI, rules "
               "explicites (§ 1).",
    },
    {
        "key": "securite_proxy", "lib": "Sécurité (proxy)",
        "mesure": "Garde-fous PRÉSENTS (pas un audit de failles) : .env gitigné, "
                  "deny rules dans settings.json, hook guard_destructive_git. "
                  "Alerte si un .env est commité.",
        "seuils": [("🟢 ok", "≥ 2 garde-fous présents"),
                   ("🟠 moyen", "≥ 1 garde-fou"),
                   ("🔴 absent", "aucun garde-fou — ou .env non gitigné")],
        "ref": "OWASP ASVS 5.0 + SAMM — proxy de maturité, l'audit qualitatif "
               "cherche les failles réelles (§ 5).",
    },
]
# Répertoire des pratiques craft (software craftsmanship) suivies côté
# développement : le principe, comment la flotte l'implémente, et par quelle
# mesure du dispositif on le constate (ou ⬜ = pas encore outillé). Source :
# criteres-pratiques.md § 1 (DORA) & § 2 (tests) + dimensions du scan.
# statut : "ok" implémenté & mesuré · "moyen" partiel/incomplet · "absent" gap outil.
CRAFT_PRATIQUES = [
    {"nom": "Gestion de version pour tout", "statut": "ok",
     "principe": "Code, config et scripts sous contrôle de version, historique propre.",
     "flotte": "6/6 en dépôt git ; règle R2 « commit scopé au périmètre » (hub).",
     "mesure": "Cadence dernier commit + détection de dette non commitée."},
    {"nom": "Petits commits scopés", "statut": "moyen",
     "principe": "Commits atomiques, un changement = un commit, message clair.",
     "flotte": "Règle CLAUDE.md (R2) ; discipline, appliquée au cas par cas.",
     "mesure": "⬜ non auto-détecté (taille/scope des commits non mesurés)."},
    {"nom": "Tests automatisés (dont TDD)", "statut": "ok",
     "principe": "Tests unitaires rapides sur la logique métier, écrits tôt.",
     "flotte": "Fichiers de test + couverture (VSCode1 84,7 % / VSCode2 ~38 %).",
     "mesure": "Dimension Test technique (compte de tests + coverage)."},
    {"nom": "Tests fonctionnels bout-en-bout réels", "statut": "ok",
     "principe": "Vérifier l'artefact RÉEL (rendu, PDF re-parsé, navigateur), pas un mock.",
     "flotte": "Marqueurs puppeteer/playwright/pymupdf/Presentation(/TestClient.",
     "mesure": "Dimension Test fonctionnel / rendu réel."},
    {"nom": "Intégration continue", "statut": "moyen",
     "principe": "Build + tests rejoués à chaque push, feedback rapide.",
     "flotte": "CI GitHub Actions présente sur VSCode1 seulement (1/6).",
     "mesure": "Dimension Pratiques + rules (présence .github/workflows)."},
    {"nom": "Revue de code systématique", "statut": "ok",
     "principe": "Tout changement relu avant merge/commit (4 yeux ou outil).",
     "flotte": "Agent reviewer + hook pré-commit (VSCode1) ; bmad-code-review ailleurs.",
     "mesure": "Dimension Revue de code."},
    {"nom": "Revue d'incrément", "statut": "ok",
     "principe": "Fin d'itération : diff relu, exigences recochées avant de clore.",
     "flotte": "Skill revue-increment + hook SessionStart de rappel.",
     "mesure": "Dimension Revue d'incrément."},
    {"nom": "Analyse statique / linter", "statut": "moyen",
     "principe": "Style et erreurs détectés automatiquement (ruff, ESLint).",
     "flotte": "ESLint (JS) sur VSCode1 ; aucun linter Python sur la flotte (finding ouvert).",
     "mesure": "Dimension Pratiques + rules (présence linter)."},
    {"nom": "Refactoring continu / dette maîtrisée", "statut": "ok",
     "principe": "Boy-scout rule : laisser le code plus propre, dette suivie.",
     "flotte": "Constatée à la lecture du code (duplication, couplage, code mort).",
     "mesure": "Audit qualitatif — dimension Risque technique."},
    {"nom": "Simple design / YAGNI", "statut": "ok",
     "principe": "Le design le plus simple qui passe les tests, pas de code mort.",
     "flotte": "Code mort et sur-ingénierie relevés à l'audit.",
     "mesure": "Audit qualitatif — dimension Risque technique."},
    {"nom": "Dépendances épinglées / build reproductible", "statut": "ok",
     "principe": "Versions figées (lockfile), build déterministe.",
     "flotte": "Lockfile OK sur VSCode1 ; VSCode2 en `>=` (constat d'audit).",
     "mesure": "Audit qualitatif — dimension Risque technique."},
    {"nom": "Conventions de code explicites", "statut": "ok",
     "principe": "Règles partagées écrites (nommage, structure, rules d'agent).",
     "flotte": "CLAUDE.md + conventions.md sur les projets outillés.",
     "mesure": "Dimension Pratiques + rules (CLAUDE.md, conventions)."},
    {"nom": "Trunk-based development", "statut": "absent",
     "principe": "Branches courtes (< 3 actives), intégration fréquente au tronc.",
     "flotte": "Non outillé — mesurable via `git branch` (écart à combler).",
     "mesure": "⬜ pas encore mesuré (cible du référentiel § 1)."},
    {"nom": "Automatisation du déploiement", "statut": "absent",
     "principe": "Déploiement scripté et rejouable, pas d'étape manuelle.",
     "flotte": "Aucun projet outillé — pertinence à évaluer (projets locaux).",
     "mesure": "⬜ pas mesuré (cible du référentiel § 1)."},
    {"nom": "Test de non-régression sur bug corrigé", "statut": "absent",
     "principe": "Chaque bug fermé laisse un test qui échouerait s'il revenait.",
     "flotte": "Discipline à documenter dans les conventions — non détectable.",
     "mesure": "⬜ non détectable automatiquement (cible § 2)."},
]

PRAT_CAT_AUDIT = [
    {
        "key": "robustesse", "lib": "Robustesse",
        "mesure": "Lecture du code : gestion d'erreur, cas limites, entrées non "
                  "validées, échecs silencieux (except: pass), idempotence, "
                  "absence de rollback.",
        "seuils": [("🟢 ok / 🟠 moyen / 🔴 critique",
                    "verdict qualitatif, findings localisés fichier:ligne")],
        "ref": "ISO 25010 (fiabilité) + tests d'erreur/cas limites (§ 2).",
    },
    {
        "key": "performance", "lib": "Performance",
        "mesure": "Lecture du code : boucles imbriquées sur gros volumes, I/O "
                  "dans une boucle, requêtes N+1, absence de cache/pagination, "
                  "rendu synchrone bloquant.",
        "seuils": [("🟢 ok / 🟠 moyen / 🔴 critique",
                    "verdict qualitatif, findings localisés fichier:ligne")],
        "ref": "ISO 25010 (efficacité de performance).",
    },
    {
        "key": "risque_technique", "lib": "Risque technique",
        "mesure": "Lecture du code : dette structurelle — duplication logique, "
                  "couplage fort, dépendance non épinglée, code mort, fonction "
                  "trop longue, chemin critique sans test.",
        "seuils": [("🟢 ok / 🟠 moyen / 🔴 critique",
                    "verdict qualitatif, findings localisés fichier:ligne")],
        "ref": "DORA — build reproductible, dépendances épinglées (§ 1).",
    },
    {
        "key": "securite", "lib": "Sécurité (audit)",
        "mesure": "Lecture du code : secrets en clair/commités, injection "
                  "(SQL/commande/template), désérialisation non sûre "
                  "(eval/pickle), chemins utilisateur non assainis, shell=True, "
                  "permissions trop larges.",
        "seuils": [("🟢 ok / 🟠 moyen / 🔴 critique",
                    "verdict qualitatif, findings localisés fichier:ligne")],
        "ref": "OWASP ASVS 5.0 (~350 exigences, 17 chapitres) + SAMM (§ 5).",
    },
]


def compute_pilotage(projects, veille, now_dt):
    """Agrège les signaux du poste de pilotage : runs à solder, cadences périmées,
    décisions en attente d'arbitrage humain."""
    existants = [p for p in projects if p["existe"]]
    en_alerte = [p for p in existants if p["alerte"]]

    runs_a_solder = []
    for p in existants:
        for r in p["runs_en_attente"]:
            ts = parse_iso(r["ts"])
            runs_a_solder.append({
                "projet": p["nom"],
                "ts": ts,
                "demande": r["demande"],
                "age": age_str(ts, now_dt),
                "en_retard": ts is None
                or (now_dt - ts) > dt.timedelta(hours=RUN_A_SOLDER_H),
            })
    runs_a_solder.sort(key=lambda r: r["ts"] or dt.datetime.min)

    cadences = []
    retards = []
    for p in existants:
        scan_d = parse_iso(p["last_scan"])
        diag_d = parse_iso(p["diag_date"])
        commit_d = parse_iso(p["dernier_commit"])
        row = {
            "projet": p["nom"],
            "scan": (scan_d, est_perime(scan_d, CADENCE_SCAN_J, now_dt)),
            "diagnostic": (diag_d, est_perime(diag_d, CADENCE_DIAGNOSTIC_J, now_dt)),
            "commit": (commit_d, est_perime(commit_d, CADENCE_COMMIT_J, now_dt)),
        }
        cadences.append(row)
        if row["scan"][1]:
            retards.append(f"{p['nom']} : scan étage 1 périmé ({age_str(scan_d, now_dt)})")
        if row["diagnostic"][1]:
            retards.append(
                f"{p['nom']} : diagnostic étage 2 à relancer ({age_str(diag_d, now_dt)})"
            )
        if row["commit"][1]:
            retards.append(
                f"{p['nom']} : dernier commit {age_str(commit_d, now_dt)}"
            )

    veille_d = parse_iso(veille["derniere_veille"])
    veille_perimee = est_perime(veille_d, CADENCE_VEILLE_J, now_dt)
    if veille_perimee:
        retards.append(f"veille agentic à lancer ({age_str(veille_d, now_dt)})")

    return {
        "nb_projets": len(existants),
        "en_alerte": en_alerte,
        "runs_a_solder": runs_a_solder,
        "cadences": cadences,
        "retards": retards,
        "veille": (veille_d, veille_perimee),
    }


def render_md(projects, veille, now, pilotage, now_dt):
    pil = pilotage
    lines = [
        "# Supervision multi-projets — agents, skills, playbooks",
        "",
        f"_Généré le {now} par `scripts/scan_projets.py` — ne pas éditer à la main._",
        "",
        "## Poste de pilotage",
        "",
        f"**{pil['nb_projets']} projets** · "
        f"**{len(pil['en_alerte'])} en alerte** "
        f"({', '.join(p['nom'] + ' ' + ALERT_MD[p['alerte']] for p in pil['en_alerte']) or '—'}) · "
        f"**{len(pil['runs_a_solder'])} run(s) à solder** · "
        f"**{len(pil['retards'])} retard(s) de cadence**",
        "",
    ]
    if pil["runs_a_solder"]:
        lines.append("**Runs `en-attente-validation` à solder** (valider ou requalifier) :")
        for r in pil["runs_a_solder"]:
            marque = " ⚠" if r["en_retard"] else ""
            lines.append(f"- [{r['projet']}] {r['age']}{marque} — {r['demande']}")
        lines.append("")
        lines.append(
            "_Solder (dans le projet concerné) : `py .claude/orchestration/log_run.py "
            "--solde <prefixe-ts> succes \"note de validation\"`_"
        )
        lines.append("")
    if pil["retards"]:
        lines.append("**Retards de cadence** :")
        lines += [f"- {t}" for t in pil["retards"]]
        lines.append("")
    lines += [
        "### Cadences",
        "",
        "| Projet | Scan étage 1 | Diagnostic étage 2 | Dernier commit |",
        "| --- | --- | --- | --- |",
    ]
    for c in pil["cadences"]:
        def cell(pair):
            d, perime = pair
            return f"{'🟠 ' if perime else ''}{age_str(d, now_dt)}"
        lines.append(
            f"| {c['projet']} | {cell(c['scan'])} | {cell(c['diagnostic'])} | {cell(c['commit'])} |"
        )
    veille_d, veille_perimee = pil["veille"]
    lines += [
        "",
        f"Veille agentic : {'🟠 ' if veille_perimee else ''}{age_str(veille_d, now_dt)} "
        f"(cadence {CADENCE_VEILLE_J} j).",
        "",
        "## 1. Supervision des projets",
        "",
        "| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for p in projects:
        if not p["existe"]:
            lines.append(f"| {p['nom']} | — | introuvable | — | — | — | — | — | — | — |")
            continue
        bmad = (
            f"{p['bmad']['version']} ({'+'.join(p['bmad']['modules'])})"
            if p["bmad"]
            else "—"
        )
        liv = p["livrable"]
        if liv and liv["href"]:
            icone = "🌐" if liv["type"] == "web" else "📊"
            liv_md = f"{icone} [{liv['label']}]({liv['href']})"
        elif liv:
            liv_md = f"⚠ {liv['label']}"
        else:
            liv_md = "—"
        lines.append(
            f"| {p['nom']} | {liv_md} | {bmad} | {len(p['skills'])} | {len(p['agents'])} | "
            f"{len(p['playbooks'])} | {'✅' if p['orchestration'] else '❌'} | "
            f"{'✅' if p['supervision'] else '❌'} | {', '.join(p['hooks']) or '—'} | "
            f"{ALERT_MD[p['alerte']]} |"
        )
    lines.append("")
    lines.append(
        "_Alerte : niveau du finding le plus haut du diagnostic superviseur local "
        f"(p{PRIO_CRITIQUE} = critique, p{PRIO_MAJEUR} = majeur)._"
    )
    lines.append("")

    for p in projects:
        if not p["existe"]:
            continue
        badge = ALERT_MD[p["alerte"]]
        lines += [
            f"### {p['nom']} — {p['description']} [{badge}]",
            "",
            f"Chemin : `{p['chemin']}`",
            "",
        ]
        if p["last_scan"]:
            lines.append(f"Dernier scan superviseur local : {p['last_scan']}")
            lines.append("")
        lines.append(
            f"**Skills utilisés** ({len(p['skills_utilises'])}) : "
            + fmt_count_list(p["skills_utilises"])
        )
        lines.append("")
        nb_bmad = sum(1 for s in p["skills_jamais_utilises"] if s.startswith("bmad-"))
        autres = [s for s in p["skills_jamais_utilises"] if not s.startswith("bmad-")]
        lines.append(
            f"**Skills jamais utilisés** ({len(p['skills_jamais_utilises'])}) : "
            f"{nb_bmad} bmad-* + {', '.join(autres) or 'aucun autre'}"
        )
        lines.append("")
        if p["agents"]:
            lines.append(f"**Sous-agents** ({len(p['agents'])}) : {', '.join(p['agents'])}")
            if p["agents_utilises"]:
                lines.append(
                    f"**Sous-agents utilisés** : {fmt_count_list(p['agents_utilises'])}"
                )
            lines.append("")
        if p["playbooks"]:
            lines.append(f"**Playbooks** : {', '.join(p['playbooks'])}")
            lines.append("")
        if p["runs_compteurs"]:
            total = sum(p["runs_compteurs"].values())
            detail = ", ".join(f"{k} ×{v}" for k, v in sorted(p["runs_compteurs"].items()))
            lines.append(f"**Runs d'orchestration** : {total} ({detail})")
            lines.append("")
        if p["findings"]:
            lines.append("**Diagnostic superviseur local (findings ouverts)** :")
            for f in sorted(p["findings"], key=lambda x: -x["priorite"]):
                lines.append(
                    f"- p{f['priorite']} `{f['categorie']}` [{f['cible']}] — {f['titre']}"
                )
            lines.append("")

    # ---- Section : pratiques, couverture & risques --------------------------
    existants = [p for p in projects if p["existe"]]
    lines += [
        "## 2. Pratiques, couverture & risques",
        "",
        "_Cible : le [référentiel de critères](technical/criteres-pratiques.md) "
        "(DORA, pyramide de tests/ISO 25010, Diátaxis, Cagan/Torres, OWASP ASVS/SAMM, "
        "DAMA-DMBOK) — ce qui suit est la MESURE ; l'écart mesure↔référentiel alimente "
        "les findings `pratique-*` du superviseur._",
        "",
        "### Référentiel des pratiques supervisées",
        "",
        "_Les 13 pratiques mesurées, avec la règle de notation et le référentiel "
        "cible (déplié ici ; replié dans `docs/wiki.html`)._",
        "",
        "#### Pratiques craft (développement)",
        "",
        "_🟢 implémenté & mesuré · 🟠 partiel · 🔴 pas encore outillé._",
        "",
        "| Pratique | Principe | Dans la flotte | Mesure |",
        "| --- | --- | --- | --- |",
    ]
    for c in CRAFT_PRATIQUES:
        lines.append(
            f"| {PASTILLE[c['statut']]} {c['nom']} | {c['principe']} | "
            f"{c['flotte']} | {c['mesure']} |")
    lines += [
        "",
        "_Source : référentiel § 1 (DORA) & § 2 (pyramide de tests) + dimensions du scan._",
        "",
    ]
    for titre, cat in (
        ("Étage déterministe (à chaque scan, 0 token)", PRAT_CAT_DET),
        ("Étage qualitatif (audit-technique à la demande)", PRAT_CAT_AUDIT),
    ):
        lines.append(f"**{titre}**")
        lines.append("")
        for pr in cat:
            regles = " ; ".join(f"{n} = {r}" for n, r in pr["seuils"])
            lines.append(f"- **{pr['lib']}** — {pr['mesure']} _Notation :_ "
                         f"{regles}. _Réf. :_ {pr['ref']}")
        lines.append("")
    lines += [
        "**Étage déterministe** (mesuré à chaque scan, 0 token — présence de dispositifs) :",
        "",
        "| Projet | " + " | ".join(lib for _, lib in DIM_DET) + " |",
        "| --- | " + " | ".join("---" for _ in DIM_DET) + " |",
    ]
    for p in existants:
        cells = []
        for key, _ in DIM_DET:
            dim = p["pratiques"][key]
            cells.append(f"{PASTILLE[dim['niveau']]} {dim['detail']}")
        lines.append(f"| {p['nom']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "🟢 ok · 🟠 moyen · 🔴 absent/manquant · ⚪ non applicable. "
        "Sécu (proxy) = garde-fous présents (.env gitigné, deny rules, guard git), "
        "PAS un audit de failles.",
        "",
        "**Étage qualitatif** (audit `audit-technique` à la demande — lit le code) :",
        "",
        "_Ce que couvre l'audit (chaque dimension = lecture du code réel, findings localisés"
        " `fichier:ligne`, niveau ok / moyen / critique) :_",
        "",
        "- **Robustesse** — gestion d'erreur, cas limites, entrées non validées, échecs"
        " silencieux (`except: pass`), idempotence, absence de rollback.",
        "- **Performance** — boucles imbriquées sur gros volumes, I/O dans une boucle,"
        " requêtes N+1, absence de cache/pagination, rendu synchrone bloquant.",
        "- **Risque technique** — dette structurelle : duplication logique, couplage fort,"
        " dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test.",
        "- **Sécurité** — secrets en clair/commités, injection (SQL/commande/template),"
        " désérialisation non sûre (`eval`/`pickle`), chemins utilisateur non assainis,"
        " `shell=True`, permissions trop larges.",
        "",
        "| Projet | " + " | ".join(lib for _, lib in DIM_AUDIT) + " | Audité le |",
        "| --- | " + " | ".join("---" for _ in DIM_AUDIT) + " | --- |",
    ]
    for p in existants:
        audit = p["audit"]
        if not audit:
            lines.append(
                f"| {p['nom']} | " + " | ".join("⚪ non audité" for _ in DIM_AUDIT)
                + " | — |"
            )
            continue
        dims = audit.get("dimensions", {})
        cells = []
        for key, _ in DIM_AUDIT:
            d = dims.get(key) or {}
            cells.append(f"{PASTILLE.get(d.get('niveau'))} {d.get('niveau', '?')}")
        lines.append(f"| {p['nom']} | " + " | ".join(cells)
                     + f" | {audit.get('date', '?')} |")
    lines += [
        "",
        "_Lancer un audit : skill `audit-technique` sur le projet cible "
        "(robustesse, performance, risque technique, failles de sécurité — lecture du code)._",
        "",
        "## 3. Veille agentic",
        "",
    ]
    if veille["derniere_veille"]:
        lines.append(f"_Dernière veille : {veille['derniere_veille']} — skill `veille-agentic` "
                     "(cadence 3 jours, déclenchable manuellement)._")
    else:
        lines.append("_Aucune veille enregistrée — lancer la skill `veille-agentic`._")
    lines.append("")
    # Volet 1 (écosystème : outils/skills/frameworks) et volet 2 (pratiques providers)
    # rendus séparément — les entrées `pratique` portent règle d'analyse + action corrective.
    outils = [e for e in veille["entrees"] if e.get("type") != "pratique"]
    pratiques = [e for e in veille["entrees"] if e.get("type") == "pratique"]
    if outils:
        lines.append("| Sujet | Type | Statut | Projets concernés | Pertinence |")
        lines.append("| --- | --- | --- | --- | --- |")
        for e in outils:
            lines.append(
                f"| [{e.get('titre', '?')}]({e.get('url', '')}) | {e.get('type', '?')} | "
                f"{e.get('statut', 'nouveau')} | {', '.join(e.get('projets_concernes', []) or ['—'])} | "
                f"{e.get('pertinence', '')} |"
            )
        lines.append("")
    if pratiques:
        lines.append("### Pratiques agentic repérées (docs providers)")
        lines.append("")
        lines.append("_Volet 2 de `veille-agentic` : pratiques recommandées par les providers, comparées à "
                     "l'état réel de la flotte. `adopte` (décision utilisateur) => la règle proposée entre au "
                     "référentiel (`criteres-pratiques.md` § 7) et l'action corrective se traite via "
                     "`evolution-flotte`._")
        lines.append("")
        lines.append("| Pratique | Source | Statut | Projets | Règle d'analyse proposée | Action corrective |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for e in pratiques:
            lines.append(
                f"| [{e.get('titre', '?')}]({e.get('url', '')}) | {e.get('source_referentiel', '?')} | "
                f"{e.get('statut', 'nouveau')} | {', '.join(e.get('projets_concernes', []) or ['—'])} | "
                f"{e.get('regle_proposee', '')} | {e.get('action_corrective', '')} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


HTML_HEAD = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Supervision multi-projets</title>
<style>
:root {
  --ink: #1b2536; --ink-soft: #5a6577; --line: #e4e8ef; --line-strong: #cfd6e0;
  --bg: #f5f7fa; --surface: #ffffff; --surface-2: #f8fafc;
  --brand: #12335a; --brand-2: #1d4e86; --brand-ink: #eaf1fb;
  --accent: #2f6fb0;
  --green: #17803d; --green-bg: #e6f4ea; --amber: #b7791f; --amber-bg: #fbf1de;
  --red: #c0362c; --red-bg: #fbe9e7; --neutral: #7a8699; --neutral-bg: #eef1f5;
  --shadow: 0 1px 3px rgba(18,51,90,.06), 0 6px 20px rgba(18,51,90,.05);
  --radius: 12px;
}
* { box-sizing: border-box; }
body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
       margin: 0 auto; max-width: 1180px; padding: 2.4rem 1.3rem 4rem;
       color: var(--ink); background: var(--bg); line-height: 1.5;
       -webkit-font-smoothing: antialiased; }
h1 { font-size: 1.85rem; letter-spacing: -.02em; margin: 0 0 .2rem; }
h2 { font-size: 1.28rem; letter-spacing: -.01em; color: var(--brand);
     margin: 2.8rem 0 .8rem; padding-bottom: .4rem;
     border-bottom: 2px solid var(--line-strong); }
h3 { font-size: 1.02rem; color: var(--brand-2); margin: 1.4rem 0 .5rem; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--neutral-bg); border-radius: 4px; padding: .05rem .35rem;
       font-size: .86em; font-family: "Cascadia Code", ui-monospace, Consolas, monospace; }

/* --- Tables : légères, lisibles, sans grille lourde --- */
table { border-collapse: separate; border-spacing: 0; width: 100%;
        margin: 1rem 0; font-size: .9rem; background: var(--surface);
        border: 1px solid var(--line); border-radius: var(--radius);
        overflow: hidden; box-shadow: var(--shadow); }
th, td { padding: .6rem .75rem; text-align: left; vertical-align: top;
         border-bottom: 1px solid var(--line); }
th { background: var(--surface-2); color: var(--brand); font-weight: 600;
     font-size: .78rem; text-transform: uppercase; letter-spacing: .04em;
     border-bottom: 2px solid var(--line-strong); }
tbody tr:last-child td, tr:last-child td { border-bottom: none; }
table tr:hover td { background: var(--surface-2); }

.ok { color: var(--green); font-weight: 600; }
.ko { color: var(--red); font-weight: 600; }
.muted { color: var(--ink-soft); font-size: .85rem; }

.badge { display: inline-block; background: var(--neutral-bg); color: var(--ink);
         border-radius: 999px; padding: .12rem .6rem; margin: .12rem .12rem;
         font-size: .8rem; border: 1px solid transparent; }
.badge.hot { background: var(--green-bg); color: #0f5c2b; border-color: #c3e6cd; }
.badge.cold { background: var(--surface-2); color: var(--ink-soft);
              border-color: var(--line); }

.alert-critique, .alert-majeur, .alert-ok {
  display: inline-block; border-radius: 999px; padding: .12rem .6rem;
  font-size: .76rem; font-weight: 700; letter-spacing: .01em; }
.alert-critique { background: var(--red-bg); color: var(--red); }
.alert-majeur { background: var(--amber-bg); color: var(--amber); }
.alert-ok { background: var(--green-bg); color: var(--green); }

.finding { margin: .35rem 0; padding: .4rem .7rem; background: var(--amber-bg);
           border-left: 3px solid var(--amber); border-radius: 0 6px 6px 0;
           font-size: .88rem; }
.prio-high { background: var(--red-bg); border-left-color: var(--red); }

/* --- Details / accordéons --- */
details { margin: .7rem 0; background: var(--surface);
          border: 1px solid var(--line); border-radius: var(--radius);
          box-shadow: var(--shadow); overflow: hidden; }
details > summary { cursor: pointer; padding: .75rem 1rem; font-weight: 600;
                    list-style: none; display: flex; align-items: center;
                    gap: .6rem; transition: background .12s; }
details > summary::-webkit-details-marker { display: none; }
details > summary:hover { background: var(--surface-2); }
details > summary::before { content: "▸"; color: var(--accent);
                            transition: transform .15s; font-size: .85em; }
details[open] > summary::before { transform: rotate(90deg); }
details[open] > summary { border-bottom: 1px solid var(--line); }
details > div { padding: .7rem 1.15rem 1.1rem; }

.statut-nouveau { color: var(--accent); font-weight: 600; }
.statut-adopte { color: var(--green); font-weight: 600; }
.statut-ecarte { color: var(--ink-soft); }

/* --- Poste de pilotage --- */
.pilotage { background: linear-gradient(135deg, var(--brand) 0%, var(--brand-2) 100%);
            color: #fff; border-radius: 16px; padding: 1.4rem 1.6rem;
            margin: 1.4rem 0 2rem; box-shadow: 0 10px 30px rgba(18,51,90,.18); }
.pilotage .chiffres { display: flex; gap: 1rem; flex-wrap: wrap;
                      margin-bottom: .8rem; }
.pilotage .chiffre { text-align: center; background: rgba(255,255,255,.08);
                     border: 1px solid rgba(255,255,255,.14); border-radius: 12px;
                     padding: .7rem 1.2rem; min-width: 5.2rem; }
.pilotage .chiffre b { display: block; font-size: 1.9rem; line-height: 1;
                       letter-spacing: -.02em; }
.pilotage .chiffre span { font-size: .74rem; opacity: .82;
                          text-transform: uppercase; letter-spacing: .05em; }
.pilotage b { font-weight: 600; }
.pilotage ul { margin: .5rem 0 .2rem; padding: 0; list-style: none;
               font-size: .9rem; }
.pilotage li { margin: .3rem 0; padding-left: 1rem; position: relative; }
.pilotage li::before { content: "•"; position: absolute; left: 0; opacity: .6; }
.pilotage .retard { color: #ffd88f; }
.pilotage .solder { color: #ffb9b0; }
.pilotage code { background: rgba(255,255,255,.14); color: #eaf1fb; }

.cadence-ok { color: var(--green); }
.cadence-perime { color: var(--amber); font-weight: 600; }

/* --- Section pratiques --- */
.prat table { font-size: .82rem; }
.prat td .lvl { font-weight: 600; font-size: 1rem; }
.prat td small { color: var(--ink-soft); display: block; font-size: .76rem;
                 margin-top: .15rem; }
.legende { font-size: .82rem; color: var(--ink-soft); margin: .4rem 0 1.1rem; }

/* --- Catalogue replié des pratiques supervisées --- */
.catalogue-wrap { background: var(--surface-2); }
.catalogue { padding: .3rem 0 .2rem; }
.cat-groupe { font-size: .82rem; text-transform: uppercase; letter-spacing: .05em;
              color: var(--ink-soft); border-top: 1px solid var(--line);
              padding-top: .9rem; margin: 1.1rem 0 .4rem; }
.prat-card { margin: .45rem 0; box-shadow: none; border: 1px solid var(--line); }
.prat-card > summary { padding: .55rem .85rem; font-size: .94rem; }
.prat-card.det > summary { border-left: 3px solid var(--accent); }
.prat-card.audit > summary { border-left: 3px solid var(--amber); }
.prat-nom { font-weight: 600; }
.prat-body { padding: .3rem .95rem .9rem; font-size: .88rem; }
.prat-mesure { margin: .3rem 0 .6rem; }
.prat-ref { margin: .6rem 0 0; color: var(--ink-soft); font-size: .84rem; }
table.seuils { margin: .3rem 0; box-shadow: none; font-size: .83rem; }
table.seuils th { font-size: .7rem; }
table.seuils .seuil-n { white-space: nowrap; font-weight: 600; }
table.craft { margin: .4rem 0; box-shadow: none; font-size: .82rem; }
table.craft th { font-size: .68rem; }
table.craft .craft-p { font-weight: 600; white-space: nowrap; }
table.craft .craft-p .lvl { font-weight: 400; }
table.craft .craft-m { color: var(--ink-soft); }
/* --- Onglets de navigation (site web, pas page monolithe) --- */
nav.tabs { display: flex; gap: .35rem; margin: 1rem 0 1.4rem; flex-wrap: wrap;
  position: sticky; top: 0; background: var(--bg); padding: .55rem 0; z-index: 30;
  border-bottom: 2px solid var(--line-strong); }
nav.tabs button { border: 1px solid var(--line-strong); background: var(--surface);
  color: var(--ink); padding: .5rem 1.05rem; border-radius: 999px; cursor: pointer;
  font-size: .88rem; font-weight: 600; }
nav.tabs button:hover { border-color: var(--brand-2); color: var(--brand-2); }
nav.tabs button.actif { background: var(--brand); border-color: var(--brand);
  color: var(--brand-ink); }
section.pane { display: none; }
section.pane.actif { display: block; }
/* --- Onglet Actions : déclencheurs + exports (densité resserrée, anti-scroll) --- */
.actions-grille { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: .55rem; margin: .6rem 0 .9rem; }
.action-carte { background: var(--surface); border: 1px solid var(--line);
  border-radius: 9px; padding: .6rem .7rem; }
.action-carte h4 { margin: 0 0 .2rem; font-size: .82rem; line-height: 1.25; }
.action-carte p { margin: 0 0 .4rem; font-size: .72rem; line-height: 1.3; color: var(--ink-soft); }
.action-carte button, a.btn-pdf { display: inline-block; border: none; cursor: pointer;
  background: var(--brand-2); color: var(--brand-ink); padding: .32rem .75rem;
  border-radius: 6px; font-size: .76rem; font-weight: 600; text-decoration: none; }
.action-carte button:hover, a.btn-pdf:hover { background: var(--brand); }
.action-carte button.llm { background: #7c3aed; }
.action-carte button.llm:hover { background: #6d28d9; }
.action-carte button:disabled { opacity: .75; cursor: wait; }
.badge-llm { font-size: .66rem; background: #ede9fe; color: #6d28d9; padding: .12rem .5rem;
  border-radius: 999px; font-weight: 700; vertical-align: middle; }
.badge-0t { font-size: .66rem; background: #dcfce7; color: #15803d; padding: .12rem .5rem;
  border-radius: 999px; font-weight: 700; vertical-align: middle; }
#serveur-etat { font-size: .8rem; padding: .5rem .8rem; border-radius: 8px; margin: .4rem 0 1rem; }
#serveur-etat.on { background: #dcfce7; color: #15803d; }
#serveur-etat.off { background: #fef3c7; color: #92400e; }
.select-projet { padding: .4rem .5rem; border: 1px solid var(--line-strong);
  border-radius: 7px; margin-right: .5rem; font-size: .84rem; }
/* --- Sablier + libellé « en cours » sur les boutons d'action --- */
.spin { display: inline-block; width: .85em; height: .85em; margin-right: .4em;
  border: 2px solid rgba(255,255,255,.45); border-top-color: #fff; border-radius: 50%;
  vertical-align: -.15em; animation: tourner .7s linear infinite; }
.spin.spin-sombre { border-color: rgba(154,52,18,.3); border-top-color: #9a3412; }
@keyframes tourner { to { transform: rotate(360deg); } }
.action-carte button.loading { cursor: wait; opacity: .9; }
/* --- Actions correctives : un <details> replié par projet (anti-scroll) --- */
.correctifs-projet { margin: .5rem 0; }
.correctifs-projet > summary { padding: .55rem .85rem; font-size: .88rem; }
.correctifs-projet > div.actions-grille { margin: .5rem 0 0; padding: 0 .1rem .3rem; }
/* --- Rapports d'exécution (encart dédié) --- */
#rapports { display: flex; flex-direction: column; gap: .6rem; margin-top: .5rem; }
#rapports .vide { font-size: .85rem; color: var(--ink-soft); }
.rapport-carte { background: var(--surface); border: 1px solid var(--line);
  border-left: 4px solid var(--line-strong); border-radius: 8px; padding: .7rem .9rem;
  font-size: .82rem; }
.rapport-carte.encours { border-left-color: #2563eb; }
.rapport-carte.ok { border-left-color: #16a34a; }
.rapport-carte.echec { border-left-color: #dc2626; }
.rapport-entete { display: flex; align-items: center; justify-content: space-between;
  gap: .6rem; flex-wrap: wrap; }
.rapport-titre { font-weight: 700; }
.rapport-heure { color: var(--ink-soft); font-size: .74rem; white-space: nowrap; }
.rapport-statut { font-size: .7rem; font-weight: 700; padding: .12rem .55rem;
  border-radius: 999px; white-space: nowrap; }
.rapport-statut.encours { background: #dbeafe; color: #1d4ed8; }
.rapport-statut.ok { background: #dcfce7; color: #15803d; }
.rapport-statut.echec { background: #fee2e2; color: #b91c1c; }
.rapport-sortie { margin-top: .4rem; font-family: ui-monospace, Consolas, monospace;
  font-size: .72rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word;
  max-height: 14rem; overflow-y: auto; background: var(--surface-2); border-radius: 6px;
  padding: .5rem .6rem; color: var(--ink-soft); }
.rapport-sortie:empty { display: none; }
/* Détail replié par défaut (sauf la dernière action lancée, ouverte d'office) */
.rapport-details { margin-top: .35rem; }
.rapport-details summary { cursor: pointer; font-size: .74rem; font-weight: 600;
  color: var(--brand-2); user-select: none; list-style: none; }
.rapport-details summary::-webkit-details-marker { display: none; }
.rapport-details summary::before { content: "▸ "; }
.rapport-details[open] summary::before { content: "▾ "; }
.rapport-details[open] summary { margin-bottom: .15rem; }
/* --- Décision Valider/Invalider sur un rapport de remédiation terminé --- */
.decision-arbitrage { margin-top: .5rem; padding: .5rem .65rem; border-radius: 7px;
  background: #fff7ed; border: 1px solid #fed7aa; font-size: .78rem; display: flex;
  align-items: center; gap: .5rem; flex-wrap: wrap; }
.decision-question { font-weight: 600; color: #9a3412; }
.decision-arbitrage button { border: none; cursor: pointer; padding: .28rem .7rem;
  border-radius: 6px; font-size: .76rem; font-weight: 700; }
.decision-arbitrage button.oui { background: #16a34a; color: #fff; }
.decision-arbitrage button.oui:hover { background: #15803d; }
.decision-arbitrage button.non { background: #dc2626; color: #fff; }
.decision-arbitrage button.non:hover { background: #b91c1c; }
.decision-arbitrage button:disabled { opacity: .5; cursor: wait; }
.decision-arbitrage.prise { background: var(--surface-2); border-color: var(--line);
  color: var(--ink-soft); font-weight: 600; }
.decision-arbitrage.prise.encours { background: #eff6ff; border-color: #bfdbfe; color: #1d4ed8; }
/* --- Choix multiples détectés dans une proposition (pas un simple oui/non) --- */
.choix-proposes { display: block; width: 100%; margin-bottom: .45rem; font-size: .76rem; }
.choix-titre { font-weight: 700; color: #9a3412; margin-right: .4rem; }
.choix-item { display: inline-block; background: #fff; border: 1px solid #fed7aa;
  border-radius: 999px; padding: .1rem .55rem; margin: .12rem .25rem .12rem 0; color: #7c2d12; }
.choix-input { display: block; width: 100%; box-sizing: border-box; margin-bottom: .4rem;
  padding: .32rem .55rem; border: 1px solid #fed7aa; border-radius: 6px; font-size: .78rem; }

footer { margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--ink-soft); font-size: .8rem; }

@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e6ebf2; --ink-soft: #9aa6b8; --line: #26303f; --line-strong: #33404f;
    --bg: #0f151d; --surface: #161d27; --surface-2: #1b2430;
    --brand: #7fb0e6; --brand-2: #9cc4f0; --brand-ink: #cfe0f5;
    --accent: #6fa8dd;
    --green: #5cc98a; --green-bg: #143726; --amber: #e0b25a; --amber-bg: #3a2f16;
    --red: #f08a80; --red-bg: #3a1e1b; --neutral: #8b96a8; --neutral-bg: #212b38;
    --shadow: 0 1px 3px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.25);
  }
  .pilotage { background: linear-gradient(135deg, #16283f 0%, #1d3a5c 100%); }
}
</style>
</head>
<body>
"""

ALERT_HTML = {
    "critique": '<span class="alert-critique">🔴 critique</span>',
    "majeur": '<span class="alert-majeur">🟠 majeur</span>',
    None: '<span class="alert-ok">✔ OK</span>',
}


def render_catalogue_html(e):
    """Catalogue replié des pratiques supervisées : chaque pratique = un
    <details> fermé (mesure, règle de notation, référentiel cible)."""
    parts = ['<div class="catalogue">']
    parts.append(
        '<p class="legende">Les 13 pratiques que le dispositif supervise, '
        "repliées : cliquer pour déplier la règle de notation exacte et le "
        "référentiel visé. C'est la <b>définition</b> de chaque colonne des "
        "tableaux de mesure ci-dessous.</p>")
    groupes = [
        ("Étage déterministe — mesuré à chaque scan (0 token)", PRAT_CAT_DET,
         "det"),
        ("Étage qualitatif — audit-technique à la demande (lit le code)",
         PRAT_CAT_AUDIT, "audit"),
    ]
    # Répertoire des pratiques craft (développement) — carte repliée dédiée
    parts.append('<h3 class="cat-groupe">Pratiques craft (développement)</h3>')
    lignes_craft = "".join(
        f'<tr><td class="craft-p"><span class="lvl">{PASTILLE[c["statut"]]}</span> '
        f'{e(c["nom"])}</td><td>{e(c["principe"])}</td>'
        f'<td>{e(c["flotte"])}</td><td class="craft-m">{e(c["mesure"])}</td></tr>'
        for c in CRAFT_PRATIQUES)
    parts.append(
        '<details class="prat-card det craft"><summary>'
        '<span class="prat-nom">Pratiques craft (développement) — répertoire</span>'
        f'<span class="muted"> — {len(CRAFT_PRATIQUES)} pratiques</span>'
        "</summary><div class='prat-body'>"
        '<p class="prat-mesure">Les pratiques de software craftsmanship suivies '
        "côté dev : le principe, comment la flotte l'implémente, et par quelle "
        "mesure du dispositif on le constate. "
        "<span class='lvl'>🟢</span> implémenté &amp; mesuré · "
        "<span class='lvl'>🟠</span> partiel · "
        "<span class='lvl'>🔴</span> pas encore outillé.</p>"
        '<table class="craft"><tr><th>Pratique</th><th>Principe</th>'
        f"<th>Dans la flotte</th><th>Mesure</th></tr>{lignes_craft}</table>"
        '<p class="prat-ref"><b>Source</b> — référentiel § 1 (DORA) &amp; § 2 '
        "(pyramide de tests) + dimensions du scan.</p>"
        "</div></details>")
    for titre, cat, cls in groupes:
        parts.append(f'<h3 class="cat-groupe">{e(titre)}</h3>')
        for pr in cat:
            seuils = "".join(
                f'<tr><td class="seuil-n">{e(n)}</td>'
                f"<td>{e(regle)}</td></tr>"
                for n, regle in pr["seuils"])
            parts.append(
                f'<details class="prat-card {cls}">'
                f'<summary><span class="prat-nom">{e(pr["lib"])}</span></summary>'
                '<div class="prat-body">'
                f'<p class="prat-mesure"><b>Ce qui est mesuré</b> — '
                f'{e(pr["mesure"])}</p>'
                '<table class="seuils"><tr><th>Note</th>'
                f"<th>Règle</th></tr>{seuils}</table>"
                f'<p class="prat-ref"><b>Référentiel cible</b> — {e(pr["ref"])}</p>'
                "</div></details>")
    parts.append(
        '<p class="legende">Référentiel complet et sources (DORA, ISO 25010, '
        "Diátaxis, Cagan/Torres, OWASP ASVS/SAMM, DAMA-DMBOK) : "
        "<code>docs/wiki/technical/criteres-pratiques.md</code>.</p>")
    parts.append("</div>")
    return "\n".join(parts)


def render_html(projects, veille, now, pilotage, now_dt):
    e = html.escape
    pil = pilotage
    parts = [HTML_HEAD, "<h1>Supervision multi-projets</h1>"]
    parts.append(
        f'<p class="muted">Généré le {e(now)} par scripts/scan_projets.py — ne pas éditer à la main.</p>'
    )
    # ---- Navigation par onglets (thématiques) --------------------------------
    parts.append(
        '<nav class="tabs">'
        '<button data-pane="pilotage" class="actif">🎛 Pilotage</button>'
        '<button data-pane="projets">📦 Projets</button>'
        '<button data-pane="pratiques">🧭 Pratiques &amp; risques</button>'
        '<button data-pane="veille">🔭 Veille</button>'
        '<button data-pane="deploiement">🚀 Déploiement</button>'
        '<button data-pane="actions">⚡ Actions</button>'
        '<button data-pane="correctifs">🩹 Actions correctives</button>'
        '<button data-pane="exports">📤 Exports</button>'
        "</nav>")
    parts.append('<section class="pane actif" id="pane-pilotage">')

    # ---- Poste de pilotage ---------------------------------------------------
    parts.append('<div class="pilotage"><div class="chiffres">')
    for valeur, libelle in (
        (pil["nb_projets"], "projets"),
        (len(pil["en_alerte"]), "en alerte"),
        (len(pil["runs_a_solder"]), "runs à solder"),
        (len(pil["retards"]), "retards de cadence"),
    ):
        parts.append(f'<div class="chiffre"><b>{valeur}</b><span>{e(libelle)}</span></div>')
    parts.append("</div>")
    decisions = []
    for r in pil["runs_a_solder"]:
        marque = " ⚠" if r["en_retard"] else ""
        decisions.append(
            f'<li class="solder">[{e(r["projet"])}] run à solder ({e(r["age"])}{marque}) — '
            f"{e(r['demande'])}</li>"
        )
    decisions += [f'<li class="retard">{e(t)}</li>' for t in pil["retards"]]
    if decisions:
        parts.append("<b>En attente d'une décision humaine :</b><ul>")
        parts += decisions
        parts.append("</ul>")
        if pil["runs_a_solder"]:
            parts.append(
                '<div style="font-size:.8rem;opacity:.75">Solder (dans le projet '
                "concerné) : <code>py .claude/orchestration/log_run.py --solde "
                "&lt;prefixe-ts&gt; succes \"note de validation\"</code></div>"
            )
    else:
        parts.append("<b>Rien en attente d'arbitrage — système sain.</b>")
    parts.append("</div>")

    # ---- Cadences ------------------------------------------------------------
    parts.append("<h2>Cadences</h2>")
    parts.append("<table><tr><th>Projet</th><th>Scan étage 1</th>"
                 "<th>Diagnostic étage 2</th><th>Dernier commit</th></tr>")
    for c in pil["cadences"]:
        def cell(pair):
            d, perime = pair
            cls = "cadence-perime" if perime else "cadence-ok"
            return f'<span class="{cls}">{e(age_str(d, now_dt))}</span>'
        parts.append(
            f"<tr><td>{e(c['projet'])}</td><td>{cell(c['scan'])}</td>"
            f"<td>{cell(c['diagnostic'])}</td><td>{cell(c['commit'])}</td></tr>"
        )
    parts.append("</table>")
    veille_d, veille_perimee = pil["veille"]
    cls = "cadence-perime" if veille_perimee else "cadence-ok"
    parts.append(
        f'<p class="muted">Veille agentic : <span class="{cls}">'
        f"{e(age_str(veille_d, now_dt))}</span> (cadence {CADENCE_VEILLE_J} j). "
        f"Seuils : scan {CADENCE_SCAN_J} j · diagnostic {CADENCE_DIAGNOSTIC_J} j · "
        f"commit {CADENCE_COMMIT_J} j · run à solder {RUN_A_SOLDER_H} h.</p>"
    )

    # ---- Section 1 : supervision des projets --------------------------------
    parts.append('</section><section class="pane" id="pane-projets">')
    parts.append("<h2>1. Supervision des projets</h2>")
    parts.append("<table><tr>"
                 "<th>Projet</th><th>Livrable principal</th><th>BMAD</th><th>Skills</th>"
                 "<th>Sous-agents</th><th>Playbooks</th><th>Orchestrateur</th>"
                 "<th>Superviseur</th><th>Hooks</th><th>Alerte</th></tr>")
    for p in projects:
        if not p["existe"]:
            parts.append(
                f"<tr><td>{e(p['nom'])}</td><td colspan=9 class='ko'>introuvable</td></tr>"
            )
            continue
        bmad = (
            f"{p['bmad']['version']} ({'+'.join(p['bmad']['modules'])})"
            if p["bmad"]
            else "—"
        )
        liv = p["livrable"]
        if liv and liv["href"]:
            icone = "🌐" if liv["type"] == "web" else "📊"
            liv_html = f'{icone} <a href="{e(liv["href"])}">{e(liv["label"])}</a>'
            if liv["type"] == "web" and liv["href"].startswith("http"):
                liv_html += '<br><span class="muted">(serveur à lancer)</span>'
        elif liv:
            liv_html = f'<span class="ko">⚠ {e(liv["label"])}</span>'
        else:
            liv_html = "—"
        ok = lambda b: '<span class="ok">✔</span>' if b else '<span class="ko">✘</span>'
        parts.append(
            f"<tr><td><b>{e(p['nom'])}</b><br><span class='muted'>{e(p['description'])}</span></td>"
            f"<td>{liv_html}</td>"
            f"<td>{e(bmad)}</td><td>{len(p['skills'])}</td><td>{len(p['agents'])}</td>"
            f"<td>{len(p['playbooks'])}</td><td>{ok(p['orchestration'])}</td>"
            f"<td>{ok(p['supervision'])}</td><td>{e(', '.join(p['hooks']) or '—')}</td>"
            f"<td>{ALERT_HTML[p['alerte']]}</td></tr>"
        )
    parts.append("</table>")
    parts.append(
        f'<p class="muted">Alerte : niveau du finding le plus haut du diagnostic superviseur '
        f"local (p{PRIO_CRITIQUE} = critique, p{PRIO_MAJEUR} = majeur). "
        "Livrable : 🌐 site web (URL locale, serveur à lancer) ou 📊 deck PPT (dernière "
        "version par date de modification). Détail par projet ci-dessous (replié par défaut).</p>"
    )

    for p in projects:
        if not p["existe"]:
            continue
        parts.append("<details>")
        parts.append(
            f"<summary>{ALERT_HTML[p['alerte']]} {e(p['nom'])} "
            f"<span class='muted'>— {e(p['description'])}</span></summary><div>"
        )
        parts.append(f"<p class='muted'>{e(p['chemin'])}"
                     + (f" · dernier scan local : {e(str(p['last_scan']))}" if p["last_scan"] else "")
                     + "</p>")
        parts.append(f"<p><b>Skills utilisés ({len(p['skills_utilises'])})</b> : ")
        parts.append(
            " ".join(
                f'<span class="badge hot">{e(n)} ×{c}</span>' for n, c in p["skills_utilises"]
            )
            or "—"
        )
        parts.append("</p>")
        nb_bmad = sum(1 for s in p["skills_jamais_utilises"] if s.startswith("bmad-"))
        autres = [s for s in p["skills_jamais_utilises"] if not s.startswith("bmad-")]
        parts.append(
            f"<p><b>Jamais utilisés ({len(p['skills_jamais_utilises'])})</b> : "
            f'<span class="badge cold">{nb_bmad} skills bmad-*</span> '
            + " ".join(f'<span class="badge cold">{e(s)}</span>' for s in autres)
            + "</p>"
        )
        if p["agents"]:
            used = dict(p["agents_utilises"])
            parts.append(f"<p><b>Sous-agents ({len(p['agents'])})</b> : ")
            parts.append(
                " ".join(
                    f'<span class="badge {"hot" if a in used else "cold"}">{e(a)}'
                    + (f" ×{used[a]}" if a in used else "")
                    + "</span>"
                    for a in p["agents"]
                )
            )
            parts.append("</p>")
        if p["playbooks"]:
            parts.append(
                "<p><b>Playbooks</b> : "
                + " ".join(f'<span class="badge">{e(x)}</span>' for x in p["playbooks"])
                + "</p>"
            )
        if p["runs_compteurs"]:
            total = sum(p["runs_compteurs"].values())
            detail = ", ".join(
                f"{e(k)} ×{v}" for k, v in sorted(p["runs_compteurs"].items())
            )
            parts.append(f"<p><b>Runs d'orchestration</b> : {total} ({detail})</p>")
        if p["findings"]:
            parts.append("<p><b>Diagnostic superviseur local</b> :</p>")
            for f in sorted(p["findings"], key=lambda x: -x["priorite"]):
                cls = "finding prio-high" if f["priorite"] >= PRIO_MAJEUR else "finding"
                parts.append(
                    f'<div class="{cls}">p{f["priorite"]} <code>{e(f["categorie"])}</code> '
                    f"[{e(f['cible'])}] — {e(f['titre'])}</div>"
                )
        parts.append("</div></details>")

    # ---- Section 2 : pratiques, couverture & risques ------------------------
    existants = [p for p in projects if p["existe"]]
    parts.append('</section><section class="pane" id="pane-pratiques">')
    parts.append('<h2>2. Pratiques, couverture &amp; risques</h2>')
    parts.append('<div class="prat">')
    parts.append(
        '<p class="legende"><b>Cible</b> : le référentiel de critères '
        '(<code>docs/wiki/technical/criteres-pratiques.md</code> — DORA, pyramide de '
        "tests/ISO 25010, Diátaxis, Cagan/Torres, OWASP ASVS/SAMM, DAMA-DMBOK). "
        "Ce qui suit est la <b>mesure</b> ; l'écart mesure↔référentiel alimente les "
        "findings <code>pratique-*</code> du superviseur.</p>")

    # Catalogue replié — définition de chaque pratique supervisée
    parts.append('<details class="catalogue-wrap"><summary>'
                 "📋 Référentiel des pratiques supervisées "
                 "<span class='muted'>— 13 pratiques, replié · déplier pour la "
                 "règle de notation de chaque colonne</span></summary>")
    parts.append(render_catalogue_html(e))
    parts.append("</details>")

    parts.append("<p><b>Étage déterministe</b> — mesuré à chaque scan (0 token), "
                 "présence de dispositifs.</p>")
    parts.append("<table><tr><th>Projet</th>"
                 + "".join(f"<th>{e(lib)}</th>" for _, lib in DIM_DET) + "</tr>")
    for p in existants:
        parts.append(f"<tr><td><b>{e(p['nom'])}</b></td>")
        for key, _ in DIM_DET:
            dim = p["pratiques"][key]
            parts.append(
                f'<td><span class="lvl">{PASTILLE[dim["niveau"]]}</span>'
                f"<small>{e(dim['detail'])}</small></td>"
            )
        parts.append("</tr>")
    parts.append("</table>")
    parts.append('<p class="legende">🟢 ok · 🟠 moyen · 🔴 absent/manquant · '
                 "⚪ non applicable. Sécu (proxy) = garde-fous présents "
                 "(.env gitigné, deny rules, guard git), <b>pas</b> un audit de failles.</p>")

    parts.append("<p><b>Étage qualitatif</b> — audit <code>audit-technique</code> "
                 "à la demande (lit le code réel, findings localisés "
                 "<code>fichier:ligne</code>).</p>")
    parts.append(
        '<p class="legende"><b>Ce que couvre l\'audit</b> — '
        "<b>Robustesse</b> : gestion d'erreur, cas limites, entrées non validées, "
        "échecs silencieux, idempotence. · "
        "<b>Performance</b> : boucles imbriquées sur gros volumes, I/O en boucle, "
        "requêtes N+1, absence de cache/pagination. · "
        "<b>Risque technique</b> : duplication, couplage fort, dépendance non épinglée, "
        "code mort, chemin critique sans test. · "
        "<b>Sécurité</b> : secrets commités, injection (SQL/commande/template), "
        "<code>eval</code>/<code>pickle</code>, <code>shell=True</code>, "
        "chemins non assainis, permissions trop larges.</p>")
    parts.append("<table><tr><th>Projet</th>"
                 + "".join(f"<th>{e(lib)}</th>" for _, lib in DIM_AUDIT)
                 + "<th>Audité le</th></tr>")
    for p in existants:
        audit = p["audit"]
        parts.append(f"<tr><td><b>{e(p['nom'])}</b></td>")
        if not audit:
            parts.append("".join("<td>⚪ non audité</td>" for _ in DIM_AUDIT)
                         + "<td>—</td></tr>")
            continue
        dims = audit.get("dimensions", {})
        for key, _ in DIM_AUDIT:
            d = dims.get(key) or {}
            syn = d.get("synthese", "")
            parts.append(
                f'<td><span class="lvl">{PASTILLE.get(d.get("niveau"))} '
                f'{e(d.get("niveau", "?"))}</span>'
                + (f"<small>{e(syn[:70])}</small>" if syn else "")
                + "</td>"
            )
        parts.append(f"<td>{e(str(audit.get('date', '?')))}</td></tr>")
    parts.append("</table>")
    parts.append('<p class="legende">Lancer un audit : skill <code>audit-technique</code> '
                 "sur le projet cible (robustesse, performance, risque technique, "
                 "failles de sécurité).</p></div>")

    # ---- Section 3 : veille agentic -----------------------------------------
    parts.append('</section><section class="pane" id="pane-veille">')
    parts.append("<h2>3. Veille agentic</h2>")
    if veille["derniere_veille"]:
        parts.append(
            f'<p class="muted">Dernière veille : {e(str(veille["derniere_veille"]))} — '
            "skill <code>veille-agentic</code> (cadence 3 jours, déclenchable manuellement).</p>"
        )
    else:
        parts.append(
            '<p class="muted">Aucune veille enregistrée — lancer la skill '
            "<code>veille-agentic</code>.</p>"
        )
    parts.append("<div class='actions-grille'>")
    parts.append(
        '<div class="action-carte"><h4>Lancer la veille <span class="badge-llm">LLM</span></h4>'
        "<p>Écosystème + pratiques providers + gestion des tokens.</p>"
        '<button class="llm" data-action="veille">Lancer</button></div>')
    parts.append(
        '<div class="action-carte"><h4>Réflexion de mise en œuvre <span class="badge-llm">LLM</span></h4>'
        "<p>Écrit une réflexion (docs/reflexions/) à partir des pratiques de veille — "
        "n'applique aucun changement, propose seulement.</p>"
        '<button class="llm" data-action="reflexion">Lancer la réflexion</button></div>')
    projets_options_v = "".join(f'<option value="{e(p["nom"])}">{e(p["nom"])}</option>'
                                for p in projects if p["existe"])
    parts.append(
        '<div class="action-carte"><h4>Déployer sur un projet <span class="badge-llm">LLM</span></h4>'
        "<p>Applique les correctifs de veille adoptés à un projet cible (evolution-flotte).</p>"
        f'<select class="select-projet" id="veille-deploy-projet">{projets_options_v}</select>'
        '<button class="llm" data-action="deployer-veille">Déployer</button></div>')
    parts.append("</div>")
    parts.append('<div id="rapports-veille"><p class="vide">Aucune action de veille lancée dans cette session.</p></div>')

    def _statut_cell(v):
        statut = v.get("statut", "nouveau")
        cls = {
            "nouveau": "statut-nouveau",
            "adopte": "statut-adopte",
            "ecarte": "statut-ecarte",
        }.get(statut, "")
        return f'<td><span class="{cls}">{e(statut)}</span></td>'

    def _link_cell(v):
        url, titre = v.get("url", ""), e(v.get("titre", "?"))
        return f'<a href="{e(url)}">{titre}</a>' if url else titre

    outils_v = [v for v in veille["entrees"] if v.get("type") != "pratique"]
    pratiques_v = [v for v in veille["entrees"] if v.get("type") == "pratique"]
    if outils_v:
        parts.append("<table><tr><th>Sujet</th><th>Type</th><th>Statut</th>"
                     "<th>Projets concernés</th><th>Pertinence</th></tr>")
        for v in outils_v:
            parts.append(
                f"<tr><td>{_link_cell(v)}</td><td>{e(v.get('type', '?'))}</td>"
                f"{_statut_cell(v)}"
                f"<td>{e(', '.join(v.get('projets_concernes', []) or ['—']))}</td>"
                f"<td>{e(v.get('pertinence', ''))}</td></tr>"
            )
        parts.append("</table>")
    if pratiques_v:
        parts.append("<h3>Pratiques agentic repérées (docs providers)</h3>")
        parts.append(
            '<p class="muted">Volet 2 de <code>veille-agentic</code> : pratiques recommandées '
            "par les providers, comparées à l'état réel de la flotte. <code>adopte</code> "
            "(décision utilisateur) → la règle proposée entre au référentiel "
            "(<code>criteres-pratiques.md</code> § 7) et l'action corrective se traite via "
            "<code>evolution-flotte</code>.</p>"
        )
        parts.append("<table><tr><th>Pratique</th><th>Source</th><th>Statut</th>"
                     "<th>Projets</th><th>Règle d'analyse proposée</th><th>Action corrective</th></tr>")
        for v in pratiques_v:
            parts.append(
                f"<tr><td>{_link_cell(v)}</td><td>{e(v.get('source_referentiel', '?'))}</td>"
                f"{_statut_cell(v)}"
                f"<td>{e(', '.join(v.get('projets_concernes', []) or ['—']))}</td>"
                f"<td>{e(v.get('regle_proposee', ''))}</td>"
                f"<td>{e(v.get('action_corrective', ''))}</td></tr>"
            )
        parts.append("</table>")

    # ---- Onglet Déploiement (package agentic pour un nouveau projet) --------
    parts.append('</section><section class="pane" id="pane-deploiement">')
    parts.append("<h2>4. Déploiement du package agentic</h2>")
    manifest = load_deploy_manifest()
    parts.append(
        '<p class="muted">Bootstrap complet d\'un NOUVEAU projet à partir des sources '
        "vivantes de la flotte (canon de supervision, hooks, skills de pilotage, "
        "playbooks, tests) — <b>zéro copie au repos</b> : corriger une source, "
        "le prochain déploiement est à jour sans rien maintenir en double.</p>")
    if manifest is not None:
        parts.append(
            f'<p class="muted">{len(manifest)} fichiers matérialisés + settings.json '
            "câblé (hooks, deny rules) + squelette CLAUDE.md généré. "
            f'<code>.claude/dispositif/package/deploy_nouveau_projet.py</code></p>')
    parts.append(
        '<div class="actions-grille">'
        '<div class="action-carte"><h4>Cible du déploiement</h4>'
        "<p>Dossier du NOUVEAU projet (créé s'il n'existe pas) — chemin complet, "
        "ou lien/chemin réseau accessible localement.</p>"
        '<input type="text" id="deploy-chemin" placeholder="C:/Users/.../NouveauProjet" '
        'style="width:100%;padding:.45rem .6rem;border:1px solid var(--line-strong);'
        'border-radius:7px;font-size:.84rem;margin-bottom:.5rem">'
        '<input type="text" id="deploy-nom" placeholder="Nom du projet (ex. VSCode6)" '
        'style="width:100%;padding:.45rem .6rem;border:1px solid var(--line-strong);'
        'border-radius:7px;font-size:.84rem;margin-bottom:.5rem">'
        '<label style="display:flex;align-items:center;gap:.4rem;font-size:.78rem;'
        'color:var(--ink-soft);margin-bottom:.6rem">'
        '<input type="checkbox" id="deploy-force">Écraser les fichiers déjà présents (--force)</label>'
        '<button data-action="deploy" data-cible-input="deploy-chemin" '
        'data-nom-input="deploy-nom" data-force-input="deploy-force">Déployer</button></div>'
        '<div class="action-carte"><h4>Vérifier les sources <span class="badge-0t">0 token</span></h4>'
        f"<p>Confirme que les {len(manifest) if manifest is not None else '…'} sources vivantes "
        "du manifeste existent avant de déployer.</p>"
        '<button data-action="package-check">Vérifier</button></div>'
        "</div>")
    parts.append('<h3>Rapport de déploiement</h3><div id="rapports-deploiement">'
                 '<p class="vide">Aucun déploiement lancé dans cette session.</p></div>')
    parts.append("</section>")

    # ---- Onglet Actions (déclencheurs agentic globaux) -----------------------
    parts.append('</section><section class="pane" id="pane-actions">')
    parts.append("<h2>5. Actions</h2>")
    parts.append(
        '<div id="serveur-etat" class="off">Vérification du serveur d\'actions…</div>'
        '<p class="muted">Les boutons appellent le serveur local '
        "(<code>py scripts/serve_wiki.py</code> puis ouvrir "
        '<a href="http://localhost:8765">localhost:8765</a>). '
        '<span class="badge-0t">0 token</span> = script déterministe · '
        '<span class="badge-llm">LLM</span> = lance <code>claude -p</code> (facturé, '
        "gouvernance propose→arbitre→applique préservée).</p>")
    parts.append("<h3>Analyses</h3><div class='actions-grille'>")
    parts.append(
        '<div class="action-carte"><h4>Re-scan de la flotte <span class="badge-0t">0 token</span></h4>'
        "<p>Relance les scans locaux des 6 projets et régénère ce wiki.</p>"
        '<button data-action="scan">Scanner</button></div>')
    parts.append(
        '<div class="action-carte"><h4>Vérifier le canon <span class="badge-0t">0 token</span></h4>'
        "<p>Détecte toute dérive des copies du dispositif vs le canon (sync --check).</p>"
        '<button data-action="sync-check">Vérifier</button></div>')
    parts.append(
        '<div class="action-carte"><h4>Vérifier le package <span class="badge-0t">0 token</span></h4>'
        "<p>Sources vivantes du package de déploiement nouveau-projet.</p>"
        '<button data-action="package-check">Vérifier</button></div>')
    parts.append(
        '<div class="action-carte"><h4>Diagnostic superviseur <span class="badge-llm">LLM</span></h4>'
        "<p>Étage 2 : qualifie usage des agents + pratiques, écrit diagnostic.json.</p>"
        '<button class="llm" data-action="diagnostic">Lancer</button></div>')
    projets_options = "".join(f'<option value="{e(p["nom"])}">{e(p["nom"])}</option>'
                              for p in projects if p["existe"])
    parts.append(
        '<div class="action-carte"><h4>Audit technique <span class="badge-llm">LLM</span></h4>'
        "<p>Lit le code réel d'un projet : robustesse, perf, risque, sécurité.</p>"
        f'<select class="select-projet" id="audit-projet">{projets_options}</select>'
        '<button class="llm" data-action="audit">Auditer</button></div>')
    parts.append("</div>")
    parts.append(
        '<p class="muted">Veille agentic, réflexion et déploiement des correctifs de veille : '
        "onglet <b>🔭 Veille</b>.</p>")
    parts.append('<h3>Rapport des actions</h3><div id="rapports-agentic">'
                 '<p class="vide">Aucune action lancée dans cette session.</p></div>')
    parts.append("</section>")

    # ---- Onglet Actions correctives (pratiques faibles, projet par projet) --
    parts.append('</section><section class="pane" id="pane-correctifs">')
    parts.append("<h2>6. Actions correctives</h2>")
    parts.append(
        '<p class="muted">Une carte par pratique mesurée <b>en écart</b> '
        '(<span class="badge-llm">LLM</span> — même gouvernance propose→arbitre→applique : '
        "chaque bouton présente une proposition et demande ton arbitrage, "
        "n'applique rien seul). Source : dimensions du scan (🟠/🔴), audit qualitatif "
        "(moyen/critique) et findings ouverts du diagnostic, groupés par projet.</p>")
    projets_avec_ecarts = 0
    for p in projects:
        if not p["existe"]:
            continue
        ecarts = []   # (lib, niveau, detail, cible_technique)
        pratiques_p = p.get("pratiques") or {}
        for cle, lib in DIM_DET:
            d = pratiques_p.get(cle) or {}
            if d.get("niveau") in ("moyen", "absent"):
                ecarts.append((lib, d.get("niveau"), d.get("detail") or "", cle))
        audit_dims = (p.get("audit") or {}).get("dimensions") or {}
        for cle, lib in DIM_AUDIT:
            dd = audit_dims.get(cle) or {}
            if dd.get("niveau") in ("moyen", "critique"):
                ecarts.append((f"Audit — {lib}", dd.get("niveau"), dd.get("synthese") or "", cle))
        findings_p = p.get("findings") or []
        if not ecarts and not findings_p:
            continue
        projets_avec_ecarts += 1
        n_total = len(ecarts) + len(findings_p)
        n_critique = sum(1 for _, niv, _, _ in ecarts if niv in ("absent", "critique")) + len(findings_p)
        pastille_resume = "🔴" if n_critique else "🟠"
        parts.append(
            f'<details class="correctifs-projet"><summary>{pastille_resume} '
            f'<b>{e(p["nom"])}</b> — {n_total} pratique(s) en écart</summary>'
            '<div class="actions-grille">')
        for lib, niv, detail, cle in ecarts:
            cible = f'{p["nom"]} :: {lib} — {detail[:140]}'
            parts.append(
                f'<div class="action-carte"><h4>{PASTILLE.get(niv, "")} {e(lib)} '
                '<span class="badge-llm">LLM</span></h4>'
                f"<p>{e(detail[:180]) or 'Écart mesuré, sans détail complémentaire.'}</p>"
                f'<button class="llm" data-action="remediation" data-cible="{e(cible)}">'
                "Traiter (arbitrage demandé)</button></div>")
        for f in findings_p:
            titre = (f.get("titre") or "")[:160]
            cible_f = f.get("cible") or ""
            cible = f'{p["nom"]} :: {cible_f} — {titre[:100]}'
            parts.append(
                f'<div class="action-carte"><h4>🔴 {e(cible_f)} '
                '<span class="badge-llm">LLM</span></h4>'
                f"<p>{e(titre)}</p>"
                f'<button class="llm" data-action="remediation" data-cible="{e(cible)}">'
                "Traiter (arbitrage demandé)</button></div>")
        parts.append("</div></details>")
    if not projets_avec_ecarts:
        parts.append('<p class="muted">Aucune pratique en écart détectée sur la flotte — rien à corriger.</p>')
    parts.append('<h3>Rapport des actions correctives</h3><div id="rapports-correctifs">'
                 '<p class="vide">Aucune action corrective lancée dans cette session.</p></div>')
    parts.append("</section>")

    # ---- Onglet Exports (PDF téléchargeables) --------------------------------
    parts.append('</section><section class="pane" id="pane-exports">')
    parts.append("<h2>7. Exports</h2>")
    parts.append("<div class='actions-grille'>")
    for fichier, titre_pdf, desc in (
        ("analyse-detaillee.pdf", "Analyse détaillée de la flotte",
         "Par projet : dimensions mesurées, audit qualitatif (findings localisés = exemples), synthèses commentées."),
        ("actions-remediation.pdf", "Actions de remédiation",
         "Findings ouverts + propositions, pratiques de veille à adopter, et remédiations déjà appliquées (exemples commentés)."),
    ):
        chemin_pdf = os.path.join(EXPORTS_DIR, fichier)
        etat = "" if os.path.isfile(chemin_pdf) else "<p class='muted'>(pas encore généré — bouton « Régénérer »)</p>"
        parts.append(
            f'<div class="action-carte"><h4>{e(titre_pdf)}</h4><p>{e(desc)}</p>{etat}'
            f'<a class="btn-pdf" href="docs/wiki/exports/{fichier}" download>Télécharger</a></div>')
    parts.append(
        '<div class="action-carte"><h4>Régénérer les PDF <span class="badge-0t">0 token</span></h4>'
        "<p>Reconstruit les 2 exports depuis les données à jour du scan.</p>"
        '<button data-action="pdf">Régénérer</button></div>')
    parts.append("</div>")
    parts.append('<h3>Rapport des exports</h3><div id="rapports-exports">'
                 '<p class="vide">Aucun export relancé dans cette session.</p></div>')
    parts.append("</section>")

    parts.append(f"<footer>Supervision projets — {e(now)}</footer>")
    # ---- JS : onglets + déclencheurs -----------------------------------------
    parts.append("""<script>
(function () {
  var API = "http://localhost:8765";
  // Onglets (hash persistant : #pane-veille rouvre l'onglet Veille)
  var boutons = document.querySelectorAll("nav.tabs button");
  function activer(nom) {
    boutons.forEach(function (b) { b.classList.toggle("actif", b.dataset.pane === nom); });
    document.querySelectorAll("section.pane").forEach(function (s) {
      s.classList.toggle("actif", s.id === "pane-" + nom);
    });
  }
  boutons.forEach(function (b) {
    b.addEventListener("click", function () {
      activer(b.dataset.pane);
      history.replaceState(null, "", "#pane-" + b.dataset.pane);
    });
  });
  var h = (location.hash || "").replace("#pane-", "");
  if (h && document.getElementById("pane-" + h)) activer(h);

  // Serveur d'actions : état + déclencheurs
  var etat = document.getElementById("serveur-etat");
  function ping() {
    fetch(API + "/api/ping").then(function (r) { return r.json(); }).then(function () {
      etat.textContent = "Serveur d'actions actif — les boutons sont opérationnels.";
      etat.className = "on";
    }).catch(function () {
      etat.textContent = "Serveur d'actions non détecté — lancer : py scripts/serve_wiki.py (puis ouvrir http://localhost:8765).";
      etat.className = "off";
    });
  }
  ping();

  // --- Sablier + libellé sur le bouton, du clic jusqu'à la fin du job --------
  var boutonParJob = {};   // id de job -> bouton qui l'a déclenché (pour le restaurer)
  var jobsTermines = {};   // id de job déjà rendu terminé (évite de re-basculer le bouton)
  var pliManuel = {};      // id de job -> true/false : dernier état choisi PAR L'UTILISATEUR
                            // (remplirZone reconstruit tout le HTML à chaque poll ; sans ceci,
                            // un rapport déplié à la main se replierait au rafraîchissement suivant)
  var scrollSortie = {};   // id de job -> scrollTop de sa <pre class="rapport-sortie"> — même
                            // cause que pliManuel : sans ça, un scroll dans la sortie revient en
                            // haut au poll suivant (le <pre> est détruit puis recréé à chaque fois)

  function demarrerChargement(b) {
    if (!b.dataset.label) b.dataset.label = b.innerHTML;   // libellé d'origine, une seule fois
    b.innerHTML = '<span class="spin"></span>En cours…';
    b.classList.add("loading");
    b.disabled = true;
  }
  function arreterChargement(b) {
    if (b.dataset.label) b.innerHTML = b.dataset.label;
    b.classList.remove("loading");
    b.disabled = false;
  }

  function classeStatut(statut) {
    if (statut === "en cours") return "encours";
    if (statut === "ok") return "ok";
    return "echec";   // echec (N) / erreur (...)
  }
  function libelleStatut(statut) {
    if (statut === "en cours") return "⏳ en cours";
    if (statut === "ok") return "✅ terminé";
    return "❌ " + statut;
  }

  function echapper(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML.replace(/"/g, "&quot;");
  }

  // Actions dont le prompt se termine par « demande l'arbitrage explicite avant
  // d'appliquer » — celles-là seules proposent une décision à trancher. « reflexion »
  // en est volontairement exclue (elle n'applique jamais rien, rien à valider/refuser).
  var ACTIONS_AVEC_ARBITRAGE = ["remediation", "deployer-veille"];

  // Cherche, dans la liste COMPLÈTE des jobs (pas la seule liste filtrée de la zone —
  // un job "valider" né d'un rapport de l'onglet Veille vit dans la zone Correctifs),
  // le dernier valider/refuser pour cette cible. Dérivé du serveur, pas d'une mémoire
  // locale : survit à un rechargement de page ET empêche de relancer une action déjà
  // en cours ou déjà tranchée (le vrai bug rapporté — l'état local se perdait au reload).
  function decisionExistante(tousJobs, cible) {
    for (var i = 0; i < tousJobs.length; i++) {
      var j = tousJobs[i];   // déjà trié du plus récent au plus ancien par le serveur
      if ((j.action === "valider" || j.action === "refuser") && j.cible === cible) return j;
    }
    return null;
  }

  // Une proposition n'est pas toujours un simple oui/non — un rapport peut énumérer
  // plusieurs options (« **Option A — …** », « **Option B — …** »). Détecter ≥ 2
  // options dans la sortie et les faire APPARAÎTRE distinctement, plutôt que de les
  // laisser noyées dans le texte replié derrière un Valider/Invalider aveugle.
  function choixProposes(tail) {
    var options = [];
    (tail || []).forEach(function (ligne) {
      var m = /^\\*\\*(Option\\s+[^*]+)\\*\\*/i.exec((ligne || "").trim());
      if (m) options.push(m[1]);
    });
    return options;
  }

  function decisionArbitrage(j, tousJobs) {
    // Sur un rapport TERMINÉ dont la proposition a été présentée, dans N'IMPORTE QUEL
    // onglet (Actions correctives, Veille…) : Valider (applique, LLM) ou Invalider
    // (note le refus, 0 token).
    if (ACTIONS_AVEC_ARBITRAGE.indexOf(j.action) === -1 || j.status !== "ok" || !j.cible) return "";
    var decision = decisionExistante(tousJobs, j.cible);
    if (decision) {
      if (decision.status === "en cours") {
        var quoi = decision.action === "valider" ? "l'application" : "l'enregistrement du refus";
        return '<div class="decision-arbitrage prise encours">' +
          '<span class="spin spin-sombre"></span>Une action est déjà en cours de traitement pour ' +
          'cette cible (' + quoi + ') — patiente qu\\'elle se termine.</div>';
      }
      if (decision.status === "ok") {
        return decision.action === "valider"
          ? '<div class="decision-arbitrage prise">✅ Validé — appliqué (' + decision.started + ')</div>'
          : '<div class="decision-arbitrage prise">🚫 Refusé (' + decision.started + ') — ne sera plus reproposé</div>';
      }
      // echec/erreur : aucune décision solide n'a abouti — on relaisse la main (boutons).
    }
    var cible = echapper(j.cible);
    var options = choixProposes(j.tail);
    var choixHtml = "";
    if (options.length >= 2) {
      choixHtml = '<div class="choix-proposes"><span class="choix-titre">Choix proposés :</span>' +
        options.map(function (o) { return '<span class="choix-item">' + echapper(o) + '</span>'; }).join("") +
        '</div><input type="text" class="choix-input" ' +
        'placeholder="Préciser un choix (ex. ' + echapper(options[0].split(/[—–-]/)[0].trim()) + ')">';
    }
    return '<div class="decision-arbitrage">' +
      choixHtml +
      '<span class="decision-question">Décision en attente :</span> ' +
      '<button class="oui" data-action="valider" data-cible="' + cible + '">Valider</button> ' +
      '<button class="non" data-action="refuser" data-cible="' + cible + '">Invalider</button>' +
      '</div>';
  }

  function carteRapport(j, estLaDerniere, tousJobs) {
    var classe = classeStatut(j.status);
    // Repliée par défaut ; la toute dernière action lancée et tout job en cours démarrent
    // ouverts — SAUF si l'utilisateur a explicitement plié/déplié cette carte lui-même,
    // auquel cas son choix prime sur la règle par défaut à chaque rafraîchissement.
    var parDefaut = estLaDerniere || j.status === "en cours";
    var ouvert = (j.id in pliManuel ? pliManuel[j.id] : parDefaut) ? " open" : "";
    // libelle et tail = sortie brute d'un sous-process / claude -p (texte non contrôlé) :
    // échappés avant injection en innerHTML (finding sécurité XSS stocké, audit 2026-07-24).
    var tailHtml = (j.tail || []).map(echapper).join("\\n");
    return '<div class="rapport-carte ' + classe + '">' +
      '<div class="rapport-entete">' +
        '<span class="rapport-titre">' + echapper(j.libelle) + '</span>' +
        '<span class="rapport-statut ' + classe + '">' + libelleStatut(j.status) + '</span>' +
      '</div>' +
      '<div class="rapport-heure">' + echapper(j.started) + (j.ended ? ' → ' + echapper(j.ended) : '') + '</div>' +
      decisionArbitrage(j, tousJobs) +
      '<details class="rapport-details" data-job="' + j.id + '"' + ouvert + '>' +
        '<summary>Détail du rapport</summary>' +
        '<pre class="rapport-sortie" data-job="' + j.id + '">' + tailHtml + '</pre>' +
      '</details>' +
    '</div>';
  }
  function zoneRapportPour(action) {
    if (action === "deploy") return "rapports-deploiement";
    if (action === "remediation" || action === "valider" || action === "refuser") return "rapports-correctifs";
    if (action === "pdf") return "rapports-exports";
    if (action === "veille" || action === "reflexion" || action === "deployer-veille") return "rapports-veille";
    return "rapports-agentic";
  }
  function remplirZone(id, jobs, tousJobs, videTexte) {
    var zone = document.getElementById(id);
    if (!zone) return;   // le conteneur peut ne pas exister sur cette page
    zone.innerHTML = jobs.length
      ? jobs.map(function (j, i) { return carteRapport(j, i === 0, tousJobs); }).join("")
      : '<p class="vide">' + videTexte + '</p>';
    // Le innerHTML ci-dessus recrée les <details> à chaque poll : ré-attacher l'écoute
    // du pli à chaque fois pour mémoriser le choix de l'utilisateur (cf. pliManuel).
    zone.querySelectorAll(".rapport-details").forEach(function (det) {
      det.addEventListener("toggle", function () {
        pliManuel[det.dataset.job] = det.open;
      });
    });
    // Même cause, même remède pour le scroll À L'INTÉRIEUR d'une sortie longue : le
    // <pre> est recréé à chaque poll, donc on restaure la position connue puis on
    // réécoute pour la garder à jour (pas de scroll = pas d'entrée, rien à restaurer).
    zone.querySelectorAll(".rapport-sortie").forEach(function (pre) {
      var id = pre.dataset.job;
      if (id in scrollSortie) pre.scrollTop = scrollSortie[id];
      pre.addEventListener("scroll", function () {
        scrollSortie[id] = pre.scrollTop;
      }, { passive: true });
    });
  }

  function rafraichirJobs() {
    fetch(API + "/api/jobs").then(function (r) { return r.json(); }).then(function (d) {
      var jobs = d.jobs || [];
      // Un job qui se termine (n'est plus "en cours") restaure son bouton une seule fois.
      jobs.forEach(function (j) {
        if (j.status !== "en cours" && boutonParJob[j.id] && !jobsTermines[j.id]) {
          arreterChargement(boutonParJob[j.id]);
          jobsTermines[j.id] = true;
        }
      });
      var AGENTIC = ["scan", "scan-rapide", "sync-check", "package-check", "diagnostic", "audit"];
      remplirZone("rapports-agentic",
                  jobs.filter(function (j) { return AGENTIC.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action lancée dans cette session.");
      var CORRECTIFS = ["remediation", "valider", "refuser"];
      remplirZone("rapports-correctifs",
                  jobs.filter(function (j) { return CORRECTIFS.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action corrective lancée dans cette session.");
      remplirZone("rapports-deploiement",
                  jobs.filter(function (j) { return j.action === "deploy"; }), jobs,
                  "Aucun déploiement lancé dans cette session.");
      remplirZone("rapports-exports",
                  jobs.filter(function (j) { return j.action === "pdf"; }), jobs,
                  "Aucun export relancé dans cette session.");
      var VEILLE_ACTIONS = ["veille", "reflexion", "deployer-veille"];
      remplirZone("rapports-veille",
                  jobs.filter(function (j) { return VEILLE_ACTIONS.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action de veille lancée dans cette session.");
      if (jobs.some(function (j) { return j.status === "en cours"; }))
        setTimeout(rafraichirJobs, 1500);
    }).catch(function () {});
  }

  // Délégation sur document (pas un forEach au chargement) : les boutons Valider/Invalider
  // sont injectés APRÈS coup par remplirZone (innerHTML) — un câblage one-shot au chargement
  // ne les verrait jamais. La délégation couvre statique et dynamique uniformément.
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    if (!b) return;
    var corps = {};
    if (b.dataset.action === "audit")
      corps.projet = document.getElementById("audit-projet").value;
    if (b.dataset.action === "deployer-veille")
      corps.projet = document.getElementById("veille-deploy-projet").value;
    if (b.dataset.action === "remediation") corps.cible = b.dataset.cible;
    if (b.dataset.action === "deploy") {
      var champChemin = document.getElementById(b.dataset.cibleInput);
      var champNom = document.getElementById(b.dataset.nomInput);
      var champForce = document.getElementById(b.dataset.forceInput);
      corps.cible = champChemin ? champChemin.value.trim() : "";
      corps.nom = champNom ? champNom.value.trim() : "";
      corps.force = champForce ? champForce.checked : false;
      if (!corps.cible) { alert("Indiquer le dossier du nouveau projet avant de déployer."); return; }
    }
    var encart = null;
    if (b.dataset.action === "valider" || b.dataset.action === "refuser") {
      corps.cible = b.dataset.cible;
      encart = b.closest(".decision-arbitrage");
      // Choix précisé (quand la proposition énumérait plusieurs options) : transmis
      // tel quel au serveur, qui l'injecte dans le prompt de valider — sans ce champ,
      // un fresh claude -p sans mémoire du run précédent devrait redeviner l'option.
      var champChoix = encart && encart.querySelector(".choix-input");
      if (champChoix && champChoix.value.trim()) corps.choix = champChoix.value.trim();
      // Désactive les 2 boutons AVANT même la réponse réseau (latence) — l'état
      // durable (déjà décidé / déjà en cours) vient ensuite du serveur via
      // decisionExistante(), pas d'une mémoire locale qui se perdrait au rechargement.
      if (encart) encart.querySelectorAll("button").forEach(function (fr) { fr.disabled = true; });
    }
    demarrerChargement(b);
    fetch(API + "/api/run/" + b.dataset.action, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    }).then(function (r) {
      if (!r.ok) return r.json().then(function (err) { throw new Error(err.message || err.erreur || "échec"); });
      return r.json();
    }).then(function (d) {
      boutonParJob[d.job] = b;   // le bouton restera "en cours" jusqu'à la fin de CE job
      rafraichirJobs();
      // Le clic « ouvre » la zone de suivi : on l'amène dans le viewport tout de
      // suite, sans attendre que l'utilisateur pense à descendre la chercher.
      var zone = document.getElementById(zoneRapportPour(b.dataset.action));
      if (zone) zone.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }).catch(function (err) {
      arreterChargement(b);
      // Refusé par le garde-fou serveur (deja_en_cours) ou tout autre échec : on
      // réactive ce qu'on avait désactivé de façon optimiste, rien ne reste bloqué.
      if (encart) encart.querySelectorAll("button").forEach(function (fr) { fr.disabled = false; });
      alert(err && err.message ? err.message : "Action refusée ou serveur injoignable : lancer py scripts/serve_wiki.py");
    });
  });
  rafraichirJobs();
})();
</script></body></html>""")
    return "\n".join(parts)


def _pdf_head(titre):
    return (HTML_HEAD.replace("<title>Supervision multi-projets</title>",
                              f"<title>{html.escape(titre)}</title>")
            + f"<h1>{html.escape(titre)}</h1>")


NIVEAU_PASTILLE_PDF = {"ok": "🟢", "moyen": "🟠", "absent": "🔴", "critique": "🔴", "n/a": "⚪"}


def generate_pdfs(projects, veille, now):
    """Deux exports PDF téléchargeables depuis l'onglet Actions du wiki :
    1. analyse-detaillee.pdf — par projet : dimensions mesurées + audit qualitatif
       (findings localisés = les exemples, synthèses = les commentaires).
    2. actions-remediation.pdf — findings ouverts + propositions, pratiques de veille
       (règle + action corrective), remédiations déjà appliquées (arbitrages commentés).
    Rendu via Edge headless --print-to-pdf (déjà l'outil de vérif visuelle du projet)."""
    e = html.escape
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    # --- 1. Analyse détaillée -------------------------------------------------
    parts = [_pdf_head("Analyse détaillée de la flotte — supervision"),
             f'<p class="muted">Généré le {e(now)} — étage déterministe (scan 0 token) '
             "+ étage qualitatif (audit-technique, lecture du code).</p>"]
    for p in projects:
        if not p["existe"]:
            continue
        parts.append(f'<h2>{e(p["nom"])} — {e(p.get("description") or "")}</h2>')
        parts.append(f'<p class="muted">Dernier commit : {e(str(p.get("dernier_commit") or "?"))}</p>')
        parts.append("<h3>Dimensions mesurées (scan déterministe)</h3>"
                     "<table><tr><th>Dimension</th><th>Niveau</th><th>Constat mesuré</th></tr>")
        for cle, lib in DIM_DET:
            d = (p.get("pratiques") or {}).get(cle) or {}
            niv = d.get("niveau", "?")
            parts.append(f"<tr><td>{e(lib)}</td><td>{NIVEAU_PASTILLE_PDF.get(niv, '')} {e(niv)}</td>"
                         f"<td>{e(d.get('detail') or '')}</td></tr>")
        parts.append("</table>")
        audit = p.get("audit") or {}
        dims = audit.get("dimensions") or {}
        if dims:
            parts.append(f'<h3>Audit qualitatif du {e(audit.get("date") or "?")} '
                         "(lecture du code réel)</h3>")
            for nom_dim, d in dims.items():
                parts.append(f'<p><b>{e(nom_dim)}</b> — {NIVEAU_PASTILLE_PDF.get(d.get("niveau"), "")} '
                             f'{e(d.get("niveau") or "?")}<br><i>Commentaire : {e(d.get("synthese") or "")}</i></p>')
                findings = d.get("findings") or []
                if findings:
                    parts.append("<table><tr><th>Exemple constaté</th><th>Localisation</th></tr>")
                    for f in findings:
                        parts.append(f"<tr><td>{e(f.get('titre') or '')}</td>"
                                     f"<td><code>{e(f.get('localisation') or '')}</code></td></tr>")
                    parts.append("</table>")
        else:
            parts.append('<p class="muted">Pas d\'audit qualitatif enregistré pour ce projet.</p>')
    parts.append(f"<footer>Analyse détaillée — {e(now)}</footer></body></html>")
    html_analyse = os.path.join(EXPORTS_DIR, "analyse-detaillee.html")
    with open(html_analyse, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))

    # --- 2. Actions de remédiation -------------------------------------------
    parts = [_pdf_head("Actions de remédiation — supervision de la flotte"),
             f'<p class="muted">Généré le {e(now)} — boucle propose → arbitre → applique : '
             "rien ne s'applique sans décision humaine.</p>"]
    parts.append("<h2>1. Findings ouverts (à arbitrer)</h2>")
    ouverts = [(p["nom"], f) for p in projects if p["existe"] for f in (p.get("findings") or [])]
    if ouverts:
        parts.append("<table><tr><th>Projet</th><th>Priorité</th><th>Cible</th><th>Constat</th></tr>")
        for nom_p, f in ouverts:
            parts.append(f"<tr><td>{e(nom_p)}</td><td>P{e(str(f.get('prio') or f.get('priorite') or '?'))}</td>"
                         f"<td>{e(f.get('cible') or '')}</td><td>{e(f.get('titre') or '')}</td></tr>")
        parts.append("</table>")
    else:
        parts.append('<p class="muted">Aucun finding ouvert.</p>')
    pratiques_v = [v for v in veille["entrees"] if v.get("type") == "pratique"
                   and v.get("statut") in ("nouveau", "etudie")]
    parts.append("<h2>2. Pratiques repérées par la veille (règle + action proposées)</h2>")
    if pratiques_v:
        for v in pratiques_v:
            parts.append(f'<h3>{e(v.get("titre") or "")}</h3>'
                         f'<p class="muted">{e(v.get("source_referentiel") or "")} — statut {e(v.get("statut"))}</p>'
                         f'<p><b>Pourquoi</b> : {e(v.get("pertinence") or "")}</p>'
                         f'<p><b>Règle d\'analyse proposée</b> : {e(v.get("regle_proposee") or "")}</p>'
                         f'<p><b>Action corrective</b> : {e(v.get("action_corrective") or "")}</p>')
    else:
        parts.append('<p class="muted">Aucune pratique en attente d\'adoption.</p>')
    parts.append("<h2>3. Remédiations déjà appliquées (exemples commentés)</h2>")
    arbitrages = (read_json(os.path.join(ROOT, ".claude", "supervision", "arbitrages.json"))
                  or {}).get("arbitrages", [])
    if arbitrages:
        parts.append("<table><tr><th>Date</th><th>Cible</th><th>Décision appliquée (commentaire)</th></tr>")
        for a in arbitrages:
            parts.append(f"<tr><td>{e(a.get('date') or '')}</td><td>{e(a.get('cible') or '')}</td>"
                         f"<td>{e(a.get('decision') or '')}</td></tr>")
        parts.append("</table>")
    parts.append(f"<footer>Actions de remédiation — {e(now)}</footer></body></html>")
    html_remed = os.path.join(EXPORTS_DIR, "actions-remediation.html")
    with open(html_remed, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))

    # --- Impression PDF via Edge headless ------------------------------------
    if not os.path.isfile(EDGE):
        print(f"exports PDF : Edge introuvable ({EDGE}) — HTML générés, PDF sautés")
        return False
    ok = True
    for src, pdf in ((html_analyse, "analyse-detaillee.pdf"),
                     (html_remed, "actions-remediation.pdf")):
        dst = os.path.join(EXPORTS_DIR, pdf)
        try:
            r = subprocess.run(
                [EDGE, "--headless=new", "--disable-gpu",
                 f"--print-to-pdf={dst}", "--no-pdf-header-footer",
                 "file:///" + src.replace(os.sep, "/")],
                capture_output=True, timeout=60)
            ok = ok and r.returncode == 0 and os.path.isfile(dst)
        except (OSError, subprocess.TimeoutExpired):
            ok = False
    print(f"exports PDF : {'2 PDF régénérés' if ok else 'échec partiel'} -> {os.path.relpath(EXPORTS_DIR, ROOT)}")
    return ok


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    config = read_json(CONFIG_PATH)
    if not config or "projets" not in config:
        print(f"projets.json introuvable ou invalide : {CONFIG_PATH}", file=sys.stderr)
        return 1
    cfg = [p for p in config["projets"] if os.path.isdir(p["chemin"])]

    etats_refresh = {}
    if "--no-refresh" not in argv:
        etats_refresh = refresh_local_scans(cfg)

    projects = [
        scan_project(p["nom"], p["chemin"], p.get("description", ""), p.get("livrable"))
        for p in config["projets"]
    ]
    veille = load_veille()
    now_dt = dt.datetime.now()
    now = now_dt.strftime("%Y-%m-%d %H:%M")
    pilotage = compute_pilotage(projects, veille, now_dt)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(render_md(projects, veille, now, pilotage, now_dt))
    if "--pdf" in argv:
        # avant le rendu HTML : l'onglet Actions vérifie l'existence des PDF
        generate_pdfs(projects, veille, now)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(render_html(projects, veille, now, pilotage, now_dt))
    total_skills = sum(len(p["skills"]) for p in projects if p["existe"])
    alertes = {p["nom"]: p["alerte"] for p in projects if p["existe"] and p["alerte"]}
    echecs = [n for n, s in etats_refresh.items() if s == "echec"]
    print(
        f"{len([p for p in projects if p['existe']])} projets scannés"
        f" (scans locaux relancés : {sum(1 for s in etats_refresh.values() if s == 'rafraichi')}"
        f"{', échecs : ' + ', '.join(echecs) if echecs else ''}), "
        f"{total_skills} skills, alertes: {alertes or 'aucune'}, "
        f"{len(pilotage['runs_a_solder'])} run(s) à solder, "
        f"{len(pilotage['retards'])} retard(s) de cadence -> "
        f"{os.path.relpath(OUT_MD, ROOT)}, {os.path.relpath(OUT_HTML, ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
