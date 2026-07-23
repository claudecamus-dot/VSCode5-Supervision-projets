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
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


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
    findings = [
        {
            "categorie": f.get("categorie", "?"),
            "priorite": f.get("priorite", 0),
            "cible": f.get("cible", ""),
            "titre": f.get("titre", ""),
        }
        for f in diagnostic.get("findings", [])
        if isinstance(f, dict)
    ]

    return {
        "nom": nom,
        "chemin": chemin,
        "description": description,
        "existe": os.path.isdir(chemin),
        "livrable": resolve_livrable(chemin, livrable),
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
    }


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

    lines += ["## 2. Veille agentic", ""]
    if veille["derniere_veille"]:
        lines.append(f"_Dernière veille : {veille['derniere_veille']} — skill `veille-agentic` "
                     "(cadence 3 jours, déclenchable manuellement)._")
    else:
        lines.append("_Aucune veille enregistrée — lancer la skill `veille-agentic`._")
    lines.append("")
    if veille["entrees"]:
        lines.append("| Sujet | Type | Statut | Projets concernés | Pertinence |")
        lines.append("| --- | --- | --- | --- | --- |")
        for e in veille["entrees"]:
            lines.append(
                f"| [{e.get('titre', '?')}]({e.get('url', '')}) | {e.get('type', '?')} | "
                f"{e.get('statut', 'nouveau')} | {', '.join(e.get('projets_concernes', []) or ['—'])} | "
                f"{e.get('pertinence', '')} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


HTML_HEAD = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Supervision multi-projets</title>
<style>
body { font-family: "Segoe UI", system-ui, sans-serif; margin: 2rem auto; max-width: 1100px;
       padding: 0 1rem; color: #1a2233; background: #fafbfc; }
h1 { border-bottom: 3px solid #0e2a47; padding-bottom: .3rem; }
h2 { color: #0e2a47; margin-top: 2.4rem; border-bottom: 1px solid #d5dbe3; padding-bottom: .25rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .92rem; }
th, td { border: 1px solid #d5dbe3; padding: .45rem .6rem; text-align: left; vertical-align: top; }
th { background: #0e2a47; color: #fff; }
tr:nth-child(even) { background: #f0f3f7; }
.ok { color: #1a7f37; font-weight: 600; }
.ko { color: #b42318; font-weight: 600; }
.muted { color: #667085; font-size: .85rem; }
.badge { display: inline-block; background: #e8eef5; border-radius: 4px; padding: .1rem .45rem;
         margin: .1rem .15rem; font-size: .85rem; }
.badge.hot { background: #d1e9d5; }
.badge.cold { background: #f5e1e0; }
.alert-critique { display: inline-block; background: #b42318; color: #fff; border-radius: 4px;
                  padding: .1rem .5rem; font-size: .82rem; font-weight: 600; }
.alert-majeur { display: inline-block; background: #c98a00; color: #fff; border-radius: 4px;
                padding: .1rem .5rem; font-size: .82rem; font-weight: 600; }
.alert-ok { display: inline-block; background: #1a7f37; color: #fff; border-radius: 4px;
            padding: .1rem .5rem; font-size: .82rem; font-weight: 600; }
.finding { margin: .25rem 0; padding-left: .5rem; border-left: 3px solid #c98a00; }
.prio-high { border-left-color: #b42318; }
details { margin: .8rem 0; background: #fff; border: 1px solid #d5dbe3; border-radius: 6px; }
details > summary { cursor: pointer; padding: .6rem .9rem; font-weight: 600; font-size: 1.02rem;
                    list-style: none; display: flex; align-items: center; gap: .6rem; }
details > summary::before { content: "▸"; transition: transform .15s; }
details[open] > summary::before { transform: rotate(90deg); }
details > div { padding: .2rem 1.1rem 1rem; }
.statut-nouveau { color: #0e5fa8; font-weight: 600; }
.statut-adopte { color: #1a7f37; font-weight: 600; }
.statut-ecarte { color: #667085; }
.pilotage { background: #0e2a47; color: #fff; border-radius: 8px; padding: 1rem 1.3rem;
            margin: 1.2rem 0; }
.pilotage .chiffres { display: flex; gap: 2.2rem; flex-wrap: wrap; margin-bottom: .6rem; }
.pilotage .chiffre { text-align: center; }
.pilotage .chiffre b { display: block; font-size: 1.7rem; line-height: 1.1; }
.pilotage .chiffre span { font-size: .8rem; opacity: .8; }
.pilotage ul { margin: .4rem 0 .2rem 1.2rem; padding: 0; font-size: .9rem; }
.pilotage li { margin: .2rem 0; }
.pilotage .retard { color: #ffd28a; }
.pilotage .solder { color: #ffb3ab; }
.cadence-ok { color: #1a7f37; }
.cadence-perime { color: #c98a00; font-weight: 600; }
footer { margin-top: 3rem; color: #667085; font-size: .8rem; }
</style>
</head>
<body>
"""

ALERT_HTML = {
    "critique": '<span class="alert-critique">🔴 critique</span>',
    "majeur": '<span class="alert-majeur">🟠 majeur</span>',
    None: '<span class="alert-ok">✔ OK</span>',
}


def render_html(projects, veille, now, pilotage, now_dt):
    e = html.escape
    pil = pilotage
    parts = [HTML_HEAD, "<h1>Supervision multi-projets</h1>"]
    parts.append(
        f'<p class="muted">Généré le {e(now)} par scripts/scan_projets.py — ne pas éditer à la main.</p>'
    )

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

    # ---- Section 2 : veille agentic -----------------------------------------
    parts.append("<h2>2. Veille agentic</h2>")
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
    if veille["entrees"]:
        parts.append("<table><tr><th>Sujet</th><th>Type</th><th>Statut</th>"
                     "<th>Projets concernés</th><th>Pertinence</th></tr>")
        for v in veille["entrees"]:
            statut = v.get("statut", "nouveau")
            cls = {
                "nouveau": "statut-nouveau",
                "adopte": "statut-adopte",
                "ecarte": "statut-ecarte",
            }.get(statut, "")
            url = v.get("url", "")
            titre = e(v.get("titre", "?"))
            link = f'<a href="{e(url)}">{titre}</a>' if url else titre
            parts.append(
                f"<tr><td>{link}</td><td>{e(v.get('type', '?'))}</td>"
                f'<td><span class="{cls}">{e(statut)}</span></td>'
                f"<td>{e(', '.join(v.get('projets_concernes', []) or ['—']))}</td>"
                f"<td>{e(v.get('pertinence', ''))}</td></tr>"
            )
        parts.append("</table>")

    parts.append(f"<footer>Supervision projets — {e(now)}</footer></body></html>")
    return "\n".join(parts)


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
