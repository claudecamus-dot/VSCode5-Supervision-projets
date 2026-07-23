# Playbook `export-ppt-verifie` — génération de deck PPT vérifiée au rendu réel

Chaîne de génération PPT : produire ou faire évoluer un deck avec `pptx-deck`, enrichir si
pertinent (cadres photo via `pptx-framed-image`, qualité rédactionnelle via
`slide-text-polish`), puis **toujours** vérifier au rendu réel avec `pptx-verify` —
python-pptx est un parseur tolérant, un fichier qui parse peut ne pas s'ouvrir correctement
dans PowerPoint. `restitution-deck-design` fournit la review checklist design (hiérarchie,
rythme d'espacement, couleur=sens, alignement, cohérence de composant).

Importé depuis le projet VSCode2, où cette colonne vertébrale génération → vérification
rendu était la pratique effective. Ici, **statut `importe` — à confirmer sur les premiers
runs de ce projet**. Toutes les skills citées (`pptx-deck`, `pptx-verify`,
`restitution-deck-design`) sont globales à l'utilisateur ; `pptx-framed-image` et
`slide-text-polish` sont installées dans ce projet.

**Itération de design ≠ reprise** : la boucle **rendu de contrôle → liste de défauts →
correction → re-rendu** est l'étape NOMINALE de ce playbook, bornée à **2 itérations**
au-delà du rendu initial ; à la 3ᵉ, escalade utilisateur avec l'état réel — même livrable
rejeté ≥ 3 tours = ne pas re-deviner le défaut, demander à l'utilisateur de pointer le
défaut précis sur SON artefact. Dans le journal (`log_run.py`), le champ `reprises` ne
compte QUE ce qui sort de ce budget ou relève d'un imprévu — jamais les itérations de la
boucle nominale.

```json
{
  "nom": "export-ppt-verifie",
  "description": "Production ou évolution d'un deck PPT : génération, enrichissements conditionnels (cadres photo, polish rédactionnel, passe design), vérification au rendu réel obligatoire, revue finale avant commit.",
  "statut": "importe",
  "source": "manuel",
  "declencheurs": [
    "génère/améliore/corrige un deck PPT de restitution",
    "remplir les cadres photo (« ici mettre une Photo ») d'un template",
    "qualité rédactionnelle / design des slides d'un deck"
  ],
  "etapes": [
    {
      "id": "cadrage",
      "agent": "session principale",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "contenu de la présentation identifié (données, structure, message), template client ou deck vierge choisi. SI la demande référence un deck/charte externe : RENDRE 2-3 slides de la référence (pptx-verify) et en extraire les motifs concrets AVANT d'implémenter — interdit d'affirmer une conformité de charte de mémoire."
      },
      "checkpoint": false
    },
    {
      "id": "generation",
      "agent": "pptx-deck",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "export .pptx produit sans exception, self-check géométrique de la skill passé"
      },
      "checkpoint": false
    },
    {
      "id": "cadres-photo",
      "agent": "pptx-framed-image",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "SI le template porte des cadres photo (prstGeom round2DiagRect, « ici mettre une Photo ») : image insérée épousant la forme exacte du cadre"
      },
      "checkpoint": false
    },
    {
      "id": "polish-texte",
      "agent": "slide-text-polish",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "deterministe",
        "critere": "SI le contenu textuel des slides a été produit ou retouché : slide_lint passé sur {title, bullets}, findings bloquants corrigés"
      },
      "checkpoint": false
    },
    {
      "id": "verification-rendu",
      "agent": "pptx-verify",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "export réel rendu en images et inspecté visuellement (valeurs alignées, panneaux ni vides ni étirés, pas de collision avec le chrome du template) — jamais retirée à l'instanciation. BOUCLE NOMINALE : rendu → liste de défauts → correction → re-rendu, ≤ 2 itérations au-delà du rendu initial puis escalade utilisateur — ces itérations ne se journalisent PAS en reprises."
      },
      "checkpoint": false
    },
    {
      "id": "design-review",
      "agent": "restitution-deck-design",
      "mode": "cascade",
      "modele": "(session)",
      "contrat": {
        "type": "reel",
        "critere": "OBLIGATOIRE dès que le diff touche un layout / composant / couleur de slide (seuil objectif, pas un auto-jugement). Lancer restitution-deck-design et appliquer sa review checklist au rendu réel, corriger, puis retour à verification-rendu."
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
        "critere": "relecture du diff (code produit s'il y en a), exigences de la demande recochées une à une, vérifications ci-dessus confirmées faites avant de proposer le commit"
      },
      "checkpoint": "avant tout commit — action difficilement réversible, proposer, ne pas exécuter unilatéralement"
    }
  ],
  "regle_reprise": "une relance ciblée par étape en échec de contrat, puis escalade utilisateur avec l'état réel. Les itérations de la boucle nominale rendre→corriger→re-rendre (≤ 2 au-delà du rendu initial, cf. verification-rendu) sont le déroulé attendu, PAS des reprises."
}
```
