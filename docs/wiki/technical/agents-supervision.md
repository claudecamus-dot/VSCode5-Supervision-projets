---
updated: 2026-07-24
generated-by: .claude/supervision/scan_transcripts.py (superviseur d'agents, étage 1)
---

# Supervision des agents — tableau de bord d'usage

> ⚠️ **Page générée automatiquement** (hook SessionStart → `.claude/supervision/scan_transcripts.py`).
> **Ne pas éditer à la main** — toute modification serait écrasée au prochain scan.
> Conception et phasage : [../../reflexions/agent-superviseur.md](../../reflexions/agent-superviseur.md).

Dernier scan : 2026-07-24T09:26:29+02:00 · **2 sessions** (transcripts) · **6** invocations de skills · **10** lancements de sous-agents.

## Skills — usage réel

| Skill | Famille | Invocations | Première | Dernière |
| --- | --- | --- | --- | --- |
| `agent-orchestrator` | projet | 4 | 2026-07-23 | 2026-07-24 |
| `agent-supervisor` | projet | 1 | 2026-07-23 | 2026-07-23 |
| `audit-technique` | projet | 1 | 2026-07-24 | 2026-07-24 |

## Sous-agents

| Sous-agent | Lancements | Premier | Dernier |
| --- | --- | --- | --- |
| `general-purpose` | 9 | 2026-07-23 | 2026-07-23 |
| `Explore` | 1 | 2026-07-23 | 2026-07-23 |

## Jamais utilisés

**projet** — 2/7 jamais invoqués :

`deck-design-library`, `veille-agentic`

**BMAD** — 46/46 jamais invoqués :

<details><summary>Voir la liste</summary>

`bmad-advanced-elicitation`, `bmad-agent-analyst`, `bmad-agent-architect`, `bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer`, `bmad-architecture`, `bmad-brainstorming`, `bmad-check-implementation-readiness`, `bmad-checkpoint-preview`, `bmad-code-review`, `bmad-correct-course`, `bmad-create-architecture`, `bmad-create-epics-and-stories`, `bmad-create-prd`, `bmad-create-story`, `bmad-customize`, `bmad-dev-auto`, `bmad-dev-story`, `bmad-document-project`, `bmad-domain-research`, `bmad-edit-prd`, `bmad-editorial-review-prose`, `bmad-editorial-review-structure`, `bmad-forge-idea`, `bmad-generate-project-context`, `bmad-help`, `bmad-index-docs`, `bmad-market-research`, `bmad-party-mode`, `bmad-prd`, `bmad-prfaq`, `bmad-product-brief`, `bmad-qa-generate-e2e-tests`, `bmad-quick-dev`, `bmad-retrospective`, `bmad-review-adversarial-general`, `bmad-review-edge-case-hunter`, `bmad-shard-doc`, `bmad-spec`, `bmad-sprint-planning`, `bmad-sprint-status`, `bmad-technical-research`, `bmad-ux`, `bmad-validate-prd`

</details>

**global** — 2/5 jamais invoqués :

`restitution-deck-design`, `skill-creator`

## Skills bibliothèque / référence

_Consommés en lisant/exécutant leurs `scripts/`, ou via un sous-agent qui les suit (ex. `ppt-designer`, qui n'a pas l'outil Skill) — le compteur d'invocations ne peut structurellement pas les voir. `n=0` n'y vaut donc PAS « mort » : ne pas désinstaller sur ce seul signal (constat superviseur #2)._

`pptx-deck`, `pptx-framed-image`, `pptx-verify`, `roadmap-keeper`, `slide-text-polish`

## TODO agents (constats automatiques)

1. **Trier les skills BMAD** : 46 installés, 0 invocation à ce jour — décider lesquels garder, customiser ou désinstaller.
2. **Skills projet sans usage** : `deck-design-library`, `veille-agentic` — vérifier pertinence et déclencheurs.

## Arbitrages enregistrés

_Constats clos par décision humaine (`.claude/supervision/arbitrages.json`) — l'usage réel reste mesuré ci-dessus._

- **`famille:linter`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : ruff configuré (pyproject.toml, baseline F/I/UP/B) sur VSCode2 (102 points mesurés, B008 ignoré car idiome FastAPI) et VScode5 (0 point après nettoyage). PAS de --fix aveugle : un ruff --fix sur VSCode2 a retiré un ré-export (is_configured) et cassé un import — reverté, tests re-verts (40 passed) ; correction au fil de l'eau. VSCode/VSCode3/VSCode4 hors périmètre (peu de code).
- **`famille:revue-code`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : hook warn_verif_before_commit porté de VSCode1 vers VSCode2, marqueurs adaptés (pytest/pptx-verify/revue-increment au lieu de npm test), câblé en PreToolUse. Rappel non bloquant au commit si du code app/ part sans vérif réelle dans la session. Fail-open vérifié. L'agent reviewer dédié reste optionnel (coût).
- **`famille:design-review`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : skill deck-design-review greffée sur VSCode4, RÉÉCRITE pour son deck OHC réel (15 slides : couverture, sommaire, dividers chapitre teardrop, leviers, personas, architecture, existant, évaluation, mentorat, arbitrages, séquencement, roadmap) et son canal (rendu LibreOffice, générateur generate_deck_ohc.py) — pas un copier-coller de VSCode2. VSCode3 reste à traiter.
- **`famille:cadrage-produit`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : product-brief rédigé pour VScode5 (docs/product-brief.md — persona = orchestrateur de flotte, why = ne pas re-découvrir/re-corriger le même écart projet par projet, besoins = voir/alerter/comparer/approfondir/corriger/veiller, proposition de valeur = piloter la flotte comme un seul système via la boucle propose→arbitre→applique). VSCode4 (deck RH) reste à cadrer sur demande. Autres projets : fragments suffisants.
- **`famille:documentation`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« applique la reco ») : le hub VScode5, jusque-là sans README ni CLAUDE.md, en est doté — README.md (ce que fait le dispositif, démarrage, skills, structure, boucle d'amélioration) et CLAUDE.md (règles R1-R5 pour agir sur la flotte : lire l'état réel, commit scopé, adapter au canal, propose→arbitre→applique, vérité du journal + vérifications avant commit). Dimension documentation VScode5 : moyen → ok. Non traité sur VSCode/VSCode3/VSCode4 (README via bmad-document-project sur demande) — hors périmètre de cet arbitrage.
- **`famille:tests`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« applique la reco pratique-test ») : couverture de test outillée sur les 2 projets à forte densité de test, via le playbook evolution-flotte. VSCode2 : pytest-cov ajouté à requirements-dev.txt, commande documentée dans conventions.md, 1ère mesure ~38 % (pptx_deck 56 %, pptx_export 48 %). VSCode1 : c8 en devDep + script npm test:cov + étape CI, 1ère mesure 84,67 % lignes. Aucun seuil imposé (on mesure d'abord). Non traité sur VSCode/VSCode3/VSCode4 (peu de code / pré-code) — hors périmètre assumé.
- **`scan_transcripts.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : le scan compte désormais les skills invoquées en slash-command (<command-name> filtré sur les skills installées), le hint revue-increment est conditionnel à la présence réelle de la skill, et le fix slug (caractères non alphanumériques → tiret) est propagé. Recomptage complet de ce projet fait (agent-orchestrator ×3, agent-supervisor ×1 mesurés). Les 3 édits sont propagés aux 5 autres copies de la flotte par édits ciblés vérifiés (py_compile vert partout).
- **`log_run.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : mode --solde <prefixe-ts> <resultat> "note" ajouté (requalification tracée d'un run en-attente-validation — la validation utilisateur devient un événement de première classe du journal, testée sur les chemins nominal et erreurs). Propagé aux 5 autres copies (copie directe sur les identiques, insertion ciblée sur les divergées). Le bandeau du wiki affiche la commande.
- **`playbooks`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : playbook evolution-flotte créé (cadrage sur l'état réel → modification scopée → vérifications → commit limité au périmètre → wiki → journal), enregistré au catalogue et dans la table des playbooks de l'orchestrateur, statut éprouvé (capitalisé des 4 runs flotte du 2026-07-23).
- **`famille:dispositif-partage`** (2026-07-24) : ACCEPTÉ + APPLIQUÉ (P1 de l'analyse craft) : la dette risque_technique CRITIQUE (audit VScode5 — 6 copies divergentes de scan_transcripts.py/log_run.py maintenues à la main) est résorbée par un canon unique + synchronisation, remplaçant la propagation manuelle par édits ciblés du 2026-07-23 (l'approche qui avait laissé diverger les copies). Canon dans .claude/dispositif/canon/, propagé par sync_dispositif.py (en-tête « généré — ne pas éditer localement », modes --check/--projet). Le cadrage a révélé que la dette n'était pas uniforme : version canonique de fait partagée par 3 projets + 2 améliorations éparpillées jamais réunies — détection des skills consommées par lecture (ex-VSCode1) et arbitrage restreint par catégorie (ex-VSCode3). Le canon = UNION des deux : chaque projet GAGNE ce qui lui manquait, aucun ne perd. Commits scopés (2 fichiers/cible + dispositif/ au hub) et push main sur les 6 remotes ; scans relancés 6/6 sans échec. Suivi : re-lancer audit-technique VScode5 pour sortir la dimension de « critique ».

## Diagnostic qualitatif (étage 2 — `agent-supervisor`)

_Diagnostic ⚠️ à relancer (> 14 j) — rien à signaler, tous les constats précédents ont été arbitrés._

---

_Étage O-C (croisement modèle × tâche × reprises, exploitation de `runs.jsonl`) : voir `.claude/orchestration/routing-hints.json`, régénéré à chaque session._
