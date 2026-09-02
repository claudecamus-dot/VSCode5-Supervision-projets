"""Écriture validée du diagnostic étage 2 (.claude/supervision/diagnostic.json).

Utilisé par la skill `agent-supervisor` : elle compose les constats (LLM), ce script
garantit le schéma que `scan_transcripts.py` consomme (fusion wiki + routing-hints).

Usage : py .claude/supervision/write_diagnostic.py '<json>'   (ou JSON sur stdin)
Schéma attendu : {"findings": [{"categorie", "titre", "preuve", ...}]}
  - categorie : ko-repete | inefficacite | agent-mort | interaction |
    verification-manquante | autre. `ko-repete` et `inefficacite` avec une `cible`
    alimentent la liste `prudence` de routing-hints.json (l'orchestrateur les évite).
  - titre (str, requis) : le constat en une phrase.
  - preuve (str, requis) : le signal objectif qui l'ancre (comptage, erreur, reprise,
    correction utilisateur) — garde-fou anti-auto-complaisance : jamais de constat
    sans donnée à l'appui.
  - priorite (int 1-5, optionnel, défaut 1), recommandation (str, optionnel).
  - cible (str, requis, non vide) : sans elle un constat reste invisible pour
    point_du_jour.py (findings_non_arbitres saute les findings sans cible).
  - proposition (str, optionnel — incrément C « challenger ») : le changement concret
    proposé (nouveau déclencheur de skill, contrat de playbook amendé, désinstallation…),
    en une phrase ou un mini-diff inline. Rendue dans le wiki avec le constat ;
    JAMAIS appliquée par le superviseur — l'humain arbitre, l'orchestrateur applique
    la version validée (gouvernance : règle R4 de CLAUDE.md, et
    .claude/skills/agent-orchestrator/SKILL.md § 2 bis).
`generated` est posé par ce script (horodatage courant) ; le fichier est réécrit en
entier à chaque diagnostic (pas un journal). Gitignoré — donnée machine.
Env (tests) : AGENT_SUPERVISION_DIAGNOSTIC.
Conception : docs/reflexions/conception-agent-supervisor.md (le POURQUOI, repris de
VSCode2 le 2026-09-02) ; le QUOI operationnel est dans .claude/skills/agent-supervisor/
SKILL.md. Entre le 2026-08-31 et cette reprise, ce champ a pointe un docs/reflexions qui
n'existait pas.
"""
import datetime
import json
import os
import sys

DIAGNOSTIC_PATH = os.environ.get("AGENT_SUPERVISION_DIAGNOSTIC") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "diagnostic.json"
)
CATEGORIES = (
    # Volet 1 — usage des agents
    "ko-repete", "inefficacite", "agent-mort", "interaction",
    "verification-manquante", "non-convergence",
    # Volet 2 — pratiques d'ingénierie (test, dev, revue, design)
    "pratique-test", "pratique-dev", "pratique-revue", "pratique-design",
    # Volet 2 — documentation et cadrage produit
    "pratique-doc", "pratique-produit",
    "autre",
)


def main(argv) -> int:
    # Console Windows en cp1252 : le JSON arrive/repart toujours en UTF-8.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raw = argv[0] if argv else sys.stdin.read()
    try:
        diag = json.loads(raw)
    except ValueError as exc:
        print(f"write_diagnostic : JSON invalide ({exc})")
        return 1
    findings = diag.get("findings") if isinstance(diag, dict) else None
    if not isinstance(findings, list) or not findings:
        print("write_diagnostic : un objet {\"findings\": [...]} non vide est attendu")
        return 1
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            print(f"write_diagnostic : finding #{i} n'est pas un objet")
            return 1
        missing = [k for k in ("categorie", "titre", "preuve") if not f.get(k)]
        if missing:
            print(f"write_diagnostic : finding #{i} sans {', '.join(missing)} "
                  "(un constat sans preuve objective ne se journalise pas)")
            return 1
        if not str(f.get("cible") or "").strip():
            print(f"write_diagnostic : finding #{i} sans cible "
                  "(un constat sans cible non vide reste invisible pour point_du_jour.py)")
            return 1
        if f["categorie"] not in CATEGORIES:
            print(f"write_diagnostic : finding #{i} categorie invalide "
                  f"(attendu : {' | '.join(CATEGORIES)})")
            return 1
        prio = f.setdefault("priorite", 1)
        if not isinstance(prio, int) or not 1 <= prio <= 5:
            print(f"write_diagnostic : finding #{i} priorite invalide (int 1-5)")
            return 1
    # Ce script ECRASE diagnostic.json en entier (pas un journal, cf. docstring) : sans
    # ce garde-fou, un appelant qui ne retransmet pas les findings ouverts precedents
    # les perd en silence (CLAUDE.md R1/generation regle "reecrire l'ensemble des
    # findings ouverts" -- jusqu'ici porte par la seule discipline humaine). Avertit,
    # ne bloque pas : la reecriture integrale reste le mode de fonctionnement normal.
    # « Absent » et « illisible » ne sont PAS la meme chose : le `except (OSError,
    # ValueError): anciens = []` d'origine rendait ce garde-fou MUET exactement quand
    # il servait le plus (precedent tronque), et comme le fichier est reecrit en
    # entier il pouvait se tronquer lui-meme puis neutraliser sa propre alarme au
    # tour suivant. Un premier diagnostic (fichier absent) reste silencieux.
    anciens = []
    precedent = None
    try:
        with open(DIAGNOSTIC_PATH, encoding="utf-8") as fh:
            precedent = json.load(fh)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        print(f"write_diagnostic AVERTISSEMENT : le diagnostic precedent est ILLISIBLE "
              f"({exc}) — impossible de verifier quels findings ouverts disparaissent "
              "de cette reecriture. Le fichier va etre remplace en entier : recuperer "
              "la version saine (git / sauvegarde) si des constats ouverts doivent "
              "etre repris.")
    if isinstance(precedent, dict) and isinstance(precedent.get("findings"), list):
        anciens = [f for f in precedent["findings"] if isinstance(f, dict)]
    elif precedent is not None:
        print("write_diagnostic AVERTISSEMENT : le diagnostic precedent est ILLISIBLE "
              "(structure inattendue, pas de liste 'findings') — meme consequence : "
              "les findings ouverts qui disparaissent ne peuvent pas etre listes.")
    nouvelles_cles = {(f.get("cible"), f.get("titre")) for f in findings}
    disparus = [f for f in anciens if (f.get("cible"), f.get("titre")) not in nouvelles_cles]
    if disparus:
        print(f"write_diagnostic AVERTISSEMENT : {len(disparus)} finding(s) du diagnostic "
              "precedent disparaissent de cette reecriture :")
        for f in disparus:
            print(f"  - {f.get('cible', '?')} : {f.get('titre', '?')}")
    out = {
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "findings": findings,
    }
    # Ecriture atomique (meme motif que canon/log_run.solder) : un "w" direct laisse
    # un diagnostic.json tronque si l'ecriture est interrompue — et un diagnostic
    # tronque est precisement ce qui rendait l'alarme ci-dessus muette.
    tmp = DIAGNOSTIC_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, DIAGNOSTIC_PATH)
    print(f"write_diagnostic : {len(findings)} constat(s) -> {os.path.basename(DIAGNOSTIC_PATH)} "
          "(relancer le scan pour propager wiki + routing-hints)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
