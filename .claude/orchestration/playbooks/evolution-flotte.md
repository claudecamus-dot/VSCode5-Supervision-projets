# Playbook `evolution-flotte` — modifier un AUTRE projet de la flotte, vérifié et scopé

Le métier récurrent de CE projet : appliquer une évolution agentic (rattachement de
skills, déploiement du dispositif, correction de playbook/catalogue, propagation d'un
fix) sur un ou plusieurs projets cibles de `projets.json`. Capitalisé depuis les 4
premiers runs réels du 2026-07-23 (correction VSCode2, correction VSCode1, déploiement
VSCode, propagation fix scan) — constat superviseur : 5 runs sur 6 se composaient à vide
faute de playbook qui matche.

**Les trois leçons fondatrices, payées le jour même** :

1. **Lire l'état RÉEL de la cible avant d'écrire** (run VSCode1 : les 5 skills «
   à rattacher » étaient déjà rattachées — la correction juste était 3 lignes, pas un
   re-câblage). Le wiki de supervision peut retarder sur la réalité : il éclaire le
   cadrage, il ne le remplace pas.
2. **Commit scopé au périmètre de l'évolution** (run VSCode : 174 fichiers de churn
   BMAD/Codex préexistant découverts au moment de committer — jamais les embarquer,
   jamais les écraser ; si le dépôt cible porte du travail non commité qui n'est pas le
   nôtre, le signaler et le laisser).
3. **Adapter au canal du projet cible, ne pas plaquer** (run VSCode : génération PPT via
   COMOP Node/PowerShell, pas python-pptx ; étape terminale = la `revue-increment`
   préexistante du projet, pas une copie).

```json
{
  "nom": "evolution-flotte",
  "description": "Évolution agentic appliquée à un ou plusieurs projets cibles de la flotte : cadrage sur l'état réel, modification scopée, vérifications, commit limité au périmètre, wiki rafraîchi, journal.",
  "statut": "eprouve",
  "source": "manuel",
  "declencheurs": [
    "corrige/rattache/répare X sur VSCodeN",
    "déploie/met à jour le dispositif (orchestrateur, superviseur, skills, playbooks) sur un projet",
    "propage un fix/une évolution d'un composant partagé vers d'autres projets",
    "traite les propositions du diagnostic pour un projet cible"
  ],
  "etapes": [
    {
      "id": "cadrage-reel",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "état RÉEL de chaque cible lu AVANT d'écrire : fichiers concernés ouverts (playbook/catalogue/settings/skills), git status du dépôt cible relevé (churn préexistant identifié et exclu du périmètre), canal/conventions propres au projet identifiés. Le wiki de supervision éclaire, la lecture directe tranche — une demande peut être déjà (partiellement) satisfaite : la correction minimale prime sur le re-câblage."
      },
      "checkpoint": false
    },
    {
      "id": "modification",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "modification scopée et adaptée à la cible (jamais un écrasement aveugle d'une copie divergée — édits ciblés si le fichier a des adaptations locales) ; chaque exigence explicite de la demande cochée contre le diff ; si plusieurs cibles, appliquer projet par projet"
      },
      "checkpoint": false
    },
    {
      "id": "verification",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "sur CHAQUE cible modifiée : py_compile sur les scripts Python touchés, JSON/settings validés, hooks exécutés à blanc si touchés, tests du projet cible lancés s'ils couvrent le périmètre (leçon VSCode1 : test-export-ppt vert avant commit), grep de cohérence sur les identifiants modifiés"
      },
      "checkpoint": false
    },
    {
      "id": "revue-fraiche",
      "agent": "sous-agent revue (contexte frais)",
      "mode": "cascade",
      "modele": "sonnet",
      "contrat": {
        "type": "reel",
        "critere": "SI l'évolution modifie du code ou de la config exécutable (script, hook, settings, playbook) : revue en CONTEXTE FRAIS avant commit (pratique Anthropic adoptée 2026-07-24 — le relecteur ne voit que le diff par cible et les exigences de la demande, pas le raisonnement de l'implémenteur) ; ne rapporter que les écarts de correctness/périmètre (fichier hors périmètre embarqué, exigence non couverte, régression visible au diff), pas les préférences de style. Étape sautable UNIQUEMENT pour une évolution purement documentaire, en le notant dans le journal."
      },
      "checkpoint": false
    },
    {
      "id": "commit-scope",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "git add limité aux fichiers du périmètre (vérifié par git diff --cached --name-only — aucun fichier du churn préexistant), message expliquant le POURQUOI avec référence au constat/diagnostic d'origine, push si le dépôt a un remote"
      },
      "checkpoint": "avant commit/push sur un dépôt cible — action difficilement réversible : mandat utilisateur explicite requis (la demande initiale peut le porter)"
    },
    {
      "id": "wiki-et-journal",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "scripts/scan_projets.py relancé (le wiki reflète l'état post-évolution), run journalisé via log_run.py avec le playbook 'evolution-flotte' et les cibles dans la demande ; si l'évolution répond à un finding du diagnostic, l'arbitrage correspondant est enregistré"
      },
      "checkpoint": false
    }
  ],
  "regle_reprise": "une relance ciblée par étape en échec de contrat, puis escalade utilisateur avec l'état réel du/des dépôt(s) cible(s)"
}
```
