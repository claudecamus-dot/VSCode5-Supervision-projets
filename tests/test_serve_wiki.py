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
import subprocess
import sys
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

    def test_content_length_negatif_refuse_sans_bloquer(self, serveur):
        """Revue fraiche 2026-07-25 sur le fix ci-dessus : Content-Length: -1 passe
        int() (pas de ValueError) ET length > 65536 (faux) -> rfile.read(-1), qui
        lit jusqu'a EOF et peut bloquer le thread indefiniment sur une connexion
        keep-alive. Doit etre rejete en 400 avant le read, avec un timeout court."""
        import http.client
        host = serveur.replace("http://", "")
        h, p = host.split(":")
        conn = http.client.HTTPConnection(h, int(p), timeout=5)
        conn.putrequest("POST", "/api/run/sync-check")
        conn.putheader("Content-Length", "-1")
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


class TestRobustesseJobs:
    """Les 2 findings robustesse ouverts de l'audit du 2026-07-24 : erreurs de job
    indistinctes (« erreur (...) » quelle que soit la cause) et JOBS non borné."""

    def _mod(self):
        os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
        return _load_serve_wiki()

    def test_executable_introuvable_donne_une_erreur_nommee(self):
        mod = self._mod()
        job_id = mod._lancer_job("test", "binaire absent", None,
                                 ["binaire-qui-nexiste-pas-42", "--version"])
        for _ in range(50):
            if mod.JOBS[job_id]["status"] != "en cours":
                break
            time.sleep(0.05)
        statut = mod.JOBS[job_id]["status"]
        assert "introuvable" in statut, statut
        assert "binaire-qui-nexiste-pas-42" in statut, statut

    def test_jobs_purges_au_dela_du_plafond(self):
        mod = self._mod()
        mod.JOBS.clear()
        for i in range(mod.JOBS_MAX + 25):
            mod.JOBS[f"j{i}"] = {"id": f"j{i}", "status": "ok", "action": "x"}
        with mod.JOBS_LOCK:
            mod._purger_jobs()
        assert len(mod.JOBS) == mod.JOBS_MAX
        # Purge par ancienneté : les plus récents survivent.
        assert f"j{mod.JOBS_MAX + 24}" in mod.JOBS
        assert "j0" not in mod.JOBS

    def test_un_job_en_cours_n_est_jamais_purge(self):
        mod = self._mod()
        mod.JOBS.clear()
        mod.JOBS["vivant"] = {"id": "vivant", "status": "en cours", "action": "x"}
        for i in range(mod.JOBS_MAX + 10):
            mod.JOBS[f"j{i}"] = {"id": f"j{i}", "status": "ok", "action": "x"}
        with mod.JOBS_LOCK:
            mod._purger_jobs()
        assert "vivant" in mod.JOBS

    def test_sous_le_plafond_rien_n_est_purge(self):
        mod = self._mod()
        mod.JOBS.clear()
        mod.JOBS["a"] = {"id": "a", "status": "ok", "action": "x"}
        with mod.JOBS_LOCK:
            mod._purger_jobs()
        assert list(mod.JOBS) == ["a"]


def _prouver_mort(proc, limite=5.0):
    """Preuve PORTABLE qu'un sous-processus est réellement mort, pas seulement marqué
    « annule ».

    La première version de ces tests sondait `tasklist` (commande Windows-only) :
    la suite passait sur cette machine et échouait sur `ubuntu-latest`, laissant la
    CI rouge de 9552b7e à 63cbd37 (2026-07-30) sur un dispositif pourtant correct.
    `proc.wait()` interroge l'OS des deux côtés (WaitForSingleObject / waitpid) et,
    côté POSIX, récolte le zombie — indispensable : après un `terminate()`, une
    sonde par PID verrait encore le process « vivant » tant qu'il n'est pas récolté.
    C'est aussi une preuve plus forte que l'absence d'une chaîne dans une sortie
    texte : le code de retour prouve la terminaison, un timeout la réfute."""
    try:
        proc.wait(timeout=limite)
    except subprocess.TimeoutExpired:
        pytest.fail(f"le process {proc.pid} tourne encore {limite} s apres l'annulation")
    assert proc.returncode is not None


class TestAnnulationJob:
    """Finding wiki:actions-irreversibles (c), diagnostic 2026-07-30 : aucune route
    d'annulation d'un job long (diagnostic/audit = plusieurs minutes, facturés).
    proc.terminate() seul ne suffit pas sur Windows (le CLI est lancé via un shim
    .cmd -> terminate() ne tuerait que cmd.exe, laissant l'agent réel tourner en
    tâche de fond) — _annuler_job utilise taskkill /F /T (tout l'arbre), et
    proc.terminate() sur les autres plateformes, où il n'y a pas de shim. La preuve
    de mort passe par _prouver_mort (portable) : la sonde `tasklist` d'origine ne
    tournait que sur cette machine."""

    def _mod(self):
        os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
        return _load_serve_wiki()

    def test_annule_un_job_reellement_en_cours(self):
        mod = self._mod()
        job_id = mod._lancer_job("test", "sommeil long", None,
                                 [sys.executable, "-c", "import time; time.sleep(30)"])
        for _ in range(50):
            if mod.JOBS[job_id].get("_proc") is not None:
                break
            time.sleep(0.05)
        else:
            pytest.fail("le sous-processus n'a jamais démarré")
        proc = mod.JOBS[job_id]["_proc"]
        ok, erreur = mod._annuler_job(job_id)
        assert ok and erreur is None
        for _ in range(50):
            if mod.JOBS[job_id]["status"] != "en cours":
                break
            time.sleep(0.1)
        else:
            pytest.fail("le job annulé n'est jamais sorti de 'en cours'")
        assert mod.JOBS[job_id]["status"] == "annule"
        # Le process est réellement mort (pas seulement marqué) : preuve que le kill
        # d'arbre a bien tué le sous-processus, et pas seulement annoncé l'annulation.
        _prouver_mort(proc)

    def test_annule_meme_si_proc_pas_encore_pose(self):
        """Course étroite trouvée en revue fraîche (2026-07-30) : _run_job pose
        "_proc" juste APRÈS le Popen, pas avant. Sans l'attente courte de
        _annuler_job, un job annulé dans cette fenêtre serait marqué "annule"
        sans jamais tuer le sous-processus, qui continuerait à tourner en
        silence malgré l'UI affichant annulé."""
        mod = self._mod()
        job_id = "course-etroite"
        mod.JOBS[job_id] = {"id": job_id, "action": "test", "status": "en cours"}
        proc_holder = {}

        def poser_proc_en_differe():
            time.sleep(0.2)   # simule le délai entre la création du job et le Popen
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            with mod.JOBS_LOCK:
                mod.JOBS[job_id]["_proc"] = p
            proc_holder["proc"] = p

        t = threading.Thread(target=poser_proc_en_differe)
        t.start()
        ok, erreur = mod._annuler_job(job_id)   # appelé AVANT que "_proc" existe
        t.join()
        assert ok and erreur is None
        _prouver_mort(proc_holder["proc"])

    def test_annuler_job_inconnu_rejete(self):
        mod = self._mod()
        ok, erreur = mod._annuler_job("id-qui-nexiste-pas")
        assert not ok
        assert erreur == "job introuvable"

    def test_annuler_job_deja_termine_rejete(self):
        mod = self._mod()
        job_id = mod._lancer_job("test", "rapide", None, [sys.executable, "-c", "pass"])
        for _ in range(50):
            if mod.JOBS[job_id]["status"] != "en cours":
                break
            time.sleep(0.05)
        else:
            pytest.fail("le job rapide n'a jamais terminé")
        ok, erreur = mod._annuler_job(job_id)
        assert not ok
        assert erreur == "ce job est deja termine"

    def test_route_cancel_http_job_inconnu(self, serveur):
        status, body = _post(serveur, "/api/cancel/id-qui-nexiste-pas", {})
        assert status == 404
        assert body["erreur"] == "job introuvable"

    def test_api_jobs_ne_serialise_jamais_les_cles_internes(self, serveur):
        status, body = _post(serveur, "/api/run/sync-check", {})
        assert status == 202
        job_id = body["job"]
        _, jobs_body = _get(serveur, "/api/jobs")
        job = next(j for j in jobs_body["jobs"] if j["id"] == job_id)
        assert not any(k.startswith("_") for k in job)


class TestRescanChaineApresEcriture:
    """Demande utilisateur 2026-07-30 : « une action corrective terminée doit mettre à
    jour les infos affichées ».

    Le chaînage n'existait que pour `valider` (2026-07-29) : un `refuser` fermait un
    finding, un `audit` écrivait son verdict, un `diagnostic` écrivait 5 constats — et la
    page continuait d'afficher l'état d'avant jusqu'à ce que quelqu'un clique « Re-scan ».
    Les prompts LLM demandent pourtant à l'agent de régénérer le wiki : c'est une
    déclaration, pas une garantie — le diagnostic du 2026-07-30 a bien écrit
    diagnostic.json et relancé scan_transcripts.py, mais PAS scan_projets.py."""

    def _mod(self):
        os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
        return _load_serve_wiki()

    def _fin_de_job(self, mod, action, status="ok", cible=None):
        """Rejoue la fin d'un job sans lancer de sous-processus : on veut savoir ce que
        le serveur ENCHAÎNE, pas re-tester le lancement."""
        lances = []
        mod.JOBS.clear()
        mod._lancer_job = lambda a, lib, c, argv: (lances.append((a, lib, c)) or "id")
        job = {"id": "x", "action": action, "status": status, "cible": cible}
        if job["status"] == "ok" and job["action"] in mod.ACTIONS_QUI_PERIMENT_LES_MESURES:
            mod._lancer_job("scan-rapide", "libelle", None, ["py"])
        return lances

    @pytest.mark.parametrize("action", [
        "valider", "refuser", "audit", "diagnostic", "veille", "deployer-veille"])
    def test_toute_action_qui_ecrit_enchaine_un_rescan(self, action):
        mod = self._mod()
        assert action in mod.ACTIONS_QUI_PERIMENT_LES_MESURES, action

    @pytest.mark.parametrize("action", [
        "scan", "scan-rapide", "sync-check", "package-check", "pdf", "remediation",
        "reflexion"])
    def test_les_actions_sans_ecriture_n_enchainent_rien(self, action):
        """`scan`/`scan-rapide` en particulier : les inclure ferait une boucle infinie
        (chaque scan relancerait un scan). `remediation` et `reflexion` PROPOSENT un
        texte sans rien écrire de mesuré."""
        mod = self._mod()
        assert action not in mod.ACTIONS_QUI_PERIMENT_LES_MESURES, action

    def test_un_job_en_echec_n_enchaine_pas_de_rescan(self):
        """Re-scanner après un échec afficherait « à jour » sur un état inchangé."""
        mod = self._mod()
        assert self._fin_de_job(mod, "valider", status="echec (1)") == []

    def test_le_rescan_chaine_est_neutralise_par_skip_scan(self, monkeypatch):
        """Sans cette garde, la suite déclenchait un VRAI scan_projets.py en tâche de
        fond (l'action « refuser » est testée pour de bon), qui réécrivait
        docs/wiki.html pendant que d'autres tests le lisaient — rouge par interférence.
        Même convention que refuser_arbitrage.py, qui saute déjà son propre ré-scan."""
        mod = self._mod()
        monkeypatch.setenv("AGENT_SUPERVISION_SKIP_SCAN", "1")
        lances = []
        monkeypatch.setattr(mod, "_lancer_job",
                            lambda a, lib, c, argv: lances.append(a) or "id")
        job = {"id": "x", "action": "refuser", "status": "ok", "cible": "c"}
        if (job["status"] == "ok"
                and job["action"] in mod.ACTIONS_QUI_PERIMENT_LES_MESURES
                and not os.environ.get("AGENT_SUPERVISION_SKIP_SCAN")):
            mod._lancer_job("scan-rapide", "x", None, ["py"])
        assert lances == []

    def test_la_liste_ne_cite_que_des_actions_connues_du_serveur(self):
        """Une faute de frappe dans la liste ne se verrait jamais à l'exécution : elle
        rendrait simplement le chaînage muet pour cette action."""
        mod = self._mod()
        connues = set(mod.ACTIONS) | {
            "remediation", "valider", "refuser", "audit", "deployer-veille", "reflexion"}
        inconnues = [a for a in mod.ACTIONS_QUI_PERIMENT_LES_MESURES if a not in connues]
        assert not inconnues, inconnues


class TestJournalDesJobs:
    """`/api/jobs` n'existait qu'en MÉMOIRE : à l'arrêt du serveur, tout ce qui avait
    été lancé depuis le wiki disparaissait. L'étude de consommation du 2026-07-30 n'a
    donc pas pu distinguer ce que coûtent les boutons de ce que coûte l'interactif.
    Une ligne JSON par job terminé ferme l'angle mort, pour 0 token."""

    def _mod(self, tmp_path, monkeypatch):
        os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"
        mod = _load_serve_wiki()
        monkeypatch.setattr(mod, "JOBS_JOURNAL", str(tmp_path / "jobs.jsonl"))
        return mod

    def _lignes(self, tmp_path):
        p = tmp_path / "jobs.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    def test_un_job_termine_ecrit_une_ligne(self, tmp_path, monkeypatch):
        mod = self._mod(tmp_path, monkeypatch)
        job_id = mod._lancer_job("test", "rapide", "VSCode2",
                                 [sys.executable, "-c", "pass"])
        for _ in range(60):
            if mod.JOBS[job_id]["status"] != "en cours":
                break
            time.sleep(0.05)
        else:
            pytest.fail("le job n'a jamais termine")
        time.sleep(0.15)
        lignes = self._lignes(tmp_path)
        assert len(lignes) == 1, lignes
        assert lignes[0]["action"] == "test"
        assert lignes[0]["cible"] == "VSCode2"
        assert lignes[0]["statut"] == "ok"
        assert lignes[0]["duree_s"] >= 0
        assert lignes[0]["llm"] is False

    def test_la_sortie_de_l_agent_n_est_jamais_journalisee(self, tmp_path, monkeypatch):
        """Le `tail` d'un job LLM peut contenir du contenu client : il ne doit jamais
        atterrir dans un fichier versionné."""
        mod = self._mod(tmp_path, monkeypatch)
        secret = "PROPOS-CONFIDENTIEL"
        job_id = mod._lancer_job("test", "bavard", None,
                                 [sys.executable, "-c", f"print('{secret}')"])
        for _ in range(60):
            if mod.JOBS[job_id]["status"] != "en cours":
                break
            time.sleep(0.05)
        time.sleep(0.15)
        brut = (tmp_path / "jobs.jsonl").read_text(encoding="utf-8")
        assert secret in "".join(mod.JOBS[job_id]["tail"])   # bien capté à l'écran
        assert secret not in brut                            # jamais sur disque

    def test_un_journal_illisible_ne_fait_pas_echouer_le_job(self, tmp_path, monkeypatch):
        """Fail-open : le journal est une commodité, le job est le livrable."""
        mod = self._mod(tmp_path, monkeypatch)
        monkeypatch.setattr(mod, "JOBS_JOURNAL", str(tmp_path / "sans" / "\x00" / "x.jsonl"))
        job = {"action": "a", "cible": None, "status": "ok", "t0": 1.0, "fin_ts": 2.0}
        mod._journaliser_job(job)     # ne doit pas lever


class TestFluxLiveDesJobsLLM:
    """P2 (2026-07-29) : en `--output-format text`, claude -p n'écrit rien avant
    sa toute dernière ligne — le rapport restait VIDE pendant toute la durée du
    job (195 s mesurées sur une remédiation réelle), ce qui se lit comme « c'est
    bloqué ». Ces tests verrouillent la traduction du flux stream-json."""

    def _mod(self):
        return _load_serve_wiki()

    def test_options_de_flux_ajoutees_aux_jobs_llm(self):
        mod = self._mod()
        mod.CLAUDE_BIN = "C:/faux/claude.exe"
        argv = mod._avec_flux([mod.CLAUDE_BIN, "-p", "prompt"])
        assert argv[0] == mod.CLAUDE_BIN
        assert "--output-format" in argv and "stream-json" in argv
        # -p et son prompt restent en DERNIER, sinon le CLI lit le prompt de travers
        assert argv[-2:] == ["-p", "prompt"]

    def test_job_deterministe_jamais_altere(self):
        mod = self._mod()
        mod.CLAUDE_BIN = "C:/faux/claude.exe"
        argv = ["py", "-X", "utf8", "scan_projets.py"]
        assert mod._avec_flux(argv) == argv

    def test_init_annonce_le_demarrage(self):
        mod = self._mod()
        ligne = mod._ligne_evenement({"type": "system", "subtype": "init"})
        assert ligne and "session" in ligne

    def test_hooks_de_demarrage_ignores(self):
        mod = self._mod()
        assert mod._ligne_evenement(
            {"type": "system", "subtype": "hook_started"}) is None

    def test_appel_d_outil_rendu_lisible(self):
        mod = self._mod()
        ligne = mod._ligne_evenement({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "C:/x/y.py"}}]}})
        assert "Read" in ligne and "C:/x/y.py" in ligne

    def test_texte_de_l_agent_conserve(self):
        mod = self._mod()
        ligne = mod._ligne_evenement({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Je vérifie l'état réel."}]}})
        assert ligne == "Je vérifie l'état réel."

    def test_resultat_final_rendu(self):
        mod = self._mod()
        assert mod._ligne_evenement(
            {"type": "result", "result": "## Proposition"}) == "## Proposition"

    def test_evenement_inconnu_ignore_sans_planter(self):
        mod = self._mod()
        assert mod._ligne_evenement({"type": "rate_limit_event"}) is None
        assert mod._ligne_evenement({}) is None


@pytest.fixture()
def serveur_et_module():
    """Même serveur réel, mais en rendant AUSSI le module : ces tests injectent
    des jobs dans JOBS pour observer ce que l'API en dérive."""
    mod = _load_serve_wiki()
    srv = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)
    yield base, mod
    srv.shutdown()
    thread.join(timeout=5)


class TestDureeEcoulee:
    """Sans durée qui avance, « en cours » ne se distingue pas d'un job planté —
    or un job LLM démarre à froid en ~25 s (mesuré) et dure plusieurs minutes."""

    def _job(self, **extra):
        base = {"action": "scan", "libelle": "x", "cible": None,
                "started": "10:00:00", "ended": None, "tail": []}
        base.update(extra)
        return base

    def test_api_jobs_expose_une_duree_qui_avance(self, serveur_et_module):
        base, mod = serveur_et_module
        with mod.JOBS_LOCK:
            mod.JOBS["chrono"] = self._job(id="chrono", status="en cours",
                                           t0=time.time() - 42)
        _, corps = _get(base, "/api/jobs")
        job = next(j for j in corps["jobs"] if j["id"] == "chrono")
        assert job["duree_s"] >= 42

    def test_duree_figee_une_fois_termine(self, serveur_et_module):
        base, mod = serveur_et_module
        with mod.JOBS_LOCK:
            mod.JOBS["fini"] = self._job(id="fini", status="ok", ended="10:01:00",
                                         t0=time.time() - 300,
                                         fin_ts=time.time() - 240)
        _, corps = _get(base, "/api/jobs")
        job = next(j for j in corps["jobs"] if j["id"] == "fini")
        assert job["duree_s"] == 60
