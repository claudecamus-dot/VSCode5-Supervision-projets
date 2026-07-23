# Supervision multi-projets — agents, skills, playbooks

_Généré le 2026-07-23 22:15 par `scripts/scan_projets.py` — ne pas éditer à la main._

## Poste de pilotage

**6 projets** · **0 en alerte** (—) · **3 run(s) à solder** · **0 retard(s) de cadence**

**Runs `en-attente-validation` à solder** (valider ou requalifier) :
- [VScode5] il y a 52 min — analyse pratiques dev/test + revue + robustesse/perf/risque/securite sur les 6 projets
- [VScode5] il y a 41 min — rajouter dans agent-supervisor l audit des pratiques de test, dev, revue, design
- [VScode5] il y a 18 min — rajouter analyse documentation + pratiques produit/cadrage (persona/why/besoins/propositio

_Solder (dans le projet concerné) : `py .claude/orchestration/log_run.py --solde <prefixe-ts> succes "note de validation"`_

### Cadences

| Projet | Scan étage 1 | Diagnostic étage 2 | Dernier commit |
| --- | --- | --- | --- |
| VSCode | il y a 0 min | il y a 1 h | il y a 56 min |
| VSCode1 | il y a 0 min | il y a 15 h | il y a 25 min |
| VSCode2 | il y a 0 min | il y a 17 h | il y a 25 min |
| VSCode3 | il y a 0 min | il y a 15 h | il y a 1 h |
| VSCode4 | il y a 0 min | il y a 5 h | il y a 1 h |
| VScode5 | il y a 0 min | il y a 19 min | il y a 18 min |

Veille agentic : il y a 4 h (cadence 3 j).

## 1. Supervision des projets

| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 📊 [comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx](file:///C:/Users/claude.camus/Documents/VSCode/comop-pptx-prototype/output/comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx) | 6.10.0 (core+bmm+tea+bmb+cis) | 77 | 1 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode1 | 🌐 [http://localhost:3000](http://localhost:3000) | 6.10.0 (core+bmm) | 54 | 17 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode2 | 🌐 [http://127.0.0.1:8000/missions](http://127.0.0.1:8000/missions) | 6.10.0 (core+bmm) | 49 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode3 | 📊 [bmad-iap-cadrage-synthese.pptx](file:///C:/Users/claude.camus/Documents/VSCode3/docs/cadrage-ppt/bmad-iap-cadrage-synthese.pptx) | 6.10.0 (core+bmm) | 52 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode4 | 📊 [Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx](file:///C:/Users/claude.camus/Documents/VSCode4/Exports/Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx) | 6.10.0 (core+bmm) | 52 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VScode5 | 🌐 [wiki.html](file:///C:/Users/claude.camus/Documents/VScode5 - Supervision projets/docs/wiki.html) | 6.10.0 (core+bmm) | 53 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |

_Alerte : niveau du finding le plus haut du diagnostic superviseur local (p5 = critique, p4 = majeur)._

### VSCode — Bac à sable proto PPT (COMOP, Node.js) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode`

Dernier scan superviseur local : 2026-07-23T22:15:33+02:00

**Skills utilisés** (0) : —

**Skills jamais utilisés** (77) : 71 bmad-* + agent-orchestrator, agent-supervisor, deck-design-library, pptx-framed-image, revue-increment, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : Explore (1)

**Playbooks** : dev-verifie, export-ppt-verifie, revue-design-parallele

**Diagnostic superviseur local (findings ouverts)** :
- p3 `verification-manquante` [revue-increment] — Increment 6 cloture alors qu'une regression PPTX bloquante est capitalisee, sans passage revue-increment
- p3 `inefficacite` [scan_transcripts] — Etage-1 diagnostique a l'aveugle : 0 session couverte, state/runs vides -> jamais_utilises est un artefact de donnees vides
- p2 `agent-mort` [bmad-catalogue-codex] — Duplication .agents/skills/ (Codex) : poids mort structurel, independant du scan

### VSCode1 — Questionnaire maturité agile/produit + export PPT [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode1`

Dernier scan superviseur local : 2026-07-23T22:15:33+02:00

**Skills utilisés** (8) : revue-increment (5), run (4), roadmap-keeper (4), pptx-verify (3), skill-creator (3), agent-supervisor (3), artifact-design (2), agent-orchestrator (2)

**Skills jamais utilisés** (51) : 46 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, restitution-ppt, slide-text-polish

**Sous-agents** (17) : auditor, auditor-subagent, debugger, developer, developer-migrator, developer-refactor, documentarian, onboarder, orchestrator, orchestrator-dev, pathfinder, planner, ppt-designer, qa-engineer, reviewer, ui-designer, ux-designer
**Sous-agents utilisés** : ppt-designer (4), ux-designer (2), ui-designer (2), documentarian (1), onboarder (1), Explore (1), reviewer (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 16 (partiel ×1, succes ×15)

### VSCode2 — Interview-to-Deck (FastAPI) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode2`

Dernier scan superviseur local : 2026-07-23T22:15:35+02:00

**Skills utilisés** (16) : run-dev-server (21), agent-orchestrator (9), agent-supervisor (9), pptx-verify (7), revue-increment (7), bmad-code-review (7), update-config (6), roadmap-keeper (5), run (3), pptx-deck (2), skill-creator (2), slide-text-polish (2), init (1), claude-api (1), restitution-deck-design (1), deck-design-review (1)

**Skills jamais utilisés** (42) : 38 bmad-* + deck-design-library, pptx-framed-image, priority-matrix, swot-matrix

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 51 (partiel ×1, succes ×50)

### VSCode3 — Cadrage BMAD IAP (deck de synthèse) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode3`

Dernier scan superviseur local : 2026-07-23T22:15:35+02:00

**Skills utilisés** (9) : agent-orchestrator (3), pptx-deck (2), artifact-design (2), agent-supervisor (2), restitution-deck-design (1), pptx-verify (1), roadmap-keeper (1), revue-increment (1), bmad-agent-pm (1)

**Skills jamais utilisés** (48) : 45 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : general-purpose (31), ppt-designer (12), Explore (3), Plan (1), claude-code-guide (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 20 (succes ×20)

### VSCode4 — Deck OHC RH dispositifs d'écoute (pré-code) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode4`

Dernier scan superviseur local : 2026-07-23T22:15:36+02:00

**Skills utilisés** (7) : pptx-deck (3), agent-orchestrator (2), revue-increment (2), agent-supervisor (2), artifact-design (1), pptx-verify (1), bmad-correct-course (1)

**Skills jamais utilisés** (48) : 45 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : ppt-designer (3), general-purpose (1), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 15 (succes ×15)

**Diagnostic superviseur local (findings ouverts)** :
- p1 `verification-manquante` [ppt-designer] — Contournement du cadre photo des dividers de chapitre jamais re-questionné, malgré l'écart documenté au pattern VSCode3 que le dispositif est censé répliquer

### VScode5 — Supervision multi-projets (ce projet) [✅]

Chemin : `C:/Users/claude.camus/Documents/VScode5 - Supervision projets`

Dernier scan superviseur local : 2026-07-23T22:15:36+02:00

**Skills utilisés** (2) : agent-orchestrator (3), agent-supervisor (1)

**Skills jamais utilisés** (51) : 46 bmad-* + audit-technique, deck-design-library, pptx-framed-image, slide-text-polish, veille-agentic

**Playbooks** : dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 13 (en-attente-validation ×3, succes ×10)

**Diagnostic superviseur local (findings ouverts)** :
- p3 `pratique-dev` [famille:linter] — Aucun linter Python sur la flotte (pyproject.toml inexistant partout) alors que 5/6 ont du code Python ; seul VSCode1 a un linter (ESLint, JS)
- p3 `pratique-revue` [famille:revue-code] — La revue de code outillee (agent reviewer + hook pre-commit) n'existe que sur VSCode1 ; les 5 autres n'ont que bmad-code-review generique, jamais force avant commit
- p2 `pratique-design` [famille:design-review] — 3 projets a deck (VSCode, VSCode3, VSCode4) n'ont pas deck-design-review — revue de design par impression, pas par contrat de slide
- p2 `pratique-produit` [famille:cadrage-produit] — 2 projets (VSCode4, VScode5) n'ont aucun artefact de cadrage produit (persona, why, besoins, proposition de valeur) ; les autres n'en ont que des fragments

## 2. Pratiques, couverture & risques

**Étage déterministe** (mesuré à chaque scan, 0 token — présence de dispositifs) :

| Projet | Test tech. | Test fonct. | Revue code | Revue incr. | Design | Doc | Cadrage produit | Pratiques+rules | Sécu (proxy) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 🟠 1 fichier(s) de test, pas de coverage | 🟠 1 test(s) à vérification réelle | 🟠 bmad-code-review | 🟢 skill + hook SessionStart | 🟠 deck-design-library, ppt-designer | 🟠 wiki, CLAUDE.md | 🟠 besoins + brief BMAD | 🟠 CLAUDE.md | 🟢 .env gitigné, deny rules, guard git |
| VSCode1 | 🟠 10 fichier(s) de test, pas de coverage | 🟠 1 test(s) à vérification réelle | 🟢 agent reviewer, hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟠 persona, why | 🟢 linter, CI, CLAUDE.md, conventions | 🟢 deny rules, guard git |
| VSCode2 | 🟢 31 fichier(s) de test, coverage configuré | 🟢 17 test(s) à vérification réelle | 🟠 bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library | 🟢 README+usage, wiki+html, CLAUDE.md | 🟠 persona, besoins | 🟠 CLAUDE.md, conventions | 🟢 .env gitigné, deny rules, guard git |
| VSCode3 | 🟠 3 fichier(s) de test, pas de coverage | 🟢 2 test(s) à vérification réelle | 🟠 bmad-code-review | 🟢 skill + hook SessionStart | 🟠 deck-design-library, ppt-designer | 🟠 wiki+html, CLAUDE.md | 🟠 why | 🟠 CLAUDE.md, conventions | 🟢 deny rules, guard git |
| VSCode4 | 🟠 1 fichier(s) de test, pas de coverage | 🟠 1 test(s) à vérification réelle | 🟠 bmad-code-review | 🟢 skill + hook SessionStart | 🟠 deck-design-library, ppt-designer | 🟠 wiki+html, CLAUDE.md | 🔴 aucun artefact de cadrage produit détecté | 🟠 CLAUDE.md | 🟢 .env gitigné, deny rules, guard git |
| VScode5 | 🔴 0 fichier(s) de test, pas de coverage | 🔴 aucune vérif fonctionnelle réelle détectée | 🟠 bmad-code-review | 🔴 absente | ⚪ ne produit pas de deck | 🟢 README+usage, wiki+html, CLAUDE.md | 🔴 aucun artefact de cadrage produit détecté | 🟠 CLAUDE.md | 🟠 guard git |

🟢 ok · 🟠 moyen · 🔴 absent/manquant · ⚪ non applicable. Sécu (proxy) = garde-fous présents (.env gitigné, deny rules, guard git), PAS un audit de failles.

**Étage qualitatif** (audit `audit-technique` à la demande — lit le code) :

| Projet | Robustesse | Perf. | Risque tech. | Sécurité | Audité le |
| --- | --- | --- | --- | --- | --- |
| VSCode | ⚪ non audité | ⚪ non audité | ⚪ non audité | ⚪ non audité | — |
| VSCode1 | ⚪ non audité | ⚪ non audité | ⚪ non audité | ⚪ non audité | — |
| VSCode2 | ⚪ non audité | ⚪ non audité | ⚪ non audité | ⚪ non audité | — |
| VSCode3 | ⚪ non audité | ⚪ non audité | ⚪ non audité | ⚪ non audité | — |
| VSCode4 | ⚪ non audité | ⚪ non audité | ⚪ non audité | ⚪ non audité | — |
| VScode5 | 🟠 moyen | 🟠 moyen | 🔴 critique | 🟢 ok | 2026-07-23 |

_Lancer un audit : skill `audit-technique` sur le projet cible (robustesse, performance, risque technique, failles de sécurité — lecture du code)._

## 3. Veille agentic

_Dernière veille : 2026-07-23T18:10:00 — skill `veille-agentic` (cadence 3 jours, déclenchable manuellement)._

| Sujet | Type | Statut | Projets concernés | Pertinence |
| --- | --- | --- | --- | --- |
| [VoltAgent/awesome-claude-code-subagents — 154+ sous-agents en 10 catégories](https://github.com/VoltAgent/awesome-claude-code-subagents) | sous-agent | nouveau | VSCode1, VScode5 | Référentiel pour comparer/enrichir la flotte de 17 sous-agents de VSCode1 avant de la mutualiser via C4 — vérifier si des rôles manquants (security, data) y sont mieux définis. |
| [BMAD-METHOD — v7 en préparation (rewrite majeur) + uv devient le standard](https://github.com/bmad-code-org/BMAD-METHOD/releases) | framework | nouveau | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Les 6 projets sont en v6.10.0 avec 4-5 skills déjà marquées DEPRECATED-v7 ; la v7 (rewrite complet) est en early testing — anticiper la migration et ne pas customiser ce qui va disparaître. uv remplace python3 comme runtime standard des scripts BMAD. |
| [disler/claude-code-hooks-multi-agent-observability — observabilité multi-agents par hooks](https://github.com/disler/claude-code-hooks-multi-agent-observability) | outil | nouveau | VScode5 | Même pattern que notre dispositif maison (hooks → événements → dashboard) mais en temps réel avec swim lanes par agent — source d'inspiration directe pour faire évoluer scan_transcripts/log_usage/wiki.html. |
| [microsoft/hve-core — skill PowerPoint python-pptx pilotée par YAML](https://github.com/microsoft/hve-core/blob/main/.github/skills/experimental/powerpoint/SKILL.md) | skill | nouveau | VSCode1, VSCode2, VSCode3, VSCode4 | Approche content.yaml + style.yaml pour découpler contenu et mise en forme des decks — alternative structurée à comparer avec nos générateurs pptx_deck maison avant d'écrire le prochain. |
| [hesreallyhim/awesome-claude-code — index de référence de l'écosystème Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | rules | nouveau | VScode5 | Point d'entrée durable pour les prochaines sessions de veille (skills, agents, hooks, plugins triés à la main) — à re-parcourir à chaque cycle plutôt que de re-chercher à froid. |

