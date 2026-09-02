"""L'onglet Tokens disait « sur tout l'historique disponible » — et « disponible » rétrécit.

Demande utilisateur du 2026-09-02 (« les informations du site web ne semblent pas à jour »),
arbitrage « publier avec la fenêtre affichée ».

CE QUI ÉTAIT CASSÉ, EN DEUX TEMPS.

**Le gel.** `tokens.json` datait du 2026-07-31 15:17 — 33 jours. Le scan régénère tout le
reste de la page à chaque passage, mais pas celui-là : le code le disait lui-même dans son
propre axe d'amélioration, « le compte en tokens n'existe que si quelqu'un lance
scripts/mesure_tokens.py à la main ». La page a donc affiché son propre diagnostic de
péremption pendant un mois sans que rien ne le lise.

**Le piège, et c'est le plus grave des deux.** Rafraîchir naïvement fait CHUTER le chiffre
de 72 %, et un lecteur y verrait une consommation maîtrisée. Mesuré le 2026-09-02 :

| | 2026-07-31 | 2026-09-02 |
| --- | --- | --- |
| fichiers lus | 124 | 10 |
| jours couverts | 8 | 4 |
| messages | 11 012 | 4 161 |
| facturable | 81 912 714 | 22 834 824 |

`mesure_tokens.py` agrège `~/.claude/projects/<projet>/*.jsonl` — le **cache éphémère des
transcripts**, que Claude Code purge. La base est passée de 124 à 10 fichiers. Le total
n'est donc pas cumulatif : il dépend de ce qui reste sur le disque au moment où on mesure.
La légende « sur tout l'historique disponible » était vraie au mot près et trompeuse en
pratique, parce qu'elle laissait croire à un historique quand elle décrivait un reste.

CE QUE CES TESTS VERROUILLENT : que la page dise sur QUOI elle compte (fichiers ET jours),
qu'elle avertisse que cette base rétrécit — donc qu'une baisse n'est pas une économie — et
que le scan relance la mesure au lieu d'attendre une commande manuelle.
"""

import importlib.util
import io
import json
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets_fenetre", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

MESURE = {
    "genere": "2026-09-02T10:41:21+02:00",
    "fichiers_parcourus": 10,
    "fenetre_jours": None,
    "total": {"input_tokens": 8306, "output_tokens": 5724696,
              "cache_creation_input_tokens": 17101822,
              "cache_read_input_tokens": 1462674799, "messages": 4161},
    "par_jour": {"2026-08-30": {"input_tokens": 1, "output_tokens": 1,
                                "cache_creation_input_tokens": 1},
                 "2026-08-31": {"input_tokens": 1, "output_tokens": 1,
                                "cache_creation_input_tokens": 1},
                 "2026-09-01": {"input_tokens": 1, "output_tokens": 1,
                                "cache_creation_input_tokens": 1},
                 "2026-09-02": {"input_tokens": 1, "output_tokens": 1,
                                "cache_creation_input_tokens": 1}},
    "par_modele": {"opus": {"input_tokens": 1, "output_tokens": 1,
                            "cache_creation_input_tokens": 1}},
}


def _html(monkeypatch, mesure=MESURE):
    monkeypatch.setattr(scan, "lire_tokens", lambda: mesure)
    return scan.render_tokens_html()


class TestLaPageDitSurQuoiElleCompte:
    def test_le_nombre_de_JOURS_couverts_est_affiche(self, monkeypatch):
        """Les fichiers lus étaient déjà affichés ; les jours, non. Or c'est le nombre
        de jours qui dit si un total est comparable à celui du mois dernier."""
        h = _html(monkeypatch)
        assert "4 jour" in h or "4 j " in h or "4 j)" in h, (
            "la page ne dit pas sur combien de jours porte le total")

    def test_la_formule_trompeuse_a_disparu(self, monkeypatch):
        h = _html(monkeypatch)
        assert "sur tout l'historique disponible" not in h, (
            "« tout l'historique disponible » laisse croire à un cumul là où la base "
            "rétrécit à chaque purge de transcripts")

    def test_la_page_avertit_que_la_base_retrecit(self, monkeypatch):
        """Sans cet avertissement, une chute du total se lit comme une économie. C'est
        exactement ce qui serait arrivé le 2026-09-02 : -72 % sans qu'aucune consommation
        ait baissé."""
        h = _html(monkeypatch).lower()
        assert "purge" in h or "rétréci" in h or "retreci" in h or "éphémère" in h, (
            "rien n'avertit que le total dépend de ce qui reste sur le disque")

    def test_une_baisse_ne_peut_pas_etre_lue_comme_une_economie(self, monkeypatch):
        """Le garde-fou porte sur la PROPRIÉTÉ, pas sur un mot : la légende doit
        contenir à la fois la taille de la base et la mise en garde, sinon l'une sans
        l'autre laisse le lecteur conclure de travers."""
        h = _html(monkeypatch)
        assert "10" in h, "le nombre de fichiers lus n'apparaît plus"
        bas = h.lower()
        assert any(m in bas for m in ("purge", "rétréci", "retreci", "éphémère")), bas[:400]


class TestLeScanRelanceLaMesure:
    """Le gel venait d'une cadence absente, pas d'un bug : personne ne lançait le script."""

    def test_la_fonction_de_rafraichissement_existe(self):
        assert hasattr(scan, "rafraichir_tokens"), (
            "aucune fonction de rafraîchissement : la mesure reste suspendue à une "
            "commande manuelle, et c'est ce qui l'a gelée 33 jours")

    def test_elle_reecrit_le_fichier(self, tmp_path, monkeypatch):
        cible = tmp_path / "tokens.json"
        io.open(cible, "w", encoding="utf-8").write(json.dumps({"genere": "2026-07-31"}))
        monkeypatch.setattr(scan, "TOKENS_JSON", str(cible))
        scan.rafraichir_tokens()
        d = json.loads(io.open(cible, encoding="utf-8").read())
        assert d.get("genere", "").startswith("2026-09") or d.get("total"), (
            "le fichier n'a pas été réécrit par la mesure")

    def test_fail_open_si_la_mesure_echoue(self, tmp_path, monkeypatch):
        """Le scan tourne dans un hook SessionStart : une mesure qui lève bloquerait
        l'ouverture de session. Elle doit renoncer en silence, pas casser le scan."""
        monkeypatch.setattr(scan, "MESURE_TOKENS_SCRIPT",
                            str(tmp_path / "script-qui-nexiste-pas.py"))
        scan.rafraichir_tokens()   # ne doit pas lever
