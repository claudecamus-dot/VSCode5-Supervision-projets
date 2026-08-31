"""Orientation des onglets Tutoriel et Dispositif (demande utilisateur 2026-08-31 :
« j'ai besoin d'avoir une vision plus claire des infos du tutoriel & dispositif »).

État mesuré avant le chantier : les deux onglets les plus lourds du wiki (Tutoriel
30 045 caractères, Dispositif 55 948) s'ouvraient sans AUCUNE couche d'orientation —
on atterrissait dans un mur de 34 fiches (Tutoriel) ou de 9 blocs h3 (Dispositif), sans
sommaire ni ancres. Et le Tutoriel DUPLIQUAIT la moitié du Dispositif : son « schéma de
la table ronde élargie » redonne les 9 salles et leurs voix, que l'onglet d'à côté porte
déjà en cartes actionnables — le lecteur croisait deux fois la même information sous deux
formes, sans lien de l'une à l'autre. C'est le constat de Portevoix en salle : « rien
dans le menu ne dit où ça pèse lourd ; il découvre les 113 Ko en tombant dedans ».

L'invariant gardé ici : le sommaire est DÉRIVÉ des titres réellement rendus, jamais
recopié — un sommaire écrit à la main mentirait dès le premier bloc ajouté (même
invariant que le schéma de la party, dérivé des TOML). D'où des assertions sur l'objet
généré : chaque entrée du sommaire pointe une ancre qui existe, et chaque h3 du pane a
son entrée.
"""

import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets_orientation", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _pane_tutoriel():
    return scan.orienter_pane(scan.render_tutoriel_html())


def _h3(bloc):
    return re.findall(r'<h3\b[^>]*>(.*?)</h3>', bloc)


class TestSommaireDerive:
    def test_le_tutoriel_a_un_sommaire(self):
        html = _pane_tutoriel()
        assert 'class="onglet-sommaire"' in html

    def test_chaque_h3_a_une_entree_au_sommaire(self):
        """Le sommaire est dérivé : un bloc ajouté demain y figure sans qu'on y pense."""
        html = _pane_tutoriel()
        sommaire = re.search(r'<nav class="onglet-sommaire".*?</nav>', html, re.S).group(0)
        liens = re.findall(r'href="#([^"]+)"', sommaire)
        assert len(liens) == len(_h3(html.split("</nav>", 1)[1])), (
            "une entrée de sommaire par h3 du pane, ni plus ni moins")

    def test_chaque_lien_du_sommaire_pointe_une_ancre_existante(self):
        """Un sommaire vers des ancres mortes est pire que pas de sommaire."""
        html = _pane_tutoriel()
        sommaire = re.search(r'<nav class="onglet-sommaire".*?</nav>', html, re.S).group(0)
        ids = set(re.findall(r'id="([^"]+)"', html))
        for cible in re.findall(r'href="#([^"]+)"', sommaire):
            assert cible in ids, f"ancre morte au sommaire : #{cible}"

    def test_un_id_existant_n_est_pas_ecrase(self):
        """`<h3 id=\"party\">` existe déjà et des liens externes peuvent le viser :
        l'orientation AJOUTE des ids aux h3 qui n'en ont pas, elle ne renomme jamais
        ceux qui en ont."""
        html = _pane_tutoriel()
        assert 'id="party"' in html

    def test_le_sommaire_est_insere_une_seule_fois(self):
        html = _pane_tutoriel()
        assert html.count('class="onglet-sommaire"') == 1


class TestDeduplicationTutorielDispositif:
    def test_le_schema_des_salles_est_replie_dans_le_tutoriel(self):
        """Les 9 salles vivent en cartes actionnables dans l'onglet Dispositif ; le
        Tutoriel garde les CONCEPTS et replie le casting complet — présent pour qui
        le déplie, plus un mur pour les autres."""
        html = scan.render_tutoriel_html()
        i = html.find('id="party"')
        assert i > -1, "le schéma doit rester présent (test_wiki_party le verrouille)"
        avant = html[:i]
        assert avant.rstrip().endswith("<summary>") or "<details" in avant[-400:], (
            "le schéma de la table ronde doit être dans un <details> replié")

    def test_le_repli_dit_ou_vivent_les_cartes_actionnables(self):
        html = scan.render_tutoriel_html()
        m = re.search(r"<summary>(.*?)</summary>", html, re.S)
        assert m, "le repli doit avoir un résumé cliquable"
        assert "Dispositif" in m.group(1), (
            "le résumé doit dire que les commandes vivent dans l'onglet Dispositif")


class TestDispositifOriente:
    def test_le_dispositif_a_aussi_son_sommaire(self):
        """Même traitement pour l'onglet le plus lourd après Pilotage."""
        source = open(os.path.join(HUB, "scripts", "scan_projets.py"),
                      encoding="utf-8").read()
        i = source.find('id="pane-dispositif"')
        assert i > -1
        assert "orienter_pane(render_dispositif_html" in source[i:i + 400], (
            "le pane dispositif doit passer par orienter_pane à l'assemblage")
