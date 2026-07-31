# Réflexion — réorganiser le wiki de supervision

**Statut : propositions, rien n'est appliqué.** Produit par la salle `atelier-idees`
(Cadreur, Portevoix, Wildcard, Splinter) le 2026-07-31, sur la demande de réduire le
nombre d'onglets et le scroll. Cette salle ne tranche pas : elle prépare de quoi trancher.

---

## 1. Les mesures, d'abord

Une seule page HTML, **11 onglets, 278 Ko, 26 230 mots**.

| Onglet | Poids | Mots | Part | Tableaux | Blocs repliés |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pilotage | 103,4 Ko | 14 293 | **55 %** | 3 | 1 |
| Dispositif | 35,9 Ko | 3 437 | 13 % | 2 | 2 |
| Pratiques & risques | 34,6 Ko | 2 326 | 9 % | 17 | 15 |
| Tutoriel | 26,7 Ko | 2 841 | 11 % | 2 | 0 |
| Projets | 13,1 Ko | 697 | 3 % | 1 | 6 |
| Veille | 11,9 Ko | 1 227 | 5 % | 2 | 0 |
| Tokens | 11,2 Ko | 674 | 3 % | 1 | 0 |
| Actions correctives | 11,0 Ko | 386 | 1 % | 0 | 5 |
| Déploiement | 2,6 Ko | 126 | 0,5 % | 0 | 0 |
| Actions | 2,6 Ko | 150 | 0,6 % | 0 | 0 |
| Exports | 1,4 Ko | 73 | 0,3 % | 0 | 0 |

Deux faits dominent tout le reste : **Pilotage pèse 55 % du site à lui seul**, et les
**quatre plus petits onglets totalisent 735 mots** — moins de 3 %.

---

## 2. Ce que la salle a trouvé, et qui change la demande

### Les deux axes demandés se contredisent

> « Fusionner des onglets pour en avoir moins, ça empile du contenu dans ceux qui restent,
> donc ça allonge le scroll — l'axe (a) peut très bien détruire l'axe (b), et personne n'a
> dit lequel prime. » — **Cadreur**

C'est le point le plus utile de la séance. *Réduire le nombre d'onglets* et *réduire le
scroll* ne sont pas deux améliorations qui s'additionnent : la première déplace du contenu
vers moins de pages, donc allonge mécaniquement celles qui restent.

### Regrouper les petits ne réglerait rien du problème réel

> « Dix onglets sur onze tiennent ensemble en moins de 36 Ko pendant que Pilotage seul pèse
> 55 % du contenu : regrouper les petits ne retire pas un mot au scroll de Pilotage. »
> — **Splinter**

L'effort de regroupement porterait sur 3 % du contenu. Le scroll dont on souffre est
ailleurs, et il ne bougera pas.

### Les sous-onglets déplacent le coût, ils ne le suppriment pas

> « Ils déplacent le contenu derrière un clic qu'il faudra se rappeler d'ouvrir — on paie
> en navigation ce qu'on croit économiser en défilement. » — **Splinter**

### Le vrai problème d'orientation n'est pas le nombre, c'est le nom

> « "Actions" range des scans et "Actions correctives" des propositions à arbitrer, et rien
> dans les deux noms ne dit lequel est lequel avant d'avoir cliqué dedans. Vous ne pouvez
> pas sentir ce flottement, parce que vous savez déjà ce que chaque onglet contient. »
> — **Portevoix**

### Et personne n'a mesuré l'usage

> « Aucune mesure d'usage réel : quel onglet s'ouvre le plus souvent, et pour y chercher
> quoi. » — **Splinter**

Le dispositif mesure la flotte, ses agents, ses tokens — mais pas la page elle-même.

---

## 3. Les options posées (Wildcard), ni classées ni défendues

| # | Option | Ce qu'elle règle | Ce qu'elle coûte |
| --- | --- | --- | --- |
| A | Fondre les 4 petits onglets (Actions, Actions correctives, Déploiement, Exports) en un seul « Agir » | 11 → 8 onglets | Ne touche pas au scroll de Pilotage ; empile 735 mots dans une page |
| B | Généraliser les blocs repliés `<details>` — déjà utilisés dans 3 onglets (26 occurrences) | Réduit le scroll sans nouveau mécanisme de navigation | Le contenu reste, replié ; un clic de plus pour le lire |
| C | Sous-onglets **réservés à Pilotage** uniquement | Attaque les 55 % qui comptent vraiment | Un mécanisme de navigation neuf, pour un seul onglet |
| D | Ranger par **fréquence de consultation** (quotidien / hebdomadaire / rare) plutôt que par thème | Met le geste du jour en premier | Demande une mesure d'usage qui n'existe pas |
| E | Supprimer les onglets, page unique à ancres | Un lecteur solo et quotidien navigue peut-être mieux au Ctrl+F | Rupture forte avec l'existant |
| F | **Ne pas réorganiser : réduire.** Couper et archiver dans Pilotage | S'attaque à la cause (14 293 mots), pas au symptôme | Décider ce qu'on cesse d'afficher — le plus dur |

> « Si Pilotage pèse 14 293 mots à lui seul, le problème n'est peut-être pas la navigation
> mais le contenu — sinon on repeint un mur qu'il faudrait abattre. » — **Wildcard**

---

## 4. Ce qu'il faudrait décider avant de coder

1. **Quel critère de réussite ?** Trois candidats, qui ne bougent pas ensemble : moins
   d'onglets comptés · moins de pixels à dérouler · moins de secondes pour retrouver une
   information un jour de panne. Le troisième est le seul qui décrive un usage réel.
2. **Traite-t-on le symptôme ou la cause ?** Les options A à E réorganisent ; seule F
   réduit. Aucune n'est exclusive des autres.
3. **Mesure-t-on l'usage d'abord ?** Le site est servi par un serveur local : compter les
   onglets ouverts serait peu coûteux et trancherait D — et validerait ou non l'intuition
   de départ.
4. **Le renommage est-il traité à part ?** « Actions » / « Actions correctives » est un
   problème de nom, pas de structure — et il se corrige en deux lignes, indépendamment de
   tout le reste. C'est le seul geste que la salle recommande sans réserve.

---

## 5. Ce que cette réflexion n'a pas fait

- Aucune mesure d'usage réel de la page n'a été prise : tout le raisonnement porte sur le
  volume de contenu, pas sur ce que quelqu'un vient y chercher.
- Aucune maquette n'a été produite ; les options sont décrites, pas dessinées.
- La salle n'a pas hiérarchisé les options — c'est délibéré, c'est le rôle de l'arbitrage.
