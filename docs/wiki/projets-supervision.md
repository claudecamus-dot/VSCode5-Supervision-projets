# Supervision multi-projets — agents, skills, playbooks

_Généré le 2026-07-23 19:32 par `scripts/scan_projets.py` — ne pas éditer à la main._

## 1. Supervision des projets

| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 📊 [comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx](file:///C:/Users/claude.camus/Documents/VSCode/comop-pptx-prototype/output/comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx) | 6.10.0 (core+bmm+tea+bmb+cis) | 77 | 0 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode1 | 🌐 [http://localhost:3000](http://localhost:3000) | 6.10.0 (core+bmm) | 54 | 17 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | 🟠 majeur |
| VSCode2 | 🌐 [http://127.0.0.1:8000/missions](http://127.0.0.1:8000/missions) | 6.10.0 (core+bmm) | 49 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | 🔴 critique |
| VSCode3 | 📊 [bmad-iap-cadrage-synthese.pptx](file:///C:/Users/claude.camus/Documents/VSCode3/docs/cadrage-ppt/bmad-iap-cadrage-synthese.pptx) | 6.10.0 (core+bmm) | 52 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode4 | 📊 [Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx](file:///C:/Users/claude.camus/Documents/VSCode4/Exports/Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx) | 6.10.0 (core+bmm) | 52 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VScode5 | 🌐 [wiki.html](file:///C:/Users/claude.camus/Documents/VScode5 - Supervision projets/docs/wiki.html) | 6.10.0 (core+bmm) | 52 | 0 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |

_Alerte : niveau du finding le plus haut du diagnostic superviseur local (p5 = critique, p4 = majeur)._

### VSCode — Bac à sable proto PPT (COMOP, Node.js) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode`

Dernier scan superviseur local : 2026-07-23T19:31:02+02:00

**Skills utilisés** (0) : —

**Skills jamais utilisés** (77) : 71 bmad-* + agent-orchestrator, agent-supervisor, deck-design-library, pptx-framed-image, revue-increment, slide-text-polish

**Playbooks** : dev-verifie, export-ppt-verifie, revue-design-parallele

### VSCode1 — Questionnaire maturité agile/produit + export PPT [🟠 majeur]

Chemin : `C:/Users/claude.camus/Documents/VSCode1`

Dernier scan superviseur local : 2026-07-23T15:34:09+02:00

**Skills utilisés** (8) : revue-increment (5), run (4), roadmap-keeper (4), pptx-verify (3), skill-creator (3), agent-supervisor (3), artifact-design (2), agent-orchestrator (2)

**Skills jamais utilisés** (51) : 46 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, restitution-ppt, slide-text-polish

**Sous-agents** (17) : auditor, auditor-subagent, debugger, developer, developer-migrator, developer-refactor, documentarian, onboarder, orchestrator, orchestrator-dev, pathfinder, planner, ppt-designer, qa-engineer, reviewer, ui-designer, ux-designer
**Sous-agents utilisés** : ppt-designer (4), ux-designer (2), ui-designer (2), documentarian (1), onboarder (1), Explore (1), reviewer (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Diagnostic superviseur local (findings ouverts)** :
- p4 `interaction` [ppt-designer] — Déléguer une grosse revue design au sous-agent ppt-designer casse la boucle revue→correction quand son transcript expire — seul run partiel de l historique
- p4 `verification-manquante` [revue-increment] — revue-increment (definition-of-done) nommée comme étape terminale des runs deck du 2026-07-22 mais le skill n a pas tourné depuis le 2026-07-21
- p3 `inefficacite` [export-ppt-verifie] — export-ppt-verifie : 3 reprises/8 runs + pptx-verify 5/11 reprises — la boucle rendu→correction→re-rendu comptée comme reprise (constat VSCode2 #3, moins intense ici : 37% vs 100%)
- p2 `agent-mort` [famille:BMAD] — 44 skills bmad-* toujours 0 usage à J+7 — converge avec le constat VSCode2 #5 (2e vague de mise en sommeil proposée là-bas)

### VSCode2 — Interview-to-Deck (FastAPI) [🔴 critique]

Chemin : `C:/Users/claude.camus/Documents/VSCode2`

Dernier scan superviseur local : 2026-07-23T15:39:25+02:00

**Skills utilisés** (16) : run-dev-server (21), agent-orchestrator (9), agent-supervisor (9), revue-increment (7), bmad-code-review (7), update-config (6), pptx-verify (6), roadmap-keeper (5), run (3), pptx-deck (2), skill-creator (2), slide-text-polish (2), init (1), claude-api (1), restitution-deck-design (1), deck-design-review (1)

**Skills jamais utilisés** (42) : 38 bmad-* + deck-design-library, pptx-framed-image, priority-matrix, swot-matrix

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Diagnostic superviseur local (findings ouverts)** :
- p5 `verification-manquante` [agent-orchestrator] — Le statut « en-attente-validation » n'a JAMAIS été utilisé depuis son introduction — les runs à livrable deck se loggent « succes » sur auto-vérification
- p5 `ko-repete` [run-dev-server] — La fraîcheur du serveur reste la cause n°1 des reprises — le --reload a ENCORE servi du code périmé le 2026-07-22 à 23h, après toutes les leçons
- p4 `inefficacite` [export-ppt-verifie] — export-ppt-verifie : 7 runs / 7 succès / 7 avec reprises — la « reprise » est en réalité la boucle nominale rendre→corriger→re-rendre, comptée comme anomalie
- p3 `interaction` [bmad-code-review] — Les chasseurs adversariaux livrent une 2e vague après leur 1er résultat — le triage du 2026-07-22 a failli se clore avant le finding le plus grave (boucle infinie prouvée)
- p2 `agent-mort` [famille:BMAD] — 30+ skills bmad-* toujours jamais invoquées 7 jours après l'install — seuls bmad-code-review et les 2 review-hunters ont un usage réel

### VSCode3 — Cadrage BMAD IAP (deck de synthèse) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode3`

Dernier scan superviseur local : 2026-07-23T12:45:13+02:00

**Skills utilisés** (9) : pptx-deck (2), artifact-design (2), agent-supervisor (2), agent-orchestrator (2), restitution-deck-design (1), pptx-verify (1), roadmap-keeper (1), revue-increment (1), bmad-agent-pm (1)

**Skills jamais utilisés** (48) : 45 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : general-purpose (31), ppt-designer (8), Explore (3), Plan (1), claude-code-guide (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Diagnostic superviseur local (findings ouverts)** :
- p3 `verification-manquante` [ppt-designer] — Fix shell ppt-designer jamais confirmé — la voie unique deck arbitrée est contournée par précédent
- p2 `interaction` [agent-orchestrator] — Le travail deck le plus lourd échappe au journal d'orchestration
- p1 `agent-mort` [tri-BMAD-retraits-D] — 6 retraits BMAD arbitrés le 2026-07-21 toujours physiquement présents

### VSCode4 — Deck OHC RH dispositifs d'écoute (pré-code) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode4`

Dernier scan superviseur local : 2026-07-23T18:06:24+02:00

**Skills utilisés** (7) : pptx-deck (3), agent-orchestrator (2), revue-increment (2), agent-supervisor (2), artifact-design (1), pptx-verify (1), bmad-correct-course (1)

**Skills jamais utilisés** (48) : 45 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : ppt-designer (3), general-purpose (1), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Diagnostic superviseur local (findings ouverts)** :
- p1 `verification-manquante` [ppt-designer] — Contournement du cadre photo des dividers de chapitre jamais re-questionné, malgré l'écart documenté au pattern VSCode3 que le dispositif est censé répliquer

### VScode5 — Supervision multi-projets (ce projet) [✅]

Chemin : `C:/Users/claude.camus/Documents/VScode5 - Supervision projets`

**Skills utilisés** (0) : —

**Skills jamais utilisés** (52) : 46 bmad-* + agent-orchestrator, agent-supervisor, deck-design-library, pptx-framed-image, slide-text-polish, veille-agentic

**Playbooks** : dev-verifie, export-ppt-verifie, revue-design-parallele

## 2. Veille agentic

_Dernière veille : 2026-07-23T18:10:00 — skill `veille-agentic` (cadence 3 jours, déclenchable manuellement)._

| Sujet | Type | Statut | Projets concernés | Pertinence |
| --- | --- | --- | --- | --- |
| [VoltAgent/awesome-claude-code-subagents — 154+ sous-agents en 10 catégories](https://github.com/VoltAgent/awesome-claude-code-subagents) | sous-agent | nouveau | VSCode1, VScode5 | Référentiel pour comparer/enrichir la flotte de 17 sous-agents de VSCode1 avant de la mutualiser via C4 — vérifier si des rôles manquants (security, data) y sont mieux définis. |
| [BMAD-METHOD — v7 en préparation (rewrite majeur) + uv devient le standard](https://github.com/bmad-code-org/BMAD-METHOD/releases) | framework | nouveau | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Les 6 projets sont en v6.10.0 avec 4-5 skills déjà marquées DEPRECATED-v7 ; la v7 (rewrite complet) est en early testing — anticiper la migration et ne pas customiser ce qui va disparaître. uv remplace python3 comme runtime standard des scripts BMAD. |
| [disler/claude-code-hooks-multi-agent-observability — observabilité multi-agents par hooks](https://github.com/disler/claude-code-hooks-multi-agent-observability) | outil | nouveau | VScode5 | Même pattern que notre dispositif maison (hooks → événements → dashboard) mais en temps réel avec swim lanes par agent — source d'inspiration directe pour faire évoluer scan_transcripts/log_usage/wiki.html. |
| [microsoft/hve-core — skill PowerPoint python-pptx pilotée par YAML](https://github.com/microsoft/hve-core/blob/main/.github/skills/experimental/powerpoint/SKILL.md) | skill | nouveau | VSCode1, VSCode2, VSCode3, VSCode4 | Approche content.yaml + style.yaml pour découpler contenu et mise en forme des decks — alternative structurée à comparer avec nos générateurs pptx_deck maison avant d'écrire le prochain. |
| [hesreallyhim/awesome-claude-code — index de référence de l'écosystème Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | rules | nouveau | VScode5 | Point d'entrée durable pour les prochaines sessions de veille (skills, agents, hooks, plugins triés à la main) — à re-parcourir à chaque cycle plutôt que de re-chercher à froid. |

