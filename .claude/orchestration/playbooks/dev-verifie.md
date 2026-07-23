# Playbook `dev-verifie` — implémentation vérifiée de bout en bout

Workflow de dev générique : implémenter, tester, **vérifier en réel** (pas seulement un
statut de test vert — une suite qui passe ne garantit pas qu'un rendu/écran/export soit
correct), puis revue finale avant tout commit.

Importé depuis le projet VSCode2 (Interview-to-Deck) où ce déroulé était éprouvé ; ici,
**statut `importé` — à confirmer sur les premiers runs de ce projet** (routing-hints le
fera évoluer vers `eprouve` une fois rejoué avec succès).

Les étapes de vérification réelle sont **conditionnelles au type de fichiers touchés** :
ne garder à l'instanciation que celles dont la condition s'applique, ne jamais retirer les
tests ni la revue finale avant commit.

Frontière avec `export-ppt-verifie` : un changement de code qui *touche* la génération PPT
au passage reste ici (l'étape `verification-pptx` couvre) ; quand le **livrable est le deck
lui-même** (layout, contenu, visuel), préférer `export-ppt-verifie`.

```json
{
  "nom": "dev-verifie",
  "description": "Implémentation d'une feature/correction avec tests, vérification réelle adaptée aux fichiers touchés, et revue finale avant commit.",
  "statut": "importe",
  "source": "manuel",
  "declencheurs": [
    "implémente/corrige/ajoute une fonctionnalité",
    "changement de template/UI (HTML, CSS, JS)",
    "changement touchant la génération d'un export PPT",
    "fin d'incrément, préparation d'un commit de code produit"
  ],
  "etapes": [
    {
      "id": "cadrage",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "fichiers concernés lus, appelants des fonctions/champs partagés grep-és avant modification"
      },
      "checkpoint": false
    },
    {
      "id": "implementation",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "chaque exigence EXPLICITE de la demande (points numérotés, contraintes) cochée une à une contre le diff — pas seulement « ça compile/passe » ; toute exigence réinterprétée ou écartée signalée, jamais silencieuse ; style du fichier environnant respecté"
      },
      "checkpoint": false
    },
    {
      "id": "tests",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "verdict lu sur la ligne de synthèse RÉELLE du test-runner (N passed / 0 failed / 0 error), pas sur une sortie tronquée ou filtrée",
        "commande": "(adapter à la stack du projet — ex. pytest -q)"
      },
      "checkpoint": false
    },
    {
      "id": "verification-ui",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "SI template/CSS/JS/écran touché : rendu réel regardé (screenshot ou app lancée), pas seulement le code source relu"
      },
      "checkpoint": false
    },
    {
      "id": "verification-pptx",
      "agent": "pptx-verify",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "SI la génération d'un export PPT est touchée : export réel rendu en images et inspecté (python-pptx est un parseur tolérant, un fichier qui parse peut ne pas s'ouvrir correctement dans PowerPoint)"
      },
      "checkpoint": false
    },
    {
      "id": "revue-finale",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "relecture du diff complet, exigences de la demande recochées une à une, tests/vérifications ci-dessus confirmés faits avant de proposer le commit"
      },
      "checkpoint": "avant tout commit — action difficilement réversible, proposer, ne pas exécuter unilatéralement"
    }
  ],
  "regle_reprise": "une relance ciblée par étape en échec de contrat, puis escalade utilisateur avec l'état réel"
}
```
