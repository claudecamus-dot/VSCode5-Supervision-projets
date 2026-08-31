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

## Skills de livrable installées dans ce projet (copiées depuis VSCode2, génériques)

| Skill | Usage |
| --- | --- |
| `deck-design-library` | Bibliothèque de patterns de slides par situation (verbatims, trajectoire, maturité, offre chiffrée…) |
| `pptx-framed-image` | Insertion d'image épousant la forme exacte d'un cadre de template PPT |
| `slide-text-polish` | Linter/amélioration de la qualité rédactionnelle des slides |
| `pdf-quality` | Génération de PDF sur gabarit reportlab **et** vérification mesurée du résultat (`pdf_verify.py` : remplissage, débordements, polices embarquées, texte réellement rendu) — à charger dès qu'un projet de la flotte produit un PDF |

## Duo orchestrateur / superviseur + veille

| Skill | Usage |
| --- | --- |
| `agent-orchestrator` | Qualifie une demande, compose un plan (cascade/parallèle/async), l'exécute, journalise |
| `agent-supervisor` | Diagnostic qualitatif étage 2 : KO répétés, inefficacité, agents morts, vérifications manquantes |
| `veille-agentic` | Veille GitHub public (agents, sous-agents, skills, rules, playbooks) — cadence 3 j (hook SessionStart) ou manuel ; sortie `.claude/veille/veille.json` → section 3 du wiki |
| `audit-technique` | Audit qualitatif d'un projet (robustesse, performance, risque technique, failles de sécurité — lit le code) ; sortie `.claude/audits/<projet>.json` → étage qualitatif de la section 2 du wiki. À la demande (facturé), pas à chaque scan |
| `revue-increment` | Revue **et amélioration** de fin d'incrément du hub : vérité du journal (runs soldés via `--solde`), arbitrages tracés, wiki régénéré et regardé, pytest vert, commits scopés (R2). Applique les correctifs puis re-vérifie — une revue constat-seulement ne vaut rien. Rappelée par le hook `remind_revue_increment.py` |

## Outillage projet (code produit)

| Outil | Usage |
| --- | --- |
| `scripts/scan_projets.py` | Scanner multi-projets (config `projets.json`) → `docs/wiki/projets-supervision.md` + `docs/wiki.html` (tableau alertes + détails repliables + veille) |

## Sous-agents maison (`.claude/agents/`, créés le 2026-07-30)

Types invocables par l'outil `Agent`. Tous portent l'outil `Skill` — leurs invocations de
skills sont donc **comptées** par l'étage 1 du superviseur (`scan_transcripts.py` ne filtre
pas les sidechains). Le contrat de sortie de chacun est dans son fichier.

| Sous-agent | Famille portée | Modèle | Écrit ? |
| --- | --- | --- | --- |
| `bmad-revue` | Revue de code/diff, critique adversariale, cas limites, revue prose/structure, checkpoint, rétrospective, `bmad-help`, `bmad-customize` | opus | Non — signale, ne corrige pas |
| `bmad-doc` | Documentation brownfield, index de docs, découpage, rédaction technique | sonnet | Oui (docs du projet cible) |
| `bmad-recherche` | Recherche technique / domaine / marché, idéation | sonnet | Rapport, et fichier si demandé |
| `bmad-cadrage` | Brief produit, PRD, PRFAQ, SPEC, forge-idea, architecture, UX, project-context, party-mode — régime **proposé** | opus | Oui (artefacts de cadrage) |
| `bmad-livraison` | Epics/stories, sprint, correct-course, readiness, dev-story, quick-dev, tests e2e — régime **proposé** | sonnet | Oui (code du projet cible) |
| `veille-agentic` | Veille agentic (dépôts publics + doc des providers) sur cadence 3 j | sonnet | `veille.json` uniquement, statut `nouveau` |
| `agent-supervisor` | Diagnostic étage 2 délégué — s'appuie sur `bmad-revue` (preuve sur code réel) et `veille-agentic` (écart à l'état de l'art) | opus | `diagnostic.json` via `write_diagnostic.py` — **sans outils `Write`/`Edit`**, garde-fou structurel |
| `agent-orchestrator` | L'orchestrateur lui-même : déléguer une orchestration entière hors du contexte principal | hérité | Oui, selon le chantier — jamais de commit ni de journal |

Aucun ne committe, ne pousse, ni n'écrit le journal (`runs.jsonl`) ou les arbitrages : ces
gestes restent à la session principale (irréversible = synchrone + confirmation).

## Commandes (`.claude/commands/`)

| Commande | Effet |
| --- | --- |
| `/orchestre <demande>` | Appel explicite de l'orchestrateur — charge la skill et applique sa méthode en 5 étapes (vaut mandat d'orchestrer) |

## BMAD-METHOD (v6.10.0, modules core + bmm)

46 skills `bmad-*` installées (agents de rôle : `bmad-agent-analyst`, `bmad-agent-architect`,
`bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer` ;
tâches : création PRD/architecture/stories, revues, recherche, brainstorming, etc.).

**Intégrées au workflow depuis le 2026-07-30** (arbitrage utilisateur). L'ancienne règle
« uniquement sur demande explicite, via `bmad-help` » avait un résultat mesuré :
0 invocation sur 113 sessions, et un TODO `agent-mort` au wiki. Désormais l'orchestrateur
les **route par besoin détecté** — table complète en § 2 quinquies de sa skill, verrouillée
par `tests/test_orchestration_bmad.py` :

- **d'office** — bornée ET ne rend qu'un rapport : revue, recherche, rétrospective,
  orientation ;
- **annoncé puis validé** — la skill coûte cher (PRD, architecture, UX, epics/stories,
  sprint, implémentation, party-mode) **ou elle écrit un fichier réel** (documentation,
  index, découpage). Second critère ajouté le 2026-07-30 par l'arbitrage du finding
  `orchestrateur:regime-office-ecriture` : R4 n'interdit pas la dépense, il interdit
  l'auto-application — une écriture non arbitrée la viole, même rapide.

4 skills ne sont jamais routées, toutes dépréciées par BMAD : `bmad-create-prd`,
`bmad-edit-prd`, `bmad-validate-prd` → `bmad-prd` ; `bmad-create-architecture` →
`bmad-architecture`.

`bmad-customize` **n'est plus gelée** : l'arbitrage `skills-jamais-utilisees` du
2026-07-27 (« aucune customisation jusqu'à la v7 ») a été levé le 2026-07-31 — attendre
une v7 qui ne sort pas est un gel définitif qui ne dit pas son nom. Elle est routée en
régime **proposé** (elle écrit un `.toml` réel). **La table de routage verrouillée par
`tests/test_orchestration_bmad.py` fait foi** : ce catalogue avait gardé un mois de retard
sur elle (revue du 2026-08-31) — en cas de doute, c'est la table de
`.claude/skills/agent-orchestrator/SKILL.md` qui tranche, pas cette page.

Le hub ne produisant pas de livrable applicatif, seules les familles revue / doc /
recherche / rétro ont un objet sur lui-même : cadrage, conception, planification et
implémentation visent les projets de la flotte, via `evolution-flotte` (commit scopé, R2).

## Playbooks (`.claude/orchestration/playbooks/`)

| Playbook | Pour | Statut |
| --- | --- | --- |
| `evolution-flotte` | Modifier un AUTRE projet de la flotte (correction, déploiement, propagation) : cadrage sur l'état réel → modification scopée → vérifs → commit limité au périmètre → wiki → journal | Éprouvé (capitalisé des 4 runs flotte du 2026-07-23) |
| `dev-verifie` | Implémentation/correction avec tests + vérification réelle + revue avant commit | Confirmé — 4 runs réels, 4 succès (mesuré le 2026-08-31 sur `runs.jsonl`) |
| `export-ppt-verifie` | Génération/évolution d'un deck PPT avec vérification au rendu réel obligatoire | Importé (VSCode2), **0 run réel** — toujours à confirmer |
| `revue-design-parallele` | Revue multi-angles d'un livrable en fan-out puis consolidation | 2 runs réels — 1 succès, 1 en attente de validation (revue du hub, 2026-08-31) |

## Non repris depuis VSCode2 (couplés au code de l'app Interview-to-Deck)

`deck-design-review`, `priority-matrix`, `swot-matrix`, `run-dev-server` référencent des
fonctions précises de `pptx_export.py` ou l'app FastAPI de VSCode2 — sans objet ici. Si un
besoin équivalent apparaît, le créer via `skill-creator` plutôt que copier tel quel un
skill qui suppose un autre code.

C'est exactement ce qui a été fait pour la revue de fin d'incrément :
**`.claude/skills/revue-increment/` existe** dans ce hub, écrite pour son canal propre
(vérité du journal, arbitrages, wiki, pytest, commits scopés), rappelée à chaque session
par le hook `remind_revue_increment.py` et publiée dans le kit `export/`. Cette page la
listait encore comme « non reprise » jusqu'au 2026-08-31.
