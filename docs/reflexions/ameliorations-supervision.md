# Réflexion — améliorer la supervision multi-projets

Rédigée le 2026-07-23, après le premier cycle complet (étude → wiki v3 → 2 corrections
C4 → 1 déploiement C4). Organisée selon les cinq verbes du dispositif : **analyser,
rechercher, proposer, surveiller, rendre lisible**. Chaque piste part d'un fait observé
sur ce cycle — pas d'une envie d'outillage.

---

## 1. Analyser — ce que le scanner ne voit pas encore

### 1.1 Écarts de version entre copies d'un même skill (le C3 promis)

**Fait observé** : `agent-orchestrator` existe en 4+ copies (VSCode1, VSCode2, VSCode3,
VSCode4, VScode5, VSCode) qui ont TOUTES divergé — VSCode2 a la table de vérifications
la plus riche (leçons payées), VScode5 une version générique allégée, VSCode1 des règles
propres (gate décision produit). Idem `deck-design-library` (4 copies), les playbooks,
les scripts `scan_transcripts.py`. Aujourd'hui le wiki dit « présent/absent », jamais
« à jour/en retard ».

**Piste** : le scanner calcule un hash par fichier des skills/scripts partagés et
affiche une matrice de divergence (identique / divergé / absent) avec la copie la plus
récente comme référence pressentie. La divergence n'est PAS toujours un défaut (les
adaptations locales sont légitimes) — l'analyse sépare « cœur commun divergé » (à
resynchroniser) de « adaptation locale » (à laisser).

### 1.2 Pratiques dev/test/doc (le volet 2 de l'étude, jamais outillé)

**Fait observé** : l'étude initiale a relevé à la main : 3 projets sans README racine,
1 seule CI (VSCode1), linter quasi absent, tests inégaux (0 → 306). Ces constats vivent
dans une réponse de chat — le scanner ne les recalcule pas, ils vont se périmer.

**Piste** : une passe « pratiques » dans `scan_projets.py` (déterministe, 0 token) :
README présent + section install/usage, CI présente, linter configuré, dossier tests +
compte de fichiers, roadmap. Rendu en badges par projet dans le wiki, avec seuils
d'alerte (ex. « code produit sans aucun test » = majeur).

### 1.3 Dette git silencieuse

**Fait observé** : VSCode portait **174 fichiers modifiés non commités** (upgrade BMAD +
miroir Codex) découverts par hasard au moment de committer. Invisible au wiki.

**Piste** : le scanner lit `git status --porcelain` (+ `git log -1 --format=%ci`) par
projet : compteur de fichiers en attente, date du dernier commit. Seuils : > 50 fichiers
non commités ou dernier commit > 14 j = signal.

### 1.4 Traçabilité des runs multi-projets

**Fait observé** : notre propre journal montre 4 runs sur 5 en `en-attente-validation`
jamais soldés — le statut d'attente est bien posé mais jamais refermé. Même pattern que
le constat VSCode2 (« en-attente-validation jamais utilisé » → ici, jamais *clôturé*).

**Piste** : agréger les `runs.jsonl` de tous les projets dans le wiki (taux
succès/attente/partiel, reprises) ET afficher les runs en attente > 48 h comme « à
solder » — avec un moyen simple de les clôturer (cf. § 5).

## 2. Rechercher — la veille, d'événementielle à systématique

**Fait observé** : la première veille a produit 5 entrées pertinentes (dont BMAD v7 en
préparation — impact direct sur 6 projets). Mais elle est purement manuelle et ses
trouvailles n'ont pas de suite organisée : `nouveau` risque de rester `nouveau` pour
toujours, comme les 44 skills BMAD « à trier » de VSCode1.

**Pistes** :
- **Suivi des trouvailles existantes avant nouvelles recherches** : chaque session de
  veille commence par re-vérifier les entrées `nouveau`/`etudie` (le repo a-t-il bougé ?
  la release est-elle sortie ?) avant d'explorer de nouveaux sujets. Déjà dans la skill,
  à renforcer : une entrée non re-visitée en 2 cycles passe automatiquement en question
  d'arbitrage (« étudier ou écarter ? »).
- **Veille dirigée par les manques** : les findings du § 1 alimentent les requêtes (un
  projet sans CI → chercher « CI patterns for agentic projects » ; BMAD v7 → suivre la
  migration). La veille cherche ce dont les projets ont besoin, pas ce qui est à la mode.
- **Sujet de veille dédié : BMAD v7** — le rewrite annoncé touche les 6 projets et 4-5
  skills déjà DEPRECATED. À suivre à chaque cycle jusqu'à la sortie, avec une note
  d'impact par projet le moment venu.

## 3. Proposer — d'une correction ad hoc à une file d'actions arbitrables

**Fait observé** : les 3 corrections C4 de ce cycle sont parties d'une demande utilisateur
au chat. Or les diagnostics locaux contiennent déjà des actions jamais exécutées (tri
BMAD décidé le 2026-07-21 sur VSCode3, jamais fait ; READMEs manquants). Il n'existe
aucun endroit où ces actions vivent, sont priorisées et attendent un arbitrage.

**Piste — la file d'actions (backlog de supervision)** : un `actions.json` dans ce
projet, alimenté par trois sources : findings des superviseurs locaux, écarts détectés
par le scanner (§ 1), trouvailles de veille adoptables (§ 2). Chaque action porte :
projet cible, quoi (diff d'intention concret), source (finding/écart/veille), statut
(`proposee` → `acceptee` → `faite` / `ecartee`). **Gouvernance identique à
agent-supervisor : le dispositif propose, l'humain arbitre, l'orchestrateur applique.**
Le wiki rend la file visible (§ 5) ; un déploiement C4 = tirer une action acceptée.

**Piste — le manifeste de distribution** : officialiser VScode5 comme « source de
référence » des composants partagés (duo orchestrateur/superviseur, scripts, playbooks
génériques, skills PPT communes) avec un fichier de manifeste (composant → version/hash
→ projets déployés). C'est le pendant outillé du § 1.1 : détecter la divergence, puis
proposer la resynchronisation comme action de la file.

## 4. Surveiller — cadences et péremption

**Faits observés** :
- Les scans locaux ne tournent qu'au SessionStart de CHAQUE projet — un projet non
  ouvert = données figées (le wiki affiche alors du périmé sans le dire).
- Les diagnostics étage 2 ont une cadence de 14 j par projet, mais personne ne voit
  globalement lesquels sont périmés.
- La veille a une cadence (3 j, hook) — c'est le seul sujet à cadence visible.

**Pistes** :
- **Le scanner multi-projets lance les scans étage 1 des autres projets** avant
  d'agréger (`py <projet>/.claude/supervision/scan_transcripts.py` — déterministe,
  0 token, ~1 s/projet). Le wiki agrège alors du frais, pas du dernier-passage.
- **Tableau des cadences dans le wiki** : par projet — dernier scan étage 1, dernier
  diagnostic étage 2 (vert < 14 j, orange au-delà), dernière veille, dernier commit.
  La péremption devient un signal de première classe, au même rang que les alertes.
- **Runs à solder** (cf. § 1.4) : tout `en-attente-validation` > 48 h remonte en tête
  de wiki comme question d'arbitrage explicite.

## 5. Rendre lisible — le wiki comme poste de pilotage

**Fait observé** : le wiki actuel est un bon inventaire (tableau + détails repliables +
veille) mais c'est une photographie sans mémoire ni file d'attente : pas de tendance
(« mieux ou moins bien qu'hier ? »), pas d'actions en attente, pas de hiérarchie entre
« ce qui demande une décision » et « ce qui est sain ».

**Pistes, par ordre d'impact** :
1. **Bandeau exécutif en tête** : 3-5 chiffres (projets OK / en alerte, actions en
   attente d'arbitrage, runs à solder, retards de cadence) + la liste courte « ce qui
   attend une décision humaine ». Un coup d'œil = l'état du système et mes décisions à
   prendre.
2. **Section « File d'actions »** (§ 3) avec statuts colorés — remplace la chasse aux
   findings dans les détails repliés par une liste actionnable unique.
3. **Tendances** : le scanner archive un snapshot JSON daté par exécution
   (`docs/wiki/history/`) et affiche les deltas (skills utilisés +2, alerte VSCode2
   critique→majeur…). La flèche compte plus que le chiffre.
4. **Tableau des cadences** (§ 4) avec code couleur frais/périmé.
5. **Confort de lecture** : ancres par projet, timestamps relatifs (« il y a 2 h »),
   tri du tableau par alerte décroissante, lien vers le repo GitHub de chaque projet à
   côté du livrable.

---

## Proposition de séquencement (à arbitrer)

| # | Incrément | Contenu | Verbe servi | Effort |
| --- | --- | --- | --- | --- |
| 1 | **Wiki poste de pilotage** | Bandeau exécutif + cadences + runs à solder + scans étage 1 relancés par le scanner | Surveiller + Lisible | S |
| 2 | **Pratiques + dette git** | Passe pratiques dev/test/doc + git status/dernier commit dans le scan | Analyser | S |
| 3 | **File d'actions** | `actions.json` + section wiki + alimentation depuis findings existants | Proposer | M |
| 4 | **Divergence des copies (C3)** | Hash/matrice des composants partagés + manifeste de distribution | Analyser + Proposer | M |
| 5 | **Tendances** | Snapshots datés + deltas dans le wiki | Lisible | S |

La veille (§ 2) s'améliore par sa skill (édition de `veille-agentic`), sans incrément
dédié — à faire au fil des cycles.
