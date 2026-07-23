---
updated: 2026-07-23
generated-by: .claude/supervision/scan_transcripts.py (superviseur d'agents, étage 1)
---

# Supervision des agents — tableau de bord d'usage

> ⚠️ **Page générée automatiquement** (hook SessionStart → `.claude/supervision/scan_transcripts.py`).
> **Ne pas éditer à la main** — toute modification serait écrasée au prochain scan.
> Conception et phasage : [../../reflexions/agent-superviseur.md](../../reflexions/agent-superviseur.md).

Dernier scan : 2026-07-23T20:38:50+02:00 · **1 sessions** (transcripts) · **4** invocations de skills · **4** lancements de sous-agents.

## Skills — usage réel

| Skill | Famille | Invocations | Première | Dernière |
| --- | --- | --- | --- | --- |
| `agent-orchestrator` | projet | 3 | 2026-07-23 | 2026-07-23 |
| `agent-supervisor` | projet | 1 | 2026-07-23 | 2026-07-23 |

## Sous-agents

| Sous-agent | Lancements | Premier | Dernier |
| --- | --- | --- | --- |
| `general-purpose` | 4 | 2026-07-23 | 2026-07-23 |

## Jamais utilisés

**projet** — 4/6 jamais invoqués :

`deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic`

**BMAD** — 46/46 jamais invoqués :

<details><summary>Voir la liste</summary>

`bmad-advanced-elicitation`, `bmad-agent-analyst`, `bmad-agent-architect`, `bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer`, `bmad-architecture`, `bmad-brainstorming`, `bmad-check-implementation-readiness`, `bmad-checkpoint-preview`, `bmad-code-review`, `bmad-correct-course`, `bmad-create-architecture`, `bmad-create-epics-and-stories`, `bmad-create-prd`, `bmad-create-story`, `bmad-customize`, `bmad-dev-auto`, `bmad-dev-story`, `bmad-document-project`, `bmad-domain-research`, `bmad-edit-prd`, `bmad-editorial-review-prose`, `bmad-editorial-review-structure`, `bmad-forge-idea`, `bmad-generate-project-context`, `bmad-help`, `bmad-index-docs`, `bmad-market-research`, `bmad-party-mode`, `bmad-prd`, `bmad-prfaq`, `bmad-product-brief`, `bmad-qa-generate-e2e-tests`, `bmad-quick-dev`, `bmad-retrospective`, `bmad-review-adversarial-general`, `bmad-review-edge-case-hunter`, `bmad-shard-doc`, `bmad-spec`, `bmad-sprint-planning`, `bmad-sprint-status`, `bmad-technical-research`, `bmad-ux`, `bmad-validate-prd`

</details>

**global** — 5/5 jamais invoqués :

`pptx-deck`, `pptx-verify`, `restitution-deck-design`, `roadmap-keeper`, `skill-creator`

## TODO agents (constats automatiques)

1. **Trier les skills BMAD** : 46 installés, 0 invocation à ce jour — décider lesquels garder, customiser ou désinstaller.
2. **Skills projet sans usage** : `deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic` — vérifier pertinence et déclencheurs.

## Arbitrages enregistrés

_Constats clos par décision humaine (`.claude/supervision/arbitrages.json`) — l'usage réel reste mesuré ci-dessus._

- **`scan_transcripts.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : le scan compte désormais les skills invoquées en slash-command (<command-name> filtré sur les skills installées), le hint revue-increment est conditionnel à la présence réelle de la skill, et le fix slug (caractères non alphanumériques → tiret) est propagé. Recomptage complet de ce projet fait (agent-orchestrator ×3, agent-supervisor ×1 mesurés). Les 3 édits sont propagés aux 5 autres copies de la flotte par édits ciblés vérifiés (py_compile vert partout).
- **`log_run.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : mode --solde <prefixe-ts> <resultat> "note" ajouté (requalification tracée d'un run en-attente-validation — la validation utilisateur devient un événement de première classe du journal, testée sur les chemins nominal et erreurs). Propagé aux 5 autres copies (copie directe sur les identiques, insertion ciblée sur les divergées). Le bandeau du wiki affiche la commande.
- **`playbooks`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : playbook evolution-flotte créé (cadrage sur l'état réel → modification scopée → vérifications → commit limité au périmètre → wiki → journal), enregistré au catalogue et dans la table des playbooks de l'orchestrateur, statut éprouvé (capitalisé des 4 runs flotte du 2026-07-23).

## Diagnostic qualitatif (étage 2 — `agent-supervisor`)

_Diagnostic à jour — rien à signaler, tous les constats précédents ont été arbitrés._

---

_Étage O-C (croisement modèle × tâche × reprises, exploitation de `runs.jsonl`) : voir `.claude/orchestration/routing-hints.json`, régénéré à chaque session._
