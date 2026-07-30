"""Verrou de la mesure de tokens (scripts/mesure_tokens.py, 2026-07-30).

L'étude de consommation a buté sur un mur : 159 invocations comptées, **zéro donnée en
tokens**. Toute économie se serait arbitrée sur des proxys. Ce script lit les compteurs
`usage` que les transcripts portent déjà.

Les deux invariants qui comptent ici :
  1. il n'agrège QUE des entiers — jamais un contenu de message (les transcripts
     contiennent du contenu d'interviews clients) ;
  2. il ne plante sur rien : un transcript tronqué, une ligne corrompue, un dossier
     absent ne doivent pas faire échouer une mesure lancée à la demande.
"""

import importlib.util
import json
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "mesure_tokens", os.path.join(HUB, "scripts", "mesure_tokens.py"))
mt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mt)


def _ligne(jour, modele="claude-opus-5", entree=10, sortie=20, cw=30, cr=40, texte=None):
    msg = {"model": modele, "usage": {
        "input_tokens": entree, "output_tokens": sortie,
        "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr}}
    if texte:
        msg["content"] = [{"type": "text", "text": texte}]
    return json.dumps({"type": "assistant", "timestamp": f"{jour}T10:00:00Z",
                       "message": msg}, ensure_ascii=False)


def _transcript(dossier, nom, lignes):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / nom).write_text("\n".join(lignes) + "\n", encoding="utf-8")


class TestAgregation:
    def test_somme_les_quatre_compteurs(self, tmp_path):
        _transcript(tmp_path, "a.jsonl", [_ligne("2026-07-30"), _ligne("2026-07-30")])
        t = mt.agreger(str(tmp_path))["total"]
        assert t == {"input_tokens": 20, "output_tokens": 40,
                     "cache_creation_input_tokens": 60,
                     "cache_read_input_tokens": 80, "messages": 2}

    def test_ventile_par_jour_et_par_modele(self, tmp_path):
        _transcript(tmp_path, "a.jsonl", [
            _ligne("2026-07-29", modele="claude-opus-5", sortie=100),
            _ligne("2026-07-30", modele="claude-sonnet-5", sortie=5),
        ])
        d = mt.agreger(str(tmp_path))
        assert d["par_jour"]["2026-07-29"]["output_tokens"] == 100
        assert d["par_jour"]["2026-07-30"]["output_tokens"] == 5
        # par_modele est trié du plus gros consommateur de sortie au plus petit
        assert list(d["par_modele"]) == ["claude-opus-5", "claude-sonnet-5"]

    def test_plusieurs_transcripts_cumules(self, tmp_path):
        _transcript(tmp_path, "a.jsonl", [_ligne("2026-07-30")])
        _transcript(tmp_path, "b.jsonl", [_ligne("2026-07-30")])
        d = mt.agreger(str(tmp_path))
        assert d["fichiers_parcourus"] == 2
        assert d["total"]["messages"] == 2

    def test_fenetre_en_jours(self, tmp_path):
        import datetime as dt
        _transcript(tmp_path, "a.jsonl", [
            _ligne("2026-07-01", sortie=999), _ligne("2026-07-30", sortie=7)])
        now = dt.datetime(2026, 7, 30, tzinfo=dt.UTC)
        d = mt.agreger(str(tmp_path), jours=3, now=now)
        assert d["total"]["output_tokens"] == 7        # le vieux message est écarté
        assert "2026-07-01" not in d["par_jour"]


class TestRobustesse:
    def test_lignes_sans_usage_ignorees(self, tmp_path):
        _transcript(tmp_path, "a.jsonl", [
            json.dumps({"type": "user", "message": {"content": "bonjour"}}),
            _ligne("2026-07-30"),
        ])
        assert mt.agreger(str(tmp_path))["total"]["messages"] == 1

    def test_ligne_corrompue_ne_plante_pas(self, tmp_path):
        _transcript(tmp_path, "a.jsonl",
                    ['{"usage": tronqu', _ligne("2026-07-30")])
        assert mt.agreger(str(tmp_path))["total"]["messages"] == 1

    def test_usage_non_dict_ignore(self, tmp_path):
        _transcript(tmp_path, "a.jsonl", [
            json.dumps({"type": "assistant", "message": {"usage": "n/a"}}),
            _ligne("2026-07-30"),
        ])
        assert mt.agreger(str(tmp_path))["total"]["messages"] == 1

    def test_dossier_absent_rend_un_agregat_vide(self, tmp_path):
        d = mt.agreger(str(tmp_path / "nulle-part"))
        assert d["fichiers_parcourus"] == 0
        assert d["total"]["messages"] == 0


class TestConfidentialite:
    def test_aucun_contenu_de_message_dans_la_sortie(self, tmp_path):
        """L'invariant non négociable : les transcripts contiennent du contenu
        d'interviews clients. La mesure ne retient que des entiers et des dates."""
        secret = "PROPOS-CONFIDENTIEL-DU-CLIENT"
        _transcript(tmp_path, "a.jsonl", [_ligne("2026-07-30", texte=secret)])
        rendu = json.dumps(mt.agreger(str(tmp_path)), ensure_ascii=False)
        assert secret not in rendu
        # et rien qui ressemble à du texte libre : seules des valeurs numériques
        for bloc in ("total", "par_jour", "par_modele"):
            valeurs = mt.agreger(str(tmp_path))[bloc]
            plates = valeurs.values() if bloc == "total" else [
                v for sous in valeurs.values() for v in sous.values()]
            assert all(isinstance(v, int) for v in plates), bloc


class TestDossierTranscripts:
    def test_slug_derive_comme_le_canon(self, tmp_path):
        """Le premier jet dérivait le slug à la main et tombait à côté : Claude Code
        remplace TOUT caractère non alphanumérique par un tiret (le point de
        « claude.camus » compris), et la casse du lecteur peut différer."""
        assert mt.dossier_transcripts(r"c:\Users\jean.dupont\Documents\Mon Projet").endswith(
            "c--Users-jean-dupont-Documents-Mon-Projet")

    def test_le_dossier_reel_du_hub_existe(self):
        """Garde-fou anti-régression silencieuse : si la dérivation casse, la mesure
        rendrait 0 token sans erreur — un zéro qu'on croirait vrai."""
        assert os.path.isdir(mt.TRANSCRIPTS), mt.TRANSCRIPTS
