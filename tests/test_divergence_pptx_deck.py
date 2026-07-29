"""Matrice de divergence des copies de pptx_deck.py (finding
pptx_deck:matrice-divergence, arbitré 2026-07-29) : la mesure ast — fonctions
communes / propres / signatures divergentes — sur des copies synthétiques,
plus les garde-fous copie absente / non parsable."""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _copie(tmp_path, projet, code):
    rel = scan.PPTX_DECK_COPIES[projet]
    chemin = tmp_path / projet / rel
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(code, encoding="utf-8")
    return {"nom": projet, "chemin": str(tmp_path / projet)}


class TestSignaturesFonctions:
    def test_extrait_les_signatures_top_niveau(self, tmp_path):
        f = tmp_path / "m.py"
        f.write_text("def a(x, y=1):\n    def interne(z):\n        pass\n\n"
                     "async def b(*args):\n    pass\n", encoding="utf-8")
        fns = scan.signatures_fonctions(str(f))
        assert set(fns) == {"a", "b"}, "les fonctions internes ne comptent pas"
        assert fns["a"] == "x, y=1"

    def test_fichier_absent_donne_none(self, tmp_path):
        assert scan.signatures_fonctions(str(tmp_path / "absent.py")) is None

    def test_fichier_non_parsable_donne_none(self, tmp_path):
        f = tmp_path / "casse.py"
        f.write_text("def oops(:\n", encoding="utf-8")
        assert scan.signatures_fonctions(str(f)) is None


class TestMatrice:
    def test_communes_propres_et_divergences(self, tmp_path):
        projets = [
            _copie(tmp_path, "VSCode2", "def carte(slide, titre):\n    pass\n"
                                        "def jauge(v):\n    pass\n"),
            _copie(tmp_path, "VSCode3", "def carte(slide, titre):\n    pass\n"
                                        "def teardrop(s):\n    pass\n"),
            _copie(tmp_path, "VSCode4", "def carte(slide, titre, accent=None):\n    pass\n"
                                        "def radar(s, axes):\n    pass\n"),
        ]
        mat = scan.matrice_divergence_pptx_deck(projets)
        assert mat["communes"] == ["carte"]
        assert mat["propres"]["VSCode2"] == ["jauge"]
        assert mat["propres"]["VSCode3"] == ["teardrop"]
        assert mat["propres"]["VSCode4"] == ["radar"]
        # carte a 2 signatures distinctes (VSCode4 a ajouté accent=None)
        assert [d["fonction"] for d in mat["divergentes"]] == ["carte"]
        assert mat["divergentes"][0]["signatures"]["VSCode4"] == "slide, titre, accent=None"

    def test_copie_absente_affichee_sans_casser(self, tmp_path):
        projets = [
            _copie(tmp_path, "VSCode2", "def carte(s):\n    pass\n"),
            _copie(tmp_path, "VSCode3", "def carte(s):\n    pass\n"),
            {"nom": "VSCode4", "chemin": str(tmp_path / "VSCode4")},  # pas de copie
        ]
        mat = scan.matrice_divergence_pptx_deck(projets)
        absente = next(c for c in mat["copies"] if c["projet"] == "VSCode4")
        assert absente["fonctions"] is None
        assert mat["communes"] == ["carte"]  # calculée sur les 2 présentes

    def test_projet_hors_copies_ignore(self, tmp_path):
        projets = [{"nom": "VScode5", "chemin": str(tmp_path)}]
        mat = scan.matrice_divergence_pptx_deck(projets)
        assert mat["copies"] == [] and mat["communes"] == []


class TestRenduEtPageLivree:
    def test_render_html_porte_les_chiffres(self, tmp_path):
        projets = [
            _copie(tmp_path, "VSCode2", "def carte(s):\n    pass\ndef jauge(v):\n    pass\n"),
            _copie(tmp_path, "VSCode3", "def carte(s):\n    pass\n"),
        ]
        mat = scan.matrice_divergence_pptx_deck(projets)
        html = scan.render_divergence_html(lambda s: s, mat)
        assert "pptx_deck.py" in html and "jauge" in html

    def test_page_livree_contient_la_matrice(self):
        page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        assert "Divergence des copies de <code>pptx_deck.py</code>" in page, \
            "matrice absente de la page livrée — régénérer via scripts/scan_projets.py"
