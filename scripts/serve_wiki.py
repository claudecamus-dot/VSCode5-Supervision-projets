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


# Une action corrective peut modifier du code sur un AUTRE dépôt de la flotte — critique
# par nature. Le prompt exige donc explicitement, pas seulement le playbook par défaut :
# revue de code, test technique ET fonctionnel, vérification par les faits (preuve, pas
# une déclaration) avant tout commit — cf. étape "revue-fraiche" + "verification" du
# playbook evolution-flotte, rendues non-optionnelles ici.
def action_remediation(cible):
    # cible libre mais bornée : injectée dans un prompt de gouvernance, pas dans un shell.
    cible = (cible or "").strip()[:200]
    if not cible or not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "-p",
            f"Via agent-orchestrator, playbook evolution-flotte : présente la proposition de "
            f"remédiation pour « {cible} » (finding du diagnostic ou pratique en écart mesurée "
            "par le scan), demande l'arbitrage explicite, et n'applique QUE si validé. "
            "ACTION CRITIQUE (peut toucher un autre dépôt de la flotte) — une fois l'arbitrage "
            "obtenu, le correctif est SYSTÉMATIQUEMENT soumis à : (1) une revue de code en "
            "contexte frais (étape revue-fraiche) AVANT tout commit ; (2) un test technique "
            "(unitaire/py_compile ou équivalent) ET un test fonctionnel (vérification réelle du "
            "rendu/du comportement, pas une lecture de code) ; (3) une vérification PAR LES FAITS "
            "— sortie de test ou artefact réel produit et montré comme preuve, jamais une simple "
            "déclaration de succès. Aucune de ces trois étapes n'est sautable ; sur un point non "
            "vérifiable factuellement, le dire explicitement plutôt que de l'affirmer."]


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
def action_valider(cible):
    cible = (cible or "").strip()[:200]
    if not cible or not CLAUDE_BIN:
        return None
    return [CLAUDE_BIN, "--dangerously-skip-permissions", "-p", NON_INTERACTIF +
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


JOBS = {}  # id -> {action, libelle, cible, status, started, ended, tail}
JOBS_LOCK = threading.Lock()


def _lancer_job(action, libelle, cible, argv):
    """Crée l'entrée JOBS et démarre le thread — factorisé pour être appelé aussi bien
    par une requête utilisateur (do_POST) que par un enchaînement automatique (le
    rescan post-validation ci-dessous)."""
    job_id = uuid.uuid4().hex[:8]
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "action": action, "libelle": libelle,
                        "cible": (cible or "").strip() or None,
                        "status": "en cours", "started": time.strftime("%H:%M:%S"),
                        "ended": None, "tail": []}
    threading.Thread(target=_run_job, args=(job_id, argv), daemon=True).start()
    return job_id


def _run_job(job_id, argv):
    with JOBS_LOCK:
        job = JOBS[job_id]
    try:
        proc = subprocess.Popen(
            argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        lines = []
        for line in proc.stdout:
            lines.append(line.rstrip())
            with JOBS_LOCK:
                job["tail"] = lines[-80:]   # rapport lisible dans l'encart dédié (scroll au-delà)
        proc.wait()
        with JOBS_LOCK:
            job["status"] = "ok" if proc.returncode == 0 else f"echec ({proc.returncode})"
    except Exception as exc:  # jamais de crash serveur pour un job
        with JOBS_LOCK:
            job["status"] = f"erreur ({exc})"
    finally:
        with JOBS_LOCK:
            job["ended"] = time.strftime("%H:%M:%S")
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
        self.send_header("Access-Control-Allow-Origin", "*")  # la page peut être ouverte en file://
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
        if not path.startswith("/api/run/"):
            return self._send(404, {"erreur": "introuvable"})
        length = int(self.headers.get("Content-Length") or 0)
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
            argv = action_valider(payload.get("cible"))
            libelle = f"Validé -> application : {payload.get('cible', '')[:55]}"
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
        cible = (payload.get("cible") or "").strip() or None
        # Garde-fou serveur (pas seulement l'UI) : un rechargement de page, un double-clic
        # ou deux onglets ouverts ne doivent jamais faire partir DEUX sessions identiques
        # en parallèle sur la même cible — la seconde tentative est refusée, pas mise en
        # file, avec un message explicite plutôt qu'un job fantôme silencieux.
        if action in ("remediation", "valider", "refuser", "deployer-veille") and cible:
            with JOBS_LOCK:
                en_double = next((j for j in JOBS.values()
                                  if j["action"] == action and j.get("cible") == cible
                                  and j["status"] == "en cours"), None)
            if en_double:
                return self._send(409, {
                    "erreur": "deja_en_cours",
                    "message": f"Une action « {action} » est déjà en cours de traitement pour "
                               "cette cible — patiente qu'elle se termine avant d'en relancer une.",
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
