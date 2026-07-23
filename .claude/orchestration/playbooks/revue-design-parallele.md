# Playbook `revue-design-parallele` — N angles de revue en fan-out

Pattern générique de revue par fan-out : plusieurs agents de revue lancés en parallèle sur
des angles distincts (ex. parcours utilisateur, cohérence visuelle, contenu, accessibilité),
consolidés ensuite en une liste de correctifs concrets.

Importé depuis le projet VSCode2, où ce pattern était éprouvé sur des revues UX/design.
Ici, **statut `importe` — à confirmer sur les premiers runs de ce projet**.

Règles du mode parallèle (cf. `agent-orchestrator`) : angles réellement indépendants,
lecture seule pendant le fan-out, ≤ 4 sous-agents, consolidation obligatoire — chaque
sous-agent repart d'un contexte froid, exiger des rapports courts et structurés.

**Garde exhaustivité** : un fan-out d'`Explore` lit des *extraits*, pas des fichiers
entiers — il ne garantit jamais l'exhaustivité. Quand le fan-out sert à recenser toutes
les références à des identifiants **avant une suppression/renommage**, la consolidation
DOIT se terminer par une garde déterministe : un `grep -r` (ou l'outil Grep) de chaque
identifiant retiré sur tout le dépôt, dont le résultat **prime** sur les rapports des
sous-agents.

```json
{
  "nom": "revue-design-parallele",
  "description": "Revue UX/design (ou revue multi-angles d'un livrable) par fan-out de sous-agents en lecture seule, puis consolidation en backlog d'actions priorisées.",
  "statut": "importe",
  "source": "manuel",
  "declencheurs": [
    "revue UX/UI indépendante d'un ensemble d'écrans",
    "passer en revue X sous plusieurs angles",
    "audit d'un livrable selon des dimensions distinctes (design, contenu, cohérence, parcours)"
  ],
  "etapes": [
    {
      "id": "definition-angles",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "2 à 4 angles réellement indépendants définis, avec pour chacun le périmètre à lire et le format de rapport attendu (constats courts + gravité)"
      },
      "checkpoint": false
    },
    {
      "id": "fan-out-revue",
      "agent": "Explore",
      "mode": "parallele",
      "modele": "sonnet",
      "fan_out_max": 4,
      "contrat": {
        "type": "deterministe",
        "critere": "un rapport court par angle reçu (jamais anticipé/fabriqué), lecture seule respectée — aucune écriture par les sous-agents"
      },
      "checkpoint": false
    },
    {
      "id": "consolidation",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "constats dédoublonnés et priorisés en un backlog d'actions concrètes, contradictions entre angles arbitrées explicitement. SI le but du fan-out était une énumération exhaustive avant suppression/renommage : garde déterministe finale OBLIGATOIRE — grep -r (ou l'outil Grep) de chaque identifiant retiré sur tout le dépôt, dont le résultat PRIME sur les rapports des sous-agents (qui ne lisent que des extraits)."
      },
      "checkpoint": "restituer le backlog à l'utilisateur avant d'appliquer le moindre correctif — la revue est le livrable, les fixes sont un mandat séparé"
    }
  ],
  "regle_reprise": "une relance ciblée par étape en échec de contrat (sous-agent muet ou hors format : une seule relance du sous-agent concerné), puis escalade utilisateur avec l'état réel"
}
```
