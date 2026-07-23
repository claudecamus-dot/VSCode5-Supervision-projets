# Catalogue des agents/skills — "VScode5 - Supervision projets"

Catalogue de départ pour ce projet (créé le 2026-07-23, en même temps que l'installation
de BMAD-METHOD et du duo agent-orchestrator/agent-supervisor). Contrairement à un
catalogue mature, aucune entrée n'a encore de recul réel dans **ce** projet — les statuts
`eprouve`/`jamais_utilise` viendront de `routing-hints.json`, généré par
`supervision/scan_transcripts.py` au fil des sessions.

## Skills globales (disponibles dans tous les projets de l'utilisateur)

| Skill | Usage |
| --- | --- |
| `pptx-deck` | Construire un deck PowerPoint avec python-pptx (bibliothèque de layout + self-check géométrique) |
| `pptx-verify` | Vérifier visuellement un .pptx généré (rendu réel + inspection) |
| `restitution-deck-design` | Système de design pour decks de restitution façon conseil (hiérarchie, rythme, couleur=sens) |
| `roadmap-keeper` | Suivi et rendu visuel de roadmap de projet |
| `skill-creator` | Créer/modifier des skills Claude Code |

## Skills PPT installées dans ce projet (copiées depuis VSCode2, génériques)

| Skill | Usage |
| --- | --- |
| `deck-design-library` | Bibliothèque de patterns de slides par situation (verbatims, trajectoire, maturité, offre chiffrée…) |
| `pptx-framed-image` | Insertion d'image épousant la forme exacte d'un cadre de template PPT |
| `slide-text-polish` | Linter/amélioration de la qualité rédactionnelle des slides |

## Duo orchestrateur / superviseur + veille

| Skill | Usage |
| --- | --- |
| `agent-orchestrator` | Qualifie une demande, compose un plan (cascade/parallèle/async), l'exécute, journalise |
| `agent-supervisor` | Diagnostic qualitatif étage 2 : KO répétés, inefficacité, agents morts, vérifications manquantes |
| `veille-agentic` | Veille GitHub public (agents, sous-agents, skills, rules, playbooks) — cadence 3 j (hook SessionStart) ou manuel ; sortie `.claude/veille/veille.json` → section 2 du wiki |

## Outillage projet (code produit)

| Outil | Usage |
| --- | --- |
| `scripts/scan_projets.py` | Scanner multi-projets (config `projets.json`) → `docs/wiki/projets-supervision.md` + `docs/wiki.html` (tableau alertes + détails repliables + veille) |

## BMAD-METHOD (v6.10.0, modules core + bmm)

46 skills `bmad-*` installées (agents de rôle : `bmad-agent-analyst`, `bmad-agent-architect`,
`bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer` ;
tâches : création PRD/architecture/stories, revues, recherche, brainstorming, etc.).
**À utiliser uniquement sur demande explicite**, via `bmad-help` pour s'orienter dans le
catalogue complet — cf. règle de l'orchestrateur.

## Playbooks (`.claude/orchestration/playbooks/`)

| Playbook | Pour | Statut |
| --- | --- | --- |
| `dev-verifie` | Implémentation/correction avec tests + vérification réelle + revue avant commit | Importé (VSCode2), à confirmer ici |
| `export-ppt-verifie` | Génération/évolution d'un deck PPT avec vérification au rendu réel obligatoire | Importé (VSCode2), à confirmer ici |
| `revue-design-parallele` | Revue multi-angles d'un livrable en fan-out puis consolidation | Importé (VSCode2), à confirmer ici |

## Non repris depuis VSCode2 (couplés au code de l'app Interview-to-Deck)

`deck-design-review`, `priority-matrix`, `swot-matrix`, `run-dev-server`,
`revue-increment` référencent des fonctions précises de `pptx_export.py` ou l'app FastAPI
de VSCode2 — sans objet ici. Si un besoin équivalent apparaît dans ce projet (ex. lancer un
serveur de dev, faire une revue de fin d'incrément), le créer via `skill-creator` plutôt que
copier tel quel un skill qui suppose un autre code.
