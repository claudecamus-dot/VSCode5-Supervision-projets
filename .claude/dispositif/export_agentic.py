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
    # Sous-agents porteurs (absents de l'ancien package — d'où des plans irréalisables)
    (os.path.join(HUB, ".claude/agents/agent-orchestrator.md"), "agents/agent-orchestrator.md",
     ".claude/agents/agent-orchestrator.md"),
    (os.path.join(HUB, ".claude/agents/agent-supervisor.md"), "agents/agent-supervisor.md",
     ".claude/agents/agent-supervisor.md"),
    (os.path.join(HUB, ".claude/agents/veille-agentic.md"), "agents/veille-agentic.md",
     ".claude/agents/veille-agentic.md"),
    (os.path.join(HUB, ".claude/agents/bmad-revue.md"), "agents/bmad-revue.md",
     ".claude/agents/bmad-revue.md"),
    (os.path.join(HUB, ".claude/agents/bmad-doc.md"), "agents/bmad-doc.md",
     ".claude/agents/bmad-doc.md"),
    (os.path.join(HUB, ".claude/agents/bmad-recherche.md"), "agents/bmad-recherche.md",
     ".claude/agents/bmad-recherche.md"),
    (os.path.join(HUB, ".claude/agents/bmad-cadrage.md"), "agents/bmad-cadrage.md",
     ".claude/agents/bmad-cadrage.md"),
    (os.path.join(HUB, ".claude/agents/bmad-livraison.md"), "agents/bmad-livraison.md",
     ".claude/agents/bmad-livraison.md"),
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

    total = len(MANIFESTE)
    ok = total - len(absents) - len(derives) - len(manquants_export)
    print(f"verification export/ : {ok}/{total} a jour, {len(derives)} derive(s), "
          f"{len(manquants_export)} absent(s) d'export, {len(absents)} source(s) introuvable(s)")
    for titre, items in (("SOURCE INTROUVABLE", absents), ("DERIVE", derives),
                         ("ABSENT D'EXPORT", manquants_export)):
        for item in items:
            print(f"  {titre:<19} {item}")
    if derives or manquants_export or absents:
        print("\nregenerer avec : py .claude/dispositif/export_agentic.py")
        return 1
    return 0


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

    print(f"export/ regenere : {copies} fichier(s) copie(s), "
          f"{len(entrees_avec_destination())} installable(s), MANIFESTE.json et README.md ecrits.")
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
        "  table de routage de l'orchestrateur ne vaut que si elles sont présentes.",
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
    args = parseur.parse_args(argv)
    return verifier() if args.check else generer()


if __name__ == "__main__":
    raise SystemExit(main())
