"""Les deux compteurs d'usage réel du site : pages SERVIES vs actions LANCÉES.

Pourquoi ils existent (salle `atelier-idees`, 2026-08-31). Le journal `jobs.jsonl`
montre **zéro clic humain en un mois** — 242 entrées dont 109 `test`, 70 `refuser` sur
des cibles de test, 62 `sync-check`, et 1 seule `party` qui était elle-même une
vérification de câblage. Mais ce zéro admet trois lectures incompatibles, qui commandent
trois refontes contraires :

- **introuvable** — la page s'ouvre, les boutons ne se trouvent pas au bon moment ;
- **inutile** — la page s'ouvre, les boutons ne servent à rien ;
- **mauvais canal** — la page ne s'ouvre pas du tout, et ce qu'on écrirait en tête
  n'aurait aucune importance.

Le dispositif ne pouvait pas les départager : `serve_wiki.py` ne journalisait QUE les
actions lancées, jamais les pages servies (`log_message` est un journal console, rien
n'en survit sur disque). Un seul compteur ne distingue pas « jamais ouvert » de
« ouvert, jamais cliqué ». Deux compteurs, oui.

L'invariant le plus important gardé ici n'est pas qu'on compte, c'est **ce qu'on ne
compte pas**. La page interroge `/api/jobs` en boucle toutes les 500 ms : compter tous
les GET noierait une poignée d'ouvertures humaines sous des milliers de sondages
automatiques, et produirait un compteur pire qu'aucun compteur — un chiffre qui a l'air
d'une mesure. Même raison pour l'isolation en test : `jobs.jsonl` avait 241 de ses 242
entrées produites par la suite elle-même, et une étude d'usage a failli conclure
l'inverse de la vérité en le lisant.
"""

import importlib.util
import json
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, "scripts", "serve_wiki.py")


@pytest.fixture()
def serveur(tmp_path):
    """VRAI serveur sur port éphémère, avec un journal de vues jetable.

    Le journal est posé dans l'environnement AVANT le chargement du module : comme
    `JOBS_JOURNAL`, le chemin est figé au niveau module, une fois pour toutes.
    """
    vues = tmp_path / "vues.jsonl"
    os.environ["AGENT_SUPERVISION_VUES_JOURNAL"] = str(vues)
    os.environ["AGENT_SUPERVISION_JOBS_JOURNAL"] = str(tmp_path / "jobs.jsonl")
    os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
    spec = importlib.util.spec_from_file_location("serve_wiki_compteurs", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    srv = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)
    else:
        pytest.fail("serveur de test jamais monte")
    yield base, vues, mod
    srv.shutdown()
    th.join(timeout=5)
    os.environ.pop("AGENT_SUPERVISION_VUES_JOURNAL", None)


def _lignes(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


class TestCeQuiEstCompte:
    def test_une_page_servie_laisse_une_ligne(self, serveur):
        base, vues, _mod = serveur
        assert _lignes(vues) == []
        assert _get(base, "/") == 200
        lignes = _lignes(vues)
        assert len(lignes) == 1, "une ouverture de page doit etre journalisee"
        assert lignes[0].get("chemin") == "/"
        assert lignes[0].get("ts")

    def test_les_quatre_routes_de_la_page_comptent(self, serveur):
        """`/`, `/index.html`, `/wiki`, `/wiki.html` servent la meme page."""
        base, vues, _mod = serveur
        for route in ("/", "/index.html", "/wiki", "/wiki.html"):
            assert _get(base, route) == 200
        assert len(_lignes(vues)) == 4


class TestCeQuiNEstPasCompte:
    def test_le_polling_de_l_api_ne_compte_pas(self, serveur):
        """LE test qui compte. La page sonde /api/jobs toutes les 500 ms.

        Comptees, ces requetes noieraient une poignee d'ouvertures humaines sous des
        milliers de sondages : le compteur aurait l'air d'une mesure sans en etre une.
        """
        base, vues, _mod = serveur
        for _ in range(12):
            _get(base, "/api/jobs")
            _get(base, "/api/ping")
        assert _lignes(vues) == [], "le sondage automatique ne doit jamais compter"

    def test_le_statique_ne_compte_pas(self, serveur):
        base, vues, _mod = serveur
        _get(base, "/docs/wiki/index.md")
        _get(base, "/introuvable-404")
        assert _lignes(vues) == []

    def test_le_journal_de_production_n_est_jamais_touche(self, serveur):
        """Meme lecon que jobs.jsonl : 241 de ses 242 entrees venaient de la suite."""
        _base, vues, mod = serveur
        assert mod.VUES_JOURNAL == str(vues)
        assert ".claude" not in mod.VUES_JOURNAL


class TestFailOpen:
    def test_un_journal_inecrivable_ne_casse_pas_la_page(self, tmp_path):
        """Mesurer l'usage ne doit jamais empecher l'usage.

        Le parent du journal est un FICHIER : `makedirs` echouera. La page doit
        continuer a repondre 200 — un compteur casse degrade la mesure, pas le site.
        """
        obstacle = tmp_path / "obstacle"
        obstacle.write_text("je ne suis pas un repertoire", encoding="utf-8")
        os.environ["AGENT_SUPERVISION_VUES_JOURNAL"] = str(obstacle / "sous" / "vues.jsonl")
        os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
        try:
            spec = importlib.util.spec_from_file_location("serve_wiki_failopen", SCRIPT)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            srv = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                for _ in range(50):
                    try:
                        urllib.request.urlopen(base + "/api/ping", timeout=1)
                        break
                    except (urllib.error.URLError, ConnectionError):
                        time.sleep(0.05)
                assert _get(base, "/") == 200
            finally:
                srv.shutdown()
                th.join(timeout=5)
        finally:
            os.environ.pop("AGENT_SUPERVISION_VUES_JOURNAL", None)


class TestLectureEtRendu:
    """Un compteur qu'on ne peut pas lire n'est pas pose, il est enterre."""

    def _scan(self):
        spec = importlib.util.spec_from_file_location(
            "scan_projets_compteurs", os.path.join(HUB, "scripts", "scan_projets.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_lire_vues_compte_et_date(self, tmp_path, monkeypatch):
        scan = self._scan()
        j = tmp_path / "vues.jsonl"
        j.write_text(
            '{"ts": "2026-08-01T09:00:00+02:00", "chemin": "/"}\n'
            '{"ts": "2026-08-15T09:00:00+02:00", "chemin": "/wiki"}\n'
            '\n'
            '{"ts": "2026-08-31T09:00:00+02:00", "chemin": "/"}\n',
            encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(j))
        vues = scan.lire_vues()
        assert vues["n"] == 3
        assert vues["premiere"].startswith("2026-08-01")
        assert vues["derniere"].startswith("2026-08-31")

    def test_lire_vues_sur_journal_absent_ne_leve_pas(self, tmp_path, monkeypatch):
        scan = self._scan()
        monkeypatch.setattr(scan, "VUES_PATH", str(tmp_path / "jamais-ecrit.jsonl"))
        assert scan.lire_vues()["n"] == 0

    def test_le_rendu_montre_les_deux_compteurs(self, tmp_path, monkeypatch):
        """Les deux, cote a cote : un seul ne departage rien."""
        scan = self._scan()
        v = tmp_path / "vues.jsonl"
        v.write_text('{"ts": "2026-08-31T09:00:00+02:00", "chemin": "/"}\n', encoding="utf-8")
        j = tmp_path / "jobs.jsonl"
        j.write_text('{"ts": "2026-08-31T09:05:00+02:00", "action": "scan"}\n', encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(v))
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        html = scan.render_usage_reel_html()
        assert "servie" in html.lower() and "lanc" in html.lower()
        assert ">1<" in html or " 1 " in html

    def test_le_rendu_dit_ce_que_zero_page_servie_signifie(self, tmp_path, monkeypatch):
        """Zero page servie ET zero action = « mauvais canal », pas « boutons inutiles ».

        C'est la lecture que la salle n'a PAS pu faire faute de compteur ; si le rendu
        ne la nomme pas, on aura remis un chiffre sans remettre la question.

        ATTENTION au prealable, ajoute le 2026-08-31 avec la reparation de l'instrument :
        cette lecture n'est autorisee que si la periode est REELLEMENT OBSERVEE, donc si
        le journal porte un marqueur de demarrage. Sans marqueur, le rendu doit dire
        « periode non observee » et surtout PAS « mauvais canal » — un zero non observe
        ne se lit pas. D'ou le marqueur pose ici.
        """
        scan = self._scan()
        v = tmp_path / "vide-v.jsonl"
        v.write_text('{"ts": "2026-08-31T09:00:00+02:00", "event": "demarrage", "version": 1}\n',
                     encoding="utf-8")
        j = tmp_path / "vide-j.jsonl"
        j.write_text('{"ts": "2026-08-31T09:00:00+02:00", "event": "demarrage", "version": 1}\n',
                     encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(v))
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        html = scan.render_usage_reel_html().lower()
        assert "canal" in html
