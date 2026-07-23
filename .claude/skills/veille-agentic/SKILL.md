---
name: veille-agentic
description: Agent de veille agentic — explore la partie publique de GitHub (et sources associées) pour repérer agents, sous-agents, skills, rules, playbooks ou frameworks pertinents pour les projets supervisés, croise avec l'inventaire multi-projets (projets.json + catalogue), et enregistre les trouvailles dans .claude/veille/veille.json (rendues dans la section 2 du wiki de supervision). Cadence : tous les 3 jours (le hook SessionStart signale « veille agentic à lancer » quand elle est périmée) ou déclenchement manuel à tout moment. À charger quand l'utilisateur demande une veille, quand le hook la signale périmée, ou quand on cherche s'il existe déjà une solution publique avant de créer un agent/skill maison.
---

# veille-agentic — veille GitHub sur l'écosystème agentic

Objectif : ne pas réinventer ce qui existe déjà publiquement, et repérer tôt les
évolutions utiles aux projets supervisés (listés dans `projets.json`).

## Méthode — 4 étapes

### 1. Contexte : qu'est-ce qui est pertinent ?

Lire `projets.json` et `docs/wiki/projets-supervision.md` (généré) pour connaître les
projets, leurs besoins réels et leurs manques du moment. Les thèmes durables des projets :

- **Claude Code** : skills, subagents (`.claude/agents`), hooks, orchestration
  multi-agents, supervision d'usage.
- **BMAD-METHOD** : nouvelles versions, nouveaux modules (tea, bmb, cis…), pratiques
  de tri/customisation.
- **Génération PPT programmatique** : python-pptx, rendu/vérification visuelle,
  design de decks.
- **Pratiques d'équipe agentic** : rules/playbooks versionnés, mémoire projet, garde-fous
  (hooks destructifs, revues adversariales).

### 2. Explorer (WebSearch / WebFetch — public uniquement)

3 à 6 recherches ciblées par session de veille, PAS une rafale exhaustive. Exemples de
requêtes efficaces :

- `github claude code skills collection <thème>` / `awesome claude code`
- `github claude code subagents <besoin du moment>`
- `BMAD-METHOD release notes` / repo `bmad-code-org/BMAD-METHOD` (releases récentes)
- `github python-pptx <problème rencontré récemment>`
- Suivre aussi les trouvailles précédentes en statut `nouveau`/`etudie` (leur repo a-t-il bougé ?)

Règles : sources **publiques** uniquement, jamais d'exécution de code téléchargé pendant
la veille, jamais d'installation — la veille observe et qualifie, l'adoption est un
chantier séparé arbitré par l'utilisateur.

### 3. Qualifier chaque trouvaille

Ne retenir que ce qui a un lien concret avec au moins un projet supervisé. Pour chaque
entrée retenue : titre, url, type (`agent` | `sous-agent` | `skill` | `rules` |
`playbook` | `framework` | `outil`), projets concernés, pertinence en une phrase
(le POURQUOI, pas un résumé du repo), statut initial `nouveau`.

5 entrées max par session de veille — une veille qui noie ne sert personne.

### 4. Enregistrer et propager

Mettre à jour `.claude/veille/veille.json` (créer le dossier au besoin) :

```json
{
  "derniere_veille": "2026-07-23T18:00:00",
  "entrees": [
    {
      "titre": "nom court",
      "url": "https://github.com/...",
      "type": "skill",
      "projets_concernes": ["VSCode2", "VScode5"],
      "pertinence": "pourquoi c'est pertinent en une phrase",
      "date": "2026-07-23",
      "statut": "nouveau"
    }
  ]
}
```

Règles d'entretien du fichier :
- **Cumulatif** : ne jamais écraser les entrées existantes — ajouter les nouvelles,
  mettre à jour `derniere_veille`.
- **Cycle de vie des statuts** : `nouveau` → `etudie` (regardé de près) → `adopte`
  (intégré à un projet — noter où) ou `ecarte` (avec la raison dans `pertinence`).
  Les transitions de statut sont des décisions utilisateur, pas automatiques.
- **Doublons** : si une trouvaille existe déjà (même url), mettre à jour sa pertinence
  plutôt que dupliquer.

Puis régénérer le wiki : `py scripts/scan_projets.py` — la section 2 « Veille agentic »
reflète le fichier. Terminer en restituant à l'utilisateur les nouvelles entrées en une
ligne chacune.

## Cadence

- Le hook SessionStart (`.claude/hooks/remind_veille_agentic.py`) signale « veille
  agentic à lancer » si la dernière veille date de plus de **3 jours**.
- Déclenchement manuel : `/veille-agentic` à tout moment.
- La veille ne bloque jamais une autre tâche en cours : si le rappel tombe au milieu
  d'un chantier, proposer de la faire en fin de session.
