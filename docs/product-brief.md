# Product Brief — VScode5, hub de supervision de flotte

Cadrage produit léger (finding `pratique-produit` du superviseur : aucun artefact de
cadrage). Rédigé le 2026-07-23. Format inspiré de `bmad-product-brief` — persona, why,
besoins, proposition de valeur — sans dérouler le workflow BMAD interactif.

## Persona

**L'orchestrateur d'une flotte de projets Claude Code** — ici, un consultant qui fait
tourner en parallèle 5+ projets (audits, decks de restitution, apps de questionnaire)
partageant le même outillage agentic (BMAD, orchestrateur, superviseur, skills PPT). Il
n'a ni le temps ni l'envie de re-fouiller chaque dépôt à la main pour savoir ce qui y est
installé, ce qui diverge, et ce qui manque.

Secondairement : **le futur lui-même** (ou un pair) qui reprend un projet dormant et doit
comprendre en un coup d'œil son état agentic et ses pratiques.

## Why — le problème à résoudre

Sans hub, la connaissance de l'état de la flotte est **implicite et volatile** :
- un fix de skill doit être propagé à la main sur N copies divergentes (vécu : 6 copies
  de `scan_transcripts.py`) ;
- une bonne pratique installée sur un projet (linter, coverage, hook de revue) n'essaime
  pas aux autres ;
- les décisions du superviseur (« trier BMAD », « README manquant ») restent des constats
  jamais exécutés ;
- les runs `en-attente-validation` ne se referment jamais ;
- on ne sait pas quels agents/skills sont réellement utilisés vs installés-et-morts.

Chaque écart se paie en reprise. Le hub existe pour **rendre cet état visible, comparable
et actionnable** — mesurer une fois, décider, appliquer, tracer.

## Besoins (jobs-to-be-done)

1. **Voir** l'état agentic + les pratiques des N projets sur une page, sans lancer N
   sessions. → tableau de bord `docs/wiki.html`.
2. **Être alerté** de ce qui demande une décision (findings critiques, runs à solder,
   cadences périmées). → bandeau exécutif du wiki.
3. **Comparer** les projets pour repérer un écart (un projet sans test/linter/doc que les
   autres ont). → 9 dimensions de pratiques, étage déterministe.
4. **Approfondir** un risque qui exige de lire le code (robustesse, sécurité…). → audit
   qualitatif `audit-technique` à la demande.
5. **Corriger** un manque une fois arbitré, et que ça essaime proprement. → playbook
   `evolution-flotte` + arbitrages tracés.
6. **Ne pas rater** ce qui existe déjà ailleurs (public). → `veille-agentic`.

## Proposition de valeur

> **Piloter une flotte de projets agentic comme un seul système** : une page qui dit ce
> qui est installé, ce qui manque et ce qui a bougé ; un superviseur qui qualifie les
> écarts en recommandations arbitrables ; un orchestrateur qui les applique et les trace.
> On mesure d'abord, on décide, on applique une fois, ça essaime — au lieu de re-découvrir
> et re-corriger le même écart projet par projet.

Ce qui la distingue d'un simple script d'inventaire : la **boucle fermée**
propose → arbitre → applique (gouvernance humaine au centre), et la **double nature** des
signaux (déterministe 0-token à chaque scan + qualitatif à la demande) — ni tout-manuel,
ni tout-automatique.

## Non-objectifs

- Ce n'est **pas** un produit à marché : pas d'utilisateurs externes, pas de monétisation.
- Ce n'est **pas** un remplaçant des superviseurs locaux : chaque projet garde le sien
  (volet usage) ; le hub ajoute la vue flotte et les pratiques.
- Ce n'est **pas** un CI/CD : il propose et applique sur arbitrage, il ne déploie pas en
  continu sans humain.

## Mesure de succès

- Un écart détecté sur un projet devient une action arbitrée puis appliquée (et non un
  constat mort) — traçable dans `arbitrages.json`.
- Une bonne pratique installée une fois essaime aux projets concernés via
  `evolution-flotte`.
- Le temps pour répondre à « où en est la flotte ? » = ouvrir une page, pas une demi-heure
  de fouille.
