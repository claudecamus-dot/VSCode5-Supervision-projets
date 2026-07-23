---
name: agent-orchestrator
description: Orchestrateur des agents et skills du projet — qualifie une demande de travail, compose un plan (cascade / parallèle / asynchrone, modèle par étape), l'exécute en s'appuyant sur le catalogue et les données du superviseur, puis journalise le run. Sait aussi APPLIQUER une recommandation arbitrée du superviseur (findings de diagnostic.json des deux volets — usage des agents ET pratiques test/dev/revue/design) via le playbook evolution-flotte, puis enregistrer l'arbitrage. À charger quand une demande implique plusieurs étapes/agents, des vérifications obligatoires, ou « applique/traite la reco du superviseur » — ou quand la grille du hook UserPromptSubmit route ici.
---

# Agent orchestrateur (étages O-A + O-B + O-C)

Données de routage :
`.claude/orchestration/catalogue.md` (recommandations),
`.claude/orchestration/routing-hints.json` (hints générés par le superviseur à chaque
session : `eprouves`/`jamais_utilises`/`en_sommeil`, `verifications_oubliees` à insérer
d'office, stats plan-vs-réel par playbook/agent, `prudence` issu du diagnostic étage 2),
`docs/wiki/technical/agents-supervision.md` (tableau de bord humain des mêmes données) et
`.claude/orchestration/playbooks/` (workflows récurrents — format dans `playbooks/FORMAT.md`).

## Méthode — 5 étapes

### 1. Qualifier (silencieux, jamais mentionné à l'utilisateur si exécution directe)

- **Exécution directe** (pas d'orchestration, pas de journal) : une seule étape, un seul
  agent/skill évident, micro-tâche, question, correction en cours de tâche.
- **Orchestrer** : ≥ 2 étapes dépendantes, ≥ 2 agents/skills, vérifications obligatoires
  en jeu (voir table), ou action difficilement réversible au milieu d'un enchaînement.

### 2. Composer le plan

**D'abord, chercher un playbook.** Si la demande matche les `declencheurs` d'un playbook
de `.claude/orchestration/playbooks/`, l'instancier plutôt que composer à vide : adapter
ses étapes à la demande **sans en retirer les vérifications obligatoires ni les
checkpoints**, ne garder que les étapes conditionnelles applicables. Playbooks actuels :

| Playbook | Pour | Statut |
| --- | --- | --- |
| `evolution-flotte` | Modifier un AUTRE projet de la flotte (corrige/rattache/déploie/propage sur VSCodeN) — cadrage sur l'état réel, commit scopé au périmètre | Éprouvé |
| `dev-verifie` | Implémentation/correction avec tests + vérif réelle + revue finale avant commit | Importé, à confirmer |
| `export-ppt-verifie` | Livrable = un deck PPT : génération + enrichissements conditionnels (cadres photo, polish, design) + `pptx-verify` obligatoire | Importé, à confirmer |
| `revue-design-parallele` | Revue multi-angles d'un livrable en fan-out puis consolidation | Importé, à confirmer |

Sinon composition libre depuis le catalogue + `routing-hints.json` : préférer les
`eprouves`, prudence explicite sur les `jamais_utilises` et les cibles listées dans
`prudence`, insérer d'office les `verifications_oubliees`. Pour chaque étape :
**agent/skill**, **mode**, **modèle** (sous-agents uniquement), **contrat de sortie**.
Suivre le plan avec TodoWrite. Règle de mode — *la dépendance de données décide* :

| Mode | Quand | Garde-fous |
| --- | --- | --- |
| Synchrone (cascade) | L'étape suivante a besoin du résultat | Contrat de sortie vérifié avant de continuer |
| Parallèle (fan-out) | Étapes indépendantes en lecture/analyse | ≤ 4 sous-agents, jamais d'écritures concurrentes sur les mêmes fichiers, consolidation obligatoire |
| Asynchrone (arrière-plan) | Long, autonome, non bloquant | Attendre la notification — ne JAMAIS anticiper/fabriquer le résultat ; 1 seul chantier async lourd à la fois |
| Irréversible (commit, suppression, publication) | — | Toujours synchrone + confirmation utilisateur, hooks/permissions jamais contournés |

**Aucun agent/skill ne couvre le besoin ?** Ne pas improviser sans le signaler — escalade
en trois temps, dans cet ordre :

1. **Mémoire git** : `py .claude/orchestration/git_agents_inventory.py` inventorie tous
   les agents/skills que git connaît — **présents et supprimés** (un agent adapté a pu
   être retiré lors d'un nettoyage). `--json` pour la version structurée.
2. **Restauration** : si un agent supprimé matche, montrer son contenu
   (`git show <commit>^:<chemin>`, la commande exacte est dans la colonne « Restaurer »)
   et **proposer** sa restauration — décision utilisateur, jamais de restauration
   silencieuse.
3. **Évolution ou création** : sinon, proposer soit l'évolution de l'agent/skill existant
   le plus proche (étendre ses déclencheurs/son périmètre), soit la création d'un nouveau
   via `skill-creator` — avec un mini-brief (nom, déclencheurs, périmètre, ce qui manque
   aux existants). C'est une décision de périmètre : toujours la faire arbitrer par
   l'utilisateur avant d'écrire quoi que ce soit.

Dans les trois cas, noter la résolution dans le `notes` du run journalisé
(`"resolution: restauration <nom>"` / `"resolution: evolution <nom>"` /
`"resolution: creation <nom>"`) — le superviseur s'en servira pour détecter les trous
récurrents du catalogue.

### 2 bis. Agir sur une recommandation du superviseur

Le superviseur *propose* (findings de `diagnostic.json`, avec un champ `proposition`),
l'utilisateur *arbitre*, **l'orchestrateur applique la version validée** — c'est la
boucle propose→arbitre→applique. Quand la demande est « applique la reco X », « traite le
finding Y », « corrige le point de pratique Z » (ou plus large : « traite tout ») :

1. **Lire les propositions** dans `.claude/supervision/diagnostic.json` (les mêmes que la
   section « Pratiques, couverture & risques » et les findings du wiki). Chaque finding
   porte `categorie`, `cible`, `titre`, `preuve`, `recommandation`, `proposition`. Les
   deux volets sont traitables :
   - **Usage des agents** (`ko-repete`, `inefficacite`, `agent-mort`, `interaction`,
     `verification-manquante`, `non-convergence`) → la proposition amende un skill, un
     playbook, un contrat d'étape, ou met un agent en sommeil.
   - **Pratiques d'ingénierie** (`pratique-test`, `pratique-dev`, `pratique-revue`,
     `pratique-design`) → la proposition installe un outil (coverage, linter), câble un
     hook (revue pré-commit), greffe une skill (`deck-design-review`), ou impose un audit
     `audit-technique` sur un projet cible.
   - **Documentation** (`pratique-doc`) → remédiation via `bmad-document-project`
     (brownfield), `bmad-agent-tech-writer` (Paige), `bmad-index-docs`, ou rédaction
     directe d'un README/CLAUDE.md manquant.
   - **Cadrage produit** (`pratique-produit`) → remédiation via `bmad-product-brief`,
     `bmad-prd`, `bmad-forge-idea`, `bmad-agent-analyst`/`bmad-agent-pm` — **skills BMAD,
     sur demande explicite** (jamais déroulées d'office ; l'utilisateur choisit le
     livrable de cadrage).
2. **N'appliquer QUE l'arbitré.** Si l'utilisateur n'a pas explicitement validé, présenter
   la proposition et demander l'arbitrage — jamais d'auto-application, même « évidente »
   (gouvernance stricte, identique côté superviseur). « Traite tout » vaut arbitrage de
   l'ensemble des findings ouverts.
3. **Choisir le véhicule d'exécution** selon la cible de la proposition :
   - proposition qui touche **un autre projet de la flotte** (installer un linter sur
     VSCode2, greffer une skill sur VSCode4…) → instancier le playbook **`evolution-flotte`**
     (cadrage sur l'état réel → modif scopée → vérifs → commit limité au périmètre → wiki
     → journal).
   - proposition qui touche **ce projet-ci** (un skill/playbook/script local) → édition
     directe suivie de la vérification adaptée (py_compile, JSON valide, test).
4. **Enregistrer l'arbitrage** une fois appliqué : `.claude/supervision/arbitrages.json`
   (champ `cible` = celle du finding, `decision` = « ACCEPTÉ + APPLIQUÉ : <ce qui a été
   fait> »). Le scan clôt alors le finding (le wiki cesse de l'afficher en alerte). Un
   finding **refusé** par l'utilisateur s'y note aussi (« REFUSÉ : <raison> ») pour ne pas
   le re-proposer.

Journaliser le run avec `resolution:` dans les notes et la ou les cibles traitées.

### 3. Valider

Présenter le plan à l'utilisateur **seulement si** : > 3 sous-agents, coût manifestement
élevé, ou étape irréversible/hors périmètre de la demande. Sinon exécuter directement —
la demande vaut mandat, la validation systématique tuerait l'usage.

### 4. Exécuter

Après chaque étape, vérifier son **contrat de sortie** (artefact attendu présent, test
vert, vérification réelle faite). Échec → **une** relance ciblée, puis escalade à
l'utilisateur avec l'état réel. Vérifications obligatoires à insérer d'office dans les
plans (leçons payées du projet — mémoires `feedback_*`) :

| Si le plan touche… | Alors le plan contient… |
| --- | --- |
| Template/CSS/JS/écran | Rendu réel regardé (screenshot ou app lancée), pas seulement pytest |
| Génération d'un export PPT | `pptx-verify` (rendu réel — python-pptx est un parseur tolérant) |
| **Livrable consommé par l'utilisateur** (deck exporté, écran) | Produire l'**artefact EXACT qu'il ouvre** (l'export réel, pas une fonction de démo maison), le rendre **ENTIER** (toutes les slides/pages, pas un extrait), et le faire **VALIDER par l'utilisateur** avant tout « fait » |
| Fin d'incrément / avant commit | Revue finale en étape terminale (relecture diff + exigences recochées) |
| Exploration volumineuse | Sous-agent `Explore`, jamais la session principale |
| Skills BMAD | Uniquement sur demande explicite, via `bmad-help` |

**Règle de non-convergence.** Si le MÊME livrable est rejeté par l'utilisateur **≥ 3
tours** (« toujours KO », « pas traité »), la boucle ne converge pas : **STOP l'itération
à l'aveugle** — ne pas re-deviner le défaut. Reproduire l'artefact utilisateur exact
(§ ligne ci-dessus) ET **demander à l'utilisateur de pointer le défaut précis** (numéro de
slide/page, capture, écran) avant de retoucher quoi que ce soit. Re-deviner produit
l'oscillation ; l'oracle, c'est l'utilisateur sur SON artefact.

### 5. Journaliser

À la fin du run (succès **ou** échec), une ligne dans `.claude/orchestration/runs.jsonl` :

```bash
py .claude/orchestration/log_run.py '{"demande": "résumé court", "qualification": "orchestre", "playbook": "dev-verifie", "plan": [{"etape": "revue design", "agent": "Explore", "mode": "parallele", "modele": "haiku"}], "resultat": "succes", "reprises": 0, "notes": ""}'
```

(JSON aussi accepté sur stdin. `qualification` : `orchestre` | `direct-signale` ;
`resultat` (issue **discriminante** — pas un `succes` réflexe, un journal où tout est
`succes` ne porte aucun signal) : `succes` = livrable produit ET toutes les exigences
explicites de la demande couvertes ET vérifications obligatoires faites **ET, pour un
livrable consommé par l'utilisateur, validé PAR l'utilisateur sur l'artefact exact** ;
`en-attente-validation` = livrable produit et auto-vérifié mais **pas encore validé par
l'utilisateur** — état par défaut d'un livrable utilisateur tant que le « OK » n'est pas
donné (ne JAMAIS logger `succes` sur une auto-évaluation d'un livrable que l'utilisateur
doit approuver) ; `partiel` = au moins une exigence non livrée, une vérification
obligatoire sautée, OU une escalade non résolue à la remise (commit/PR bloqué renvoyé à
l'utilisateur) ; `echec` = objectif non atteint / run abandonné ; `playbook` : nom du
playbook instancié ou `null` en composition libre. Les exécutions directes ne se
journalisent pas — le journal trace les orchestrations, pas la conversation.)

## Politique de modèle (sous-agents uniquement)

La session principale — donc les skills inline — reste sur le modèle choisi par
l'utilisateur : l'orchestrateur peut **proposer** une bascule (`/model`), jamais l'imposer.

| Modèle | Pour | Exemple |
| --- | --- | --- |
| Haiku | Fan-out mécanique : recherches simples, extraction, inventaires | 4 × Explore sur des questions factuelles |
| Sonnet | Défaut dev : exploration de code, implémentation standard, revue ciblée | general-purpose sur une feature bornée |
| Opus / Fable | Structurant : architecture, plan complexe, revue adversariale, arbitrage | Plan, revue de conception |

Arbitrage par défaut (décision n°6) : qualité d'abord sur le structurant, économe sur le
fan-out — le superviseur croisera modèle × tâche × reprises pour ajuster poste par poste.
