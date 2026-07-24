"""Non-régression de la règle « CLAUDE.md borné » du scan (chantier 2, veille pratiques).

Pratique Anthropic adoptée le 2026-07-24 : un CLAUDE.md trop long fait ignorer les
règles — le scan mesure la taille (0 token) et alerte au-delà de CLAUDE_MD_MAX_LIGNES.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class TestClaudeMdLignes:
    def test_absent_donne_none(self, tmp_path):
        assert scan.claude_md_lignes(str(tmp_path / "CLAUDE.md")) is None

    def test_compte_les_lignes(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_text("a\nb\nc\n", encoding="utf-8")
        assert scan.claude_md_lignes(str(p)) == 3

    def test_derniere_ligne_sans_newline_comptee(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_text("a\nb", encoding="utf-8")
        assert scan.claude_md_lignes(str(p)) == 2


class TestClaudeMdLibelle:
    def test_absent_none(self):
        assert scan.claude_md_libelle(None) is None

    def test_sous_le_seuil_simple(self):
        assert scan.claude_md_libelle(scan.CLAUDE_MD_MAX_LIGNES) == "CLAUDE.md"

    def test_au_dessus_du_seuil_alerte(self):
        lib = scan.claude_md_libelle(scan.CLAUDE_MD_MAX_LIGNES + 1)
        assert "⚠" in lib and "élaguer" in lib

    def test_seuil_est_celui_de_la_pratique(self):
        # Le seuil documenté par la veille (150) — le changer est une décision, pas un accident.
        assert scan.CLAUDE_MD_MAX_LIGNES == 150
