# Supervision multi-projets — agents, skills, playbooks

_Généré le 2026-07-31 20:10 par `scripts/scan_projets.py` — ne pas éditer à la main._

## Poste de pilotage

**6 projets** · **1 en alerte** (VSCode2 🟠 majeur) · **5 pratique(s) en écart** · **2 finding(s) ouvert(s)** · **6 run(s) à solder** · **0 retard(s) de cadence**

_Depuis le scan précédent (2026-07-31 20:06) : pratiques en écart, findings, runs à solder, retards._

**À arbitrer (onglet Actions correctives)** :
- 🔴 VSCode4 : 2 pratique(s) en écart + 1 finding(s) ouvert(s)
- 🔴 VSCode2 : 1 finding(s) ouvert(s)
- 🟠 VSCode : 1 pratique(s) en écart
- 🟠 VSCode1 : 1 pratique(s) en écart
- 🟠 VSCode3 : 1 pratique(s) en écart

**Runs `en-attente-validation` à solder** (valider ou requalifier) :
- [VSCode2] il y a 7 h — Garantir l'enregistrement audio/transcription (entretien a distance Meet/Teams inclus) ou 
- [VScode5] il y a 5 h — Lever le gel bmad-customize, creer la party elargie et documenter son schema au wiki
- [VScode5] il y a 4 h — Mettre en place le systeme de table ronde, corriger le test instable, relancer le supervis
- [VScode5] il y a 4 h — Cabler les actions des onglets veille / actions / correctifs / deploiement / exports au la
- [VScode5] il y a 4 h — Reflexion de reorganisation du site (regrouper les onglets, reduire le scroll) + salle d'i
- [VScode5] il y a 3 h — UX du site : meilleure lecture, replier le peu consulte, approfondir le schema avec salles

_Solder (dans le projet concerné) : `py .claude/orchestration/log_run.py --solde <prefixe-ts> succes "note de validation"`_

### Cadences

| Projet | Scan étage 1 | Diagnostic étage 2 | Dernier commit |
| --- | --- | --- | --- |
| VSCode | il y a 0 min | il y a 4 j | il y a 1 j |
| VSCode1 | il y a 0 min | il y a 3 j | il y a 3 h |
| VSCode2 | il y a 0 min | il y a 2 j | il y a 3 h |
| VSCode3 | il y a 0 min | il y a 8 j | il y a 1 j |
| VSCode4 | il y a 0 min | il y a 8 j | il y a 1 j |
| VScode5 | il y a 0 min | il y a 4 h | il y a 3 h |

Veille agentic : il y a 2 j (cadence 3 j).

## 1. Supervision des projets

| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 📊 [comop-verifie-2026-07-28.pptx](file:///C:/Users/claude.camus/Documents/VSCode/comop-pptx-prototype/output/comop-verifie-2026-07-28.pptx) | 6.10.0 (core+bmm+tea+bmb+cis) | 78 | 1 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode1 | 🌐 [http://localhost:3000](http://localhost:3000) | 6.10.0 (core+bmm) | 54 | 18 | 3 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode2 | 🌐 [http://127.0.0.1:8000/missions](http://127.0.0.1:8000/missions) | 6.10.0 (core+bmm) | 49 | 0 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | 🟠 majeur |
| VSCode3 | 📊 [bmad-iap-cadrage-synthese.pptx](file:///C:/Users/claude.camus/Documents/VSCode3/docs/cadrage-ppt/bmad-iap-cadrage-synthese.pptx) | 6.10.0 (core+bmm) | 53 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode4 | 📊 [Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx](file:///C:/Users/claude.camus/Documents/VSCode4/Exports/Chantiers OHC - dispositif écoute - avec synthese RH - v7-genere.pptx) | 6.10.0 (core+bmm) | 53 | 1 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VScode5 | 🌐 [wiki.html](file:///C:/Users/claude.camus/Documents/VScode5 - Supervision projets/docs/wiki.html) | 6.10.0 (core+bmm) | 54 | 8 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |

_Alerte : niveau du finding le plus haut du diagnostic superviseur local (p5 = critique, p4 = majeur)._

### VSCode — Bac à sable proto PPT (COMOP, Node.js) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (2) : agent-supervisor (2), agent-orchestrator (1)

**Skills jamais utilisés** (76) : 71 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, revue-increment, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : Explore (2)

**Playbooks** : dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 1 (partiel ×1)

### VSCode1 — Questionnaire maturité agile/produit + export PPT [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode1`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (8) : agent-orchestrator (9), agent-supervisor (7), revue-increment (6), run (5), pptx-verify (3), artifact-design (2), roadmap-keeper (1), skill-creator (1)

**Skills jamais utilisés** (51) : 46 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, restitution-ppt, slide-text-polish

**Sous-agents** (18) : auditor, auditor-subagent, debugger, developer, developer-migrator, developer-refactor, documentarian, onboarder, orchestrator, orchestrator-dev, pathfinder, planner, ppt-designer, qa-engineer, reviewer, security-auditor, ui-designer, ux-designer
**Sous-agents utilisés** : ppt-designer (3), ux-designer (2), ui-designer (2), reviewer (1), documentarian (1), onboarder (1), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie

**Runs d'orchestration** : 18 (partiel ×1, succes ×17)

### VSCode2 — Interview-to-Deck (FastAPI) [🟠 majeur]

Chemin : `C:/Users/claude.camus/Documents/VSCode2`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (21) : run-dev-server (38), agent-orchestrator (30), agent-supervisor (19), bmad-code-review (13), revue-increment (11), pptx-verify (10), update-config (6), roadmap-keeper (4), run (3), pptx-deck (2), deck-design-review (2), skill-creator (2), slide-text-polish (2), init (1), restitution-deck-design (1), bmad-sprint-status (1), claude-api (1), deck-design-library (1), swot-matrix (1), priority-matrix (1), bmad-party-mode (1)

**Skills jamais utilisés** (37) : 36 bmad-* + pptx-framed-image

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 60 (en-attente-validation ×1, partiel ×1, succes ×58)

**Diagnostic superviseur local (findings ouverts)** :
- p4 `verification-manquante` [CI] — Angle mort CI : 6 runs rouges d'affilée pendant que la suite locale était verte

### VSCode3 — Cadrage BMAD IAP (deck de synthèse) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode3`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (9) : agent-orchestrator (7), agent-supervisor (6), pptx-deck (2), revue-increment (2), artifact-design (2), restitution-deck-design (1), pptx-verify (1), bmad-agent-pm (1), roadmap-keeper (1)

**Skills jamais utilisés** (49) : 45 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : general-purpose (31), ppt-designer (12), Explore (3), Plan (1), claude-code-guide (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 20 (succes ×20)

### VSCode4 — Deck OHC RH dispositifs d'écoute (pré-code) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode4`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (7) : agent-orchestrator (4), pptx-deck (3), agent-supervisor (3), revue-increment (2), artifact-design (1), bmad-correct-course (1), pptx-verify (1)

**Skills jamais utilisés** (49) : 45 bmad-* + deck-design-library, deck-design-review, pptx-framed-image, slide-text-polish

**Sous-agents** (1) : ppt-designer
**Sous-agents utilisés** : ppt-designer (3), general-purpose (1), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 15 (succes ×15)

**Diagnostic superviseur local (findings ouverts)** :
- p1 `verification-manquante` [ppt-designer] — Contournement du cadre photo des dividers de chapitre jamais re-questionné, malgré l'écart documenté au pattern VSCode3 que le dispositif est censé répliquer

### VScode5 — Supervision multi-projets (ce projet) [✅]

Chemin : `C:/Users/claude.camus/Documents/VScode5 - Supervision projets`

Dernier scan superviseur local : 2026-07-31T20:10:06+02:00

**Skills utilisés** (10) : agent-orchestrator (94), agent-supervisor (10), bmad-party-mode (6), audit-technique (5), revue-increment (4), veille-agentic (2), dataviz (2), update-config (1), run (1), bmad-customize (1)

**Skills jamais utilisés** (47) : 44 bmad-* + deck-design-library, pptx-framed-image, slide-text-polish

**Sous-agents** (8) : agent-orchestrator, agent-supervisor, bmad-cadrage, bmad-doc, bmad-livraison, bmad-recherche, bmad-revue, veille-agentic
**Sous-agents utilisés** : general-purpose (73), Explore (19), bmad-revue (4), agent-supervisor (3), bmad-recherche (1)

**Playbooks** : dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 66 (en-attente-validation ×5, partiel ×1, succes ×60)

## 2. Pratiques, couverture & risques

_Cible : le [référentiel de critères](technical/criteres-pratiques.md) (DORA, pyramide de tests/ISO 25010, Diátaxis, Cagan/Torres, OWASP ASVS/SAMM, DAMA-DMBOK) — ce qui suit est la MESURE ; l'écart mesure↔référentiel alimente les findings `pratique-*` du superviseur._

### Référentiel des pratiques supervisées

_Les 13 pratiques mesurées, avec la règle de notation et le référentiel cible (déplié ici ; replié dans `docs/wiki.html`)._

#### Pratiques craft (développement)

_🟢 implémenté & mesuré · 🟠 partiel · 🔴 pas encore outillé._

| Pratique | Principe | Dans la flotte | Mesure |
| --- | --- | --- | --- |
| 🟢 Gestion de version pour tout | Code, config et scripts sous contrôle de version, historique propre. | 6/6 en dépôt git ; règle R2 « commit scopé au périmètre » (hub). | Cadence du dernier commit + dette non commitée (`git status --porcelain`) + nombre de branches, sur les 6 dépôts. |
| 🟠 Petits commits scopés | Commits atomiques, un changement = un commit, message clair. | Règle CLAUDE.md (R2) ; discipline, appliquée au cas par cas. | ⬜ non auto-détecté (taille/scope des commits non mesurés). |
| 🟢 Tests automatisés (dont TDD) | Tests unitaires rapides sur la logique métier, écrits tôt. | Fichiers de test + couverture (VSCode1 84,7 % / VSCode2 ~38 %). | Dimension Test technique (compte de tests + coverage). |
| 🟢 Tests fonctionnels bout-en-bout réels | Vérifier l'artefact RÉEL (rendu, PDF re-parsé, navigateur), pas un mock. | Marqueurs puppeteer/playwright/pymupdf/Presentation(/TestClient. | Dimension Test fonctionnel / rendu réel. |
| 🟠 Intégration continue | Build + tests rejoués à chaque push, feedback rapide. | CI GitHub Actions détectée sur VSCode, VSCode1, VSCode2, VSCode4, VScode5 (5/6). | Dimension Pratiques + rules (présence .github/workflows). |
| 🟢 Revue de code systématique | Tout changement relu avant merge/commit (4 yeux ou outil). | Agent reviewer + hook pré-commit (VSCode1) ; bmad-code-review ailleurs. | Dimension Revue de code. |
| 🟢 Revue d'incrément | Fin d'itération : diff relu, exigences recochées avant de clore. | Skill revue-increment + hook SessionStart de rappel. | Dimension Revue d'incrément. |
| 🟢 Analyse statique / linter | Style et erreurs détectés automatiquement (ruff, ESLint). | Linter détecté sur VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 (6/6). | Dimension Pratiques + rules (présence linter). |
| 🟢 Refactoring continu / dette maîtrisée | Boy-scout rule : laisser le code plus propre, dette suivie. | Constatée à la lecture du code (duplication, couplage, code mort). | Audit qualitatif — dimension Risque technique. |
| 🟢 Simple design / YAGNI | Le design le plus simple qui passe les tests, pas de code mort. | Code mort et sur-ingénierie relevés à l'audit. | Audit qualitatif — dimension Risque technique. |
| 🟢 Dépendances épinglées / build reproductible | Versions figées (lockfile), build déterministe. | Lockfile OK sur VSCode1 ; VSCode2 épinglé `==` (audit 2026-07-24, finding fermé). | Audit qualitatif — dimension Risque technique. |
| 🟢 Conventions de code explicites | Règles partagées écrites (nommage, structure, rules d'agent). | CLAUDE.md + conventions.md sur les projets outillés. | Dimension Pratiques + rules (CLAUDE.md, conventions). |
| 🔴 Trunk-based development | Branches courtes (< 3 actives), intégration fréquente au tronc. | Non outillé — mesurable via `git branch` (écart à combler). | ⬜ pas encore mesuré (cible du référentiel § 1). |
| 🔴 Automatisation du déploiement | Déploiement scripté et rejouable, pas d'étape manuelle. | Aucun projet outillé — pertinence à évaluer (projets locaux). | ⬜ pas mesuré (cible du référentiel § 1). |
| 🔴 Test de non-régression sur bug corrigé | Chaque bug fermé laisse un test qui échouerait s'il revenait. | Discipline à documenter dans les conventions — non détectable. | ⬜ non détectable automatiquement (cible § 2). |

_Source : référentiel § 1 (DORA) & § 2 (pyramide de tests) + dimensions du scan._

### Divergence des copies de pptx_deck.py

| Copie | Lignes | Fonctions | Propres à cette copie |
| --- | --- | --- | --- |
| VSCode2 `app/services/pptx_deck.py` | 608 | 29 | 0  |
| VSCode3 `docs/cadrage-ppt/pptx_deck.py` | 305 | 16 | 0  |
| VSCode4 `scripts/pptx_deck.py` | 930 | 41 | 12 `_normaliser`, `add_forme`, `add_text_runs`, `clear_slides`, `configurer_text_frame`, `definir_geometrie`, `definir_paragraphes`, `purger_rels_slides_orphelines`… |

_16 fonction(s) communes, dont 1 à signature divergente : `add_card`._

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
| VSCode | 🟢 6 fichier(s) de test, coverage configuré | 🟢 2 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 .env gitigné, deny rules, guard git |
| VSCode1 | 🟢 15 fichier(s) de test, coverage configuré | 🟢 2 test(s) à vérification réelle | 🟢 agent reviewer, hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 deny rules, guard git |
| VSCode2 | 🟢 45 fichier(s) de test, coverage configuré | 🟢 28 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins + brief BMAD | 🟢 linter, CI, CLAUDE.md ⚠ 162 l (> 150 — élaguer), conventions, discipline tokens | 🟢 .env gitigné, deny rules, guard git |
| VSCode3 | 🟢 4 fichier(s) de test, coverage configuré | 🟢 2 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CLAUDE.md, conventions, discipline tokens | 🟢 deny rules, guard git |
| VSCode4 | 🟢 4 fichier(s) de test, coverage configuré | 🟢 3 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 .env gitigné, deny rules, guard git |
| VScode5 | 🟢 19 fichier(s) de test, coverage configuré | 🟢 3 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | ⚪ ne produit pas de deck | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 deny rules, guard git |

🟢 ok · 🟠 moyen · 🔴 absent/manquant · ⚪ non applicable. Sécu (proxy) = garde-fous présents (.env gitigné, deny rules, guard git), PAS un audit de failles.

**Étage qualitatif** (audit `audit-technique` à la demande — lit le code) :

_Ce que couvre l'audit (chaque dimension = lecture du code réel, findings localisés `fichier:ligne`, niveau ok / moyen / critique) :_

- **Robustesse** — gestion d'erreur, cas limites, entrées non validées, échecs silencieux (`except: pass`), idempotence, absence de rollback.
- **Performance** — boucles imbriquées sur gros volumes, I/O dans une boucle, requêtes N+1, absence de cache/pagination, rendu synchrone bloquant.
- **Risque technique** — dette structurelle : duplication logique, couplage fort, dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test.
- **Sécurité** — secrets en clair/commités, injection (SQL/commande/template), désérialisation non sûre (`eval`/`pickle`), chemins utilisateur non assainis, `shell=True`, permissions trop larges.

| Projet | Robustesse | Perf. | Risque tech. | Sécurité | Audité le |
| --- | --- | --- | --- | --- | --- |
| VSCode | 🟢 ok | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-30 |
| VSCode1 | 🟢 ok | 🟢 ok | 🟢 ok | 🟠 moyen | 2026-07-25 |
| VSCode2 | 🟢 ok | 🟢 ok | 🟢 ok | 🟢 ok | 2026-07-24 |
| VSCode3 | 🟢 ok | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-30 |
| VSCode4 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-07-30 |
| VScode5 | 🟢 ok | 🟢 ok | 🟢 ok | 🟢 ok | 2026-07-29 |

_Lancer un audit : skill `audit-technique` sur le projet cible (robustesse, performance, risque technique, failles de sécurité — lecture du code)._

## 3. Veille agentic

_Dernière veille : 2026-07-29T10:20:00 — skill `veille-agentic` (cadence 3 jours, déclenchable manuellement)._

| Sujet | Type | Statut | Projets concernés | Pertinence |
| --- | --- | --- | --- | --- |
| [VoltAgent/awesome-claude-code-subagents — 154+ sous-agents en 10 catégories](https://github.com/VoltAgent/awesome-claude-code-subagents) | sous-agent | adopte | VSCode1, VScode5 | Référentiel pour comparer/enrichir la flotte de 17 sous-agents de VSCode1 avant de la mutualiser via C4 — vérifier si des rôles manquants (security, data) y sont mieux définis. [adopte 2026-07-29 : utilisé comme grille de comparaison, PAS comme source à copier. Un seul agent greffé sur VSCode1 (security-auditor, cas d'usage daté Epic 10 / 2026-08-08) — greffe volontairement minimale, 11 des 17 agents locaux étant déjà jamais invoqués. Manques accessibilité/données documentés, non greffés : ils alimentent le tri du 2026-08-16.] |
| [BMAD-METHOD — v7 ANNONCEE (uv standard) — PAS sortie : derniere release v6.10.0](https://github.com/bmad-code-org/BMAD-METHOD/releases) | framework | etudie | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Suivi 2026-07-29 : la v7 est sortie — uv remplace python3 pour tous les scripts (l'installateur le vérifie), bmad-forge-idea nouvelle skill cœur, bmad-architecture réécrite en routage par intention (les shims DEPRECATED de la flotte — create-architecture, create-prd, edit-prd, validate-prd — sont RETIRÉS en v7). Les 6 projets sont en v6.10.0 avec statu quo « aucune customisation jusqu'à la v7 » (arbitrage skills-jamais-utilisees 2026-07-27) : la migration est désormais ARBITRABLE — décider quand migrer et si le tri des 46 skills se fait à cette occasion. [2026-07-30 : ENTREE CORRIGEE apres verification a la source (API GitHub releases/latest = v6.10.0 du 2026-07-03, aucun tag v7*, dist-tag npm latest = 6.10.0). La v7 N EST PAS SORTIE. Deux des trois arguments de cette entree etaient des faits de v6.9.0 DEJA installes (bmad-forge-idea, reecriture de bmad-architecture - le routage par intention est deja en production sur les 6 depots). Le troisieme (uv standard) est une annonce prospective publiee dans les notes de v6.9.0, sans date. Statut repasse de nouveau a etudie : il n y a rien a arbitrer tant que la version n existe pas. CE QUI EST REEL AUJOURD HUI : uv est absent du PATH de la machine alors que 22 fichiers du v6.10.0 installe invoquent deja uv run en forme primaire (repli python3 documente mais non garanti) - c est un manque actuel, pas un prerequis de migration future. Le volet uv est SOLDE le 2026-07-30 : uv 0.11.32 installe (winget), uv run verifie de bout en bout sur un vrai script du dispositif. Reste en veille uniquement la sortie eventuelle de la v7.] |
| [disler/claude-code-hooks-multi-agent-observability — observabilité multi-agents par hooks](https://github.com/disler/claude-code-hooks-multi-agent-observability) | outil | etudie | VScode5 | Même pattern que notre dispositif maison (hooks → événements → dashboard) mais en temps réel avec swim lanes par agent — source d'inspiration directe pour faire évoluer scan_transcripts/log_usage/wiki.html. [instruit le 2026-07-31] Verifie a la source : 1 501 etoiles, mais DERNIER PUSH le 2026-02-08, soit ~5,7 mois d'inactivite — vivant mais dormant. La note de pertinence ci-dessus etait FAUSSE sur un point : il n'y a PAS de swim lanes par agent, mais une timeline unifiee plus un graphique de densite d'activite. Ecart reel mesure : 12 types d'evenements captes chez eux (dont SubagentStop, echecs d'outil, demandes de permission) contre UN SEUL chez nous (log_usage.py, 42 lignes : PostToolUse sur Skill|Agent|Task), et un flux temps reel par WebSocket contre notre scan differe. Pile Bun + SQLite + Vue ecartee : un process persistant contredit un hub qui regenere un wiki statique a 0 token. RETENU A COUT BORNE, en attente d'arbitrage : capturer la FIN de sous-agent (duree, issue) dans log_usage.py, et etudier un panneau « runs en cours » dans serve_wiki.py. |
| [microsoft/hve-core — skill PowerPoint python-pptx pilotée par YAML](https://github.com/microsoft/hve-core/blob/main/.github/skills/experimental/powerpoint/SKILL.md) | skill | etudie | VSCode1, VSCode2, VSCode3, VSCode4 | Approche content.yaml + style.yaml pour découpler contenu et mise en forme des decks — alternative structurée à comparer avec nos générateurs pptx_deck maison avant d'écrire le prochain. [instruit le 2026-07-31] Verifie : MIT, 1 307 etoiles, pousse le jour meme — mais la skill PPT vit sous .github/skills/EXPERIMENTAL/powerpoint/, non stabilisee par Microsoft lui-meme. Son apport : content.yaml + style.yaml par slide, un mode dry-run (parse sans build) et un validate_geometry.py (marges, gaps, debordement, degagement du titre). ECARTE pour une migration de VSCode3/VSCode4 : les deux ont un generateur Python fonctionnel et deja arbitre le 2026-07-23, migrer serait une refonte sans point de douleur identifie (R1 : correction minimale > refonte). On perdrait ajuster_police (adaptation dynamique au texte reel, indispensable sur du contenu client variable), les 22 patterns de deck-design-library, et rien ne prouve que leur validateur capte les 7 defauts que pptx-verify chasse par rendu reel. SANS OBJET pour VSCode (COMOP Node.js, pas python-pptx). SEULE PISTE RETENUE : importer l'idee du mode dry-run dans pptx-deck. |
| [hesreallyhim/awesome-claude-code — index de référence de l'écosystème Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | rules | adopte | VScode5 | Point d'entrée durable pour les prochaines sessions de veille (skills, agents, hooks, plugins triés à la main) — à re-parcourir à chaque cycle plutôt que de re-chercher à froid. [ADOPTE le 2026-07-31] Verifie vivant a la source : 51 394 etoiles, pousse le jour meme, avec CONTRIBUTING/CODE_OF_CONDUCT/SECURITY et un index GENERE programmatiquement depuis des entrees structurees — curation reelle, pas un dump de liens. Inscrit comme source recurrente dans veille-agentic/SKILL.md, section « Sources a surveiller (publiques) », avec la reserve explicite qu'un index signale ce qui existe sans dire si c'est vivant ni si ca vaut pour cette flotte. Trois entrees reperees pour le prochain cycle : cctop (sessions actives et taille de contexte, utile aux 6 projets au titre de la discipline tokens), Claude Code Agent Monitor (arbres d'orchestration — a croiser avec la trouvaille observabilite), UI Craft (critique design par heuristiques Nielsen, pour les 2 apps web). |
| [Dev Browser — l'agent vérifie son travail dans un vrai navigateur (Playwright + sandbox WASM)](https://github.com/sawyerhood/dev-browser) | skill | etudie | VSCode1, VSCode2 | Skill/plugin qui donne à Claude Code un navigateur piloté (API Playwright + outils pixel/DOM, scripts en sandbox QuickJS WASM sans accès disque/réseau hôte) pour TESTER ce qu'il produit — la vérification réelle des écrans de VSCode1 (questionnaire web) et VSCode2 (FastAPI+HTMX) repose aujourd'hui sur des tests HTTP et des screenshots manuels ; à comparer avant d'écrire un harnais navigateur maison. [instruit le 2026-07-31] Depot identifie avec certitude : SawyerHood/dev-browser, MIT, 6 490 etoiles, dernier push 2026-07-15. Point important souvent mal lu : le sandbox QuickJS WASM restreint le SCRIPT ecrit par l'agent, pas le navigateur — Chrome est un process normal qui atteint localhost sans probleme. SANS OBJET pour VSCode1 : app/scripts/capture-screenshots.js pilote deja un vrai Chrome sur localhost:3000 via Puppeteer ; l'apport se reduirait a la surete du sandbox et a l'API Playwright. OBJET REEL pour VSCode2 : grep confirme AUCUN playwright/selenium/puppeteer dans son dossier tests/ — une app FastAPI verifiee par pytest seul, sans aucun controle de rendu en navigateur. Reserve avant adoption : cela ajoute une dependance Node a un projet Python pur, a isoler en outillage agent plutot qu'en dependance projet. |

### Pratiques agentic repérées (docs providers)

_Volet 2 de `veille-agentic` : pratiques recommandées par les providers, comparées à l'état réel de la flotte. `adopte` (décision utilisateur) => la règle proposée entre au référentiel (`criteres-pratiques.md` § 7) et l'action corrective se traite via `evolution-flotte`._

| Pratique | Source | Statut | Projets | Règle d'analyse proposée | Action corrective |
| --- | --- | --- | --- | --- | --- |
| [Vérification exécutable fournie à l'agent (checks déterministes, Stop/pré-commit hooks)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Give Claude a way to verify its work ») | adopte | VSCode, VSCode3, VSCode4 | Critère scan (dimension revue de code) : hook de vérification pré-commit présent (warn_verif_before_commit ou équivalent) — pas seulement une skill de revue invocable. | Propager warn_verif_before_commit à VSCode/VSCode3/VSCode4 (adapté au canal de chaque projet), via evolution-flotte. |
| [CLAUDE.md concis, entretenu comme du code (pruning régulier)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Write an effective CLAUDE.md », « The over-specified CLAUDE.md ») | adopte | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Critère scan (dimension pratiques + rules) : taille du CLAUDE.md bornée (alerte au-delà d'un seuil, ex. 150 lignes) — mesurable à froid, 0 token. | Passe de pruning des CLAUDE.md de la flotte : chaque ligne justifiée par « sa suppression causerait-elle une erreur ? », convertir en hook ce qui doit être garanti. |
| [Revue adversariale en contexte frais avant de clore (reviewer ≠ implémenteur)](https://code.claude.com/docs/en/best-practices) | Anthropic — Claude Code docs / best practices (« Add an adversarial review step ») + Writer/Reviewer pattern | adopte | VSCode, VSCode3, VSCode4, VScode5 | Règle playbooks : toute orchestration qui commit porte une étape terminale de revue en contexte frais (sous-agent sur le diff), tracée dans le plan du run. | Ancrer l'étape « revue contexte frais » dans les playbooks evolution-flotte et export-ppt-verifie (dev-verifie l'a déjà), et le vérifier au diagnostic étage 2 (catégorie verification-manquante). |
| [Guardrails en couches pour actions irréversibles (défense combinée, pas un garde unique)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | OpenAI — A practical guide to building agents (guardrails en couches, tool-specific risk controls) | adopte | VScode5 | Critère scan (dimension sécurité proxy) : les projets qui ÉCRIVENT sur d'autres dépôts exigent le niveau complet (deny rules + guard destructif + .env gitigné), pas un garde unique. | Aligner les settings du hub : ajouter les deny rules manquantes (webhooks/secrets/curl destructif) au niveau des autres projets de la flotte. |
| [Gestion du contexte outillée : statusline de suivi, /compact cadré, sous-agents d'exploration](https://code.claude.com/docs/en/costs) | Anthropic — Claude Code docs (reduce token usage, context window) + best practices (context is the fundamental constraint) | adopte | VSCode, VSCode2, VSCode4, VScode5 | Critère scan (dimension pratiques + rules) : discipline tokens écrite dans le CLAUDE.md/conventions du projet (marqueurs /compact, sous-agent, lecture ciblée) — mesurable 0 token. | Propager la section « optimisation tokens » (modèle VSCode1/VSCode3, adaptée au canal) aux CLAUDE.md de VSCode/VSCode2/VSCode4/VScode5. |
| [Agent Teams Claude Code — équipe de sessions coordonnées (lead + équipiers), expérimental](https://code.claude.com/docs/en/agent-teams) | Anthropic — Claude Code docs / agent teams (expérimental, CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS) | adopte | VScode5 | Règle skill agent-orchestrator : le plan justifie le véhicule de parallélisme choisi — sous-agents par défaut (résultat seul), agent team uniquement si les travailleurs doivent se coordonner entre eux (revue multi-angles avec débat, hypothèses concurrentes), avec taille 3-5 et partition stricte des fichiers. | Compléter la section « 2 ter » de la skill agent-orchestrator avec le critère de choix subagents vs agent teams et les garde-fous officiels (expérimental, opt-in env var, coût linéaire par équipier) — proposition arbitrable, ne rien activer d'office. |

