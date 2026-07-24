"""Garde à la génération du JS du wiki — finding risque_technique de l'audit
2026-07-24 : le <script> de wiki.html est une grosse chaîne générée depuis Python,
et DEUX bugs d'échappement Python->JS ont été vécus le même jour (un \\' consommé
par Python cassant la syntaxe JS du fichier ENTIER — silencieusement —, puis des
SyntaxWarning \\* / \\s). Ce test verrouille la classe de bugs : le JS réellement
livré doit être syntaxiquement valide, vérifié par un vrai parseur (node --check),
pas par une relecture.
"""

import os
import re
import shutil
import subprocess

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(HUB, "docs", "wiki.html")

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node absent du PATH")
class TestJsGenere:
    def _script_livre(self):
        html = open(WIKI, encoding="utf-8").read()
        blocs = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert blocs, "aucun <script> dans docs/wiki.html"
        return blocs

    def test_wiki_html_existe(self):
        assert os.path.isfile(WIKI), "docs/wiki.html absent — lancer scripts/scan_projets.py"

    def test_js_livre_syntaxiquement_valide(self, tmp_path):
        # node --check parse sans exécuter : exactement la garde qui aurait attrapé
        # le bug du \' (SyntaxError: Unexpected identifier 'elle') avant livraison.
        for i, bloc in enumerate(self._script_livre()):
            f = tmp_path / f"bloc{i}.js"
            f.write_text(bloc, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)],
                               capture_output=True, text=True, timeout=30)
            assert r.returncode == 0, f"JS invalide (bloc {i}) : {r.stderr[:400]}"

    def test_echappement_pieges_connus(self):
        # Les deux pièges déjà payés : un \' nu consommé par Python (il ne doit
        # rester AUCUNE séquence backslash-apostrophe cassée hors chaîne), et les
        # regex JS dont l'échappement doit survivre au transit par Python.
        script = "\n".join(self._script_livre())
        assert "qu\\'elle" in script or "qu'elle" not in script, \
            "l'apostrophe de « qu'elle » doit être échappée dans la chaîne JS"
        # la regex des options doit garder ses backslashes (\*, \s)
        if "choixProposes" in script:
            assert re.search(r"/\^\\\*\\\*\(Option\\s", script), \
                "la regex de choixProposes a perdu son échappement au transit Python->JS"
