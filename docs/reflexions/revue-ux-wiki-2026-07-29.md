# Revue UX/UI du site de supervision — 2026-07-29

Revue en fan-out (playbook `revue-design-parallele`, 3 angles indépendants en lecture
seule, sous-agents à contexte froid) sur le **rendu réel** : les 9 onglets ont été
capturés en images avant la revue, aucun relecteur n'a jugé sur le code source seul.

> **Statut : backlog restitué, aucun correctif appliqué.** Le playbook impose ce
> checkpoint — la revue est le livrable, les correctifs sont un mandat séparé.
> ⚠️ Leçon du finding `docs/reflexions` (2026-07-28) : une proposition écrite ici n'est
> **pas arbitrable** (ni bouton Valider, ni suivi). Les items retenus doivent être
> reversés en findings de `diagnostic.json` au prochain passage du superviseur.

## P1 — Le tableau de bord se contredit à l'endroit le plus lu

**Constat vérifié directement sur `docs/wiki.html`** (pas seulement rapporté) : le
bandeau du Pilotage affiche *« 6 projets · 1 en alerte · 0 runs à solder · 0 retards de
cadence — Rien en attente d'arbitrage, système sain »*, tandis que l'onglet Actions
correctives liste au même scan : VSCode 5, VSCode1 1, VSCode2 1 (🔴), VSCode3 4,
VSCode4 7 (🔴) — **18 pratiques en écart**.

La phrase de synthèse n'agrège que les runs à solder et les retards de cadence ; elle
ignore les écarts de pratiques. Le point d'entrée du dispositif dit « tout va bien »
pendant qu'un autre onglet montre des écarts critiques.

*Correctif* : calculer « rien en attente d'arbitrage » sur le total réel incluant les
pratiques en écart, ou restreindre explicitement le libellé à son périmètre.

**Aggravant (angle hiérarchie)** : la tuile « 1 EN ALERTE » a exactement le même style
que les tuiles à 0 — rien ne guide l'œil. Ajouter une variante colorée dès que la valeur
dépasse 0.

## P2 — Actions coûteuses ou irréversibles insuffisamment protégées

1. **Aucune confirmation avant « Valider »**, qui lance un agent écrivant sur un autre
   dépôt : seule protection, le grisage optimiste des boutons. Ajouter un `confirm()`
   nommant le dépôt cible.
2. **Déduplication serveur incomplète** : le garde-fou anti-double-lancement ne couvre
   que 4 actions ; `audit`, `diagnostic`, `veille`, `reflexion` — les actions **facturées**
   — n'en ont aucune. Un rechargement de page peut relancer un `claude -p` identique en
   parallèle. Étendre la clé de déduplication à `action + projet`.
3. **Aucune annulation** d'un job long (diagnostic/audit = plusieurs minutes facturées) :
   ni route serveur, ni bouton. Ajouter `/api/cancel/<job>` + bouton Annuler.
4. **Déploiement `--force`** : case à cocher qui écrase des fichiers réels, sans second
   avis, sur des champs dépourvus de `<label>`.

## P3 — Accessibilité : les onglets ne sont pas des onglets

Les 9 onglets sont de vrais `<button>` (le focus clavier natif est préservé — acquis),
mais **aucune sémantique ARIA** : ni `role="tablist"/"tab"/"tabpanel"`, ni
`aria-selected`, ni `aria-controls`. Un lecteur d'écran énonce neuf boutons sans dire
lequel est actif. Correctif mécanique, sans refonte.

## P4 — Deux langages visuels pour la même notion d'état

Les trois angles convergent : l'état est écrit **en toutes lettres** dans le tableau
qualitatif (« 🟢 ok », « 🟠 moyen ») et dans les badges de l'onglet Projets (« ✓ OK »,
« majeur »), mais porté **par la seule couleur** dans le tableau déterministe à 9
colonnes et dans les résumés par projet des correctifs. Unifier sur icône + mot +
couleur, le pattern déjà présent ailleurs.

## P5 — Nommage et parcours de décision

- **« Actions » vs « Actions correctives »** : noms quasi identiques, contenus disjoints
  (outils de mesure d'un côté, décisions à arbitrer de l'autre). Renommer le premier en
  « Outils & diagnostics ».
- **Trois vocabulaires pour le même problème** : « 1 EN ALERTE » (Pilotage), pastille
  « majeur » (Projets), « 1 pratique en écart » (Correctifs) — sans lien cliquable entre
  eux. Unifier le terme et rendre la tuile du bandeau cliquable.
- **La Veille est un troisième gisement de décisions** (statuts `nouveau`/`adopte`),
  placée loin des Actions correctives. Regrouper les onglets porteurs de décision.
- **Le Tutoriel est en dernière position** alors qu'il définit le jargon (*finding*,
  *arbitrage*, *canon*, *run à solder*) que le lecteur croise pendant huit onglets.

## P6 — Finitions de lisibilité

- Descriptions d'audit **coupées en plein mot** sans ellipse : « …un process PowerShell
  par r ». Le lecteur croit lire la phrase entière.
- Le corps du **Tutoriel** hérite d'une classe de légende de bouton (~11,5 px gris pâle)
  alors que c'est du texte à lire en continu.
- Colonne « Audité le » trop étroite : les dates cassent sur deux lignes.
- Cibles de clic ~20-24 px sur les boutons d'action, sous le seuil recommandé.
- Métadonnée collée : « agents-supervision.md**généré** : … » se lit comme une extension
  de fichier.

## Acquis à préserver

- Le statut de job n'est **jamais** porté par la seule couleur (emoji + mot).
- Aucune règle CSS ne supprime l'`outline` de focus — le clavier reste utilisable.
- Le couple garde-fou serveur 409 + réactivation des boutons en cas d'échec réseau est
  un bon traitement du double-clic sur Valider/Invalider (état dérivé du serveur, il
  survit au rechargement).
- Le code couleur unique entre étage déterministe et étage qualitatif permet un scan
  visuel projet par projet.
