# Sous-agents porteurs en sommeil

Ces sous-agents ne sont **pas supprimés** : ils sont sortis de `.claude/agents/`, donc
plus adressables par l'outil `Agent`, mais leur contenu est là et leur historique git
intact. Les réveiller, c'est un `git mv` dans l'autre sens.

## Pourquoi, et depuis quand

Mise en sommeil le **2026-09-01**, sur arbitrage utilisateur, en soldant un rendez-vous
que le hub s'était donné à lui-même et qu'il avait laissé passer.

L'arbitrage `agents:emprunt-routage-bmad` du 2026-07-30 disait : les 8 porteurs viennent
d'être créés, ils sont à **0/46 skills empruntées et 2/8 porteurs lancés** ; on ne les
propage pas à la flotte, et on se donne **une semaine d'usage** avant de trancher.
Échéance : le 2026-08-06. Personne n'est revenu. Le rendez-vous a été retrouvé le
2026-09-01 en passant en revue les 110 arbitrages enregistrés — **26 jours de retard**.

Mesure faite ce jour-là, 33 jours après la création :

| | 2026-07-30 | 2026-09-01 |
| --- | --- | --- |
| Porteurs ayant servi au moins une fois | 2 / 8 | **4 / 8** |
| Skills BMAD chargées au moins une fois | 0 / 46 | **2 / 46** |

Les quatre porteurs qui ont servi restent en place : `agent-supervisor` (11 invocations),
`bmad-revue` (7), `bmad-recherche` (1), `veille-agentic` (1). Les quatre d'ici n'ont
**jamais** été invoqués.

## Le fait qui a pesé le plus

Les deux seules skills BMAD jamais chargées sont `bmad-party-mode` (7, les salles de
table ronde) et `bmad-customize` (1) — et **aucune des deux ne l'a été par un porteur**.
`bmad-revue` a tourné 7 fois sans charger une seule des skills de revue qu'il existe
pour porter.

Le porteur n'est donc pas le mécanisme qui fait partir une skill BMAD. C'est ce que la
skill `agent-orchestrator` dit déjà dans son propre § 2 quinquies : « une skill BMAD dont
le travail tient dans la conversation courante s'invoque **inline** ». Les rangées de la
table de routage qui nommaient ces trois porteurs disent maintenant `—` : la skill reste
routée, elle part inline.

## La réserve, gardée telle quelle

`bmad-cadrage` et `bmad-livraison` sont en régime **proposé** : ils ne se lancent que sur
feu vert explicite de l'utilisateur. Leur zéro peut donc mesurer une absence de demande
plutôt qu'une inutilité — la distinction a été posée au moment de l'arbitrage, et
l'utilisateur a tranché en connaissance de cause. Si un chantier de cadrage produit ou
d'implémentation arrive, les réveiller est le geste attendu, pas un aveu.

## Réveiller un porteur

```bash
git mv .claude/agents-en-sommeil/<nom>.md .claude/agents/<nom>.md
# puis remettre son nom dans la colonne « Sous-agent porteur » de la table
# BMAD-ROUTAGE de .claude/skills/agent-orchestrator/SKILL.md, regenerer le kit
# et re-propager le socle.
```

Le registre des types d'agents est chargé au **démarrage de session** : un porteur
réveillé n'est adressable qu'à la session suivante.
