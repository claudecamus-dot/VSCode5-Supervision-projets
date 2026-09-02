# Inspection critique du site de supervision — 2026-09-02

**Statut : rapport d'inspection. Aucun retrait n'est arbitré.** Salle `inspection-critique`
(Boundary, Sally, Portevoix, Argus, Quincaillier) en mode subagent, deux tours. Première
convocation de cette salle depuis sa création.

Demandes à l'origine : « continue la refonte du site web » et « lance un chantier de
performance et qualité pour la réalisation ».

Périmètre inspecté : `docs/wiki.html` (page générée), `scripts/serve_wiki.py` (serveur et
console), `tests/test_serve_wiki.py`. Hors périmètre : le scan, les autres dépôts, `export/`.

---

## 1. Ce que la salle a changé à la question posée

La demande supposait deux chantiers séparés — finir la refonte, puis améliorer performance
et qualité. La salle rend un seul dossier, parce que ses quatre axes convergent sur le même
objet : **une console que personne n'utilise, qui grossit, et qui est exposée**.

Le désaccord central n'était pas prévu par la convocation. Il a émergé au second tour et il
est le livrable principal de cette séance :

> Un zéro d'usage sur un dispositif dont la porte d'entrée est fermée mesure-t-il le
> désintérêt, ou l'obstacle ?

**Aucune des deux voix n'a été réfutée, et la mesure a départagé une partie du terrain.**
Argus a trouvé ce que personne n'avait lu : `_journaliser_vue` est appelée **côté serveur**,
sur la route `/` uniquement (`serve_wiki.py:754`). Les 24 ouvertures de page enregistrées
ont donc toutes eu lieu **serveur allumé, console détectée, boutons actifs** — la bannière
« serveur non détecté » ne s'est affichée dans aucune. Sur cette fenêtre-là, la porte de
Portevoix n'était pas fermée : elle a été ouverte 24 fois et personne n'est passé à l'action.

Mais la mesure ne permet pas d'aller plus loin, et c'est Argus qui pose la limite lui-même :
**les ouvertures en `file://` ne sont comptées nulle part** — or c'est exactement le canal que
CLAUDE.md prescrit (« régénérer via `scan_projets.py` et **ouvrir `docs/wiki.html`** »). La
règle du hub envoie l'utilisateur sur le canal où la console est morte par construction.
Dénominateur inconnu, obstacle institutionnalisé.

Le docstring de `_journaliser_vue`, écrit par `atelier-idees` le 2026-08-31, énonçait déjà
les trois lectures possibles du zéro : boutons introuvables, boutons inutiles, page jamais
ouverte. Le compteur de vues a éliminé la troisième. **Il n'a pas séparé les deux
premières** — et c'est précisément là que la salle se divise.

---

## 2. Axe 1 — Bugs latents (🌶️ Boundary)

Six trajectoires rejouées sur un serveur réel, processus Windows tués au bon moment, pas
décrites au conditionnel. Deux d'entre elles ont été re-vérifiées indépendamment par Argus,
et la première par l'orchestrateur.

| # | Constat | Statut | Coût du statu quo |
| --- | --- | --- | --- |
| 1 | **Le CORS n'exclut pas ce qu'il prétend exclure.** `serve_wiki.py:739` autorise tout Origin qui *commence par* `http://localhost` ou `http://127.0.0.1` — donc `http://localhost.evil.com` passe. `origin == "null"` est accepté en prime, et le préflight `do_OPTIONS` renvoie la même autorisation. | **CONSTAT** — reproduit trois fois, dont une par l'orchestrateur : l'origine hostile reçoit son propre `Access-Control-Allow-Origin`, une origine sans rapport est refusée. | N'importe quelle page tierce ouverte dans le même navigateur peut POSTer sur `/api/run/valider`, qui lance un agent en `--dangerously-skip-permissions` sur un dépôt réel. Le bind est bien `127.0.0.1` seul, mais le navigateur de l'utilisateur **est** sur la machine. |
| 2 | **`action_deploy` n'a aucune allowlist**, alors que le docstring du module en promet une (lignes 6 et 19) et que `action_audit` et `action_party` en ont une. Il ne fait que `strip()` et tronquer à 80 caractères. | **CONSTAT** — vérifié par Boundary puis par Argus. | Un `cible` quelconque, n'importe quel chemin du poste, devient une cible d'écriture. Combiné au défaut 1, cela n'exige même pas un clic humain. |
| 3 | **Annuler un job qui vient de finir lui vole sa réussite.** Le drapeau `_annule` est testé AVANT le code retour (ligne 691) : un processus terminé avec succès sort étiqueté « annulé ». | **CONSTAT** — et il s'est produit **en production ce matin** (voir § 6). | Ligne fausse dans `jobs.jsonl` et suppression du rescan de `ACTIONS_QUI_PERIMENT_LES_MESURES`. R5 prise en défaut par le serveur lui-même. |
| 4 | **Un job survit au serveur.** `JOBS` est un dict en mémoire pure, `_journaliser_job` n'écrit qu'au retour de `_run_job`. Driver tué pour de vrai : enfant vivant, `jobs.jsonl` vide. | **CONSTAT** — reproduit par arrêt forcé du processus. | Un agent continue seul sur un dépôt de la flotte, invisible de `/api/jobs`, sans bouton Annuler capable de le retrouver, sans trace au journal. |
| 5 | **Le tri de `/api/jobs` casse à minuit.** `started` est un `%H:%M:%S` sans date, trié en chaîne décroissante. | **CONSTAT** | Sur un serveur conçu pour « tourner en fond des journées entières », la carte ouverte par défaut peut être celle d'hier. |
| 6 | **Le sondage s'arrête définitivement au premier raté.** `ping()` n'est appelé qu'au chargement ; `rafraichirJobs` ne se réarme que dans le `.then()` de succès, et le `.catch` est muet. | **CONSTAT** | L'utilisateur croit un job « en cours » indéfiniment, sans autre recours qu'un F5 auquel rien ne l'invite. |

**Argus, sur cet axe** : « Mes instruments n'ont pas vu ce que tu as reproduit en une
matinée. » Le diagnostic étage 2 le plus récent (2026-09-02 00:02) porte 5 findings ouverts
et **aucun ne vise `serve_wiki.py`**.

---

## 3. Axe 2 — Design (🎨 Sally)

Constats, chacun avec son emplacement :

- **Le même chiffre rendu deux fois à quinze lignes d'écart**, dans deux grammaires
  visuelles différentes (`.reponse-jour` ligne 436, puis `.pilotage .chiffre`). *Coût :* le
  lecteur pressé lit le total deux fois et croit avoir vu deux informations.
- **La pastille 🟢🟠🔴 mesure trois choses différentes sous le même habit** : maturité
  générique d'une pratique (ligne 833), score d'un projet sur cette pratique (855+), note
  qualitative LLM sur quatre dimensions. *Coût :* il faut relire la phrase à côté pour savoir
  de quel vert on parle — exactement le travail qu'une pastille est censée épargner.
- **`cadence-perime` recyclé sur un compteur de fichiers non commités** (ligne 474), qui n'a
  rien de périmé. *Coût :* l'ambre criera sur une flotte à jour, et on apprendra à ignorer la
  couleur.
- **Sept familles de pastilles qui ne se parlent pas** : `.badge.hot/.cold`,
  `.alert-critique/majeur/ok`, `.statut-adopte/ecarte`, `.rapport-statut.*`, le trio
  `.badge-llm/.badge-0t/.badge-nature`, les boutons de `.decision-arbitrage`. Le vert veut
  dire « adopté » ici, « chaud » là, « accepter » ailleurs.
- **Six formes de carte pour la même idée**, six rayons de coin différents (`.action-carte`
  9px, `.prat-card`, `.salle-carte` 10px, `.schema-agent` 10px + ombre, `.flux-etape` 9px,
  `.rapport-carte` 8px). *Coût :* la douzième section copiera la voisine la plus proche.
- **Une colonne de pastilles monochrome** dans l'onglet Veille (lignes 988-996) : `adopte`
  sur ses huit lignes. *Coût :* l'œil saute la colonne et rate la seule vraie information,
  qui est dans la prose.
- **Ce que le doublement a fait, sans généralité** : aucun étage de hiérarchie ajouté, le
  même étage rempli. La cellule `.craft-m` loge, même police et même graisse, « Dimension
  Revue de code. » (24 caractères) et un `title` de **905 caractères** de récit d'enquête.

**Argus a chiffré la dégradation** : l'arbitrage du 2026-09-01 notait 11 onglets → 11 et
26 230 → 49 345 mots. Recompté le 2026-09-02 : **57 162 mots, 483 938 octets, toujours
11 onglets**. **+15,8 % en 24 heures**, le lendemain de l'arbitrage qui demandait à la page
de se subordonner. C'est le seul point du dossier qui **se dégrade tout seul**.

---

## 4. Axe 3 — Expérience (🙋 Portevoix)

- **La page ment par défaut** en `file://` : « Serveur d'actions non détecté — lancer :
  py scripts/serve_wiki.py ». Le site ne peut pas se démarrer lui-même ; il faut sortir du
  navigateur pour le réveiller.
- **La réponse remontée au-dessus des onglets est le bon geste, écrite dans la langue de la
  structure** : « 5 cadence(s) en retard », « audit technique à relancer », « lignes changées
  depuis » — trois termes maison dans la première phrase. « Un site qui a besoin d'un onglet
  dictionnaire (📚 Tutoriel) pour que ses dix autres onglets se lisent n'a pas des libellés
  clairs, il a une notice. »
- **« Appliquer (le clic vaut arbitrage) » expose la règle interne R4** au lieu de dire ce
  qui va changer. Sa `confirm()` cite `--dangerously-skip-permissions` sans traduction, sans
  dire quel dépôt, quel fichier, ni comment revenir en arrière.
- **L'ordre de prudence est inversé** : le bouton qui touche un dépôt réel demande
  confirmation ; celui qui lance un run facturé de plusieurs minutes (🗣️ Déclencher) n'en
  demande aucune — la seule information avant le clic est un `title=` à survoler.
- **Quand ça échoue, le recours par défaut du site est de sortir du site** : une `alert()`
  navigateur qui renvoie vers une commande Python.

**Sa réponse à la question qu'on lui a demandé de ne pas éviter**, gardée intacte avec sa
condition : les 102 runs prouvent que la personne obtient déjà ce qu'elle veut par un canal
plus court ; mais une page qui exige un terminal pour démarrer, un dictionnaire pour se lire
et une alerte navigateur pour échouer **n'a jamais été mise à l'épreuve d'un vrai premier
clic** — donc personne ne peut honnêtement dire qu'elle a été essayée et rejetée.

**Argus lui retire un appui, et c'est justice** : « obtient ce qu'elle veut » n'est mesuré
nulle part. 4 des 6 derniers runs sont `partiel`, et `evolution-flotte` porte 0,67 reprise
par run (24 sur 36). Le canal conversationnel gagne parce qu'il est le seul emprunté, pas
parce qu'il est propre.

---

## 5. Axe 4 — Ce qui n'est jamais utilisé (🧰 Quincaillier)

**La mesure, avec sa fenêtre.** Depuis le correctif d'isolement du journal (`bfcf0b0`,
2026-07-31 22h34, qui a détourné les tests vers un fichier isolé), le journal réel n'a plus
produit **une seule ligne de job pendant 32 jours et 14 heures** — dernière ligne le
2026-07-31 à 20:11:19, suivante le 2026-09-02 à 09:51:55. Ce zéro-là n'était pollué par rien.
Sur la même période, 24 ouvertures de page, aucune suivie d'un job.

**Le coût du statu quo, chiffré par Argus au-delà de ce que Quincaillier apportait** :
depuis le dernier job réel, `serve_wiki.py` a pris **+234 lignes / −4 en 3 commits** (975
lignes aujourd'hui) pour un usage resté à zéro. Et la facture d'entretien que personne
n'avait posée : **10 fichiers de tests, 147 fonctions, 1 950 lignes — 18,6 % des 791 tests
du hub** gardent une surface qui n'a pas servi une fois en 32 jours.

### Retraits proposés

| Retrait | Mesure | Fenêtre observée | Pourquoi c'était là, et où le consigner |
| --- | --- | --- | --- |
| **Le bouton « Valider »** (onglet Arbitrer) | 1 seule ligne `action=valider` dans toute l'histoire du journal, et c'est une reproduction d'agent de ce matin — 0 clic humain | 2026-07-30 → 2026-09-02, 34 j, non pollués | Fermer la boucle R4 sans repasser par la conversation (commit `f73326f`). À consigner dans l'onglet Arbitrer ou dans un commentaire de `serve_wiki.py` — pas seulement dans le message du commit de suppression, sinon la prochaine personne qui lit R4 se demandera pourquoi la page ne l'applique plus. |
| **La console entière** (party/refuser/valider/audit/diagnostic, sondage 500 ms, anti-doublon, suivi de jobs) — c'est la **Rupture C** | 32 jours consécutifs à zéro + 24 ouvertures sans suite ; la machinerie a continué de grossir après la mesure du 31 juillet | 2026-07-31 → 2026-09-02 | La tension doit rester dans `approche-disruptive-wiki-2026-07-31.md`. **Non tranché en salle.** |

### Deux candidats que Quincaillier a retirés de sa propre liste

- **L'allowlist des 12 salles** (`_salles_valides()` en autorise 12, la page n'en câble que
  4) : documentée comme volontairement large, coût de maintien nul — une lecture de TOML,
  pas de code par salle.
- **Le bouton « Annuler » et `/api/cancel`** : cicatrice d'un incident réel (l'agent restait
  orphelin derrière le shim `.cmd`). « Retirer une protection contre un incident déjà vécu
  coûterait plus cher que la garder. »

---

## 6. Ce que l'inspection a produit en s'inspectant

À 09:51:55 ce matin, la reproduction du défaut 3 par Boundary a écrit dans le journal **de
production** :

```json
{"ts": "2026-09-02T09:51:55+02:00", "action": "valider", "cible": "cible reelle",
 "statut": "annule", "duree_s": 0.6, "llm": false}
```

Deux choses à la fois, et il faut les tenir séparées :

1. **C'est le défaut 3 attrapé en conditions réelles** — un travail qui a réussi, sorti
   étiqueté `annule`.
2. **C'est le journal repollué par sa propre inspection.** Le correctif `bfcf0b0` isole la
   suite de tests via `AGENT_SUPERVISION_JOBS_JOURNAL` ; il **n'isole pas une reproduction
   ad hoc lancée contre un vrai serveur**. Le § 5 de la réflexion du 2026-07-31 avait
   diagnostiqué « un journal d'usage pollué par ses propres tests ne peut pas servir à
   décider quoi que ce soit » : le correctif a fermé le canal `pytest`, pas le canal
   « quelqu'un vérifie à la main ».

Argus avait lu cette ligne comme un clic de la salle. L'orchestrateur l'a re-mesurée :
`cible: "cible reelle"`, `llm: false`, 0,6 s — c'est le harnais de Boundary, pas un clic.
La correction ne diminue pas le constat, elle le déplace : ce n'est pas « le bouton a enfin
servi », c'est « l'instrument de mesure a bougé pendant qu'on le lisait ».

---

## 7. La mesure manquante, et elle est bon marché

Proposée par Argus, et c'est la seule chose que la salle demande **avant** l'arbitrage de C :

> La page porte déjà 11 boutons `data-pane`. **Cinq lignes** qui journalisent le changement
> d'onglet côté serveur, fail-open comme les deux autres journaux, répondent à « l'onglet
> Actions a-t-il jamais été atteint ? »

- **Jamais atteint en 24 ouvertures** → Portevoix a raison, c'est un problème de porte.
- **Atteint et jamais cliqué** → Quincaillier a raison, c'est un problème d'utilité.

Sans cet instrument, l'arbitrage de la Rupture C se fait sur une conviction, et on
recommencera cette séance dans un mois sans avoir séparé « introuvable » de « inutile ».

Limite à énoncer avec l'instrument : il ne comptera **que le canal servi**. Tant que
CLAUDE.md prescrit d'ouvrir `docs/wiki.html` en `file://`, le dénominateur restera inconnu.
Poser l'instrument sans corriger la règle du hub, c'est mesurer à nouveau la moitié éclairée.

---

## 8. Tri par coût du statu quo (Argus)

1. **Le CORS et l'allowlist de `action_deploy`.** Coût de ne rien faire : une page tierce
   dans le même navigateur POSTe sur un serveur qui lance `--dangerously-skip-permissions`,
   sur un chemin d'écriture non contraint. Coût de faire : deux comparaisons de chaînes.
   **Échéance aujourd'hui, indépendamment de C** — une surface morte reste allumée.
2. **Les cinq lignes d'instrumentation d'onglet.** Sans elles, l'arbitrage de C se fait sur
   une conviction.
3. **Le drapeau `_annule` testé avant le code retour.** Il corrompt la mesure même sur
   laquelle la salle raisonne, et il vient de le faire. Un journal qui ment sur l'usage coûte
   plus cher qu'un bouton inutilisé.
4. **La subordination de la page.** Seul point qui se dégrade tout seul : +15,8 % en 24 h.
5. **Le retrait de la console.** Pas parce qu'il est bon marché — il vaut 18,6 % du parc de
   tests — mais parce que c'est le seul que la salle n'a pas le droit de trancher.

---

## 9. Sortant, producteur et recette

**Sortant** : ce rapport à quatre axes + la liste de retraits proposés du § 5.

**Producteur** : le playbook `dev-verifie` pour les correctifs (§ 8 points 1 à 4) ;
`evolution-flotte` si un correctif devait toucher un autre dépôt. **La salle ne produit
rien elle-même** et n'a modifié aucun fichier.

**Recette, bloquante** — le run ne se clôt pas en `succes` tant que ces points ne sont pas
joués :

- [ ] Chaque axe porte au moins un constat, ou la trace de ce qui a été regardé pour le
      clore. — **Tenu** : les quatre axes portent des constats, aucun n'a été clos à vide.
- [ ] Chaque retrait proposé cite sa mesure d'usage ET la fenêtre observée. — **Tenu** :
      § 5, deux retraits, deux fenêtres datées ; et deux candidats retirés avec leur raison.
- [ ] Aucun retrait n'est appliqué sans arbitrage. — **Tenu** : rien n'a été retiré.

---

## 10. Ce que la salle n'a pas fait

- **Elle n'a pas tranché la Rupture C**, et Argus refuse même de la re-proposer :
  l'arbitrage du 2026-09-01 se termine littéralement par « RESTE NON FAIT ET NON ARBITRÉ :
  réduire le nombre d'onglets, et la rupture C ». Elle est devant l'utilisateur depuis
  24 heures.
- **Elle n'a mesuré aucune performance côté navigateur** : pas de temps de rendu, pas de
  profil mémoire sur les 484 Ko. Les chiffres de performance de ce rapport sont des tailles
  et des volumes, pas des latences.
- **Elle n'a pas audité le générateur** (`scan_projets.py`), hors périmètre — alors que
  c'est lui qui fait grossir la page de 15,8 % en 24 heures.
- **Elle n'a pas ouvert le dénominateur `file://`**, faute d'instrument.
