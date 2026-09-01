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


def tmp_court() -> str:
    r"""Un répertoire temporaire au chemin COURT, portable.

    Windows plafonne les chemins à 260 caractères, et le scratchpad de session du
    harnais dépasse à lui seul cette limite : plusieurs tests fabriquaient de faux
    échecs (« chemin introuvable » sur un répertoire qui venait d'être créé). D'où
    l'usage de `C:	mp` — mais l'écrire EN DUR dans un fichier versionné le rend
    faux partout ailleurs : autre poste, autre volume, CI Linux. C'est la dette que
    `test_propager_socle._lire` avait déjà eu à corriger, pour la même raison.

    Ici : le chemin court sous Windows, `tempfile.gettempdir()` ailleurs — où la
    limite n'existe pas et où une lettre de lecteur n'a aucun sens.
    """
    if os.name != "nt":
        return tempfile.gettempdir()
    base = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "tmp")
    try:
        os.makedirs(base, exist_ok=True)
        return base
    except OSError:
        return tempfile.gettempdir()
