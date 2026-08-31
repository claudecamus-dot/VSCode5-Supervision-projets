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
- **R6 — Exécuter avant d'écrire.** Tout **chiffre**, nom de script, compte d'artefacts ou
  version publiée s'écrit avec la commande qui l'a produit — sinon il est marqué
  « estimation non mesurée ». Si une vérification est **exécutable**, elle passe AVANT la
  rédaction, pas après : lancer le script, ouvrir la page servie, appeler la fonction.
  Motif mesuré (finding `etudes:faits-verifiables-non-verifies`, 2026-07-31) : **6
  corrections en 48 h**, toutes rattrapées en aval — une étude invalidée sur 3 faits pour
  un résolveur jamais lancé, une latence fausse d'un facteur 3, une CI annoncée 1/6 alors
  qu'elle était 5/6. `evolution-flotte` : 36 runs pour **22 reprises** (19 runs en
  ont eu au moins une), contre 1 reprise sur 4 runs pour `dev-verifie` — mesuré le
  2026-08-31 sur `runs.jsonl` (80 runs). Corollaire : **l'étage 1 mesure la présence,
  jamais le fonctionnement** —
  une skill comptée « installée » peut ne pas démarrer (4 sur 46 étaient dans ce cas).

## Vérifications avant commit

| Si le changement touche… | Alors… |
| --- | --- |
| Un script Python (`scan_projets.py`, hooks, supervision) | `py -m py_compile` sur le fichier |
| Les tests ou les scripts qu'ils couvrent | `py -m pytest tests/ -q --cov=scripts --cov=.claude/dispositif/canon` — couverture mesurée (2026-07-27 : 24 % ; 2026-08-31 : **67 %**), aucun seuil imposé. Un script lancé en **sous-processus** (hooks, CLI) s'affiche à 0 % sans être non testé : `coverage.py` n'instrumente pas les fils |
| `settings.json` / un JSON de données | valider le JSON (`json.load`) |
| Le wiki | régénérer via `py scripts/scan_projets.py` et **ouvrir `docs/wiki.html`** pour contrôler le rendu réel |
| Une source du kit agentic (skill de pilotage, sous-agent, hook, playbook) | `py .claude/dispositif/export_agentic.py` puis `--check` — sinon le kit publié dérive en silence |
| Un autre projet de la flotte | instancier le playbook `evolution-flotte` (cadrage réel → modif scopée → vérifs → commit scopé → wiki → journal) |

## Données générées (ne pas éditer à la main)

`docs/wiki.html`, `docs/wiki/projets-supervision.md`, `docs/wiki/index.md`,
`.claude/supervision/state.json`, `.claude/orchestration/routing-hints.json` sont
**régénérés** par les scans — les modifier
à la main est perdu au passage suivant. `diagnostic.json` s'écrit via `write_diagnostic.py`
(qui **écrase** — réécrire l'ensemble des findings ouverts, pas seulement les nouveaux).
`runs.jsonl` et `arbitrages.json` sont le journal et les décisions : append/édition via
leurs scripts.

`export/` est **entièrement généré** par `py .claude/dispositif/export_agentic.py` : c'est
le kit agentic repris par les autres projets (skills de pilotage, sous-agents, hooks,
playbooks, canon) plus son installateur auto-portant. Le modifier à la main est perdu à la
régénération — corriger la source dans le hub, puis régénérer. `--check` signale la dérive
entre les sources vivantes et le kit publié : c'est ce garde-fou qui manquait quand le
déploiement servait, sans le dire, un `agent-orchestrator` de 120 lignes contre 467 au hub
(mesuré le 2026-08-31). Deux hooks (`remind_revue_increment`, `warn_verif_before_commit`)
sont sourcés depuis VSCode2 (provenance donnée par le docstring de
`warn_verif_before_commit.py` ; CLAUDE.md disait VSCode3 — corrigé le 2026-08-31) :
leur version du hub est spécialisée « canal hub » et n'a pas
de sens dans un projet applicatif.

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
  et les **cinq fichiers générés volumineux**, à interroger par `grep` ciblé — tailles
  mesurées le 2026-08-31 (`stat -c%s`), et **à re-mesurer plutôt qu'à croire** : elles
  grossissent à chaque incrément.
  `docs/wiki.html` (346 Ko), `.claude/orchestration/runs.jsonl` (152 Ko),
  `.claude/orchestration/routing-hints.json` (108 Ko),
  `.claude/supervision/arbitrages.json` (105 Ko),
  `docs/wiki/technical/agents-supervision.md` (106 Ko).
  Les chiffres précédents dataient du 2026-07-30 et sous-estimaient de 32 à 62 % : qui
  budgétait un `Read` dessus se trompait d'un facteur 1,6 (revue du 2026-08-31).
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
- `remind_revue_increment.py` — rappelle la boucle `/revue-increment` avant de considérer
  un incrément livré.
- `point_du_jour.py` — liste ce qui attend une décision de l'utilisateur (findings sans
  arbitrage, trouvailles de veille non tranchées).
- Le diagnostic étage 2 (`agent-supervisor`) se relance à la demande ou quand le hook le
  signale périmé (14 j).
