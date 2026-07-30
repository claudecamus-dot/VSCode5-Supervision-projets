"""Serveur local du wiki de supervision — transforme la page en site web actionnable.

Sert `docs/wiki.html` et expose des déclencheurs (boutons de l'onglet « Actions ») :
analyses et remédiations lancées DEPUIS la page web, sans ouvrir un terminal.

Deux familles d'actions (allowlist stricte, jamais de commande arbitraire) :
  - Déterministes (0 token, instantanées) : re-scan de la flotte, vérification du
    canon (sync --check), vérification du package de déploiement, régénération des
    exports PDF.
  - LLM (facturées, via `claude -p` non-interactif — pratique documentée par les
    best practices Claude Code) : diagnostic superviseur, audit technique d'un
    projet, veille agentic, application d'une remédiation arbitrée. Le serveur
    LANCE ; la gouvernance (propose→arbitre→applique) reste dans les skills.

Usage :  py scripts/serve_wiki.py          # http://localhost:8765
         py scripts/serve_wiki.py --port 9000

Sécurité : bind 127.0.0.1 UNIQUEMENT (leçon audit VSCode : jamais 0.0.0.0 pour un
serveur qui exécute des commandes) ; actions par identifiant d'allowlist ; le
paramètre `projet` est validé contre projets.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
PY = sys.executable

# --- Allowlist d'actions : id -> (libellé, argv | callable(param) -> argv) ----------
def _projets_valides():
    try:
        with open(os.path.join(ROOT, "projets.json"), encoding="utf-8") as fh:
            return [p["nom"] for p in json.load(fh)["projets"]]
    except (OSError, ValueError, KeyError):
        return []


# Sur Windows, les CLI installées via npm sont des shims .cmd/.ps1 : subprocess.Popen
# sans shell=True ne les résout pas par le seul nom "claude" (contrairement à un shell
# interactif, qui applique PATHEXT). shutil.which() applique PATHEXT lui-même et rend
# le chemin réel — on garde argv en LISTE (jamais shell=True, pas d'injection).
CLAUDE_BIN = shutil.which("claude")

ACTIONS = {
    # Déterministes (0 token)
    "scan": ("Re-scan de la flotte + wiki", [PY, "-X", "utf8", os.path.join(ROOT, "scripts", "scan_projets.py")]),
    "scan-rapide": ("Re-scan sans relancer les scans locaux", [PY, "-X", "utf8", os.path.join(ROOT, "scripts", "scan_projets.py"), "--no-refresh"]),
    "sync-check": ("Vérifier la dérive du canon (flotte)", [PY, "-X", "utf8", os.path.join(ROOT, ".claude", "dispositif", "sync_dispositif.py"), "--check"]),
    "package-check": ("Vérifier les sources du package de déploiement", [PY, "-X", "utf8", os.path.join(ROOT, ".claude", "dispositif", "package", "deploy_nouveau_projet.py"), "--check"]),
    "pdf": ("Régénérer les exports PDF", [PY, "-X", "utf8", os.path.join(ROOT, "scripts", "scan_projets.py"), "--no-refresh", "--pdf"]),
}
# Préfixe systématique de tout prompt LLM lancé par un bouton : `claude -p` est NON
# INTERACTIF — un agent qui s'arrête pour poser une question ne reçoit jamais de
# réponse, le run se termine "ok" sans avoir rien fait (vécu réellement avec la
# première version du bouton Réflexion : le job finissait "ok" mais le fichier
# n'existait pas — l'agent avait demandé confirmation et personne n'a pu répondre).
NON_INTERACTIF = ("SESSION NON INTERACTIVE (claude -p, lancée par un bouton du wiki) : "
                   "personne ne peut répondre à une question. Le clic sur le bouton EST "
                   "l'autorisation d'agir — n'attends aucune confirmation supplémentaire, "
                   "ne pose aucune question, exécute directement l'action demandée. ")

if CLAUDE_BIN:
    # LLM (facturées) — claude -p, prompt fixe, gouvernance dans les skills. Absentes de
    # l'allowlist si le binaire n'est pas résolu : mieux vaut un bouton manquant qu'un
    # job qui échoue systématiquement en "fichier introuvable".
    ACTIONS["diagnostic"] = ("Diagnostic superviseur (étage 2, LLM)",
        [CLAUDE_BIN, "-p", NON_INTERACTIF + "Lance la skill agent-supervisor : diagnostic des deux volets sur les données de l'étage 1, écris diagnostic.json puis relance le scan wiki."])
    ACTIONS["veille"] = ("Veille agentic (LLM)",
        [CLAUDE_BIN, "-p", NON_INTERACTIF + "Lance la skill veille-agentic (volets écosystème + pratiques providers + gestion des tokens), enregistre les trouvailles et régénère le wiki."])


def action_audit(projet):
    if projet not in _projets_valides() or not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "-p", NON_INTERACTIF + f"Lance la skill audit-technique sur le projet {projet} "
            "(4 dimensions, lecture du code réel), écris l'audit puis régénère le wiki."]


# Ce bouton PROPOSE, il n'applique rien : c'est « Valider » qui écrit (et qui porte,
# lui, les exigences revue-fraiche / tests / preuve). Les y répéter ici coûtait du
# temps et des tokens sur l'action la plus cliquée, pour un run dont le seul livrable
# est un texte — un `claude -p` démarre déjà à froid en ~25 s (mesuré le 2026-07-29),
# tout ce qui allonge le tour se paie à chaque clic. Ce qui reste non négociable ici :
# le cadrage sur l'état RÉEL (R1) et l'interdiction d'appliquer sans arbitrage (R4).
def action_remediation(cible):
    # cible libre mais bornée : injectée dans un prompt de gouvernance, pas dans un shell.
    cible = (cible or "").strip()[:200]
    if not cible or not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "-p",
            f"Cible : « {cible} » (finding du diagnostic ou pratique en écart mesurée par le "
            "scan). Lis l'état RÉEL de la cible avant toute proposition — la reco peut être "
            "déjà satisfaite, en tout ou partie ; le dire alors plutôt que d'inventer un "
            "correctif. Puis RENDS UNE PROPOSITION ÉCRITE, courte et actionnable : le constat "
            "vérifié, le correctif proposé (fichiers touchés, nature du changement), et son "
            "coût/risque. S'il existe plusieurs voies, présente-les en « **Option A — …** », "
            "« **Option B — …** ». N'APPLIQUE RIEN, ne commite rien, ne modifie aucun fichier : "
            "l'utilisateur arbitre ensuite avec les boutons Valider/Invalider du wiki, et c'est "
            "« Valider » qui déclenchera l'application (revue de code, tests technique et "
            "fonctionnel, preuve factuelle). Ta réponse EST le livrable — pas de préambule."]


# Boutons Oui/Non de l'onglet Actions correctives, sur un rapport de remédiation déjà
# terminé (la proposition a été présentée) : l'utilisateur tranche l'arbitrage sans
# rouvrir une session interactive. « Non » est un fait déterministe (0 token, pas de
# LLM nécessaire pour noter un refus) ; « Oui » relance un agent qui applique — même
# rigueur (revue-fraiche, tests technique+fonctionnel, preuve factuelle) que la
# proposition initiale, car chaque `claude -p` est sans mémoire du run précédent.
REFUSER_SCRIPT = os.path.join(ROOT, ".claude", "supervision", "refuser_arbitrage.py")


# --dangerously-skip-permissions : SCOPÉ À CETTE SEULE ACTION (arbitrage explicite
# de l'utilisateur, 2026-07-24 — pas étendu à audit/diagnostic/veille/reflexion,
# qui restent bloqués par le mur de permission en attendant une session interactive).
# Un `claude -p` non interactif ne peut ni poser ni recevoir de prompt de permission —
# constaté en conditions réelles (job « valider » réel : « aucune écriture, aucun
# commit... je n'ai donc pas ajouté d'entrée ACCEPTÉ + APPLIQUÉ — ça aurait été un
# mensonge (R5) »). Les hooks de garde-fou déterministes (guard_destructive_git.py,
# deny rules) restent actifs malgré ce flag — ce sont des mécanismes différents.
def action_valider(cible, choix=None):
    cible = (cible or "").strip()[:200]
    if not cible or not CLAUDE_BIN:
        return None
    choix = (choix or "").strip()[:200]
    # Une proposition à plusieurs options (« Option A / B / C ») ne se résume pas à un
    # oui/non — sans ce choix explicite, un fresh claude -p (sans mémoire du run
    # précédent) devrait redeviner laquelle l'utilisateur a choisie.
    precision = (f"L'utilisateur a précisé son choix : « {choix} ». Retiens EXACTEMENT "
                 "cette option parmi celles proposées — n'en substitue aucune autre. "
                 if choix else "")
    return [CLAUDE_BIN, "--dangerously-skip-permissions", "-p", NON_INTERACTIF + precision +
            f"L'utilisateur a VALIDÉ (bouton « Valider » du wiki) la remédiation proposée pour "
            f"« {cible} ». Retrouve l'état réel de la cible (cadrage réel avant d'écrire, ne suppose "
            "rien du run précédent — chaque appel est sans mémoire), reconstruis la proposition si "
            "besoin, puis APPLIQUE-la directement via le playbook evolution-flotte : PAS de nouvelle "
            "demande d'arbitrage, l'utilisateur a déjà tranché. ACTION CRITIQUE (peut toucher un "
            "autre dépôt) — SYSTÉMATIQUE avant tout commit : (1) revue de code en contexte frais "
            "(étape revue-fraiche) ; (2) test technique ET test fonctionnel (vérification réelle, "
            "pas une lecture de code) ; (3) vérification PAR LES FAITS (preuve produite, jamais une "
            "déclaration). Puis enregistre dans .claude/supervision/arbitrages.json une entrée "
            "'ACCEPTÉ + APPLIQUÉ : <ce qui a été fait>' pour cette cible."]


def action_refuser(cible, raison):
    cible = (cible or "").strip()[:200]
    if not cible:
        return None
    argv = [PY, "-X", "utf8", REFUSER_SCRIPT, cible]
    raison = (raison or "").strip()[:300]
    if raison:
        argv.append(raison)
    return argv


# Boutons de l'onglet Veille — ferment la boucle veille -> réflexion -> déploiement sur
# la flotte, sans que l'utilisateur ait à composer le prompt à la main à chaque fois.
def action_reflexion():
    if not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "-p", NON_INTERACTIF +
            "Le clic sur le bouton EST l'autorisation d'écrire le fichier. "
            "Rédige une réflexion de mise en œuvre dans docs/reflexions/ (même format "
            "que docs/reflexions/ameliorations-supervision.md : organisée par verbe, chaque piste "
            "part d'un FAIT observé — pas d'une envie d'outillage —, table de séquencement à "
            "arbitrer en fin de document). Source : les pratiques de veille adoptées/nouvelles "
            "de .claude/veille/veille.json (règle d'analyse proposée + action corrective de "
            "chacune) et l'état réel du dispositif/de la flotte. N'APPLIQUE AUCUN changement de "
            "code ni de configuration — cette action écrit une réflexion à arbitrer (le fichier "
            "lui-même), elle ne déploie rien (le bouton « Déployer sur un projet » est l'étape "
            "suivante, séparée) : écrire le document EST l'action attendue, pas une étape à "
            "confirmer avant."]


def action_deployer_veille(projet):
    if projet not in _projets_valides() or not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "-p",
            f"Via agent-orchestrator, playbook evolution-flotte : à partir des pratiques de veille "
            f"ADOPTÉES (.claude/veille/veille.json, statut adopte — règle d'analyse proposée + "
            f"action corrective) et des findings ouverts pertinents, identifie ce qui s'applique "
            f"concrètement à {projet}. Présente les correctifs candidats et demande l'arbitrage "
            "explicite avant d'appliquer quoi que ce soit — même gouvernance que les actions "
            "correctives (revue-fraiche, test technique+fonctionnel, preuve factuelle avant tout "
            "commit). Si aucune pratique de veille adoptée n'est pertinente pour ce projet, le dire "
            "explicitement plutôt que d'inventer un correctif."]


DEPLOY_SCRIPT = os.path.join(ROOT, ".claude", "dispositif", "package", "deploy_nouveau_projet.py")


def action_deploy(cible, nom, force):
    # cible/nom passés en éléments d'argv distincts (jamais shell=True) : pas d'injection
    # possible même avec des espaces/caractères spéciaux dans le chemin choisi.
    cible = (cible or "").strip()
    if not cible:
        return None
    nom = (nom or "NouveauProjet").strip()[:80] or "NouveauProjet"
    argv = [PY, "-X", "utf8", DEPLOY_SCRIPT, cible, "--nom", nom]
    if force:
        argv.append("--force")
    return argv


# --- Flux live des jobs LLM -------------------------------------------------------
# Mesuré le 2026-07-29 sur cette machine (claude.exe 2.1.217), prompt trivial :
#   binaire seul (--version) ............  2,1 s
#   premier événement de session ........ 21,9 s   <- démarrage à froid du CLI
#   tour Claude lui-même (duration_ms) ...  4,3 s
#   total ............................... 28,9 s
# Le démarrage à froid n'est pas compressible depuis ce dépôt (ni --safe-mode, ni
# --setting-sources, ni --strict-mcp-config, ni --model n'y changent quoi que ce
# soit : tous mesurés entre 18 et 26 s). Ce qui l'était, c'est l'ABSENCE TOTALE de
# retour : en `--output-format text`, claude -p n'écrit rien avant la toute
# dernière ligne — le rapport restait vide plusieurs minutes, ce qui se lit comme
# « c'est bloqué ». En stream-json, chaque étape (session prête, outil appelé,
# texte produit) arrive au fil de l'eau et alimente le rapport.
STREAM_ARGS = ["--output-format", "stream-json", "--verbose"]


def _est_job_llm(argv):
    return bool(CLAUDE_BIN) and argv and argv[0] == CLAUDE_BIN


def _avec_flux(argv):
    """Insère les options de streaming juste après le binaire (avant -p, qui doit
    rester en dernier avec son prompt)."""
    return [argv[0]] + STREAM_ARGS + argv[1:] if _est_job_llm(argv) else argv


def _ligne_evenement(ev):
    """Traduit un événement stream-json en UNE ligne lisible, ou None à ignorer.
    Objectif : que l'utilisateur voie l'agent AVANCER, pas un JSON brut."""
    t = ev.get("type")
    if t == "system":
        sous = ev.get("subtype")
        if sous == "init":
            return "· session prête — l'agent démarre"
        if sous == "hook_started":
            return None      # bruit : 3 hooks de démarrage à chaque lancement
        return None
    if t == "assistant":
        lignes = []
        for bloc in (ev.get("message") or {}).get("content") or []:
            if bloc.get("type") == "text" and (bloc.get("text") or "").strip():
                lignes.append((bloc["text"] or "").strip())
            elif bloc.get("type") == "tool_use":
                cible = ""
                entree = bloc.get("input") or {}
                for cle in ("file_path", "path", "command", "pattern", "prompt", "skill"):
                    if entree.get(cle):
                        cible = str(entree[cle]).replace("\n", " ")[:90]
                        break
                lignes.append(f"· {bloc.get('name', 'outil')} {cible}".rstrip())
        return "\n".join(lignes) or None
    if t == "result":
        return ev.get("result") or None
    return None


JOBS = {}  # id -> {action, libelle, cible, status, started, ended, tail}
JOBS_LOCK = threading.Lock()
# Borne de rétention des jobs terminés (finding robustesse de l'audit 2026-07-24 :
# JOBS croissait sans limite — négligeable sur une session courte, mais le serveur
# est fait pour tourner en fond des journées entières). Les jobs EN COURS ne sont
# jamais purgés, quel que soit leur nombre.
JOBS_MAX = 200


def _purger_jobs():
    """Garde les JOBS_MAX jobs les plus récents (en cours toujours conservés).
    Appelé sous JOBS_LOCK par l'appelant."""
    if len(JOBS) <= JOBS_MAX:
        return
    termines = [j for j in JOBS.values() if j["status"] != "en cours"]
    surplus = len(JOBS) - JOBS_MAX
    for job in termines[:surplus]:  # dict ordonné par insertion : les plus anciens d'abord
        JOBS.pop(job["id"], None)


def _lancer_job(action, libelle, cible, argv):
    """Crée l'entrée JOBS et démarre le thread — factorisé pour être appelé aussi bien
    par une requête utilisateur (do_POST) que par un enchaînement automatique (le
    rescan post-validation ci-dessous)."""
    job_id = uuid.uuid4().hex[:8]
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "action": action, "libelle": libelle,
                        "cible": (cible or "").strip() or None,
                        "status": "en cours", "started": time.strftime("%H:%M:%S"),
                        "t0": time.time(), "ended": None, "tail": []}
        _purger_jobs()
    threading.Thread(target=_run_job, args=(job_id, argv), daemon=True).start()
    return job_id


def _annuler_job(job_id):
    """Termine réellement le sous-processus d'un job "en cours" (pas un marquage
    cosmétique) — finding wiki:actions-irreversibles (c). Sur Windows, le CLI est
    lancé via un shim .cmd/.ps1 (cf. CLAUDE_BIN ci-dessus) : proc.terminate() ne
    tuerait que cmd.exe et laisserait l'agent réel orphelin en tâche de fond ;
    taskkill /T tue tout l'arbre de processus."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return False, "job introuvable"
        if job["status"] != "en cours":
            return False, "ce job est deja termine"
        proc = job.get("_proc")
        job["_annule"] = True
    if proc is not None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                capture_output=True, timeout=5)
            else:
                proc.terminate()
        except OSError:
            pass
    return True, None


def _run_job(job_id, argv):
    with JOBS_LOCK:
        job = JOBS[job_id]
    flux = _est_job_llm(argv)
    try:
        proc = subprocess.Popen(
            _avec_flux(argv), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        with JOBS_LOCK:
            job["_proc"] = proc   # nécessaire pour _annuler_job ; jamais sérialisé (cf. /api/jobs)
        lines = []
        rapport = None      # texte final de l'agent (événement `result`)
        for line in proc.stdout:
            line = line.rstrip()
            if flux and line.startswith("{"):
                try:
                    ev = json.loads(line)
                except ValueError:
                    ev = None
                if ev is not None:
                    if ev.get("type") == "result":
                        rapport = ev.get("result") or rapport
                    rendu = _ligne_evenement(ev)
                    if not rendu:
                        continue
                    lines.extend(rendu.splitlines())
                    with JOBS_LOCK:
                        job["tail"] = lines[-80:]
                    continue
            # Ligne non-JSON : sortie d'un script déterministe, ou stderr du CLI —
            # gardée telle quelle plutôt que masquée (sinon une erreur de lancement
            # deviendrait invisible dans le rapport).
            lines.append(line)
            with JOBS_LOCK:
                job["tail"] = lines[-80:]   # rapport lisible dans l'encart dédié (scroll au-delà)
        proc.wait()
        # Le rapport FINAL prime sur la trace de progression : sans cela, un job
        # bavard (30+ appels d'outils) chasserait sa propre conclusion hors des 80
        # lignes gardées — or c'est elle que l'utilisateur lit pour arbitrer, et
        # c'est elle où le JS repère les « **Option A/B/C** ».
        if rapport:
            with JOBS_LOCK:
                job["tail"] = (["— rapport final —"] + rapport.splitlines())[-200:]
        with JOBS_LOCK:
            job["status"] = ("annule" if job.get("_annule")
                              else "ok" if proc.returncode == 0 else f"echec ({proc.returncode})")
    # Erreurs TYPÉES (finding robustesse de l'audit 2026-07-24 : tout était rendu
    # « erreur (...) », diagnostic pauvre — on ne savait pas si l'interpréteur
    # manquait, si le script avait disparu ou s'il avait planté). Le libellé doit
    # dire quoi faire, pas seulement que ça a raté.
    except FileNotFoundError as exc:
        with JOBS_LOCK:
            job["status"] = f"erreur : executable ou script introuvable ({exc.filename or argv[0]})"
    except PermissionError as exc:
        with JOBS_LOCK:
            job["status"] = f"erreur : acces refuse ({exc.filename or argv[0]})"
    except OSError as exc:
        with JOBS_LOCK:
            job["status"] = f"erreur systeme au lancement ({exc.__class__.__name__}: {exc})"
    except Exception as exc:  # jamais de crash serveur pour un job
        with JOBS_LOCK:
            job["status"] = f"erreur inattendue ({exc.__class__.__name__}: {exc})"
    finally:
        with JOBS_LOCK:
            job["ended"] = time.strftime("%H:%M:%S")
            job["fin_ts"] = time.time()   # fige la durée affichée une fois terminé
    # Post-remédiation : réévaluer automatiquement le niveau de criticité mesuré par
    # le scan (déterministe, 0 token — analyse_pratiques relit le disque à chaque
    # exécution, --no-refresh ne change que l'agrégation d'usage, pas ces dimensions).
    # Sans ce chaînage, le tableau de synthèse resterait périmé tant que personne ne
    # clique "Re-scan" à la main. N'attrape PAS les dimensions d'audit qualitatif —
    # celles-là exigent un nouvel audit-technique, décision distincte de l'utilisateur.
    if job["action"] == "valider" and job["status"] == "ok":
        _lancer_job("scan-rapide",
                    f"Ré-évaluation post-remédiation (scan) : {(job.get('cible') or '')[:55]}",
                    None, ACTIONS["scan-rapide"][1])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # CORS restreint (audit securite 2026-07-24) : le wiki est souvent ouvert en
        # file:// (Origin "null") ou depuis localhost — on n'autorise que ceux-la, pas
        # "*". Sinon n'importe quelle page web tierce du meme navigateur pourrait POSTer
        # /api/run/* vers ce serveur, dont valider (qui tourne a --dangerously-skip-permissions).
        origin = self.headers.get("Origin", "")
        if origin == "null" or origin.startswith(("http://localhost", "http://127.0.0.1")):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(200, {})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html", "/wiki", "/wiki.html"):
            return self._serve_file(os.path.join(DOCS, "wiki.html"), "text/html; charset=utf-8")
        if path == "/api/jobs":
            with JOBS_LOCK:
                jobs = sorted(JOBS.values(), key=lambda j: j["started"], reverse=True)[:20]
                # Durée écoulée servie par le SERVEUR : un job LLM démarre à froid
                # en ~25 s (mesuré) et dure plusieurs minutes — sans compteur qui
                # avance, la carte « en cours » est indiscernable d'un job planté.
                maintenant = time.time()
                # Les clés internes (_proc = objet Popen, non sérialisable) ne quittent
                # jamais le serveur : filtrées avant toute réponse JSON.
                jobs = [{**{k: v for k, v in j.items() if not k.startswith("_")},
                         "duree_s": int((j["fin_ts"] if j.get("fin_ts")
                                        else maintenant) - j["t0"])}
                        for j in jobs]
            return self._send(200, {"jobs": jobs})
        if path == "/api/ping":
            return self._send(200, {"ok": True})
        # Statique sous docs/ uniquement (PDF, wiki markdown rendu, images)
        rel = os.path.normpath(path.lstrip("/"))
        if rel.startswith("docs" + os.sep):
            full = os.path.join(ROOT, rel)
            if os.path.commonpath([os.path.abspath(full), DOCS]) == DOCS and os.path.isfile(full):
                ctype = ("application/pdf" if full.endswith(".pdf")
                         else "text/html; charset=utf-8" if full.endswith(".html")
                         else "text/plain; charset=utf-8")
                return self._serve_file(full, ctype)
        self._send(404, {"erreur": "introuvable"})

    def _serve_file(self, full, ctype):
        try:
            with open(full, "rb") as fh:
                self._send(200, fh.read(), ctype)
        except OSError:
            self._send(404, {"erreur": "fichier illisible"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/cancel/"):
            job_id = path[len("/api/cancel/"):]
            ok, erreur = _annuler_job(job_id)
            if not ok:
                return self._send(404 if erreur == "job introuvable" else 409, {"erreur": erreur})
            return self._send(200, {"ok": True})
        if not path.startswith("/api/run/"):
            return self._send(404, {"erreur": "introuvable"})
        # Content-Length malforme -> 400 propre (pas un ValueError -> 500) ; corps borne
        # a 64 Kio (audit robustesse+securite 2026-07-24 : un POST est un petit JSON).
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"erreur": "Content-Length invalide"})
        if length < 0 or length > 65536:
            return self._send(400, {"erreur": "corps trop volumineux"})
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            payload = {}
        action = path[len("/api/run/"):]
        if action == "audit":
            argv = action_audit(payload.get("projet"))
            libelle = f"Audit technique {payload.get('projet')}"
        elif action == "remediation":
            argv = action_remediation(payload.get("cible"))
            libelle = f"Remédiation : {payload.get('cible', '')[:60]}"
        elif action == "valider":
            argv = action_valider(payload.get("cible"), payload.get("choix"))
            choix_suffixe = f" [{payload['choix'][:40]}]" if payload.get("choix") else ""
            libelle = f"Validé -> application : {payload.get('cible', '')[:55]}{choix_suffixe}"
        elif action == "refuser":
            argv = action_refuser(payload.get("cible"), payload.get("raison"))
            libelle = f"Refusé : {payload.get('cible', '')[:60]}"
        elif action == "deploy":
            argv = action_deploy(payload.get("cible"), payload.get("nom"), payload.get("force"))
            libelle = f"Déploiement -> {payload.get('cible', '')[:80]}"
        elif action == "reflexion":
            argv = action_reflexion()
            libelle = "Réflexion de mise en œuvre"
        elif action == "deployer-veille":
            argv = action_deployer_veille(payload.get("projet"))
            libelle = f"Déploiement veille -> {payload.get('projet', '')}"
            # payload porte "projet", pas "cible" — composer une cible réutilisable pour
            # que les boutons Valider/Invalider de ce rapport aient de quoi travailler.
            if payload.get("projet"):
                payload = dict(payload, cible=f"déploiement des correctifs de veille sur {payload['projet']}")
        elif action in ACTIONS:
            libelle, argv = ACTIONS[action]
        else:
            return self._send(400, {"erreur": f"action inconnue : {action}"})
        if not argv:
            return self._send(400, {"erreur": "paramètre invalide"})
        # audit n'a pas de "cible" dans son payload (il porte "projet") : repli pour
        # que la même garde de déduplication ci-dessous s'applique aussi à lui.
        cible = (payload.get("cible") or payload.get("projet") or "").strip() or None
        # Garde-fou serveur (pas seulement l'UI) : un rechargement de page, un double-clic
        # ou deux onglets ouverts ne doivent jamais faire partir DEUX sessions identiques
        # en parallèle sur la même cible — la seconde tentative est refusée, pas mise en
        # file, avec un message explicite plutôt qu'un job fantôme silencieux.
        # Étendu (finding wiki:actions-irreversibles (b), 2026-07-30) aux actions FACTURÉES
        # qui n'avaient jusqu'ici aucune déduplication serveur : audit (par projet),
        # diagnostic/veille/reflexion (globales — un seul exemplaire à la fois, elles ne
        # portent pas de cible).
        ACTIONS_DEDUP_PAR_CIBLE = ("remediation", "valider", "refuser", "deployer-veille", "audit")
        ACTIONS_DEDUP_GLOBALES = ("diagnostic", "veille", "reflexion")
        en_double = None
        if action in ACTIONS_DEDUP_PAR_CIBLE and cible:
            with JOBS_LOCK:
                en_double = next((j for j in JOBS.values()
                                  if j["action"] == action and j.get("cible") == cible
                                  and j["status"] == "en cours"), None)
        elif action in ACTIONS_DEDUP_GLOBALES:
            with JOBS_LOCK:
                en_double = next((j for j in JOBS.values()
                                  if j["action"] == action and j["status"] == "en cours"), None)
        if en_double:
            return self._send(409, {
                "erreur": "deja_en_cours",
                "message": f"Une action « {action} » est déjà en cours de traitement — "
                           "patiente qu'elle se termine avant d'en relancer une.",
                "job": en_double["id"],
            })
        job_id = _lancer_job(action, libelle, cible, argv)
        self._send(202, {"job": job_id, "libelle": libelle})

    def log_message(self, fmt, *args):  # journal console minimal
        sys.stderr.write("serve_wiki : " + fmt % args + "\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    port = 8765
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # localhost uniquement
    print(f"serve_wiki : http://localhost:{port}  (Ctrl+C pour arrêter)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("serve_wiki : arrêt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
