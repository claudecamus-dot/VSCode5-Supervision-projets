---
updated: 2026-07-23
generated-by: .claude/supervision/scan_transcripts.py (superviseur d'agents, étage 1)
---

# Supervision des agents — tableau de bord d'usage

> ⚠️ **Page générée automatiquement** (hook SessionStart → `.claude/supervision/scan_transcripts.py`).
> **Ne pas éditer à la main** — toute modification serait écrasée au prochain scan.
> Conception et phasage : [../../reflexions/agent-superviseur.md](../../reflexions/agent-superviseur.md).

Dernier scan : 2026-07-23T20:23:45+02:00 · **1 sessions** (transcripts) · **1** invocations de skills · **4** lancements de sous-agents.

## Skills — usage réel

| Skill | Famille | Invocations | Première | Dernière |
| --- | --- | --- | --- | --- |
| `agent-supervisor` | projet | 1 | 2026-07-23 | 2026-07-23 |

## Sous-agents

| Sous-agent | Lancements | Premier | Dernier |
| --- | --- | --- | --- |
| `general-purpose` | 4 | 2026-07-23 | 2026-07-23 |

## Jamais utilisés

**projet** — 5/6 jamais invoqués :

`agent-orchestrator`, `deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic`

**BMAD** — 46/46 jamais invoqués :

<details><summary>Voir la liste</summary>

`bmad-advanced-elicitation`, `bmad-agent-analyst`, `bmad-agent-architect`, `bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer`, `bmad-architecture`, `bmad-brainstorming`, `bmad-check-implementation-readiness`, `bmad-checkpoint-preview`, `bmad-code-review`, `bmad-correct-course`, `bmad-create-architecture`, `bmad-create-epics-and-stories`, `bmad-create-prd`, `bmad-create-story`, `bmad-customize`, `bmad-dev-auto`, `bmad-dev-story`, `bmad-document-project`, `bmad-domain-research`, `bmad-edit-prd`, `bmad-editorial-review-prose`, `bmad-editorial-review-structure`, `bmad-forge-idea`, `bmad-generate-project-context`, `bmad-help`, `bmad-index-docs`, `bmad-market-research`, `bmad-party-mode`, `bmad-prd`, `bmad-prfaq`, `bmad-product-brief`, `bmad-qa-generate-e2e-tests`, `bmad-quick-dev`, `bmad-retrospective`, `bmad-review-adversarial-general`, `bmad-review-edge-case-hunter`, `bmad-shard-doc`, `bmad-spec`, `bmad-sprint-planning`, `bmad-sprint-status`, `bmad-technical-research`, `bmad-ux`, `bmad-validate-prd`

</details>

**global** — 5/5 jamais invoqués :

`pptx-deck`, `pptx-verify`, `restitution-deck-design`, `roadmap-keeper`, `skill-creator`

## TODO agents (constats automatiques)

1. **Trier les skills BMAD** : 46 installés, 0 invocation à ce jour — décider lesquels garder, customiser ou désinstaller.
2. **Skills projet sans usage** : `agent-orchestrator`, `deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic` — vérifier pertinence et déclencheurs.

## Diagnostic qualitatif (étage 2 — `agent-supervisor`)

_Diagnostic à jour._

1. **Le scan etage 1 porte de VSCode2 sous-mesure CE projet : les skills lancees en slash-command comptent 0 - agent-orchestrator et agent-supervisor apparaissent 'jamais utilisees' malgre 6 runs orchestres** — Passe d'adaptation du script porte : compter les command-message comme invocations de skill, parametrer le hint revue-increment sur les skills reellement presentes. · **Proposition** : 1 edit cible dans scan_transcripts.py (detection des <command-name> dans les transcripts -> compteur skills) + remplacer le texte du hint par une reference a l'etape terminale generique 'revue finale'. Puis propager le fix slug + ces 2 edits aux 5 autres copies (candidat n1 de l'increment 4 divergence des copies).
2. **La boucle en-attente-validation ne se referme jamais seule : 5 runs sur 6 sont restes ouverts jusqu'a une demande utilisateur explicite, et le solde s'est fait par edition manuelle du journal** — Outiller la transition de statut : la validation utilisateur est un evenement de premiere classe du journal, pas une rature. · **Proposition** : Ajouter a log_run.py un mode solde : py log_run.py --solde <ts> 'succes|partiel|echec' 'note de validation' qui requalifie le run existant en tracant date+motif. Le bandeau 'runs a solder' du wiki mentionne la commande exacte a copier-coller.
3. **Les 3 playbooks importes ne matchent pas les demandes reelles du projet : 5 runs sur 6 en composition libre et 4 resolutions ad hoc (2 creations, 2 evolutions) en une seule journee** — Capitaliser le pattern deja joue 4 fois (VSCode2, VSCode1, VSCode x2 corrections/deploiements) en playbook au lieu de recomposer a vide. · **Proposition** : Creer via generate/manuel le playbook 'evolution-flotte' : cadrage multi-projets (lire l'etat REEL de la cible avant d'ecrire - lecon VSCode1 ou tout etait deja rattache) -> modification scoped -> verification (py_compile/tests/grep coherence) -> commit scoped au perimetre (jamais le churn preexistant) -> wiki rafraichi -> journal. Declencheurs : 'corrige/rattache/deploie/met a jour sur VSCodeN'.

---

_Étage O-C (croisement modèle × tâche × reprises, exploitation de `runs.jsonl`) : voir `.claude/orchestration/routing-hints.json`, régénéré à chaque session._
