"""L'instrument doit dire quand il regardait, et ce qu'il a refusé.

Pourquoi ce fichier existe (étape 1 arbitrée le 2026-08-31, après le tour 3 de la salle
`atelier-idees`). Le compte rendu affirmait « zéro clic humain en un mois ». Le
croisement de `jobs.jsonl` avec `runs.jsonl` l'a démenti sur deux points :

1. le journal n'a observé que **26 heures** (30/07 18:09 → 31/07 20:11), pas un mois ;
2. une pression réelle du bouton « Valider », datée du **30/07 18:38** par `runs.jsonl`,
   tombe DANS cette fenêtre et n'a laissé **aucune trace** — alors que la journalisation
   était déployée depuis 18:12:50 (commit `d9ed306`).

Trois chemins d'oubli SILENCIEUX ont été trouvés dans `do_POST`, et un quatrième,
structurel :

- `if not argv: return 400 « paramètre invalide »` — c'est le cas quand `CLAUDE_BIN` est
  introuvable : la personne clique, le serveur refuse, le journal ne dit rien ;
- `action inconnue` → 400, rien ;
- doublon détecté → 409, rien : « la personne a essayé deux fois » est invisible ;
- et un serveur lancé AVANT le déploiement de la journalisation ne journalise jamais,
  sans que rien ne distingue cette cécité d'un vrai silence.

L'invariant gardé ici est le seul qui rende un compteur d'usage lisible : **un zéro ne
vaut que rapporté à une fenêtre d'observation déclarée**. Un journal qui ne dit pas
quand il regardait ne permet pas de distinguer « personne n'a cliqué » de « personne ne
regardait ».
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


def _lignes(chemin):
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _charger(tmp_path):
    """Module serve_wiki avec ses deux journaux détournés vers tmp_path."""
    os.environ["AGENT_SUPERVISION_JOBS_JOURNAL"] = str(tmp_path / "jobs.jsonl")
    os.environ["AGENT_SUPERVISION_VUES_JOURNAL"] = str(tmp_path / "vues.jsonl")
    os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
    spec = importlib.util.spec_from_file_location("serve_wiki_instrument", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def serveur(tmp_path):
    mod = _charger(tmp_path)
    srv = mod.ServeurJournalise(("127.0.0.1", 0), mod.Handler)
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
    yield base, tmp_path, mod
    srv.shutdown()
    th.join(timeout=5)


def _post(base, action, payload):
    corps = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + "/api/run/" + action, data=corps,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


class TestLeRefusLaisseUneTrace:
    """« La personne a cliqué et rien ne s'est passé » doit être VISIBLE.

    C'est l'information exacte qui manquait : un clic refusé était indiscernable d'un
    clic jamais fait.
    """

    def test_un_parametre_invalide_est_journalise(self, serveur):
        base, tmp, _mod = serveur
        avant = len(_lignes(tmp / "jobs.jsonl"))
        assert _post(base, "valider", {}) == 400
        lignes = _lignes(tmp / "jobs.jsonl")
        assert len(lignes) == avant + 1, "un refus doit laisser une ligne"
        refus = lignes[-1]
        assert refus["action"] == "valider"
        assert refus.get("lance") is False
        assert "refus" in (refus.get("statut") or "")

    def test_une_action_inconnue_est_journalisee(self, serveur):
        base, tmp, _mod = serveur
        avant = len(_lignes(tmp / "jobs.jsonl"))
        assert _post(base, "action-qui-nexiste-pas", {"cible": "x"}) == 400
        lignes = _lignes(tmp / "jobs.jsonl")
        assert len(lignes) == avant + 1
        assert lignes[-1].get("lance") is False

    def test_le_refus_ne_pretend_pas_avoir_lance(self, serveur):
        """Une ligne de refus ne doit pas etre comptee comme une action reussie."""
        base, tmp, _mod = serveur
        _post(base, "valider", {})
        refus = _lignes(tmp / "jobs.jsonl")[-1]
        assert refus.get("statut") != "ok"
        assert refus.get("duree_s") in (None, 0, 0.0)


class TestLeJournalDitQuandIlRegardait:
    def test_le_demarrage_ecrit_un_marqueur_dans_les_deux_journaux(self, serveur):
        _base, tmp, _mod = serveur
        for nom in ("jobs.jsonl", "vues.jsonl"):
            lignes = _lignes(tmp / nom)
            demarrages = [l for l in lignes if l.get("event") == "demarrage"]
            assert len(demarrages) == 1, f"{nom} doit porter un marqueur de demarrage"
            assert demarrages[0].get("ts")

    def test_le_marqueur_porte_la_version_du_format(self, serveur):
        """Sans version, une ligne ancienne et une ligne neuve sont indiscernables."""
        _base, tmp, _mod = serveur
        d = [l for l in _lignes(tmp / "jobs.jsonl") if l.get("event") == "demarrage"][0]
        assert isinstance(d.get("version"), int) and d["version"] >= 1

    def test_le_marqueur_n_est_pas_compte_comme_une_action(self, serveur):
        base, tmp, _mod = serveur
        _post(base, "valider", {})
        lignes = _lignes(tmp / "jobs.jsonl")
        actions = [l for l in lignes if not l.get("event")]
        assert len(actions) == 1, "seul le refus est une action, pas le demarrage"


class TestLaLectureRapporteLeZeroAUneFenetre:
    def _scan(self):
        spec = importlib.util.spec_from_file_location(
            "scan_projets_instrument", os.path.join(HUB, "scripts", "scan_projets.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_le_marqueur_n_est_compte_ni_en_vue_ni_en_action(self, tmp_path, monkeypatch):
        scan = self._scan()
        j = tmp_path / "vues.jsonl"
        j.write_text(
            '{"ts": "2026-08-31T09:00:00+02:00", "event": "demarrage", "version": 1}\n'
            '{"ts": "2026-08-31T09:01:00+02:00", "chemin": "/"}\n', encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(j))
        assert scan.lire_vues()["n"] == 1, "le demarrage n'est pas une ouverture de page"

    def test_les_fenetres_observees_sont_derivees_des_marqueurs(self, tmp_path, monkeypatch):
        scan = self._scan()
        j = tmp_path / "jobs.jsonl"
        j.write_text(
            '{"ts": "2026-08-01T09:00:00+02:00", "event": "demarrage", "version": 1}\n'
            '{"ts": "2026-08-01T11:00:00+02:00", "action": "scan", "statut": "ok"}\n'
            '{"ts": "2026-08-20T09:00:00+02:00", "event": "demarrage", "version": 1}\n',
            encoding="utf-8")
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        f = scan.fenetres_observees()
        assert f["sessions"] == 2
        assert f["premiere"].startswith("2026-08-01")
        assert f["derniere"].startswith("2026-08-20")

    def test_sans_marqueur_la_fenetre_est_INCONNUE_pas_zero(self, tmp_path, monkeypatch):
        """Le defaut d'origine : un journal muet passait pour un silence mesure.

        C'est exactement l'etat de jobs.jsonl au 2026-08-31 — 242 entrees, aucun
        marqueur, donc aucune fenetre d'observation declaree.
        """
        scan = self._scan()
        j = tmp_path / "jobs.jsonl"
        j.write_text('{"ts": "2026-07-30T18:09:57+02:00", "action": "sync-check"}\n',
                     encoding="utf-8")
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        assert scan.fenetres_observees()["sessions"] == 0

    def test_le_rendu_refuse_de_presenter_un_zero_non_observe(self, tmp_path, monkeypatch):
        """Un zero sans fenetre declaree doit etre annonce comme NON MESURE."""
        scan = self._scan()
        v = tmp_path / "vues.jsonl"
        v.write_text("", encoding="utf-8")
        j = tmp_path / "jobs.jsonl"
        j.write_text('{"ts": "2026-07-30T18:09:57+02:00", "action": "sync-check"}\n',
                     encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(v))
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        html = scan.render_usage_reel_html().lower()
        assert "non observ" in html or "pas observ" in html, (
            "sans marqueur, le rendu doit dire que la periode n'est pas observee")

    def test_le_rendu_annonce_la_fenetre_quand_elle_existe(self, tmp_path, monkeypatch):
        scan = self._scan()
        v = tmp_path / "vues.jsonl"
        v.write_text(
            '{"ts": "2026-08-31T09:00:00+02:00", "event": "demarrage", "version": 1}\n'
            '{"ts": "2026-08-31T09:01:00+02:00", "chemin": "/"}\n', encoding="utf-8")
        j = tmp_path / "jobs.jsonl"
        j.write_text(
            '{"ts": "2026-08-31T09:00:00+02:00", "event": "demarrage", "version": 1}\n',
            encoding="utf-8")
        monkeypatch.setattr(scan, "VUES_PATH", str(v))
        monkeypatch.setattr(scan, "JOBS_PATH", str(j))
        html = scan.render_usage_reel_html().lower()
        assert "session" in html and "2026-08-31" in html
