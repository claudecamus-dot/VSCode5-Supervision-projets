"""Non-régression des MARQUEURS de détection du scan (test fonctionnel, coverage).

Corrige un artefact de mesure trouvé au cadrage 2026-07-24 : le scan ne reconnaissait
ni c8 (coverage réel de VSCode1) ni les tests montant un vrai serveur HTTP (VScode5
test_serve_wiki) — les deux existaient mais la mesure les ignorait. Ces règles n'avaient
aucun test (finding recurrent : les règles du scan ne sont pas couvertes).
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class TestMarqueursFonctionnels:
    def _match(self, txt):
        return bool(scan.FONCTIONNEL_MARQUEURS.search(txt))

    def test_marqueurs_historiques_toujours_reconnus(self):
        for m in ("puppeteer", "playwright", "libreoffice", "pymupdf",
                  "Presentation(", "TestClient", "smoke-test"):
            assert self._match(f"import {m}"), m

    def test_serveur_http_reel_reconnu(self):
        # tests/test_serve_wiki.py : monte un vrai serveur + le sollicite en réseau.
        for m in ("ThreadingHTTPServer", "serve_forever", "urllib.request",
                  "http.client", "httpx.get", "requests.post(url)"):
            assert self._match(f"    {m}"), m

    def test_un_test_purement_unitaire_ne_matche_pas(self):
        # Pas de faux positif : un test unitaire sans I/O réel ne doit pas compter
        # comme vérification fonctionnelle.
        code = "def test_add():\n    assert 1 + 1 == 2\n"
        assert not self._match(code)

    def test_mention_requests_sans_appel_ne_matche_pas(self):
        # « requests » seul (dans un commentaire) ne suffit pas — il faut un appel réel.
        assert not self._match("# on pourrait utiliser requests plus tard")


class TestDetectionCoverage:
    """Reproduit la logique de détection coverage de analyse_pratiques (marqueurs
    cherchés dans requirements*.txt / package.json)."""
    MARQUEURS = ("pytest-cov", "coverage", "nyc", "--cov", '"c8"')

    def _a_coverage(self, contenu):
        return any(m in contenu for m in self.MARQUEURS)

    def test_c8_dans_package_json_reconnu(self):
        pkg = '{"devDependencies": {"c8": "^10.1.0", "eslint": "^9"}, "scripts": {"test:cov": "c8 npm test"}}'
        assert self._a_coverage(pkg)

    def test_pytest_cov_reconnu(self):
        assert self._a_coverage("pytest-cov==5.0.0\n")

    def test_c8_faux_positif_evite_sur_un_hash(self):
        # "c8" nu apparaîtrait dans un hash (ex. sha "…abc8f…") — on cherche `"c8"`
        # AVEC guillemets (clé de package.json), pas le substring nu.
        assert not self._a_coverage('{"integrity": "sha512-abc8fde"}')

    def test_absence_de_coverage(self):
        assert not self._a_coverage('{"devDependencies": {"eslint": "^9"}}')


class TestRefreshLocalScansParallele:
    """Étude de latence 2026-07-30, arbitrée : la boucle était séquentielle et pesait
    l'essentiel des ~16-24 s du bouton « Re-scan » (5-6 sous-processus à 2,5-4 s chacun).
    Les scans sont indépendants — chacun lit et écrit dans son propre dépôt — donc la
    durée tombe à celle du plus lent. Gain de temps pur, 0 token."""

    def _projets(self, tmp_path, noms, avec_script=True, rendezvous=None):
        cfg = []
        for n in noms:
            d = tmp_path / n / ".claude" / "supervision"
            if avec_script:
                d.mkdir(parents=True)
                # Scan factice. Sans rendez-vous : dort un peu, c'est tout. Avec
                # rendez-vous : chaque scan signale son arrivée par SON PROPRE fichier
                # (jamais d'append concurrent, cf. docstring du test), puis attend que
                # tous les autres soient arrivés — une barrière.
                corps = "import time\ntime.sleep(0.3)\n"
                if rendezvous:
                    attendus = len(noms)
                    corps = (
                        "import os, time\n"
                        f"salle = r'{rendezvous}'\n"
                        f"open(os.path.join(salle, '{n}.arrive'), 'w').close()\n"
                        # 6 s : large devant les quelques ms d'un vrai rendez-vous, et
                        # assez court pour qu'une régression séquentielle (4 x 6 s) se
                        # signale vite, bien avant le timeout de 90 s du scan réel.
                        "limite = time.time() + 6\n"
                        "tous = False\n"
                        "while time.time() < limite:\n"
                        f"    if len(os.listdir(salle)) >= {attendus}:\n"
                        "        tous = True\n"
                        "        break\n"
                        "    time.sleep(0.005)\n"
                        f"open(os.path.join(salle, '{n}.verdict'), 'w')."
                        "write('tous' if tous else 'seul')\n")
                (d / "scan_transcripts.py").write_text(corps, encoding="utf-8")
            cfg.append({"nom": n, "chemin": str(tmp_path / n)})
        return cfg

    def test_les_scans_se_chevauchent_vraiment(self, tmp_path):
        """Prouve le parallélisme par un RENDEZ-VOUS, ni par un chronomètre ni par
        une trace partagée.

        Trois générations de ce test, chacune corrigeant le défaut de la précédente :

        1. « 4 scans de 0,4 s en moins de 1,2 s » — un seuil au chronomètre, qui a
           lâché dès que la suite a tourné en concurrence d'autre travail.
        2. Chaque scan notait son intervalle [début, fin] dans un fichier COMMUN, en
           append, et on cherchait un chevauchement. Instable à son tour (~1 échec sur
           5, mesuré le 2026-07-31) — mais pas pour la raison qu'on croit : le
           parallélisme marchait, c'est le HARNAIS qui perdait une ligne. Quatre
           processus qui écrivent en append dans le même fichier au même instant, et
           l'assertion tombait sur `len(intervalles) == 4`. Un test instable finit
           toujours par être ignoré, et celui-là accusait le code à la place du test.
        3. Ici : chaque scan pose son propre fichier (aucune écriture concurrente sur
           une même cible), puis ATTEND que les autres aient posé le leur. Un `for`
           séquentiel ne peut pas franchir cette barrière — le premier scan attendrait
           des camarades qui ne démarreront qu'après lui. La preuve ne dépend donc plus
           d'aucune durée : ni de la vitesse de la machine, ni de sa charge.
        """
        salle = tmp_path / "rendezvous"
        salle.mkdir()
        cfg = self._projets(tmp_path, ["A", "B", "C", "D"],
                            rendezvous=str(salle).replace("\\", "\\\\"))
        etats = scan.refresh_local_scans(cfg)
        assert etats == {"A": "rafraichi", "B": "rafraichi",
                         "C": "rafraichi", "D": "rafraichi"}
        verdicts = {f.stem: f.read_text(encoding="utf-8")
                    for f in salle.glob("*.verdict")}
        assert set(verdicts) == {"A", "B", "C", "D"}, verdicts
        seuls = sorted(n for n, v in verdicts.items() if v != "tous")
        assert not seuls, (
            f"{seuls} n'ont jamais vu les autres démarrer : les scans se sont "
            "exécutés en séquentiel, pas en parallèle")

    def test_l_ordre_du_resultat_suit_la_config_pas_l_arrivee(self, tmp_path):
        """Sortie stable d'une exécution à l'autre : sans ça, le libellé du scan
        changerait d'ordre au hasard de l'ordonnancement."""
        cfg = self._projets(tmp_path, ["Z", "A", "M"])
        assert list(scan.refresh_local_scans(cfg)) == ["Z", "A", "M"]

    def test_un_projet_sans_script_est_absent_sans_bloquer_les_autres(self, tmp_path):
        cfg = self._projets(tmp_path, ["A", "B"])
        cfg.append({"nom": "SansDispositif", "chemin": str(tmp_path / "vide")})
        etats = scan.refresh_local_scans(cfg)
        assert etats["SansDispositif"] == "absent"
        assert etats["A"] == etats["B"] == "rafraichi"

    def test_un_scan_qui_echoue_n_empeche_pas_les_autres(self, tmp_path):
        cfg = self._projets(tmp_path, ["OK"])
        d = tmp_path / "KO" / ".claude" / "supervision"
        d.mkdir(parents=True)
        (d / "scan_transcripts.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
        cfg.append({"nom": "KO", "chemin": str(tmp_path / "KO")})
        etats = scan.refresh_local_scans(cfg)
        assert etats == {"OK": "rafraichi", "KO": "echec"}

    def test_config_vide(self, tmp_path):
        assert scan.refresh_local_scans([]) == {}


class TestGitEtat:
    """Ferme deux ⬜ du référentiel que le hub annonçait sans les mesurer (2026-07-30) :
    la dette non commitée n'était vue que sur le hub lui-même, et le trunk-based pas du
    tout. L'angle mort était réel : VSCode2 portait 19 fichiers non commités dont 13
    applicatifs, invisibles depuis le hub — alors que R2 (commit scopé) est la leçon la
    plus chère du projet."""

    def _depot(self, tmp_path, nom="d"):
        import subprocess as sp
        d = tmp_path / nom
        d.mkdir()
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                    ["config", "user.name", "t"]):
            sp.run(["git", "-C", str(d), *cmd], capture_output=True, timeout=15)
        (d / "a.txt").write_text("x", encoding="utf-8")
        sp.run(["git", "-C", str(d), "add", "-A"], capture_output=True, timeout=15)
        sp.run(["git", "-C", str(d), "commit", "-q", "-m", "init"],
               capture_output=True, timeout=15)
        return d

    def test_arbre_propre(self, tmp_path):
        assert scan.git_etat(str(self._depot(tmp_path)))["non_commite"] == 0

    def test_compte_les_fichiers_non_commites(self, tmp_path):
        d = self._depot(tmp_path)
        (d / "b.txt").write_text("y", encoding="utf-8")     # non suivi
        (d / "a.txt").write_text("modifie", encoding="utf-8")  # modifié
        assert scan.git_etat(str(d))["non_commite"] == 2

    def test_compte_les_branches(self, tmp_path):
        import subprocess as sp
        d = self._depot(tmp_path)
        assert scan.git_etat(str(d))["branches"] == 1
        sp.run(["git", "-C", str(d), "branch", "feature"], capture_output=True, timeout=15)
        assert scan.git_etat(str(d))["branches"] == 2

    def test_pas_un_depot_git_fail_open(self, tmp_path):
        """Le scan ne doit jamais échouer à cause d'un projet : None, pas d'exception.
        (`doyen_jours` ajouté le 2026-08-31 — finding flotte:canon-ecrit-jamais-commite
        (b) — même contrat fail-open que les deux autres compteurs.)"""
        assert scan.git_etat(str(tmp_path)) == {
            "non_commite": None, "branches": None, "doyen_jours": None}

    def test_chemin_inexistant_fail_open(self, tmp_path):
        assert scan.git_etat(str(tmp_path / "nulle-part")) == {
            "non_commite": None, "branches": None, "doyen_jours": None}
