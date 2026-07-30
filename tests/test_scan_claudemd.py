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


class TestDisciplineTokens:
    """Adoption de la trouvaille de veille « Gestion du contexte outillée » (2026-07-24,
    dormante 6 jours, remontée en finding veille:contexte-outille le 2026-07-30).

    Le piège que ces tests verrouillent : les CLAUDE.md de la flotte parlent de tokens
    EN PASSANT (« grille ~50 tokens », « étage 1, 0 token ») sans documenter la moindre
    discipline. Un marqueur qui compterait les occurrences du mot rendrait 6/6 vert et
    la mesure serait un mensonge — c'est le titre de section qui fait foi."""

    def test_titre_de_section_reconnu(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            "# Projet\n\n## Discipline de gestion des tokens\n\n- /compact à 40 %\n",
            encoding="utf-8")
        assert scan.discipline_tokens(str(tmp_path)) is True

    def test_variante_de_titre_reconnue(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            "## Optimisation tokens (cf. export)\n", encoding="utf-8")
        assert scan.discipline_tokens(str(tmp_path)) is True

    def test_mot_token_en_passant_ne_suffit_pas(self, tmp_path):
        """LE cas qui rendrait la mesure fausse."""
        (tmp_path / "CLAUDE.md").write_text(
            "# Projet\n\n- `scan.py` : etage 1, 0 token, lance par le hook\n"
            "- grille ~50 tokens routant les demandes\n", encoding="utf-8")
        assert scan.discipline_tokens(str(tmp_path)) is False

    def test_cherche_aussi_dans_les_conventions(self, tmp_path):
        d = tmp_path / "docs" / "wiki" / "technical"
        d.mkdir(parents=True)
        (d / "conventions.md").write_text("### Gestion du contexte\n", encoding="utf-8")
        assert scan.discipline_tokens(str(tmp_path)) is True

    def test_projet_sans_rien(self, tmp_path):
        assert scan.discipline_tokens(str(tmp_path)) is False


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
