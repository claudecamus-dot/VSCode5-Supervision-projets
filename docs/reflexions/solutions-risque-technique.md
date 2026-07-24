# Solutions — résorber le risque technique restant de la flotte

Rédigée le 2026-07-24, après la campagne risque+perf (les 6 projets sont 🟠 sur
`risque_technique` ; perf est 🟢 partout). Chaque solution part du **finding d'audit
réel** et d'un **fait vérifié aujourd'hui** — pas d'une envie de refactoring. Format :
fait observé → solution concrète (le diff d'intention) → effort (S/M/L) → vérification.

**Boucle de gouvernance inchangée** : ce document *propose*, l'humain *arbitre*,
l'orchestrateur *applique* (evolution-flotte, commits scopés, suites relancées).

---

## 1. La duplication `pptx_deck` (VSCode2 → VSCode3 → VSCode4) — le sujet n°1

**Fait observé (mesuré aujourd'hui)** : les 3 copies ont **forké pour de vrai** —
VSCode2 608 l (source), VSCode3 305 l (sous-ensemble taillé : −307 l), VSCode4 930 l
(+393 lignes de primitives PROPRES). Ce n'est PAS la situation du canon P1
(scan_transcripts, où les copies étaient quasi identiques) : un canon+sync naïf
**écraserait la valeur locale** de VSCode4.

**Solution en 2 temps** :

1. **(S) Surveiller la divergence au lieu de la subir** : le scan calcule un hash du
   **cœur commun** (les fonctions présentes dans les 3 copies : `ajuster_police`,
   `estimer_lignes`, échelle typo…) et rend une matrice `identique / divergé / absent`
   dans le wiki. La divergence d'une fonction partagée devient un signal visible, les
   extensions locales restent libres. C'est le § 1.1 de `ameliorations-supervision.md`,
   jamais outillé — et le pré-requis factuel du temps 2.
2. **(L, phasé) Extraire le cœur commun en canon** `dispositif/canon/pptx_deck_core.py`
   (uniquement les fonctions identiques dans les 3 copies), propagé par le
   `sync_dispositif.py` existant ; chaque projet garde son fichier local qui
   `from pptx_deck_core import *` puis ajoute SES primitives. Migration projet par
   projet, suites de deck relancées à chaque pas (`test_generate_deck*.py`, 330 VSCode2).

**Vérification** : matrice visible dans le wiki (temps 1) ; suites deck vertes par
projet + `sync --check` sans dérive (temps 2).

## 2. VScode5 — sortir le JS inline de `scan_projets.py`

**Fait observé** : 287 lignes de JS (~15 k chars) vivent dans une chaîne Python d'un
fichier de 2 476 lignes ; 2 bugs d'échappement Python→JS payés le même jour (dont un
cassant TOUTE la page) ; la garde `node --check` (posée aujourd'hui) teste le produit
mais l'éditabilité reste piégeuse.

**Solution (S/M)** : déplacer le JS dans un **vrai fichier** `scripts/wiki_app.js` ;
`render_html` le lit (`read_text`) et l'inline tel quel dans la page (le wiki reste
autonome, zéro dépendance au serveur). Effets : plus AUCUN échappement Python→JS
(la classe de bugs disparaît à la racine), le JS devient éditable/lintable/testable
directement (`node --check scripts/wiki_app.js` en garde), et `scan_projets.py` perd
~290 lignes. Étape suivante optionnelle (M) : découper le reste du monolithe en
modules (`collecte.py`, `rendu_md.py`, `rendu_html.py`, `pdf.py`) importés par un
`scan_projets.py` orchestrateur mince — mécanique, mais gros diff.

**Vérification** : suite hub (63 tests, dont `test_wiki_js.py` qui vérifie déjà le
script LIVRÉ — il validera le nouveau chemin sans modification) + capture du rendu.

## 3. VSCode2 — migrations SQLite outillées a minima

**Fait observé** : migrations additives en f-string DDL dans `app/db.py:53-85` — pas
d'outil, pas d'historique, pas de rollback ; chaque évolution de schéma est artisanale.

**Solution (S)** : le pattern **`PRAGMA user_version`** — une liste ordonnée
`MIGRATIONS = [(1, "ALTER TABLE ..."), (2, "...")]` et une boucle qui applique ce qui
manque puis bump `user_version`, le tout dans une transaction par migration. Zéro
dépendance externe (pas d'Alembic pour du SQLite embarqué), historique lisible dans le
code, idempotent au démarrage. Les f-strings actuelles deviennent les migrations 1..N.

**Vérification** : test dédié (base vierge → toutes migrations ; base déjà à jour →
no-op) + suite 330.

## 4. VSCode2 — découper `pptx_export.py` (1 636 l)

**Fait observé** : un seul module porte hints de calibrage, constructeurs de slides et
orchestration ; `budget_ok` vient d'être factorisé mais la taille demeure.

**Solution (M)** : découpage par responsabilité EXISTANTE (pas de redesign) :
`pptx_fit.py` (calibrage : `_per_line_height_in`, `_budget_lignes`, hints),
`pptx_slides.py` (constructeurs par type de slide), `pptx_export.py` (orchestration,
API publique inchangée pour ne pas toucher les appelants). Déplacement de code pur,
imports ajustés.

**Vérification** : suite 330 (dont les tests deck qui rendent réellement) — aucun
changement de comportement attendu.

## 5. VSCode1 — duplication de routes et singleton db

**Faits observés** : routes `/equipes` et `/departements` quasi identiques + motif
`manager==='sans'` répété ~6 fois ; tous les modules importent le singleton `db`.

**Solutions** :
- **(S) Factoriser le motif** : `filtrerRepondants(repondants, {manager})` +
  une fabrique de handler paramétrée par la dimension (`equipe`/`departement`) —
  les deux routes deviennent 2 instanciations d'une même fonction.
- **(M, optionnel) Injection légère du db** : les fonctions cœur prennent
  `db = require('./db')` en **paramètre par défaut** (`function agregerResultats(sessionId, filtre, manager, dbi = db)`)
  — zéro changement d'appel existant, testabilité gagnée (un test peut passer une base
  in-memory). Pas de framework DI.

**Vérification** : `npm test` complet (inclut désormais le PPT réel).

## 6. VSCode3 — le générateur monolithique (2 767 l)

**Fait observé** : `generate_deck.py` porte contenu ET rendu de 40 slides sur
8 chapitres ; le CLAUDE.md a déjà été élagué de sa narration, mais le fichier reste
le plus gros code de la flotte. La robustesse note aussi : template chargé sans garde
dès l'import.

**Solutions** :
- **(S) Garde du template à l'import** : charger `template-octo.pptx` dans une
  fonction avec message d'erreur actionnable (fichier manquant/corrompu) au lieu du
  chargement à l'import de module — corrige aussi le finding robustesse.
- **(M, phasé par chapitre) Séparer contenu et rendu** : un module `contenu/` (les
  textes/données par chapitre, dicts purs) et `generate_deck.py` qui ne garde que les
  constructeurs de slides. Migration chapitre par chapitre (08 KPI d'abord, le plus
  autonome), `test_generate_deck.py` + rendu LibreOffice à chaque pas.

**Vérification** : `python test_generate_deck.py` (build + rendu réel) après chaque
chapitre migré.

## 7. VSCode — CI + duplication PowerShell

**Faits observés** : pas de `.github/workflows/` alors que de vrais tests
`node --test` existent (test-routes/security/static, 5 fichiers, coverage c8
configuré) ; 6+ scripts PS1 avec des fonctions dupliquées entre eux (constat d'audit).

**Solutions** :
- **(S) CI minimale** : le `ci.yml` de VSCode1 adapté — `npm install` (aucune dep
  runtime), `npm test`, `npm run coverage` en informatif. Le proto reste un proto,
  mais ses tests tournent à chaque push.
- **(S/M) Module PS commun** : extraire les fonctions partagées des scripts PS1 vers
  `src/comop-common.ps1` dot-sourcé (`. "$PSScriptRoot/comop-common.ps1"`) par les
  6 scripts — une définition par fonction.

**Vérification** : CI verte sur GitHub ; `npm test` + `smoke-test.ps1` locaux verts
après l'extraction PS.

---

## Séquencement proposé (à arbitrer)

| # | Solution | Projet | Effort | Risque d'exécution | Gain risque-tech |
| --- | --- | --- | --- | --- | --- |
| 1 | JS du wiki → `wiki_app.js` (fichier réel inliné) | VScode5 | S/M | Faible (garde node --check déjà en place) | Élevé — classe de bugs éliminée à la racine |
| 2 | Migrations `PRAGMA user_version` | VSCode2 | S | Faible (test dédié + 330) | Élevé — schéma outillé |
| 3 | Matrice de divergence `pptx_deck` au scan | VScode5 (mesure) | S | Nul (lecture seule) | Moyen — rend la dette n°1 visible |
| 4 | CI VSCode + module PS commun | VSCode | S | Faible | Moyen |
| 5 | Factorisation routes + filtre manager | VSCode1 | S | Faible (npm test complet) | Moyen |
| 6 | Garde template à l'import | VSCode3 | S | Nul | Faible (mais corrige robustesse) |
| 7 | Découpage `pptx_export.py` | VSCode2 | M | Moyen (déplacement pur, 330 en filet) | Moyen |
| 8 | Injection légère db (param par défaut) | VSCode1 | M | Faible | Moyen |
| 9 | Contenu/rendu séparés, chapitre par chapitre | VSCode3 | M/L | Moyen (rendu réel en filet) | Élevé à terme |
| 10 | Cœur commun `pptx_deck_core` en canon+sync | flotte | L | Élevé (forks réels — préserver VSCode4) | Élevé à terme — nécessite #3 d'abord |

Lecture recommandée : **#1-#6 = un lot « S » sûr et à fort rendement** (chaque item
vérifié par la suite réelle de son projet) ; #7-#8 ensuite ; #9-#10 = chantiers phasés
qui méritent chacun leur propre arbitrage au moment de les ouvrir.
