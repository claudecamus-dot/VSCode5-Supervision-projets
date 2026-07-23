# CLAUDE.md — règles du hub de supervision

Ce projet supervise une **flotte d'autres projets** (VSCode, VSCode1–4). Sa particularité :
il agit **sur d'autres dépôts**. Les règles ci-dessous existent parce que chaque écart a
coûté une reprise réelle (voir `.claude/supervision/diagnostic.json` et les arbitrages).

## Ce que fait / ne fait pas ce projet

- **Fait** : inventorier, mesurer les pratiques, diagnostiquer, proposer, et — sur
  arbitrage — appliquer des correctifs à la flotte, puis journaliser.
- **Ne fait pas** : produire un livrable applicatif. Pas de test applicatif attendu ici
  au sens d'un produit ; les scripts (`scan_projets.py`, `log_run.py`,
  `scan_transcripts.py`) mériteraient néanmoins des tests (finding `risque_technique` de
  l'audit VScode5 — dette assumée).

## Règles absolues

- **R1 — Lire l'état réel avant d'écrire.** Le wiki éclaire, il ne remplace pas la lecture
  directe de la cible. Une reco « à appliquer » peut être déjà (partiellement) satisfaite
  (leçon VSCode1 : 5 skills « à rattacher » l'étaient déjà). Correction minimale > refonte.
- **R2 — Commit scopé au périmètre.** En agissant sur un autre dépôt, ne jamais embarquer
  ni écraser du travail non commité qui n'est pas le nôtre (leçon VSCode : 174 fichiers de
  churn BMAD découverts au commit). Toujours `git diff --cached --name-only` avant de
  committer ; exclure ce qui sort du périmètre.
- **R3 — Adapter au canal de la cible.** Ne pas plaquer un pattern : génération PPT via
  COMOP (VSCode) ≠ python-pptx ; `npm test` chaîné (VSCode1) ≠ framework ; réutiliser la
  skill préexistante du projet plutôt que la dupliquer.
- **R4 — Propose → arbitre → applique.** Le superviseur *propose*, l'utilisateur *arbitre*,
  l'orchestrateur *applique la version validée*. Jamais d'auto-application d'un correctif,
  même « évident ». Tout arbitrage (accepté OU refusé) est tracé dans `arbitrages.json`.
- **R5 — Vérité du journal.** Ne jamais logger `succes` sur un livrable que l'utilisateur
  doit valider : `en-attente-validation` tant que le « OK » n'est pas donné. Solder via
  `log_run.py --solde`, jamais par édition manuelle du journal.

## Vérifications avant commit

| Si le changement touche… | Alors… |
| --- | --- |
| Un script Python (`scan_projets.py`, hooks, supervision) | `py -m py_compile` sur le fichier |
| `settings.json` / un JSON de données | valider le JSON (`json.load`) |
| Le wiki | régénérer via `py scripts/scan_projets.py` et **ouvrir `docs/wiki.html`** pour contrôler le rendu réel |
| Un autre projet de la flotte | instancier le playbook `evolution-flotte` (cadrage réel → modif scopée → vérifs → commit scopé → wiki → journal) |

## Données générées (ne pas éditer à la main)

`docs/wiki.html`, `docs/wiki/projets-supervision.md`, `.claude/supervision/state.json`,
`.claude/orchestration/routing-hints.json` sont **régénérés** par les scans — les modifier
à la main est perdu au passage suivant. `diagnostic.json` s'écrit via `write_diagnostic.py`
(qui **écrase** — réécrire l'ensemble des findings ouverts, pas seulement les nouveaux).
`runs.jsonl` et `arbitrages.json` sont le journal et les décisions : append/édition via
leurs scripts.

## Cadences (hooks SessionStart)

- `scan_transcripts.py` — scan étage 1 déterministe à chaque session.
- `remind_veille_agentic.py` — rappelle la veille au-delà de 3 jours.
- Le diagnostic étage 2 (`agent-supervisor`) se relance à la demande ou quand le hook le
  signale périmé (14 j).
