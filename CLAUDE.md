# CLAUDE.md — règles du hub de supervision

Ce projet supervise une **flotte d'autres projets** (VSCode, VSCode1–4). Sa particularité :
il agit **sur d'autres dépôts**. Les règles ci-dessous existent parce que chaque écart a
coûté une reprise réelle (voir `.claude/supervision/diagnostic.json` et les arbitrages).

## Ce que fait / ne fait pas ce projet

- **Fait** : inventorier, mesurer les pratiques, diagnostiquer, proposer, et — sur
  arbitrage — appliquer des correctifs à la flotte, puis journaliser.
- **Ne fait pas** : produire un livrable applicatif. Pas de test applicatif attendu ici
  au sens d'un produit — mais les scripts, eux, **sont** testés : `scan_projets.py` est
  exercé par 26 fichiers de `tests/`, `scan_transcripts.py` par 8, `log_run.py` par 7,
  sur 38 (mesuré le 2026-09-01, `grep -rl` ; la couverture est dans le tableau ci-dessous).
  Cette ligne annonçait une « dette assumée » éteinte depuis longtemps : une règle qui
  décrit une dette soldée fait renoncer à ce qui existe déjà.

## Règles absolues

- **R1 — Lire l'état réel avant d'écrire.** Le wiki éclaire, il ne remplace pas la lecture
  directe de la cible. Une reco « à appliquer » peut être déjà (partiellement) satisfaite
  (leçon VSCode1 : 5 skills « à rattacher » l'étaient déjà). Correction minimale > refonte.
  Vaut pour CE fichier aussi : un texte qui décrit un état révolu envoie travailler à faux.
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
  qu'elle était 5/6. Reprises par playbook, mesurées sur `runs.jsonl` :
  <!-- CHIFFRES-MESURES:REPRISES:START — régénéré par scripts/scan_projets.py, ne pas éditer à la main -->
  - `evolution-flotte` : 26 reprise(s) sur 40 run(s) — 0.65 par run
  - `dev-verifie` : 9 reprise(s) sur 10 run(s) — 0.90 par run
  - `revue-design-parallele` : 1 reprise(s) sur 2 run(s) — 0.50 par run
  <!-- CHIFFRES-MESURES:REPRISES:END -->
  R6 tient sur les 6 corrections en 48 h, pas sur ce tableau — un playbook sûr contre un
  risqué n'est plus ce qu'il montre ; lire les ratios avant de s'en réclamer.
  Corollaire : **l'étage 1 mesure la présence, jamais le fonctionnement** — une skill
  comptée « installée » peut ne pas démarrer (4 sur 46 étaient dans ce cas).

## Vérifications avant commit

| Si le changement touche… | Alors… |
| --- | --- |
| Un script Python (`scan_projets.py`, hooks, supervision) | `py -m py_compile` sur le fichier |
| Les tests ou les scripts qu'ils couvrent | `py -m pytest tests/ -q --cov=scripts --cov=.claude/dispositif/canon` — couverture mesurée (2026-07-27 : 24 % ; 2026-08-31 : 67 % ; 2026-09-01 : **75 %** sur 663 tests), aucun seuil imposé. Un script lancé en **sous-processus** (hooks, CLI) s'affiche à 0 % sans être non testé : `coverage.py` n'instrumente pas les fils |
| `settings.json` / un JSON de données | valider le JSON (`json.load`) |
| Le wiki | régénérer via `py scripts/scan_projets.py`, puis contrôler le rendu réel **sur le canal servi** : `py scripts/serve_wiki.py` et ouvrir `http://localhost:8765`. Un `file://` sur `docs/wiki.html` suffit pour juger la mise en page, mais **la console y est morte par construction** (l'origine devient `null`, aucune vue n'est comptée) — donc y contrôler, c'est vérifier la moitié éclairée |
| Une source du kit agentic (skill de pilotage, sous-agent, hook, playbook) | `py .claude/dispositif/export_agentic.py` puis `--check` — sinon le kit publié dérive en silence |
| Un autre projet de la flotte | instancier le playbook `evolution-flotte` (cadrage réel → modif scopée → vérifs → commit scopé → wiki → journal) |

Pas de `\| tail`/`\| head` ni de `2>&1` sur une commande du dispositif (pytest, sync,
scan) : le classificateur d'auto-mode les refuse plus que la commande nue (6 refus sur
11 portaient un tube, 7 une redirection, mesuré 2026-09-04) — lire la sortie complète.

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
(mesuré le 2026-08-31).

Deux hooks (`remind_revue_increment`, `warn_verif_before_commit`) sont sourcés depuis
**VSCode3** — `export_agentic.GENERIQUE` pointe `~/Documents/VSCode3/.claude/hooks` ; c'est
cette constante qui fait foi, jamais un docstring. Leur version du hub est spécialisée
« canal hub », sans sens dans un projet applicatif. `warn_verif_before_commit` lit un
`.claude/warn_verif_before_commit.json` optionnel (chemin dérivé de `__file__`), repli
générique champ par champ, message composé depuis les valeurs réellement configurées,
fail-open préservé, verrouillé par un test — VSCode3 garde son comportement via sa propre
configuration.

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
  **régénérées à chaque scan** (`os.path.getsize`), plus à re-mesurer à la main :
  <!-- CHIFFRES-MESURES:VOLUMINEUX:START — régénéré par scripts/scan_projets.py, ne pas éditer à la main -->
  `docs/wiki.html` (514 Ko),
  `.claude/orchestration/runs.jsonl` (292 Ko),
  `.claude/orchestration/routing-hints.json` (205 Ko),
  `.claude/supervision/arbitrages.json` (199 Ko),
  `docs/wiki/technical/agents-supervision.md` (194 Ko).
  <!-- CHIFFRES-MESURES:VOLUMINEUX:END -->
  Écrites à la main avant le 2026-09-01, elles se trompaient déjà de +9 à +36 % d'un jour
  sur l'autre — une consigne d'économie de tokens adossée à des chiffres périmés coûte ce
  qu'elle prétend épargner. Mesuré : un `Read` de `runs.jsonl` entier coûte **~109 000
  tokens**.
- **`runs.jsonl` se lit par la FIN**, jamais depuis le début : c'est un journal
  append-only, les runs utiles sont les derniers. Lire les ~10 dernières lignes
  (`Read` avec `offset`, ou `tail`), pas les 57 premières — le fichier grossit à chaque
  incrément et le coût avec lui.
- **Sous-agent pour toute sortie volumineuse** : exploration de la flotte, inventaire,
  longs logs. Les porteurs de `.claude/agents/` existent pour ça, et leur invocation reste
  comptée par l'étage 1 (le scan ne filtre pas les sidechains).
- **Lire l'état réel avant d'écrire (R1) n'est pas une invitation à tout lire** : cadrer sur
  la cible exacte du chantier, pas sur le dépôt entier.
- **`/compact` dès ~40 %** de fenêtre ; **`/clear` (pas `/compact`) après deux corrections
  ratées sur le même problème** — `/clear` et un meilleur prompt battent une 3e rustine.
- **Le cache de prompt de la session expire en ~5 min** : enchaîner les actions d'un même
  chantier plutôt que laisser une session ouverte en pause — chaque reprise après
  expiration refacture le contexte entier. `cacheTtl: "1h"` ne vaut que pour les 2 porteurs
  qui le déclarent (`bmad-revue`, `bmad-recherche`), pas la session principale.

## Cadences (hooks SessionStart)

- `scan_transcripts.py` — scan étage 1 déterministe à chaque session.
- `remind_veille_agentic.py` — rappelle la veille au-delà de 3 jours.
- `remind_revue_increment.py` — rappelle la boucle `/revue-increment` avant de considérer
  un incrément livré.
- `point_du_jour.py` — liste ce qui attend une décision de l'utilisateur (findings sans
  arbitrage, trouvailles de veille non tranchées).
- Le diagnostic étage 2 (`agent-supervisor`) se relance à la demande ou quand le hook le
  signale périmé (14 j).
