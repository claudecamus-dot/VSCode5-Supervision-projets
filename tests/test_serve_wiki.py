"""Test fonctionnel réel de serve_wiki.py — requêtes HTTP effectives contre le
serveur, pas une lecture de code. Comble le finding pratique-test du diagnostic
agent-supervisor (2026-07-24) : le hub avait un vrai site web (wiki, serve_wiki.py,
PDF) vérifié uniquement par des harnais Edge headless ad hoc en session, jamais
capturés en test permanent.

Isolation : port EFFÉMÈRE (0 → l'OS en choisit un libre) — jamais 8765, jamais de
collision avec une instance réelle déjà lancée. AGENT_SUPERVISION_ARBITRAGES et
AGENT_SUPERVISION_SKIP_SCAN pointent vers un fichier jetable — l'action "refuser"
(seule action déterministe qui écrit) n'écrit jamais le vrai arbitrages.json.
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


def _load_serve_wiki():
    spec = importlib.util.spec_from_file_location("serve_wiki_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def serveur(tmp_path_factory):
    """Démarre le VRAI serveur (ThreadingHTTPServer + Handler de serve_wiki.py) sur
    un port éphémère, dans un thread ; l'arrête proprement en fin de module."""
    tmp = tmp_path_factory.mktemp("serve_wiki_arbitrages")
    os.environ["AGENT_SUPERVISION_ARBITRAGES"] = str(tmp / "arbitrages.json")
    os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
    mod = _load_serve_wiki()
    srv = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    # attend que le serveur réponde réellement (pas juste que le thread ait démarré)
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)
    else:
        pytest.fail("serveur de test jamais monté")
    yield base
    srv.shutdown()
    thread.join(timeout=5)
    os.environ.pop("AGENT_SUPERVISION_ARBITRAGES", None)
    os.environ.pop("AGENT_SUPERVISION_SKIP_SCAN", None)


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, None


def _get_raw(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def _post(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


class TestServeWikiHTTP:
    def test_ping(self, serveur):
        status, body = _get(serveur, "/api/ping")
        assert status == 200
        assert body == {"ok": True}

    def test_wiki_html_servi(self, serveur):
        status, ctype, body = _get_raw(serveur, "/")
        assert status == 200
        assert "html" in ctype
        assert b"Supervision multi-projets" in body

    def test_jobs_liste_toujours_valide(self, serveur):
        status, body = _get(serveur, "/api/jobs")
        assert status == 200
        assert isinstance(body.get("jobs"), list)

    def test_action_inconnue_rejetee(self, serveur):
        status, body = _post(serveur, "/api/run/n-importe-quoi", {})
        assert status == 400
        assert body["erreur"] == "action inconnue : n-importe-quoi"

    def test_remediation_sans_cible_rejetee(self, serveur):
        status, body = _post(serveur, "/api/run/remediation", {})
        assert status == 400
        assert body["erreur"] == "paramètre invalide"

    def test_action_deterministe_reelle_sync_check(self, serveur):
        """sync-check est réel (py .claude/dispositif/sync_dispositif.py --check),
        lecture seule sur le dépôt courant — 0 token, rapide, sans effet de bord."""
        status, body = _post(serveur, "/api/run/sync-check", {})
        assert status == 202
        job_id = body["job"]
        for _ in range(100):
            _, jobs_body = _get(serveur, "/api/jobs")
            job = next((j for j in jobs_body["jobs"] if j["id"] == job_id), None)
            if job and job["status"] != "en cours":
                break
            time.sleep(0.1)
        else:
            pytest.fail("le job sync-check n'a jamais terminé")
        assert job["status"] == "ok", job["tail"]
        assert job["action"] == "sync-check"

    def test_refuser_ecrit_reellement_et_regenere_pas_le_vrai_wiki(self, serveur):
        """Action déterministe (0 token, pas de claude -p) : preuve la plus simple
        et la plus rapide qu'une action du serveur produit un effet réel observable."""
        cible = "test-serve-wiki-refuser-isole"
        status, body = _post(serveur, "/api/run/refuser", {"cible": cible})
        assert status == 202
        job_id = body["job"]
        for _ in range(50):
            _, jobs_body = _get(serveur, "/api/jobs")
            job = next((j for j in jobs_body["jobs"] if j["id"] == job_id), None)
            if job and job["status"] != "en cours":
                break
            time.sleep(0.05)
        else:
            pytest.fail("le job refuser n'a jamais terminé")
        assert job["status"] == "ok", job["tail"]
        arb_path = os.environ["AGENT_SUPERVISION_ARBITRAGES"]
        data = json.load(open(arb_path, encoding="utf-8"))
        assert any(a["cible"] == cible for a in data["arbitrages"])

    def test_anti_doublon_409_sur_deux_refus_identiques_concurrents(self, serveur):
        """Régression du bug rapporté 2026-07-24 : deux requêtes identiques
        (même action + même cible) pendant qu'une tourne encore -> la seconde est
        refusée (409), pas mise en file silencieusement."""
        cible = "test-serve-wiki-anti-doublon"
        resultats = {}

        def poster(idx):
            resultats[idx] = _post(serveur, "/api/run/refuser", {"cible": cible})

        t1 = threading.Thread(target=poster, args=(0,))
        t2 = threading.Thread(target=poster, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        statuses = sorted(r[0] for r in resultats.values())
        assert statuses == [202, 409]
        rejet = next(r for r in resultats.values() if r[0] == 409)
        assert rejet[1]["erreur"] == "deja_en_cours"

    def test_statique_hors_docs_refuse(self, serveur):
        """Le serveur ne doit servir que sous docs/ — pas une évasion de chemin."""
        status, _ = _get(serveur, "/../CLAUDE.md")
        assert status in (400, 404)

    def test_content_length_malforme_donne_400_pas_500(self, serveur):
        """Finding robustesse audit 2026-07-24 : un Content-Length non numérique
        levait ValueError -> 500 ; doit être un 400 propre."""
        import http.client
        host = serveur.replace("http://", "")
        h, p = host.split(":")
        conn = http.client.HTTPConnection(h, int(p), timeout=10)
        conn.putrequest("POST", "/api/run/sync-check")
        conn.putheader("Content-Length", "abc")
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        conn.send(b"{}")
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

    def test_corps_trop_volumineux_refuse(self, serveur):
        """Finding sécurité/robustesse : corps POST borné (64 Kio)."""
        status, body = _post(serveur, "/api/run/sync-check",
                             {"bourrage": "x" * 70000})
        assert status == 400
        assert body["erreur"] == "corps trop volumineux"
