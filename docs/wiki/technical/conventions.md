---
updated: 2026-07-29
confidence: confirmed
agents: [agent-orchestrator]
---

# Conventions — hub de supervision

Ce projet **agit sur d'autres dépôts** : chaque convention ci-dessous existe parce qu'un
écart a coûté une reprise réelle. Les règles de gouvernance (R1-R5) vivent dans
[`CLAUDE.md`](../../../CLAUDE.md) ; ce document couvre le **comment coder** du hub.

## Linting & formatage

- **ruff** configuré (`pyproject.toml`, baseline `select = F, I, UP, B`, ligne 100).
  Lancer : `py -m ruff check .` — baseline à 0 point, à garder à 0.
- **Pas de `--fix` aveugle** : un `ruff --fix` a retiré un ré-export (`is_configured`) et
  cassé un import sur VSCode2 le 2026-07-23. Corriger au fil de l'eau, tests à l'appui.

## Tests & couverture

- Suite `pytest` dans `tests/`. Lancer : `py -m pytest tests/ -q`.
- Couverture : `py -m pytest tests/ -q --cov=scripts --cov=.claude/dispositif/canon`
  — 1ʳᵉ mesure 2026-07-27 : **24 %**, aucun seuil imposé (on mesure d'abord).
- **Verdict lu sur la ligne de synthèse réelle** (`N passed`), jamais sur une sortie
  tronquée. Sur ce poste, la jonction `%TEMP%\pytest-of-*\pytest-current` est morte :
  passer `--basetemp <dossier jetable>` sinon pytest crashe au teardown et masque le
  verdict (exit 1 sur une suite pourtant verte).
- **CI** : `.github/workflows/ci.yml` rejoue la suite à chaque push/PR (ruff informatif,
  pytest bloquant).

## Canon du dispositif — la règle qui coûte le plus cher quand on l'oublie

- Les scripts partagés par les 6 projets vivent dans `.claude/dispositif/canon/`. Toute
  correction se fait **DANS le canon**, jamais dans une copie : une copie éditée
  localement est écrasée au sync suivant (en-tête « GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT »).
- Après `py .claude/dispositif/sync_dispositif.py`, **rejouer les suites des cibles** que
  le script liste : le canon synchronise les scripts, **pas** les tests locaux, qui
  peuvent asserter sur un comportement que le canon vient de changer (incident du
  2026-07-29 — un sync « 12/12 à jour » avait cassé un test-contrat de VSCode2).
- **stdout du canon en ASCII strict** : les tests des projets cibles capturent ce flux en
  subprocess sous console cp1252 ; un caractère hors cp1252 (emoji, `—`, texte libre du
  journal) y lève `UnicodeDecodeError` et rend stdout `None`. Échapper les données
  interpolées (`.encode("ascii", "replace")`), pas seulement les littéraux.

## Données générées — ne jamais éditer à la main

`docs/wiki.html`, `docs/wiki/projets-supervision.md`, `.claude/supervision/state.json`,
`.claude/orchestration/routing-hints.json` sont **régénérés** par les scans. `diagnostic.json`
s'écrit via `write_diagnostic.py` (qui écrase : réécrire TOUS les findings ouverts).
`runs.jsonl` et `arbitrages.json` s'éditent par leurs scripts (`log_run.py --solde`,
`refuser_arbitrage.py`) — jamais à la main.

Le **JS du wiki** est un fichier réel : `docs/wiki_app.js`, édité comme du code et inliné à
la génération. Les valeurs dynamiques passent par le bloc JSON `wiki-config` — **aucune
interpolation de chaîne Python dans du JS** (deux bugs d'échappement en une journée le
2026-07-24, dont un cassant la page entière).

## Nommage & style

- Fichiers Python : `snake_case.py` ; fonctions/variables : `snake_case` ; classes :
  `PascalCase`.
- **Vocabulaire FR du domaine** dans le code comme dans les échanges : *finding*,
  *arbitrage*, *pastille*, *cadence*, *reliquat*, *écart*. Ne pas angliciser.
- Docstrings : dire **pourquoi** (le constat ou la leçon qui a motivé le code), pas ce que
  la ligne suivante fait déjà voir.

## Git

- Messages en français, impératif, titre < 70 caractères disant le **pourquoi**.
- Message de commit écrit **dans un fichier** puis `git commit -F <fichier>` — jamais de
  here-string/heredoc pour un message portant apostrophes, backticks ou `$` (3 reprises
  payées : heredoc bash 2026-07-24, here-string PowerShell 2026-07-27, collision de casse
  `realOpen`/`RealOpen` 2026-07-28 — les variables PowerShell sont insensibles à la casse).
- **Commit scopé au périmètre** (R2) : `git diff --cached --name-only` relu avant chaque
  commit, churn étranger exclu. Sessions concurrentes fréquentes sur la flotte —
  re-vérifier `git status` juste avant de stager.
