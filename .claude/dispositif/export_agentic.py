"""Génère `export/` — le kit agentic du hub, repris tel quel par les autres projets.

Pourquoi ce script existe. Le hub est le propriétaire des skills de pilotage
(`agent-orchestrator`, `agent-supervisor`, `veille-agentic`…), de ses huit sous-agents
et de ses hooks : c'est ici qu'ils évoluent. Or `deploy_nouveau_projet.py` allait
chercher les skills dans `~/Documents/VSCode2/export`, un kit figé au 2026-07-21 —
mesuré le 2026-08-31, il servait un `agent-orchestrator` de **120 lignes** quand le hub
en avait **467** : tout nouveau projet héritait d'un orchestrateur amputé du routage
BMAD, du multi-agents et de la veille, et d'aucun sous-agent.

`export/` corrige la source : il est **généré depuis les sources vivantes du hub**, donc
jamais périmé tant qu'on le régénère, et **auto-portant** (`install_agentic.py` +
`MANIFESTE.json` posés dedans) — un projet peut le reprendre sans accéder au hub.

Comme `docs/wiki.html`, `export/` est une **donnée générée** : le modifier à la main est
perdu au passage suivant. Corriger la source dans le hub, puis régénérer.

Usage :
  py .claude/dispositif/export_agentic.py            # (re)génère export/
  py .claude/dispositif/export_agentic.py --check    # signale la dérive, n'écrit rien
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

DISPOSITIF = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(DISPOSITIF))
CANON = os.path.join(DISPOSITIF, "canon")
PACKAGE = os.path.join(DISPOSITIF, "package")
EXPORT = os.path.join(HUB, "export")
# Deux hooks n'ont pas leur version de reference dans le hub : celle du hub est
# specialisee « canal hub » (journal, arbitrages, wiki) et n'a aucun sens dans un
# projet applicatif. La version generique de la flotte vit dans VSCode3, et c'est
# elle que le deploiement historique servait deja. Le --check surveille sa derive.
GENERIQUE = os.path.join(os.path.expanduser("~"), "Documents", "VSCode3", ".claude", "hooks")

SALLES_TOML = os.path.join(HUB, "_bmad", "custom", "bmad-party-mode.toml")


def nb_salles() -> int:
    """Nombre de salles REELLEMENT declarees dans le TOML source.

    Le README publie annoncait « 9 salles » alors que le TOML en declarait 12 : un
    projet cible lisait un compte faux dans le kit qu'il installait (finding
    VScode5:CLAUDE.md, arbitre le 2026-09-01). Un compte se lit a la source, il ne
    se recopie pas — c'est R6 applique au kit lui-meme.
    """
    try:
        with open(SALLES_TOML, encoding="utf-8") as fh:
            return sum(1 for ligne in fh
                       if ligne.strip() == "[[workflow.party_groups]]")
    except OSError:
        return 0

# --- Manifeste : (source vivante dans le hub, chemin dans export/, destination cible) ---
# La source est TOUJOURS le fichier que le hub fait vivre. Pour les deux scripts du
# canon, la référence est le canon lui-même (c'est lui que `sync_dispositif.py` propage).
MANIFESTE: list[tuple[str, str, str]] = [
    # Dispositif de supervision — étage 1 (déterministe, 0 token)
    (os.path.join(CANON, "scan_transcripts.py"), "supervision/scan_transcripts.py",
     ".claude/supervision/scan_transcripts.py"),
    (os.path.join(CANON, "log_run.py"), "orchestration/log_run.py",
     ".claude/orchestration/log_run.py"),
    (os.path.join(HUB, ".claude/supervision/log_usage.py"), "supervision/log_usage.py",
     ".claude/supervision/log_usage.py"),
    (os.path.join(HUB, ".claude/supervision/write_diagnostic.py"), "supervision/write_diagnostic.py",
     ".claude/supervision/write_diagnostic.py"),
    (os.path.join(HUB, ".claude/supervision/refuser_arbitrage.py"), "supervision/refuser_arbitrage.py",
     ".claude/supervision/refuser_arbitrage.py"),
    # Hooks de garde-fou et de rappel
    (os.path.join(HUB, ".claude/hooks/guard_destructive_git.py"), "hooks/guard_destructive_git.py",
     ".claude/hooks/guard_destructive_git.py"),
    (os.path.join(HUB, ".claude/hooks/orchestrator_gate.py"), "hooks/orchestrator_gate.py",
     ".claude/hooks/orchestrator_gate.py"),
    (os.path.join(GENERIQUE, "remind_revue_increment.py"), "hooks/remind_revue_increment.py",
     ".claude/hooks/remind_revue_increment.py"),
    (os.path.join(GENERIQUE, "warn_verif_before_commit.py"), "hooks/warn_verif_before_commit.py",
     ".claude/hooks/warn_verif_before_commit.py"),
    # Sans ce hook, la skill veille-agentic exportee n'a AUCUNE cadence : c'est exactement
    # ce qui a laisse passer 32 jours au hub pour une cadence de 3 (constate le 2026-08-31).
    (os.path.join(HUB, ".claude/hooks/remind_veille_agentic.py"), "hooks/remind_veille_agentic.py",
     ".claude/hooks/remind_veille_agentic.py"),
    # Skills de pilotage — la couche « connaissance » du dispositif
    (os.path.join(HUB, ".claude/skills/agent-orchestrator/SKILL.md"), "skills/agent-orchestrator/SKILL.md",
     ".claude/skills/agent-orchestrator/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/agent-supervisor/SKILL.md"), "skills/agent-supervisor/SKILL.md",
     ".claude/skills/agent-supervisor/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/revue-increment/SKILL.md"), "skills/revue-increment/SKILL.md",
     ".claude/skills/revue-increment/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/veille-agentic/SKILL.md"), "skills/veille-agentic/SKILL.md",
     ".claude/skills/veille-agentic/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/audit-technique/SKILL.md"), "skills/audit-technique/SKILL.md",
     ".claude/skills/audit-technique/SKILL.md"),
    # Chaine documentaire : image posee dans un cadre du template a sa forme exacte
    # (prstGeom clone, cover-crop, photos CC0 + repli offline), lint de texte et
    # catalogue de representations. Les tests des skills partent AVEC elles : sans eux,
    # le projet cible herite du code sans le filet qui le tient (analyse flotte 2026-08-31).
    (os.path.join(HUB, ".claude/skills/pptx-framed-image/SKILL.md"), "skills/pptx-framed-image/SKILL.md",
     ".claude/skills/pptx-framed-image/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/pptx-framed-image/scripts/framed_image.py"), "skills/pptx-framed-image/scripts/framed_image.py",
     ".claude/skills/pptx-framed-image/scripts/framed_image.py"),
    (os.path.join(HUB, ".claude/skills/pptx-framed-image/scripts/stock_images.py"), "skills/pptx-framed-image/scripts/stock_images.py",
     ".claude/skills/pptx-framed-image/scripts/stock_images.py"),
    (os.path.join(HUB, ".claude/skills/pptx-framed-image/scripts/nature_images.py"), "skills/pptx-framed-image/scripts/nature_images.py",
     ".claude/skills/pptx-framed-image/scripts/nature_images.py"),
    (os.path.join(HUB, ".claude/skills/pptx-framed-image/tests/test_framed_image.py"), "skills/pptx-framed-image/tests/test_framed_image.py",
     ".claude/skills/pptx-framed-image/tests/test_framed_image.py"),
    (os.path.join(HUB, ".claude/skills/slide-text-polish/SKILL.md"), "skills/slide-text-polish/SKILL.md",
     ".claude/skills/slide-text-polish/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/slide-text-polish/scripts/slide_lint.py"), "skills/slide-text-polish/scripts/slide_lint.py",
     ".claude/skills/slide-text-polish/scripts/slide_lint.py"),
    (os.path.join(HUB, ".claude/skills/slide-text-polish/tests/test_slide_lint.py"), "skills/slide-text-polish/tests/test_slide_lint.py",
     ".claude/skills/slide-text-polish/tests/test_slide_lint.py"),
    (os.path.join(HUB, ".claude/skills/deck-design-library/SKILL.md"), "skills/deck-design-library/SKILL.md",
     ".claude/skills/deck-design-library/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/deck-design-library/references/catalogue-restitution.md"), "skills/deck-design-library/references/catalogue-restitution.md",
     ".claude/skills/deck-design-library/references/catalogue-restitution.md"),
    # Generation de PDF de qualite sur gabarit + verificateur qui MESURE le resultat.
    # Ne pas confondre « le PDF se genere sans erreur » et « le PDF est correct » : l'audit
    # du 2026-08-31 a trouve un HTTP 500 sur verbatim long et des caracteres perdus en
    # silence sur une chaine dont les 23 tests passaient. Prerequis : reportlab (generation)
    # et PyMuPDF (verification) — la skill le dit et degrade proprement s'ils manquent.
    (os.path.join(HUB, ".claude/skills/pdf-quality/SKILL.md"), "skills/pdf-quality/SKILL.md",
     ".claude/skills/pdf-quality/SKILL.md"),
    (os.path.join(HUB, ".claude/skills/pdf-quality/scripts/pdf_report.py"), "skills/pdf-quality/scripts/pdf_report.py",
     ".claude/skills/pdf-quality/scripts/pdf_report.py"),
    (os.path.join(HUB, ".claude/skills/pdf-quality/scripts/pdf_verify.py"), "skills/pdf-quality/scripts/pdf_verify.py",
     ".claude/skills/pdf-quality/scripts/pdf_verify.py"),
    (os.path.join(HUB, ".claude/skills/pdf-quality/tests/test_pdf_quality.py"), "skills/pdf-quality/tests/test_pdf_quality.py",
     ".claude/skills/pdf-quality/tests/test_pdf_quality.py"),
    # Sous-agents porteurs (absents de l'ancien package — d'où des plans irréalisables)
    # Quatre porteurs (agent-orchestrator, bmad-cadrage, bmad-doc, bmad-livraison) ont
    # ete MIS EN SOMMEIL le 2026-09-01 et retires d'ici : jamais invoques en 33 jours,
    # ils partaient pourtant dans le kit de chaque cible. Ils vivent desormais dans
    # .claude/agents-en-sommeil/, qui porte la mesure et la facon de les reveiller.
    (os.path.join(HUB, ".claude/agents/agent-supervisor.md"), "agents/agent-supervisor.md",
     ".claude/agents/agent-supervisor.md"),
    (os.path.join(HUB, ".claude/agents/veille-agentic.md"), "agents/veille-agentic.md",
     ".claude/agents/veille-agentic.md"),
    (os.path.join(HUB, ".claude/agents/bmad-revue.md"), "agents/bmad-revue.md",
     ".claude/agents/bmad-revue.md"),
    (os.path.join(HUB, ".claude/agents/bmad-recherche.md"), "agents/bmad-recherche.md",
     ".claude/agents/bmad-recherche.md"),
    # Orchestration — catalogue, playbooks et outils
    (os.path.join(HUB, ".claude/orchestration/catalogue.md"), "orchestration/catalogue.md",
     ".claude/orchestration/catalogue.md"),
    (os.path.join(HUB, ".claude/orchestration/git_agents_inventory.py"), "orchestration/git_agents_inventory.py",
     ".claude/orchestration/git_agents_inventory.py"),
    (os.path.join(HUB, ".claude/orchestration/generate_bmad_playbook.py"), "orchestration/generate_bmad_playbook.py",
     ".claude/orchestration/generate_bmad_playbook.py"),
    (os.path.join(HUB, ".claude/orchestration/playbooks/FORMAT.md"), "orchestration/playbooks/FORMAT.md",
     ".claude/orchestration/playbooks/FORMAT.md"),
    (os.path.join(HUB, ".claude/orchestration/playbooks/dev-verifie.md"), "orchestration/playbooks/dev-verifie.md",
     ".claude/orchestration/playbooks/dev-verifie.md"),
    (os.path.join(HUB, ".claude/orchestration/playbooks/export-ppt-verifie.md"),
     "orchestration/playbooks/export-ppt-verifie.md",
     ".claude/orchestration/playbooks/export-ppt-verifie.md"),
    (os.path.join(HUB, ".claude/orchestration/playbooks/revue-design-parallele.md"),
     "orchestration/playbooks/revue-design-parallele.md",
     ".claude/orchestration/playbooks/revue-design-parallele.md"),
    (os.path.join(HUB, ".claude/orchestration/playbooks/evolution-flotte.md"),
     "orchestration/playbooks/evolution-flotte.md",
     ".claude/orchestration/playbooks/evolution-flotte.md"),
    # La commande /orchestre : sans elle, la skill existe mais rien ne l'appelle.
    # Mesure du 2026-08-31 : aucun des 4 projets de la flotte n'avait de .claude/commands/,
    # donc /orchestre n'etait utilisable qu'au hub.
    (os.path.join(HUB, ".claude/commands/orchestre.md"), "commands/orchestre.md",
     ".claude/commands/orchestre.md"),
    # Les salles de table ronde (compte reel : voir nb_salles(), jamais un chiffre
    # ecrit ici — le kit a publie « 9 salles » pendant que le TOML en declarait 12).
    # SEULE entree du kit dont la destination sort de .claude/ : c'est un override de
    # la skill bmad-party-mode, qui le cherche dans _bmad/custom/ — le poser ailleurs
    # le rendrait inerte en silence.
    # Sans lui, un projet installait la skill agent-orchestrator AVEC sa section
    # 2 septies (« convoquer une salle ») et sa table SALLES-ROUTAGE, donc un plan
    # qui renvoie a des salles introuvables chez lui : exactement le defaut d'un
    # mode d'emploi qui vit ailleurs que la ou il s'applique.
    (os.path.join(HUB, "_bmad/custom/bmad-party-mode.toml"), "party/bmad-party-mode.toml",
     "_bmad/custom/bmad-party-mode.toml"),
    # L'installateur lui-même (source vivante dans package/)
    (os.path.join(PACKAGE, "install_agentic.py"), "install_agentic.py", None),
]

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
                {"type": "command",
                 "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/guard_destructive_git.py"',
                 "timeout": 10, "statusMessage": "Garde-fou git destructif..."},
                {"type": "command",
                 "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/warn_verif_before_commit.py"',
                 "timeout": 10, "statusMessage": "Verif reelle avant commit..."},
            ],
        }],
        "UserPromptSubmit": [{
            "hooks": [{"type": "command",
                       "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/orchestrator_gate.py"',
                       "timeout": 10}],
        }],
        "SessionStart": [{
            "hooks": [
                {"type": "command",
                 "command": 'py "$CLAUDE_PROJECT_DIR/.claude/supervision/scan_transcripts.py"',
                 "timeout": 60, "statusMessage": "Scan supervision (etage 1)..."},
                {"type": "command",
                 "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/remind_revue_increment.py"',
                 "timeout": 10, "statusMessage": "Rappel revue-increment..."},
                {"type": "command",
                 "command": 'py "$CLAUDE_PROJECT_DIR/.claude/hooks/remind_veille_agentic.py"',
                 "timeout": 10, "statusMessage": "Cadence veille agentic..."},
            ],
        }],
        "PostToolUse": [{
            "matcher": "Skill|Agent|Task",
            "hooks": [{"type": "command",
                       "command": 'py "$CLAUDE_PROJECT_DIR/.claude/supervision/log_usage.py"',
                       "timeout": 10}],
        }],
    },
}

CLAUDE_MD_TEMPLATE = """# {nom}

<une phrase : ce que fait ce projet et son livrable principal.>

## Commandes

<setup/run/test copiables — inclure la commande d'un test unique.>

## Claude Code — configuration du projet

- `.claude/settings.json` (versionné) : garde-fou git destructif, rappel de vérif
  réelle avant commit (adapter `_WATCHED_PREFIXES`/`_VERIF_BASH` dans
  `.claude/hooks/warn_verif_before_commit.py` au canal de CE projet), gate
  orchestrateur, scan supervision en SessionStart, deny rules secrets.
- `.claude/skills/` : orchestrateur (compose et exécute les plans multi-étapes),
  superviseur (diagnostic étage 2), revue-increment (definition of done),
  veille-agentic (état de l'art), audit-technique.
- `.claude/agents/` : les sous-agents porteurs que l'orchestrateur dispatche.
- `.claude/supervision/` + `.claude/orchestration/` : dispositif de supervision.
  Journal des orchestrations : `log_run.py` (`--solde` pour requalifier un run en
  attente). Arbitrages humains : `arbitrages.json`.

Le dispositif vient du hub de supervision : **corriger là-bas puis régénérer
l'export**, jamais localement — les copies locales divergent (leçon P1).

## Règles de travail

- Propose → arbitre → applique : aucun correctif auto-appliqué sans arbitrage humain.
- Jamais `succes` au journal sur un livrable que l'utilisateur doit encore valider.
- Tout chiffre écrit s'appuie sur la commande qui l'a produit.
"""

CHECKLIST = [
    "Adapter _WATCHED_PREFIXES et _VERIF_BASH dans .claude/hooks/warn_verif_before_commit.py au canal reel du projet (test, build, rendu).",
    "Completer CLAUDE.md : livrable, commandes de test, regles propres au projet.",
    "Lancer une session Claude Code : le hook SessionStart doit afficher le scan de supervision sans avertissement.",
    "Verifier que les skills sont vues : /orchestre doit etre proposee, .claude/agents/ doit lister les sous-agents.",
    "Salles de table ronde : elles n'existent que si la skill bmad-party-mode est installee (l'override _bmad/custom/ est sans effet sans elle). Verifier par /bmad-party-mode --party atelier-dev --mode subagent, et adapter les relais de projet du TOML a la cible.",
    "Ajouter le projet a projets.json du hub de supervision pour qu'il entre dans le scan de la flotte.",
    "Committer l'installation dans un commit scope au dispositif, sans embarquer de travail etranger (R2).",
]


def entrees_avec_destination() -> list[tuple[str, str, str]]:
    return [(src, rel, dst) for src, rel, dst in MANIFESTE if dst]


def _identiques(a: str, b: str) -> bool:
    """Compare deux fichiers sur leur contenu réel.

    Volontairement pas `filecmp.cmp` : même en `shallow=False`, il mémorise ses
    verdicts dans un cache indexé par (taille, date de modification) — une dérive qui
    conserve ces deux valeurs lui échappe dans un même processus. Mesuré ici : le test
    de dérive restait vert. Les fichiers du kit pèsent quelques centaines de kilo-octets
    au total, la lecture intégrale ne coûte rien.
    """
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def _orphelins() -> list[str]:
    """Fichiers présents sous export/ mais absents du manifeste.

    Sans ce sens de comparaison, `verifier()` ne voyait que le manifeste vers
    export/ : un fichier RETIRÉ du manifeste garderait éternellement sa copie
    périmée dans le kit publié, `--check` restant vert. Mesuré le 2026-08-31 :
    47/47 « à jour » alors qu'export/ contenait réellement 57 fichiers (les 10
    en trop étaient du bytecode).

    `__pycache__`/`*.pyc` sont volontairement IGNORÉS ici : ce sont des
    artefacts d'exécution locale (créés en important `install_agentic.py`
    depuis export/), pas des fichiers du kit — `TestProprete` (bytecode publié)
    les couvre déjà avec un message dédié, plus lisible qu'un ORPHELIN
    générique. Un fichier orphelin NON-bytecode, lui, doit faire sortir 1.
    """
    if not os.path.isdir(EXPORT):
        return []
    attendus = {rel.replace("/", os.sep) for _src, rel, _dst in MANIFESTE}
    # Écrits par generer() mais absents de MANIFESTE (qui ne couvre que ce qui a
    # une source vivante dans le hub) : légitimement présents, pas des orphelins.
    generes_hors_manifeste = {"MANIFESTE.json", "README.md"}
    orphelins: list[str] = []
    for racine, dossiers, fichiers in os.walk(EXPORT):
        dossiers[:] = [d for d in dossiers if d != "__pycache__"]
        for nom in fichiers:
            if nom.endswith(".pyc"):
                continue
            chemin = os.path.join(racine, nom)
            rel_disque = os.path.relpath(chemin, EXPORT)
            if rel_disque in attendus or rel_disque in generes_hors_manifeste:
                continue
            orphelins.append(rel_disque.replace(os.sep, "/"))
    return sorted(orphelins)


def verifier() -> int:
    """Signale la dérive entre les sources vivantes et export/ — n'écrit rien."""
    absents: list[str] = []
    derives: list[str] = []
    manquants_export: list[str] = []

    for src, rel, _dst in MANIFESTE:
        cible = os.path.join(EXPORT, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            absents.append(f"{rel}  (source absente : {os.path.relpath(src, HUB)})")
            continue
        if not os.path.isfile(cible):
            manquants_export.append(rel)
            continue
        if not _identiques(src, cible):
            derives.append(rel)

    orphelins = _orphelins()

    total = len(MANIFESTE)
    ok = total - len(absents) - len(derives) - len(manquants_export)
    print(f"verification export/ : {ok}/{total} a jour, {len(derives)} derive(s), "
          f"{len(manquants_export)} absent(s) d'export, {len(absents)} source(s) introuvable(s), "
          f"{len(orphelins)} orphelin(s)")
    for titre, items in (("SOURCE INTROUVABLE", absents), ("DERIVE", derives),
                         ("ABSENT D'EXPORT", manquants_export), ("ORPHELIN", orphelins)):
        for item in items:
            print(f"  {titre:<19} {item}")
    if derives or manquants_export or absents or orphelins:
        print("\nregenerer avec : py .claude/dispositif/export_agentic.py")
        return 1
    return 0


def _projets_flotte() -> list[tuple[str, str]]:
    """(nom, chemin) des projets de la flotte — le hub EXCLU, comme `propager_socle.projets()`.

    Le hub n'est pas une cible de propagation : comparer son `.claude/` a son propre
    `export/`, c'est comparer une chose a sa copie, et c'est le travail de `--check`.
    Deux de ces ecarts sont meme structurellement insolubles — `remind_revue_increment`
    et `warn_verif_before_commit` sont sources depuis VSCode3 parce que la version du hub
    est specialisee « canal hub ». Le hub apparaissait donc eternellement en derive de
    lui-meme sur deux fichiers qu'aucune correction ne pourra aligner : du bruit
    permanent, la meme famille que les 16 faux positifs de bandeau/CRLF.
    """
    chemin = os.path.join(HUB, "projets.json")
    if not os.path.isfile(chemin):
        return []
    with open(chemin, encoding="utf-8") as fh:
        data = json.load(fh)
    return [(p["nom"], p["chemin"]) for p in data.get("projets", [])
            if p.get("nom") and p.get("chemin")
            and os.path.abspath(p["chemin"]) != os.path.abspath(HUB)]


def verifier_flotte() -> int:
    """Compare le kit INSTALLÉ chez chaque projet de la flotte à celui du hub.

    Pourquoi cette commande existe (finding `flotte:agent-orchestrator-socle-vs-local`,
    arbitré le 2026-09-01) : `--check` ne compare que le hub à son propre `export/`,
    c'est-à-dire **le seul endroit où la dérive ne peut pas se produire** — les deux
    sont régénérés par la même commande. Le garde-fou était posé là où il n'y a pas de
    risque, pendant que les 6 copies de la flotte dérivaient sans que rien ne le dise :
    5 sections de capacité absentes des 6 copies, sans une seule exception.

    CE QUE CETTE COMMANDE NE FAIT PAS : juger. Un écart n'est pas une faute — trois
    copies portent du texte local introuvable au hub (VSCode1 et son pilotage par
    tickets, VSCode2 et son `slides_diagnostic.py`, VSCode et son journal en deux
    temps), et c'est R3 correctement appliquée. Écraser détruirait ce travail. Elle
    rapporte donc trois états distincts — `identique`, `absent`, `différent` — et
    laisse l'humain trancher lequel est une dérive et lequel est une spécialisation.

    Lecture seule sur les dépôts tiers : aucune écriture, jamais.
    """
    projets = _projets_flotte()
    if not projets:
        # « Je n'ai rien verifie » et « tout va bien » sortaient le MEME code : aucun
        # appelant ne pouvait les distinguer. Le code reste 0 des qu'un RAPPORT est
        # produit, meme avec des ecarts — la commande informe, elle ne juge pas
        # (« un ecart n'est PAS forcement une derive ») ; en faire un portail la ferait
        # echouer sur 88 specialisations R3 legitimes.
        print("aucun projet de flotte declare dans projets.json", file=sys.stderr)
        return 1

    total_absents = total_differents = total_signatures = 0
    for nom, racine in projets:
        if not os.path.isdir(racine):
            print(f"\n{nom} : dépôt introuvable ({racine}) — ignoré")
            continue
        identiques, absents, differents, socle_ok, signatures = [], [], [], [], []
        # `entrees_avec_destination()` et non MANIFESTE : une entree peut n'avoir
        # aucune destination (fichier publie mais non installable chez une cible).
        installables = entrees_avec_destination()
        for _src, rel, dst in installables:
            publie = os.path.join(EXPORT, rel.replace("/", os.sep))
            installe = os.path.join(racine, dst.replace("/", os.sep))
            if not os.path.isfile(installe):
                absents.append(dst)
            elif _identiques(publie, installe):
                identiques.append(dst)
            elif _signature_propagation(publie, installe):
                # Identique AU CORPS : l'écart est le bandeau « GÉNÉRÉ » et les CRLF
                # que la propagation écrit elle-même. Pas une dérive — la signature.
                signatures.append(dst)
            elif _socle_a_jour(publie, installe):
                # Fichier coupé socle/local : « différent » est ATTENDU et ne dit rien.
                socle_ok.append(dst)
            else:
                differents.append(dst)
        total_absents += len(absents)
        total_differents += len(differents)
        total_signatures += len(signatures)
        print(f"\n{nom} : {len(identiques)} identique(s), {len(signatures)} signature(s), "
              f"{len(socle_ok)} socle-a-jour+local, "
              f"{len(differents)} different(s), {len(absents)} absent(s) sur {len(installables)}")
        for dst in signatures:
            print(f"  SIGNATURE  {dst}  (corps identique ; bandeau genere + CRLF de propagation)")
        for dst in socle_ok:
            print(f"  SOCLE A JOUR  {dst}  (partie generee identique, chapitre local preserve)")
        for dst in differents:
            installe = os.path.join(racine, dst.replace("/", os.sep))
            publie = os.path.join(EXPORT, dst_rel(dst))
            n_cible = _lignes(installe)
            n_hub = _lignes(publie)
            print(f"  DIFFERENT  {dst}  ({n_cible} l. chez la cible / {n_hub} l. au hub)")
        for dst in absents:
            print(f"  ABSENT     {dst}")

    print(f"\ntotal flotte : {total_differents} different(s), {total_signatures} signature(s), "
          f"{total_absents} absent(s) "
          f"sur {len(projets)} depot(s) x {len(entrees_avec_destination())} fichier(s)")
    print("un ecart n'est PAS forcement une derive : lire avant de propager (R1/R3),\n"
          "et ne jamais ecraser un chapitre local — le finding le dit explicitement.")
    print("SIGNATURE = corps identique au kit publie, seuls le bandeau genere et les\n"
          "fins de ligne CRLF different : c'est la trace de la propagation, pas une derive.")
    return 0


# --- Signature de propagation --------------------------------------------------
# Ce que `sync_dispositif.py` ajoute de lui-même en installant une copie chez une
# cible : un bandeau « GÉNÉRÉ » de 8 lignes (bandeau + ligne vide), et des fins de
# ligne CRLF là où le canon et `export/` sont en LF. Comparer sans les retirer, c'est
# compter en dérive la trace de la synchronisation — le détecteur mesurait sa propre
# signature.
#
# Mesuré le 2026-09-01 avant correction : 16 des 104 « différents » (15,4 %), dont les
# DEUX seuls fichiers du canon (`scan_transcripts.py`, `log_run.py`) sur les 6 dépôts.
# Ce sont les plus critiques, et ils étaient DIFFERENT en permanence : une vraie dérive
# sur eux se serait noyée dans son propre bruit. Le finding d'origine n'avait vu que le
# bandeau ; le retirer seul laisse la comparaison fausse sur les 5 dépôts (4 écarts n'ont
# même pas de bandeau, seulement des CRLF) — d'où les DEUX normalisations.
MARQUEUR_BANNIERE = "# +-- GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT"
FIN_BANNIERE = "# +---------------------------------------------------------------------------"


def _lire_lf(chemin: str) -> str:
    """Contenu du fichier, fins de ligne normalisées — comme `sync_dispositif.read_lf`."""
    with open(chemin, "rb") as fh:
        brut = fh.read().decode("utf-8")
    return brut.replace("\r\n", "\n").replace("\r", "\n")


def _sans_banniere(texte: str) -> str:
    """Retire le bandeau « GÉNÉRÉ » de tête s'il y en a un.

    Même découpe que `sync_dispositif.strip_header` : c'est le même bandeau, écrit par
    le même script — deux règles de découpe divergentes rouvriraient exactement le trou
    qu'on ferme ici.
    """
    if not texte.startswith(MARQUEUR_BANNIERE):
        return texte
    fin = texte.find(FIN_BANNIERE)
    if fin == -1:
        return texte
    saut = texte.find("\n", fin)
    if saut == -1:
        return texte
    reste = texte[saut + 1:]
    return reste[1:] if reste.startswith("\n") else reste


def _signature_propagation(publie: str, installe: str) -> bool:
    """La copie cible est-elle le fichier publié PLUS la seule signature de propagation ?

    Vrai = rien n'a dérivé, l'écart est la trace de la synchronisation elle-même. Ce
    n'est pas un blanchiment : une seule ligne de corps changée fait retomber en
    `False` — c'est ce que vérifie `test_une_vraie_derive_reste_signalee`.
    """
    try:
        return _sans_banniere(_lire_lf(installe)) == _lire_lf(publie)
    except (OSError, UnicodeDecodeError, ValueError):
        return False


MARQUEUR_SOCLE = "<!-- SOCLE-PROVENANCE:"
ANCRE_SOCLE = "## Méthode — 5 étapes"


def _socle_a_jour(publie: str, installe: str) -> bool:
    """Un fichier coupé socle/local est-il à jour SUR SA PARTIE GÉNÉRÉE ?

    Sans cette distinction, `--check-flotte` classe « différent » toute copie qui porte
    un chapitre « Portée sur ce projet » — c'est-à-dire, après la propagation du
    2026-09-01, les cinq. Le signal deviendrait constant, donc muet : on ne saurait plus
    distinguer « socle à jour + spécialisation locale » (l'état voulu) de « socle en
    retard d'une génération » (le défaut que le finding dénonçait).

    On compare donc la seule partie que le hub possède : tout ce qui suit `## Méthode`.
    Le chapitre local, lui, n'a PAS à ressembler à quoi que ce soit du hub — c'est sa
    raison d'être.
    """
    try:
        a = open(installe, encoding="utf-8").read()
        b = open(publie, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return False
    if MARQUEUR_SOCLE not in a or ANCRE_SOCLE not in a or ANCRE_SOCLE not in b:
        return False
    return a.split(ANCRE_SOCLE, 1)[1] == b.split(ANCRE_SOCLE, 1)[1]


def dst_rel(dst: str) -> str:
    """Chemin relatif dans export/ correspondant à une destination du manifeste."""
    for _src, rel, d in MANIFESTE:
        if d == dst:
            return rel.replace("/", os.sep)
    return dst


def _lignes(chemin: str) -> int:
    try:
        with open(chemin, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return -1


def generer() -> int:
    absents = [rel for src, rel, _ in MANIFESTE if not os.path.isfile(src)]
    if absents:
        print("ECHEC : source(s) introuvable(s), export non regenere pour ne pas publier un kit incomplet :")
        for rel in absents:
            print(f"  {rel}")
        return 1

    os.makedirs(EXPORT, exist_ok=True)
    # Le kit se copie tel quel sur une autre machine : il ne doit pas emporter de bytecode
    # (cree ici par les tests qui importent install_agentic.py depuis export/).
    for racine, dossiers, _fichiers in os.walk(EXPORT):
        for mort in [d for d in dossiers if d == "__pycache__"]:
            shutil.rmtree(os.path.join(racine, mort), ignore_errors=True)
    copies = 0
    for src, rel, _dst in MANIFESTE:
        cible = os.path.join(EXPORT, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(cible), exist_ok=True)
        shutil.copy2(src, cible)
        copies += 1

    genere_le = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    manifeste_json = {
        "genere_le": genere_le,
        "origine": "hub de supervision (VScode5) — py .claude/dispositif/export_agentic.py",
        "avertissement": "Contenu GENERE : le modifier ici est perdu a la regeneration. Corriger la source dans le hub.",
        "fichiers": [{"export": rel, "destination": dst} for _src, rel, dst in entrees_avec_destination()],
        "settings_template": SETTINGS_TEMPLATE,
        "claude_md_template": CLAUDE_MD_TEMPLATE,
        "checklist": CHECKLIST,
    }
    with open(os.path.join(EXPORT, "MANIFESTE.json"), "w", encoding="utf-8") as fh:
        json.dump(manifeste_json, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    with open(os.path.join(EXPORT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(readme(genere_le))

    # `verifier()` prescrit « regenerer avec : py export_agentic.py » sur un ORPHELIN —
    # mais `generer()` ne supprimait jamais rien : le remede ne corrigeait pas le
    # defaut qu'il nommait, et le signal restait rouge indefiniment (audit du
    # 2026-09-01). Un remede qui ne remedie pas finit ignore, comme tout garde-fou qui
    # crie sans qu'on puisse le taire. `export/` est ENTIEREMENT genere : y retirer un
    # fichier sorti du manifeste est le geste juste, et git le rend reversible.
    retires = []
    for rel in _orphelins():
        chemin = os.path.join(EXPORT, rel.replace("/", os.sep))
        try:
            os.remove(chemin)
            retires.append(rel)
        except OSError as err:
            print(f"  ORPHELIN non retire : {rel} ({err})", file=sys.stderr)
    for rel in retires:
        print(f"  retire   {rel} (sorti du manifeste)")

    print(f"export/ regenere : {copies} fichier(s) copie(s), "
          f"{len(entrees_avec_destination())} installable(s)"
          + (f", {len(retires)} orphelin(s) retire(s)" if retires else "")
          + ", MANIFESTE.json et README.md ecrits.")
    print(f"  installation dans un projet : py export/install_agentic.py --dry-run \"<chemin cible>\"")
    return 0


def readme(genere_le: str) -> str:
    lignes = [
        "# export/ — kit agentic du hub de supervision",
        "",
        "Bundle **auto-portant** du dispositif agentic éprouvé sur la flotte : skills de",
        "pilotage, sous-agents porteurs, hooks de garde-fou, playbooks, catalogue et scripts",
        "de supervision. Destiné à être **repris tel quel par un autre projet**, y compris",
        "sur une machine qui n'a pas le hub.",
        "",
        f"Généré le **{genere_le}** par `py .claude/dispositif/export_agentic.py`.",
        "",
        "> **Contenu généré.** Ne rien modifier ici : le correctif serait perdu à la",
        "> régénération suivante. Corriger la source dans le hub, puis régénérer.",
        "> `--check` signale la dérive entre les sources vivantes et ce répertoire.",
        "",
        "## Installer dans un projet",
        "",
        "```bash",
        "py export/install_agentic.py --liste                      # ce qui serait installé, et où",
        "py export/install_agentic.py --dry-run \"C:/chemin/Projet\"  # simulation, aucune écriture",
        "py export/install_agentic.py \"C:/chemin/Projet\" --nom MonProjet",
        "```",
        "",
        "Aucun fichier existant n'est écrasé sans `--force`. `settings.json` n'est jamais",
        "écrasé : ses hooks sont **fusionnés** (ceux du projet cible sont préservés, et",
        "réinstaller ne duplique pas les hooks du dispositif).",
        "",
        "## Contenu",
        "",
        "| Fichier | Installé dans le projet cible |",
        "| --- | --- |",
    ]
    for _src, rel, dst in entrees_avec_destination():
        lignes.append(f"| `{rel}` | `{dst}` |")
    lignes += [
        "",
        "Plus `install_agentic.py` (l'installateur), `MANIFESTE.json` (la table ci-dessus,",
        "les gabarits `settings.json`/`CLAUDE.md` et la checklist) et ce README.",
        "",
        "## Ce que l'installation ne fait pas",
        "",
        "- Elle n'installe **pas BMAD** : les skills `bmad-*` s'installent séparément, et la",
        "  table de routage de l'orchestrateur ne vaut que si elles sont présentes. Cela vaut",
        "  aussi pour les **salles** : `_bmad/custom/bmad-party-mode.toml` est un *override*",
        "  de la skill `bmad-party-mode` — sans cette skill installée, il est inerte, et",
        "  silencieusement. Le vérifier après installation (checklist).",
        f"- Les {nb_salles()} salles arrivent avec les **relais de la flotte du hub** "
        "(`relais-vscode1`…) :",
        "  ce sont les contraintes réelles des dépôts supervisés, pas celles du projet cible.",
        "  Sur un projet hors flotte, écrire son propre relais plutôt que d'emprunter un voisin.",
        "- Elle n'adapte **pas** les hooks au canal du projet : `warn_verif_before_commit.py`",
        "  contient des préfixes surveillés à ajuster (checklist, étape 1).",
        "- Elle n'inscrit **pas** le projet au scan de la flotte : c'est `projets.json` du hub.",
        "- Deux hooks (`remind_revue_increment`, `warn_verif_before_commit`) sont pris dans leur",
        "  version **générique** (VSCode3) et non dans celle du hub, spécialisée supervision.",
        "- `revue-increment` exportée est la version du hub, orientée supervision (journal,",
        "  arbitrages, wiki) : dans un projet applicatif, sa passe 2 est à réécrire sur le",
        "  canal réel du projet — tests, rendu, livrable.",
        "",
    ]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Genere export/, le kit agentic reprenable du hub.")
    parseur.add_argument("--check", action="store_true",
                         help="signaler la derive entre sources vivantes et export/, sans rien ecrire")
    parseur.add_argument("--check-flotte", action="store_true",
                         help="comparer le kit INSTALLE chez chaque projet de la flotte a celui du hub "
                              "(lecture seule : rapporte identique/different/absent, ne juge pas)")
    args = parseur.parse_args(argv)
    if args.check_flotte:
        return verifier_flotte()
    return verifier() if args.check else generer()


if __name__ == "__main__":
    raise SystemExit(main())
