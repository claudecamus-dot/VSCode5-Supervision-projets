# Supervision multi-projets — agents, skills, playbooks

_Généré le 2026-07-24 17:43 par `scripts/scan_projets.py` — ne pas éditer à la main._

## Poste de pilotage

**6 projets** · **0 en alerte** (—) · **1 run(s) à solder** · **0 retard(s) de cadence**

**Runs `en-attente-validation` à solder** (valider ou requalifier) :
- [VScode5] il y a 7 h — Chantiers 1-9 : appliquer les 4 pratiques adoptees + package de deploiement + wiki site we

_Solder (dans le projet concerné) : `py .claude/orchestration/log_run.py --solde <prefixe-ts> succes "note de validation"`_

### Cadences

| Projet | Scan étage 1 | Diagnostic étage 2 | Dernier commit |
| --- | --- | --- | --- |
| VSCode | il y a 5 h | il y a 21 h | il y a 7 h |
| VSCode1 | il y a 3 h | il y a 1 j | il y a 7 h |
| VSCode2 | il y a 3 h | il y a 1 j | il y a 11 h |
| VSCode3 | il y a 5 h | il y a 1 j | il y a 7 h |
| VSCode4 | il y a 5 h | il y a 1 j | il y a 7 h |
| VScode5 | il y a 21 min | il y a 4 h | il y a 49 min |

Veille agentic : il y a 6 h (cadence 3 j).

## 1. Supervision des projets

| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 📊 [comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx](file:///C:/Users/claude.camus/Documents/VSCode/comop-pptx-prototype/output/comop-3f1c4b5c-a919-4aeb-a6c3-bd1dbe5bf2f6.pptx) | 6.10.0 (core+bmm+tea+bmb+cis) | 77 | 1 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode1 | 🌐 [http://localhost:3000](http://localhost:3000) | 6.10.0 (core+bmm) | 54 | 17 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode2 | 🌐 [http://127.0.0.1:8000/missions](http://127.0.0.1:8000/missions) | 6.10.0 (core+bmm) | 49 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode3 | 📊 [bmad-iap-cadrage-synthese.pptx](file:///C:/Users/claude.camus/Documents/VSCode3/docs/cadrage-ppt/bmad-iap-cadrage-synthese.pptx) | 6.10.0 (core+bmm) | 52 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode4 | 📊 [Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx](file:///C:/Users/claude.camus/Documents/VSCode4/Exports/Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx) | 6.10.0 (core+bmm) | 53 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VScode5 | 🌐 [wiki.html](file:///C:/Users/claude.camus/Documents/VScode5 - Supervision projets/docs/wiki.html) | 6.10.0 (core+bmm) | 53 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |

_Alerte : niveau du finding le plus haut du diagnostic superviseur local (p5 = critique, p4 = majeur)._

### VSCode — Bac à sable proto PPT (COMOP, Node.js) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode`

Dernier scan superviseur local : 2026-07-24T12:39:10+02:00

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

Dernier scan superviseur local : 2026-07-24T14:23:23+02:00

**Skills utilisés** (8) : revue-increment (5), run (4), roadmap-keeper (4), pptx-verify (3), skill-creator (3), agent-supervisor (3), artifact-design (2), agent-orchestrator (2)

**Skills jamais utilisés** (51) : 46 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, restitution-ppt, slide-text-polish

**Sous-agents** (17) : auditor, auditor-subagent, debugger, developer, developer-migrator, developer-refactor, documentarian, onboarder, orchestrator, orchestrator-dev, pathfinder, planner, ppt-designer, qa-engineer, reviewer, ui-designer, ux-designer
**Sous-agents utilisés** : ppt-designer (4), ux-designer (2), ui-designer (2), documentarian (1), onboarder (1), Explore (1), reviewer (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 16 (partiel ×1, succes ×15)

### VSCode2 — Interview-to-Deck (FastAPI) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode2`

Dernier scan superviseur local : 2026-07-24T14:23:29+02:00

**Skills utilisés** (16) : run-dev-server (21), agent-orchestrator (9), agent-supervisor (9), pptx-verify (7), revue-increment (7), bmad-code-review (7), update-config (6), roadmap-keeper (5), run (3), pptx-deck (2), skill-creator (2), slide-text-polish (2), init (1), claude-api (1), restitution-deck-design (1), deck-design-review (1)

**Skills jamais utilisés** (42) : 38 bmad-* + deck-design-library, pptx-framed-image, priority-matrix, swot-matrix

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 51 (partiel ×1, succes ×50)

### VSCode3 — Cadrage BMAD IAP (deck de synthèse) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode3`

Dernier scan superviseur local : 2026-07-24T12:39:14+02:00

**Skills utilisés** (9) : agent-orchestrator (3), pptx-deck (2), artifact-design (2), agent-supervisor (2), restitution-deck-design (1), pptx-verify (1), roadmap-keeper (1), revue-increment (1), bmad-agent-pm (1)

**Skills jamais utilisés** (48) : 45 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : general-purpose (31), ppt-designer (12), Explore (3), Plan (1), claude-code-guide (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 20 (succes ×20)

### VSCode4 — Deck OHC RH dispositifs d'écoute (pré-code) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode4`

Dernier scan superviseur local : 2026-07-24T12:39:15+02:00

**Skills utilisés** (7) : pptx-deck (3), agent-orchestrator (2), revue-increment (2), agent-supervisor (2), artifact-design (1), pptx-verify (1), bmad-correct-course (1)

**Skills jamais utilisés** (49) : 45 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : ppt-designer (3), general-purpose (1), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 15 (succes ×15)

**Diagnostic superviseur local (findings ouverts)** :
- p1 `verification-manquante` [ppt-designer] — Contournement du cadre photo des dividers de chapitre jamais re-questionné, malgré l'écart documenté au pattern VSCode3 que le dispositif est censé répliquer

### VScode5 — Supervision multi-projets (ce projet) [✅]

Chemin : `C:/Users/claude.camus/Documents/VScode5 - Supervision projets`

Dernier scan superviseur local : 2026-07-24T17:21:51+02:00

**Skills utilisés** (4) : agent-orchestrator (35), agent-supervisor (5), audit-technique (3), update-config (1)

**Skills jamais utilisés** (50) : 46 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish, veille-agentic

**Playbooks** : dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 26 (en-attente-validation ×1, succes ×25)

**Diagnostic superviseur local (findings ouverts)** :
- p3 `verification-manquante` [audit-technique:VScode5] — Audit securite VScode5 perime face a la nouvelle surface serve_wiki.py
- p3 `pratique-test` [VScode5] — VScode5 reste rouge sur test fonctionnel malgre un vrai site web jamais couvert par un test permanent
- p2 `pratique-revue` [VScode5] — VScode5 n a jamais adopte sur lui-meme la revue qu il propage a toute la flotte
- p2 `ko-repete` [non_invocation_skills] — tests/test_canon.py ne couvre pas la fonction qui a casse deux fois

## 2. Pratiques, couverture & risques

_Cible : le [référentiel de critères](technical/criteres-pratiques.md) (DORA, pyramide de tests/ISO 25010, Diátaxis, Cagan/Torres, OWASP ASVS/SAMM, DAMA-DMBOK) — ce qui suit est la MESURE ; l'écart mesure↔référentiel alimente les findings `pratique-*` du superviseur._

### Référentiel des pratiques supervisées

_Les 13 pratiques mesurées, avec la règle de notation et le référentiel cible (déplié ici ; replié dans `docs/wiki.html`)._

#### Pratiques craft (développement)

_🟢 implémenté & mesuré · 🟠 partiel · 🔴 pas encore outillé._

| Pratique | Principe | Dans la flotte | Mesure |
| --- | --- | --- | --- |
| 🟢 Gestion de version pour tout | Code, config et scripts sous contrôle de version, historique propre. | 6/6 en dépôt git ; règle R2 « commit scopé au périmètre » (hub). | Cadence dernier commit + détection de dette non commitée. |
| 🟠 Petits commits scopés | Commits atomiques, un changement = un commit, message clair. | Règle CLAUDE.md (R2) ; discipline, appliquée au cas par cas. | ⬜ non auto-détecté (taille/scope des commits non mesurés). |
| 🟢 Tests automatisés (dont TDD) | Tests unitaires rapides sur la logique métier, écrits tôt. | Fichiers de test + couverture (VSCode1 84,7 % / VSCode2 ~38 %). | Dimension Test technique (compte de tests + coverage). |
| 🟢 Tests fonctionnels bout-en-bout réels | Vérifier l'artefact RÉEL (rendu, PDF re-parsé, navigateur), pas un mock. | Marqueurs puppeteer/playwright/pymupdf/Presentation(/TestClient. | Dimension Test fonctionnel / rendu réel. |
| 🟠 Intégration continue | Build + tests rejoués à chaque push, feedback rapide. | CI GitHub Actions présente sur VSCode1 seulement (1/6). | Dimension Pratiques + rules (présence .github/workflows). |
| 🟢 Revue de code systématique | Tout changement relu avant merge/commit (4 yeux ou outil). | Agent reviewer + hook pré-commit (VSCode1) ; bmad-code-review ailleurs. | Dimension Revue de code. |
| 🟢 Revue d'incrément | Fin d'itération : diff relu, exigences recochées avant de clore. | Skill revue-increment + hook SessionStart de rappel. | Dimension Revue d'incrément. |
| 🟠 Analyse statique / linter | Style et erreurs détectés automatiquement (ruff, ESLint). | ESLint (JS) sur VSCode1 ; aucun linter Python sur la flotte (finding ouvert). | Dimension Pratiques + rules (présence linter). |
| 🟢 Refactoring continu / dette maîtrisée | Boy-scout rule : laisser le code plus propre, dette suivie. | Constatée à la lecture du code (duplication, couplage, code mort). | Audit qualitatif — dimension Risque technique. |
| 🟢 Simple design / YAGNI | Le design le plus simple qui passe les tests, pas de code mort. | Code mort et sur-ingénierie relevés à l'audit. | Audit qualitatif — dimension Risque technique. |
| 🟢 Dépendances épinglées / build reproductible | Versions figées (lockfile), build déterministe. | Lockfile OK sur VSCode1 ; VSCode2 en `>=` (constat d'audit). | Audit qualitatif — dimension Risque technique. |
| 🟢 Conventions de code explicites | Règles partagées écrites (nommage, structure, rules d'agent). | CLAUDE.md + conventions.md sur les projets outillés. | Dimension Pratiques + rules (CLAUDE.md, conventions). |
| 🔴 Trunk-based development | Branches courtes (< 3 actives), intégration fréquente au tronc. | Non outillé — mesurable via `git branch` (écart à combler). | ⬜ pas encore mesuré (cible du référentiel § 1). |
| 🔴 Automatisation du déploiement | Déploiement scripté et rejouable, pas d'étape manuelle. | Aucun projet outillé — pertinence à évaluer (projets locaux). | ⬜ pas mesuré (cible du référentiel § 1). |
| 🔴 Test de non-régression sur bug corrigé | Chaque bug fermé laisse un test qui échouerait s'il revenait. | Discipline à documenter dans les conventions — non détectable. | ⬜ non détectable automatiquement (cible § 2). |

_Source : référentiel § 1 (DORA) & § 2 (pyramide de tests) + dimensions du scan._

**Étage déterministe (à chaque scan, 0 token)**

- **Test technique** — Compte les fichiers de test unitaires/techniques (motifs test_*, *_test, *.spec/*.test) et détecte une couverture configurée (pytest-cov, coverage, nyc, --cov). _Notation :_ 🟢 ok = ≥ 3 fichiers de test ET couverture configurée ; 🟠 moyen = ≥ 1 fichier de test ; 🔴 absent = aucun test alors qu'il y a du code de prod ; ⚪ n/a = le projet n'a pas de code applicatif. _Réf. :_ Pyramide de tests + ISO/IEC 25010 (§ 2 du référentiel).
- **Test fonctionnel / rendu réel** — Parmi les tests, ceux qui vérifient l'artefact RÉEL : marqueurs puppeteer, playwright, win32com/comtypes, soffice/LibreOffice, pymupdf/fitz, Presentation(, TestClient, smoke. _Notation :_ 🟢 ok = ≥ 2 tests à vérification réelle ; 🟠 moyen = ≥ 1 test à vérification réelle ; 🔴 absent = aucune vérif fonctionnelle réelle détectée. _Réf. :_ e2e réels de la pyramide — tester le livrable, pas seulement la logique (§ 2).
- **Revue de code** — Présence d'un dispositif de revue : agent reviewer dédié OU hook pré-commit warn_verif_before_commit.py (fort) ; skill bmad-code-review générique (faible). _Notation :_ 🟢 ok = agent reviewer OU hook pré-commit présent ; 🟠 moyen = bmad-code-review seul (générique, non forcé) ; 🔴 absent = aucun dispositif de revue. _Réf. :_ DORA — revue systématique avant merge/commit (§ 1).
- **Revue d'incrément** — Skill revue-increment + son hook SessionStart (remind_revue_increment) qui la rappelle en cadence. _Notation :_ 🟢 ok = skill + hook SessionStart ; 🟠 moyen = skill seule (pas de rappel automatique) ; 🔴 absent = pas de revue d'incrément. _Réf. :_ Cadence de revue de fin d'incrément (leçon flotte — diff relu, exigences recochées).
- **Pratique de design (deck)** — Pour les projets à livrable deck : discipline de design de slide — deck-design-review (contrat par slide) + deck-design-library ; à défaut agent ppt-designer. _Notation :_ 🟢 ok = deck-design-review ET deck-design-library ; 🟠 moyen = deck-design-library OU ppt-designer seul ; 🔴 absent = aucune discipline de design ; ⚪ n/a = le projet ne produit pas de deck. _Réf. :_ Design par contrat de slide, pas par impression (companion restitution-deck-design).
- **Documentation** — Porte d'entrée et référence : README avec section install/usage, wiki (docs/wiki), CLAUDE.md. _Notation :_ 🟢 ok = ≥ 2 dispositifs dont un README avec install/usage ; 🟠 moyen = au moins un README, wiki ou CLAUDE.md ; 🔴 absent = aucune documentation. _Réf. :_ Diátaxis — tutorial / how-to / référence / explication (§ 3).
- **Cadrage produit** — Marqueurs de discovery dans docs/cadrage/_bmad-output : persona, why/problème, besoins/pain points, proposition de valeur, + artefact product-brief/PRD BMAD. _Notation :_ 🟢 ok = ≥ 3 marqueurs de cadrage (ou marqueurs + brief BMAD) ; 🟠 moyen = ≥ 1 marqueur ; 🔴 absent = aucun artefact de cadrage produit. _Réf. :_ 4 risques de Cagan + Opportunity Solution Tree de Torres (§ 4).
- **Pratiques + rules** — Outillage projet : linter (ruff/ESLint/flake8/prettier/pyproject), CI (.github/workflows), CLAUDE.md, conventions.md. _Notation :_ 🟢 ok = ≥ 3 des 4 dispositifs ; 🟠 moyen = ≥ 1 dispositif ; 🔴 absent = rien de configuré. _Réf. :_ DORA capabilities — version control, linter, CI, rules explicites (§ 1).
- **Sécurité (proxy)** — Garde-fous PRÉSENTS (pas un audit de failles) : .env gitigné, deny rules dans settings.json, hook guard_destructive_git. Alerte si un .env est commité. _Notation :_ 🟢 ok = ≥ 2 garde-fous présents ; 🟠 moyen = ≥ 1 garde-fou ; 🔴 absent = aucun garde-fou — ou .env non gitigné. _Réf. :_ OWASP ASVS 5.0 + SAMM — proxy de maturité, l'audit qualitatif cherche les failles réelles (§ 5).

**Étage qualitatif (audit-technique à la demande)**

- **Robustesse** — Lecture du code : gestion d'erreur, cas limites, entrées non validées, échecs silencieux (except: pass), idempotence, absence de rollback. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ ISO 25010 (fiabilité) + tests d'erreur/cas limites (§ 2).
- **Performance** — Lecture du code : boucles imbriquées sur gros volumes, I/O dans une boucle, requêtes N+1, absence de cache/pagination, rendu synchrone bloquant. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ ISO 25010 (efficacité de performance).
- **Risque technique** — Lecture du code : dette structurelle — duplication logique, couplage fort, dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ DORA — build reproductible, dépendances épinglées (§ 1).
- **Sécurité (audit)** — Lecture du code : secrets en clair/commités, injection (SQL/commande/template), désérialisation non sûre (eval/pickle), chemins utilisateur non assainis, shell=True, permissions trop larges. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ OWASP ASVS 5.0 (~350 exigences, 17 chapitres) + SAMM (§ 5).

**Étage déterministe** (mesuré à chaque scan, 0 token — présence de dispositifs) :

| Projet | Test tech. | Test fonct. | Revue code | Revue incr. | Design | Doc | Cadrage produit | Pratiques+rules | Sécu (proxy) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 🟠 5 fichier(s) de test, pas de coverage | 🟢 2 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟠 deck-design-library, ppt-designer | 🟠 wiki, CLAUDE.md | 🟠 besoins + brief BMAD | 🟠 CLAUDE.md | 🟢 .env gitigné, deny rules, guard git |
| VSCode1 | 🟠 11 fichier(s) de test, pas de coverage | 🟠 1 test(s) à vérification réelle | 🟢 agent reviewer, hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟠 persona, why | 🟢 linter, CI, CLAUDE.md, conventions | 🟢 deny rules, guard git |
| VSCode2 | 🟢 31 fichier(s) de test, coverage configuré | 🟢 17 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library | 🟢 README+usage, wiki+html, CLAUDE.md | 🟠 persona, besoins | 🟢 linter, CI, CLAUDE.md, conventions | 🟢 .env gitigné, deny rules, guard git |
| VSCode3 | 🟠 3 fichier(s) de test, pas de coverage | 🟢 2 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟠 deck-design-library, ppt-designer | 🟠 wiki+html, CLAUDE.md | 🟠 why | 🟠 CLAUDE.md, conventions | 🟢 deny rules, guard git |
| VSCode4 | 🟠 1 fichier(s) de test, pas de coverage | 🟠 1 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟠 wiki+html, CLAUDE.md | 🔴 aucun artefact de cadrage produit détecté | 🟠 CLAUDE.md | 🟢 .env gitigné, deny rules, guard git |
| VScode5 | 🟠 4 fichier(s) de test, pas de coverage | 🔴 aucune vérif fonctionnelle réelle détectée | 🟢 hook pré-commit, bmad-code-review | 🔴 absente | ⚪ ne produit pas de deck | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟠 linter, CLAUDE.md | 🟢 deny rules, guard git |

🟢 ok · 🟠 moyen · 🔴 absent/manquant · ⚪ non applicable. Sécu (proxy) = garde-fous présents (.env gitigné, deny rules, guard git), PAS un audit de failles.

**Étage qualitatif** (audit `audit-technique` à la demande — lit le code) :

_Ce que couvre l'audit (chaque dimension = lecture du code réel, findings localisés `fichier:ligne`, niveau ok / moyen / critique) :_

- **Robustesse** — gestion d'erreur, cas limites, entrées non validées, échecs silencieux (`except: pass`), idempotence, absence de rollback.
- **Performance** — boucles imbriquées sur gros volumes, I/O dans une boucle, requêtes N+1, absence de cache/pagination, rendu synchrone bloquant.
- **Risque technique** — dette structurelle : duplication logique, couplage fort, dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test.
- **Sécurité** — secrets en clair/commités, injection (SQL/commande/template), désérialisation non sûre (`eval`/`pickle`), chemins utilisateur non assainis, `shell=True`, permissions trop larges.

| Projet | Robustesse | Perf. | Risque tech. | Sécurité | Audité le |
| --- | --- | --- | --- | --- | --- |
| VSCode | 🟢 ok | 🟢 ok | 🟠 moyen | 🟠 moyen | 2026-07-23 |
| VSCode1 | 🟢 ok | 🟠 moyen | 🟠 moyen | 🟠 moyen | 2026-07-23 |
| VSCode2 | 🟢 ok | 🟠 moyen | 🟠 moyen | 🟢 ok | 2026-07-23 |
| VSCode3 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-23 |
| VSCode4 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-23 |
| VScode5 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-24 |

_Lancer un audit : skill `audit-technique` sur le projet cible (robustesse, performance, risque technique, failles de sécurité — lecture du code)._

## 3. Veille agentic

_Dernière veille : 2026-07-24T10:45:00 — skill `veille-agentic` (cadence 3 jours, déclenchable manuellement)._

| Sujet | Type | Statut | Projets concernés | Pertinence |
| --- | --- | --- | --- | --- |
| [VoltAgent/awesome-claude-code-subagents — 154+ sous-agents en 10 catégories](https://github.com/VoltAgent/awesome-claude-code-subagents) | sous-agent | nouveau | VSCode1, VScode5 | Référentiel pour comparer/enrichir la flotte de 17 sous-agents de VSCode1 avant de la mutualiser via C4 — vérifier si des rôles manquants (security, data) y sont mieux définis. |
| [BMAD-METHOD — v7 en préparation (rewrite majeur) + uv devient le standard](https://github.com/bmad-code-org/BMAD-METHOD/releases) | framework | nouveau | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Les 6 projets sont en v6.10.0 avec 4-5 skills déjà marquées DEPRECATED-v7 ; la v7 (rewrite complet) est en early testing — anticiper la migration et ne pas customiser ce qui va disparaître. uv remplace python3 comme runtime standard des scripts BMAD. |
| [disler/claude-code-hooks-multi-agent-observability — observabilité multi-agents par hooks](https://github.com/disler/claude-code-hooks-multi-agent-observability) | outil | nouveau | VScode5 | Même pattern que notre dispositif maison (hooks → événements → dashboard) mais en temps réel avec swim lanes par agent — source d'inspiration directe pour faire évoluer scan_transcripts/log_usage/wiki.html. |
| [microsoft/hve-core — skill PowerPoint python-pptx pilotée par YAML](https://github.com/microsoft/hve-core/blob/main/.github/skills/experimental/powerpoint/SKILL.md) | skill | nouveau | VSCode1, VSCode2, VSCode3, VSCode4 | Approche content.yaml + style.yaml pour découpler contenu et mise en forme des decks — alternative structurée à comparer avec nos générateurs pptx_deck maison avant d'écrire le prochain. |
| [hesreallyhim/awesome-claude-code — index de référence de l'écosystème Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | rules | nouveau | VScode5 | Point d'entrée durable pour les prochaines sessions de veille (skills, agents, hooks, plugins triés à la main) — à re-parcourir à chaque cycle plutôt que de re-chercher à froid. |

### Pratiques agentic repérées (docs providers)

_Volet 2 de `veille-agentic` : pratiques recommandées par les providers, comparées à l'état réel de la flotte. `adopte` (décision utilisateur) => la règle proposée entre au référentiel (`criteres-pratiques.md` § 7) et l'action corrective se traite via `evolution-flotte`._

| Pratique | Source | Statut | Projets | Règle d'analyse proposée | Action corrective |
| --- | --- | --- | --- | --- | --- |
| [Vérification exécutable fournie à l'agent (checks déterministes, Stop/pré-commit hooks)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Give Claude a way to verify its work ») | adopte | VSCode, VSCode3, VSCode4 | Critère scan (dimension revue de code) : hook de vérification pré-commit présent (warn_verif_before_commit ou équivalent) — pas seulement une skill de revue invocable. | Propager warn_verif_before_commit à VSCode/VSCode3/VSCode4 (adapté au canal de chaque projet), via evolution-flotte. |
| [CLAUDE.md concis, entretenu comme du code (pruning régulier)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Write an effective CLAUDE.md », « The over-specified CLAUDE.md ») | adopte | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Critère scan (dimension pratiques + rules) : taille du CLAUDE.md bornée (alerte au-delà d'un seuil, ex. 150 lignes) — mesurable à froid, 0 token. | Passe de pruning des CLAUDE.md de la flotte : chaque ligne justifiée par « sa suppression causerait-elle une erreur ? », convertir en hook ce qui doit être garanti. |
| [Revue adversariale en contexte frais avant de clore (reviewer ≠ implémenteur)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Add an adversarial review step ») + Writer/Reviewer pattern | adopte | VSCode, VSCode3, VSCode4, VScode5 | Règle playbooks : toute orchestration qui commit porte une étape terminale de revue en contexte frais (sous-agent sur le diff), tracée dans le plan du run. | Ancrer l'étape « revue contexte frais » dans les playbooks evolution-flotte et export-ppt-verifie (dev-verifie l'a déjà), et le vérifier au diagnostic étage 2 (catégorie verification-manquante). |
| [Guardrails en couches pour actions irréversibles (défense combinée, pas un garde unique)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | OpenAI — A practical guide to building agents (guardrails en couches, tool-specific risk controls) | adopte | VScode5 | Critère scan (dimension sécurité proxy) : les projets qui ÉCRIVENT sur d'autres dépôts exigent le niveau complet (deny rules + guard destructif + .env gitigné), pas un garde unique. | Aligner les settings du hub : ajouter les deny rules manquantes (webhooks/secrets/curl destructif) au niveau des autres projets de la flotte. |
| [Gestion du contexte outillée : statusline de suivi, /compact cadré, sous-agents d'exploration](https://code.claude.com/docs/en/costs) | Anthropic — Claude Code docs (reduce token usage, context window) + best practices (context is the fundamental constraint) | nouveau | VSCode, VSCode2, VSCode4, VScode5 | Critère scan (dimension pratiques + rules) : discipline tokens écrite dans le CLAUDE.md/conventions du projet (marqueurs /compact, sous-agent, lecture ciblée) — mesurable 0 token. | Propager la section « optimisation tokens » (modèle VSCode1/VSCode3, adaptée au canal) aux CLAUDE.md de VSCode/VSCode2/VSCode4/VScode5 ; mesurer le gain rtk (rtk gain --history) à chaque veille et le reporter dans le wiki. |

