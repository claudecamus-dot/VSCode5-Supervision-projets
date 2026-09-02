"""Aucun `subprocess.run(text=True)` sans `encoding=` dans le dispositif.

Revue de sécurité du 2026-09-01, quatre findings d'une même famille, arbitrés le jour
même. Le motif est banal et le dégât ne l'est pas.

LE MÉCANISME. `text=True` seul décode la sortie avec l'**encodage local**, pas en UTF-8.
Mesuré sur ce poste : `locale.getpreferredencoding(False)` rend `cp1252`. Trois effets,
tous constatés :

1. **Comparaison impossible.** Le premier caractère accentué suffit. C'est ce qui a fait
   refuser TOUTE propagation par `_socle_non_commite` pendant une heure le 2026-09-01 :
   400 lignes accentuées dans le socle, 0 survivante au décodage, et un refus permanent
   annonçant « le socle diffère du blob HEAD » alors que `git status` disait propre et
   que les deux textes faisaient 49 262 caractères identiques.
2. **`stdout` à `None`.** Sur un octet indécodable, le thread lecteur meurt, `stdout`
   vaut `None` et `returncode` reste **0** — donc les `except` qui guettent une erreur
   ne se déclenchent pas, et c'est un `AttributeError: 'NoneType'` qui remonte, ailleurs,
   en désignant la mauvaise cause.
3. **Le fail-open annoncé devient un fail-hard.** `warn_verif_before_commit.py` promet
   « fail-open partout » dans son docstring : avec un seul nom de fichier non-cp1252
   indexé, il sort en **exit 1 avec 27 lignes de traceback** sur un `git commit`, et
   l'avertissement est perdu pour TOUT le commit. Et dans `scan_transcripts.py` — le
   hook SessionStart des six projets — le contrôle « reliquat non commité » disparaît
   pendant que le traceback est imprimé sur stdout, donc injecté dans le contexte de
   démarrage, à chaque session.

POURQUOI UN TEST PAR AST plutôt qu'un `grep`. Le grep ligne à ligne se trompe dans les
deux sens : il rate un appel dont `encoding=` est sur la ligne suivante (faux positif),
et il ne voit pas un `text=True` passé par un dictionnaire. Ce test lit l'arbre
syntaxique, donc il mesure ce que Python exécutera.
"""

import ast
import os

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Le code du dispositif — pas les skills BMAD installées (46, non maintenues ici), pas
# les tests (leur sortie n'alimente aucun garde-fou).
RACINES = (
    os.path.join(HUB, "scripts"),
    os.path.join(HUB, ".claude", "hooks"),
    os.path.join(HUB, ".claude", "supervision"),
    os.path.join(HUB, ".claude", "dispositif"),
    os.path.join(HUB, ".claude", "orchestration"),
)


def _fichiers():
    for racine in RACINES:
        for dossier, _sous, noms in os.walk(racine):
            if "__pycache__" in dossier:
                continue
            for nom in noms:
                if nom.endswith(".py"):
                    yield os.path.join(dossier, nom)


def _appels_fautifs(chemin):
    """Les `subprocess.run(...)` en mode texte sans encodage explicite."""
    with open(chemin, encoding="utf-8") as fh:
        try:
            arbre = ast.parse(fh.read(), filename=chemin)
        except SyntaxError:  # pragma: no cover - un fichier illisible se voit ailleurs
            return []
    fautifs = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        nom = getattr(cible, "attr", None) or getattr(cible, "id", None)
        if nom not in ("run", "check_output", "Popen"):
            continue
        mots = {k.arg for k in noeud.keywords if k.arg}
        texte = any(k.arg in ("text", "universal_newlines")
                    and getattr(k.value, "value", None) is True
                    for k in noeud.keywords)
        if texte and "encoding" not in mots:
            fautifs.append(noeud.lineno)
    return fautifs


@pytest.mark.parametrize("chemin", sorted(_fichiers()),
                         ids=lambda c: os.path.relpath(c, HUB).replace("\\", "/"))
def test_aucun_mode_texte_sans_encodage_explicite(chemin):
    fautifs = _appels_fautifs(chemin)
    assert not fautifs, (
        f"{os.path.relpath(chemin, HUB)} : subprocess en mode texte sans `encoding=` "
        f"aux lignes {fautifs} — la sortie sera decodee en cp1252 sur ce poste, et "
        "un seul caractere accentue rend la comparaison fausse ou `stdout` a None "
        "avec un returncode 0 trompeur")


class TestLeDetecteurDetecteVraiment:
    """Un garde-fou qu'on n'a pas vu crier ne prouve rien (lecon du 2026-07-30)."""

    def test_il_voit_un_appel_fautif(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("import subprocess\n"
                     "subprocess.run(['git'], capture_output=True, text=True)\n",
                     encoding="utf-8")
        assert _appels_fautifs(str(f)) == [2]

    def test_il_laisse_passer_un_appel_correct(self, tmp_path):
        f = tmp_path / "y.py"
        f.write_text("import subprocess\n"
                     "subprocess.run(['git'], capture_output=True, text=True,\n"
                     "               encoding='utf-8')\n", encoding="utf-8")
        assert _appels_fautifs(str(f)) == []

    def test_il_ignore_le_mode_binaire(self, tmp_path):
        """Sans `text=True`, la sortie est en octets : aucun decodage, aucun probleme."""
        f = tmp_path / "z.py"
        f.write_text("import subprocess\n"
                     "subprocess.run(['git'], capture_output=True)\n", encoding="utf-8")
        assert _appels_fautifs(str(f)) == []

    def test_il_voit_aussi_universal_newlines(self, tmp_path):
        f = tmp_path / "w.py"
        f.write_text("import subprocess\n"
                     "subprocess.run(['git'], universal_newlines=True)\n",
                     encoding="utf-8")
        assert _appels_fautifs(str(f)) == [2]
