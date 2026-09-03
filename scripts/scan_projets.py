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

import ast
import concurrent.futures
import datetime as dt
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "projets.json")
VEILLE_PATH = os.path.join(ROOT, ".claude", "veille", "veille.json")
OUT_MD = os.path.join(ROOT, "docs", "wiki", "projets-supervision.md")
OUT_HTML = os.path.join(ROOT, "docs", "wiki.html")
EXPORTS_DIR = os.path.join(ROOT, "docs", "wiki", "exports")
HISTORY_PATH = os.path.join(ROOT, "docs", "wiki", "history", "snapshots.jsonl")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Seuils d'alerte sur la priorité des findings des superviseurs locaux (1..5)
PRIO_CRITIQUE = 5
PRIO_MAJEUR = 4

# Seuils de péremption des cadences (jours)
CADENCE_SCAN_J = 3        # scan étage 1 — rafraîchi par ce script, doit rester frais
CADENCE_DIAGNOSTIC_J = 14  # cadence documentée d'agent-supervisor
CADENCE_COMMIT_J = 14      # un projet actif sans commit depuis 14 j interroge
CADENCE_VEILLE_J = 3       # cadence de la skill veille-agentic
# Audit qualitatif : il ne périme pas au calendrier, il périme AU CODE ÉCRIT.
# Finding `VScode5:audit-technique-perime`, arbitré le 2026-09-01 — l'audit du hub avait
# 34 jours pendant que 6 781 lignes s'ajoutaient, dont les deux scripts qui ont produit
# les défauts du jour. Le calendrier seul ne l'aurait pas dit plus tôt que le code ; et
# à l'inverse un projet gelé n'a aucune raison de repayer un audit LLM tous les 30 jours.
# D'où la DOUBLE condition : les deux, jamais l'une seule.
CADENCE_AUDIT_J = 30
AUDIT_LIGNES_SEUIL = 1500  # lignes du dispositif changées depuis la date de l'audit
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


def _refresh_un_projet(p):
    """Relance le scan étage 1 d'UN projet. Rendu séparé pour être exécutable en
    parallèle : chaque scan écrit dans SON dépôt, il n'y a aucun état partagé."""
    script = os.path.join(p["chemin"], ".claude", "supervision", "scan_transcripts.py")
    if not os.path.isfile(script):
        return p["nom"], "absent"
    try:
        r = subprocess.run(
            [sys.executable, "-X", "utf8", script],
            cwd=p["chemin"], capture_output=True, timeout=90,
        )
        return p["nom"], "rafraichi" if r.returncode == 0 else "echec"
    except (OSError, subprocess.TimeoutExpired):
        return p["nom"], "echec"


def refresh_local_scans(projets_cfg):
    """Relance le scan étage 1 (déterministe, 0 token) de chaque projet qui en a un,
    pour que l'agrégation porte sur du frais — pas sur le dernier passage local.
    Renvoie {nom: 'rafraichi' | 'absent' | 'echec'}.

    EN PARALLÈLE depuis le 2026-07-30 (étude de latence, arbitrée) : c'était une boucle
    séquentielle de 5 à 6 sous-processus à ~2,5-4 s chacun, soit l'essentiel des ~16-24 s
    du bouton « Re-scan » du wiki. Les scans sont indépendants — chacun lit et écrit dans
    son propre dépôt, aucun état partagé — donc la durée tombe à celle du plus lent.
    Gain de temps pur : 0 token, aucune contrepartie.

    Le parallélisme reste borné : un thread par projet, jamais plus (la flotte en compte
    6). `subprocess.run` relâche le GIL pendant l'attente, des threads suffisent — pas
    besoin de processus. L'ordre du dict rendu suit la config, pas l'ordre d'arrivée, pour
    que la sortie du scan reste stable d'une exécution à l'autre."""
    projets_cfg = list(projets_cfg)
    if not projets_cfg:
        return {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(projets_cfg)) as pool:
        resultats = dict(pool.map(_refresh_un_projet, projets_cfg))
    return {p["nom"]: resultats[p["nom"]] for p in projets_cfg}


def read_runs(chemin):
    """Lit runs.jsonl du projet : (compteurs par résultat, liste des en-attente).

    `errors="replace"` et non le décodage strict par défaut : un seul octet non-UTF-8
    dans le journal d'UN projet suffisait sinon à faire remonter un `UnicodeDecodeError`
    jusqu'à `main()` — qui n'a pas de handler — et à faire échouer TOUT le scan, wiki
    compris. C'est exactement ce que produit un `Add-Content` PowerShell 5.1 (0xe9 pour
    « é »). Fail-open comme `git_etat` : un journal corrompu dégrade la mesure de ce
    projet-là (la ligne fautive devient illisible, donc ignorée par `json.loads`), il
    n'interrompt ni la lecture des lignes suivantes ni le scan des autres projets."""
    path = os.path.join(chemin, ".claude", "orchestration", "runs.jsonl")
    compteurs, en_attente = {}, []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
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
            capture_output=True, timeout=15, text=True, encoding="utf-8",
        )
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_etat(chemin):
    """Dette non commitée et nombre de branches d'un dépôt (0 token, git seul).

    Ferme deux ⬜ du référentiel `criteres-pratiques.md` (§ 1, DORA) que le hub
    annonçait sans les mesurer :

    - **dette non commitée** : le hook de session la voit (`arbre_sale()`), mais SUR LE
      HUB SEUL. Les 5 autres dépôts étaient un angle mort — au 2026-07-30, VSCode2
      portait 19 fichiers non commités dont 13 sous `app/`, et personne ne le voyait
      depuis le hub. C'est pourtant la leçon R2 la plus chère du projet (174 fichiers
      d'un chantier étranger découverts au moment de committer).
    - **trunk-based** : « < 3 branches actives », annoncé « mesurable via git branch,
      à ajouter au scan » depuis le 2026-07-23.

    Fail-open : pas un dépôt git, git absent, timeout → None sur les deux compteurs
    (le scan ne doit jamais échouer à cause d'un projet, cf. les 5 autres dimensions)."""
    def _git(*args):
        try:
            r = subprocess.run(["git", "-C", chemin, *args],
                               capture_output=True, timeout=15, text=True,
                               encoding="utf-8", errors="replace")
            return r.stdout if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    statut = _git("status", "--porcelain")
    branches = _git("branch", "--format=%(refname:short)")
    sales = [] if statut is None else [l for l in statut.splitlines() if l.strip()]
    # Âge du DOYEN non commité (finding flotte:canon-ecrit-jamais-commite (b),
    # arbitré le 2026-08-31) : « 20 non commités » ne distingue pas une séance en
    # cours d'une dette de 39 jours — « 20 · doyen 39 j » tranche d'un coup d'œil.
    # Même méthode que la preuve du finding (mtime) ; un chemin disparu (statut D)
    # n'a plus de mtime : ignoré, jamais inventé.
    doyen = None
    for ligne in sales:
        rel = ligne[3:].split(" -> ")[-1].strip().strip('"')
        try:
            age = int((time.time() - os.path.getmtime(os.path.join(chemin, rel)))
                      // 86400)
        except (OSError, ValueError):
            continue
        if age >= 0 and (doyen is None or age > doyen):
            doyen = age
    return {
        "non_commite": None if statut is None else len(sales),
        "branches": None if branches is None else len(
            [l for l in branches.splitlines() if l.strip()]),
        "doyen_jours": doyen,
    }


def cellule_arbre(n, doyen):
    """Cellule « arbre de travail » du tableau des cadences. Un arbre sale n'est
    pas une faute (une séance en cours) ; c'est un risque R2 — et l'âge du doyen
    dit s'il s'agit d'une séance ou d'une dette (39 j mesurés le 2026-08-31 sur
    les 5 dépôts de la flotte, personne ne le voyait)."""
    if n == 0:
        return "<span class='cadence-ok'>propre</span>"
    if n is None:
        return "?"
    suffixe = f" · doyen {doyen} j" if doyen is not None else ""
    return (f"<span class='cadence-perime'>{n} non commité"
            f"{'s' if n > 1 else ''}{suffixe}</span>")


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


def ecrire_atomique(path, contenu):
    """Publie `contenu` dans `path` sans jamais laisser d'artefact tronqué.

    `open(path, "w")` vide le fichier À L'OUVERTURE, donc AVANT que le rendu passé en
    argument à `fh.write(...)` ne soit évalué : une exception pendant le rendu publiait
    un `docs/wiki.html` de 0 octet à la place des 230 Ko de la page servie. L'appelant
    calcule donc le contenu d'abord ; on l'écrit ici dans un temporaire voisin (même
    dossier, donc même volume) puis `os.replace` bascule la version complète d'un seul
    coup. Un lecteur du wiki voit l'ancienne page ou la nouvelle, jamais un fichier vide."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(contenu)
    os.replace(tmp, path)


def tronque(txt, limite):
    """Coupe à la dernière frontière de mot avant `limite` et signale la coupe
    par une ellipse. Un `txt[:n]` brut coupait en plein mot (« un process
    PowerShell par r ») et le lecteur croyait lire la phrase entière — finding
    wiki:finitions-lisibilite. Le texte complet reste accessible via title=."""
    txt = (txt or "").strip()
    if len(txt) <= limite:
        return txt
    coupe = txt[:limite]
    espace = coupe.rfind(" ")
    if espace > limite * 0.6:          # sinon un mot très long mangerait tout
        coupe = coupe[:espace]
    return coupe.rstrip(" ,;:.—-") + "…"


# --- Détail borné : résumé dans la page, texte intégral par un lien ----------
# Arbitrage du 2026-09-02 (« les deux, générateur d'abord ») sur un défaut mesuré :
# la page pesait 483 938 octets / 57 162 mots (+15,8 % de mots en 24 h) alors que
# le nombre d'onglets n'avait pas bougé — « le même étage a juste été rempli ».
# Exemple chiffré de la salle d'inspection : une synthèse d'audit peut narrer une
# enquête sur plusieurs centaines de caractères (895 mesurés dans
# .claude/audits/*.json, 14 des 24 synthèses dépassent 240 caractères) et
# `tronque()` ne borne que le texte AFFICHÉ — le texte intégral, lui, part quand
# même en entier dans l'attribut title=, et deux fois : la cellule de la table
# d'audit et la carte de l'onglet Arbitrer partagent la même source
# (`ecarts_du_projet`). Une pastille verte « Dimension Revue de code. » (24
# caractères) et cette synthèse-là logent dans la même cellule `<small>`, même
# police, même couleur — rien ne dit au lecteur que l'une est un résumé et
# l'autre une enquête complète.
#
# DETAIL_LIMITE borne aussi title=, pas seulement l'affichage. Sous la limite :
# rien ne change, title= porte le texte complet (leçon wiki:finitions-lisibilite).
# Au-dessus : title= s'arrête à la limite et le texte intégral part dans
# docs/wiki/projets-supervision.md — canal de détail déjà publié par ce même
# script, pas un mécanisme inventé pour l'occasion — avec un lien VISIBLE (pas
# seulement une infobulle qu'il faut deviner) vers l'ancre correspondante.
# Aucune information ne disparaît, elle change de canal.
DETAIL_LIMITE = 240


def _slug(txt):
    """Identifiant d'ancre stable : minuscules, ASCII, tirets.

    Utilisé à l'identique côté HTML (le lien) et côté markdown (l'ancre posée
    dans docs/wiki/projets-supervision.md) : c'est la MÊME fonction des deux
    côtés qui les fait correspondre, pas la convention d'autoslug d'un moteur de
    rendu markdown (variable d'un visualiseur à l'autre)."""
    return re.sub(r"[^a-z0-9]+", "-", (txt or "").lower()).strip("-") or "x"


def ancre_synthese(projet, dim_key):
    """Ancre partagée par le lien HTML et l'appendice markdown pour LA MÊME
    synthèse d'audit (projet, dimension) — voir DETAIL_LIMITE ci-dessus."""
    return f"audit-{_slug(projet)}-{dim_key}"


def rendu_detail_borne(e, texte, ancre):
    """Attribut `title=` borné à DETAIL_LIMITE + lien visible si le texte le dépasse.

    Renvoie `(attribut_title, lien_html)`. Sous la limite, `lien_html` est vide et
    `attribut_title` porte le texte complet — comportement IDENTIQUE à avant
    (aucune régression sur les synthèses courtes, la majorité des cas). Au-dessus,
    `attribut_title` s'arrête à la limite et `lien_html` pointe vers l'ancre du
    détail intégral."""
    if not texte:
        return "", ""
    if len(texte) <= DETAIL_LIMITE:
        return f' title="{e(texte)}"', ""
    attr = f' title="{e(texte[:DETAIL_LIMITE].rstrip())}…"'
    lien = (f' <a class="lien-detail" href="wiki/projets-supervision.md#{ancre}">'
            "détail complet →</a>")
    return attr, lien


def details_syntheses_longues(existants):
    """(projet, dim_key, lib, texte) pour chaque synthèse d'audit qui dépasse
    DETAIL_LIMITE — LA source commune consultée par le HTML (pour poser le lien)
    ET par le markdown (pour publier le texte intégral que ce lien cible). Une
    seule fonction pour les deux : elles ne peuvent pas diverger sur ce qui
    dépasse la limite."""
    out = []
    for p in existants:
        dims = (p.get("audit") or {}).get("dimensions") or {}
        for key, lib in DIM_AUDIT:
            syn = (dims.get(key) or {}).get("synthese") or ""
            if len(syn) > DETAIL_LIMITE:
                out.append((p["nom"], key, lib, syn))
    return out


# --- Divergence des copies de pptx_deck.py (finding pptx_deck:matrice-
# divergence, arbitré 2026-07-29) : la dette de duplication n°1 de la flotte,
# chiffrée à chaque scan (ast, 0 token). La mesure rend arbitrable l'extraction
# d'un cœur commun — elle ne décide rien (leçon P1 : la dette n'est pas
# uniforme, VSCode4 porte un fork réel).
PPTX_DECK_COPIES = {
    "VSCode2": os.path.join("app", "services", "pptx_deck.py"),
    "VSCode3": os.path.join("docs", "cadrage-ppt", "pptx_deck.py"),
    "VSCode4": os.path.join("scripts", "pptx_deck.py"),
}


def signatures_fonctions(chemin):
    """{nom: signature} des fonctions top-niveau d'un fichier Python.

    Fichier absent ou non parsable -> None : la matrice l'affiche comme tel,
    le scan ne casse jamais pour une copie malade."""
    src = read_text(chemin)
    if src is None:
        return None
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return None
    return {n.name: ast.unparse(n.args)
            for n in arbre.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def matrice_divergence_pptx_deck(projets):
    """Fonctions communes aux copies, propres à chacune, et écarts de signature
    sur les communes — les trois chiffres qui manquaient au tableau de bord."""
    copies = []
    for p in projets:
        rel = PPTX_DECK_COPIES.get(p["nom"])
        if not rel:
            continue
        chemin = os.path.join(p["chemin"], rel)
        fns = signatures_fonctions(chemin)
        src = read_text(chemin)
        copies.append({
            "projet": p["nom"], "rel": rel.replace(os.sep, "/"),
            "fonctions": fns,
            "lignes": len(src.splitlines()) if src is not None else 0,
        })
    presentes = [c for c in copies if c["fonctions"] is not None]
    if len(presentes) < 2:
        return {"copies": copies, "communes": [], "propres": {}, "divergentes": []}
    ensembles = {c["projet"]: set(c["fonctions"]) for c in presentes}
    communes = sorted(set.intersection(*ensembles.values()))
    propres = {
        c["projet"]: sorted(
            ensembles[c["projet"]]
            - set.union(*(e for n, e in ensembles.items() if n != c["projet"])))
        for c in presentes
    }
    divergentes = []
    for f in communes:
        signatures = {c["projet"]: c["fonctions"][f] for c in presentes}
        if len(set(signatures.values())) > 1:
            divergentes.append({"fonction": f, "signatures": signatures})
    return {"copies": copies, "communes": communes, "propres": propres,
            "divergentes": divergentes}


def render_divergence_html(e, mat):
    """Bloc HTML de la matrice, section « Pratiques, couverture & risques »."""
    parts = ["<h3>Divergence des copies de <code>pptx_deck.py</code></h3>"]
    parts.append(
        '<p class="legende">Trois projets embarquent leur copie de la '
        "bibliothèque de slides. Mesure ast à chaque scan (0 token) — l'écart "
        "chiffré ci-dessous est ce qui rendra arbitrable, plus tard, "
        "l'extraction d'un cœur commun. Une divergence n'est pas toujours un "
        "défaut : les adaptations locales sont légitimes, l'invisible ne "
        "l'est pas.</p>")
    parts.append("<table><tr><th>Copie</th><th>Lignes</th><th>Fonctions</th>"
                 "<th>Propres à cette copie</th></tr>")
    for c in mat["copies"]:
        if c["fonctions"] is None:
            parts.append(f"<tr><td><b>{e(c['projet'])}</b> <small>{e(c['rel'])}</small></td>"
                         '<td colspan="3">⚠️ absente ou non parsable</td></tr>')
            continue
        p_list = mat["propres"].get(c["projet"], [])
        detail = ", ".join(p_list[:8]) + ("…" if len(p_list) > 8 else "")
        parts.append(
            f"<tr><td><b>{e(c['projet'])}</b> <small>{e(c['rel'])}</small></td>"
            f"<td>{c['lignes']}</td><td>{len(c['fonctions'])}</td>"
            f"<td>{len(p_list)}<small> {e(detail)}</small></td></tr>")
    parts.append("</table>")
    div = mat["divergentes"]
    parts.append(
        f'<p class="legende"><b>{len(mat["communes"])}</b> fonction(s) communes aux '
        f"{len([c for c in mat['copies'] if c['fonctions'] is not None])} copies, "
        f"dont <b>{len(div)}</b> à signature divergente"
        + (" : " + ", ".join(f"<code>{e(d['fonction'])}</code>" for d in div[:10])
           + ("…" if len(div) > 10 else "") if div else "")
        + ".</p>")
    return "\n".join(parts)


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


TITRE_DISCIPLINE_TOKENS = re.compile(
    r"^#{1,4}\s.*(discipline\s+de\s+gestion\s+des\s+tokens|optimisation\s+tokens"
    r"|gestion\s+du\s+contexte)", re.I | re.M)


def discipline_tokens(chemin):
    """Le projet documente-t-il une discipline de contexte/tokens ? (0 token, marqueur)

    Adoption de la trouvaille de veille « Gestion du contexte outillée » (2026-07-24,
    doc officielle : la fenêtre de contexte est LA ressource à gérer — /compact cadré,
    sous-agents pour l'exploration, lecture ciblée). Elle a dormi 6 jours en statut
    `nouveau` et est remontée en finding `veille:contexte-outille` le 2026-07-30 : une
    règle proposée qui n'entre ni au référentiel ni au scan reste une intention.

    On exige un TITRE de section, pas une occurrence du mot « token » : les CLAUDE.md
    parlent de tokens en passant (« grille ~50 tokens », « étage 1, 0 token ») sans
    documenter la moindre discipline. Mesuré à la première adoption : 5 projets sur 6
    ont la section (VSCode, VSCode1, VSCode2, VSCode3, VSCode4) — le seul manque est le
    hub lui-même, ce qui contredisait la trouvaille (qui annonçait VSCode1/VSCode3
    seulement). Lire l'état réel avant d'écrire, R1."""
    for rel in ("CLAUDE.md", "CONVENTIONS.md",
                os.path.join("docs", "wiki", "technical", "conventions.md")):
        txt = read_text(os.path.join(chemin, rel))
        if txt and TITRE_DISCIPLINE_TOKENS.search(txt):
            return True
    return False


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


def _contient_un_deck(chemin):
    """Un dossier d'export de ce projet contient-il RÉELLEMENT un deck ?

    Le critère portait sur le nom du répertoire (`Exports`/`export`) : trois projets
    de livrable `web` étaient de ce fait jugés sur une discipline de design de slide,
    dont le hub, dont l'`export/` est son kit agentic. On cherche donc le `.pptx`.

    Profondeur bornée à 2 niveaux : un deck rangé dans `export/2026-09/` compte, mais
    on ne descend pas tout un dépôt — le scan doit rester à 0 token ET rapide.
    """
    for dossier in ("Exports", "export"):
        racine = os.path.join(chemin, dossier)
        if not os.path.isdir(racine):
            continue
        try:
            for entree in os.scandir(racine):
                if entree.is_file() and entree.name.lower().endswith(".pptx"):
                    return True
                if entree.is_dir():
                    try:
                        if any(f.lower().endswith(".pptx")
                               for f in os.listdir(entree.path)):
                            return True
                    except OSError:
                        continue
        except OSError:
            continue
    return False


def permissions_par_canal(chemin):
    """Les permissions d'un projet, par CANAL — versionné et local.

    Arbitrage `flotte:rtk-settings-local` (2026-09-01). Le scan ne lisait que
    `.claude/settings.json`. Or `settings.local.json` est git-ignoré : il porte des
    permissions bien réelles que ni un commit scopé (R2) ni ce scan ne voyaient.
    Conséquence mesurée : l'arbitrage `flotte:rtk` du 2026-07-29 annonçait le retrait
    de l'outil « de toute la flotte, permissions comprises » alors que `Bash(rtk *)`
    survivait dans TROIS `settings.local.json` — 11 permissions actives sur 3 dépôts
    sur 5. Un retrait de flotte s'arrêtait à la frontière du versionné EN SILENCE.

    Rend `versionne`, `local`, et `local_seules` — les permissions que SEUL le canal
    git-ignoré porte, c'est-à-dire précisément celles qu'un retrait par commit ne peut
    pas atteindre. Les trois familles (`allow`, `ask`, `deny`) sont balayées : un
    `deny` posé en local est une garantie que le canal versionné ne porte pas, et le
    scan la comptait pour rien.

    Dégrade sans planter sur un JSON illisible : une mesure absente vaut mieux qu'un
    scan qui tombe.
    """
    def _perms(nom):
        d = read_json(os.path.join(chemin, ".claude", nom)) or {}
        perms = d.get("permissions") or {}
        out = []
        for cle in ("allow", "ask", "deny"):
            v = perms.get(cle)
            if isinstance(v, list):
                out.extend(x for x in v if isinstance(x, str))
        return out

    versionne = _perms("settings.json")
    local = _perms("settings.local.json")
    return {
        "versionne": versionne,
        "local": local,
        "local_seules": [x for x in local if x not in versionne],
    }


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
    settings_local = read_json(os.path.join(chemin, ".claude", "settings.local.json")) or {}
    # Les deux canaux, parce que l'ensemble EFFECTIF est leur union : un hook ou un
    # deny pose dans le fichier git-ignore compte autant (arbitrage
    # flotte:rtk-settings-local du 2026-09-01).
    canaux = permissions_par_canal(chemin)
    settings_txt = json.dumps([settings, settings_local])

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
    # Un dossier nommé « export » n'est PAS un deck. Mesuré le 2026-09-01 : la
    # présence du seul répertoire faisait juger VSCode1, VSCode2 et VScode5 — tous
    # trois de livrable `web` — sur une discipline de design de slide, alors qu'aucun
    # des trois `export/` ne contient un seul .pptx (0, 0 et 0 sur 5, 13 et 50
    # fichiers). Celui du hub est son kit agentic. Un critère qui teste un nom de
    # répertoire mesure une ressemblance, pas un livrable — même faute que l'étage 1
    # qui compte la présence d'une skill pour son fonctionnement.
    produit_deck = (livrable_deck
                    or "restitution-ppt" in skills
                    or _contient_un_deck(chemin))
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
    tokens = discipline_tokens(chemin)
    score = sum([linter, ci, claude_md, conventions, tokens])
    d_pratiques = {
        "niveau": _niveau(score >= 4, score >= 1),
        "detail": ", ".join(filter(None, [
            "linter" if linter else None, "CI" if ci else None,
            claude_md_libelle(claude_lignes),
            "conventions" if conventions else None,
            "discipline tokens" if tokens else "⬜ pas de discipline tokens écrite",
        ])) or "rien de configuré",
    }

    # 6. Proxies sécurité (déterministes — pas un audit, des garde-fous présents)
    gitignore = read_text(os.path.join(chemin, ".gitignore")) or ""
    env_ignore = ".env" in gitignore
    deny_rules = bool((settings.get("permissions") or {}).get("deny")
                      or (settings_local.get("permissions") or {}).get("deny"))
    guard_hook = "guard_destructive_git" in settings_txt
    env_committed = os.path.isfile(os.path.join(chemin, ".env")) and not env_ignore
    sec_score = sum([env_ignore, deny_rules, guard_hook])
    # Les permissions du seul canal git-ignore sont une EXPOSITION, pas une protection.
    # Premiere version de ce rendu (2026-09-01, matin) : elles etaient enumerees dans la
    # meme liste que les garde-fous, sous la meme pastille verte et la legende « Garde-
    # fous PRESENTS » — « deny rules, guard git, 89 perm. hors git ». Les 89 de VSCode1
    # n'ont jamais ete relues et contiennent `Read(//c/Users/claude.camus/**)`, deux
    # `Edit` sur les skills globales, `Bash(node -e ...)` a joker, `Skill(run:*)`. Une
    # exposition rendue comme une protection : exactement la famille de defaut que la
    # journee corrigeait, commise dans la mesure censee la fermer.
    hors_git = len(canaux["local_seules"])
    _niv = "absent" if env_committed else _niveau(sec_score >= 2, sec_score >= 1)
    # La NOTATION, pas seulement l'affichage : un ensemble de permissions qu'aucun
    # commit ne peut relire n'est pas une posture verte. Plafond, pas penalite —
    # un projet sans permission hors git atteint le vert comme avant.
    if hors_git and _niv == "ok":
        _niv = "moyen"
    _garde_fous = ", ".join(filter(None, [
        ".env gitigné" if env_ignore else None,
        "deny rules" if deny_rules else None,
        "guard git" if guard_hook else None])) or "aucun garde-fou"
    _detail = "⚠ .env non gitigné" if env_committed else _garde_fous
    if hors_git:
        _detail += (f" · ⚠ {hors_git} perm. hors git, "
                    "jamais relues par un commit")
    d_secu_proxy = {"niveau": _niv, "detail": _detail}

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
        # Ce qu'un retrait de flotte par commit ne peut pas atteindre.
        "permissions_locales_seules": canaux["local_seules"],
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


CANON_SCAN = os.path.join(ROOT, ".claude", "dispositif", "canon", "scan_transcripts.py")
_CANON_CACHE = []


def _canon():
    """Le module du canon, ou None s'il est illisible (fail-open).

    Import PARESSEUX et mis en cache : le canon est chargé une fois, à la première
    évaluation de findings, pas à l'import de ce fichier — un scan qui planterait à
    l'import parce qu'un fichier du dispositif est en cours d'édition serait pire que
    le défaut qu'on corrige.
    """
    if _CANON_CACHE:
        return _CANON_CACHE[0]
    module = None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("canon_scan_transcripts", CANON_SCAN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:   # noqa: BLE001 - fail-open, cf. docstring
        module = None
    _CANON_CACHE.append(module)
    return module


def findings_ouverts(diagnostic, arbitrages):
    """Sépare les constats d'un diagnostic en (ouverts, masqués), via la règle DU CANON.

    LE DÉFAUT QUE ÇA CORRIGE (demande utilisateur du 2026-09-02, « beaucoup de projets
    sont notés critiques, est-ce normal ? »). Ce fichier tenait sa propre version de la
    règle : l'ensemble de TOUTES les cibles jamais arbitrées, et tout finding dont la
    cible s'y trouvait était écarté — sans regarder la catégorie, ni la date, ni le
    drapeau `re_challenge`. `diag_date` était lu juste au-dessus et jamais utilisé.
    Un finding dont la cible avait été arbitrée UNE fois devenait donc invisible pour
    toujours, et plus un sujet récidivait, plus sûrement ses nouveaux constats
    disparaissaient. Mesuré avant correction : 3 findings invisibles sur la flotte, dont
    un p5 — `revue-increment` chez VSCode2, éteint par 10 arbitrages datant tous de
    juillet alors que le constat était du 2026-09-01.

    POURQUOI ON N'ÉCRIT PAS UNE TROISIÈME VERSION. Le canon tenait déjà la règle juste,
    et depuis le 2026-07-28 : `finding_arbitre()` compare la cible ET la couverture de
    catégorie, et n'oppose un arbitrage ANTÉRIEUR au diagnostic à un constat re-challengé
    que s'il est du jour même ou postérieur. `diagnostic_masques()` rend en plus visibles
    les constats écartés — « le filtrage était silencieux ». Les deux moitiés de ce qu'il
    fallait existaient ; le hub s'en était écrit une copie naïve à côté sans le savoir.
    C'est le motif que ce dépôt paie en boucle : deux définitions d'une même chose
    divergent, et c'est la plus récente qui perd, parce que personne ne sait qu'elle est
    là.

    Vérifié avant de câbler : appliquée aux 3 masqués, la règle du canon en rouvre 2
    (ceux qui portent `re_challenge: True`) et laisse le 3ᵉ fermé. Elle ne rouvre pas
    tout — elle rouvre ce que le superviseur avait explicitement re-challengé.

    Fail-open : canon injoignable → aucun filtre, tous les constats sont rendus ouverts.
    Un tableau de bord qui montre trop se corrige en le lisant ; un tableau qui cache ne
    se corrige pas, puisque personne ne sait qu'il manque quelque chose.
    """
    bruts = [f for f in (diagnostic or {}).get("findings", []) if isinstance(f, dict)]
    if not bruts:
        return [], []

    def _resume(f):
        return {
            "categorie": f.get("categorie", "?"),
            "priorite": f.get("priorite", 0),
            "cible": f.get("cible", ""),
            "titre": f.get("titre", ""),
        }

    canon = _canon()
    arbitrages = [a for a in (arbitrages or []) if isinstance(a, dict) and a.get("decision")]
    if canon is None or not hasattr(canon, "finding_arbitre") or not arbitrages:
        return [_resume(f) for f in bruts], []

    genere = (diagnostic or {}).get("generated") or ""
    ouverts, masques = [], []
    for f in bruts:
        try:
            clos = canon.finding_arbitre(f, arbitrages, posterieur_a=genere)
        except Exception:   # noqa: BLE001 - fail-open : on préfère montrer que cacher
            clos = False
        (masques if clos else ouverts).append(_resume(f))
    return ouverts, masques


AGENTS_SOMMEIL = os.path.join(ROOT, ".claude", "agents-en-sommeil")


def agents_en_sommeil():
    """Les porteurs mis en sommeil : présents sur disque, retirés du routage sur décision.

    Ils vivent dans `.claude/agents-en-sommeil/`, qui porte aussi la mesure qui a motivé
    leur mise au repos et la façon de les réveiller. Les distinguer d'un porteur
    RÉELLEMENT manquant est tout l'objet de cette fonction : les confondre faisait rendre
    une décision tracée comme une panne (demande utilisateur du 2026-09-02).

    Fail-open : répertoire absent → aucun endormi, et le rendu retombe sur « absent »,
    ce qui est le comportement d'avant — jamais une exception dans un générateur.
    """
    return {n for n in list_md(AGENTS_SOMMEIL, exclude=("README.md",))
            if os.path.isfile(os.path.join(AGENTS_SOMMEIL, n + ".md"))}


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
    arbitrages = read_json(os.path.join(claude, "supervision", "arbitrages.json")) or {}
    livrable_resolu = resolve_livrable(chemin, livrable)
    findings, findings_masques = findings_ouverts(
        diagnostic, arbitrages.get("arbitrages", []))

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
        "git_etat": git_etat(chemin),
        "findings": findings,
        "findings_masques": findings_masques,
        "alerte": alert_level(findings),
        "orchestration": "agent-orchestrator" in skills,
        "supervision": "agent-supervisor" in skills,
        "pratiques": analyse_pratiques(
            chemin, set(skills), set(agents),
            livrable_deck=bool(livrable_resolu and livrable_resolu.get("type") == "deck"),
        ),
        "audit": load_audit(nom),
    }


def audit_perime(projet, now):
    """L'audit qualitatif d'un projet est-il périmé ? Double condition : temps ET code.

    Rend `(perime, jours, lignes)`. `perime` n'est vrai que si l'audit a plus de
    `CADENCE_AUDIT_J` jours **et** que plus de `AUDIT_LIGNES_SEUIL` lignes ont bougé
    depuis sa date. Un seuil de temps seul crierait sur un dépôt gelé ; un seuil de
    lignes seul laisserait passer un audit très ancien sur un dépôt calme.

    Le volume se mesure par `git log --numstat` depuis la date de l'audit — c'est du
    git local, donc 0 token, comme tout l'étage 1.

    Fail-open sur toute la chaîne (pas d'audit, date illisible, git absent, timeout) :
    le scan ne doit jamais échouer ni inventer un retard à cause d'un projet.
    """
    audit = projet.get("audit") or {}
    date_audit = parse_iso(audit.get("date"))
    if date_audit is None:
        return (False, None, None)          # jamais audité : ce n'est pas un retard
    jours = (now - date_audit).days
    try:
        r = subprocess.run(
            ["git", "-C", projet["chemin"], "log",
             f"--since={date_audit.strftime('%Y-%m-%d')}", "--numstat", "--format="],
            capture_output=True, timeout=20, text=True, encoding="utf-8",
            errors="replace")
        if r.returncode != 0:
            return (False, jours, None)
    except (OSError, subprocess.TimeoutExpired):
        return (False, jours, None)
    lignes = 0
    for ligne in r.stdout.splitlines():
        colonnes = ligne.split("\t")
        if len(colonnes) != 3:
            continue
        for n in colonnes[:2]:
            if n.isdigit():                  # « - » pour les binaires : ignoré
                lignes += int(n)
    return (jours > CADENCE_AUDIT_J and lignes > AUDIT_LIGNES_SEUIL, jours, lignes)


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


def age_doyenne_trouvaille(veille, maintenant=None, statuts=("nouveau", "etudie")):
    """(jours, titre) de la plus vieille trouvaille dans `statuts`, ou None.

    Deux attentes très différentes se cachent derrière « non arbitrée », et les
    confondre rend le signal inactionnable :

      * `nouveau` — **personne ne l'a regardée**. C'est le dispositif qui ne suit pas :
        la veille a payé pour produire une proposition que rien n'instruit.
      * `etudie` — instruite, verdict proposé, **en attente de la décision humaine**.
        L'attente est ici légitime (R4 : l'arbitrage appartient à l'utilisateur), mais
        elle ne doit pas devenir éternelle non plus.

    D'où le paramètre `statuts` : l'appelant choisit laquelle des deux il mesure.
    """
    # Naïf local, comme tout le reste du fichier : `parse_iso` convertit déjà les
    # dates aware en local naïf, mélanger les deux lève un TypeError.
    maintenant = maintenant or dt.datetime.now()
    candidates = []
    for e in veille.get("entrees", []):
        if e.get("statut") not in statuts:
            continue
        d = parse_iso(e.get("date") or veille.get("derniere_veille"))
        if d:
            candidates.append((d, e.get("titre") or "sans titre"))
    if not candidates:
        return None
    d, titre = min(candidates, key=lambda t: t[0])
    return (maintenant - d).days, titre


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
    # veille adoptee 2026-09-03 : une dimension d'audit-technique non couverte
    # (temps/acces manquant) doit pouvoir le dire plutot que forcer un niveau
    # ok/moyen/critique par defaut — cf. audit-technique/SKILL.md.
    "non_evalue": "⚪",
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
DIM_AUDIT_KEYS = {k for k, _ in DIM_AUDIT}

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
                  "deny rules, hook guard_destructive_git — lus dans les DEUX "
                  "canaux, settings.json ET settings.local.json (git-ignoré). "
                  "Alerte si un .env est commité. Les « ⚠ N perm. hors git » sont "
                  "signalées À PART des garde-fous, jamais parmi eux : ce sont les "
                  "permissions que seul le canal git-ignoré porte, donc celles qu'un "
                  "retrait de flotte par commit ne peut pas atteindre — c'est ainsi "
                  "que le retrait de rtk s'était arrêté en silence sur 3 dépôts. "
                  "Elles PLAFONNENT la note à 🟠 : un ensemble de permissions "
                  "qu'aucun commit ne relit n'est pas une posture verte (arbitrages "
                  "du 2026-09-01, le second corrigeant le rendu du premier, qui les "
                  "affichait comme un troisième garde-fou).",
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
    # Cette cellule a affirmé « + détection de dette non commitée » en statut `ok`
    # alors qu'aucun `git status --porcelain` n'existait dans ce scan (relevé par le
    # diagnostic du 2026-07-30, même classe que le finding wiki-verite du 2026-07-27).
    # Passée en `moyen` avec la mesure dite telle qu'elle était, puis remise à `ok` le
    # même jour — cette fois parce que la mesure existe VRAIMENT (git_etat, ci-dessus),
    # sur les 6 dépôts et non plus sur le seul hub. L'ordre compte : on a corrigé
    # l'affirmation d'abord, outillé ensuite. Jamais l'inverse.
    {"nom": "Gestion de version pour tout", "statut": "ok",
     "principe": "Code, config et scripts sous contrôle de version, historique propre.",
     "flotte": "6/6 en dépôt git ; règle R2 « commit scopé au périmètre » (hub).",
     "mesure": "Cadence du dernier commit + dette non commitée (`git status "
               "--porcelain`) + nombre de branches, sur les 6 dépôts."},
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
     "flotte": "(dérivé de la mesure à chaque scan — cf. craft_effectives)",
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
     "flotte": "(dérivé de la mesure à chaque scan — cf. craft_effectives)",
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
     "flotte": "Lockfile OK sur VSCode1 ; VSCode2 épinglé `==` (audit 2026-07-24, finding fermé).",
     "mesure": "Audit qualitatif — dimension Risque technique."},
    {"nom": "Conventions de code explicites", "statut": "ok",
     "principe": "Règles partagées écrites (nommage, structure, rules d'agent).",
     "flotte": "CLAUDE.md + conventions.md sur les projets outillés.",
     "mesure": "Dimension Pratiques + rules (CLAUDE.md, conventions)."},
    {"nom": "Trunk-based development", "statut": "ok",
     "principe": "Branches courtes (< 3 actives), intégration fréquente au tronc.",
     "flotte": "6/6 dépôts à une seule branche `main` (mesuré le 2026-07-30, re-mesuré "
               "le 2026-08-31).",
     "mesure": "✅ `git_etat()` (comptage `git branch`, seuil DORA < 3 au rendu). La "
               "ligne disait « non outillé » un mois après l'avoir été — corrigé le "
               "2026-08-31, finding `referentiel:deux-sources-qui-se-contredisent`."},
    {"nom": "Automatisation du déploiement", "statut": "absent",
     "principe": "Déploiement scripté et rejouable, pas d'étape manuelle.",
     "flotte": "Aucun projet outillé — pertinence à évaluer (projets locaux).",
     "mesure": "⬜ pas mesuré (cible du référentiel § 1)."},
    {"nom": "Test de non-régression sur bug corrigé", "statut": "absent",
     "principe": "Chaque bug fermé laisse un test qui échouerait s'il revenait.",
     "flotte": "Discipline à documenter dans les conventions — non détectable.",
     "mesure": "⬜ non détectable automatiquement (cible § 2)."},
]

def craft_effectives(existants):
    """CRAFT_PRATIQUES avec les cellules « Dans la flotte » de la CI et du linter
    DÉRIVÉES de la mesure du scan (dimension pratiques_rules) au lieu d'un texte
    figé — un texte figé ment dès l'arbitrage suivant (finding wiki-verite)."""
    def _avec(disp):
        return [p["nom"] for p in existants
                if disp in (p["pratiques"]["pratiques_rules"]["detail"] or "").split(", ")]
    n = len(existants)
    ci, linter = _avec("CI"), _avec("linter")

    def _statut(lst):
        return "ok" if n and len(lst) == n else ("moyen" if lst else "absent")
    out = []
    for c in CRAFT_PRATIQUES:
        c = dict(c)
        if c["nom"] == "Intégration continue":
            c["flotte"] = (f"CI GitHub Actions détectée sur {', '.join(ci)} ({len(ci)}/{n})."
                           if ci else "Aucune CI détectée sur la flotte.")
            c["statut"] = _statut(ci)
        elif c["nom"] == "Analyse statique / linter":
            c["flotte"] = (f"Linter détecté sur {', '.join(linter)} ({len(linter)}/{n})."
                           if linter else "Aucun linter détecté sur la flotte.")
            c["statut"] = _statut(linter)
        out.append(c)
    return out


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


def ecarts_du_projet(p):
    """Écarts d'un projet : dimensions déterministes non vertes + dimensions
    d'audit dégradées + findings ouverts de son diagnostic local.

    UNE SEULE source pour le bandeau du pilotage ET l'onglet Actions correctives.
    Les deux comptaient séparément — le bandeau ignorait les pratiques et
    affichait « système sain » pendant que l'onglet listait 18 écarts sur 5
    projets (revue UX 2026-07-29, P1 vérifié sur la page livrée)."""
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
            ecarts.append((f"Audit — {lib}", dd.get("niveau"),
                           dd.get("synthese") or "", cle))
    return ecarts


def libelle_ecarts(n_pratiques, n_findings):
    """Libellé HONNÊTE d'un lot d'actions correctives : une pratique mesurée en
    écart et un finding de diagnostic sont deux natures différentes, jamais
    additionnées sous un seul mot.

    Les fusionner produisait la contradiction rapportée (2026-07-29) : VScode5
    affichait « 🔴 5 pratique(s) en écart » alors que ses 9 dimensions étaient
    vertes — les 5 « écarts » étaient des findings ouverts du diagnostic."""
    morceaux = []
    if n_pratiques:
        morceaux.append(f"{n_pratiques} pratique(s) en écart")
    if n_findings:
        morceaux.append(f"{n_findings} finding(s) ouvert(s)")
    return " + ".join(morceaux) or "rien à corriger"


def compte_ecarts(projects):
    """[{projet, n_pratiques, n_findings, n_total, n_critique}] pour les projets
    qui portent un écart, du plus critique au moins critique.

    `n_pratiques` (dimensions du scan + audit) et `n_findings` (diagnostic)
    restent SÉPARÉS : le bandeau et l'onglet doivent pouvoir dire lequel des
    deux est en cause plutôt que d'annoncer des « pratiques en écart » sur un
    projet dont toutes les pratiques sont vertes."""
    resume = []
    for p in projects:
        if not p.get("existe"):
            continue
        ecarts = ecarts_du_projet(p)
        findings_p = p.get("findings") or []
        if not ecarts and not findings_p:
            continue
        n_critique = sum(1 for _, niv, _, _ in ecarts
                         if niv in ("absent", "critique")) + len(findings_p)
        resume.append({"projet": p["nom"],
                       "n_pratiques": len(ecarts),
                       "n_findings": len(findings_p),
                       "n_total": len(ecarts) + len(findings_p),
                       "n_critique": n_critique})
    resume.sort(key=lambda r: (-r["n_critique"], -r["n_total"]))
    return resume


def compute_pilotage(projects, veille, now_dt):
    """Agrège les signaux du poste de pilotage : runs à solder, cadences périmées,
    décisions en attente d'arbitrage humain."""
    existants = [p for p in projects if p["existe"]]
    en_alerte = [p for p in existants if p["alerte"]]
    ecarts = compte_ecarts(existants)

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
        # Péremption de l'audit qualitatif : le temps ET le code (finding
        # VScode5:audit-technique-perime). Le message porte les DEUX chiffres —
        # « périmé depuis 34 j » seul ne dit pas s'il y a de quoi le repayer.
        audit_vieux, audit_j, audit_l = audit_perime(p, now_dt)
        row["audit"] = (audit_j, audit_l, audit_vieux)
        if audit_vieux:
            retards.append(
                f"{p['nom']} : audit technique à relancer ({audit_j} j, "
                f"{audit_l} lignes changées depuis)"
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
        "ecarts": ecarts,
        "nb_ecarts": sum(r["n_total"] for r in ecarts),
        "nb_pratiques_ecart": sum(r["n_pratiques"] for r in ecarts),
        "nb_findings": sum(r["n_findings"] for r in ecarts),
    }


# --- Tendances (incrément 5 de docs/reflexions/ameliorations-supervision.md,
# 2026-07-23 — resté sans suite 7 jours, reversé en finding wiki:tendances-wiki du
# diagnostic 2026-07-30) : un snapshot daté par scan + les deltas vs le précédent,
# pour que le bandeau dise « mieux ou moins bien qu'hier », pas seulement l'état
# instantané. Lecture/écriture strictement locales (0 token), un fichier JSONL
# versionné comme runs.jsonl/usage.jsonl.

def charger_dernier_snapshot():
    """Dernière ligne de HISTORY_PATH, ou None (absent / vide / corrompu — jamais
    fatal, les tendances sont un confort d'affichage, pas une donnée critique)."""
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            derniere = None
            for ligne in fh:
                ligne = ligne.strip()
                if ligne:
                    derniere = ligne
        return json.loads(derniere) if derniere else None
    except (OSError, ValueError):
        return None


def snapshot_actuel(projects, pil, now_iso):
    existants = [p for p in projects if p["existe"]]
    return {
        "ts": now_iso,
        "nb_projets": pil["nb_projets"],
        "nb_en_alerte": len(pil["en_alerte"]),
        "nb_pratiques_ecart": pil["nb_pratiques_ecart"],
        "nb_findings": pil["nb_findings"],
        "nb_runs_a_solder": len(pil["runs_a_solder"]),
        "nb_retards": len(pil["retards"]),
        "alertes": {p["nom"]: p["alerte"] for p in existants},
    }


def ecrire_snapshot(snap):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snap, ensure_ascii=False) + "\n")


def calcule_tendances(actuel, precedent):
    """Deltas des compteurs du bandeau + transitions d'alerte par projet (l'exemple
    même de la réflexion d'origine : « alerte VSCode2 critique->majeur »). None si
    pas de précédent (premier scan de l'historique)."""
    if precedent is None:
        return None
    deltas = {
        cle: actuel[cle] - precedent.get(cle, actuel[cle])
        for cle in ("nb_en_alerte", "nb_pratiques_ecart", "nb_findings",
                    "nb_runs_a_solder", "nb_retards")
    }
    transitions = []
    alertes_avant = precedent.get("alertes", {})
    for nom, apres in actuel["alertes"].items():
        avant = alertes_avant.get(nom)
        if avant != apres:
            transitions.append((nom, avant, apres))
    return {"depuis": precedent.get("ts"), "deltas": deltas, "transitions": transitions}


def rendu_delta(n):
    """▲/▼ + valeur, vide si nul — jamais de flèche pour "rien n'a changé"."""
    if not n:
        return ""
    return (f' <span class="delta-hausse">▲{n}</span>' if n > 0
            else f' <span class="delta-baisse">▼{-n}</span>')


# --- Chiffres mesurés de CLAUDE.md ----------------------------------------------
# Finding `VScode5:CLAUDE.md`, arbitré le 2026-09-01 (« traite tous les points de la
# page pilotage »). Les tailles des fichiers générés et les taux de reprise par
# playbook étaient écrits À LA MAIN dans CLAUDE.md, qui prêche pourtant R6. Mesuré :
# ils dérivaient de +9 à +36 % en UN jour, et l'écart de fiabilité entre playbooks qui
# servait à justifier R6 avait purement disparu sans que personne le relise. Un chiffre
# recopié vieillit en silence ; un chiffre régénéré ne peut pas être plus vieux que le
# dernier scan — et le scan tourne à chaque session, à 0 token.
CLAUDEMD_PATH = os.path.join(ROOT, "CLAUDE.md")
HINTS_PATH = os.path.join(ROOT, ".claude", "orchestration", "routing-hints.json")

# Les cinq fichiers générés que CLAUDE.md interdit d'ouvrir en entier. La liste est
# ici et NON dans CLAUDE.md : c'est elle la source, la page n'en est que le rendu.
VOLUMINEUX = [
    "docs/wiki.html",
    ".claude/orchestration/runs.jsonl",
    ".claude/orchestration/routing-hints.json",
    ".claude/supervision/arbitrages.json",
    "docs/wiki/technical/agents-supervision.md",
]


def bloc_volumineux():
    """Les fichiers volumineux, du plus gros au plus petit, avec leur taille réelle.

    Tri par taille et non par ordre d'écriture : c'est le plus gros qui coûte le plus
    cher à ouvrir, donc celui qu'on doit lire en premier dans la consigne."""
    tailles = []
    for rel in VOLUMINEUX:
        try:
            tailles.append((os.path.getsize(os.path.join(ROOT, rel.replace("/", os.sep))), rel))
        except OSError:
            continue          # fichier pas encore généré : on ne l'invente pas
    tailles.sort(reverse=True)
    if not tailles:
        return "  (aucun fichier généré mesurable)"
    return "\n".join(
        f"  `{rel}` ({round(taille / 1024)} Ko)"
        + ("," if i < len(tailles) - 1 else ".")
        for i, (taille, rel) in enumerate(tailles))


def bloc_reprises():
    """Reprises par playbook, lues dans routing-hints.json (déjà agrégé par le scan)."""
    stats = (read_json(HINTS_PATH) or {}).get("playbooks") or {}
    lignes = []
    for nom, s in sorted(stats.items(), key=lambda kv: -(kv[1].get("n") or 0)):
        n, rep = s.get("n") or 0, s.get("reprises") or 0
        if not n:
            continue
        lignes.append(f"  - `{nom}` : {rep} reprise(s) sur {n} run(s) — "
                      f"{rep / n:.2f} par run")
    return "\n".join(lignes) or "  - (aucun run journalisé)"


def regenerer_chiffres_claudemd():
    """Réécrit les blocs `CHIFFRES-MESURES` de CLAUDE.md. Idempotent.

    Écriture en `newline=""` : CLAUDE.md est en LF, et le mode texte par défaut de
    Windows le repasserait en CRLF — soit un diff de 132 lignes à chaque scan pour
    deux chiffres changés, exactement le churn que R2 interdit.
    """
    texte = read_text(CLAUDEMD_PATH)
    if not texte:
        return False
    avant = texte
    for cle, bloc in (("VOLUMINEUX", bloc_volumineux()), ("REPRISES", bloc_reprises())):
        debut, fin = f"<!-- CHIFFRES-MESURES:{cle}:START", f"<!-- CHIFFRES-MESURES:{cle}:END -->"
        i, j = texte.find(debut), texte.find(fin)
        if i == -1 or j == -1 or j < i:
            continue          # marqueur retiré à la main : on ne réinvente pas la place
        ouverture = texte.find("-->", i)
        if ouverture == -1 or ouverture > j:
            continue
        texte = texte[:ouverture + 3] + "\n" + bloc + "\n  " + texte[j:]
    if texte == avant:
        return False
    tmp = CLAUDEMD_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(texte)
    os.replace(tmp, CLAUDEMD_PATH)
    return True


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
        f"**{pil['nb_pratiques_ecart']} pratique(s) en écart** · "
        f"**{pil['nb_findings']} finding(s) ouvert(s)** · "
        f"**{len(pil['runs_a_solder'])} run(s) à solder** · "
        f"**{len(pil['retards'])} retard(s) de cadence**",
        "",
    ]
    tend = pil.get("tendances")
    if tend:
        def fleche(n):
            return f" (+{n})" if n > 0 else f" ({n})" if n < 0 else ""
        lines += [
            f"_Depuis le scan précédent ({tend['depuis']}) : "
            f"pratiques en écart{fleche(tend['deltas']['nb_pratiques_ecart'])}, "
            f"findings{fleche(tend['deltas']['nb_findings'])}, "
            f"runs à solder{fleche(tend['deltas']['nb_runs_a_solder'])}, "
            f"retards{fleche(tend['deltas']['nb_retards'])}"
            + ("." if not tend["transitions"] else
               " — " + ", ".join(f"{n} {a or 'sain'} → {ap or 'sain'}"
                                  for n, a, ap in tend["transitions"]) + ".")
            + "_",
            "",
        ]
    if pil["ecarts"]:
        lines.append("**À arbitrer (onglet Actions correctives)** :")
        for r in pil["ecarts"]:
            pastille = "🔴" if r["n_critique"] else "🟠"
            lines.append(f"- {pastille} {r['projet']} : "
                         f"{libelle_ecarts(r['n_pratiques'], r['n_findings'])}")
        lines.append("")
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
        # LE FILTRAGE CESSE D'ÊTRE SILENCIEUX (arbitrage du 2026-09-02, « les deux »).
        # Un constat écarté par un arbitrage antérieur n'est pas une alerte, mais son
        # effacement complet est ce qui a rendu 3 findings invisibles — dont un p5. On
        # le montre replié : présent pour qui vérifie, absent du décompte d'alerte.
        if p.get("findings_masques"):
            lines.append(
                f"**Écartés par un arbitrage** ({len(p['findings_masques'])}) — "
                "montrés plutôt que supprimés : ils ne comptent pas dans le niveau "
                "d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :")
            for f in sorted(p["findings_masques"], key=lambda x: -x["priorite"]):
                lines.append(
                    f"- ~~p{f['priorite']} `{f['categorie']}` [{f['cible']}]~~ — {f['titre']}"
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
    for c in craft_effectives(existants):
        lines.append(
            f"| {PASTILLE[c['statut']]} {c['nom']} | {c['principe']} | "
            f"{c['flotte']} | {c['mesure']} |")
    lines += [
        "",
        "_Source : référentiel § 1 (DORA) & § 2 (pyramide de tests) + dimensions du scan._",
        "",
    ]
    mat = matrice_divergence_pptx_deck(existants)
    lines += [
        "### Divergence des copies de pptx_deck.py",
        "",
        "| Copie | Lignes | Fonctions | Propres à cette copie |",
        "| --- | --- | --- | --- |",
    ]
    for c in mat["copies"]:
        if c["fonctions"] is None:
            lines.append(f"| {c['projet']} `{c['rel']}` | — | — | absente ou non parsable |")
        else:
            p_list = mat["propres"].get(c["projet"], [])
            detail = ", ".join(f"`{f}`" for f in p_list[:8]) + ("…" if len(p_list) > 8 else "")
            lines.append(f"| {c['projet']} `{c['rel']}` | {c['lignes']} | "
                         f"{len(c['fonctions'])} | {len(p_list)} {detail} |")
    div = mat["divergentes"]
    lines += [
        "",
        f"_{len(mat['communes'])} fonction(s) communes, dont {len(div)} à signature "
        "divergente" + (" : " + ", ".join(f"`{d['fonction']}`" for d in div[:10])
                        + ("…" if len(div) > 10 else "") if div else "") + "._",
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
    ]
    # Détail intégral des synthèses d'audit trop longues pour title= (DETAIL_LIMITE,
    # arbitrage 2026-09-02) : la page HTML ne pose un lien « détail complet → » que
    # vers CE bloc, ancre par ancre (ancre_synthese) — rien n'est tronqué sans recours.
    longues = details_syntheses_longues(existants)
    if longues:
        lines += [
            "### Détail des synthèses d'audit",
            "",
            "_Synthèses trop longues pour l'infobulle de la page HTML — texte intégral, "
            "un lien « détail complet → » y renvoie depuis les onglets Pratiques et "
            "Arbitrer._",
            "",
        ]
        for projet, key, lib, syn in longues:
            lines += [
                f'<a id="{ancre_synthese(projet, key)}"></a>',
                f"**{projet} — {lib}** : {syn}",
                "",
            ]
    lines += [
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
  /* Séries catégorielles des graphiques (slots 1-3 de la palette de référence
     dataviz). Distinctes des couleurs de statut, qui restent réservées au sens
     bon/moyen/absent — une série ne doit jamais emprunter le vert d'un « ok ». */
  --serie-1: #2a78d6; --serie-2: #eb6834; --serie-3: #1baf7a;
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
/* Une tuile à 0 est neutre ; une tuile > 0 appelle une décision — le style seul
   doit le montrer avant même de lire le chiffre (revue UX 2026-07-29, P1/P1bis). */
.pilotage .chiffre.alerte { background: rgba(255,196,105,.22);
                            border-color: rgba(255,196,105,.55); }
.pilotage .chiffre.alerte b { color: #ffd88a; }
/* Tendances (incrément 5, finding wiki:tendances-wiki 2026-07-30) : la flèche
   compte plus que le chiffre — vert = ça baisse (mieux), rouge = ça monte. */
.pilotage .chiffre .delta-hausse { color: #ffb4b4; font-weight: 700; font-size: .82rem; }
.pilotage .chiffre .delta-baisse { color: #86efac; font-weight: 700; font-size: .82rem; }
.pilotage .tendance-transitions { font-size: .8rem; opacity: .85; margin: -.3rem 0 .8rem; }
.pilotage b { font-weight: 600; }
.pilotage li.ecart { list-style: none; }
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
/* Un résumé tronqué et son lien de détail ne doivent PAS se confondre avec le
   texte muet qui les entoure (constat designer : même police, même graisse,
   même couleur qu'un libellé de 24 caractères — DETAIL_LIMITE, arbitrage
   2026-09-02). Couleur d'accent + gras : visible d'un coup d'œil, pas seulement
   au survol d'un title=. */
a.lien-detail { color: var(--accent); font-weight: 600; text-decoration: none; }
a.lien-detail:hover, a.lien-detail:focus { text-decoration: underline; }

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
/* Cartes qu'on LIT en continu (glossaire du Tutoriel) : .action-carte p est
   calibré pour de courtes légendes de bouton, pas pour du texte suivi
   (finding wiki:finitions-lisibilite). */
.carte-lecture p { font-size: .88rem; line-height: 1.45; color: var(--ink); }
.carte-lecture p.muted { font-size: .8rem; color: var(--ink-soft); }
/* Cible de clic ≥ 32px de haut : les boutons faisaient 20-24px. */
.action-carte button, a.btn-pdf { display: inline-block; border: none; cursor: pointer;
  background: var(--brand-2); color: var(--brand-ink); padding: .5rem .85rem;
  border-radius: 6px; font-size: .76rem; font-weight: 600; text-decoration: none; }
/* Une date ne se coupe jamais en deux lignes ("2026-/07-23"). */
td.date-audit { white-space: nowrap; }
/* Métadonnée de fichier : sans séparateur, "…agents-supervision.md" et
   "généré : …" se lisaient collés comme une extension de fichier. */
.file-meta { display: flex; flex-wrap: wrap; gap: .25rem .75rem;
  font-size: .78rem; color: var(--ink-soft); }
.file-meta span:first-child { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.file-meta span + span::before { content: "· "; }
.action-carte button:hover, a.btn-pdf:hover { background: var(--brand); }
.action-carte button.llm { background: #7c3aed; }
.action-carte button.llm:hover { background: #6d28d9; }
.action-carte button:disabled { opacity: .75; cursor: wait; }
.badge-llm { font-size: .66rem; background: #ede9fe; color: #6d28d9; padding: .12rem .5rem;
  border-radius: 999px; font-weight: 700; vertical-align: middle; }
.badge-0t { font-size: .66rem; background: #dcfce7; color: #15803d; padding: .12rem .5rem;
  border-radius: 999px; font-weight: 700; vertical-align: middle; }
/* Nature de la carte corrective : une pratique mesurée (pastille de l'onglet
   Pratiques) n'est pas un finding de diagnostic (constat qualitatif, sans
   pastille). Les confondre faisait annoncer « pratiques en écart » sur un
   projet 100 % vert. */
.badge-nature { font-size: .66rem; background: var(--surface-2, #f1f5f9); color: #475569;
  padding: .12rem .5rem; border-radius: 999px; font-weight: 700; vertical-align: middle;
  border: 1px solid var(--line, #cbd5e1); }
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
.rapport-carte.annule { border-left-color: #6b7280; }
.rapport-entete { display: flex; align-items: center; justify-content: space-between;
  gap: .6rem; flex-wrap: wrap; }
.rapport-titre { font-weight: 700; }
.rapport-heure { color: var(--ink-soft); font-size: .74rem; white-space: nowrap; }
.rapport-statut { font-size: .7rem; font-weight: 700; padding: .12rem .55rem;
  border-radius: 999px; white-space: nowrap; }
.rapport-statut.encours { background: #dbeafe; color: #1d4ed8; }
.rapport-statut.ok { background: #dcfce7; color: #15803d; }
.rapport-statut.echec { background: #fee2e2; color: #b91c1c; }
.rapport-statut.annule { background: #f3f4f6; color: #4b5563; }
.rapport-entete button.annuler { margin-left: auto; border: 1px solid #dc2626;
  background: #fff; color: #dc2626; cursor: pointer; padding: .15rem .55rem;
  border-radius: 6px; font-size: .72rem; font-weight: 600; }
.rapport-entete button.annuler:hover { background: #fee2e2; }
.rapport-entete button.annuler:disabled { opacity: .5; cursor: default; }
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
.decision-arbitrage button { border: none; cursor: pointer; padding: .45rem .85rem;
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

/* --- Onglet Dispositif : la boucle, les 2 agents, les règles --------------- */
/* Tout est exprimé en variables CSS existantes : le thème sombre suit sans règle
   dédiée (la media query en fin de feuille redéfinit les variables, pas les
   composants). */
.flux { display: flex; flex-wrap: wrap; align-items: stretch; gap: .3rem;
  margin: .7rem 0 1.5rem; }
.flux-etape { flex: 1 1 9rem; min-width: 8.5rem; background: var(--surface);
  border: 1px solid var(--line); border-radius: 9px; padding: .55rem .7rem; }
.flux-etape.agent { border: 2px solid var(--brand); background: var(--surface-2); }
.flux-etape .qui { font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
  color: var(--ink-soft); font-weight: 700; }
.flux-etape .quoi { font-weight: 700; font-size: .87rem; margin: .1rem 0 .25rem;
  word-break: break-word; }
.flux-etape .ou { font-size: .72rem; color: var(--ink-soft); line-height: 1.35;
  word-break: break-word; }
/* Le chemin d'artefact est long et monospace : `break-all` remplit les lignes au
   lieu de laisser une coupe en plein mot au milieu d'un blanc (« state.js / on »). */
.flux-etape .ou + .ou { margin-top: .25rem; font-size: .68rem; word-break: break-all;
  font-family: ui-monospace, Consolas, monospace; }
.flux-fleche { align-self: center; color: var(--brand); font-weight: 700; font-size: 1.1rem; }
.schema-duo { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr));
  gap: .9rem; margin-bottom: 1.2rem; }
.schema-agent { background: var(--surface); border: 1px solid var(--line);
  border-top: 4px solid var(--brand); border-radius: 10px; padding: .8rem 1rem;
  box-shadow: var(--shadow); }
.schema-agent h4 { margin: 0 0 .15rem; font-size: .98rem; }
.schema-agent .invoc { font-size: .76rem; color: var(--ink-soft); margin: 0 0 .3rem; }
.schema-agent dl { margin: 0; }
.schema-agent dt { font-size: .69rem; text-transform: uppercase; letter-spacing: .05em;
  color: var(--brand-2); font-weight: 700; margin-top: .6rem; }
.schema-agent dd { margin: .15rem 0 0; font-size: .82rem; line-height: 1.5; }
.schema-agent dd.interdit { color: var(--red); }
.regle-chip { display: inline-block; background: var(--surface-2);
  border: 1px solid var(--line-strong); border-radius: 999px; padding: .08rem .55rem;
  margin-right: .4rem; font-size: .73rem; font-weight: 700; color: var(--brand-2); }
.playbook-carte { border-left: 4px solid var(--accent); }

footer { margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--ink-soft); font-size: .8rem; }

/* --- Graphiques de l'onglet Tokens ------------------------------------------
   Marques fines, extrémité arrondie ancrée à la ligne de base, 2 px de fond entre
   deux segments empilés (un filet de surface, pas un trait : deux aplats collés se
   lisent comme un seul), valeur écrite au bout de chaque barre. Pas de grille : à
   huit barres, elle ajouterait du bruit sans aider à comparer. */
/* --- Salles utilisables : la carte porte la commande, pas un paragraphe ------ */
.salles-grille { display: grid; gap: .7rem; margin: .6rem 0 1rem;
                 grid-template-columns: repeat(auto-fill, minmax(285px, 1fr)); }
.salle-carte { border: 1px solid var(--line); border-radius: 10px; padding: .75rem .85rem;
               background: var(--surface-2); }
.salle-carte h4 { margin: 0 0 .3rem; font-size: .95rem; }
.salle-quand { margin: .1rem 0 .45rem; font-size: .84rem; color: var(--ink); font-style: italic; }
.onglet-sommaire { display: flex; flex-wrap: wrap; gap: .4rem; margin: .55rem 0 1.1rem; }
.onglet-sommaire a { font-size: .8rem; padding: .18rem .6rem; border: 1px solid var(--line);
  border-radius: 999px; text-decoration: none; }
.salle-cmd { margin: .35rem 0; }
.salle-sujet { display: block; margin-top: .25rem; font-size: .78rem; color: var(--muted); }
.salle-cmd code { display: block; padding: .4rem .5rem; border-radius: 6px;
                  background: var(--brand-ink); color: var(--brand);
                  font-size: .78rem; overflow-wrap: anywhere; }
.salle-carte .muted { margin: .3rem 0 0; font-size: .78rem; }
.salle-pourquoi { border-top: 1px dashed var(--line); padding-top: .35rem; margin-top: .45rem; }
.salle-voix { margin: .3rem 0 0; font-size: .78rem; line-height: 1.45; }
.salle-dest { margin: .45rem 0 0; font-size: .8rem; padding: .35rem .5rem;
              background: var(--neutral-bg); border-radius: 6px; }
.party-deroule { font-size: .84rem; line-height: 1.55; border: 1px solid var(--line);
                 border-left: 3px solid var(--brand-2); border-radius: 8px;
                 padding: .65rem .85rem; margin: .5rem 0 .9rem; background: var(--surface-2); }
.arbitrages-archive > summary { cursor: pointer; }

/* --- Schéma d'ensemble (SVG inline, suit le thème) --------------------------- */
.schema-ensemble { width: 100%; height: auto; max-width: 980px; margin: .6rem 0 1.4rem;
                   display: block; }
.schema-ensemble rect { fill: var(--surface-2); stroke: var(--line-strong); stroke-width: 1.5; }
.schema-ensemble .sch-t { font-size: 14px; font-weight: 700; fill: var(--ink);
                          text-anchor: middle; }
.schema-ensemble .sch-s { font-size: 11.5px; fill: var(--ink-soft); text-anchor: middle; }
.schema-ensemble .sch-f { font-size: 11px; fill: var(--ink-soft); text-anchor: middle;
                          font-style: italic; }
.schema-ensemble .sch-l { stroke: var(--line-strong); stroke-width: 1.5; fill: none; }
.schema-ensemble .sch-m { fill: var(--line-strong); }
.schema-ensemble .sch-humain rect { fill: var(--brand-ink); stroke: var(--brand-2); }
.schema-ensemble .sch-orch rect { fill: var(--brand-ink); stroke: var(--brand); stroke-width: 2; }
.schema-ensemble .sch-salle rect { stroke: var(--serie-1); }
.schema-ensemble .sch-agent rect { stroke: var(--serie-2); }
.schema-ensemble .sch-sup rect { stroke: var(--serie-3); }

/* --- La reponse du jour : ce qu'on lit AVANT les chiffres -------------------- */
.reponse-jour { margin: 0 0 1rem; padding: .85rem 1rem; border-radius: 12px;
                background: var(--surface); border: 1px solid var(--line-strong);
                box-shadow: var(--shadow); }
.reponse-jour p { margin: .3rem 0; font-size: .95rem; line-height: 1.5; }
.rj-quoi { display: inline-block; min-width: 12.5rem; font-weight: 700;
           color: var(--ink-soft); font-size: .8rem; text-transform: uppercase;
           letter-spacing: .03em; }
.reponse-jour .rj-casse { border-left: 3px solid var(--red); padding-left: .6rem; }
.reponse-jour .rj-decision { border-left: 3px solid var(--amber); padding-left: .6rem; }
.reponse-jour .rj-bouge { border-left: 3px solid var(--line-strong); padding-left: .6rem;
                          color: var(--ink-soft); font-size: .88rem; }
.reponse-jour a { margin-left: .4rem; font-size: .85rem; }
.reponse-calme { border-left: 3px solid var(--green); }
@media (max-width: 720px) { .rj-quoi { min-width: 0; display: block; } }

.btn-party { background: transparent; color: var(--brand-2); border: 1px solid var(--line-strong);
             margin-left: .4rem; }
.btn-party:hover:not(:disabled) { background: var(--brand-ink); border-color: var(--brand-2); }

.viz-legende { display: flex; flex-wrap: wrap; gap: 1.1rem; margin: .4rem 0 .9rem; }
.viz-cle { display: inline-flex; align-items: center; gap: .4rem;
           font-size: .82rem; color: var(--ink-soft); }
.viz-pastille { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
.viz-barres { display: flex; flex-direction: column; gap: .3rem; margin: .2rem 0 1.2rem; }
.viz-ligne { display: grid; grid-template-columns: 3.2rem 1fr 6.5rem;
             align-items: center; gap: .6rem; }
.viz-ligne-large { grid-template-columns: 13rem 1fr 6.5rem; }
.viz-etiq { font-size: .8rem; color: var(--ink-soft); text-align: right;
            font-variant-numeric: tabular-nums; }
.viz-ligne-large .viz-etiq { text-align: left; overflow-wrap: anywhere; }
.viz-piste { display: flex; gap: 2px; height: 15px; align-items: stretch; }
.viz-seg:first-child { border-radius: 4px 0 0 4px; }
.viz-seg:last-child { border-radius: 0 4px 4px 0; }
.viz-seg:only-child { border-radius: 4px; }
.viz-seg { min-width: 2px; }
.viz-val { font-size: .8rem; color: var(--ink); text-align: right;
           font-variant-numeric: tabular-nums; }
@media (max-width: 640px) {
  .viz-ligne { grid-template-columns: 3rem 1fr; }
  .viz-val { grid-column: 2; text-align: left; font-size: .74rem; }
}

@media (prefers-color-scheme: dark) {
  :root {
    --ink: #e6ebf2; --ink-soft: #9aa6b8; --line: #26303f; --line-strong: #33404f;
    --bg: #0f151d; --surface: #161d27; --surface-2: #1b2430;
    --brand: #7fb0e6; --brand-2: #9cc4f0; --brand-ink: #cfe0f5;
    --accent: #6fa8dd;
    --green: #5cc98a; --green-bg: #143726; --amber: #e0b25a; --amber-bg: #3a2f16;
    --red: #f08a80; --red-bg: #3a1e1b; --neutral: #8b96a8; --neutral-bg: #212b38;
    /* Les mêmes huit teintes RE-PAS pour la surface sombre (#161d27), pas un
       basculement automatique : validées séparément dans ce mode. */
    --serie-1: #3987e5; --serie-2: #d95926; --serie-3: #199e70;
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

# Marqueurs du bloc « supervision des agents » de wiki.html : le CONTENU est
# injecté par .claude/supervision/scan_transcripts.py (hook SessionStart) ; ce
# générateur ne fait que poser les marqueurs — les perdre à la régénération
# rendait le bloc agents du HTML définitivement périmé (finding wiki-verite).
AGENTS_HTML_START = "<!-- TODO-AGENTS-HTML:START"
AGENTS_HTML_END = "<!-- TODO-AGENTS-HTML:END -->"


def replier_arbitrages(bloc):
    """Replie la section « Arbitrages enregistrés » du bloc agents dans un <details>.

    Mesuré le 2026-07-31 : cette liste pesait 90,4 Ko sur les 102 de l'onglet
    Pilotage — 88 % de l'onglet, un tiers du site — pour un contenu d'archive qu'on
    consulte à l'occasion d'un doute, pas à chaque visite. Le repli se fait ICI, au
    moment de l'émission : `scan_transcripts.py` est un fichier du canon propagé aux
    6 projets, y toucher pour un besoin d'affichage du hub casserait les cibles
    (leçon `feedback-sync-canon-rejouer-suites-cibles`). Idempotent — un bloc déjà
    replié ressort inchangé.
    """
    if "<details" in bloc.split("Arbitrages enregistrés")[0][-400:]:
        return bloc  # déjà replié (régénération sur une page déjà traitée)
    m = re.search(r"( *)<h3>Arbitrages enregistrés</h3>\n(.*?)(?=\n *<h3>|\Z)",
                  bloc, re.DOTALL)
    if not m:
        return bloc
    indent, corps = m.group(1), m.group(2)
    n = corps.count("<li>")
    remplacement = (
        f'{indent}<details class="det arbitrages-archive"><summary>'
        f"<b>Arbitrages enregistrés</b> — {n} décision(s), replié"
        f"<span class=\"muted\"> (l'archive des décisions humaines ; l'usage réel "
        f"reste mesuré ci-dessus)</span></summary>\n{corps}\n{indent}</details>")
    return bloc[:m.start()] + remplacement + bloc[m.end():]


def bloc_agents_html(ancien_html):
    """Bloc entre marqueurs TODO-AGENTS-HTML à émettre dans la page régénérée.

    Préserve le dernier bloc injecté par scan_transcripts.py s'il existe dans
    l'ancienne page (les données agents survivent à la régénération) ; sinon pose
    les marqueurs avec un contenu d'attente."""
    if ancien_html:
        m = re.search(re.escape(AGENTS_HTML_START) + r".*?" + re.escape(AGENTS_HTML_END),
                      ancien_html, re.DOTALL)
        if m:
            return replier_arbitrages(m.group(0))
    return (
        AGENTS_HTML_START + " — contenu injecté par .claude/supervision/scan_transcripts.py -->\n"
        '<p class="muted">Supervision des agents : bloc pas encore injecté — il se remplit '
        "au prochain démarrage de session (hook SessionStart) ou via "
        "<code>py .claude/supervision/scan_transcripts.py</code>.</p>\n"
        + AGENTS_HTML_END)


# Glossaire de l'onglet Tutoriel : (famille, [(terme, définition, exemple réel
# dans CE dispositif)]). Contenu curaté — chaque exemple pointe un objet qui
# existe vraiment dans la flotte, pas une généralité.
TUTORIEL_CONCEPTS = [
    ("Les acteurs", [
        ("Agent",
         "Instance LLM autonome dotée d'outils (lire, écrire, exécuter) et d'une mission. "
         "La session Claude Code que vous pilotez EST un agent : elle raisonne, choisit ses "
         "outils, agit, et rend compte.",
         "La « session principale » qui apparaît dans les plans des runs journalisés."),
        ("Sous-agent",
         "Agent lancé PAR un agent (outil Task/Agent), avec son propre contexte vierge et un "
         "brief : il travaille en isolation et rend un résultat unique. Idéal pour explorer "
         "sans polluer le contexte, ou relire un diff avec un regard neuf.",
         "« Explore » (recherche en lecture seule), « general-purpose » (tâches multi-étapes), "
         "l'étape revue-fraiche des playbooks (relecteur au contexte frais)."),
        ("Modèle (haiku / sonnet / opus)",
         "Le moteur LLM d'un agent, choisi par tâche : haiku = fan-out mécanique économe, "
         "sonnet = défaut dev, opus/fable = structurant (architecture, arbitrage, revue "
         "adversariale). La politique de modèle vit dans la skill agent-orchestrator.",
         "La revue fraîche d'un diff tourne en sonnet ; le diagnostic superviseur sur le "
         "modèle de la session."),
    ]),
    ("La connaissance embarquée", [
        ("Skill",
         "Paquet d'instructions versionné (SKILL.md + scripts éventuels) chargé À LA DEMANDE "
         "— par une commande /nom-de-skill ou automatiquement quand la tâche matche sa "
         "description. C'est la mémoire procédurale du projet : la façon éprouvée de faire "
         "une tâche récurrente.",
         ".claude/skills/ : agent-orchestrator, agent-supervisor, revue-increment, "
         "audit-technique, veille-agentic, pptx-deck…"),
        ("Rules (CLAUDE.md)",
         "Règles PERMANENTES injectées au début de chaque session du projet — contraintes et "
         "conventions que l'agent doit respecter sans qu'on les répète. Règle de flotte : "
         "≤ 150 lignes, sinon plus personne ne les lit (ni humain ni agent).",
         "Le CLAUDE.md du hub porte R1-R5 (lire l'état réel, commit scopé, adapter au canal, "
         "propose→arbitre→applique, vérité du journal)."),
        ("Hook",
         "Commande DÉTERMINISTE (0 token LLM) branchée sur le cycle de vie de la session : "
         "SessionStart, avant/après un outil (PreToolUse/PostToolUse), soumission du prompt. "
         "Le hook exécute du code, il ne « demande » pas au LLM — c'est ce qui le rend fiable "
         "pour les garde-fous et les cadences.",
         "Au SessionStart : scan_transcripts.py (usage réel des agents) et le rappel de "
         "veille ; en PreToolUse : warn_verif_before_commit (alerte si du code part sans "
         "vérification réelle)."),
        ("Mémoire d'agent",
         "Faits persistés ENTRE les sessions (préférences, leçons payées, frictions) — "
         "distincts des rules : la mémoire capitalise ce qui a été appris en travaillant, "
         "les rules imposent ce qui est décidé.",
         "« pytest : jonction morte dans %TEMP% » ou « re-vérifier git status juste avant de "
         "stager » — leçons réutilisées à chaque séance."),
        ("Skills BMAD",
         "Catalogue de 46 skills « méthode » (PRD, architecture, stories, revues…) installé "
         "sur les projets de la flotte. Elles ne dépendent plus d'une demande explicite : "
         "l'orchestrateur les ROUTE par besoin détecté, d'office pour les passes de lecture "
         "et de critique, annoncées-puis-validées dès qu'elles coûtent cher ou écrivent un "
         "fichier réel.",
         "bmad-code-review (d'office), bmad-prd et bmad-customize (proposé) — table de "
         "routage dans agent-orchestrator/SKILL.md, verrouillée par test_orchestration_bmad.py."),
    ]),
    ("Le processus outillé", [
        ("Playbook",
         "Workflow récurrent CONTRACTUALISÉ : une suite d'étapes avec pour chacune un agent, "
         "un mode d'exécution, un modèle et un CONTRAT de sortie vérifiable — plus des "
         "checkpoints avant les actions difficilement réversibles. L'orchestrateur instancie "
         "un playbook plutôt que de composer un plan à vide.",
         ".claude/orchestration/playbooks/ : evolution-flotte (modifier un autre dépôt), "
         "dev-verifie, export-ppt-verifie, revue-design-parallele."),
        ("Orchestrateur",
         "La skill qui QUALIFIE une demande (exécution directe ou orchestration), compose le "
         "plan (étapes, modes cascade/parallèle/arrière-plan, modèles), l'exécute en "
         "vérifiant chaque contrat de sortie, et JOURNALISE le run. C'est le « comment » du "
         "dispositif.",
         "Skill agent-orchestrator + catalogue.md + routing-hints.json (agents éprouvés / "
         "jamais utilisés / prudence)."),
        ("Superviseur (étages 1 et 2)",
         "Le « est-ce que ça marche » du dispositif, en deux étages : étage 1 déterministe "
         "(scan des transcripts, 0 token — compteurs d'usage réel, hints de routage) ; "
         "étage 2 LLM (skill agent-supervisor — diagnostic qualitatif : chaque constat porte "
         "une PREUVE et une proposition concrète, jamais auto-appliquée).",
         "scan_transcripts.py (hook SessionStart) + diagnostic.json (findings arbitrables "
         "rendus dans l'onglet Actions correctives)."),
        ("Finding",
         "Constat priorisé du diagnostic : catégorie (ko-répété, vérification manquante, "
         "pratique-test…), CIBLE exacte, preuve objective, recommandation et proposition "
         "arbitrable d'un coup d'œil. Un constat sans preuve ne se journalise pas.",
         "« Le contrat du playbook evolution-flotte est incomplet à ses deux extrémités » "
         "(diagnostic du 2026-07-29)."),
        ("Arbitrage",
         "La décision HUMAINE qui clôt un finding — acceptée ou refusée, toujours tracée "
         "(arbitrages.json) à la cible exacte. C'est la boucle de gouvernance du dispositif : "
         "le superviseur PROPOSE, l'humain ARBITRE, l'orchestrateur APPLIQUE la version "
         "validée. Jamais d'auto-application.",
         "Les boutons Valider/Invalider de l'onglet Actions correctives écrivent cette "
         "décision ; le scan cesse alors d'afficher le finding."),
        ("Run (journal)",
         "Une ligne par orchestration dans runs.jsonl : demande, plan, résultat DISCRIMINANT "
         "(succès / en-attente-validation / partiel / échec), reprises, notes. Journalisé dès "
         "la composition du plan (un run interrompu laisse une trace), soldé via log_run.py "
         "--solde quand l'utilisateur valide — jamais par édition manuelle.",
         "Les « runs à solder » du bandeau de l'onglet Pilotage sortent de ce journal."),
    ]),
    ("La table ronde (party mode)", [
        ("Party (table ronde)",
         "Réunion de personas qui DÉLIBÈRENT sur une question, chacun défendant son angle "
         "— l'inverse d'un agent seul qui se convainc tout seul. Elle produit une décision "
         "et une partition du travail ; elle n'écrit jamais de code. L'exécution qui suit "
         "est un fan-out orchestré normal, avec ses vérifications et son journal.",
         "5 salles maison + 2 livrées, définies dans _bmad/custom/bmad-party-mode.toml."),
        ("Rôle (persona)",
         "Une voix de la table ronde : un code unique, un nom, et surtout un « persona » — "
         "ce qu'il défend et ce qu'il refuse de laisser passer. Un rôle n'est utile que "
         "s'il peut CONTREDIRE les autres : trois avis identiques ne valent pas mieux qu'un.",
         "Garde-fou exige qu'un test ait été vu rouge ; Aiguilleur refuse un secret dans un "
         "fichier versionné ; Contrôleur refuse de dire « conforme » sans avoir regardé."),
        ("Salle (groupe)",
         "Le sous-ensemble réellement convoqué, 5 voix au plus — le vivier entier ne se "
         "réunit jamais (coût, et dilution du débat). Une salle peut garder une MÉMOIRE "
         "entre séances, ou être « open-cast » et générer ses voix à la volée.",
         "conseil-flotte (mémoire), atelier-dev (mémoire), atelier-deck, mise-en-service, "
         "accueil-projet (open-cast)."),
        ("Relais de projet",
         "Un rôle par dépôt supervisé, qui parle AU NOM de sa cible et porte ses contraintes "
         "réelles — c'est la règle R3 incarnée : ne jamais plaquer le canal d'un projet sur "
         "un autre. Il s'invite dans une salle selon le projet discuté.",
         "Relais VSCode défend COMOP contre python-pptx ; Relais VSCode4 refuse qu'on "
         "réclame des tests applicatifs à un projet pré-code."),
        ("Mode d'exécution",
         "Qui parle vraiment : `session` = un seul modèle joue toutes les voix (aucun "
         "parallélisme) ; `auto` = spawn ciblé quand un tour exige une pensée indépendante ; "
         "`subagent` = un vrai sous-agent par voix et par tour. Le mode est GLOBAL, il se "
         "choisit à l'ouverture (--mode), pas par salle.",
         "Défaut `session` ; ouvrir en --mode auto, et --mode subagent quand le désaccord "
         "est réel et mérite de vraies voix indépendantes."),
    ]),
    ("Le dispositif de flotte", [
        ("Canon + sync",
         "Source UNIQUE des scripts partagés par les 6 projets (.claude/dispositif/canon/), "
         "propagée par sync_dispositif.py — remplace les copies maintenues à la main qui "
         "divergeaient. Toute correction se fait dans le canon puis se synchronise ; une "
         "copie modifiée localement est écrasée au passage suivant.",
         "scan_transcripts.py et log_run.py existent en 6 copies, toutes générées depuis le "
         "canon (en-tête « GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT »)."),
        ("Scan + wiki",
         "scan_projets.py MESURE la flotte (pratiques, tests, cadrage, cadences, usage des "
         "agents) et régénère ce site — données générées, jamais éditées à la main. Le wiki "
         "éclaire mais ne remplace pas la lecture directe d'une cible avant d'agir (règle "
         "R1).",
         "docs/wiki.html (ce site), projets-supervision.md, routing-hints.json, state.json."),
        ("Audit technique",
         "Étage QUALITATIF facturé : lire le code réel d'un projet sur 4 dimensions "
         "(robustesse, performance, risque technique, sécurité) — là où le scan déterministe "
         "ne mesure que la présence de dispositifs. Lancé sur demande, résultat versionné.",
         ".claude/audits/<projet>.json, rendu dans l'onglet Pratiques & risques."),
        ("Veille agentic",
         "Skill cadencée (3 jours, rappelée par hook) qui surveille l'écosystème agentic — "
         "frameworks, pratiques recommandées des providers — et en dérive des critères "
         "d'analyse et des actions correctives arbitrables sur la flotte.",
         ".claude/veille/veille.json, rendu dans l'onglet Veille."),
    ]),
]


# --- Onglet Dispositif : schéma de fonctionnement des 2 agents ----------------
# Demande utilisateur 2026-07-30. Le schéma est DÉRIVÉ de l'état réel du dépôt
# (fichiers de .claude/agents/, playbooks présents, règles lues dans CLAUDE.md) et
# non recopié à la main : un schéma recopié divergerait au premier agent ajouté, et
# un schéma faux est pire qu'aucun schéma. Ce qui reste déclaré ici — qui lance qui —
# est verrouillé par tests/test_wiki_dispositif.py.
DISPOSITIF_LANCE = {
    "agent-orchestrator": ["bmad-revue", "bmad-doc", "bmad-recherche", "bmad-cadrage",
                           "bmad-livraison", "veille-agentic", "agent-supervisor"],
    "agent-supervisor": ["bmad-revue", "veille-agentic"],
}

# La boucle du dispositif : (verbe, acteur, ce qu'il fait, artefact, est-ce un des 2 agents)
DISPOSITIF_BOUCLE = [
    ("mesure", "hooks — étage 1", "déterministe, 0 token, à chaque session",
     ".claude/supervision/state.json", False),
    ("qualifie", "agent-supervisor", "5 findings max, chacun avec sa preuve",
     ".claude/supervision/diagnostic.json", True),
    ("arbitre", "l'humain", "accepte ou refuse — R4, jamais d'auto-application",
     ".claude/supervision/arbitrages.json", False),
    ("applique", "agent-orchestrator", "playbook + vérifications obligatoires",
     "le code de la cible", True),
    ("trace", "journal + wiki", "run soldé, page régénérée",
     ".claude/orchestration/runs.jsonl", False),
]


def lire_frontmatter_agent(chemin):
    """Les clés utiles du frontmatter d'un `.claude/agents/*.md` : name, description,
    model, tools. Parseur volontairement étroit — ces fichiers sont écrits à la main
    dans un format fixe, un vrai parseur YAML serait une dépendance pour quatre clés.
    Fichier illisible ou sans frontmatter → dict vide (fail-open : le schéma se rend
    sans l'agent plutôt que de faire planter la génération du wiki)."""
    txt = read_text(chemin) or ""
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    if not m:
        return {}
    out = {}
    for ligne in m.group(1).splitlines():
        cle, sep, val = ligne.partition(":")
        if not sep or cle != cle.strip() or cle.strip() not in (
                "name", "description", "model", "tools"):
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[cle.strip()] = val
    return out


def lister_sous_agents(dossier=None):
    """Les sous-agents réellement installés dans `.claude/agents/`, triés par nom.

    `dossier` sert aux tests : le cas « frontmatter sans `model:` → hérité » n'était
    vérifiable que tant qu'un agent RÉEL était dans ce cas. Il n'y en a plus depuis la
    mise en sommeil du 2026-09-01, et le test se serait tu — une propriété du code ne
    doit pas dépendre de quel fichier existe ce jour-là.
    """
    d = dossier or os.path.join(ROOT, ".claude", "agents")
    agents = []
    for nom in list_md(d):
        fm = lire_frontmatter_agent(os.path.join(d, nom + ".md"))
        if not fm:
            continue
        agents.append({
            "fichier": nom,
            "nom": fm.get("name") or nom,
            "description": fm.get("description", ""),
            "modele": fm.get("model") or "hérité",
            "outils": [o.strip() for o in (fm.get("tools") or "").split(",") if o.strip()],
        })
    return agents


def regles_absolues():
    """Les règles R1..Rn du hub, lues dans CLAUDE.md — la source, pas une recopie.
    Format attendu : `- **R1 — Titre de la règle.** explication…`"""
    txt = read_text(os.path.join(ROOT, "CLAUDE.md")) or ""
    return re.findall(r"- \*\*(R\d+) — (.+?)\*\*", txt)


DATE_ROUTAGE_BMAD = "2026-07-30"        # mise en service de la table de routage
DATE_REVUE_ROUTAGE_BMAD = "2026-08-06"  # échéance de revue de son emprunt réel


def emprunt_routage_bmad():
    """Mesure l'EMPRUNT du routage BMAD : combien de skills `bmad-*` ont réellement été
    invoquées, et combien de sous-agents porteurs ont réellement été lancés.

    Finding `orchestrateur:emprunt-routage-bmad-non-mesure` (diagnostic 2026-07-30) :
    l'ancienne règle « uniquement sur demande explicite » a produit 0 invocation sur
    113 sessions SANS qu'aucun instrument ne le signale — la table qui l'a remplacée
    pouvait rester lettre morte exactement de la même façon. Les tests de
    `tests/test_orchestration_bmad.py` verrouillent la COHÉRENCE de la table ; cette
    fonction mesure son USAGE. 0 token : tout vient de `state.json` (étage 1)."""
    state = read_json(os.path.join(ROOT, ".claude", "supervision", "state.json")) or {}
    usage_skills = state.get("skills") or {}
    usage_agents = state.get("subagents") or {}

    def n(entree):
        return entree.get("n", 0) if isinstance(entree, dict) else 0

    installees = [d for d in list_dirs(os.path.join(ROOT, ".claude", "skills"))
                  if d.startswith("bmad-")]
    empruntees = sorted(s for s in installees if n(usage_skills.get(s)))
    porteurs = [a["nom"] for a in lister_sous_agents()]
    lances = sorted(p for p in porteurs if n(usage_agents.get(p)))
    return {
        "installees": len(installees), "empruntees": empruntees,
        "porteurs": len(porteurs), "lances": lances,
    }


def pilotage_duo(projects):
    """Le duo orchestrateur/superviseur, projet par projet — présence, usage réel,
    fraîcheur du diagnostic. Le hub (VScode5) est le projet TRANSVERSE : il pilote le
    dispositif des autres. La liste vient de `projets.json`, donc tout projet ajouté
    à la flotte entre ici automatiquement — rien n'est recopié à la main."""
    lignes = []
    for p in projects:
        if not p.get("existe"):
            continue
        usage = dict(p.get("skills_utilises") or [])
        lignes.append({
            "nom": p["nom"],
            "transverse": os.path.normcase(os.path.abspath(p["chemin"]))
                          == os.path.normcase(ROOT),
            "orchestrateur": "agent-orchestrator" in (p.get("skills") or []),
            "superviseur": "agent-supervisor" in (p.get("skills") or []),
            "n_orchestrateur": usage.get("agent-orchestrator", 0),
            "n_superviseur": usage.get("agent-supervisor", 0),
            "sous_agents": len(p.get("agents") or []),
            "playbooks": len(p.get("playbooks") or []),
            "diag_date": (p.get("diag_date") or "")[:10],
        })
    return lignes


def render_dispositif_html(projects=()):
    """Onglet Dispositif : le schéma de fonctionnement de l'orchestrateur et du
    superviseur — leurs déclencheurs, ce que chacun lance (sous-agents, skills), ce
    qu'il écrit, ce que les règles lui interdisent, et l'état du duo sur la flotte."""
    ee = html.escape
    agents = lister_sous_agents()
    presents = {a["nom"] for a in agents}
    playbooks = list_md(os.path.join(ROOT, ".claude", "orchestration", "playbooks"),
                        exclude=("FORMAT.md",))
    regles = regles_absolues()
    parts = ["<h2>Dispositif — comment les deux agents fonctionnent</h2>"]
    parts.append(
        '<p class="legende">Deux agents portent le dispositif : le <strong>superviseur'
        "</strong> qualifie ce que les hooks ont mesuré, l'<strong>orchestrateur</strong> "
        "applique ce que l'humain a arbitré. Aucun des deux ne franchit la frontière de "
        "l'autre — c'est la boucle <em>propose → arbitre → applique</em>, et c'est ce qui "
        "empêche un diagnostic de se corriger tout seul. Ce schéma est <strong>dérivé de "
        "l'état réel du dépôt</strong> (fichiers de <code>.claude/agents/</code>, playbooks "
        "présents, règles lues dans <code>CLAUDE.md</code>) : il ne peut pas décrire un "
        "agent qui n'existe plus.</p>")

    # --- Vue d'ensemble (demande utilisateur 2026-07-31) ---------------------
    parts.append("<h3>Comment tout cela fonctionne ensemble</h3>")
    parts.append(
        '<p class="legende">De la demande à la trace, en une vue. Les nombres sont '
        "<strong>dérivés du dépôt</strong> — agents de <code>.claude/agents/</code>, "
        "salles et rôles des TOML de party, playbooks du dossier, skills du disque : "
        "le schéma vieillit avec le dispositif au lieu de le décrire tel qu'il était. "
        "Trois voies partent de l'orchestrateur, et une seule d'entre elles modifie des "
        "fichiers — <em>les salles délibèrent, le superviseur propose, seuls les "
        "sous-agents agissent</em>.</p>")
    parts.append(render_ensemble_svg())
    parts.append(render_salles_utilisables_html())

    # --- La boucle -----------------------------------------------------------
    parts.append("<h3>La boucle</h3>")
    parts.append('<div class="flux">')
    for i, (verbe, acteur, quoi, artefact, est_agent) in enumerate(DISPOSITIF_BOUCLE):
        if i:
            parts.append('<div class="flux-fleche" aria-hidden="true">→</div>')
        parts.append(
            f'<div class="flux-etape{" agent" if est_agent else ""}">'
            f'<div class="qui">{ee(verbe)}</div>'
            f'<div class="quoi">{ee(acteur)}</div>'
            f'<div class="ou">{ee(quoi)}</div>'
            f'<div class="ou">{ee(artefact)}</div></div>')
    parts.append("</div>")

    # --- Les deux agents côte à côte ----------------------------------------
    parts.append("<h3>Les deux agents</h3>")
    parts.append('<div class="schema-duo">')
    fiches = [
        {
            "nom": "agent-orchestrator",
            "titre": "🎯 agent-orchestrator — applique",
            "invoc": "3 formes : la skill (inline), le sous-agent (délégation d'une "
                     "orchestration entière), la commande /orchestre",
            "declencheurs": "≥ 2 étapes dépendantes · ≥ 2 agents/skills · une "
                            "vérification obligatoire en jeu · « applique le finding X » · "
                            "« adopte <trouvaille> » · la grille du hook UserPromptSubmit",
            "lit": ".claude/orchestration/catalogue.md · routing-hints.json (hints frais "
                   "du superviseur) · les playbooks · diagnostic.json · veille.json",
            "ecrit": "le code de la cible · runs.jsonl (log_run.py) · arbitrages.json",
            "interdit": "appliquer un correctif non arbitré (R4) · committer hors périmètre "
                        "(R2) · logger succes sur un livrable que l'utilisateur doit valider (R5)",
        },
        {
            "nom": "agent-supervisor",
            "titre": "🔎 agent-supervisor — qualifie",
            "invoc": "2 formes : la skill (inline) et le sous-agent — ce dernier "
                     "volontairement SANS outils Write/Edit",
            "declencheurs": "le hook SessionStart signale le diagnostic périmé (14 j) · "
                            "l'étape diagnostic de revue-increment · une demande d'audit "
                            "des pratiques",
            "lit": "state.json · routing-hints.json · runs.jsonl · les pratiques mesurées "
                   "du wiki · .claude/audits/*.json · criteres-pratiques.md · veille.json · git log",
            "ecrit": "diagnostic.json, et uniquement via write_diagnostic.py",
            "interdit": "appliquer sa propre proposition (R4) · un constat sans preuve "
                        "objective · ouvrir les transcripts JSONL bruts · dépasser 5 findings",
        },
    ]
    # « ABSENT » ET « EN SOMMEIL » NE SONT PAS LA MÊME CHOSE (demande utilisateur du
    # 2026-09-02). La page rendait `bmad-doc`, `bmad-cadrage` et `bmad-livraison`
    # « absent de .claude/agents/ » alors qu'ils ont été mis en sommeil le 2026-09-01 sur
    # décision tracée, et déplacés dans `.claude/agents-en-sommeil/`. Rendre une décision
    # comme une panne coûte deux fois : on cherche à réparer ce qu'on a retiré exprès, et
    # on cesse de croire l'étiquette le jour où elle désignera un vrai manque.
    endormis = agents_en_sommeil()
    for f in fiches:
        declares = DISPOSITIF_LANCE.get(f["nom"], [])
        lance = [n for n in declares if n in presents]
        au_repos = [n for n in declares if n not in presents and n in endormis]
        manquants = [n for n in declares if n not in presents and n not in endormis]
        puces = " ".join(f'<span class="badge">{ee(n)}</span>' for n in lance)
        if au_repos:
            puces += " " + " ".join(
                f'<span class="badge-nature" title="Mis en sommeil sur décision tracée : '
                'la skill reste routée et part inline dans la conversation courante. '
                'Voir .claude/agents-en-sommeil/README.md pour la mesure et le réveil.">'
                f'{ee(n)} — en sommeil</span>' for n in au_repos)
        if manquants:
            puces += " " + " ".join(
                f'<span class="badge-nature">{ee(n)} — absent de .claude/agents/</span>'
                for n in manquants)
        parts.append(
            f'<div class="schema-agent"><h4>{ee(f["titre"])}</h4>'
            f'<p class="invoc">{ee(f["invoc"])}</p><dl>'
            f'<dt>Se déclenche sur</dt><dd>{ee(f["declencheurs"])}</dd>'
            f'<dt>Lit</dt><dd>{ee(f["lit"])}</dd>'
            f"<dt>Lance</dt><dd>{puces or '<span class=\"muted\">aucun sous-agent</span>'}</dd>"
            f'<dt>Écrit</dt><dd>{ee(f["ecrit"])}</dd>'
            f'<dt>Ne fait jamais</dt><dd class="interdit">{ee(f["interdit"])}</dd>'
            "</dl></div>")
    parts.append("</div>")

    # --- Les sous-agents lançables ------------------------------------------
    parts.append(f"<h3>Les sous-agents lançables ({len(agents)})</h3>")
    parts.append(
        '<p class="legende">Tous portent l\'outil <code>Skill</code> : leurs invocations '
        "sont donc <strong>comptées</strong> par l'étage 1 (le scan des transcripts ne "
        "filtre pas les sous-agents). Aucun ne committe, ne pousse, ni n'écrit le journal "
        "— l'irréversible reste à la session principale.</p>")
    parts.append('<table><thead><tr><th>Sous-agent</th><th>Modèle</th>'
                 "<th>Porte l'outil Skill</th><th>Rôle</th></tr></thead><tbody>")
    for a in agents:
        # Le rôle = la description privée de son préambule (« Porteur de la famille X
        # de BMAD — … »), tronquée à la frontière de mot : le texte entier reste
        # accessible en title= (leçon wiki:finitions-lisibilite).
        role = a["description"].split(" — ", 1)[-1]
        parts.append(
            f'<tr><td><code>{ee(a["nom"])}</code></td><td>{ee(a["modele"])}</td>'
            f'<td>{"✅" if "Skill" in a["outils"] else "❌"}</td>'
            f'<td title="{ee(role)}">{ee(tronque(role, 160))}</td></tr>')
    parts.append("</tbody></table>")

    # --- Les playbooks -------------------------------------------------------
    parts.append(f"<h3>Les playbooks ({len(playbooks)})</h3>")
    parts.append(
        '<p class="legende">Un playbook est un workflow récurrent déjà payé une fois : '
        "l'orchestrateur en cherche un <strong>avant</strong> de composer un plan à vide, "
        "et l'instancie sans jamais retirer ses vérifications obligatoires ni ses "
        "checkpoints. C'est là que vivent les leçons de la flotte.</p>")
    parts.append('<div class="actions-grille">')
    for pb in playbooks:
        parts.append(
            f'<div class="action-carte carte-lecture playbook-carte"><h4>{ee(pb)}</h4>'
            f'<p>{ee(DISPOSITIF_PLAYBOOKS.get(pb, "workflow récurrent du dépôt"))}</p>'
            f'<p class="muted">.claude/orchestration/playbooks/{ee(pb)}.md</p></div>')
    parts.append("</div>")

    # --- Les règles ----------------------------------------------------------
    parts.append(f"<h3>Les règles absolues ({len(regles)})</h3>")
    parts.append(
        '<p class="legende">Lues dans <code>CLAUDE.md</code>. Chacune existe parce qu\'un '
        "écart a coûté une reprise réelle — elles contraignent les deux agents, et le "
        "schéma ci-dessus indique où chacune mord.</p>")
    parts.append("<ul>")
    for code, titre in regles:
        parts.append(f'<li><span class="regle-chip">{ee(code)}</span> {ee(titre)}</li>')
    parts.append("</ul>")

    # --- Pilotage du duo sur la flotte ---------------------------------------
    duo = pilotage_duo(projects)
    parts.append("<h3>Pilotage du duo sur la flotte</h3>")
    parts.append(
        '<p class="legende"><strong>VScode5 est le projet transverse</strong> : il porte le '
        "dispositif et pilote celui des autres. Les projets de la flotte ont leur propre "
        "copie du duo — cette table dit, pour chacun, si les deux skills sont là et si "
        "elles <em>servent</em> réellement (le compteur vient du <code>state.json</code> "
        "local de chaque projet, pas d'une déclaration). La liste est celle de "
        "<code>projets.json</code> : <strong>tout nouveau projet ajouté à la flotte entre "
        "ici automatiquement</strong>, sous la charge de VScode5.</p>")
    if duo:
        parts.append(
            "<table><thead><tr><th>Projet</th><th>agent-orchestrator</th>"
            "<th>agent-supervisor</th><th>Sous-agents</th><th>Playbooks</th>"
            "<th>Dernier diagnostic</th></tr></thead><tbody>")
        for d in duo:
            nom = ee(d["nom"]) + (
                ' <span class="badge">transverse</span>' if d["transverse"] else "")
            def cellule(present, n):
                if not present:
                    return '<td><span class="alert-critique">❌ absente</span></td>'
                if n:
                    return f"<td>✅ {n} invocation{'s' if n > 1 else ''}</td>"
                return '<td>✅ présente · <span class="muted">0 invocation</span></td>'
            parts.append(
                f"<tr><td>{nom}</td>"
                + cellule(d["orchestrateur"], d["n_orchestrateur"])
                + cellule(d["superviseur"], d["n_superviseur"])
                + f'<td>{d["sous_agents"]}</td><td>{d["playbooks"]}</td>'
                + f'<td>{ee(d["diag_date"] or "—")}</td></tr>')
        parts.append("</tbody></table>")
        sans = [d["nom"] for d in duo if not (d["orchestrateur"] and d["superviseur"])]
        dormants = [d["nom"] for d in duo
                    if d["orchestrateur"] and d["superviseur"]
                    and not (d["n_orchestrateur"] or d["n_superviseur"])]
        if sans:
            parts.append(
                '<p class="legende">À équiper : <b>' + ee(", ".join(sans)) + "</b> — "
                "greffe via le playbook <code>evolution-flotte</code> (cadrage sur l'état "
                "réel, commit scopé au périmètre), ou l'onglet <b>🚀 Déploiement</b> pour "
                "un projet neuf.</p>")
        if dormants:
            parts.append(
                '<p class="legende">Duo installé mais jamais invoqué : <b>'
                + ee(", ".join(dormants)) + "</b> — présence n'est pas usage. C'est le "
                "signal que le superviseur qualifie en <code>agent-mort</code> : soit le "
                "projet n'a pas de travail qui les justifie, soit ses déclencheurs ne "
                "matchent pas ses demandes réelles.</p>")
    else:
        parts.append('<p class="muted">Aucun projet existant dans projets.json.</p>')

    # --- Le routage BMAD -----------------------------------------------------
    parts.append("<h3>Le routage des skills BMAD</h3>")
    parts.append(
        '<p class="legende">46 skills <code>bmad-*</code> sont installées. Jusqu\'au '
        "2026-07-30 elles étaient réservées à la « demande explicite » : "
        "<strong>0 invocation sur 113 sessions</strong>. Elles sont désormais routées par "
        "besoin détecté (table complète en § 2 quinquies de la skill de l'orchestrateur), "
        "avec deux régimes — <strong>d'office</strong> seulement si la skill est bornée "
        "ET ne rend qu'un rapport (revue, recherche, rétrospective, orientation), "
        "<strong>annoncé puis validé</strong> dès qu'elle coûte cher (PRD, architecture, "
        "epics, code) <em>ou qu'elle écrit un fichier réel</em> (documentation, index, "
        "découpage). Ce second critère vient de l'arbitrage du 2026-07-30 : R4 n'interdit "
        "pas la dépense, il interdit l'auto-application — une écriture non arbitrée la "
        "viole, même rapide. 5 skills ne sont jamais routées : 4 dépréciées par BMAD, et "
        "<code>bmad-customize</code>, gelée par arbitrage jusqu'à levée explicite.</p>")
    # Emprunt RÉEL de la table — l'ancienne règle est morte sans qu'aucun instrument ne
    # le signale ; celle-ci est mesurée, pas seulement testée.
    emp = emprunt_routage_bmad()
    dormant = not emp["empruntees"] and not emp["lances"]
    parts.append(
        '<p class="legende"><b>Emprunt mesuré</b> depuis le '
        f'{ee(DATE_ROUTAGE_BMAD)} : <b>{len(emp["empruntees"])}/{emp["installees"]}</b> '
        "skills BMAD réellement invoquées, "
        f'<b>{len(emp["lances"])}/{emp["porteurs"]}</b> sous-agents porteurs réellement '
        "lancés"
        + (" — " + ee(", ".join(emp["empruntees"] + emp["lances"]))
           if not dormant else "")
        + f". Revue de l'emprunt au <b>{ee(DATE_REVUE_ROUTAGE_BMAD)}</b> : si le compte "
        "est encore à zéro, ce n'est pas la table qu'il faut enrichir — c'est le routage "
        "qu'il faut instrumenter autrement, ou abandonner. La cohérence de la table est "
        "verrouillée par des tests ; son <em>usage</em>, lui, ne se teste pas, il se "
        "mesure.</p>")
    return "\n".join(parts)


# Ce que chaque playbook présent adresse — texte affiché dans l'onglet Dispositif.
# Un playbook ajouté sans entrée ici s'affiche quand même (libellé par défaut).
DISPOSITIF_PLAYBOOKS = {
    "evolution-flotte": "Modifier un AUTRE dépôt de la flotte : cadrage sur l'état réel "
                        "→ modification scopée → vérifications → commit limité au "
                        "périmètre (R2) → wiki → journal. Éprouvé.",
    "dev-verifie": "Implémentation ou correction avec tests, vérification réelle et revue "
                   "finale avant commit.",
    "export-ppt-verifie": "Livrable = un deck PPT : génération, enrichissements "
                          "conditionnels, puis pptx-verify au rendu réel — obligatoire, "
                          "python-pptx étant un parseur tolérant.",
    "revue-design-parallele": "Revue multi-angles d'un livrable en fan-out, puis "
                              "consolidation obligatoire.",
}


PARTY_SKILL = os.path.join(ROOT, ".claude", "skills", "bmad-party-mode")
PARTY_OVERRIDE = os.path.join(ROOT, "_bmad", "custom", "bmad-party-mode.toml")

# Situations d'usage → salle à convoquer. Curaté (une situation est un jugement, elle
# ne se déduit d'aucun fichier), MAIS l'identifiant de salle est vérifié contre le TOML
# réel par tests/test_wiki_party.py : un exemple qui pointerait une salle supprimée
# serait un mode d'emploi qui ne marche pas.
PARTY_SITUATIONS = [
    ("« Personne n'a relu ce projet à froid depuis des mois »",
     "inspection-critique",
     "Quatre axes que personne ne tient ensemble ailleurs : les bugs latents, le design, "
     "l'expérience de celui qui s'en sert, et ce qui n'est JAMAIS utilisé — le plus "
     "rentable et le plus oublié des quatre.",
     "Part d'un périmètre et de mesures d'usage, pas d'un diff. Elle propose des "
     "retraits, elle n'en applique aucun."),
    ("« Est-ce qu'on est en retard sur ce qui se fait ailleurs ? »",
     "observatoire-agentic",
     "Elle classe chaque pratique sur une échelle qui n'est jamais implicite — prouvé, "
     "sorti, annoncé, hype — et exige la source primaire : une annonce de version n'est "
     "pas une sortie.",
     "Le sous-agent veille-agentic COLLECTE, cette salle QUALIFIE, le conseil de flotte "
     "ARBITRE. Elle n'adopte rien."),
    ("« Sur quoi part-on en production, et pourquoi celui-là ? »",
     "socle-technique",
     "Le choix d'environnement de production s'y écrit avec ses deux alternatives écartées "
     "et la raison de leur écart — un environnement subi parce qu'il était déjà là se "
     "repaie à chaque incident.",
     "Apporter les contraintes qui bornent le choix : données, conformité, budget, "
     "compétences disponibles pour l'exploiter."),
    ("« Dans quel langage on écrit ça ? »",
     "atelier-dev",
     "Le langage et la pile se tranchent en tête de déroulé avec la structure, pas en "
     "cours d'implémentation : le Charpentier dit ce que le choix oblige ailleurs, le "
     "Relecteur ce qu'il coûtera à relire.",
     "Apporter la pile déjà en place : un langage neuf dans un dépôt qui n'en parle aucun "
     "autre se paie en outillage, en CI et en relecteurs."),
    ("« Combien coûtent nos environnements, et sait-on encore les redéployer ? »",
     "socle-technique",
     "Le parc est décrit avant d'être corrigé, puis trié par risque : environnements, "
     "secrets et leur rotation, coût de ce qui tourne, reprise après incident.",
     "À ne pas confondre avec la mise en service, qui est un guichet par release. "
     "Elle ne touche aucun environnement."),
    ("« Ce bug de VSCode2 touche trois couches, je ne sais pas par où commencer »",
     "atelier-dev",
     "Les trois dev défendent chacun leur couche : c'est ce qui fait sortir le conflit "
     "d'interface avant l'implémentation, et la partition des fichiers qui suivra.",
     "Inviter le relais du projet. La salle rend un plan, pas un diff."),
    ("« La veille propose une pratique — on l'adopte ou pas ? »",
     "conseil-flotte",
     "Vigie apporte l'état de l'art, Argus ce que les mesures disent, Quincaillier si "
     "l'outil existe déjà, Garde-fou ce que ça coûterait à maintenir.",
     "La salle ne décide pas : elle instruit. L'adoption reste un arbitrage humain (R4)."),
    ("« Ce deck est techniquement correct mais il ne ressemble à rien »",
     "atelier-deck",
     "Le Maquettiste défend la fabrication, le Contrôleur le gabarit, Sally le regard "
     "de celui qui reçoit le document.",
     "Aucun avis ne vaut sans avoir ouvert l'artefact exact, en entier."),
    ("« On voudrait passer VSCode1 en production »",
     "mise-en-service",
     "Aiguilleur regarde les environnements et les secrets, Passerelle ce qui sortirait "
     "du poste, Archiviste si la doc d'exploitation existe, Garde-fou si les tests tiennent.",
     "La seule cible de la flotte où cette salle a un objet réel aujourd'hui."),
    ("« Ma consommation de tokens a doublé ce mois-ci »",
     "revue-consommation",
     "Jauge part des chiffres mesurés, Argus des runs réellement joués, Quincaillier "
     "des outils qui tournent pour rien.",
     "Première question de la salle : le bon étage a-t-il été essayé d'abord ?"),
    ("« Un nouveau projet VSCode6 arrive, personne ne le connaît »",
     "accueil-projet",
     "Salle open-cast : elle génère les voix dont elle a besoin le temps de cadrer la "
     "cible, sans qu'on ait à écrire un relais d'avance.",
     "Si le projet reste, lui écrire un relais durable dans le TOML — les voix "
     "générées sont jetables."),
    ("« Ce code me paraît risqué mais je n'arrive pas à dire pourquoi »",
     "code-review-crew",
     "Salle livrée avec la skill : cinq angles d'attaque distincts (sécurité, "
     "contradiction, cas limites, artisanat, livrer) qui se disputent sur ce qui compte.",
     "Prévue pour --mode subagent : chaque angle doit examiner avant de confronter."),
    ("« J'ai une intuition mais je n'arrive pas à en faire une question »",
     "atelier-idees",
     "Salle d'AMONT : le Cadreur pose le problème avant qu'on cherche des solutions, "
     "Portevoix parle pour l'usager absent, Wildcard ouvre les options, Splinter casse "
     "l'accord trop facile.",
     "Sa sortie alimente les autres salles : une liste d'options avec leurs critères, "
     "qui part ensuite au conseil de flotte ou à l'atelier concerné."),
    ("« Cette dépense de tokens a-t-elle acheté quelque chose ? »",
     "revue-consommation",
     "Jauge part des chiffres mesurés, Argus des runs réellement joués, Quincaillier "
     "des outils qui tournent pour rien.",
     "Première question de la salle : le bon étage a-t-il été essayé d'abord ?"),
    ("« Tout le monde est d'accord trop vite et ça me met mal à l'aise »",
     "anti-consensus-club",
     "Salle livrée : elle existe pour casser le faux consensus, ouvrir des options et "
     "arrêter les boucles qui tournent à vide.",
     "Elle soutient votre jugement, elle ne le remplace pas : elle ne vote pas."),
]

# Étapes du schéma de fonctionnement de la table ronde. Ce qui est ÉCRIT ici est la
# boucle (invariante) ; les rôles et les salles, eux, sont DÉRIVÉS du TOML réel —
# un schéma qui recopierait le casting mentirait dès le premier rôle ajouté.
PARTY_BOUCLE = [
    ("1. Convoquer", "l'humain", "choisit une salle et un mode",
     "--party <id> --mode auto|subagent"),
    ("2. Délibérer", "les rôles", "défendent chacun leur angle, et se contredisent",
     "chaque voix reçoit toute la salle à chaque tour"),
    ("3. Conclure", "la salle", "produit une décision ET une partition du travail",
     "un plan, jamais un diff"),
    ("4. Exécuter", "l'orchestrateur", "reprend le plan en fan-out de sous-agents",
     "vérifications obligatoires + runs.jsonl"),
]


def _lire_toml(chemin):
    """Charge un TOML, {} si absent ou illisible (fail-open : le wiki se rend sans)."""
    try:
        import tomllib
        with open(chemin, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, ImportError, ValueError):
        return {}


def party_collectif():
    """(membres, groupes) de la table ronde, mergés comme le fait le vrai résolveur.

    DÉRIVÉ des TOML réels, jamais recopié — en lecture seule et à 0 token. Trois
    sources, dans l'ordre où `resolve_party.py` les empile : les agents BMAD
    « installés » (_bmad/config.toml), les personas « livrés » avec la skill, puis
    les rôles « maison » de notre override, qui peuvent écraser les précédents.

    Les agents installés DOIVENT être du lot : une salle peut convoquer Sally ou
    Winston, et sans eux le schéma les afficherait « non résolu » alors que le
    résolveur, lui, les trouve — un schéma faux coûte plus cher que pas de schéma.
    """
    agents = _lire_toml(os.path.join(ROOT, "_bmad", "config.toml")).get("agents", {})
    installes = [{"code": code, **(entree or {})} for code, entree in agents.items()]
    base = _lire_toml(os.path.join(PARTY_SKILL, "customize.toml")).get("workflow", {})
    over = _lire_toml(PARTY_OVERRIDE).get("workflow", {})

    def merge(cle, ident, couches):
        out, index = [], {}
        for source, entrees in couches:
            for entree in entrees or []:
                code = entree.get(ident)
                if not code:
                    continue
                fusion = {**entree, "source": source}
                if code in index:
                    out[index[code]] = {**out[index[code]], **fusion}
                else:
                    index[code] = len(out)
                    out.append(fusion)
        return out

    membres = merge("party_members", "code", (
        ("installé", installes),
        ("livré", base.get("party_members")),
        ("maison", over.get("party_members")),
    ))
    groupes = merge("party_groups", "id", (
        ("livré", base.get("party_groups")),
        ("maison", over.get("party_groups")),
    ))
    return membres, groupes


def render_contrat_salle(g):
    """Le contrat d'une salle : redevabilités, qualité requise, entrants, sortants.

    Demande utilisateur du 2026-09-01. Ce que le contrat sert à empêcher : une salle
    convoquée sans ses entrants délibère sur du vide, et une salle dont le sortant
    n'est pas recevable produit un compte rendu que personne ne peut opposer au
    livrable. Les **entrants** sont donc la dent amont (on refuse de siéger sans eux),
    la **recette** la dent aval (l'orchestrateur ne clôt pas tant qu'elle n'est pas
    jouée).

    Le producteur est TOUJOURS quelqu'un d'autre que la salle : elle nomme le livrable,
    elle ne l'écrit pas — c'est l'invariant qui garde R4 contre l'auto-application
    collective. Rendu ici plutôt que décrit ailleurs, parce qu'un contrat qui vit dans
    un fichier que ni le wiki ni le plan ne lisent est exactement la panne déjà payée
    par la table situation→salle (corrigée le 2026-08-31).
    """
    ee = html.escape
    sortants = g.get("sortants") or {}
    # Même filtre que le hook guard_salle_skills : une valeur mal typée dans le TOML ne
    # doit pas avorter la génération du wiki entier (revue du 2026-09-02).
    brut = g.get("skills_bmad")
    skills_bmad = [x for x in (brut if isinstance(brut, list) else []) if isinstance(x, str)]
    if not (g.get("redevabilites") or g.get("entrants") or sortants or g.get("manifeste")
            or skills_bmad):
        return ""

    def liste(items):
        return "<ul>" + "".join(f"<li>{ee(i)}</li>" for i in items or []) + "</ul>"

    out = ['<details class="contrat-salle"><summary>Contrat et manifeste de la salle</summary>']
    if g.get("manifeste"):
        out.append("<p class='muted'><b>Manifeste de fonctionnement</b> — comment elle "
                   "siège</p>")
        out.append(liste(g["manifeste"]))
    if g.get("redevabilites"):
        out.append("<p class='muted'><b>Redevabilités</b> — ce dont la salle répond</p>")
        out.append(liste(g["redevabilites"]))
    if g.get("qualite_requise"):
        out.append("<p class='muted'><b>Qualité requise</b></p>")
        out.append(f"<p>{ee(g['qualite_requise'])}</p>")
    # LES SKILLS QUE LES VOIX DOIVENT CHARGER (raccord du 2026-09-02). Rendues ici parce
    # qu'une donnée que ni le wiki ni le plan ne lisent est exactement la panne déjà payée
    # par la table situation→salle. Seules des skills du régime « d'office » y figurent :
    # une salle ne modifie aucun fichier, un test l'exige.
    if skills_bmad:
        out.append("<p class='muted'><b>Skills BMAD à charger</b> — les voix les invoquent "
                   "réellement via l'outil <code>Skill</code>, le nom va dans leur brief</p>")
        out.append("<p>" + " · ".join(f"<code>{ee(s)}</code>" for s in skills_bmad)
                   + "</p>")
    if g.get("entrants"):
        out.append("<p class='muted'><b>Entrants</b> — sans eux, la salle ne siège pas</p>")
        out.append(liste(g["entrants"]))
    if sortants:
        out.append("<p class='muted'><b>Sortants</b></p>")
        out.append(f"<p>{ee(sortants.get('type', ''))} — produit par "
                   f"<i>{ee(sortants.get('producteur', ''))}</i>, "
                   "jamais par la salle elle-même.</p>")
        if sortants.get("recette"):
            out.append("<p class='muted'><b>Recette</b> — l'orchestrateur ne clôt pas "
                       "tant qu'elle n'est pas jouée</p>")
            out.append(liste(sortants["recette"]))
    out.append("</details>")
    return "".join(out)


def render_party_html():
    """Schéma de fonctionnement de la table ronde élargie (demande utilisateur
    2026-07-31), dérivé de `_bmad/custom/bmad-party-mode.toml` et du `customize.toml`
    de la skill : les salles, leur casting résolu, et la boucle convoquer → délibérer
    → conclure → exécuter."""
    ee = html.escape
    membres, groupes = party_collectif()
    if not membres:
        return ""
    par_code = {m["code"]: m for m in membres}
    # Index de résolution du vrai résolveur : code, code en minuscules, alias sans
    # préfixe bmad-*, et NOM du membre. Une salle peut donc citer « ux-designer »
    # ou « Sally » aussi bien que « bmad-agent-ux-designer ».
    for m in membres:
        for cle in (m["code"].lower(),
                    re.sub(r"^bmad-(agent-)?", "", m["code"]).lower(),
                    (m.get("name") or "").lower()):
            if cle:
                par_code.setdefault(cle, m)
    maison = [m for m in membres if m.get("source") == "maison"]
    livres = [m for m in membres if m.get("source") == "livré"]
    installes = [m for m in membres if m.get("source") == "installé"]

    parts = ['<h3 id="party">Le schéma de la table ronde élargie</h3>']
    parts.append(
        '<p class="legende">La table ronde <strong>délibère</strong> ; elle n\'exécute pas. '
        "C'est ce qui la distingue d'un fan-out : les voix sont là pour se contredire et "
        "faire sortir un désaccord AVANT l'implémentation, pas pour travailler en parallèle. "
        f"Le vivier compte <strong>{len(membres)} voix</strong> — {len(maison)} rôles maison, "
        f"{len(livres)} personas livrés avec la skill, {len(installes)} agents BMAD installés "
        f"— réparties en <strong>{len(groupes)} salles</strong>. Dérivé des TOML réels : "
        "ce schéma ne peut pas décrire un rôle qui n'existe plus.</p>")

    parts.append('<div class="flux">')
    for i, (verbe, acteur, quoi, artefact) in enumerate(PARTY_BOUCLE):
        if i:
            parts.append('<div class="flux-fleche" aria-hidden="true">→</div>')
        parts.append(
            '<div class="flux-etape agent">'
            f'<div class="qui">{ee(verbe)}</div>'
            f'<div class="quoi">{ee(acteur)}</div>'
            f'<div class="ou">{ee(quoi)}</div>'
            f'<div class="ou">{ee(artefact)}</div></div>')
    parts.append("</div>")

    parts.append("<h4>Les salles</h4>")
    parts.append('<div class="actions-grille">')
    for g in groupes:
        codes = g.get("members") or []
        if codes:
            noms = []
            for c in codes:
                m = par_code.get(c)
                noms.append(m.get("name") or c if m else f"{c} (non résolu)")
            casting = ", ".join(noms)
            taille = f"{len(codes)} voix"
        else:
            casting = "open-cast — la salle génère ses voix à la volée"
            taille = "variable"
        memoire = "mémoire gardée" if g.get("memory") else "sans mémoire"
        # Les scènes livrées par BMAD font jusqu'à ~1000 caractères d'anglais : vu au
        # rendu réel, elles écrasent les nôtres (~150) et la grille devient illisible.
        # On tronque à l'affichage, le texte intégral restant en infobulle.
        scene = (g.get("scene") or "").strip()
        court = scene if len(scene) <= 230 else scene[:227].rstrip(" ,.;:") + "…"
        titre_attr = f' title="{ee(scene)}"' if court != scene else ""
        parts.append(
            '<div class="action-carte carte-lecture">'
            f'<h4>{ee(g.get("name") or g.get("id"))}'
            f' <span class="muted">({ee(taille)}, {ee(memoire)})</span></h4>'
            f'<p{titre_attr}>{ee(court)}</p>'
            f'<p class="muted">Casting : {ee(casting)}</p>'
            f'<p class="muted">Ouvrir : <code>--party {ee(g.get("id"))}</code></p>'
            + render_contrat_salle(g) +
            "</div>")
    parts.append("</div>")

    parts.append("<h4>Quelle salle pour quelle situation ?</h4>")
    parts.append(
        '<p class="legende">Le mode d\'emploi : à gauche ce qu\'on se dit vraiment quand '
        "on bloque, à droite la salle à convoquer et ce qu'on peut en attendre. Les "
        "identifiants de salle sont vérifiés contre le TOML réel — un exemple qui "
        "pointerait une salle supprimée serait un mode d'emploi qui ne marche pas.</p>")
    parts.append('<table class="tbl"><thead><tr><th>La situation</th><th>La salle</th>'
                 "<th>Pourquoi celle-là</th><th>À savoir</th></tr></thead><tbody>")
    noms_salles = {g["id"]: (g.get("name") or g["id"]) for g in groupes}
    for situation, salle, pourquoi, savoir in PARTY_SITUATIONS:
        if salle not in noms_salles:
            continue  # salle supprimée : ne pas afficher un mode d'emploi mort
        parts.append(
            f"<tr><td>{ee(situation)}</td>"
            f'<td><b>{ee(noms_salles[salle])}</b><br>'
            f'<code>--party {ee(salle)}</code></td>'
            f"<td>{ee(pourquoi)}</td>"
            f'<td class="muted">{ee(savoir)}</td></tr>')
    parts.append("</tbody></table>")

    parts.append("<h4>Les rôles maison</h4>")
    parts.append(
        '<p class="legende">Ajoutés par notre override, en plus des personas livrés avec '
        "la skill (que le merge keyé préserve). Un rôle adossé à un agent existant "
        "<strong>cite ce qui est déjà mesuré</strong> et ne réinvente pas de chiffre : s'il "
        "faut une preuve nouvelle, la salle demande de lancer l'agent, elle ne l'improvise "
        "pas.</p>")
    parts.append('<table class="tbl"><thead><tr><th>Rôle</th><th>Porte</th>'
                 "<th>S'appuie sur</th></tr></thead><tbody>")
    for m in maison:
        parts.append(
            f'<tr><td><b>{ee(m.get("name") or m["code"])}</b><br>'
            f'<span class="muted">{ee(m["code"])}</span></td>'
            f'<td>{ee(m.get("title") or "")}</td>'
            f'<td class="muted">{ee(m.get("capabilities") or "")}</td></tr>')
    parts.append("</tbody></table>")
    return "\n".join(parts)


TOKENS_JSON = os.path.join(ROOT, ".claude", "supervision", "tokens.json")

# Qui REÇOIT la sortie de chaque salle. Une table ronde rend un compte rendu et une
# partition du travail : ce tableau dit à qui ce livrable est destiné — l'humain qui
# arbitre, l'orchestrateur qui exécute, ou une AUTRE salle qui en repart (la sortie
# de l'atelier d'idées est l'entrée du conseil de flotte ou d'un atelier). Vérifié
# par test : toute salle citée ici doit exister, et toute salle doit avoir un
# destinataire — un travail que personne ne réceptionne est un travail perdu.
PARTY_DESTINATAIRES = {
    "observatoire-agentic": ("le sous-agent veille-agentic, puis le conseil de flotte",
                             "ses pratiques CLASSÉES alimentent veille.json ; l'adoption "
                             "reste un arbitrage humain, jamais prononcé par la salle"),
    "inspection-critique": ("l'humain, puis l'orchestrateur",
                            "ses constats partent en correctifs scopés ; ses RETRAITS "
                            "proposés sont un arbitrage humain, jamais appliqués par la salle"),
    "socle-technique": ("l'humain, puis evolution-flotte",
                        "son plan d'infrastructure est trié par risque ; tout changement "
                        "d'environnement reste arbitré — la salle ne déploie rien"),
    "conseil-flotte": ("l'humain, qui arbitre",
                       "ses conclusions deviennent des arbitrages (adopte/écarte, "
                       "valide/refuse) — jamais auto-appliquées"),
    "atelier-dev": ("l'orchestrateur, qui exécute",
                    "son plan et sa partition de fichiers partent en fan-out de "
                    "sous-agents, avec vérifications et journal"),
    "atelier-deck": ("le Maquettiste, puis l'humain",
                     "ses exigences guident la fabrication ; le deck final revient à "
                     "l'humain pour validation sur l'artefact exact"),
    "mise-en-service": ("l'orchestrateur, via evolution-flotte",
                        "ses prérequis (environnements, secrets, doc) deviennent des "
                        "correctifs scopés sur le projet cible"),
    "atelier-idees": ("les autres salles",
                      "sa sortie — des options formulées avec leurs critères — est "
                      "l'ENTRÉE du conseil de flotte ou de l'atelier concerné"),
    "revue-consommation": ("l'humain et le superviseur",
                           "ses constats chiffrés alimentent les axes d'amélioration "
                           "et peuvent devenir des findings"),
    "accueil-projet": ("l'atelier d'idées ou le conseil",
                       "son cadrage du nouveau projet nourrit la création d'un relais "
                       "durable, arbitrée par l'humain"),
    "code-review-crew": ("l'auteur du code, qui corrige",
                         "ses findings par sévérité reviennent à celui qui a écrit — "
                         "la salle signale, elle ne corrige pas"),
    "anti-consensus-club": ("celui qui doutait",
                            "elle rend le désaccord visible et la décision à l'humain "
                            "— elle ne vote pas"),
}

# Quelle salle pour quel endroit du wiki. Le principe : la salle DÉLIBÈRE avant (ou à
# côté de) l'action, elle ne la remplace pas — on convoque des voix quand la question
# est « faut-il, et comment ? », pas quand elle est « lance le scan ».
# Les identifiants sont vérifiés contre le TOML réel par tests/test_wiki_party.py :
# un bouton qui pointerait une salle supprimée serait un bouton mort.
PARTY_PAR_CONTEXTE = {
    "veille": ("conseil-flotte",
               "Faut-il adopter cette trouvaille de veille, et à quel coût de maintenance ?"),
    "diagnostic": ("conseil-flotte",
                   "Que disent les findings ouverts, et lesquels méritent d'être traités "
                   "en premier ?"),
    "correctif": ("conseil-flotte",
                  "Ce finding vaut-il un correctif, et lequel — la reco est-elle déjà "
                  "satisfaite en tout ou partie ?"),
    "correctif-dev": ("atelier-dev",
                      "Comment implémenter ce correctif, et qui touche quels fichiers ?"),
    "correctif-deck": ("atelier-deck",
                       "Ce livrable respecte-t-il son gabarit, et que faut-il refaire ?"),
    "deploiement": ("mise-en-service",
                    "Ce déploiement est-il prêt : environnements, secrets, doc "
                    "d'exploitation, tests ?"),
    "exports": ("atelier-deck",
                "Ce document exporté est-il lisible et conforme pour son destinataire ?"),
    "tokens": ("revue-consommation",
               "Cette dépense achète-t-elle des décisions, et quel étage moins cher "
               "aurait suffi ?"),
}

# Un correctif n'appelle pas les mêmes voix selon ce qu'il touche : un écart de test
# se débat entre dev, un gabarit de deck entre maquettiste et contrôleur, un sujet
# d'exploitation en mise en service. Le contexte est DÉDUIT de la catégorie du
# finding ou du libellé de la pratique en écart, avec repli sur le conseil de flotte.
def contexte_party_correctif(cle_ou_categorie):
    texte = (cle_ou_categorie or "").lower()
    if any(m in texte for m in ("test", "dev", "couverture", "lint", "revue", "risque",
                                "securite", "sécurité", "robustesse", "performance")):
        return "correctif-dev"
    if any(m in texte for m in ("design", "deck", "slide", "ppt", "charte", "gabarit")):
        return "correctif-deck"
    if any(m in texte for m in ("doc", "deploiement", "déploiement", "env", "produit")):
        return "deploiement"
    return "correctif"


def bouton_party(contexte, sujet=None, libelle="🗣️ Déclencher"):
    """Le bouton « convoquer la salle » d'un contexte donné.

    Rendu vide si le contexte est inconnu — mieux vaut pas de bouton qu'un bouton qui
    lance une salle inexistante.
    """
    entree = PARTY_PAR_CONTEXTE.get(contexte)
    if not entree:
        return ""
    salle, sujet_defaut = entree
    sujet = (sujet or sujet_defaut).replace('"', "'")
    return (f'<button class="llm btn-party" data-action="party" '
            f'data-salle="{html.escape(salle)}" data-sujet="{html.escape(sujet)}" '
            f'title="Convoque la salle « {html.escape(salle)} » en mode subagent : elle '
            "délibère et rend un compte rendu, elle ne modifie aucun fichier. Le compte "
            f'rendu apparaît dans l\'onglet Actions.">{libelle}</button>')

# Palette catégorielle des 3 composantes du coût. Slots 1-3 de la palette de
# référence dataviz, VALIDÉE par scripts/validate_palette.js dans les deux modes
# (bande de clarté, plancher de chroma, séparation CVD deutan ΔE 9.2 / normal 27.6,
# contraste). Le vert clair sort à 2,74:1 sur fond blanc, sous le seuil de 3:1 :
# le validateur l'autorise à condition d'un relief — d'où les labels directs ET la
# vue tableau plus bas, qui ne sont donc pas décoratifs.
COUT_SERIES = [
    ("input_tokens", "Entrée", "var(--serie-1)"),
    ("output_tokens", "Sortie", "var(--serie-2)"),
    ("cache_creation_input_tokens", "Écriture de cache", "var(--serie-3)"),
]


def _fr(n):
    """12345 -> '12 345' (espace insécable fine, lisible dans un tableau)."""
    return f"{int(n):,}".replace(",", " ")


VUES_PATH = os.path.join(ROOT, ".claude", "supervision", "vues.jsonl")
JOBS_PATH = os.path.join(ROOT, ".claude", "supervision", "jobs.jsonl")


def _compter_journal(chemin):
    """(n, première date, dernière date) d'un journal JSONL. Fail-open à 0."""
    n, n_onglets, premiere, derniere = 0, 0, None, None
    try:
        with open(chemin, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    entree = json.loads(ligne)
                except ValueError:
                    continue
                # Un marqueur de démarrage déclare une fenêtre d'observation ; ce
                # n'est ni une ouverture de page ni une action lancée.
                if entree.get("event"):
                    continue
                # Un clic d'onglet (champ `onglet`, posé le 2026-09-02) n'est pas une
                # ouverture de page : le compter ici casserait la ligne de base que
                # `_journaliser_vue` promet de ne pas bouger (revue du 2026-09-02).
                if entree.get("onglet"):
                    n_onglets += 1
                    continue
                ts = entree.get("ts")
                n += 1
                if ts:
                    premiere = ts if premiere is None or ts < premiere else premiere
                    derniere = ts if derniere is None or ts > derniere else derniere
    except OSError:
        pass
    return {"n": n, "premiere": premiere, "derniere": derniere, "n_onglets": n_onglets}


def fenetres_observees():
    """Combien de fois l'instrument a DÉCLARÉ commencer à regarder, et quand.

    Sans marqueur, la fenêtre est INCONNUE — pas vide. C'est la distinction qui
    manquait au 2026-08-31 : `jobs.jsonl` portait 242 entrées et zéro marqueur, donc
    aucune fenêtre déclarée, et son silence a été lu comme une mesure.
    """
    sessions, premiere, derniere = 0, None, None
    try:
        with open(JOBS_PATH, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    entree = json.loads(ligne)
                except ValueError:
                    continue
                if entree.get("event") != "demarrage":
                    continue
                ts = entree.get("ts")
                sessions += 1
                if ts:
                    premiere = ts if premiere is None or ts < premiere else premiere
                    derniere = ts if derniere is None or ts > derniere else derniere
    except OSError:
        pass
    return {"sessions": sessions, "premiere": premiere, "derniere": derniere}


def lire_vues():
    """Combien de fois la page a été OUVERTE (journal posé le 2026-08-31).

    `n_onglets` compte à part les onglets atteints (lignes portant `onglet`, posées le
    2026-09-02) : c'est l'instrument qui sépare « jamais atteint » de « atteint sans
    clic », et il ne doit pas gonfler `n`."""
    return _compter_journal(VUES_PATH)


def lire_actions_lancees():
    """Combien d'actions ont été LANCÉES depuis la page."""
    return _compter_journal(JOBS_PATH)


_PDJ = None


def charge_point_du_jour():
    """Charge `.claude/hooks/point_du_jour.py` (hub-local) pour RÉUTILISER sa
    collecte des décisions en attente au lieu de la réimplémenter — même geste que
    point_du_jour avec le canon (leçon payée le 2026-07-31 : recoder de tête une
    sémantique déjà corrigée réintroduit ses bugs)."""
    global _PDJ
    if _PDJ is None:
        chemin = os.path.join(ROOT, ".claude", "hooks", "point_du_jour.py")
        spec = importlib.util.spec_from_file_location("point_du_jour_scan", chemin)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _PDJ = mod
    return _PDJ


def collecte_decisions_en_attente():
    """Les trois familles de décisions en attente d'un arbitrage HUMAIN — même
    sémantique que le hook point_du_jour (findings non arbitrés au sens canonique,
    trouvailles non couvertes par un arbitrage conclusif), plus les runs
    `en-attente-validation` du hub. Fail-open par famille : le wiki se génère
    même si une source casse (règle du scan : jamais échouer pour un fichier)."""
    try:
        findings = charge_point_du_jour().findings_ouverts()
    except Exception:
        findings = []
    try:
        trouvailles = [{"titre": (t.get("titre") or "").strip(),
                        "date": t.get("date")}
                       for t in charge_point_du_jour().trouvailles_ouvertes()]
    except Exception:
        trouvailles = []
    _, en_attente = read_runs(ROOT)
    return {"findings": findings, "trouvailles": trouvailles, "runs": en_attente}


def render_decisions_html(dec):
    """Le judas à trois décisions (arbitrage « Judas compté », salle atelier-idées,
    page « Trois lectures d'un zéro » v3, 2026-08-31).

    Chaque bouton est posé SUR l'objet en attente — un clic ne met à l'épreuve
    l'hypothèse « introuvables au bon moment » que si le bouton est visiblement
    relié à la décision. Les boutons génériques (scan, vérifications, audit,
    veille, exports, déploiement…) sont retirés du générateur : leurs commandes
    restent documentées au terminal, et les compteurs de vues/actions observent
    le résultat."""
    e = html.escape
    parts = ["<h3>Ce qui attend votre décision</h3>"]
    if not (dec["findings"] or dec["trouvailles"] or dec["runs"]):
        parts.append(
            '<p class="muted">Rien n\'attend votre décision — le silence est une '
            "information (les compteurs, eux, continuent de regarder).</p>")
    parts.append('<div class="actions-grille">')
    for f in dec["findings"]:
        titre = f.get("titre") or ""
        parts.append(
            '<div class="action-carte"><h4>Arbitrer le finding '
            '<span class="badge-llm">LLM</span></h4>'
            f'<p title="{e(titre)}"><code>{e(f["cible"])}</code> — '
            f"{e(tronque(titre, 150)) or 'sans titre'}</p>"
            f'<button class="llm oui" data-action="valider" data-cible="{e(f["cible"])}">'
            "Appliquer (le clic vaut arbitrage)</button> "
            f'<button class="non" data-action="refuser" data-cible="{e(f["cible"])}">'
            "Refuser</button></div>")
    for t in dec["trouvailles"]:
        titre = t.get("titre") or ""
        date = str(t.get("date") or "")
        parts.append(
            '<div class="action-carte"><h4>Arbitrer la trouvaille de veille '
            '<span class="badge-llm">LLM</span></h4>'
            f'<p title="{e(titre)}">{e(tronque(titre, 150))}'
            + (f' <span class="muted">(depuis le {e(date)})</span>' if date else "")
            + "</p>"
            f'<button class="llm oui" data-action="adopter" data-cible="{e(titre)}">'
            "Adopter (applique)</button> "
            f'<button class="non" data-action="ecarter-veille" data-cible="{e(titre)}">'
            "Écarter</button></div>")
    for r in dec["runs"]:
        ts = str(r.get("ts") or "")
        parts.append(
            '<div class="action-carte"><h4>Solder le run en attente '
            '<span class="badge-0t">0 token</span></h4>'
            f'<p>{e(tronque(r.get("demande") or "", 150))} '
            f'<span class="muted">({e(ts)})</span></p>'
            f'<button class="oui" data-action="solder" data-cible="{e(ts)}">'
            "Valider ce livrable (solde en succès)</button></div>")
    parts.append("</div>")
    parts.append('<h3>Rapports de la session</h3><div id="rapports-decisions">'
                 '<p class="vide">Aucune action lancée dans cette session.</p></div>')
    return "\n".join(parts)


def lire_journal_usage():
    """usage.jsonl agrégé : invocations, fins de sous-agent, échecs avérés.

    Ce lecteur est la moitié qui manquait. Mesuré le 2026-09-01 en instruisant
    l'adoption de `veille:disler-observabilite` : le journal portait **250 lignes et
    AUCUN lecteur** — `log_usage.py` écrivait à chaque invocation depuis des semaines,
    et rien dans le hub ne l'ouvrait. Les compteurs de l'étage 1 viennent de
    `state.json`, produit par le scan des transcripts, pas d'ici.

    C'est précisément « le dispositif actif que personne ne lit » que la salle
    `revue-consommation` existe pour nommer. Élargir ce qui est capté sans donner un
    lecteur au journal aurait doublé la dépense sans rien acheter — l'adoption d'une
    pratique d'observabilité qui n'observe rien.
    """
    chemin = os.path.join(ROOT, ".claude", "supervision", "usage.jsonl")
    agg = {"invocations": 0, "fins_sous_agent": 0, "echecs": 0, "sessions": set(),
           "premier": None, "dernier": None, "par_skill": {}}
    if not os.path.isfile(chemin):
        return agg
    with open(chemin, encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                e = json.loads(ligne)
            except ValueError:
                continue  # une ligne illisible ne doit pas faire mentir tout le reste
            if not isinstance(e, dict):
                continue
            ts = e.get("ts")
            if ts:
                agg["premier"] = min(agg["premier"] or ts, ts)
                agg["dernier"] = max(agg["dernier"] or ts, ts)
            if e.get("session_id"):
                agg["sessions"].add(e["session_id"])
            if e.get("event") == "subagent-stop":
                agg["fins_sous_agent"] += 1
                continue
            agg["invocations"] += 1
            if e.get("echec"):
                agg["echecs"] += 1
            nom = e.get("skill") or e.get("subagent_type") or e.get("tool") or "?"
            agg["par_skill"][nom] = agg["par_skill"].get(nom, 0) + 1
    return agg


def render_journal_usage_html():
    """Rend le journal temps réel — et dit ce que l'écart dispatch/retour signifie."""
    ee = html.escape
    a = lire_journal_usage()
    if not a["invocations"] and not a["fins_sous_agent"]:
        return ""
    top = sorted(a["par_skill"].items(), key=lambda kv: -kv[1])[:8]
    parts = ['<h4>Journal temps réel des invocations (<code>usage.jsonl</code>)</h4>']
    parts.append(
        '<p class="legende">Écrit par le hook <code>log_usage.py</code> à chaque '
        "invocation, et — depuis l'adoption de <code>veille:disler-observabilite</code> "
        "le 2026-09-01 — à chaque FIN de sous-agent. Jusqu'à cette date le journal "
        "n'avait <strong>aucun lecteur</strong> : 250 lignes écrites, zéro lue. "
        "Élargir ce qu'on capte sans donner un lecteur au journal, c'est doubler la "
        "dépense sans rien acheter.</p>")
    parts.append('<div class="actions-grille">')
    parts.append(
        '<div class="action-carte carte-lecture"><h4>Ce que le journal compte</h4>'
        f'<p><b>{a["invocations"]}</b> invocation(s) · '
        f'<b>{a["fins_sous_agent"]}</b> fin(s) de sous-agent · '
        f'<b>{a["echecs"]}</b> échec(s) avéré(s)</p>'
        f'<p class="muted">{len(a["sessions"])} session(s), du '
        f'{ee((a["premier"] or "")[:10] or "—")} au {ee((a["dernier"] or "")[:10] or "—")}.</p>'
        "</div>")
    if a["fins_sous_agent"] == 0:
        lecture = ("Aucune fin de sous-agent enregistrée : soit aucun sous-agent n'a "
                   "tourné depuis le câblage du hook <code>SubagentStop</code>, soit le "
                   "hook ne se déclenche pas. Les deux se distinguent en dispatchant un "
                   "sous-agent et en relisant cette carte — pas en le supposant.")
    else:
        lecture = ("L'écart entre invocations et fins de sous-agent est le signal neuf : "
                   "un sous-agent DISPATCHÉ et un sous-agent REVENU s'écrivaient pareil "
                   "avant, donc un fan-out dont une branche meurt était indiscernable "
                   "d'un fan-out complet.")
    parts.append('<div class="action-carte carte-lecture"><h4>Comment le lire</h4>'
                 f"<p>{lecture}</p>"
                 '<p class="muted">Un échec n\'est compté que s\'il est POSITIVEMENT '
                 "marqué par l'outil : absence de marque signifie « on ne sait pas », "
                 "jamais « ça a marché ».</p></div>")
    if top:
        lignes = "".join(f"<li>{ee(n)} — <b>{c}</b></li>" for n, c in top)
        parts.append('<div class="action-carte carte-lecture"><h4>Le plus invoqué</h4>'
                     f"<ul>{lignes}</ul></div>")
    parts.append("</div>")
    return "".join(parts)


def render_usage_reel_html():
    """Les deux compteurs côte à côte, et ce que leur combinaison signifie.

    Un seul compteur ne départage rien. `jobs.jsonl` montrait zéro clic humain en un
    mois (mesuré le 2026-08-31 : 242 entrées, dont 109 `test`, 70 `refuser` sur cibles
    de test, 62 `sync-check`, et 1 `party` qui était elle-même un test de câblage), et
    ce zéro admettait trois lectures contraires — boutons introuvables, boutons
    inutiles, ou page jamais ouverte. La salle `atelier-idees` a buté là-dessus faute
    de mesure. Le rendu doit donc NOMMER la lecture, pas seulement afficher un nombre :
    sinon on aura remis un chiffre sans remettre la question.
    """
    v, a, f = lire_vues(), lire_actions_lancees(), fenetres_observees()
    def _jour(ts):
        return (ts or "")[:10] or "—"
    if f["sessions"] == 0:
        lecture = ("<b>Période NON OBSERVÉE</b> : le journal ne porte aucun marqueur de "
                   "démarrage, donc rien ne dit que l'instrument regardait. Un zéro ne "
                   "vaut que rapporté à une fenêtre déclarée — celui-ci ne se lit pas. "
                   "C'est l'état de <code>jobs.jsonl</code> jusqu'au 2026-08-31 : "
                   "242 entrées, 26 h réellement observées, et une pression de bouton "
                   "réelle manquée dans sa propre fenêtre.")
    elif v["n"] == 0 and a["n"] == 0:
        lecture = ("Aucune ouverture, aucune action : rien ne dit encore si les boutons "
                   "sont introuvables ou inutiles — l'hypothèse à écarter d'abord est le "
                   "<b>mauvais canal</b> (la page ne s'ouvre pas, donc ce qu'on écrit en "
                   "tête n'a aucune importance).")
    elif v["n"] > 0 and a["n"] == 0:
        lecture = ("La page s'ouvre et rien n'est lancé : le canal est bon, la question "
                   "devient <b>introuvables ou inutiles</b> — et elle se tranche en "
                   "regardant si la décision a été prise ailleurs, au terminal.")
    elif v["n"] == 0 and a["n"] > 0:
        lecture = ("Des actions sans ouverture de page : elles viennent d'ailleurs que "
                   "du site (tests, appels directs) — vérifier l'isolation avant de "
                   "conclure quoi que ce soit.")
    else:
        lecture = ("La page s'ouvre <em>et</em> des actions partent : le rapport entre "
                   "les deux nombres est le taux de passage à l'acte, à suivre dans le "
                   "temps plutôt qu'à interpréter sur un point.")
    return (
        '<h3 id="usage-reel">Usage réel de cette page</h3>'
        '<p class="legende">Deux compteurs, parce qu&rsquo;un seul ne distingue pas '
        "« jamais ouvert » de « ouvert, jamais cliqué ». Le sondage automatique de "
        "<code>/api/jobs</code> n'est jamais compté.</p>"
        '<table class="tbl"><thead><tr><th>Mesure</th><th>Depuis</th>'
        "<th>Dernière</th><th>Nombre</th></tr></thead><tbody>"
        f'<tr><td>Pages servies</td><td>{_jour(v["premiere"])}</td>'
        f'<td>{_jour(v["derniere"])}</td><td><b>{v["n"]}</b></td></tr>'
        f'<tr><td>Actions lancées</td><td>{_jour(a["premiere"])}</td>'
        f'<td>{_jour(a["derniere"])}</td><td><b>{a["n"]}</b></td></tr>'
        f'<tr><td>Sessions du serveur observées</td><td>{_jour(f["premiere"])}</td>'
        f'<td>{_jour(f["derniere"])}</td><td><b>{f["sessions"]}</b></td></tr>'
        f"</tbody></table><p class=\"muted\">{lecture}</p>")


MESURE_TOKENS_SCRIPT = os.path.join(ROOT, "scripts", "mesure_tokens.py")


def rafraichir_tokens():
    """Relance la mesure des tokens à chaque scan, au lieu de l'attendre à la main.

    LE GEL QUE ÇA CORRIGE. `tokens.json` datait du 2026-07-31 15:17 quand l'utilisateur
    a signalé, le 2026-09-02, que « les informations du site ne semblent pas à jour » :
    33 jours. Tout le reste de la page était régénéré à chaque passage ; ce fichier-là
    attendait une commande manuelle. Le plus instructif est que la page AFFICHAIT déjà
    son propre diagnostic — l'axe « Mesurer en continu, pas quand on y pense » disait
    mot pour mot que le compte « n'existe que si quelqu'un lance mesure_tokens.py à la
    main ». Un diagnostic publié pendant un mois sans que rien ne l'exécute.

    FAIL-OPEN, et ce n'est pas négociable : ce scan tourne dans un hook `SessionStart`.
    Une mesure qui lève bloquerait l'ouverture de session — on renonce en silence et le
    scan continue avec le tokens.json précédent, périmé mais présent.
    """
    try:
        # On IMPOSE la destination plutôt que de faire confiance au défaut du script :
        # le scan lit `TOKENS_JSON`, il doit donc écrire là et nulle part ailleurs. C'est
        # aussi ce qui rend la relance testable sans toucher à la mesure de production.
        env = dict(os.environ, AGENT_SUPERVISION_TOKENS_JSON=TOKENS_JSON)
        subprocess.run([sys.executable, "-X", "utf8", MESURE_TOKENS_SCRIPT],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, env=env)
    except Exception:   # noqa: BLE001 - fail-open assumé, cf. docstring
        pass


def lire_tokens():
    """Le contenu de tokens.json, {} s'il n'a jamais été généré (fail-open)."""
    try:
        with open(TOKENS_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def axes_amelioration_tokens(d):
    """Les axes d'amélioration, DÉRIVÉS des chiffres — pas une liste de conseils.

    Chacun ne s'affiche que si la donnée le déclenche, et porte le chiffre qui le
    justifie : un axe sans mesure derrière est une opinion, et le hub en a déjà assez.
    """
    axes = []
    total = d.get("total") or {}
    par_jour = d.get("par_jour") or {}
    par_modele = d.get("par_modele") or {}
    if not total:
        return axes

    def facturable(x):
        return (x.get("input_tokens", 0) + x.get("output_tokens", 0)
                + x.get("cache_creation_input_tokens", 0))

    # 1. Fraîcheur de la mesure elle-même — le constat de la revue de consommation
    #    du 2026-07-31 : l'instrument existait, personne ne le lançait.
    genere = str(d.get("genere") or "")[:10]
    if genere:
        axes.append((
            "Mesurer en continu, pas quand on y pense",
            f"Ce tableau date du {genere}. usage.jsonl (étage 1, à chaque session) "
            "enregistre les invocations mais AUCUN token : le compte en tokens n'existe "
            "que si quelqu'un lance scripts/mesure_tokens.py à la main.",
            "Brancher la mesure sur une cadence (hook SessionStart, comme le scan) pour "
            "que la dépense soit surveillée au lieu d'être constatée."))

    # 2. Concentration temporelle : un jour qui pèse anormalement lourd.
    if len(par_jour) >= 3:
        jours = sorted(((j, facturable(v)) for j, v in par_jour.items()),
                       key=lambda kv: -kv[1])
        pire, pire_v = jours[0]
        median = sorted(v for _, v in jours)[len(jours) // 2]
        if median and pire_v > 3 * median:
            axes.append((
                "Une séance pèse autant que plusieurs",
                f"Le {pire} a coûté {_fr(pire_v)} tokens facturables, soit "
                f"{pire_v / median:.1f}× la journée médiane ({_fr(median)}).",
                "Regarder ce qui s'est joué ce jour-là : une exploration non bornée et "
                "un chantier dense laissent la même trace ici, mais pas la même valeur."))

    # 3. Poids du cache relu — le poste le plus gros, et le moins cher.
    relu = total.get("cache_read_input_tokens", 0)
    fact = facturable(total)
    if relu and fact:
        axes.append((
            "Le cache relu domine le volume, pas la facture",
            f"{_fr(relu)} tokens relus en cache contre {_fr(fact)} facturables "
            f"(×{relu / fact:.0f}). Le cache relu ne se facture pas au prix plein.",
            "Ne pas lire ce ratio comme une alerte : c'est le signe que le contexte est "
            "réutilisé. L'alerte serait l'inverse — beaucoup d'écriture de cache pour "
            "peu de relecture."))

    # 4. Concentration par modèle : le structurant doit rester minoritaire.
    if par_modele:
        classement = sorted(((m, facturable(v)) for m, v in par_modele.items()),
                            key=lambda kv: -kv[1])
        total_m = sum(v for _, v in classement) or 1
        gros = [(m, v) for m, v in classement if v]
        if gros:
            tete, tete_v = gros[0]
            axes.append((
                "Le modèle le plus cher fait-il le travail le plus dur ?",
                f"{tete} porte {tete_v / total_m:.0%} du facturable "
                f"({_fr(tete_v)} sur {_fr(total_m)}).",
                "La politique du hub veut le fan-out mécanique en haiku et le structurant "
                "en opus. Un modèle structurant en tête sur du volume mécanique est un "
                "poste à corriger dans les briefs, pas dans la facture."))
        haiku = [v for m, v in classement if "haiku" in m.lower()]
        if haiku and sum(haiku) / total_m < 0.02:
            axes.append((
                "Haiku est prévu par la politique de modèle, mais quasi inutilisé",
                f"Haiku pèse {sum(haiku) / total_m:.1%} du facturable.",
                "Les fan-out mécaniques (inventaires, extractions factuelles) y sont "
                "éligibles : c'est le levier le moins risqué, puisqu'il ne touche ni la "
                "revue ni l'arbitrage."))
    return axes


def render_reponse_du_jour(pil, veille):
    """La réponse à la question qu'on se pose en ouvrant la page.

    Rupture A de `docs/reflexions/approche-disruptive-wiki-2026-07-31.md`, arbitrée le
    2026-07-31. Ce que la mesure avait montré : les 11 onglets recopient
    l'organigramme du dispositif, pas la question d'un lundi matin — et sur 242 jobs
    lancés depuis les boutons, un seul venait d'un humain. Une page que personne
    n'interroge doit commencer par répondre.

    Trois questions, dans cet ordre d'urgence : **qu'est-ce qui a cassé**, **qu'est-ce
    qui attend ma décision**, **qu'est-ce qui a bougé**. Chaque réponse est une phrase
    et un lien vers l'onglet qui la traite — les chiffres du bandeau restent juste en
    dessous, comme preuve.

    Le silence est une information : quand rien n'appelle, on le DIT au lieu de ne
    rien afficher — une absence de message se lit comme un rendu cassé.
    """
    ee = html.escape
    casse, decision, bouge = [], [], []

    # 1. Ce qui a cassé — les projets en alerte, nommés (un chiffre ne se traite pas).
    alertes = pil.get("en_alerte") or []
    if alertes:
        # compute_pilotage construit en_alerte comme une liste de dicts projet,
        # chacun portant "nom" — pas de branche str, elle serait du code mort.
        noms = [a.get("nom") or "?" for a in alertes]
        casse.append(
            f"{'1 projet est' if len(noms) == 1 else str(len(noms)) + ' projets sont'} "
            f"en alerte : <b>{ee(', '.join(noms))}</b>")
    retards = pil.get("retards") or []
    if retards:
        suite = "…" if len(retards) > 2 else ""
        casse.append(f"{len(retards)} cadence(s) en retard : "
                     f"{ee(', '.join(map(str, retards[:2])))}{suite}")

    # 2. Ce qui attend une décision — le seul bloc qui appelle un geste humain.
    nb_f = pil.get("nb_findings") or 0
    if nb_f:
        decision.append(f"<b>{nb_f}</b> finding(s) du diagnostic à arbitrer")
    en_attente = [x for x in (veille.get("entrees") or [])
                  if x.get("statut") in ("nouveau", "etudie")]
    if en_attente:
        decision.append(f"<b>{len(en_attente)}</b> trouvaille(s) de veille à trancher")
    runs = pil.get("runs_a_solder") or []
    if runs:
        decision.append(f"<b>{len(runs)}</b> run(s) à solder")

    # 3. Ce qui a bougé — seulement si le scan précédent existe ET que ça a changé.
    tend = pil.get("tendances")
    if tend:
        for cle, libelle in (("nb_en_alerte", "projets en alerte"),
                             ("nb_findings", "findings"),
                             ("nb_pratiques_ecart", "pratiques en écart")):
            d = (tend.get("deltas") or {}).get(cle)
            if isinstance(d, (int, float)) and d:
                sens = "en plus" if d > 0 else "en moins"
                bouge.append(f"{abs(int(d))} {libelle} {sens}")

    if not (casse or decision or bouge):
        return ('<div class="reponse-jour reponse-calme">'
                "<p><b>Rien ne vous attend.</b> Aucun projet en alerte, aucun finding à "
                "arbitrer, aucune trouvaille en suspens — la flotte est à jour.</p></div>")

    parts = ['<div class="reponse-jour">']
    if casse:
        parts.append('<p class="rj-casse"><span class="rj-quoi">Ce qui a cassé</span> — '
                     + " · ".join(casse)
                     + ' <a href="#" data-goto="projets">voir les projets</a></p>')
    if decision:
        parts.append('<p class="rj-decision"><span class="rj-quoi">Ce qui attend votre '
                     'décision</span> — ' + " · ".join(decision)
                     + ' <a href="#" data-goto="correctifs">traiter</a></p>')
    if bouge:
        parts.append('<p class="rj-bouge"><span class="rj-quoi">Depuis le scan '
                     'précédent</span> — ' + ee(" · ".join(bouge)) + "</p>")
    parts.append("</div>")
    return "\n".join(parts)


def render_ensemble_svg():
    """Le schéma d'ensemble : qui appelle quoi, du geste humain jusqu'aux skills.

    Demande utilisateur du 2026-07-31 — il manquait une vue de comment les pièces
    fonctionnent ENSEMBLE : l'orchestrateur, les salles de table ronde, les
    sous-agents porteurs et les skills.

    SVG inline, sans image externe ni bibliothèque : les nombres sont DÉRIVÉS (agents
    de .claude/agents/, salles et rôles des TOML, playbooks du dossier, skills du
    disque), donc le schéma vieillit avec le dépôt au lieu de mentir. Les couleurs
    passent par les variables CSS, donc il suit le thème clair/sombre.
    """
    ee = html.escape
    agents = lister_sous_agents()
    membres, groupes = party_collectif()
    playbooks = list_md(os.path.join(ROOT, ".claude", "orchestration", "playbooks"),
                        exclude=("FORMAT.md",))
    skills_dir = os.path.join(ROOT, ".claude", "skills")
    try:
        toutes = [d for d in os.listdir(skills_dir)
                  if os.path.isfile(os.path.join(skills_dir, d, "SKILL.md"))]
    except OSError:
        toutes = []
    n_bmad = len([d for d in toutes if d.startswith("bmad-")])
    n_maison = len(toutes) - n_bmad
    porteurs = [a["nom"] for a in agents if a["nom"].startswith("bmad-")]
    salles_bornees = [g for g in groupes if g.get("members")]

    def boite(x, y, w, h, titre, sous, classe):
        return (f'<g class="sch-{classe}">'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>'
                f'<text class="sch-t" x="{x + w / 2}" y="{y + 21}">{ee(titre)}</text>'
                + "".join(
                    f'<text class="sch-s" x="{x + w / 2}" y="{y + 39 + 15 * i}">{ee(l)}</text>'
                    for i, l in enumerate(sous))
                + "</g>")

    def fleche(x1, y1, x2, y2, libelle="", dx=0):
        mid_y = (y1 + y2) / 2
        t = (f'<text class="sch-f" x="{(x1 + x2) / 2 + dx}" y="{mid_y - 3}">{ee(libelle)}</text>'
             if libelle else "")
        return (f'<line class="sch-l" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'marker-end="url(#fl)"/>{t}')

    p = ['<svg viewBox="0 0 980 560" class="schema-ensemble" role="img" '
         'aria-label="Schéma : de la demande humaine aux skills, via l\'orchestrateur, '
         'les salles de table ronde et les sous-agents porteurs">',
         '<defs><marker id="fl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         'markerHeight="6" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" class="sch-m"/></marker></defs>']

    # Étage 1 — l'humain
    p.append(boite(390, 10, 200, 52, "L'humain", ["demande · arbitre · valide"], "humain"))
    p.append(fleche(490, 62, 490, 96, ""))

    # Étage 2 — l'orchestrateur
    p.append(boite(330, 96, 320, 62, "agent-orchestrator",
                   ["qualifie la demande, compose le plan,",
                    f"instancie un playbook ({len(playbooks)} disponibles)"], "orch"))

    # Étage 3 — les trois voies
    p.append(fleche(410, 158, 190, 210, "délibérer", -30))
    p.append(fleche(490, 158, 490, 210, "exécuter"))
    p.append(fleche(570, 158, 800, 210, "mesurer", 30))

    p.append(boite(40, 210, 300, 76, "Les salles (table ronde)",
                   [f"{len(salles_bornees)} salles bornées + 1 open-cast",
                    f"{len(membres)} voix au vivier",
                    "délibèrent — ne modifient aucun fichier"], "salle"))
    p.append(boite(370, 210, 240, 76, "Les sous-agents",
                   [f"{len(agents)} porteurs, contexte vierge",
                    f"dont {len(porteurs)} porteurs BMAD",
                    "rendent un résultat, pas un message"], "agent"))
    p.append(boite(640, 210, 300, 76, "Le superviseur",
                   ["étage 1 : scan déterministe (0 token)",
                    "étage 2 : agent-supervisor (findings)",
                    "propose — n'applique jamais"], "sup"))

    # Étage 4 — les skills
    p.append(fleche(190, 286, 420, 340, ""))
    p.append(fleche(490, 286, 490, 340, "invoque"))
    p.append(fleche(790, 286, 560, 340, ""))
    p.append(boite(330, 340, 320, 62, "Les skills",
                   [f"{n_bmad} BMAD + {n_maison} maison",
                    "routées par besoin détecté"], "skill"))

    # Retour — la boucle
    p.append(fleche(650, 371, 900, 371, ""))
    p.append('<path class="sch-l" d="M 900 371 L 940 371 L 940 470 L 490 470 L 490 440" '
             'fill="none" marker-end="url(#fl)"/>')
    p.append('<text class="sch-f" x="700" y="364">produit un livrable</text>')
    p.append(boite(330, 440, 320, 62, "Le journal et le wiki",
                   ["runs.jsonl · arbitrages.json · wiki.html",
                    "la trace, relue au prochain tour"], "trace"))
    p.append(fleche(490, 502, 490, 534, ""))
    p.append('<text class="sch-f" x="490" y="550">…et l\'humain arbitre de nouveau</text>')
    p.append("</svg>")
    return "\n".join(p)


def render_salles_utilisables_html():
    """Le mode d'emploi opérationnel des salles : quoi taper, et quand.

    Complète le schéma d'ensemble (demande utilisateur du 2026-07-31 : « approfondir
    le schéma avec les salles utilisables et les commandes à lancer dans le prompt »).
    Les salles et leurs membres sont DÉRIVÉS des TOML ; les situations viennent de
    PARTY_SITUATIONS, dont chaque cible est vérifiée contre le TOML réel par les tests.
    """
    ee = html.escape
    membres, groupes = party_collectif()
    if not groupes:
        return ""
    par_code = {m["code"]: m for m in membres}
    for m in membres:
        for cle in (m["code"].lower(),
                    re.sub(r"^bmad-(agent-)?", "", m["code"]).lower(),
                    (m.get("name") or "").lower()):
            if cle:
                par_code.setdefault(cle, m)
    situations = {}
    for sit, salle, pourquoi, _savoir in PARTY_SITUATIONS:
        situations.setdefault(salle, (sit, pourquoi))

    parts = ['<h3 id="salles-commandes">Les salles utilisables, et quoi taper</h3>']
    parts.append(
        '<p class="legende"><b>Trois façons de convoquer une salle, au choix.</b> '
        "<strong>1. La demander en clair</strong> — « fais débattre une salle sur… », "
        "ou n'importe quelle demande qui pose un CHOIX à instruire plutôt qu'un travail "
        "à exécuter : l'orchestrateur reconnaît la situation et convoque la salle "
        "lui-même, en annonçant laquelle et pourquoi (câblé le 2026-08-31 — avant cette "
        "date il ne savait pas que ces salles existaient, et n'en ouvrait aucune). "
        "<strong>2. Le bouton « Déclencher »</strong> présent sur les onglets concernés, "
        "qui lance la même chose sans terminal. <strong>3. La commande</strong> ci-dessous, "
        "en tapant le sujet juste après. Le mode par défaut est <code>session</code> — "
        "une seule voix qui joue tout le monde, donc aucun débat réel : "
        "<strong>ouvrir en <code>--mode subagent</code> quand le désaccord compte</strong>, "
        "chaque persona pense alors dans son propre contexte.</p>")

    # Le déroulé d'une séance — le « comment ça marche » que le casting seul ne dit pas.
    parts.append(
        '<div class="party-deroule"><b>Comment se déroule une table ronde.</b> '
        "<strong>1. Convoquer</strong> — la commande ouvre la salle ; chaque voix reçoit "
        "l'objectif, son persona et toute la conversation, à chaque tour. "
        "<strong>2. Délibérer, en deux tours au moins</strong> — tour 1 : positions "
        "indépendantes, les voix ne se sont pas vues ; tour 2 : CONFRONTATION, chaque "
        "voix reçoit les répliques des autres et attaque, concède ou affine — un seul "
        "tour de paroles parallèles est un sondage, pas un débat. L'humain est DANS la "
        "salle : il relance, tranche un point, invite une voix (« fais venir Winston ») "
        "ou change de salle en cours de route. "
        "<strong>3. Conclure</strong> — quand l'humain dit stop, la salle rend ses "
        "conclusions : points tranchés, désaccords restants (ce sont eux qui ont de la "
        "valeur), et qui-fait-quoi. "
        "<strong>4. Transmettre</strong> — la sortie part à son destinataire (encadré "
        "de chaque carte) ; si la salle a une mémoire, la séance y laisse ses moments "
        "clés pour la prochaine fois.</div>")

    parts.append('<div class="salles-grille">')
    for g in groupes:
        codes = g.get("members") or []
        voix = []
        for c in codes:
            m = par_code.get(c)
            if m:
                titre = (m.get("title") or "").strip()
                nom = f"{m.get('icon', '')} <b>{ee(m.get('name') or c)}</b>".strip()
                voix.append(f"{nom}<span class=\"muted\"> — {ee(titre)}</span>" if titre else nom)
            else:
                voix.append(ee(c))
        sit = situations.get(g["id"])
        dest = PARTY_DESTINATAIRES.get(g["id"])
        memoire = g.get("memory")
        parts.append('<div class="salle-carte">')
        parts.append(f'<h4>{ee(g.get("name") or g["id"])}'
                     + (' <span class="muted">🧠 mémoire</span>' if memoire else "")
                     + "</h4>")
        if sit:
            parts.append(f'<p class="salle-quand">{ee(sit[0])}</p>')
        parts.append(
            '<p class="salle-cmd"><code>/bmad-party-mode --party '
            f'{ee(g["id"])} --mode subagent</code>'
            '<span class="salle-sujet">puis, sur la ligne suivante, <b>le sujet</b> — '
            'la commande seule ouvre la salle sur rien.</span></p>')
        if voix:
            parts.append('<p class="salle-voix">Autour de la table : '
                         + " · ".join(voix) + "</p>")
        else:
            parts.append('<p class="salle-voix muted">Open-cast : la salle génère ses '
                         "voix à la volée selon le sujet — elles sont jetables.</p>")
        parts.append(
            '<p class="salle-voix muted">+ invités selon le sujet : le relais du projet '
            "visé, Winston (archi), Sally (UX), ou toute voix du vivier — « fais venir "
            "X » en cours de séance suffit.</p>")
        if dest:
            parts.append(
                f'<p class="salle-dest">→ <b>Le travail part à : {ee(dest[0])}.</b> '
                f'<span class="muted">{ee(dest[1])}.</span></p>')
        if sit:
            parts.append(f'<p class="muted salle-pourquoi">{ee(sit[1])}</p>')
        parts.append("</div>")
    parts.append("</div>")
    parts.append(
        '<p class="legende">Une salle <strong>délibère</strong> : sa sortie est un compte '
        "rendu et une partition du travail, jamais un diff. L'exécution qui suit est un "
        "fan-out orchestré normal, avec ses vérifications et son journal — c'est ce qui "
        "empêche une table ronde d'appliquer ses propres conclusions.</p>")
    return "\n".join(parts)


def render_tokens_html():
    """Onglet Tokens : piloter la consommation (demande utilisateur 2026-07-31,
    motivée par la salle « revue-consommation » qui a constaté que la dépense était
    constatée après coup, jamais suivie).

    Formes choisies avant les couleurs, selon le job de la donnée : des tuiles pour
    les totaux (une magnitude seule n'est pas un graphique), des barres empilées pour
    la composition du coût par jour (mêmes unités, sous-parties d'un tout — jamais
    deux axes), des barres horizontales triées pour le classement par modèle (une
    magnitude, donc UNE couleur : la teinte n'y porterait aucune information)."""
    ee = html.escape
    d = lire_tokens()
    if not d.get("total"):
        return ('<h2>Tokens — piloter la consommation</h2>'
                '<p class="legende">Aucune mesure disponible. Lancer '
                "<code>py scripts/mesure_tokens.py</code> (0 token LLM : le script lit "
                "les transcripts locaux) pour produire "
                "<code>.claude/supervision/tokens.json</code>.</p>")

    total = d["total"]
    par_jour = d.get("par_jour") or {}
    par_modele = d.get("par_modele") or {}

    def facturable(x):
        return (x.get("input_tokens", 0) + x.get("output_tokens", 0)
                + x.get("cache_creation_input_tokens", 0))

    parts = ["<h2>Tokens — piloter la consommation</h2>"]
    parts.append(
        '<p class="legende">Mesure <strong>déterministe</strong>, à 0 token LLM : '
        "<code>scripts/mesure_tokens.py</code> agrège le bloc <code>usage</code> des "
        f"transcripts locaux ({_fr(d.get('fichiers_parcourus', 0))} fichiers, "
        f"{_fr(total.get('messages', 0))} messages, "
        + (f"fenêtre {ee(str(d['fenetre_jours']))} j" if d.get("fenetre_jours")
           else f"{_fr(len(par_jour))} jours couverts")
        + f"). Généré le {ee(str(d.get('genere') or '?')[:16])}.</p>"
        # CE TOTAL N'EST PAS CUMULATIF, et le dire est la moitié de la mesure. Claude
        # Code PURGE les transcripts locaux : la base est passée de 124 fichiers /
        # 8 jours (2026-07-31) à 10 fichiers / 4 jours (2026-09-02), et le facturable
        # avec elle, de 81,9 M à 22,8 M — soit -72 % sans qu'aucune consommation ait
        # baissé. La légende disait « sur tout l'historique disponible » : vrai au mot
        # près, trompeur en pratique, puisque « disponible » rétrécit. Un lecteur qui
        # compare deux relevés sans connaître leurs bases conclut de travers.
        '<p class="legende alerte-mesure">⚠ <strong>Ce total n\'est pas cumulatif.</strong> '
        "Il ne compte que les transcripts encore présents sur le disque, et Claude Code "
        "les <strong>purge</strong> : la base est éphémère et rétrécit. Une baisse d\'un "
        "relevé à l\'autre peut n\'être qu\'une base plus petite — comparer les totaux "
        "sans comparer d\'abord le nombre de fichiers et de jours ci-dessus n\'a pas de "
        "sens. Mesuré : 124 fichiers / 8 jours le 2026-07-31, 10 fichiers / 4 jours le "
        "2026-09-02.</p>")

    # --- Tuiles : une magnitude seule ne mérite pas un graphique ---------------
    fact_total = facturable(total)
    tuiles = [
        ("Facturable", fact_total, "entrée + sortie + écriture de cache"),
        ("Sortie", total.get("output_tokens", 0), "ce que les modèles ont écrit"),
        ("Écriture de cache", total.get("cache_creation_input_tokens", 0),
         "payé une fois, relu ensuite"),
        ("Cache relu", total.get("cache_read_input_tokens", 0),
         "hors facturation au prix plein"),
    ]
    parts.append('<div class="actions-grille">')
    for titre, valeur, sous in tuiles:
        parts.append(
            '<div class="action-carte carte-lecture">'
            f"<h4>{ee(titre)}</h4>"
            f'<p style="font-size:1.6rem;font-weight:700;line-height:1.2">{_fr(valeur)}</p>'
            f'<p class="muted">{ee(sous)}</p></div>')
    parts.append("</div>")

    # --- Composition du coût par jour : barres empilées ------------------------
    if par_jour:
        jours = sorted(par_jour.items())
        maxi = max(facturable(v) for _, v in jours) or 1
        parts.append("<h3>Ce que chaque journée a coûté</h3>")
        parts.append(
            '<p class="legende">Les trois composantes du facturable, à la même '
            "échelle : elles s'additionnent, donc elles s'empilent. Le cache relu en "
            "est absent — il ne se facture pas au prix plein et écraserait le reste.</p>")
        parts.append('<div class="viz-legende">')
        for _, libelle, couleur in COUT_SERIES:
            parts.append(
                f'<span class="viz-cle"><span class="viz-pastille" '
                f'style="background:{couleur}"></span>{ee(libelle)}</span>')
        parts.append("</div>")
        parts.append('<div class="viz-barres">')
        for jour, v in jours:
            f = facturable(v)
            parts.append('<div class="viz-ligne">')
            parts.append(f'<div class="viz-etiq">{ee(jour[5:])}</div>')
            parts.append('<div class="viz-piste">')
            for cle, libelle, couleur in COUT_SERIES:
                val = v.get(cle, 0)
                if not val:
                    continue
                largeur = 100 * val / maxi
                parts.append(
                    f'<div class="viz-seg" style="width:{largeur:.3f}%;background:{couleur}" '
                    f'title="{ee(jour)} — {ee(libelle)} : {_fr(val)} tokens"></div>')
            parts.append("</div>")
            parts.append(f'<div class="viz-val">{_fr(f)}</div>')
            parts.append("</div>")
        parts.append("</div>")

    # --- Classement par modèle : une magnitude, donc une seule couleur ---------
    if par_modele:
        classement = sorted(((m, facturable(v), v) for m, v in par_modele.items()),
                            key=lambda t: -t[1])
        classement = [t for t in classement if t[1]]
        maxi = classement[0][1] if classement else 1
        parts.append("<h3>Quels modèles portent la dépense</h3>")
        parts.append(
            '<p class="legende">Une seule mesure comparée entre modèles : la couleur '
            "n'y porterait aucune information, seule la longueur compte. Rappel de la "
            "politique du hub — fan-out mécanique en haiku, dev en sonnet, structurant "
            "en opus.</p>")
        parts.append('<div class="viz-barres">')
        for modele, f, v in classement:
            parts.append('<div class="viz-ligne viz-ligne-large">')
            parts.append(f'<div class="viz-etiq">{ee(modele)}</div>')
            parts.append('<div class="viz-piste">')
            parts.append(
                f'<div class="viz-seg" style="width:{100 * f / maxi:.3f}%;'
                f'background:var(--accent)" title="{ee(modele)} : {_fr(f)} facturables, '
                f'{_fr(v.get("output_tokens", 0))} de sortie"></div>')
            parts.append("</div>")
            parts.append(f'<div class="viz-val">{_fr(f)}</div>')
            parts.append("</div>")
        parts.append("</div>")

    # --- Vue tableau : exigée par le WARN de contraste du validateur -----------
    if par_jour:
        parts.append("<h3>Les mêmes chiffres, en tableau</h3>")
        parts.append(
            '<p class="legende">La vue lisible sans couleur — une palette dont un ton '
            "passe sous 3:1 de contraste n'est acceptable qu'accompagnée des valeurs "
            "écrites.</p>")
        parts.append('<table class="tbl"><thead><tr><th>Jour</th><th>Entrée</th>'
                     "<th>Sortie</th><th>Écriture de cache</th><th>Facturable</th>"
                     "<th>Cache relu</th></tr></thead><tbody>")
        for jour, v in sorted(par_jour.items()):
            parts.append(
                f"<tr><td>{ee(jour)}</td>"
                f"<td>{_fr(v.get('input_tokens', 0))}</td>"
                f"<td>{_fr(v.get('output_tokens', 0))}</td>"
                f"<td>{_fr(v.get('cache_creation_input_tokens', 0))}</td>"
                f"<td><b>{_fr(facturable(v))}</b></td>"
                f'<td class="muted">{_fr(v.get("cache_read_input_tokens", 0))}</td></tr>')
        parts.append("</tbody></table>")

    # --- Axes d'amélioration, dérivés des chiffres -----------------------------
    axes = axes_amelioration_tokens(d)
    if axes:
        parts.append("<h3>Axes d'amélioration</h3>")
        parts.append(
            '<p class="legende">Dérivés des chiffres ci-dessus : chacun ne s\'affiche '
            "que si la mesure le déclenche, et porte le chiffre qui le justifie. Un axe "
            "sans mesure derrière est une opinion.</p>")
        parts.append('<div class="actions-grille">')
        for titre, constat, action in axes:
            parts.append(
                '<div class="action-carte carte-lecture">'
                f"<h4>{ee(titre)}</h4>"
                f"<p>{ee(constat)}</p>"
                f'<p class="muted">→ {ee(action)}</p></div>')
        parts.append("</div>")
    return "\n".join(parts)


def orienter_pane(html_pane):
    """Ajoute à un onglet une couche d'orientation DÉRIVÉE de ses titres réels.

    Demande utilisateur du 2026-08-31 (« vision plus claire des infos du tutoriel &
    dispositif ») + constat de la salle atelier-idées : les deux onglets les plus
    lourds s'ouvraient sans sommaire ni ancres — « rien ne dit où ça pèse lourd, il
    découvre les 113 Ko en tombant dedans ».

    Le sommaire est construit à partir des <h3> du pane rendu, jamais écrit à la
    main : un bloc ajouté demain y figure sans qu'on y pense, un bloc supprimé en
    disparaît — même invariant que le schéma de la party (dérivé des TOML). Un id
    déjà posé sur un h3 (ex. `id="party"`, visé par des liens existants) n'est
    JAMAIS renommé ; les autres reçoivent un slug de leur titre."""
    import unicodedata

    def _slug(titre):
        txt = re.sub(r"<[^>]+>", "", titre)
        txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
        txt = re.sub(r"[^a-z0-9]+", "-", txt.lower()).strip("-")
        return txt or "bloc"

    entrees, vus = [], set()

    def _equiper(m):
        attrs, titre = m.group(1), m.group(2)
        deja = re.search(r'id="([^"]+)"', attrs)
        if deja:
            ident = deja.group(1)
        else:
            ident = base = _slug(titre)
            n = 2
            while ident in vus:
                ident, n = f"{base}-{n}", n + 1
            attrs += f' id="{ident}"'
        vus.add(ident)
        label = html.unescape(re.sub(r"<[^>]+>", "", titre)).strip()
        entrees.append((ident, label))
        return f"<h3{attrs}>{titre}</h3>"

    equipe = re.sub(r"<h3([^>]*)>(.*?)</h3>", _equiper, html_pane, flags=re.S)
    if not entrees:
        return html_pane
    nav = ('<nav class="onglet-sommaire" aria-label="Dans cet onglet">'
           + "".join(f'<a href="#{html.escape(i)}">{html.escape(l)}</a>'
                     for i, l in entrees)
           + "</nav>")
    tete, sep, corps = equipe.partition("</h2>")
    return tete + sep + nav + corps if sep else nav + equipe


def render_tutoriel_html():
    """Onglet Tutoriel : glossaire des concepts du dispositif (demande
    utilisateur 2026-07-29). Contenu statique curaté — les exemples citent des
    objets réels de la flotte pour que la définition reste vérifiable."""
    parts = ['<h2>Tutoriel — les concepts du dispositif</h2>']
    parts.append(
        '<p class="legende">Le dispositif tient en une boucle : les <strong>hooks</strong> '
        "mesurent à chaque session (étage déterministe, 0 token), le <strong>superviseur"
        "</strong> qualifie et propose des <strong>findings</strong> prouvés, "
        "l'<strong>humain arbitre</strong>, l'<strong>orchestrateur</strong> applique la "
        "version validée via un <strong>playbook</strong>, le <strong>journal</strong> et le "
        "<strong>wiki</strong> gardent la trace. Chaque terme ci-dessous, avec son incarnation "
        "réelle dans ce dépôt.</p>")
    for famille, concepts in TUTORIEL_CONCEPTS:
        parts.append(f"<h3>{html.escape(famille)}</h3>")
        parts.append('<div class="actions-grille">')
        for terme, definition, exemple in concepts:
            parts.append(
                '<div class="action-carte carte-lecture">'
                f"<h4>{html.escape(terme)}</h4>"
                f"<p>{html.escape(definition)}</p>"
                f'<p class="muted">Ici : {html.escape(exemple)}</p>'
                "</div>")
        parts.append("</div>")
    schema = render_party_html()
    if schema:
        # Replié, pas retiré : les 9 salles vivent déjà en CARTES ACTIONNABLES dans
        # l'onglet Dispositif (commande, casting, destinataire). Le Tutoriel garde
        # les concepts ; le casting complet reste là pour qui le déplie — dupliqué
        # ouvert des deux côtés, c'était deux murs pour une même information
        # (constat utilisateur du 2026-08-31).
        parts.append(
            "<details><summary>Le schéma complet de la table ronde — casting des "
            "salles et rôles (les commandes pour les convoquer sont dans l'onglet "
            "🧩 Dispositif)</summary>" + schema + "</details>")
    return "\n".join(parts)


def render_catalogue_html(e, existants):
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
        for c in craft_effectives(existants))
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


def render_html(projects, veille, now, pilotage, now_dt, ancien_html=None):
    e = html.escape
    pil = pilotage
    parts = [HTML_HEAD, "<h1>Supervision multi-projets</h1>"]
    parts.append(
        f'<p class="muted">Généré le {e(now)} par scripts/scan_projets.py — ne pas éditer à la main.</p>'
    )
    # ---- La réponse du jour, AVANT la navigation (rupture A, seconde moitié) ---
    # Arbitrée le 2026-07-31 pour son contenu, complétée le 2026-09-01 pour sa PLACE.
    # Le bloc existait depuis juillet mais vivait DANS le panneau « Pilotage » : il
    # arrivait donc après la barre d'onglets, et disparaissait dès qu'on ouvrait l'un
    # des dix autres. La page continuait d'ouvrir sur l'organigramme du dispositif.
    #
    # La salle demandait que « les 11 onglets se subordonnent » et que le reste
    # devienne « une archive consultable, pas une façade à parcourir ». Mesuré le
    # 2026-09-01 contre sa propre mesure du 2026-07-31 : onglets 11 -> 11, page
    # 278 Ko -> 458 Ko, 26 230 mots -> 49 345. La page avait presque doublé pendant
    # qu'on demandait qu'elle se subordonne.
    #
    # Subordonner n'est pas supprimer : on ne retire aucun onglet (ce serait une autre
    # décision, que personne n'a arbitrée). On cesse de les présenter en premier, et la
    # réponse reste lisible quel que soit l'onglet ouvert.
    parts.append(render_reponse_du_jour(pil, veille))

    # ---- Navigation par onglets (thématiques) --------------------------------
    # role=tablist/tab/tabpanel + aria-selected/aria-controls (finding
    # wiki:accessibilite-onglets, diagnostic 2026-07-29) : les 9 boutons n'avaient
    # jusqu'ici que la classe CSS "actif", invisible à un lecteur d'écran. La bascule
    # de aria-selected reste faite en JS (docs/wiki_app.js, fonction activer()).
    parts.append(
        '<nav class="tabs" role="tablist">'
        '<button id="tab-pilotage" data-pane="pilotage" class="actif" role="tab" '
        'aria-selected="true" aria-controls="pane-pilotage">🎛 Pilotage</button>'
        '<button id="tab-projets" data-pane="projets" role="tab" '
        'aria-selected="false" aria-controls="pane-projets">📦 Projets</button>'
        '<button id="tab-pratiques" data-pane="pratiques" role="tab" '
        'aria-selected="false" aria-controls="pane-pratiques">🧭 Pratiques &amp; risques</button>'
        '<button id="tab-veille" data-pane="veille" role="tab" '
        'aria-selected="false" aria-controls="pane-veille">🔭 Veille</button>'
        '<button id="tab-deploiement" data-pane="deploiement" role="tab" '
        'aria-selected="false" aria-controls="pane-deploiement">🚀 Déploiement</button>'
        '<button id="tab-actions" data-pane="actions" role="tab" '
        'aria-selected="false" aria-controls="pane-actions">⚡ Analyser</button>'
        '<button id="tab-correctifs" data-pane="correctifs" role="tab" '
        'aria-selected="false" aria-controls="pane-correctifs">🩹 Arbitrer</button>'
        '<button id="tab-exports" data-pane="exports" role="tab" '
        'aria-selected="false" aria-controls="pane-exports">📤 Exports</button>'
        '<button id="tab-tokens" data-pane="tokens" role="tab" '
        'aria-selected="false" aria-controls="pane-tokens">📊 Tokens</button>'
        '<button id="tab-tutoriel" data-pane="tutoriel" role="tab" '
        'aria-selected="false" aria-controls="pane-tutoriel">📚 Tutoriel</button>'
        '<button id="tab-dispositif" data-pane="dispositif" role="tab" '
        'aria-selected="false" aria-controls="pane-dispositif">🧩 Dispositif</button>'
        "</nav>")
    parts.append('<section class="pane actif" id="pane-pilotage" role="tabpanel" '
                 'aria-labelledby="tab-pilotage" tabindex="0">')

    # ---- Poste de pilotage ---------------------------------------------------
    parts.append('<div class="pilotage"><div class="chiffres">')
    # Une tuile non nulle est un appel à décision : elle doit se voir (revue UX
    # 2026-07-29 — « 1 en alerte » avait exactement le style d'une tuile à 0).
    tend = pil.get("tendances")
    deltas = tend["deltas"] if tend else {}
    for valeur, libelle, cle_delta in (
        (pil["nb_projets"], "projets", None),
        (len(pil["en_alerte"]), "en alerte", "nb_en_alerte"),
        (pil["nb_pratiques_ecart"], "pratiques en écart", "nb_pratiques_ecart"),
        (pil["nb_findings"], "findings ouverts", "nb_findings"),
        (len(pil["runs_a_solder"]), "runs à solder", "nb_runs_a_solder"),
        (len(pil["retards"]), "retards de cadence", "nb_retards"),
    ):
        classe = "chiffre alerte" if (valeur and libelle != "projets") else "chiffre"
        # Tendance vs le scan précédent (incrément 5 de la réflexion 2026-07-23,
        # finding wiki:tendances-wiki 2026-07-30) : la flèche compte plus que le
        # chiffre — absente si aucun historique ou si rien n'a changé.
        delta_html = rendu_delta(deltas.get(cle_delta)) if cle_delta else ""
        parts.append(f'<div class="{classe}"><b>{valeur}</b>{delta_html}<br><span>{e(libelle)}</span></div>')
    parts.append("</div>")
    if tend and tend["transitions"]:
        parts.append(
            '<p class="tendance-transitions">Depuis le scan précédent : '
            + ", ".join(f'<b>{e(n)}</b> {ALERT_MD[a]} → {ALERT_MD[ap]}'
                        for n, a, ap in tend["transitions"])
            + "</p>")
    decisions = []
    for r in pil["runs_a_solder"]:
        marque = " ⚠" if r["en_retard"] else ""
        decisions.append(
            f'<li class="solder">[{e(r["projet"])}] run à solder ({e(r["age"])}{marque}) — '
            f"{e(r['demande'])}</li>"
        )
    # Les écarts de pratiques SONT des décisions en attente : les omettre faisait
    # afficher « système sain » pendant que l'onglet Actions correctives en
    # listait 18 sur 5 projets (P1 de la revue UX, vérifié sur la page livrée).
    # Pratiques et findings restent NOMMÉS SÉPARÉMENT : les additionner sous
    # « pratique(s) en écart » contredisait les pastilles vertes de l'onglet
    # Pratiques (VScode5 : 9 dimensions vertes, 5 findings — annoncé « 5
    # pratiques en écart »).
    for r in pil["ecarts"]:
        pastille = "🔴" if r["n_critique"] else "🟠"
        decisions.append(
            f'<li class="ecart">{pastille} [{e(r["projet"])}] '
            f'{e(libelle_ecarts(r["n_pratiques"], r["n_findings"]))} — à arbitrer '
            "dans l'onglet <b>Actions correctives</b></li>")
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
    parts.append("<h2>Cadences et hygiène git</h2>")
    parts.append("<table><tr><th>Projet</th><th>Scan étage 1</th>"
                 "<th>Diagnostic étage 2</th><th>Dernier commit</th>"
                 "<th>Arbre de travail</th><th>Branches</th></tr>")
    etats_git = {p["nom"]: (p.get("git_etat") or {}) for p in projects}
    for c in pil["cadences"]:
        def cell(pair):
            d, perime = pair
            cls = "cadence-perime" if perime else "cadence-ok"
            return f'<span class="{cls}">{e(age_str(d, now_dt))}</span>'
        g = etats_git.get(c["projet"], {})
        n, br = g.get("non_commite"), g.get("branches")
        arbre = cellule_arbre(n, g.get("doyen_jours"))
        # Trunk-based (DORA) : au-delà de 3 branches actives, le critère décroche.
        bcell = ("?" if br is None else
                 f"{br}" if br < 3 else f"<span class='cadence-perime'>{br}</span>")
        parts.append(
            f"<tr><td>{e(c['projet'])}</td><td>{cell(c['scan'])}</td>"
            f"<td>{cell(c['diagnostic'])}</td><td>{cell(c['commit'])}</td>"
            f"<td>{arbre}</td><td>{bcell}</td></tr>"
        )
    parts.append("</table>")
    parts.append(
        '<p class="muted">Arbre de travail et branches : mesurés par <code>git status '
        "--porcelain</code> et <code>git branch</code> sur chaque dépôt (0 token, ajouté "
        "le 2026-07-30). Ils ferment deux critères du référentiel qui étaient annoncés "
        "sans être mesurés — la dette non commitée ne l'était que sur le hub, et le "
        "trunk-based pas du tout. Un arbre sale n'est pas une faute : c'est le risque R2 "
        "à connaître AVANT de committer sur un dépôt de la flotte. Le <b>doyen</b> "
        "(mtime du plus vieux fichier non commité, ajouté le 2026-08-31) sépare la "
        "séance en cours de la dette : 39 jours mesurés sur la flotte quand personne "
        "ne le voyait.</p>")
    veille_d, veille_perimee = pil["veille"]
    cls = "cadence-perime" if veille_perimee else "cadence-ok"
    parts.append(
        f'<p class="muted">Veille agentic : <span class="{cls}">'
        f"{e(age_str(veille_d, now_dt))}</span> (cadence {CADENCE_VEILLE_J} j). "
        f"Seuils : scan {CADENCE_SCAN_J} j · diagnostic {CADENCE_DIAGNOSTIC_J} j · "
        f"commit {CADENCE_COMMIT_J} j · run à solder {RUN_A_SOLDER_H} h.</p>"
    )

    # ---- Bloc agents (rempli par scan_transcripts.py, marqueurs préservés) ---
    # Le bloc injecté porte déjà son propre titre : n'émettre le nôtre que tant
    # qu'il est absent (sinon la page affiche deux fois « Supervision des agents »).
    bloc_agents = bloc_agents_html(ancien_html)
    if "<h2>" not in bloc_agents:
        parts.append('<h2>Supervision des agents</h2>')
    parts.append(bloc_agents)

    # ---- Section 1 : supervision des projets --------------------------------
    parts.append('</section><section class="pane" id="pane-projets" role="tabpanel" '
                 'aria-labelledby="tab-projets" tabindex="0">')
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
    parts.append('</section><section class="pane" id="pane-pratiques" role="tabpanel" '
                 'aria-labelledby="tab-pratiques" tabindex="0">')
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
    parts.append(render_catalogue_html(e, [p for p in projects if p["existe"]]))
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

    parts.append(render_divergence_html(e, matrice_divergence_pptx_deck(existants)))

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
            attr, lien = rendu_detail_borne(e, syn, ancre_synthese(p["nom"], key))
            parts.append(
                f'<td><span class="lvl">{PASTILLE.get(d.get("niveau"))} '
                f'{e(d.get("niveau", "?"))}</span>'
                + (f'<small{attr}>{e(tronque(syn, 70))}{lien}</small>'
                   if syn else "")
                + "</td>"
            )
        parts.append(
            f'<td class="date-audit">{e(str(audit.get("date", "?")))}</td></tr>')
    parts.append("</table>")
    parts.append('<p class="legende">Lancer un audit : skill <code>audit-technique</code> '
                 "sur le projet cible (robustesse, performance, risque technique, "
                 "failles de sécurité).</p></div>")

    # ---- Section 3 : veille agentic -----------------------------------------
    parts.append('</section><section class="pane" id="pane-veille" role="tabpanel" '
                 'aria-labelledby="tab-veille" tabindex="0">')
    parts.append("<h2>3. Veille agentic</h2>")
    if veille["derniere_veille"]:
        # Deux âges, pas un. Une veille fraîche dont les trouvailles dorment depuis
        # huit jours ressemble à un dispositif qui tourne — c'est un dispositif qui
        # paie pour produire des propositions que personne n'arbitre (finding
        # `veille:trouvailles-dormantes`, diagnostic du 2026-07-31). L'âge de la
        # doyenne rend ce pourrissement visible à côté de la fraîcheur.
        # Deux attentes distinctes, deux messages distincts : « personne ne l'a
        # regardée » accuse le dispositif, « instruite, en attente de décision »
        # renvoie la balle à l'humain. Les confondre rendait le signal inactionnable.
        jamais_vue = age_doyenne_trouvaille(veille, statuts=("nouveau",))
        instruite = age_doyenne_trouvaille(veille, statuts=("etudie",))
        suffixe = ""
        if jamais_vue:
            jours, titre = jamais_vue
            alerte = " ⚠️" if jours >= 7 else ""
            suffixe = (f' · <b>jamais instruite depuis {jours} j{alerte}</b> '
                       f'<span class="muted">({e(tronque(titre, 55))})</span>')
        elif instruite:
            jours, titre = instruite
            suffixe = (f' · <b>{jours} j</b> que la doyenne trouvaille attend votre '
                       f'décision <span class="muted">({e(tronque(titre, 55))})</span>')
        parts.append(
            f'<p class="muted">Dernière veille : {e(str(veille["derniere_veille"]))} — '
            "skill <code>veille-agentic</code> (cadence 3 jours, déclenchable "
            f"manuellement){suffixe}.</p>"
        )
    else:
        parts.append(
            '<p class="muted">Aucune veille enregistrée — lancer la skill '
            "<code>veille-agentic</code>.</p>"
        )
    # Judas compté (2026-08-31) : plus de boutons d'action ici — la veille part à
    # sa cadence ou dans la conversation, et les trouvailles à trancher portent
    # leurs boutons Adopter/Écarter dans l'onglet Actions, posés sur l'objet même.
    parts.append(
        '<p class="muted">La veille se lance à sa cadence (hook SessionStart, '
        "3 jours) ou à la demande dans la conversation — plus de bouton ici "
        "(judas compté, 2026-08-31). Les trouvailles en attente portent leurs "
        "boutons <b>Adopter / Écarter</b> dans l'onglet <b>⚡ Actions</b>.</p>")
    parts.append("<p>" + bouton_party(
        "veille",
        "Que retenir des trouvailles de veille en attente, et qu'est-ce qui est "
        "déjà satisfait ?", libelle="🗣️ Déclencher") + "</p>")

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
    parts.append('</section><section class="pane" id="pane-deploiement" role="tabpanel" '
                 'aria-labelledby="tab-deploiement" tabindex="0">')
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
    # Judas compté (2026-08-31) : le déploiement est un geste de terminal — la
    # commande dit tout, le formulaire n'a jamais servi.
    parts.append(
        '<p class="muted">Le déploiement se fait au terminal (judas compté, '
        "2026-08-31) : <code>py .claude/dispositif/package/deploy_nouveau_projet.py "
        "&lt;dossier&gt; --nom &lt;Nom&gt;</code> — vérification des sources : "
        "<code>--check</code>, écrasement volontaire : <code>--force</code>.</p>")
    parts.append("<p>" + bouton_party("deploiement") + "</p>")
    parts.append("</section>")

    # ---- Onglet Actions : le judas à trois décisions -------------------------
    # (arbitrage « Judas compté » + « Vous prévenir ailleurs », salle
    # atelier-idées — page « Trois lectures d'un zéro » v3, 2026-08-31. Les
    # boutons génériques jamais servis sont retirés ; restent les décisions,
    # posées sur l'objet qu'elles tranchent, sous l'œil des compteurs. Un bouton
    # de salle « Déclencher » n'est pas un bouton d'action : ils restent.)
    parts.append('</section><section class="pane" id="pane-actions" role="tabpanel" '
                 'aria-labelledby="tab-actions" tabindex="0">')
    parts.append("<h2>5. Décisions en attente</h2>")
    parts.append(render_usage_reel_html())
    parts.append(render_journal_usage_html())
    parts.append(
        '<div id="serveur-etat" class="off">Vérification du serveur d\'actions…</div>'
        '<p class="muted">Trois décisions, posées sur l\'objet qu\'elles tranchent : '
        "arbitrer un <b>finding</b>, arbitrer une <b>trouvaille de veille</b>, "
        "<b>solder un run</b>. Les boutons appellent le serveur local "
        "(<code>py scripts/serve_wiki.py</code> puis ouvrir "
        '<a href="http://localhost:8765">localhost:8765</a>). '
        '<span class="badge-0t">0 token</span> = script déterministe · '
        '<span class="badge-llm">LLM</span> = lance <code>claude -p</code> (facturé, '
        "le clic vaut arbitrage — gouvernance propose→arbitre→applique).</p>")
    parts.append(render_decisions_html(collecte_decisions_en_attente()))
    # Débattre AVANT de trancher : la salle conseil-flotte instruit les findings
    # ouverts — un bouton de salle n'est pas un bouton d'action, il reste.
    parts.append("<p>" + bouton_party("diagnostic") + "</p>")
    parts.append(
        "<h3>Le reste vit au terminal</h3>"
        '<p class="muted">Re-scan : <code>py scripts/scan_projets.py</code> · '
        "dérive du canon : <code>py .claude/dispositif/sync_dispositif.py --check</code> · "
        "kit agentic : <code>py .claude/dispositif/export_agentic.py --check</code> · "
        "PDF : <code>py scripts/scan_projets.py --no-refresh --pdf</code> · "
        "nouveau projet : <code>py .claude/dispositif/package/deploy_nouveau_projet.py</code> · "
        "audit, diagnostic, veille : à demander dans la conversation — le point du "
        "jour du terminal pousse déjà les commandes d'arbitrage "
        "(<code>applique/refuse &lt;cible&gt;</code>, "
        "<code>adopte/ecarte \"&lt;titre&gt;\"</code>).</p>")
    parts.append("</section>")

    # ---- Onglet Actions correctives (pratiques faibles, projet par projet) --
    parts.append('</section><section class="pane" id="pane-correctifs" role="tabpanel" '
                 'aria-labelledby="tab-correctifs" tabindex="0">')
    parts.append("<h2>6. Actions correctives</h2>")
    parts.append(
        '<p class="muted">Deux natures distinctes, jamais additionnées : les '
        '<b>pratiques en écart</b> (dimensions du scan 🟠/🔴 et audit qualitatif '
        "moyen/critique — visibles dans l'onglet Pratiques) et les <b>findings "
        "ouverts</b> du diagnostic (constats qualitatifs non arbitrés, qui "
        "n'abaissent aucune pastille de pratique). Un projet dont toutes les "
        "pratiques sont vertes peut donc porter des findings ouverts — ce n'est "
        "pas une contradiction. Les findings OUVERTS portent leurs boutons "
        "d'arbitrage dans l'onglet <b>⚡ Actions</b> (judas compté, 2026-08-31) ; "
        "ici : l'inventaire complet, et les salles pour en débattre.</p>")
    projets_avec_ecarts = 0
    for p in projects:
        if not p["existe"]:
            continue
        ecarts = ecarts_du_projet(p)   # même source que le bandeau du pilotage
        findings_p = p.get("findings") or []
        if not ecarts and not findings_p:
            continue
        projets_avec_ecarts += 1
        n_critique = sum(1 for _, niv, _, _ in ecarts if niv in ("absent", "critique")) + len(findings_p)
        pastille_resume = "🔴" if n_critique else "🟠"
        parts.append(
            f'<details class="correctifs-projet"><summary>{pastille_resume} '
            f'<b>{e(p["nom"])}</b> — {e(libelle_ecarts(len(ecarts), len(findings_p)))}'
            "</summary><div class=\"actions-grille\">")
        for lib, niv, detail, cle in ecarts:
            # Les écarts d'audit (cle in DIM_AUDIT_KEYS) partagent leur `detail` avec
            # la synthèse de la table de l'onglet Pratiques (ecarts_du_projet lit la
            # même clé "synthese") : même ancre, même borne — voir DETAIL_LIMITE.
            ancre = ancre_synthese(p["nom"], cle) if cle in DIM_AUDIT_KEYS else ""
            attr, lien = rendu_detail_borne(e, detail, ancre) if ancre else (
                (f' title="{e(detail)}"', "") if detail else ("", ""))
            parts.append(
                f'<div class="action-carte"><h4>{PASTILLE.get(niv, "")} {e(lib)} '
                '<span class="badge-nature">pratique</span> '
                '<span class="badge-llm">LLM</span></h4>'
                f'<p{attr}>'
                f"{e(tronque(detail, 180)) or 'Écart mesuré, sans détail complémentaire.'}{lien}</p>"
                + bouton_party(contexte_party_correctif(f"{cle} {lib}"),
                               f"Écart mesuré sur {p['nom']} — {lib} : {tronque(detail, 160)}")
                + "</div>")
        for f in findings_p:
            titre_complet = f.get("titre") or ""
            titre = tronque(titre_complet, 160)
            cible_f = f.get("cible") or ""
            parts.append(
                f'<div class="action-carte"><h4>🔴 {e(cible_f)} '
                '<span class="badge-nature">finding</span> '
                '<span class="badge-llm">LLM</span></h4>'
                f'<p title="{e(titre_complet)}">{e(titre)}</p>'
                + bouton_party(
                    contexte_party_correctif(f"{f.get('categorie', '')} {cible_f}"),
                    f"Finding {f.get('categorie', '')} sur {p['nom']} — {cible_f} : "
                    f"{tronque(titre_complet, 160)}")
                + "</div>")
        parts.append("</div></details>")
    if not projets_avec_ecarts:
        parts.append('<p class="muted">Aucune pratique en écart détectée sur la flotte — rien à corriger.</p>')
    parts.append("</section>")

    # ---- Onglet Exports (PDF téléchargeables) --------------------------------
    parts.append('</section><section class="pane" id="pane-exports" role="tabpanel" '
                 'aria-labelledby="tab-exports" tabindex="0">')
    parts.append("<h2>7. Exports</h2>")
    parts.append("<div class='actions-grille'>")
    for fichier, titre_pdf, desc in (
        ("analyse-detaillee.pdf", "Analyse détaillée de la flotte",
         "Par projet : dimensions mesurées, audit qualitatif (findings localisés = exemples), synthèses commentées."),
        ("actions-remediation.pdf", "Actions de remédiation",
         "Findings ouverts + propositions, pratiques de veille à adopter, et remédiations déjà appliquées (exemples commentés)."),
    ):
        chemin_pdf = os.path.join(EXPORTS_DIR, fichier)
        etat = "" if os.path.isfile(chemin_pdf) else "<p class='muted'>(pas encore généré — commande « Régénérer » ci-contre)</p>"
        parts.append(
            f'<div class="action-carte"><h4>{e(titre_pdf)}</h4><p>{e(desc)}</p>{etat}'
            f'<a class="btn-pdf" href="docs/wiki/exports/{fichier}" download>Télécharger</a></div>')
    parts.append(
        '<div class="action-carte"><h4>Régénérer <span class="badge-0t">0 token</span></h4>'
        "<p>Au terminal (judas compté, 2026-08-31) : <code>py "
        "scripts/scan_projets.py --no-refresh --pdf</code></p>"
        + bouton_party("exports") + "</div>")
    parts.append("</div>")
    parts.append("</section>")

    # ---- Onglet Tutoriel (glossaire des concepts du dispositif) --------------
    # ---- Onglet Tokens (pilotage de la consommation) -------------------------
    parts.append('<section class="pane" id="pane-tokens" role="tabpanel" '
                 'aria-labelledby="tab-tokens" tabindex="0">')
    parts.append(render_tokens_html())
    parts.append("</section>")

    parts.append('<section class="pane" id="pane-tutoriel" role="tabpanel" '
                 'aria-labelledby="tab-tutoriel" tabindex="0">')
    parts.append(orienter_pane(render_tutoriel_html()))
    parts.append("</section>")

    # ---- Onglet Dispositif (schéma de fonctionnement des 2 agents) -----------
    parts.append('<section class="pane" id="pane-dispositif" role="tabpanel" '
                 'aria-labelledby="tab-dispositif" tabindex="0">')
    parts.append(orienter_pane(render_dispositif_html(projects)))
    parts.append("</section>")

    parts.append(f"<footer>Supervision projets — {e(now)}</footer>")
    # ---- JS : onglets + déclencheurs — code réel dans docs/wiki_app.js -------
    # (finding VScode5:js-inline-wiki arbitré 2026-07-29 : le JS est un fichier
    # .js édité comme du code — node --check natif, coloration, lint — inliné
    # ici pour garder la page standalone. Les valeurs dynamiques passent par le
    # bloc JSON wiki-config ci-dessous, JAMAIS par interpolation de chaîne
    # Python dans du code JS : c'est la classe de bugs qui a cassé la page deux
    # fois le 2026-07-24.)
    config = {"api": "http://localhost:8765", "genere": now}
    parts.append('<script id="wiki-config" type="application/json">'
                 + json.dumps(config, ensure_ascii=False) + "</script>")
    parts.append("<script>\n" + lire_wiki_app_js() + "\n</script></body></html>")
    return "\n".join(parts)


def lire_wiki_app_js():
    """Le JS du wiki vit dans docs/wiki_app.js — un fichier réel, versionné,
    édité comme du code. Absent = arrêt net avec le chemin attendu : mieux vaut
    échouer à la génération que livrer une page dont aucun bouton ne marche."""
    chemin = os.path.join(ROOT, "docs", "wiki_app.js")
    if not os.path.isfile(chemin):
        raise SystemExit(f"scan_projets : docs/wiki_app.js introuvable ({chemin}) — "
                         "le JS du wiki est un fichier source versionné, le restaurer via git.")
    with open(chemin, encoding="utf-8") as fh:
        return fh.read().rstrip("\n")


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
        # La mesure des tokens suit la MÊME cadence que les scans locaux : c'est ce qui
        # manquait, et son absence a gelé l'onglet Tokens 33 jours (cf. rafraichir_tokens).
        # Sous `--no-refresh` on ne la relance pas non plus — ce drapeau existe pour un
        # passage à coût nul, et lire 10 transcripts n'en est pas un.
        rafraichir_tokens()

    projects = [
        scan_project(p["nom"], p["chemin"], p.get("description", ""), p.get("livrable"))
        for p in config["projets"]
    ]
    veille = load_veille()
    now_dt = dt.datetime.now()
    now = now_dt.strftime("%Y-%m-%d %H:%M")
    pilotage = compute_pilotage(projects, veille, now_dt)
    # Tendances (incrément 5, finding wiki:tendances-wiki 2026-07-30) : lire le
    # PRÉCÉDENT avant d'écrire le nouveau snapshot, sinon on se compare à soi-même.
    precedent = charger_dernier_snapshot()
    snap = snapshot_actuel(projects, pilotage, now)
    pilotage["tendances"] = calcule_tendances(snap, precedent)
    ecrire_snapshot(snap)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    # Rendre AVANT d'ouvrir en écriture, puis publier atomiquement (cf.
    # `ecrire_atomique`) : le contenu est calculé en entier, et l'artefact déjà publié
    # n'est remplacé que si le rendu a abouti — une exception ne peut plus laisser
    # derrière elle un wiki de 0 octet.
    contenu_md = render_md(projects, veille, now, pilotage, now_dt)
    ecrire_atomique(OUT_MD, contenu_md)
    if "--pdf" in argv:
        # avant le rendu HTML : l'onglet Actions vérifie l'existence des PDF
        generate_pdfs(projects, veille, now)
    ancien_html = read_text(OUT_HTML)
    contenu_html = render_html(projects, veille, now, pilotage, now_dt, ancien_html)
    ecrire_atomique(OUT_HTML, contenu_html)
    # APRÈS l'écriture du wiki : la consigne de tokens cite la taille de docs/wiki.html,
    # qui vient d'être réécrit. La mesurer avant publierait la taille d'hier.
    chiffres_maj = regenerer_chiffres_claudemd()
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
        + (", CLAUDE.md (chiffres mesures) rafraichi" if chiffres_maj else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
