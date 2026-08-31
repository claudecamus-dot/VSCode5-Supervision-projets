"""Isolation des journaux de PRODUCTION pendant la suite de tests.

Pourquoi ce fichier existe (mesuré le 2026-07-31). `.claude/supervision/jobs.jsonl`
est le journal des actions lancées depuis les boutons du wiki — la seule trace
d'usage réel du site. Sur les **242 entrées** qu'il contenait, **241 provenaient de
la suite de tests** : cibles `test-serve-wiki-anti-doublon`,
`binaire-qui-nexiste-pas-42`, jobs `annule`… Une seule action humaine s'y trouvait.

Ce n'est pas un détail cosmétique : une réflexion sur l'usage du site a failli
conclure l'inverse de la vérité en lisant ce fichier. **Un journal d'usage pollué par
ses propres tests ne peut servir à décider de rien.**

Le mécanisme d'isolation existait déjà — `serve_wiki.py` lit
`AGENT_SUPERVISION_JOBS_JOURNAL` avant de retomber sur le chemin de production — mais
seuls 2 tests sur 41 le posaient. On le pose ici pour TOUTE la suite, une fois, au
niveau le plus haut : ainsi un test nouveau est isolé par défaut, sans que son auteur
ait à y penser. C'est le seul régime qui tienne dans la durée.

`setdefault` et non affectation directe : si quelqu'un lance la suite avec la variable
déjà posée (CI, débogage ciblé), son choix l'emporte.
"""

import os
import tempfile

# Posé à l'IMPORT du conftest, donc avant que le moindre module de test n'importe
# `serve_wiki` — le chemin y est figé au niveau module, une fois pour toutes.
_JOURNAL_ISOLE = os.path.join(
    tempfile.gettempdir(), "supervision-tests-jobs.jsonl")
os.environ.setdefault("AGENT_SUPERVISION_JOBS_JOURNAL", _JOURNAL_ISOLE)

# Même raison, même geste, pour le journal des VUES posé le 2026-08-31 : plusieurs
# tests fonctionnels demandent `/` au vrai serveur, donc sans cette ligne la suite
# gonflerait elle-même le compteur d'ouvertures de page — et on referait, sur un
# journal neuf, exactement l'erreur qui a rendu jobs.jsonl inexploitable (241 de ses
# 242 entrées produites par les tests). Un compteur d'usage pollué par ses propres
# tests ne peut servir à décider de rien : il est pire qu'absent, il a l'air d'une
# mesure.
_VUES_ISOLE = os.path.join(
    tempfile.gettempdir(), "supervision-tests-vues.jsonl")
os.environ.setdefault("AGENT_SUPERVISION_VUES_JOURNAL", _VUES_ISOLE)
