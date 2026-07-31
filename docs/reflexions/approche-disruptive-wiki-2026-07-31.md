# Réflexion — une approche disruptive du site de supervision

**Statut : proposition. Rien n'est appliqué.** 2026-07-31, salle `atelier-idees`
(Cadreur, Portevoix, Wildcard, Splinter) en mode subagent, quatre voix indépendantes.

---

## 1. La salle a refusé de répondre avant qu'on mesure

Les quatre voix ont convergé sur le même reproche, chacune depuis son angle :

> « "Disruptif" n'est pas un objectif, c'est une humeur commandée sans qu'on sache ce
> qu'elle doit produire. » — **Cadreur**

> « Vous avez 66 runs et 89 arbitrages dans vos fichiers, mais zéro donnée sur moi,
> l'utilisateur unique, celui pour qui tout ça tourne. » — **Portevoix**

> « Le vrai trou commun à ces options, c'est qu'on n'a aucune mesure de ce que la
> personne vient chercher — sans ça, on disrupte à l'aveugle. » — **Wildcard**

> « On saute à "disruptif" sur une page servie à une seule personne sans avoir mesuré
> ce qu'elle vient y chercher : c'est exactement le trou que la réflexion précédente
> signalait déjà, et R6 dit qu'une vérification exécutable passe AVANT la rédaction. »
> — **Splinter**

La mesure était **exécutable**. Elle a donc été faite avant d'écrire la suite.

---

## 2. Ce que la mesure a trouvé — et qui retourne la question

### Le site n'est pas utilisé comme un poste de pilotage

`jobs.jsonl` enregistre chaque action lancée depuis un bouton du site. Sur **242 jobs
enregistrés** :

| Origine | Nombre |
| --- | --- |
| Artefacts de la suite de tests (`test-serve-wiki-refuser-isole`, `test-serve-wiki-anti-doublon`, `binaire-qui-nexiste-pas-42`…) | **241** |
| Actions réellement lancées depuis un bouton | **1** — la table ronde de vérification du câblage, lancée par l'agent le 2026-07-31 |

**Aucun clic utilisateur n'a jamais été mesuré sur les boutons de ce site.** Ni scan, ni
diagnostic, ni audit, ni veille, ni remédiation, ni validation d'arbitrage.

### Pendant ce temps, le pilotage réel passe ailleurs

`runs.jsonl` : **67 runs orchestrés**, tous déclenchés par la conversation. Leurs sujets :

| Ce que les demandes concernent | Runs |
| --- | --- |
| le wiki / le site lui-même | 28 |
| agents, orchestration, salles | 27 |
| un autre dépôt de la flotte | 24 |
| diagnostic et findings | 24 |
| tests et qualité | 16 |
| veille | 12 |

Et `evolution-flotte` porte **30 runs** à lui seul.

### La conclusion qui en découle

> Le site a été conçu comme une **console**, il est utilisé comme un **artefact**.
> Le poste de pilotage réel, c'est la conversation.

Ce n'est pas un échec du site : c'est une erreur sur sa nature. On a passé du temps à
câbler des boutons (12 boutons de table ronde, allowlists, anti-doublon, suivi de jobs)
pour un usage qui ne s'est jamais produit — pendant que 28 des 67 runs portaient sur le
site lui-même. **Le site est le sujet le plus travaillé du dispositif, et son interface
d'action est la moins utilisée.**

---

## 3. La rupture proposée : changer la nature de l'objet, pas sa mise en page

Les six options précédentes (fondre des onglets, replier, sous-onglets, ranger par
fréquence, page unique, réduire) partagent une hypothèse que la mesure invalide : **que
le problème est la navigation**. Si personne ne clique, réorganiser les clics ne change
rien.

Trois ruptures, par ordre de radicalité. Elles ne sont pas exclusives.

### Rupture A — Le site répond à une question, il n'expose plus une structure

Aujourd'hui les 11 onglets recopient l'architecture interne du dispositif : Pilotage,
Pratiques, Veille, Dispositif, Tokens… c'est l'organigramme du hub, pas la question d'un
lundi matin. Portevoix l'a dit sans détour :

> « Demandez-moi juste ce que je viens chercher à 8 h : "qu'est-ce qui a cassé" ou
> "qu'est-ce qui attend ma décision" — si la réponse tient en une phrase, la page devrait
> tenir en un écran, pas en onze onglets. »

**Ce que ça change :** la page d'entrée n'est plus un sommaire mais **une réponse**. Trois
ou quatre lignes en haut de page, calculées : ce qui a cassé, ce qui attend une décision,
ce qui a bougé depuis la dernière visite. Le reste devient une archive consultable, pas
une façade à parcourir.

**Ce que ça coûte :** il faut décider ce qui mérite la première ligne — donc trancher, ce
qui est plus dur que ranger. Les 11 onglets ne disparaissent pas, ils se subordonnent.

### Rupture B — Le dispositif vient à l'utilisateur au lieu de l'attendre

Wildcard :

> « Et si le wiki n'existait plus comme page à ouvrir mais comme flux qu'on reçoit — un
> poste qui pousse un message le matin ("VSCode3 a un finding ouvert depuis 14 jours, tu
> le regardes ?") au lieu d'attendre que la seule personne clique dessus. »

C'est cohérent avec la mesure : l'utilisateur ne vient pas, mais il **converse tous les
jours**. Le dispositif a déjà tout ce qu'il faut — un hook `SessionStart` qui parle à
chaque ouverture de session, et qui affiche déjà des compteurs.

**Ce que ça change :** l'information ne s'affiche plus sur une page qu'il faut penser à
ouvrir ; elle arrive **dans le canal réellement utilisé**. Le site cesse d'être le point
d'entrée et devient la profondeur de champ — on y va quand le hook a dit qu'il fallait y
aller.

**Ce que ça coûte :** le hook doit rester court, sinon il devient un mur qu'on cesse de
lire — exactement la maladie que le site a déjà.

### Rupture C — Assumer que le site est un rapport et retirer la console

Position la plus radicale, et la seule qui **soustrait** au lieu d'ajouter : les boutons
n'ont jamais servi. Soit on les supprime et le site redevient un rendu qu'on lit, soit on
les garde en sachant qu'on maintient une console fantôme — avec ses allowlists, son
anti-doublon, son suivi de jobs et ses tests.

**Ce que ça change :** une réduction franche de la surface à maintenir.

**Ce que ça coûte :** on perd une capacité réelle qui pourrait servir un jour, et le
câblage des tables rondes vient d'être posé. Splinter avertit :

> « Qu'est-ce qu'on abandonnerait pour de bon si le disruptif l'emporte, et l'hôte
> est-il prêt à perdre ça sans savoir ce qu'il perd ? »

---

## 4. Ce qu'il reste à trancher — et qui n'appartient pas à l'agent

1. **Quel critère de réussite ?** Cadreur exige une phrase de la forme « on saura que
   c'est réglé quand *tel geste quotidien* prend moins de *tel temps* ». Sans elle, on
   élira la proposition la plus séduisante, pas la plus juste.
2. **Console ou rapport ?** La mesure penche pour « rapport », mais elle mesure un usage
   passé, sur des boutons dont certains n'existent que depuis hier.
3. **A, B ou C ?** Elles se combinent : B change le canal, A change la page, C réduit la
   surface. L'ordre le moins risqué est **B puis A**, en gardant C en réserve.

---

## 5. Un défaut trouvé en chemin, sans rapport avec la demande

**La suite de tests écrit dans le journal de production.** 241 des 242 entrées de
`.claude/supervision/jobs.jsonl` proviennent de `tests/test_serve_wiki.py` — cibles
`test-serve-wiki-*`, `binaire-qui-nexiste-pas-42`, `annule`. Certains tests isolent bien
le journal (`monkeypatch` sur `JOBS_JOURNAL`, ligne 495), d'autres non.

Conséquence : **toute mesure d'usage tirée de ce fichier est faussée** — c'est
précisément ce qui a failli me faire conclure que le site était très utilisé. Un journal
d'usage pollué par ses propres tests ne peut pas servir à décider quoi que ce soit.

**Le correctif est d'une ligne, et le mécanisme existe déjà.** `serve_wiki.py:404` lit
`AGENT_SUPERVISION_JOBS_JOURNAL` avant de retomber sur le chemin de production :

```python
JOBS_JOURNAL = os.environ.get("AGENT_SUPERVISION_JOBS_JOURNAL") or os.path.join(
    ROOT, ".claude", "supervision", "jobs.jsonl")
```

Sur 41 tests dans `test_serve_wiki.py`, seuls 2 redirigent ce chemin. Il suffit de poser
la variable pour toute la suite (dans `conftest.py`, ou via `pytest.ini`) pour que plus
aucun test ne touche le journal réel. **Proposé, non appliqué** — c'est une modification
hors du périmètre de la demande, et elle mérite d'être vue plutôt que glissée dans un
travail d'idéation.

Reste ensuite à décider si les 241 lignes déjà écrites doivent être purgées du journal :
elles ne sont pas fausses (ces jobs ont bien tourné), elles sont simplement **hors sujet**
pour qui veut mesurer un usage humain.

---

## 6. Ce que cette réflexion n'a pas fait

- **Aucune mesure du parcours réel** : on sait maintenant que les boutons ne servent pas,
  on ne sait toujours pas quels onglets sont ouverts ni dans quel ordre. Le serveur
  pourrait le compter pour un coût dérisoire.
- **Aucune maquette** : les trois ruptures sont décrites, pas dessinées.
- **Rien n'a été appliqué**, et rien ne le sera sans arbitrage (R4).
