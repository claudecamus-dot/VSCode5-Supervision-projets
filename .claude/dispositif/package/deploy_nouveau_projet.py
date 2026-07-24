"""Package de déploiement agentic — bootstrap complet d'un NOUVEAU projet de la flotte.

Matérialise dans un projet cible toute la configuration agentic éprouvée par la
flotte : dispositif de supervision (canon), hooks de garde-fou, skills de pilotage
(orchestrateur, superviseur, revue-increment), catalogue + playbooks, settings.json
câblé, squelette CLAUDE.md et tests de non-régression.

Principe (leçon P1 — jamais de copies au repos) : ce package NE STOCKE AUCUNE copie.
C'est un MANIFESTE de sources vivantes — le canon du hub, les hooks du hub, le kit
d'export documenté de VSCode2, les tests à jour de VSCode3 — matérialisées à la
demande. Les sources évoluent → le prochain déploiement est à jour, sans maintenance
de duplicata. `--check` vérifie que toutes les sources existent (à câbler en CI/scan).

Usage :
  py .claude/dispositif/package/deploy_nouveau_projet.py --check
  py .claude/dispositif/package/deploy_nouveau_projet.py "C:/chemin/NouveauProjet" --nom MonProjet
  py .claude/dispositif/package/deploy_nouveau_projet.py "..." --nom X --force   # écrase l'existant

Après déploiement, suivre la checklist imprimée (adapter la zone du hook de vérif,
lancer les tests, premier scan) puis ajouter le projet à projets.json du hub.
"""

from __future__ import annotations

import json
import os
import shutil
import sys

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DISPOSITIF = os.path.dirname(PKG_DIR)
HUB = os.path.dirname(os.path.dirname(DISPOSITIF))
DOCS = os.path.expanduser("~/Documents")

# --- Manifeste : (source vivante, destination relative dans le projet cible) --------
# Chaque source est LA version de référence de la flotte, jamais une copie du package.
CANON = os.path.join(DISPOSITIF, "canon")
KIT_V2 = os.path.join(DOCS, "VSCode2", "export")            # couche connaissance (documentée README §)
TESTS_V3 = os.path.join(DOCS, "VSCode3", "tests")           # tests à jour du canon (fix 2026-07-24)
HOOKS_V3 = os.path.join(DOCS, "VSCode3", ".claude", "hooks")

MANIFEST = [
    # Dispositif de supervision — étage 1 (canon, source unique)
    (os.path.join(CANON, "scan_transcripts.py"), ".claude/supervision/scan_transcripts.py"),
    (os.path.join(CANON, "log_run.py"), ".claude/orchestration/log_run.py"),
    (os.path.join(HUB, ".claude", "supervision", "log_usage.py"), ".claude/supervision/log_usage.py"),
    (os.path.join(HUB, ".claude", "supervision", "write_diagnostic.py"), ".claude/supervision/write_diagnostic.py"),
    # Hooks de garde-fou et de routage (génériques dans le hub / VSCode3)
    (os.path.join(HUB, ".claude", "hooks", "guard_destructive_git.py"), ".claude/hooks/guard_destructive_git.py"),
    (os.path.join(HUB, ".claude", "hooks", "orchestrator_gate.py"), ".claude/hooks/orchestrator_gate.py"),
    (os.path.join(HOOKS_V3, "remind_revue_increment.py"), ".claude/hooks/remind_revue_increment.py"),
    (os.path.join(HOOKS_V3, "warn_verif_before_commit.py"), ".claude/hooks/warn_verif_before_commit.py"),
    # Skills de pilotage — couche connaissance (kit d'export VSCode2, documenté)
    (os.path.join(KIT_V2, "agent-orchestrator", "SKILL.md"), ".claude/skills/agent-orchestrator/SKILL.md"),
    (os.path.join(KIT_V2, "agent-supervisor", "SKILL.md"), ".claude/skills/agent-supervisor/SKILL.md"),
    (os.path.join(KIT_V2, "revue-increment", "SKILL.md"), ".claude/skills/revue-increment/SKILL.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "catalogue.md"), ".claude/orchestration/catalogue.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "playbooks", "FORMAT.md"), ".claude/orchestration/playbooks/FORMAT.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "playbooks", "dev-verifie.md"), ".claude/orchestration/playbooks/dev-verifie.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "playbooks", "export-ppt-verifie.md"), ".claude/orchestration/playbooks/export-ppt-verifie.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "playbooks", "revue-design-parallele.md"), ".claude/orchestration/playbooks/revue-design-parallele.md"),
    (os.path.join(KIT_V2, "agent-orchestrator", "playbooks", "cycle-produit-bmad.md"), ".claude/orchestration/playbooks/cycle-produit-bmad.md"),
    (os.path.join(KIT_V2, "README.md"), "docs/setup-agentic.md"),
    # Outils d'orchestration exécutables (génériques — VSCode3 à jour)
    (os.path.join(DOCS, "VSCode3", ".claude", "orchestration", "git_agents_inventory.py"),
     ".claude/orchestration/git_agents_inventory.py"),
    (os.path.join(DOCS, "VSCode3", ".claude", "orchestration", "generate_bmad_playbook.py"),
     ".claude/orchestration/generate_bmad_playbook.py"),
    # Tests de non-régression du dispositif (VSCode3 = à jour du canon)
    (os.path.join(TESTS_V3, "test_agent_orchestration.py"), "tests/test_agent_orchestration.py"),
    (os.path.join(TESTS_V3, "test_agent_supervision.py"), "tests/test_agent_supervision.py"),
]

# Adaptations à la matérialisation : le test d'arbitrage cite une skill propre à
# VSCode3 — dans un nouveau projet, la skill « projet sans scripts/ » déployée est
# revue-increment... déjà utilisée par d'autres asserts ; agent-supervisor est déployée,
# sans scripts/, non citée par chemin : c'est l'exemple valide ici.
SUBSTITUTIONS = {
    "tests/test_agent_supervision.py": [
        ("deck-design-library", "agent-supervisor"),
        ("catalogue de design consulté à la demande", "diagnostic à la demande, pas à chaque session"),
    ],
}

SETTINGS_TEMPLATE = {
    "permissions": {
        "deny": [
            "Read(./.env)",
            "Read(./secrets/**)",
            "Read(./config/credentials.json)",
        ]
    },
    "hooks": {
        "PreToolUse": [{
            "matcher": "Bash|PowerShell",
            "hooks": [
                {"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/guard_destructive_git.py"',
                 "timeout": 10, "statusMessage": "Garde-fou git destructif..."},
                {"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/warn_verif_before_commit.py"',
                 "timeout": 10, "statusMessage": "Verif reelle avant commit..."},
            ],
        }],
        "UserPromptSubmit": [{
            "hooks": [{"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/orchestrator_gate.py"',
                       "timeout": 10}],
        }],
        "SessionStart": [{
            "hooks": [
                {"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/supervision/scan_transcripts.py"',
                 "timeout": 60, "statusMessage": "Scan supervision (etage 1)..."},
                {"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/remind_revue_increment.py"',
                 "timeout": 10, "statusMessage": "Rappel revue-increment..."},
            ],
        }],
        "PostToolUse": [{
            "matcher": "Skill|Agent|Task",
            "hooks": [{"type": "command", "command": 'py "$CLAUDE_PROJECT_DIR/.claude/supervision/log_usage.py"',
                       "timeout": 10}],
        }],
    },
}

CLAUDE_MD_TEMPLATE = """# {nom}

<une phrase : ce que fait ce projet et son livrable principal.>

## Commandes

<setup/run/test copiables — inclure la commande d'un test unique.>

## Claude Code — configuration du projet

- `.claude/settings.json` (versionné) : hooks garde-fou git destructif + rappel de
  vérif réelle avant commit (adapter `_WATCHED_PREFIXES`/`_VERIF_BASH` dans
  `.claude/hooks/warn_verif_before_commit.py` au canal de CE projet), gate
  orchestrateur, scan supervision en SessionStart, deny rules secrets.
- `.claude/supervision/` + `.claude/orchestration/` : dispositif de supervision
  (source : canon du hub VScode5 — corriger LÀ-BAS puis `sync_dispositif.py`,
  jamais localement). Journal des orchestrations : `log_run.py` (`--solde` pour
  requalifier un run en attente). Arbitrages humains : `arbitrages.json`.
- Skills de pilotage : `agent-orchestrator` (demandes multi-étapes),
  `agent-supervisor` (diagnostic à la demande), `revue-increment`
  (definition-of-done avant commit).
- Tests du dispositif : `py -m pytest tests/test_agent_*.py` (sur Windows, passer
  `--basetemp` sur un dossier neuf).

## Règles

- Garder ce fichier sous 150 lignes (pratique flotte : un CLAUDE.md long fait
  ignorer les règles) — chaque ligne doit éviter une erreur réelle.
- Vérif RÉELLE avant tout commit de code applicatif (tests + rendu regardé).
"""


def check(verbose=True) -> list:
    manquantes = [src for src, _ in MANIFEST if not os.path.isfile(src)]
    if verbose:
        for src, _ in MANIFEST:
            etat = "ok" if os.path.isfile(src) else "MANQUANTE"
            if etat != "ok" or "--verbose" in sys.argv:
                print(f"  {etat:9} {src}")
        print(f"check : {len(MANIFEST) - len(manquantes)}/{len(MANIFEST)} sources vivantes présentes"
              + (f", {len(manquantes)} MANQUANTE(S)" if manquantes else ""))
    return manquantes


def read_lf(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def deploy(cible: str, nom: str, force: bool) -> int:
    manquantes = check(verbose=False)
    if manquantes:
        print("deploy : sources manquantes, déploiement refusé :")
        for m in manquantes:
            print("  -", m)
        return 2
    os.makedirs(cible, exist_ok=True)
    n = 0
    for src, rel in MANIFEST:
        dst = os.path.join(cible, rel.replace("/", os.sep))
        if os.path.exists(dst) and not force:
            print(f"  existe déjà (utiliser --force) : {rel}")
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        contenu = read_lf(src)
        for old, new in SUBSTITUTIONS.get(rel, []):
            contenu = contenu.replace(old, new)
        with open(dst, "wb") as fh:
            fh.write(contenu.replace("\n", "\r\n").encode("utf-8"))
        n += 1
    # Fichiers générés (pas des copies) : settings, CLAUDE.md, arbitrages vide
    generes = {
        ".claude/settings.json": json.dumps(SETTINGS_TEMPLATE, ensure_ascii=False, indent=2),
        "CLAUDE.md": CLAUDE_MD_TEMPLATE.format(nom=nom),
        ".claude/supervision/arbitrages.json": json.dumps({"arbitrages": []}, indent=2),
    }
    for rel, contenu in generes.items():
        dst = os.path.join(cible, rel.replace("/", os.sep))
        if os.path.exists(dst) and not force:
            print(f"  existe déjà (utiliser --force) : {rel}")
            continue
        os.makedirs(os.path.dirname(dst) or cible, exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(contenu)
        n += 1
    print(f"deploy : {n} fichier(s) matérialisé(s) dans {cible}")
    print(f"""
Checklist post-déploiement ({nom}) :
  0. git init + commit initial (le dispositif s'appuie sur git : inventaire des
     agents, commits scopés — 2 tests échouent hors dépôt git).
  1. Adapter `_WATCHED_PREFIXES`/`_VERIF_BASH` de .claude/hooks/warn_verif_before_commit.py
     au canal de ce projet (où vit le code ? comment on le teste ?).
  2. Compléter CLAUDE.md (sections en <chevrons>) — rester sous 150 lignes.
  3. Installer BMAD-METHOD (docs/setup-agentic.md § 5) — une partie des tests
     (tri BMAD, générateur cycle-produit) présuppose cette installation.
  4. Vérifier : py -m pytest tests/test_agent_*.py --basetemp <dossier neuf et COURT,
     ex. C:/tmp/bt — un basetemp long dépasse MAX_PATH Windows et fait échouer les
     tests git en « Filename too long »>. Avant l'étape 3, les 3 tests marqués BMAD
     échouent — attendu (vérifié au déploiement d'essai : 26/29 verts pré-BMAD).
  5. Premier scan : py .claude/supervision/scan_transcripts.py
  6. Déclarer le projet dans projets.json du hub VScode5 (supervision de flotte).""")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        return 1 if check() else 0
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    cible = args[0]
    nom = "NouveauProjet"
    if "--nom" in argv:
        i = argv.index("--nom")
        if i + 1 < len(argv):
            nom = argv[i + 1]
            args = [a for a in args if a != nom]
    return deploy(cible, nom, "--force" in argv)


if __name__ == "__main__":
    sys.exit(main())
