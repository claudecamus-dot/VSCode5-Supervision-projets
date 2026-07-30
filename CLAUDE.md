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
| Les tests ou les scripts qu'ils couvrent | `py -m pytest tests/ -q --cov=scripts --cov=.claude/dispositif/canon` — couverture mesurée (1ʳᵉ mesure 2026-07-27 : 24 %), aucun seuil imposé |
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

## Discipline de gestion des tokens

Le contexte est un cache actif facturé à chaque tour, pas une mémoire gratuite. Ce hub a
une exposition que les autres projets n'ont pas : **il lit six dépôts**, dont une flotte de
46 skills BMAD et des pages générées de plusieurs centaines de kilo-octets. Un dump
récursif y coûte davantage qu'ailleurs. Règles concrètes (adoptées le 2026-07-30 depuis la
veille du 2026-07-24 — la seule pratique que la flotte avait et pas le hub) :

- **Le bon étage d'abord.** Le scan déterministe est à **0 token** : lire son résultat
  (`state.json`, `routing-hints.json`, la page mesurée du wiki) avant de mobiliser un étage
  facturé. Le diagnostic `agent-supervisor` et `audit-technique` lisent du code réel — on
  les lance pour trancher, pas pour se renseigner.
- **Ne jamais ouvrir en entier** : les transcripts JSONL (`~/.claude/projects/*.jsonl`) et
  `usage.jsonl` — l'étage 1 les a déjà agrégés, et ils contiennent du contenu client ;
  `_bmad/`, `_bmad-output/`, `.claude/skills/bmad-*` — 46 skills, grep avant read ;
  et les **cinq fichiers générés volumineux**, à interroger par `grep` ciblé :
  `docs/wiki.html` (~230 Ko), `.claude/orchestration/runs.jsonl` (~94 Ko),
  `.claude/orchestration/routing-hints.json` (~82 Ko),
  `.claude/supervision/arbitrages.json` (~78 Ko),
  `docs/wiki/technical/agents-supervision.md` (~78 Ko).
  Les quatre derniers manquaient à cette liste jusqu'au 2026-07-30 : mesuré, un
  `Read` de `runs.jsonl` entier coûte **~109 000 tokens** (l'étude de consommation s'est
  fait tronquer à 42 589 tokens pour la moitié du fichier).
- **`runs.jsonl` se lit par la FIN**, jamais depuis le début : c'est un journal
  append-only, les runs utiles sont les derniers. Lire les ~10 dernières lignes
  (`Read` avec `offset`, ou `tail`), pas les 57 premières — le fichier grossit à chaque
  incrément et le coût avec lui.
- **Sous-agent pour toute sortie volumineuse** : exploration de la flotte, inventaire,
  longs logs. Les porteurs de `.claude/agents/` existent pour ça, et leur invocation reste
  comptée par l'étage 1 (le scan ne filtre pas les sidechains).
- **Lire l'état réel avant d'écrire (R1) n'est pas une invitation à tout lire** : cadrer sur
  la cible exacte du chantier, pas sur le dépôt entier.
- **`/compact` dès ~40 %** de fenêtre utilisée si la séance doit continuer sur le même sujet.

## Cadences (hooks SessionStart)

- `scan_transcripts.py` — scan étage 1 déterministe à chaque session.
- `remind_veille_agentic.py` — rappelle la veille au-delà de 3 jours.
- Le diagnostic étage 2 (`agent-supervisor`) se relance à la demande ou quand le hook le
  signale périmé (14 j).
