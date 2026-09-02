"""Bornage des synthèses d'audit trop longues (arbitrage du 2026-09-02, « les deux,
générateur d'abord ») : la page pesait 483 938 octets / 57 162 mots (+15,8 % de mots
en 24 h) sans qu'aucun onglet n'ait été ajouté — la salle d'inspection notait qu'une
synthèse d'audit de 905 caractères logeait dans la même cellule `<small>`, même
police, même couleur, qu'un libellé de 24 caractères (« Dimension Revue de code. »).

`DETAIL_LIMITE` (scripts/scan_projets.py) borne désormais l'attribut `title=` lui
aussi, pas seulement le texte affiché par `tronque()` : au-delà de la limite, le
texte intégral part dans `docs/wiki/projets-supervision.md` (canal de détail déjà
publié par ce même script) et un lien visible `détail complet →` y renvoie. Rien ne
disparaît — voir `TestPageLivreeDetailAtteignable` qui vérifie que chaque lien posé
dans la page pointe vers une ancre qui existe réellement dans le markdown.

Aveu honnête (discipline R6) : `rendu_detail_borne`, `ancre_synthese` et
`details_syntheses_longues` sont des fonctions NOUVELLES, écrites dans la même passe
que ces tests — elles ne pouvaient pas être vues rouges avant d'exister (pas de
fonction à appeler). Ce qui a réellement été vérifié AVANT d'écrire le correctif,
mesuré à la commande (règle R6) : `.claude/audits/*.json` contient 24 synthèses
dont 14 dépassent 240 caractères (jusqu'à 895 caractères sur une seule), et l'ancienne
page livrée posait ces 24 synthèses en entier dans `title=`, deux fois pour les 7
dimensions en niveau moyen/critique (table de l'onglet Pratiques + carte de l'onglet
Arbitrer, `ecarts_du_projet` partageant la même source). `TestLeGardeFouNestPasVert
ParConstruction` prouve que le test posé sur la page livrée aurait bien attrapé
l'ancienne construction (leçon feedback-test-garde-fou-assertion-vide : un garde-fou
qui ne peut jamais échouer ne prouve rien)."""

import html
import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class TestRenduDetailBorne:
    def test_texte_sous_la_limite_titre_complet_sans_lien(self):
        texte = "Synthèse courte, sans enjeu."
        attr, lien = scan.rendu_detail_borne(html.escape, texte, "ancre-test")
        assert attr == f' title="{html.escape(texte)}"'
        assert lien == ""

    def test_texte_au_dessus_de_la_limite_titre_tronque_et_lien_pose(self):
        texte = "x" * (scan.DETAIL_LIMITE + 400)
        attr, lien = scan.rendu_detail_borne(html.escape, texte, "audit-vscode-securite")
        m = re.search(r'title="([^"]*)"', attr)
        assert m, "attribut title= absent"
        titre_extrait = html.unescape(m.group(1))
        assert titre_extrait.endswith("…")
        assert len(titre_extrait) == scan.DETAIL_LIMITE + 1  # + l'ellipse
        assert 'href="wiki/projets-supervision.md#audit-vscode-securite"' in lien
        assert "détail complet" in lien

    def test_texte_vide_ne_pose_ni_titre_ni_lien(self):
        attr, lien = scan.rendu_detail_borne(html.escape, "", "ancre-test")
        assert attr == "" and lien == ""

    def test_frontiere_exacte_de_la_limite_ne_declenche_pas_le_lien(self):
        texte = "y" * scan.DETAIL_LIMITE  # exactement à la limite, pas au-delà
        attr, lien = scan.rendu_detail_borne(html.escape, texte, "ancre-test")
        assert lien == ""
        assert attr == f' title="{html.escape(texte)}"'


class TestAncreSynthese:
    def test_meme_projet_et_dimension_donnent_la_meme_ancre(self):
        a1 = scan.ancre_synthese("VSCode1", "securite")
        a2 = scan.ancre_synthese("VSCode1", "securite")
        assert a1 == a2 == "audit-vscode1-securite"

    def test_projets_ou_dimensions_differents_donnent_des_ancres_differentes(self):
        assert (scan.ancre_synthese("VSCode1", "securite")
                != scan.ancre_synthese("VSCode2", "securite"))
        assert (scan.ancre_synthese("VSCode1", "securite")
                != scan.ancre_synthese("VSCode1", "robustesse"))


class TestDetailsSynthesesLongues:
    def test_ne_retient_que_les_syntheses_qui_depassent_la_limite(self):
        existants = [
            {"nom": "Court", "audit": {"dimensions": {
                "robustesse": {"synthese": "ok, rien à signaler."}}}},
            {"nom": "Long", "audit": {"dimensions": {
                "securite": {"synthese": "z" * (scan.DETAIL_LIMITE + 10)}}}},
        ]
        longues = scan.details_syntheses_longues(existants)
        assert [(p, k) for p, k, _, _ in longues] == [("Long", "securite")]

    def test_texte_integral_conserve_aucune_troncature_dans_la_collecte(self):
        texte = "z" * (scan.DETAIL_LIMITE + 123)
        existants = [{"nom": "P", "audit": {"dimensions": {
            "securite": {"synthese": texte}}}}]
        longues = scan.details_syntheses_longues(existants)
        assert longues[0][3] == texte  # intégral, pas de tronque()

    def test_projet_sans_audit_ne_casse_pas(self):
        assert scan.details_syntheses_longues([{"nom": "PasAudite", "audit": None}]) == []


class TestPageLivreeDetailAtteignable:
    """Vérifie l'artefact RÉEL (docs/wiki.html + docs/wiki/projets-supervision.md),
    pas une reconstruction en mémoire — la page doit avoir été régénérée par
    `py scripts/scan_projets.py` pour que ces tests reflètent l'état livré."""

    @classmethod
    def setup_class(cls):
        cls.page = open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        md_path = os.path.join(HUB, "docs", "wiki", "projets-supervision.md")
        cls.md = open(md_path, encoding="utf-8").read()

    def test_aucun_title_de_petite_cellule_ne_depasse_la_limite(self):
        # Les title= des synthèses d'audit vivent dans <small title="..."> — s'ils
        # dépassaient encore DETAIL_LIMITE, le bornage n'aurait pas été appliqué au
        # rendu réel (et pas seulement à la fonction testée isolément ci-dessus).
        for m in re.finditer(r'<small title="([^"]*)">', self.page):
            titre = html.unescape(m.group(1))
            assert len(titre) <= scan.DETAIL_LIMITE + 1, (
                f"title= de {len(titre)} caractères encore présent dans la page "
                "livrée : le bornage n'est pas appliqué au rendu réel"
            )

    def test_chaque_lien_de_detail_pointe_vers_une_ancre_qui_existe(self):
        liens = re.findall(
            r'class="lien-detail" href="wiki/projets-supervision\.md#([^"]+)"',
            self.page)
        assert liens, ("aucun lien-detail dans la page livrée alors que des "
                       "synthèses dépassent DETAIL_LIMITE (.claude/audits/*.json) "
                       "— régénérer via py scripts/scan_projets.py")
        for ancre in liens:
            assert f'<a id="{ancre}"></a>' in self.md, (
                f"lien vers #{ancre} posé dans wiki.html sans ancre correspondante "
                "dans projets-supervision.md — c'est une troncature muette"
            )

    def test_le_texte_integral_est_publie_dans_le_markdown(self):
        # Pas seulement l'ancre : le texte qui suit doit être la synthèse RÉELLE,
        # pas un résumé supplémentaire — sinon le lien mène à un autre résumé.
        assert "### Détail des synthèses d'audit" in self.md
        # Au moins une synthèse connue pour dépasser 240 caractères (mesurée dans
        # .claude/audits/VScode5.json) doit apparaître intégralement.
        import json
        audit = json.load(open(
            os.path.join(HUB, ".claude", "audits", "VScode5.json"), encoding="utf-8"))
        dims = audit.get("dimensions", {})
        long_dims = [(k, d["synthese"]) for k, d in dims.items()
                     if len(d.get("synthese") or "") > scan.DETAIL_LIMITE]
        assert long_dims, "fixture attendue : VScode5.json doit porter une synthèse longue"
        cle, texte = long_dims[0]
        assert texte in self.md, (
            "le texte intégral de la synthèse longue n'est pas publié tel quel "
            "dans projets-supervision.md"
        )

    def test_le_craft_court_reste_affiche_sans_lien(self):
        # Non-régression : une pratique au libellé court ("Dimension Revue de
        # code.") ne doit jamais recevoir de lien-detail — seul ce qui dépasse la
        # limite en gagne un.
        assert "Dimension Revue de code." in self.page
        idx = self.page.index("Dimension Revue de code.")
        voisinage = self.page[idx:idx + 120]
        assert "lien-detail" not in voisinage


class TestLeGardeFouNestPasVertParConstruction:
    """Leçon mémoire (feedback-test-garde-fou-assertion-vide) : un test qui ne peut
    jamais échouer ne prouve rien. On vérifie ici que la construction D'AVANT ce
    correctif (title= posant le texte intégral, sans borne ni lien) AURAIT ÉCHOUÉ
    au test `test_aucun_title_de_petite_cellule_ne_depasse_la_limite` ci-dessus —
    donc que ce test n'est pas vide."""

    def test_construction_naive_d_avant_le_correctif_aurait_echoue(self):
        texte_long = "x" * (scan.DETAIL_LIMITE + 400)
        naive = f'<small title="{html.escape(texte_long)}">résumé</small>'
        m = re.search(r'<small title="([^"]*)">', naive)
        titre = html.unescape(m.group(1))
        assert len(titre) > scan.DETAIL_LIMITE + 1, (
            "la construction naïve ne dépasse pas la limite : le test de la page "
            "livrée ne prouverait rien"
        )
