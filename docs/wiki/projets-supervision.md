# Supervision multi-projets — agents, skills, playbooks

_Généré le 2026-09-03 09:33 par `scripts/scan_projets.py` — ne pas éditer à la main._

## Poste de pilotage

**6 projets** · **1 en alerte** (VSCode3 🟠 majeur) · **15 pratique(s) en écart** · **5 finding(s) ouvert(s)** · **9 run(s) à solder** · **1 retard(s) de cadence**

_Depuis le scan précédent (2026-09-03 09:32) : pratiques en écart, findings, runs à solder, retards._

**À arbitrer (onglet Actions correctives)** :
- 🔴 VSCode3 : 2 pratique(s) en écart + 4 finding(s) ouvert(s)
- 🔴 VScode5 : 3 pratique(s) en écart + 1 finding(s) ouvert(s)
- 🟠 VSCode1 : 5 pratique(s) en écart
- 🟠 VSCode : 3 pratique(s) en écart
- 🟠 VSCode2 : 1 pratique(s) en écart
- 🟠 VSCode4 : 1 pratique(s) en écart

**Runs `en-attente-validation` à solder** (valider ou requalifier) :
- [VSCode2] il y a 2 j ⚠ — Relance des travaux de la derniere session (traitement des 12 constats R3 : verifier, fair
- [VSCode2] il y a 1 j — Solder le run en attente et lancer une revue (cible arbitree par l'utilisateur : le commit
- [VSCode1] il y a 1 j — cloture le run de ce projet (increment app/ non commite : durcissement robustesse/confiden
- [VSCode2] il y a 1 j — lance le superviseur
- [VSCode2] il y a 1 j — relance le chantier correctif de l entretien libre, cloture le sujet, commit et push
- [VSCode2] il y a 10 h — Finaliser l entretien libre : operationnel, sans regression, audio par tranche, transcript
- [VSCode3] il y a 10 h — regenere le deck ppt en archivant le dernier, en tenant compte des slides modifiees en ses
- [VSCode3] il y a 7 h — rajoute en executive summary apres le slide 2 un nouveau slide qui montre par un schema l'
- [VSCode3] il y a 6 h — corriger des coquilles graphiques signalees sur slide 1 (trait arrondi qui ne rejoint pas)

_Solder (dans le projet concerné) : `py .claude/orchestration/log_run.py --solde <prefixe-ts> succes "note de validation"`_

**Retards de cadence** :
- VSCode2 : audit technique à relancer (41 j, 39603 lignes changées depuis)

### Cadences

| Projet | Scan étage 1 | Diagnostic étage 2 | Dernier commit |
| --- | --- | --- | --- |
| VSCode | il y a 0 min | il y a 1 j | il y a 16 min |
| VSCode1 | il y a 0 min | il y a 1 j | il y a 8 min |
| VSCode2 | il y a 0 min | il y a 21 h | il y a 8 h |
| VSCode3 | il y a 0 min | il y a 1 j | il y a 6 h |
| VSCode4 | il y a 0 min | il y a 1 j | il y a 1 min |
| VScode5 | il y a 0 min | il y a 1 min | il y a 57 min |

Veille agentic : il y a 9 h (cadence 3 j).

## 1. Supervision des projets

| Projet | Livrable principal | BMAD | Skills | Sous-agents | Playbooks | Orchestrateur | Superviseur | Hooks | Alerte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 📊 [comop-verifie-2026-07-28.pptx](file:///C:/Users/claude.camus/Documents/VSCode/comop-pptx-prototype/output/comop-verifie-2026-07-28.pptx) | 6.10.0 (core+bmm+tea+bmb+cis) | 84 | 5 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode1 | 🌐 [http://localhost:3000](http://localhost:3000) | 6.10.0 (core+bmm) | 57 | 26 | 5 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode2 | 🌐 [http://127.0.0.1:8000/missions](http://127.0.0.1:8000/missions) | 6.10.0 (core+bmm) | 52 | 8 | 5 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VSCode3 | 📊 [bmad-iap-cadrage-synthese.pptx](file:///C:/Users/claude.camus/Documents/VSCode3/docs/cadrage-ppt/bmad-iap-cadrage-synthese.pptx) | 6.10.0 (core+bmm) | 56 | 9 | 5 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | 🟠 majeur |
| VSCode4 | 📊 [Chantiers OHC - dispositif écoute - avec synthese RH - v8-genere.pptx](file:///C:/Users/claude.camus/Documents/VSCode4/Exports/Chantiers OHC - dispositif écoute - avec synthese RH - v8-genere.pptx) | 6.10.0 (core+bmm) | 56 | 9 | 5 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, UserPromptSubmit | ✅ |
| VScode5 | 🌐 [wiki.html](file:///C:/Users/claude.camus/Documents/VScode5 - Supervision projets/docs/wiki.html) | 6.10.0 (core+bmm) | 58 | 4 | 4 | ✅ | ✅ | PostToolUse, PreToolUse, SessionStart, SubagentStop, UserPromptSubmit | ✅ |

_Alerte : niveau du finding le plus haut du diagnostic superviseur local (p5 = critique, p4 = majeur)._

### VSCode — Bac à sable proto PPT (COMOP, Node.js) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (2) : agent-supervisor (2), agent-orchestrator (1)

**Skills jamais utilisés** (82) : 71 bmad-* + audit-technique, deck-design-library, deck-design-review, pdf-quality, pptx-deck, pptx-framed-image, pptx-verify, restitution-deck-design, revue-increment, slide-text-polish, veille-agentic

**Sous-agents** (5) : agent-supervisor, bmad-recherche, bmad-revue, ppt-designer, veille-agentic
**Sous-agents utilisés** : Explore (2)

**Playbooks** : dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 3 (partiel ×3)

**Écartés par un arbitrage** (5) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p5 `verification-manquante` [smoke-test-hors-ci]~~ — La seule suite qui couvre les scripts de mutation OOXML (34 assertions, verte) n'est rejouee ni par npm test ni par la CI - exactement le trou qui a laisse vivre la regression 45 jours
- ~~p5 `verification-manquante` [state-transcripts-absents]~~ — La base de mesure de l'etage 1 a disparu : zero transcript sur disque, state.json pointe deux fichiers absents, et le scan de ce jour a quand meme publie 75 skills « jamais utilisees » comme si c'etait une mesure
- ~~p4 `interaction` [playbooks-comop]~~ — Les deux playbooks de ce projet decrivent un produit qui a 35 jours de retard : ils exigent smoke-test.ps1 comme unique gate et font escalader sur le script innocente de la regression
- ~~p3 `autre` [increment-6-validation]~~ — L'increment 6 attend depuis 35 jours une validation utilisateur que personne n'a demandee, et gele une roadmap dont le blocage est pourtant leve
- ~~p2 `autre` [server-api-corps-json]~~ — Un corps JSON malforme sur /api/generate rend un 500 avec le message brut du parseur au lieu d'un 400 - finding d'audit reste sans arbitrage depuis 33 jours

### VSCode1 — Questionnaire maturité agile/produit + export PPT [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode1`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (9) : agent-orchestrator (16), agent-supervisor (7), revue-increment (6), run (6), pptx-verify (3), artifact-design (3), roadmap-keeper (1), skill-creator (1), dataviz (1)

**Skills jamais utilisés** (54) : 46 bmad-* + audit-technique, deck-design-library, deck-design-review, pdf-quality, pptx-framed-image, restitution-ppt, slide-text-polish, veille-agentic

**Sous-agents** (26) : agent-orchestrator, agent-supervisor, auditor, auditor-subagent, bmad-cadrage, bmad-doc, bmad-livraison, bmad-recherche, bmad-revue, debugger, developer, developer-migrator, developer-refactor, documentarian, onboarder, orchestrator, orchestrator-dev, pathfinder, planner, ppt-designer, qa-engineer, reviewer, security-auditor, ui-designer, ux-designer, veille-agentic
**Sous-agents utilisés** : general-purpose (5), ppt-designer (3), ux-designer (3), Explore (3), bmad-revue (3), reviewer (2), ui-designer (2), qa-engineer (2), documentarian (1), onboarder (1), security-auditor (1), auditor (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 22 (en-attente-validation ×1, partiel ×2, succes ×19)

**Écartés par un arbitrage** (5) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p5 `verification-manquante` [securite:barriere-auth-fail-closed]~~ — La barriere Basic Auth declaree « fail-closed, activee en PROD » ne l'est ni l'une ni l'autre : contournement par la CASSE prouve sur HEAD, et aucun environnement ne pose AUTH_USER/AUTH_PASS - la dimension securite « moyen » du 2026-07-30 sous-estimait le risque
- ~~p5 `verification-manquante` [journalisation:dod-au-commit]~~ — 3e recidive du trou de journalisation/DoD : 19 commits en 35 jours pour 0 run journalise, 0 marqueur DoD et revue-increment jamais rechargee - le garde-fou arbitre le 2026-07-28 etait aveugle au shell primaire pendant toute la periode
- ~~p4 `interaction` [propagation-canon:2026-09-01]~~ — La resynchro canon du 2026-09-01 a propage a l'envers : elle a ressuscite un playbook qu'un arbitrage avait supprime, et laisse le superviseur local incapable d'ecrire le moindre constat de pratique
- ~~p4 `interaction` [arbitrages:revue-mvp-2026-09-01]~~ — La revue multi-agents du 2026-09-01 a trouve des defauts bloquants et remis 3 arbitrages a l'utilisateur - aucun n'a de canal : arbitrages.json s'arrete au 2026-07-29 et le diagnostic n'avait pas bouge depuis le 2026-07-28
- ~~p3 `agent-mort` [echeance:2026-08-16-tri-agents-bmad]~~ — Les deux decisions datees au 2026-08-16 (mise en sommeil groupee des agents jamais appeles, tri des 46 skills BMAD) n'ont pas ete prises : 16 jours de retard, et la remediation par « declencheur de routage » du 2026-07-28 n'a rien change au routage reel

### VSCode2 — Interview-to-Deck (FastAPI) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode2`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (21) : agent-orchestrator (44), run-dev-server (42), agent-supervisor (21), bmad-code-review (13), revue-increment (12), pptx-verify (10), update-config (6), roadmap-keeper (4), run (3), pptx-deck (2), deck-design-review (2), skill-creator (2), slide-text-polish (2), init (1), restitution-deck-design (1), bmad-sprint-status (1), claude-api (1), deck-design-library (1), swot-matrix (1), priority-matrix (1), bmad-party-mode (1)

**Skills jamais utilisés** (40) : 36 bmad-* + audit-technique, pdf-quality, pptx-framed-image, veille-agentic

**Sous-agents** (8) : agent-orchestrator, agent-supervisor, bmad-cadrage, bmad-doc, bmad-livraison, bmad-recherche, bmad-revue, veille-agentic
**Sous-agents utilisés** : general-purpose (52), Explore (30), bmad-revue (20), claude (4), Plan (3), claude-code-guide (1), agent-supervisor (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 73 (en-attente-validation ×5, partiel ×5, succes ×63)

**Écartés par un arbitrage** (5) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p5 `interaction` [write_diagnostic.py]~~ — Ecrire un diagnostic EFFACE les constats precedents non arbitres — la boucle propose/arbitre/applique fuit a son premier maillon
- ~~p4 `interaction` [log_run.py]~~ — Le journal ne se solde jamais : 4 runs restent en-attente-validation, dont celui du superviseur lui-meme
- ~~p4 `verification-manquante` [dev-verifie]~~ — Sept tours consecutifs ou un correctif introduit un defaut de la classe qu'il corrigeait — le gate les attrape, la cause reste
- ~~p3 `autre` [scan_transcripts.py]~~ — Le backlog de revue a triple sans qu'aucun compteur ne le voie : 115 identifiants de constat dans .claude/triage
- ~~p3 `interaction` [CLAUDE.md]~~ — Les regles R1 a R4 sont citees par la skill et par le journal, et ne sont definies nulle part

### VSCode3 — Cadrage BMAD IAP (deck de synthèse) [🟠 majeur]

Chemin : `C:/Users/claude.camus/Documents/VSCode3`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (10) : agent-orchestrator (16), agent-supervisor (6), pptx-deck (2), revue-increment (2), artifact-design (2), restitution-deck-design (1), pptx-verify (1), bmad-agent-pm (1), roadmap-keeper (1), bmad-party-mode (1)

**Skills jamais utilisés** (51) : 44 bmad-* + audit-technique, deck-design-library, deck-design-review, pdf-quality, pptx-framed-image, slide-text-polish, veille-agentic

**Sous-agents** (9) : agent-orchestrator, agent-supervisor, bmad-cadrage, bmad-doc, bmad-livraison, bmad-recherche, bmad-revue, ppt-designer, veille-agentic
**Sous-agents utilisés** : general-purpose (35), ppt-designer (16), Explore (7), Plan (1), claude-code-guide (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 27 (en-attente-validation ×3, succes ×24)

**Diagnostic superviseur local (findings ouverts)** :
- p4 `autre` [CLAUDE.md] — La discipline tokens et 4 autres sections de CLAUDE.md ont été supprimées le 2026-09-01 sans arbitrage, dont un correctif flotte adopté
- p3 `autre` [docs/cadrage-ppt/generate_deck.py] — Le générateur monolithique a crû de 13 % depuis l'audit : la pastille « risque technique moyen » repose sur un chiffre périmé
- p3 `agent-mort` [deck-design-review] — Deux instruments de revue de design, zéro exécution en 23 runs — dont une skill réécrite pour CE deck et câblée nulle part
- p2 `verification-manquante` [arbitrages.json] — Le diagnostic a affiché 3 constats déjà clos pendant 40 jours, et le journal des arbitrages est figé depuis autant

**Écartés par un arbitrage** (1) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p5 `verification-manquante` [docs/vscode1-export/ppt-toolkit.md]~~ — Un correctif de sécurité ne vit que dans la copie locale : la resynchronisation documentée le supprimerait

### VSCode4 — Deck OHC RH dispositifs d'écoute (pré-code) [✅]

Chemin : `C:/Users/claude.camus/Documents/VSCode4`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (9) : agent-orchestrator (15), revue-increment (6), pptx-deck (3), agent-supervisor (3), artifact-design (1), bmad-correct-course (1), pptx-verify (1), deck-design-review (1), code-review (1)

**Skills jamais utilisés** (51) : 45 bmad-* + audit-technique, deck-design-library, pdf-quality, pptx-framed-image, slide-text-polish, veille-agentic

**Sous-agents** (9) : agent-orchestrator, agent-supervisor, bmad-cadrage, bmad-doc, bmad-livraison, bmad-recherche, bmad-revue, ppt-designer, veille-agentic
**Sous-agents utilisés** : ppt-designer (15), general-purpose (6), bmad-revue (3), Explore (1)

**Playbooks** : cycle-produit-bmad, dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 28 (partiel ×2, succes ×26)

**Écartés par un arbitrage** (5) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p4 `verification-manquante` [arbitrages.json]~~ — La boucle propose -> arbitre -> applique ne se referme pas sur ce projet : un finding resolu sans arbitrage trace, un diagnostic perime 39 jours, et un script d'ecriture en retard sur le kit publie
- ~~p3 `inefficacite` [pptx_deck.py]~~ — Duplication cross-projet non soldee : les 12 helpers durcis payes sur ce deck ne sont jamais remontes dans le module de reference, et le generateur a grossi de 56 % depuis l'audit
- ~~p2 `agent-mort` [deck-design-review]~~ — La skill de revue de design greffee sur arbitrage n'a jamais ete invoquee en 40 jours, n'est cablee dans aucun playbook, et son contrat est deja perime
- ~~p1 `verification-manquante` [export-ppt-verifie]~~ — Les chiffres annonces par les documents du depot derivent a chaque increment et ne sont rattrapes que par une passe humaine a posteriori - deuxieme occurrence en 24 h
- ~~p1 `verification-manquante` [generate_deck_ohc.py]~~ — Un divider de chapitre servi par l'image procedurale de repli passe le self-check du build ET les 32 tests : la degradation du livrable est silencieuse

### VScode5 — Supervision multi-projets (ce projet) [✅]

Chemin : `C:/Users/claude.camus/Documents/VScode5 - Supervision projets`

Dernier scan superviseur local : 2026-09-03T09:33:02+02:00

**Skills utilisés** (13) : agent-orchestrator (120), agent-supervisor (10), revue-increment (9), bmad-party-mode (8), audit-technique (5), veille-agentic (2), dataviz (2), update-config (1), run (1), bmad-customize (1), artifact-design (1), bmad-advanced-elicitation (1), bmad-editorial-review-structure (1)

**Skills jamais utilisés** (49) : 42 bmad-* + deck-design-library, pdf-quality, pptx-deck, pptx-framed-image, pptx-verify, restitution-deck-design, slide-text-polish

**Sous-agents** (4) : agent-supervisor, bmad-recherche, bmad-revue, veille-agentic
**Sous-agents utilisés** : general-purpose (126), Explore (30), agent-supervisor (13), bmad-revue (12), veille-agentic (3), bmad-recherche (1)

**Playbooks** : dev-verifie, evolution-flotte, export-ppt-verifie, revue-design-parallele

**Runs d'orchestration** : 112 (partiel ×14, succes ×98)

**Diagnostic superviseur local (findings ouverts)** :
- p3 `autre` [flotte:VSCode,VSCode1] — Chantier a planifier (demande utilisateur du 2026-09-02) : realigner la suite agentic de VSCode et VSCode1 sur le kit du hub

**Écartés par un arbitrage** (9) — montrés plutôt que supprimés : ils ne comptent pas dans le niveau d'alerte, mais un filtrage muet est ce qui les rendait invérifiables :
- ~~p3 `verification-manquante` [flotte:warn_verif_before_commit]~~ — Le kit publie embarque les chemins surveilles d un AUTRE projet : ailleurs, le garde-fou pre-commit est un no-op muet
- ~~p3 `verification-manquante` [.claude/dispositif/package/install_agentic.py::_fusionner_settings]~~ — Un settings.json dont un evenement de hook n est pas une liste fait planter l installateur APRES la copie des 43 fichiers, sans rollback
- ~~p3 `autre` [VScode5:skills-pptx-globales-non-versionnees]~~ — Trois skills dont les projets de deck dependent vivent dans un repertoire NON VERSIONNE, hors de tout depot et hors du kit
- ~~p2 `autre` [export/orchestration/git_agents_inventory.py]~~ — L outil qui repond « un agent equivalent a-t-il deja existe ? » repond NON a tort sur tout chemin accentue, et plante sur un chemin commencant par arobase
- ~~p2 `autre` [export/skills/pptx-framed-image/scripts/stock_images.py]~~ — La garde SSRF filtre le SCHEMA mais pas la DESTINATION : une url http vers une adresse interne reste telechargee
- ~~p2 `verification-manquante` [.claude/dispositif/sync_dispositif.py]~~ — Le refus de synchronisation accuse la cible alors que c est le canon qui a bouge
- ~~p2 `autre` [VScode5:openhub-code-herite]~~ — Le code de couverture OpenHub est inerte au hub mais VIVANT dans le canon propage aux 5 cibles, et n a jamais produit une seule ligne nulle part
- ~~p2 `verification-manquante` [VScode5:seuil-qualification-non-mesurable]~~ — Le ratio qui devait calibrer le seuil « orchestrer ou executer directement » est non mesurable par construction : 106 runs, 106 orchestre, 0 direct-signale
- ~~p1 `autre` [VScode5:portee-multi-projets-jamais-arbitree]~~ — La decision la plus structurante du dispositif — un depot hub dedie plutot qu une skill locale ou globale — n a aucune trace de deliberation

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
| 🟢 Trunk-based development | Branches courtes (< 3 actives), intégration fréquente au tronc. | 6/6 dépôts à une seule branche `main` (mesuré le 2026-07-30, re-mesuré le 2026-08-31). | ✅ `git_etat()` (comptage `git branch`, seuil DORA < 3 au rendu). La ligne disait « non outillé » un mois après l'avoir été — corrigé le 2026-08-31, finding `referentiel:deux-sources-qui-se-contredisent`. |
| 🔴 Automatisation du déploiement | Déploiement scripté et rejouable, pas d'étape manuelle. | Aucun projet outillé — pertinence à évaluer (projets locaux). | ⬜ pas mesuré (cible du référentiel § 1). |
| 🔴 Test de non-régression sur bug corrigé | Chaque bug fermé laisse un test qui échouerait s'il revenait. | Discipline à documenter dans les conventions — non détectable. | ⬜ non détectable automatiquement (cible § 2). |

_Source : référentiel § 1 (DORA) & § 2 (pyramide de tests) + dimensions du scan._

### Divergence des copies de pptx_deck.py

| Copie | Lignes | Fonctions | Propres à cette copie |
| --- | --- | --- | --- |
| VSCode2 `app/services/pptx_deck.py` | 608 | 29 | 0  |
| VSCode3 `docs/cadrage-ppt/pptx_deck.py` | 305 | 16 | 0  |
| VSCode4 `scripts/pptx_deck.py` | 944 | 41 | 12 `_normaliser`, `add_forme`, `add_text_runs`, `clear_slides`, `configurer_text_frame`, `definir_geometrie`, `definir_paragraphes`, `purger_rels_slides_orphelines`… |

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
- **Sécurité (proxy)** — Garde-fous PRÉSENTS (pas un audit de failles) : .env gitigné, deny rules, hook guard_destructive_git — lus dans les DEUX canaux, settings.json ET settings.local.json (git-ignoré). Alerte si un .env est commité. Les « ⚠ N perm. hors git » sont signalées À PART des garde-fous, jamais parmi eux : ce sont les permissions que seul le canal git-ignoré porte, donc celles qu'un retrait de flotte par commit ne peut pas atteindre — c'est ainsi que le retrait de rtk s'était arrêté en silence sur 3 dépôts. Elles PLAFONNENT la note à 🟠 : un ensemble de permissions qu'aucun commit ne relit n'est pas une posture verte (arbitrages du 2026-09-01, le second corrigeant le rendu du premier, qui les affichait comme un troisième garde-fou). _Notation :_ 🟢 ok = ≥ 2 garde-fous présents ; 🟠 moyen = ≥ 1 garde-fou ; 🔴 absent = aucun garde-fou — ou .env non gitigné. _Réf. :_ OWASP ASVS 5.0 + SAMM — proxy de maturité, l'audit qualitatif cherche les failles réelles (§ 5).

**Étage qualitatif (audit-technique à la demande)**

- **Robustesse** — Lecture du code : gestion d'erreur, cas limites, entrées non validées, échecs silencieux (except: pass), idempotence, absence de rollback. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ ISO 25010 (fiabilité) + tests d'erreur/cas limites (§ 2).
- **Performance** — Lecture du code : boucles imbriquées sur gros volumes, I/O dans une boucle, requêtes N+1, absence de cache/pagination, rendu synchrone bloquant. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ ISO 25010 (efficacité de performance).
- **Risque technique** — Lecture du code : dette structurelle — duplication logique, couplage fort, dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ DORA — build reproductible, dépendances épinglées (§ 1).
- **Sécurité (audit)** — Lecture du code : secrets en clair/commités, injection (SQL/commande/template), désérialisation non sûre (eval/pickle), chemins utilisateur non assainis, shell=True, permissions trop larges. _Notation :_ 🟢 ok / 🟠 moyen / 🔴 critique = verdict qualitatif, findings localisés fichier:ligne. _Réf. :_ OWASP ASVS 5.0 (~350 exigences, 17 chapitres) + SAMM (§ 5).

**Étage déterministe** (mesuré à chaque scan, 0 token — présence de dispositifs) :

| Projet | Test tech. | Test fonct. | Revue code | Revue incr. | Design | Doc | Cadrage produit | Pratiques+rules | Sécu (proxy) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VSCode | 🟢 7 fichier(s) de test, coverage configuré | 🟢 3 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer, design-system | 🟢 README+usage, wiki, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 .env gitigné, deny rules, guard git |
| VSCode1 | 🟢 28 fichier(s) de test, coverage configuré | 🟢 2 test(s) à vérification réelle | 🟢 agent reviewer, hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, ⬜ pas de discipline tokens écrite | 🟠 deny rules, guard git · ⚠ 89 perm. hors git, jamais relues par un commit |
| VSCode2 | 🟢 48 fichier(s) de test, coverage configuré | 🟢 28 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | ⚪ ne produit pas de deck | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, ⬜ pas de discipline tokens écrite | 🟠 .env gitigné, deny rules, guard git · ⚠ 16 perm. hors git, jamais relues par un commit |
| VSCode3 | 🟢 6 fichier(s) de test, coverage configuré | 🟢 2 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CLAUDE.md, conventions, discipline tokens | 🟢 .env gitigné, deny rules, guard git |
| VSCode4 | 🟢 4 fichier(s) de test, coverage configuré | 🟢 3 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | 🟢 deck-design-review, deck-design-library, ppt-designer | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, ⬜ pas de discipline tokens écrite | 🟢 .env gitigné, deny rules, guard git |
| VScode5 | 🟢 68 fichier(s) de test, coverage configuré | 🟢 10 test(s) à vérification réelle | 🟢 hook pré-commit, bmad-code-review | 🟢 skill + hook SessionStart | ⚪ ne produit pas de deck | 🟢 README+usage, wiki+html, CLAUDE.md | 🟢 persona, why, besoins, valeur + brief BMAD | 🟢 linter, CI, CLAUDE.md, conventions, discipline tokens | 🟢 deny rules, guard git |

🟢 ok · 🟠 moyen · 🔴 absent/manquant · ⚪ non applicable. Sécu (proxy) = garde-fous présents (.env gitigné, deny rules, guard git), PAS un audit de failles.

**Étage qualitatif** (audit `audit-technique` à la demande — lit le code) :

_Ce que couvre l'audit (chaque dimension = lecture du code réel, findings localisés `fichier:ligne`, niveau ok / moyen / critique) :_

- **Robustesse** — gestion d'erreur, cas limites, entrées non validées, échecs silencieux (`except: pass`), idempotence, absence de rollback.
- **Performance** — boucles imbriquées sur gros volumes, I/O dans une boucle, requêtes N+1, absence de cache/pagination, rendu synchrone bloquant.
- **Risque technique** — dette structurelle : duplication logique, couplage fort, dépendance non épinglée, code mort, fonction trop longue, chemin critique sans test.
- **Sécurité** — secrets en clair/commités, injection (SQL/commande/template), désérialisation non sûre (`eval`/`pickle`), chemins utilisateur non assainis, `shell=True`, permissions trop larges.

| Projet | Robustesse | Perf. | Risque tech. | Sécurité | Audité le |
| --- | --- | --- | --- | --- | --- |
| VSCode | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟠 moyen | 2026-09-02 |
| VSCode1 | 🟠 moyen | 🟠 moyen | 🟠 moyen | 🟠 moyen | 2026-09-02 |
| VSCode2 | 🟢 ok | 🟢 ok | 🟢 ok | 🟢 ok | 2026-07-24 |
| VSCode3 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-09-02 |
| VSCode4 | 🟢 ok | 🟢 ok | 🟠 moyen | 🟢 ok | 2026-09-02 |
| VScode5 | 🟠 moyen | 🟢 ok | 🟠 moyen | 🟠 moyen | 2026-09-01 |

_Lancer un audit : skill `audit-technique` sur le projet cible (robustesse, performance, risque technique, failles de sécurité — lecture du code)._

### Détail des synthèses d'audit

_Synthèses trop longues pour l'infobulle de la page HTML — texte intégral, un lien « détail complet → » y renvoie depuis les onglets Pratiques et Arbitrer._

<a id="audit-vscode-robustesse"></a>
**VSCode — Robustesse** : Base solide (validations Mandatory/Test-Path cote PowerShell, garde-fous de taille et de chemin cote Node, deja bons a l'audit precedent) mais 4 points d'incoherence ou de fragilite persistent, dont deux deja releves le 2026-07-30 et non traites.

<a id="audit-vscode-performance"></a>
**VSCode — Perf.** : Perimetre volontairement restreint (template ~1,4 Mo, 3 slides, usage local mono-utilisateur) : pas de boucle imbriquee sur volume, pas d'I/O reseau/DB en boucle, regex OOXML appliquees a des XML de taille modeste. Rien de significatif au-dela de l'absence de timeout deja comptee en robustesse.

<a id="audit-vscode-risque_technique"></a>
**VSCode — Risque tech.** : La deduplication de New-TempDirectory actee au 2026-07-30 (commit 9114ec9) n'a couvert que 2 scripts sur 5 qui en ont besoin : la meme duplication qu'elle visait a eliminer subsiste ailleurs. Le choix regex-sur-XML-brut, deja identifie comme fragile, reste non traite (assume comme design du canal COMOP).

<a id="audit-vscode-securite"></a>
**VSCode — Sécurité** : Les risques majeurs deja trouves (injection de commande, traversee de repertoire, exposition LAN) restent corriges et testes. Reste ouvert : aucune validation du CONTENU d'un template uploade avant de le stocker et de l'extraire, et aucun garde-fou sur la taille decompressee d'un zip.

<a id="audit-vscode1-robustesse"></a>
**VSCode1 — Robustesse** : Le socle applicatif s'est nettement durci (transactions via tx.js, validation avant ecriture, handlers async proteges, filet d'erreur terminal, dates NaN gardees) mais la couche d'ENTREE reste naive sur un point : un parametre de requete repete casse ou desactive silencieusement un filtre, et les scripts d'exploitation (restore, seed, synthese PPT) n'ont pas recu le meme soin que src/.

<a id="audit-vscode1-performance"></a>
**VSCode1 — Perf.** : Le N+1 corrige le 2026-07-24 dans agregerResultats est bien parti, mais il s'est DEPLACE D'UN ETAGE : getReferentiel fait 66 requetes mesurees par appel et l'export departement l'appelle 1+3E fois — le cout a suivi la meme forme, un niveau plus haut.

<a id="audit-vscode1-risque_technique"></a>
**VSCode1 — Risque tech.** : La dette de test du coeur de calcul est soldee (23 suites chainees dans npm test), mais la chaine de LIVRAISON ment sur elle-meme a trois endroits : la CI ignore un lockfile qu'elle croit absent, l'artefact de deploiement de-epingle la dependance Python que le depot venait d'epingler, et le filet geometrique du deck ne fait qu'avertir.

<a id="audit-vscode1-securite"></a>
**VSCode1 — Sécurité** : Les deux findings du 2026-07-25 sont traites : la barriere Basic Auth est desormais fail-closed integral ET refuse de demarrer en PROD sans identifiants (verifie : exit 1), et les .env versionnes relevent d'une convention explicite verrouillee par un test chaine dans npm test. Restent la surface PII ouverte par conception du parcours repondant (Epic 10) et l'hygiene des scripts d'exploitation, qui n'ont recu aucun des durcissements de src/.

<a id="audit-vscode2-performance"></a>
**VSCode2 — Perf.** : Les 2 findings majeurs sont RESOLUS : le travail CPU-bound (Whisper, extraction IA) passe par asyncio.to_thread (la boucle d'evenements ne gele plus pendant des minutes) et l'audio complet est streame par blocs vers le disque au lieu de passer en RAM. Reste une opportunite mineure (map-reduce IA sequentiel) et le bon point historique (transcription parallele ProcessPoolExecutor).

<a id="audit-vscode2-risque_technique"></a>
**VSCode2 — Risque tech.** : Les 2 derniers findings sont traites : pptx_export decoupe en package (plus gros fichier 475 l, API inchangee, verbatim) et migrations SQLite verrouillees par un filet de tests (idempotence, rattrapage, anti-derive). Dette residuelle assumee : le mecanisme de migration reste additif sans rollback (documente, teste).

<a id="audit-vscode3-robustesse"></a>
**VSCode3 — Robustesse** : Bonne discipline de fail-open déjà en place (garde template à l'import, dégradation photo en cascade, hook de commit fail-open champ par champ) ; les points restants sont mineurs — troncature silencieuse possible sur des zip() jumelés, et une lacune de détection de flag git combiné dans le hook propagé aux 5 dépôts.

<a id="audit-vscode3-performance"></a>
**VSCode3 — Perf.** : Aucun goulot avéré dans le périmètre : verifier_geometrie() et build() restent linéaires en nombre de formes/slides (aucune boucle imbriquée sur un volume qui grossit), et le seul point d'E/S répété (une photo Openverse par chapitre, 9 appels) est déjà mis en cache sur disque par scène avant tout retour réseau, donc non répété d'un build à l'autre.

<a id="audit-vscode3-risque_technique"></a>
**VSCode3 — Risque tech.** : La dette structurelle mesurable n'est plus la logique du générateur (bien factorisée via pptx_deck.py, content_slide() réutilisé 34 fois) mais deux tendances qui s'aggravent à chaque itération : des binaires .pptx volumineux recommités en boucle, et un fichier générateur qui continue de grossir sans découpage.

<a id="audit-vscode3-securite"></a>
**VSCode3 — Sécurité** : Aucun secret en dur, aucune commande shell/eval/pickle sur une entrée externe, .env et secrets/ correctement gitignorés ; le générateur ne traite aucune entrée utilisateur non fiable (script local, template/manifest lus localement par chemin fixe dérivé de __file__).

<a id="audit-vscode4-robustesse"></a>
**VSCode4 — Robustesse** : Le finding du 2026-07-30 (« photo de divider manquante ne fait pas echouer build() ») est resolu : _remplir_cadre_chapitre remonte desormais l'origine reelle (photo/repli/cadre-absent) jusqu'a `problemes`, agregee par _problemes_dividers et bloquante dans le self-check de build() -- plus de degradation silencieuse. Gardes explicites deja en place et testees (template/media absents -> SystemExit nomme, la suite ne construit plus sur le livrable).

<a id="audit-vscode4-performance"></a>
**VSCode4 — Perf.** : Volume fixe et petit (20 slides, ~10 images de dividers, une v6 zip ouverte une fois) : aucune boucle imbriquee sur un gros volume ni de re-telechargement -- fetch Openverse cache sur disque par nom de fichier (os.path.exists avant fetch_to), aucun signe de N+1.

<a id="audit-vscode4-risque_technique"></a>
**VSCode4 — Risque tech.** : Rien de nouveau cote logique metier (bien teste, bien commente), mais trois sujets de dette structurelle mesures ce jour : un depot qui pese 2,4x plus que sa politique documentee ne le prevoit, une dependance reellement utilisee mais non declaree, et un generateur dont la taille (deja signalee en 2026-07-28) continue de croitre avec un historique de decisions recopie en dur dans un docstring de fonction.

<a id="audit-vscode4-securite"></a>
**VSCode4 — Sécurité** : Aucun secret, cle ou chemin machine en clair dans les fichiers suivis (grep cible + git grep sur C:\\Users\\ et claude.camus, aucun resultat hors .claude/skills) ; aucun eval/pickle/os.system/shell=True dans scripts/ ni tests/, les seuls subprocess (LibreOffice) sont en forme-liste avec timeout. Le garde-fou SSRF sur le telechargement d'images Openverse (resolution d'hote, refus des plages privees/loopback/link-local, non-suivi automatique des redirections) vit dans la skill partagee .claude/skills/pptx-framed-image -- hors code propre de VSCode4, donc hors perimetre de cet audit, mais deja corrige au moment de cette lecture.

<a id="audit-vscode5-robustesse"></a>
**VScode5 — Robustesse** : CRITIQUE -> MOYEN. Les quatre echecs silencieux qui portaient le niveau ont disparu et chacun a ete verifie : le garde-fou anti-perte se declenche desormais sur le cas reel (ligne locale tissee HORS chapitre), le journal d'usage ecrit sur stderr ce qu'il perd, l'installateur ne plante plus a mi-parcours, `propager_socle` sort 1 quand il refuse. Ce qui reste est d'une autre nature : le garde-fou repare est trop LARGE — reproduit, il refuse la propagation des que le hub REFORMULE une ligne de son propre socle, c'est-a-dire a la seule occasion ou l'outil sert — et sa porte de sortie (`--accepter-pertes`) desactive au passage, sans le dire, le controle de fraicheur d'export/ ajoute le meme jour. S'y ajoutent trois codes de sortie qui disent encore 0 sur un « rien fait ».

<a id="audit-vscode5-performance"></a>
**VScode5 — Perf.** : OK -> OK, sans changement de nature. Les correctifs ajoutent trois lectures (deux pour `_socle_perime`, une traversee d'export/ pour les orphelins) et une double boucle arbitrages x trouvailles au point du jour : mesures, tous les temps restent sous la seconde et demie pour des commandes lancees a la demande, et le hook de session reste a quelques dizaines de millisecondes de travail utile. Aucun goulot. Le seul point a surveiller est celui du matin, et il a empire en un jour : arbitrages.json est passe de 122 317 a 136 819 octets (+11,9 %) et le point du jour le reparse toujours trois fois.

<a id="audit-vscode5-risque_technique"></a>
**VScode5 — Risque tech.** : CRITIQUE -> MOYEN. Les cinq points qui portaient le niveau sont traites et verifies : l'assertion vacante a une valeur unique, les 2 tests rouges sont verts (701 passed), le socle publie est controle en fraicheur, `generer()` supprime enfin les orphelins qu'il se contentait de signaler, le hub n'est plus sa propre cible, et l'ancre de coupe est liee par un test. Ce qui empeche de descendre plus bas, c'est que le motif du jour n'est pas eteint : deux assertions restent VERTES sans le correctif qu'elles pretendent garder — dont celle qui protege le rempart contre le bruit qui avait bloque les 5 cibles — et le defaut n6 a ete referme par un ETAT DU MONDE, pas par une refonte : 14 des 21 tests de la suite s'executent contre les 5 depots tiers reels, et j'ai reproduit qu'un simple edit du socle non propage les fait retomber au rouge.

<a id="audit-vscode5-securite"></a>
**VScode5 — Sécurité** : CRITIQUE -> MOYEN. Les trois chemins par lesquels ces scripts pouvaient abimer un autre depot sont fermes, et chacun verifie dans les deux sens : la traversee de chemin est refusee (rien n'est ecrit dehors, exit 1), `--force` ne remplace plus le CLAUDE.md redige de la cible, une derive de corps n'est plus ecrasee sans `--accepter-derive`, et la SSRF `file://` de `stock_images` est fermee — les tests qui les gardent passent tous au ROUGE sur les sources d'avant. Les fondamentaux restent sains : aucun `shell=True`, `eval`, `exec`, `pickle` ni `os.system` sur les 2 197 lignes du perimetre, et les deux seuls `subprocess.run` passent argv en liste. Ce qui reste tient a la finition des gardes elles-memes : l'une ne resout pas les jonctions Windows, une autre ecrase un fichier voisin sans le dire, la troisieme ne couvre qu'une des deux lectures reseau du module.

## 3. Veille agentic

_Dernière veille : 2026-09-03T00:00:00 — skill `veille-agentic` (cadence 3 jours, déclenchable manuellement)._

| Sujet | Type | Statut | Projets concernés | Pertinence |
| --- | --- | --- | --- | --- |
| [VoltAgent/awesome-claude-code-subagents — 154+ sous-agents en 10 catégories](https://github.com/VoltAgent/awesome-claude-code-subagents) | sous-agent | adopte | VSCode1, VScode5 | Référentiel pour comparer/enrichir la flotte de 17 sous-agents de VSCode1 avant de la mutualiser via C4 — vérifier si des rôles manquants (security, data) y sont mieux définis. [adopte 2026-07-29 : utilisé comme grille de comparaison, PAS comme source à copier. Un seul agent greffé sur VSCode1 (security-auditor, cas d'usage daté Epic 10 / 2026-08-08) — greffe volontairement minimale, 11 des 17 agents locaux étant déjà jamais invoqués. Manques accessibilité/données documentés, non greffés : ils alimentent le tri du 2026-08-16.] |
| [BMAD-METHOD — v7 ANNONCEE (uv standard) — PAS sortie : derniere release v6.10.0](https://github.com/bmad-code-org/BMAD-METHOD/releases) | framework | ecarte | VSCode, VSCode1, VSCode2, VSCode3, VSCode4, VScode5 | Suivi 2026-07-29 : la v7 est sortie — uv remplace python3 pour tous les scripts (l'installateur le vérifie), bmad-forge-idea nouvelle skill cœur, bmad-architecture réécrite en routage par intention (les shims DEPRECATED de la flotte — create-architecture, create-prd, edit-prd, validate-prd — sont RETIRÉS en v7). Les 6 projets sont en v6.10.0 avec statu quo « aucune customisation jusqu'à la v7 » (arbitrage skills-jamais-utilisees 2026-07-27) : la migration est désormais ARBITRABLE — décider quand migrer et si le tri des 46 skills se fait à cette occasion. [2026-07-30 : ENTREE CORRIGEE apres verification a la source (API GitHub releases/latest = v6.10.0 du 2026-07-03, aucun tag v7*, dist-tag npm latest = 6.10.0). La v7 N EST PAS SORTIE. Deux des trois arguments de cette entree etaient des faits de v6.9.0 DEJA installes (bmad-forge-idea, reecriture de bmad-architecture - le routage par intention est deja en production sur les 6 depots). Le troisieme (uv standard) est une annonce prospective publiee dans les notes de v6.9.0, sans date. Statut repasse de nouveau a etudie : il n y a rien a arbitrer tant que la version n existe pas. CE QUI EST REEL AUJOURD HUI : uv est absent du PATH de la machine alors que 22 fichiers du v6.10.0 installe invoquent deja uv run en forme primaire (repli python3 documente mais non garanti) - c est un manque actuel, pas un prerequis de migration future. Le volet uv est SOLDE le 2026-07-30 : uv 0.11.32 installe (winget), uv run verifie de bout en bout sur un vrai script du dispositif. Reste en veille uniquement la sortie eventuelle de la v7.] [2026-08-31 : SUIVI 32 jours apres. La v7 n'est toujours pas sortie, mais v6.11.0 EST sortie le 2026-08-09/10 (verifie double source : GitHub API releases/latest published_at=2026-08-10T17:49:41Z, et CHANGELOG.md brut du depot). Changements reels, avec breaking changes : bmad-quick-dev renomme bmad-build (ancien id conserve via shim de compatibilite), catalogue de skills core reduit de 14 a 8 (revue+editorial fusionnes dans bmad-review, trio recherche fusionne dans bmad-deep-recon, doc+contexte fusionnes dans bmad-project-context), config bascule en TOML en couches, et surtout : uv + Python 3.11+ devient une EXIGENCE DURE pour les skills rendus (plus un repli documente comme en v6.10.0) — les renderers s'arretent desormais sur config manquante. Ecart de mesure : seul le hub (VScode5) a confirme la presence d'uv (0.11.32, installe le 2026-07-30) ; le statut d'uv sur VSCode/VSCode1/VSCode2/VSCode3/VSCode4 n'est mesure nulle part (grep sur criteres-pratiques.md : aucune occurrence d'uv). Migrer vers v6.11.0 sans verifier uv sur les 5 autres depots casserait les skills rendues. Reste etudie : pas encore arbitre, mais l'arbitrage ne devrait plus attendre la v7 — v6.11.0 est deja un palier avec un prerequis dur non verifie sur 5/6 projets.] [ecarte le 2026-09-01 : Ecartee : le titre dit lui-meme ANNONCEE, PAS sortie, et la verification a la source du 2026-07-30 l'a confirme (API GitHub releases/latest = v6.10.0 du 2026-07-03, aucun tag v7*, dist-tag npm latest = 6.10.0). Deux des trois arguments de l'entree etaient des faits de v6.9.0 DEJA installes. Surtout : la seule decision qu'elle bloquait — le gel « aucune customisation jusqu'a la v7 » — a ete LEVEE le 2026-07-31 sans attendre la v7, au motif qu'un gel conditionne a un evenement qui ne vient pas est un gel definitif qui ne dit pas son nom. Il ne reste donc rien a arbitrer ici. La migration redeviendra une decision a part entiere quand la v7 sortira vraiment ; la cadence de veille la re-signalera.] |
| [disler/claude-code-hooks-multi-agent-observability — observabilité multi-agents par hooks](https://github.com/disler/claude-code-hooks-multi-agent-observability) | outil | adopte | VScode5 | Même pattern que notre dispositif maison (hooks → événements → dashboard) mais en temps réel avec swim lanes par agent — source d'inspiration directe pour faire évoluer scan_transcripts/log_usage/wiki.html. [instruit le 2026-07-31] Verifie a la source : 1 501 etoiles, mais DERNIER PUSH le 2026-02-08, soit ~5,7 mois d'inactivite — vivant mais dormant. La note de pertinence ci-dessus etait FAUSSE sur un point : il n'y a PAS de swim lanes par agent, mais une timeline unifiee plus un graphique de densite d'activite. Ecart reel mesure : 12 types d'evenements captes chez eux (dont SubagentStop, echecs d'outil, demandes de permission) contre UN SEUL chez nous (log_usage.py, 42 lignes : PostToolUse sur Skill|Agent|Task), et un flux temps reel par WebSocket contre notre scan differe. Pile Bun + SQLite + Vue ecartee : un process persistant contredit un hub qui regenere un wiki statique a 0 token. RETENU A COUT BORNE, en attente d'arbitrage : capturer la FIN de sous-agent (duree, issue) dans log_usage.py, et etudier un panneau « runs en cours » dans serve_wiki.py. [2026-09-01 : ADOPTEE partiellement. Pile Bun+SQLite+Vue et flux WebSocket ECARTES (un process persistant contredit un hub qui regenere un wiki statique a 0 token ; depot dormant depuis le 2026-02-08). RETENU : log_usage.py capte desormais SubagentStop (la FIN d'un sous-agent, pas seulement son lancement) et marque un echec quand l'outil le DIT ; hook cable dans settings.json. Surtout, decouvert en instruisant l'adoption : usage.jsonl portait 250 lignes et AUCUN lecteur depuis le 2026-07-23. scan_projets.lire_journal_usage() + render_journal_usage_html() le lisent et le rendent — elargir la captation sans lecteur aurait double la depense sans rien acheter.] |
| [microsoft/hve-core — skill PowerPoint python-pptx pilotée par YAML](https://github.com/microsoft/hve-core/blob/main/.github/skills/experimental/powerpoint/SKILL.md) | skill | ecarte | VSCode1, VSCode2, VSCode3, VSCode4 | Approche content.yaml + style.yaml pour découpler contenu et mise en forme des decks — alternative structurée à comparer avec nos générateurs pptx_deck maison avant d'écrire le prochain. [instruit le 2026-07-31] Verifie : MIT, 1 307 etoiles, pousse le jour meme — mais la skill PPT vit sous .github/skills/EXPERIMENTAL/powerpoint/, non stabilisee par Microsoft lui-meme. Son apport : content.yaml + style.yaml par slide, un mode dry-run (parse sans build) et un validate_geometry.py (marges, gaps, debordement, degagement du titre). ECARTE pour une migration de VSCode3/VSCode4 : les deux ont un generateur Python fonctionnel et deja arbitre le 2026-07-23, migrer serait une refonte sans point de douleur identifie (R1 : correction minimale > refonte). On perdrait ajuster_police (adaptation dynamique au texte reel, indispensable sur du contenu client variable), les 22 patterns de deck-design-library, et rien ne prouve que leur validateur capte les 7 defauts que pptx-verify chasse par rendu reel. SANS OBJET pour VSCode (COMOP Node.js, pas python-pptx). SEULE PISTE RETENUE : importer l'idee du mode dry-run dans pptx-deck. [ecarte le 2026-09-01 : Ecartee sur arbitrage utilisateur du 2026-09-01, apres 40 jours en statut etudie. La decision etait DEJA prise et tracee le 2026-07-31 (« INSTRUIT, MIGRATION ECARTEE ») : la skill PPT de hve-core vit sous .github/skills/EXPERIMENTAL/, non stabilisee par Microsoft lui-meme, et migrer VSCode3/VSCode4 vers un pipeline YAML serait une refonte sans point de douleur identifie — contre R1, correction minimale > refonte. Seul le STATUT etait reste 'etudie', ce qui faisait annoncer chaque matin comme en attente une trouvaille deja tranchee. C'est exactement la panne que le finding veille:trouvailles-dormantes denonce : une decision prise mais non reinjectee dans l'etat.] |
| [hesreallyhim/awesome-claude-code — index de référence de l'écosystème Claude Code](https://github.com/hesreallyhim/awesome-claude-code) | rules | adopte | VScode5 | Point d'entrée durable pour les prochaines sessions de veille (skills, agents, hooks, plugins triés à la main) — à re-parcourir à chaque cycle plutôt que de re-chercher à froid. [ADOPTE le 2026-07-31] Verifie vivant a la source : 51 394 etoiles, pousse le jour meme, avec CONTRIBUTING/CODE_OF_CONDUCT/SECURITY et un index GENERE programmatiquement depuis des entrees structurees — curation reelle, pas un dump de liens. Inscrit comme source recurrente dans veille-agentic/SKILL.md, section « Sources a surveiller (publiques) », avec la reserve explicite qu'un index signale ce qui existe sans dire si c'est vivant ni si ca vaut pour cette flotte. Trois entrees reperees pour le prochain cycle : cctop (sessions actives et taille de contexte, utile aux 6 projets au titre de la discipline tokens), Claude Code Agent Monitor (arbres d'orchestration — a croiser avec la trouvaille observabilite), UI Craft (critique design par heuristiques Nielsen, pour les 2 apps web). |
| [Dev Browser — l'agent vérifie son travail dans un vrai navigateur (Playwright + sandbox WASM)](https://github.com/sawyerhood/dev-browser) | skill | ecarte | VSCode1, VSCode2 | Skill/plugin qui donne à Claude Code un navigateur piloté (API Playwright + outils pixel/DOM, scripts en sandbox QuickJS WASM sans accès disque/réseau hôte) pour TESTER ce qu'il produit — la vérification réelle des écrans de VSCode1 (questionnaire web) et VSCode2 (FastAPI+HTMX) repose aujourd'hui sur des tests HTTP et des screenshots manuels ; à comparer avant d'écrire un harnais navigateur maison. [instruit le 2026-07-31] Depot identifie avec certitude : SawyerHood/dev-browser, MIT, 6 490 etoiles, dernier push 2026-07-15. Point important souvent mal lu : le sandbox QuickJS WASM restreint le SCRIPT ecrit par l'agent, pas le navigateur — Chrome est un process normal qui atteint localhost sans probleme. SANS OBJET pour VSCode1 : app/scripts/capture-screenshots.js pilote deja un vrai Chrome sur localhost:3000 via Puppeteer ; l'apport se reduirait a la surete du sandbox et a l'API Playwright. OBJET REEL pour VSCode2 : grep confirme AUCUN playwright/selenium/puppeteer dans son dossier tests/ — une app FastAPI verifiee par pytest seul, sans aucun controle de rendu en navigateur. Reserve avant adoption : cela ajoute une dependance Node a un projet Python pur, a isoler en outillage agent plutot qu'en dependance projet. [ecarte le 2026-09-01 : Ecartee sur arbitrage utilisateur du 2026-09-01, apres 34 jours en statut etudie — la plus ancienne attente du dispositif, annoncee chaque matin par le hook. L'instruction du 2026-07-31 avait deja fait le travail : le sandbox QuickJS WASM restreint le SCRIPT ecrit par l'agent, pas le navigateur, et la trouvaille est SANS OBJET pour VSCode1, qui pilote deja un vrai Chrome sur localhost:3000 via app/scripts/capture-screenshots.js. L'objet reel se limitait a VSCode2 (FastAPI+HTMX), sans point de douleur mesure a ce jour. Ecarter n'interdit rien : si la verification en navigateur devient un besoin reel sur VSCode2, elle se rouvre par un arbitrage neuf, sur un besoin constate plutot que sur une possibilite.] |
| [stefanprodan/cctop — moniteur top-style en temps réel des sessions Claude Code](https://github.com/stefanprodan/cctop) | outil | ecarte | VScode5 | Lecture seule, aucun process persistant ni base de données (contrairement à disler/claude-code-hooks-multi-agent-observability déjà instruit et à hoangsonww/Claude-Code-Agent-Monitor croisé cette session, tous deux des stacks web/DB) — un simple binaire qui lit ~/.claude et la table des process pour afficher en direct mémoire, CPU, taille de contexte et état par session. Pertinent pour le hub qui pilote des sessions concurrentes sur 6 dépôts sans visibilité temps réel autre que le scan différé (state.json). Vérifié à la source (API GitHub) : 135 étoiles, licence Apache-2.0, pushed_at 2026-08-21T10:32:01Z — vivant, poussé il y a 10 jours. [2026-08-31 — ECARTE] Entree sans regle ni action correctives : moniteur temps reel optionnel, cote operateur. Un process persistant de surveillance est etranger a la philosophie du hub (etage 1 deterministe a 0 token, lance par hook). Reste installable a la main ; ne sera pas re-propose. |

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
| [Fork subagent actif par défaut (v2.1.232+) : risque de contaminer l'étape « revue en contexte frais »](https://code.claude.com/docs/en/agents) | Anthropic — Claude Code docs / « Run agents in parallel » + « Subagents » (fork mode ON par défaut en session interactive depuis v2.1.232, 13 août 2026) — citation vérifiée verbatim à la source : « Claude also spawns one itself where fork mode is on. » | adopte | VScode5 | Règle playbooks : l'étape de revue en contexte frais exclut explicitement le sous-agent type fork (et /subtask) — vérifiable par la présence d'une mention anti-fork explicite dans le contrat JSON de l'étape revue-fraiche des playbooks evolution-flotte et export-ppt-verifie. | Préciser dans evolution-flotte.md et export-ppt-verifie.md, à l'étape revue-fraiche, que le sous-agent doit être un sous-agent standard isolé (jamais un fork) ; évaluer si CLAUDE_CODE_FORK_SUBAGENT=0 au niveau du hub serait une garantie plus fiable qu'une simple consigne de prompt. |
| [Dynamic Workflows (outil Workflow) — orchestrer des dizaines à centaines de sous-agents via un script réexécutable](https://code.claude.com/docs/en/workflows) | Anthropic — Claude Code docs / « Run agents in parallel » (tableau comparatif subagents / agent view / agent teams / dynamic workflows) | adopte | VScode5 | Règle agent-orchestrator : au-delà d'une poignée de sous-agents ou quand les résultats doivent être vérifiés entre eux, le plan envisage un dynamic workflow (script via l'outil Workflow / skill workflow-authoring) plutôt qu'un fan-out manuel — critère de choix de plan, non mesurable à froid par le scan. | Étudier la skill workflow-authoring déjà installée avant la prochaine orchestration à grande échelle (>5 sous-agents ou vérification croisée) menée par agent-orchestrator ; si le critère se confirme utile en pratique, l'ajouter à SKILL.md en miroir du §2 ter déjà écrit pour agent teams. |
| [TTL de cache prompt par sous-agent (experimental.cacheTtl) — levier de discipline tokens non exploité](https://code.claude.com/docs/en/changelog) | Anthropic — Claude Code docs / changelog v2.1.248 (27 août 2026) : experimental.cacheTtl en frontmatter d'agent ("5m" ou "1h") + promptCacheTtl/subagentPromptCacheTtl | adopte | VScode5 | Critère scan (dimension discipline_tokens) : présence de cacheTtl en frontmatter des sous-agents à invocation répétée dans une même séance — mesurable à froid par grep sur .claude/agents/*.md. | Évaluer l'ajout de experimental.cacheTtl: "1h" aux frontmatters de bmad-revue.md / bmad-doc.md / bmad-recherche.md / bmad-cadrage.md / bmad-livraison.md (agents ré-invoqués en séquence dans une séance de routage §2 quinquies), en mesurant le gain réel via /cost avant de généraliser. |
| [Règle des deux corrections : /clear (pas /compact) après deux échecs consécutifs sur le même problème](https://davidsilvera.com/guides/coder-avec-claude/iterer-corriger-contexte) | davidsilvera.com — guide « Coder avec Claude », chapitre 7 « Savoir s'arrêter » (mise à jour affichée 7 août 2026) : « au bout de deux allers-retours ratés, stop » / « un /clear et un meilleur prompt battent dix rustines, à chaque fois ». Critères précisés : /clear si changement de sujet, deux corrections ratées, ou fausses pistes accumulées dans le fil ; /compact si même tâche mais fil long et détails sacrifiables. | nouveau | VScode5 | Critère scan (dimension discipline_tokens) : la section « discipline tokens » du CLAUDE.md mentionne explicitement un critère de bascule vers /clear (pas seulement le seuil /compact) — mesurable à froid par grep du texte de section, en extension du marqueur déjà mesuré (titre de section). | Compléter la section « Discipline de gestion des tokens » du CLAUDE.md du hub avec le critère /clear vs /compact du guide (deux échecs consécutifs sur le même problème → /clear + reformuler, pas une 3e rustine). Vérifier ensuite si les 5 autres projets de la flotte ont la même lacune avant de généraliser (non vérifié ce tour, hors périmètre du check ciblé). |
| [Seuil de dilution des skills (>10, purge à un mois d'inutilisation) — étendre la dormance déjà mesurée des porteurs à chaque skill individuelle](https://davidsilvera.com/guides/coder-avec-claude/skills-subagents-mcp-hooks) | davidsilvera.com — guide « Coder avec Claude », chapitre 9 « La boîte à outils » (mise à jour affichée 7 août 2026) : « une skill mérite création après la 3e répétition d'une explication identique, jamais avant » ; « chaque skill coûte sa description en permanence, au-delà de dix la dilution ralentit les réponses » ; « supprimez celles inutilisées depuis un mois ». | nouveau | VScode5 | Étendre la mesure de dormance déjà adoptée pour les porteurs (33 j sans invocation) à CHAQUE skill routée via un porteur (les 46 BMAD au minimum) — mesurable à froid via usage.jsonl / routing-hints.json (dernière invocation par skill), en miroir exact du mécanisme déjà en place pour les porteurs. | Avant le prochain tri BMAD, croiser la liste des 46 skills avec leur dernière invocation réelle dans usage.jsonl/routing-hints.json pour repérer celles inutilisées depuis >30 jours, à proposer en retrait ou fusion — proposition arbitrable, aucun retrait d'office. |
| [Aucune borne murale (wall-clock) fiable pour un sous-agent d'arrière-plan qui ne converge pas — maxTurns frontmatter documenté non appliqué, aucune durée journalisée dans le dispositif](https://code.claude.com/docs/en/agent-sdk/subagents) | Anthropic — Claude Agent SDK docs / Subagents, section « Cap subagent depth, concurrency, and spend » (seules bornes documentées : profondeur CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH, concurrence CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS, dépense max_budget_usd — AUCUNE borne de durée murale) + GitHub anthropics/claude-code issue #41143, « [BUG] maxTurns frontmatter not enforced on sub-agents — agent runs 72+ turns with maxTurns: 10 », fermée CLOSED as not planned, aucun correctif proposé. | adopte | VScode5 | Étendre la catégorie diagnostic `non-convergence` d'agent-supervisor à un second signal, distinct du « livrable rejeté à répétition » : un sous-agent d'arrière-plan sans notification au-delà d'un multiple (proposition : 3 à 5×) de la durée p95 des runs comparables déjà journalisés pour le même agent/skill — mesurable seulement une fois la durée effectivement captée (corollaire de l'action corrective). | (1) Apparier dans log_usage.py l'entrée de lancement (Agent/Task, déjà captée) et l'entrée SubagentStop pour produire un `duree_s` par run — aujourd'hui ni usage.jsonl ni runs.jsonl ne permettent de calculer une durée réelle, donc aucun seuil n'est aujourd'hui mesurable. (2) Documenter dans agent-orchestrator §2 ter la règle opérationnelle constatée cette session : au-delà d'un multiple de la durée des runs comparables sans notification, vérifier l'état plutôt qu'attendre indéfiniment, et ne JAMAIS s'appuyer sur `maxTurns` en frontmatter comme filet de sécurité (bug connu, fermé not-planned). (3) En cas d'arrêt sans réponse, relancer proprement plutôt que fabriquer un résultat — cohérent avec la règle déjà écrite « ne jamais anticiper le résultat async ». |
| [Aucune vérification de repos de la cible avant de dispatcher un sous-agent d'audit/exploration sur un AUTRE dépôt de la flotte — analogie écriture-concurrente, pas de source directe sur la contention en lecture](https://code.claude.com/docs/en/worktrees) | Anthropic — Claude Code docs / worktrees + GitHub anthropics/claude-code issue #55708 (« Agent tool's isolation: worktree does not isolate git HEAD modifications — subagent's git checkout affects parent repo's branch »). ANALOGIE ASSUMÉE, pas une correspondance directe : ces deux sources documentent la contention en ÉCRITURE (deux agents qui modifient le même état git), pas le cas rencontré ici — une session interactive active en continu pendant qu'un sous-agent LIT/audite le même dépôt. Aucune source publique trouvée traitant spécifiquement ce cas de contention en lecture (recherche ciblée sans résultat, cf. rapport). | adopte | VScode5 | Avant de dispatcher un sous-agent de lecture/audit vers un dépôt distant de la flotte, vérifier un signal de « dépôt chaud » (ex. deux relevés `git status --porcelain`/mtime espacés de quelques secondes qui diffèrent) — mesurable à froid par script, mais À TRAITER COMME GARDE-FOU MAISON, pas comme alignement sur une pratique documentée par un provider : aucune source ne la prescrit telle quelle. | Ajouter au playbook evolution-flotte (et en pré-requis d'un audit-technique sur cible distante) une étape « cible au repos ? » (deux relevés `git status --porcelain` espacés avant dispatch) ; si la cible est chaude, reporter le dispatch ou élargir explicitement le budget de patience attendu avant de qualifier le run de non convergent (cf. entrée précédente). |
| [Permission d'incertitude et relecture avant écriture — absentes d'audit-technique, qui force un niveau ok/moyen/critique par dimension sans option « non évalué », et n'a pas de passe de retrait des constats sans citation](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) | Anthropic — Claude Platform docs / Reduce hallucinations : « Allow Claude to say I don't know... This simple technique can drastically reduce false information » ; « Verify with citations... If it can't find a quote, it must retract the claim. » | adopte | VScode5 | Étendre le format `.claude/audits/<projet>.json` avec un niveau `non_evalue` par dimension (distinct de `ok`, réservé à une dimension non couverte faute de temps/accès) — mesurable à froid par grep sur les audits existants une fois adopté. | Proposer dans audit-technique/SKILL.md : ajouter `non_evalue` à la liste des niveaux (§ Règles) et une étape 3bis « relecture : tout finding sans fichier:ligne est retiré avant l'étape 4 » entre Qualifier et Écrire. |

