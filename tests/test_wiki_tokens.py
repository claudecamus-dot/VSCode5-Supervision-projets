"""Onglet Tokens du wiki (demande utilisateur 2026-07-31, motivée par la salle
« revue-consommation » : la dépense était constatée après coup, jamais suivie).

Ce que ces tests protègent, au-delà du « le HTML contient un titre » :

  * les axes d'amélioration sont **dérivés des chiffres**, donc ils doivent
    disparaître quand la donnée qui les justifie disparaît. Un axe qui s'afficherait
    quoi qu'il arrive serait un conseil générique déguisé en mesure ;
  * l'onglet ne tombe pas quand `tokens.json` n'existe pas — le script qui le produit
    se lance à la main, donc l'absence est l'état NORMAL d'un projet frais ;
  * le cache relu n'est jamais additionné au facturable (il ne se facture pas au prix
    plein, et il pèse ici 32× le reste : l'additionner rendrait tout le tableau faux).
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

FAUX = {
    "genere": "2026-07-31T15:00:00",
    "fichiers_parcourus": 3,
    "fenetre_jours": None,
    "total": {"input_tokens": 100, "output_tokens": 200,
              "cache_creation_input_tokens": 700, "cache_read_input_tokens": 9000,
              "messages": 42},
    "par_jour": {
        "2026-07-01": {"input_tokens": 10, "output_tokens": 20,
                       "cache_creation_input_tokens": 70, "cache_read_input_tokens": 900},
        "2026-07-02": {"input_tokens": 40, "output_tokens": 80,
                       "cache_creation_input_tokens": 280, "cache_read_input_tokens": 3600},
        "2026-07-03": {"input_tokens": 50, "output_tokens": 100,
                       "cache_creation_input_tokens": 350, "cache_read_input_tokens": 4500},
    },
    "par_modele": {
        "claude-opus-5": {"input_tokens": 80, "output_tokens": 160,
                          "cache_creation_input_tokens": 560, "cache_read_input_tokens": 7000},
        "claude-haiku-4-5": {"input_tokens": 20, "output_tokens": 40,
                             "cache_creation_input_tokens": 140, "cache_read_input_tokens": 2000},
    },
}


class TestAxesDerives:
    def test_aucun_axe_sans_donnee(self):
        """Pas de mesure, pas d'axe — surtout pas une liste de conseils par défaut."""
        assert scan.axes_amelioration_tokens({}) == []

    def test_l_axe_de_cadence_cite_la_date_de_la_mesure(self):
        axes = scan.axes_amelioration_tokens(FAUX)
        cadence = [a for a in axes if "continu" in a[0]]
        assert cadence, [a[0] for a in axes]
        assert "2026-07-31" in cadence[0][1]

    def test_l_axe_du_jour_hors_norme_ne_sort_que_si_l_ecart_est_reel(self):
        """3× la médiane est le seuil. Des journées régulières ne doivent PAS
        déclencher l'axe : sinon il crie en permanence et finit ignoré."""
        regulier = dict(FAUX, par_jour={
            f"2026-07-0{i}": {"input_tokens": 10, "output_tokens": 20,
                              "cache_creation_input_tokens": 70}
            for i in (1, 2, 3)})
        assert not [a for a in scan.axes_amelioration_tokens(regulier) if "pèse" in a[0]]

        hors_norme = dict(FAUX, par_jour={
            "2026-07-01": {"input_tokens": 10, "output_tokens": 20,
                           "cache_creation_input_tokens": 70},
            "2026-07-02": {"input_tokens": 10, "output_tokens": 20,
                           "cache_creation_input_tokens": 70},
            "2026-07-03": {"input_tokens": 1000, "output_tokens": 2000,
                           "cache_creation_input_tokens": 7000},
        })
        pics = [a for a in scan.axes_amelioration_tokens(hors_norme) if "pèse" in a[0]]
        assert pics and "2026-07-03" in pics[0][1]

    def test_l_axe_haiku_ne_sort_que_sous_le_seuil(self):
        """Le seuil est 2 % du facturable. Dans FAUX, haiku pèse 20 % : l'axe ne doit
        PAS sortir — un axe qui s'afficherait aussi quand la pratique est déjà bonne
        ne dirait plus rien."""
        assert not [a for a in scan.axes_amelioration_tokens(FAUX) if "Haiku" in a[0]]

        haiku_neglige = dict(FAUX, par_modele={
            "claude-opus-5": {"input_tokens": 1000, "output_tokens": 1000,
                              "cache_creation_input_tokens": 1000},
            "claude-haiku-4-5": {"input_tokens": 5, "output_tokens": 5,
                                 "cache_creation_input_tokens": 5},
        })
        axes = scan.axes_amelioration_tokens(haiku_neglige)
        assert [a for a in axes if "Haiku" in a[0]], [a[0] for a in axes]

    def test_chaque_axe_porte_un_chiffre(self):
        """Un axe sans mesure derrière est une opinion : son constat doit contenir
        au moins un chiffre."""
        for titre, constat, action in scan.axes_amelioration_tokens(FAUX):
            assert any(c.isdigit() for c in constat), f"axe sans chiffre : {titre}"


class TestRendu:
    def test_absence_de_mesure_ne_casse_pas_la_page(self, monkeypatch, tmp_path):
        monkeypatch.setattr(scan, "TOKENS_JSON", str(tmp_path / "rien.json"))
        h = scan.render_tokens_html()
        assert "mesure_tokens.py" in h  # dit comment produire la donnée
        assert "None" not in h

    def test_le_cache_relu_n_est_jamais_dans_le_facturable(self, monkeypatch, tmp_path):
        """Le cache relu pèse 32× le facturable dans les vraies données : l'additionner
        rendrait chaque barre et chaque total faux."""
        import json
        f = tmp_path / "tokens.json"
        f.write_text(json.dumps(FAUX), encoding="utf-8")
        monkeypatch.setattr(scan, "TOKENS_JSON", str(f))
        h = scan.render_tokens_html()
        assert scan._fr(1000) in h          # facturable = 100+200+700
        assert scan._fr(10000) not in h     # 1000 + 9000 de cache relu : jamais

    def test_les_series_passent_par_les_variables_css(self, monkeypatch, tmp_path):
        """Le mode sombre a ses propres pas de palette (validés pour sa surface) :
        une couleur écrite en dur dans le HTML ne pourrait pas basculer."""
        import json
        f = tmp_path / "tokens.json"
        f.write_text(json.dumps(FAUX), encoding="utf-8")
        monkeypatch.setattr(scan, "TOKENS_JSON", str(f))
        h = scan.render_tokens_html()
        assert "var(--serie-1)" in h
        assert "#2a78d6" not in h

    def test_la_vue_tableau_existe(self, monkeypatch, tmp_path):
        """Exigée par le validateur de palette : un ton passe sous 3:1 de contraste,
        ce qui n'est acceptable qu'avec les valeurs écrites à côté."""
        import json
        f = tmp_path / "tokens.json"
        f.write_text(json.dumps(FAUX), encoding="utf-8")
        monkeypatch.setattr(scan, "TOKENS_JSON", str(f))
        h = scan.render_tokens_html()
        assert "<table" in h and "Cache relu" in h


class TestPageLivree:
    def test_l_onglet_et_sa_pane_sont_declares(self):
        page = os.path.join(HUB, "docs", "wiki.html")
        with open(page, encoding="utf-8") as fh:
            h = fh.read()
        assert 'id="tab-tokens"' in h and 'id="pane-tokens"' in h
        assert 'aria-controls="pane-tokens"' in h
