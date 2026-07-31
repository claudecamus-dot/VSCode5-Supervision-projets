# Fork local — `bmad-party-mode/scripts/resolve_party.py`

**Date** : 2026-07-31 · **Statut** : actif · **Verrou** : `tests/test_bmad_party_mode_resolve.py`

## Pourquoi ce fichier existe

Le fichier corrigé est **livré par BMAD**, pas écrit par nous : il porte une empreinte
SHA-256 au manifeste `_bmad/_config/files-manifest.csv` (ligne 232). Une mise à jour de
BMAD l'écrasera et **reprendra silencieusement le bug**. Ce document existe pour que le
correctif soit réappliquable, et le test pour que sa disparition soit bruyante.

## Le symptôme

Sur un poste Windows dont la console est en cp1252 (le cas ici), `party-mode` ne démarrait
pas du tout. Le résolveur crashait en exit 1 :

```text
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 1458
AttributeError: 'NoneType' object has no attribute 'strip'   ← resolve_party.py:52
```

Conséquence mesurée avant correctif : `installed_agents_resolved: false`, `members: 0`.
La table ronde se tenait à **zéro participant**. Cohérent avec l'étage 1, qui comptait
1 invocation de la skill (2026-07-30) et 0 run journalisé.

## Le diagnostic — deux défauts distincts et ordonnés

| # | Où | Cause | Quand il frappe |
| --- | --- | --- | --- |
| **B** | `resolve_party.py:_run_json` | `subprocess.run(..., text=True)` sans `encoding=` décode en cp1252 une sortie UTF-8 (l'octet 0x8F vient de U+FE0F, sélecteur de variante d'un emoji). L'erreur naît dans un **thread lecteur**, donc n'atteint pas l'`except` ; `out.stdout` reste `None`, et la ligne `out.stdout.strip()`, **hors du `try`**, lève `AttributeError` | Immédiatement — seul défaut sur le chemin fatal |
| **A** | `_bmad/scripts/resolve_config.py:174` | `json.dumps(..., ensure_ascii=False)` écrit des emoji sur un stdout cp1252 → `UnicodeEncodeError` côté producteur | **Après B corrigé** : les agents ne se résolvent plus |

`resolve_customization.py` est, lui, **correct** (il reconfigure son propre stdout en
UTF-8) : c'est pour cela que le correctif ne le touche pas.

## Le correctif appliqué

Un seul point de modification, dans `_run_json` :

1. `encoding="utf-8", errors="replace"` — corrige le **côté lecture** (défaut B) ;
2. `env={**os.environ, "PYTHONIOENCODING": "utf-8"}` — corrige le **côté écriture** de
   l'enfant (défaut A) **sans patcher `resolve_config.py`**, qui est un fichier installeur
   partagé par toutes les skills BMAD ;
3. `out.stdout is None` ajouté à la garde — rétablit le contrat que la fonction annonce
   dans son propre docstring (« None on any failure ») et que le crash a démenti.

Le point 3 est ce qui distingue une correction de classe d'une rustine : sans lui, tout
futur mode d'échec laissant `stdout` à `None` refait tomber la skill entière.

`import os` a été ajouté aux imports (le module ne l'importait pas).

## Ce qu'il ne faut pas faire à la place

- **Patcher `_bmad/scripts/resolve_config.py`** : même volatilité (SHA au manifeste,
  ligne 245), mais surface bien plus large — ce script sert à toutes les skills BMAD.
- **Se contenter de `errors="replace"`** sans le reste : cela remplacerait un crash bruyant
  par une salle vide silencieuse — exactement l'état qui a rendu ce bug invisible.
- **Poser `PYTHONIOENCODING` dans l'environnement de la session** : cela masquerait le
  problème pour nous sans corriger l'appel, et ne survivrait pas à un lancement depuis un
  autre contexte.

## Réappliquer après une mise à jour BMAD

`tests/test_bmad_party_mode_resolve.py` échoue si le correctif disparaît (canari sur le
source **et** exécution réelle du script). Rejouer alors les trois points ci-dessus dans
`_run_json`, puis relancer la suite.

## À remonter en amont

Le défaut vaut pour tout utilisateur Windows non-UTF-8 de BMAD. Il mériterait un rapport
au projet BMAD — non fait à ce jour.
