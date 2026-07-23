# VScode5 — Supervision multi-projets

Hub de **supervision de la flotte de projets Claude Code** de l'utilisateur (VSCode,
VSCode1, VSCode2, VSCode3, VSCode4 + ce projet). Il n'a pas de livrable applicatif : son
produit est le **pilotage** — savoir, sans re-fouiller chaque dépôt à la main, quels
agents/skills/playbooks sont installés où, quelles pratiques d'ingénierie et de produit
sont en place, et quoi corriger en priorité.

## Ce qu'il fait

1. **Inventaire agentic** de chaque projet (BMAD, skills, sous-agents, playbooks, hooks).
2. **Analyse des pratiques** sur 9 dimensions (2 étages) : couverture de test technique et
   fonctionnelle, revue de code, revue d'incrément, design, documentation, cadrage
   produit, pratiques+rules, sécurité (proxies) — plus un étage qualitatif à la demande
   (robustesse, performance, risque technique, failles de sécurité).
3. **Cadences** : relance les scans locaux, signale les diagnostics périmés, les runs
   `en-attente-validation` à solder, les projets sans commit récent.
4. **Veille agentic** : repère sur GitHub public les agents/skills/playbooks pertinents.
5. **Boucle propose → arbitre → applique** : le superviseur propose des correctifs,
   l'utilisateur arbitre, l'orchestrateur applique (sur ce projet ou un autre de la flotte)
   et enregistre l'arbitrage.

Le tout se lit dans **une page** : [`docs/wiki.html`](docs/wiki.html) (autonome, ouvrable
sans serveur).

## Démarrage

Prérequis : Python 3 (`py` sur Windows), Git, Node (pour BMAD). Aucune dépendance à
installer — les scripts n'utilisent que la bibliothèque standard.

```bash
# 1. Régénérer le wiki de supervision (relance les scans locaux des 6 projets)
py scripts/scan_projets.py            # --no-refresh pour ne pas relancer les scans locaux

# 2. Ouvrir le tableau de bord
#    Windows : start docs/wiki.html   —   ou double-clic sur le fichier
```

La liste des projets supervisés et leur livrable principal (site web ou dernier deck PPT)
est dans [`projets.json`](projets.json).

## Skills du dispositif

| Skill | Rôle |
| --- | --- |
| `agent-orchestrator` | Qualifie une demande, compose/exécute un plan, applique les recos arbitrées, journalise |
| `agent-supervisor` | Diagnostic étage 2 : usage des agents **et** pratiques (test/dev/revue/design/doc/produit) |
| `veille-agentic` | Veille GitHub public (cadence 3 j ou manuel) → `.claude/veille/veille.json` |
| `audit-technique` | Audit qualitatif à la demande (robustesse/perf/risque/sécurité) → `.claude/audits/<projet>.json` |

Skills PPT réutilisables également présentes : `deck-design-library`, `pptx-framed-image`,
`slide-text-polish` (+ les globales `pptx-deck`, `pptx-verify`, `restitution-deck-design`).

## Structure

```
projets.json                     # les projets supervisés + leur livrable
scripts/scan_projets.py          # le scanner (inventaire + pratiques + cadences + wiki)
docs/wiki.html                   # tableau de bord autonome (généré)
docs/wiki/projets-supervision.md # version markdown (générée)
docs/reflexions/                 # notes de conception (roadmap d'amélioration)
.claude/skills/                  # skills du dispositif + BMAD
.claude/orchestration/           # playbooks, catalogue, journal des runs, log_run.py
.claude/supervision/             # scan étage 1, diagnostic, arbitrages, write_diagnostic.py
.claude/veille/                  # résultats de veille
.claude/audits/                  # audits techniques par projet
_bmad/                           # BMAD-METHOD (core + bmm)
```

## Boucle d'amélioration

Pour agir sur un constat du superviseur : `applique la reco <catégorie>` (ex.
`pratique-doc`, `pratique-test`). L'orchestrateur lit `diagnostic.json`, applique la
proposition **arbitrée** (via le playbook `evolution-flotte` si la cible est un autre
projet), puis enregistre l'arbitrage dans `.claude/supervision/arbitrages.json` — ce qui
clôt le finding et le retire des alertes du wiki.

Pour solder un run en attente : `py .claude/orchestration/log_run.py --solde <prefixe-ts>
succes "note de validation"`.
