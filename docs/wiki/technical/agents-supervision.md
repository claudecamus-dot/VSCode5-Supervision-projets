---
updated: 2026-07-23
generated-by: .claude/supervision/scan_transcripts.py (superviseur d'agents, étage 1)
---

# Supervision des agents — tableau de bord d'usage

> ⚠️ **Page générée automatiquement** (hook SessionStart → `.claude/supervision/scan_transcripts.py`).
> **Ne pas éditer à la main** — toute modification serait écrasée au prochain scan.
> Conception et phasage : [../../reflexions/agent-superviseur.md](../../reflexions/agent-superviseur.md).

Dernier scan : 2026-07-23T21:56:22+02:00 · **1 sessions** (transcripts) · **4** invocations de skills · **5** lancements de sous-agents.

## Skills — usage réel

| Skill | Famille | Invocations | Première | Dernière |
| --- | --- | --- | --- | --- |
| `agent-orchestrator` | projet | 3 | 2026-07-23 | 2026-07-23 |
| `agent-supervisor` | projet | 1 | 2026-07-23 | 2026-07-23 |

## Sous-agents

| Sous-agent | Lancements | Premier | Dernier |
| --- | --- | --- | --- |
| `general-purpose` | 4 | 2026-07-23 | 2026-07-23 |
| `Explore` | 1 | 2026-07-23 | 2026-07-23 |

## Jamais utilisés

**projet** — 5/7 jamais invoqués :

`audit-technique`, `deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic`

**BMAD** — 46/46 jamais invoqués :

<details><summary>Voir la liste</summary>

`bmad-advanced-elicitation`, `bmad-agent-analyst`, `bmad-agent-architect`, `bmad-agent-dev`, `bmad-agent-pm`, `bmad-agent-tech-writer`, `bmad-agent-ux-designer`, `bmad-architecture`, `bmad-brainstorming`, `bmad-check-implementation-readiness`, `bmad-checkpoint-preview`, `bmad-code-review`, `bmad-correct-course`, `bmad-create-architecture`, `bmad-create-epics-and-stories`, `bmad-create-prd`, `bmad-create-story`, `bmad-customize`, `bmad-dev-auto`, `bmad-dev-story`, `bmad-document-project`, `bmad-domain-research`, `bmad-edit-prd`, `bmad-editorial-review-prose`, `bmad-editorial-review-structure`, `bmad-forge-idea`, `bmad-generate-project-context`, `bmad-help`, `bmad-index-docs`, `bmad-market-research`, `bmad-party-mode`, `bmad-prd`, `bmad-prfaq`, `bmad-product-brief`, `bmad-qa-generate-e2e-tests`, `bmad-quick-dev`, `bmad-retrospective`, `bmad-review-adversarial-general`, `bmad-review-edge-case-hunter`, `bmad-shard-doc`, `bmad-spec`, `bmad-sprint-planning`, `bmad-sprint-status`, `bmad-technical-research`, `bmad-ux`, `bmad-validate-prd`

</details>

**global** — 5/5 jamais invoqués :

`pptx-deck`, `pptx-verify`, `restitution-deck-design`, `roadmap-keeper`, `skill-creator`

## TODO agents (constats automatiques)

1. **Trier les skills BMAD** : 46 installés, 0 invocation à ce jour — décider lesquels garder, customiser ou désinstaller.
2. **Skills projet sans usage** : `audit-technique`, `deck-design-library`, `pptx-framed-image`, `slide-text-polish`, `veille-agentic` — vérifier pertinence et déclencheurs.

## Arbitrages enregistrés

_Constats clos par décision humaine (`.claude/supervision/arbitrages.json`) — l'usage réel reste mesuré ci-dessus._

- **`famille:tests`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« applique la reco pratique-test ») : couverture de test outillée sur les 2 projets à forte densité de test, via le playbook evolution-flotte. VSCode2 : pytest-cov ajouté à requirements-dev.txt, commande documentée dans conventions.md, 1ère mesure ~38 % (pptx_deck 56 %, pptx_export 48 %). VSCode1 : c8 en devDep + script npm test:cov + étape CI, 1ère mesure 84,67 % lignes. Aucun seuil imposé (on mesure d'abord). Non traité sur VSCode/VSCode3/VSCode4 (peu de code / pré-code) — hors périmètre assumé.
- **`scan_transcripts.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : le scan compte désormais les skills invoquées en slash-command (<command-name> filtré sur les skills installées), le hint revue-increment est conditionnel à la présence réelle de la skill, et le fix slug (caractères non alphanumériques → tiret) est propagé. Recomptage complet de ce projet fait (agent-orchestrator ×3, agent-supervisor ×1 mesurés). Les 3 édits sont propagés aux 5 autres copies de la flotte par édits ciblés vérifiés (py_compile vert partout).
- **`log_run.py`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : mode --solde <prefixe-ts> <resultat> "note" ajouté (requalification tracée d'un run en-attente-validation — la validation utilisateur devient un événement de première classe du journal, testée sur les chemins nominal et erreurs). Propagé aux 5 autres copies (copie directe sur les identiques, insertion ciblée sur les divergées). Le bandeau du wiki affiche la commande.
- **`playbooks`** (2026-07-23) : ACCEPTÉ + APPLIQUÉ (« traite tout ») : playbook evolution-flotte créé (cadrage sur l'état réel → modification scopée → vérifications → commit limité au périmètre → wiki → journal), enregistré au catalogue et dans la table des playbooks de l'orchestrateur, statut éprouvé (capitalisé des 4 runs flotte du 2026-07-23).

## Diagnostic qualitatif (étage 2 — `agent-supervisor`)

_Diagnostic à jour._

1. **Aucun linter Python sur la flotte (pyproject.toml inexistant partout) alors que 5/6 ont du code Python ; seul VSCode1 a un linter (ESLint, JS)** — Introduire ruff (zero-config) sur les 2 plus gros projets Python d'abord. · **Proposition** : pyproject.toml minimal [tool.ruff] sur VSCode2 puis VScode5, documente dans conventions.md. Propageable via evolution-flotte une fois eprouve sur 1 projet.
2. **La revue de code outillee (agent reviewer + hook pre-commit) n'existe que sur VSCode1 ; les 5 autres n'ont que bmad-code-review generique, jamais force avant commit** — Porter le hook pre-commit (avertit si aucune verif reelle avant un commit de code) sur les projets a code produit. · **Proposition** : Propager warn_verif_before_commit.py vers VSCode2 en priorite via evolution-flotte. L'agent reviewer dedie reste optionnel (cout) ; le hook est 0 token.
3. **3 projets n'ont pas de README utile a la racine ; VScode5 n'a ni README ni CLAUDE.md (hub de supervision sans porte d'entree)** — Doter au minimum VScode5 (le hub) d'un README + CLAUDE.md decrivant le dispositif. · **Proposition** : VScode5 : rediger README.md (scan_projets, veille, audit) + CLAUDE.md (regles du hub) directement. VSCode/3/4 : bmad-document-project ou README via bmad-agent-tech-writer, sur demande. Priorite VScode5 (le superviseur de la flotte est le moins documente).
4. **3 projets a deck (VSCode, VSCode3, VSCode4) n'ont pas deck-design-review — revue de design par impression, pas par contrat de slide** — Greffer deck-design-review adaptee au deck de chaque projet, comme sur VSCode1/2. · **Proposition** : Porter deck-design-review sur VSCode4 (deck RH actif) puis VSCode3, contrat par type de slide adapte au deck reel. Faible priorite : deja deck-design-library + ppt-designer presents.
5. **2 projets (VSCode4, VScode5) n'ont aucun artefact de cadrage produit (persona, why, besoins, proposition de valeur) ; les autres n'en ont que des fragments** — Formaliser un cadrage leger la ou le projet a un enjeu produit. · **Proposition** : Sur demande (skills BMAD) : bmad-product-brief pour VScode5 (persona = utilisateur de la flotte, why = ne pas re-decouvrir les ecarts a la main, valeur = pilotage + remediation) ; bmad-forge-idea pour pressuriser. Faible priorite : outillage, pas des produits a marche.

---

_Étage O-C (croisement modèle × tâche × reprises, exploitation de `runs.jsonl`) : voir `.claude/orchestration/routing-hints.json`, régénéré à chaque session._
