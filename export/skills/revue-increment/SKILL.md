---
name: revue-increment
description: Boucle de revue ET d'amélioration de fin d'incrément pour le hub de supervision — vérifie la vérité du JOURNAL (runs soldés via --solde, jamais de succès auto-déclaré sur un livrable à valider), la traçabilité des arbitrages, la fraîcheur du wiki régénéré, la suite pytest verte, et les commits scopés au périmètre quand la séance a touché d'autres dépôts de la flotte (R2). Puis APPLIQUE les correctifs et re-vérifie — une revue qui ne produit que des constats ne vaut rien. À lancer avant de considérer un incrément « livré », après une campagne de remédiations flotte, ou sur demande de rétrospective. Le hook SessionStart la rappelle.
---

# Revue-et-amélioration d'incrément — hub de supervision

Ce projet ne livre pas une application : il **agit sur d'autres dépôts** et
produit du jugement (diagnostics, arbitrages, wiki). Sa definition of done est
donc différente de celle des projets de la flotte — elle porte sur la **vérité
des traces** (journal, arbitrages, wiki) autant que sur le code des scripts.
Deux phases : **A. Revue** (constats vérifiés, pas des impressions) puis
**B. Améliorations** (chaque constat rouge devient un correctif appliqué et
re-vérifié).

## Phase A — les 6 passes

### 1. Vérité terrain (avant tout)

- [ ] `git status` + `git log --oneline -10` lus **maintenant** — l'état réel.
      Sessions concurrentes fréquentes sur la flotte : re-vérifier juste avant
      de stager (cf. mémoire [[flotte-sessions-concurrentes]]).
- [ ] Le diff de la séance correspond à ce qui était visé — rien d'orphelin,
      aucun fichier scratch dans le repo.
- [ ] **Conformité à la demande, exigence par exigence** : relister les points
      explicites de la demande initiale et cocher chacun contre le diff réel.
      Toute exigence écartée est dite dans « Reste », jamais tue.

### 2. Vérité du journal et des arbitrages (le cœur du canal hub — R4/R5)

- [ ] Aucun run `en-attente-validation` qui devrait être soldé, aucun run
      oublié : `runs.jsonl` relu sur la séance. Solde **uniquement** via
      `py .claude/orchestration/log_run.py --solde <prefixe-ts> <resultat> "note"` —
      jamais d'édition manuelle (R5).
- [ ] Jamais `succes` sur un livrable que l'utilisateur doit encore valider.
- [ ] Chaque remédiation appliquée cette séance a son entrée dans
      `arbitrages.json` (cible EXACTE du finding — une cible sœur ne ferme pas
      le finding, leçon bmad-catalogue-codex 2026-07-27) ; les refus via
      `refuser_arbitrage.py`.
- [ ] Chaque finding traité l'a été **après** cadrage sur l'état réel de la
      cible (R1) — pas sur la foi du wiki.

### 3. Vérification réelle des scripts et du wiki

- [ ] Scripts Python touchés → `py -m py_compile` + suite
      `py -m pytest tests/ -q` verte, verdict lu sur la ligne de synthèse
      réelle (`N passed`), pas un résumé filtré.
- [ ] Canon du dispositif touché (`.claude/dispositif/canon/`) →
      `py .claude/dispositif/sync_dispositif.py --check` propre, et la
      propagation aux 6 projets faite par le sync, jamais par édits manuels
      (leçon P1 : les copies divergent).
- [ ] Wiki touché → régénéré via `py scripts/scan_projets.py` AU HUB (une cible n'a
      pas ce script : elle régénère par `py .claude/supervision/scan_transcripts.py`,
      et n'a pas de wiki de flotte à reconstruire) — jamais édité à
      la main, il serait écrasé) **et rendu réel regardé** (`docs/wiki.html`
      ouvert ou screenshot) ; le bloc agents entre marqueurs TODO-AGENTS-HTML
      est présent et `scan_transcripts.py` s'exécute sans avertissement.
- [ ] Séance ayant modifié un autre dépôt de la flotte → les vérifications du
      playbook `evolution-flotte` ont réellement tourné sur la cible (tests du
      projet cible, revue fraîche) et le commit est **scopé** (R2 :
      `git diff --cached --name-only` relu, churn étranger exclu).

### 4. Cohérence de la matière produite

- [ ] Le code ressemble au code autour (style, nommage FR du domaine
      supervision : findings, arbitrages, pastilles).
- [ ] Pas de duplication d'un helper existant ; pas de sur-ingénierie.
- [ ] Aucun chemin machine-spécifique ni secret dans un fichier versionné.
- [ ] Données générées (`wiki.html`, `projets-supervision.md`, `state.json`,
      `routing-hints.json`) jamais éditées à la main — modifiées uniquement via
      leurs générateurs.

### 5. Capitalisation (mémoire)

- [ ] Friction, correction de cap ou approche confirmée → mémoire `feedback-*`
      (Pourquoi + Comment l'appliquer) ; fait projet non dérivable du repo →
      mémoire `project` ; ligne d'index dans `MEMORY.md`.
- [ ] Rien sauvegardé qui soit déjà dans le repo ou le journal.

### 6. Supervision des agents (étage 2)

- [ ] Si le hook signale « diagnostic agent-supervisor a lancer ou perime »
      (cadence 14 j), ou si l'incrément a beaucoup sollicité skills/sous-agents :
      lancer `agent-supervisor` (données étage 1 uniquement — jamais les
      transcripts bruts), puis relancer le scan pour propager.
- [ ] **Méta** : bon niveau d'effort ? irréversible confirmé ? demande vérifiée
      avant d'agir ? Nommer **une chose à changer** la prochaine fois — durable
      → mémoire `feedback`.

## Phase B — Actions d'amélioration (agir, pas seulement constater)

1. **Trier** : correctifs sûrs et cadrés → appliquer maintenant ; qualité /
   simplification → `/code-review` ou `/simplify`, relire leurs changements ;
   sensible ou irréversible (suppression versionnée, push, action sur un autre
   dépôt non arbitrée) → **proposer**, ne pas exécuter (R4 : propose → arbitre
   → applique).
2. **Appliquer** le premier panier + les sorties validées du deuxième.
3. **Re-vérifier pour de vrai** : pytest, scan relancé, rendu wiki regardé.
   Un correctif non re-vérifié n'est pas un correctif.
4. **Capitaliser** (Phase A §5) et **boucler** : sortir quand il ne reste que
   des items proposés à l'utilisateur ou des gaps explicitement documentés.

## Verdict

```text
Revue incrément — <titre>
Produit      : <livré & vérifié réellement | livré mais X non vérifié | partiel>
Journal      : <runs soldés / en attente ; arbitrages tracés | écarts : ...>
Améliorations: <appliqué + re-vérifié cette passe>
Reste        : <proposé à l'utilisateur / gaps connus, listés>
```

Un item rouge de la Phase A non corrigé en Phase B est listé dans « Reste » —
on ne déclare pas « fait » un incrément avec une vérif réelle sautée.
