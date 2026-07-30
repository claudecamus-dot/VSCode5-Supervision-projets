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

    def _projets(self, tmp_path, noms, avec_script=True, trace=None):
        cfg = []
        for n in noms:
            d = tmp_path / n / ".claude" / "supervision"
            if avec_script:
                d.mkdir(parents=True)
                # Scan factice : dort un peu et note SON intervalle d'exécution — on
                # observe l'ordonnancement, jamais les vrais dépôts de la flotte.
                corps = "import time\ntime.sleep(0.3)\n"
                if trace:
                    corps = (
                        "import time\n"
                        "debut = time.time()\n"
                        "time.sleep(0.3)\n"
                        f"open(r'{trace}', 'a', encoding='utf-8').write("
                        f"f'{n} {{debut}} {{time.time()}}\\n')\n")
                (d / "scan_transcripts.py").write_text(corps, encoding="utf-8")
            cfg.append({"nom": n, "chemin": str(tmp_path / n)})
        return cfg

    def test_les_scans_se_chevauchent_vraiment(self, tmp_path):
        """Prouve le parallélisme par une PROPRIÉTÉ, pas par un chronomètre.

        La première version assertait « 4 scans de 0,4 s en moins de 1,2 s » : vrai,
        mais dépendant de la charge de la machine — elle a lâché dès que la suite
        complète a tourné en concurrence d'autre travail. Un seuil au chronomètre finit
        toujours par devenir instable, et un test instable finit par être ignoré.

        Ici chaque scan factice note son intervalle [début, fin]. Deux intervalles qui
        se chevauchent sont impossibles en séquentiel — quelle que soit la vitesse de
        la machine, un `for` attend la fin du précédent avant de lancer le suivant."""
        trace = str(tmp_path / "intervalles.txt").replace("\\", "\\\\")
        cfg = self._projets(tmp_path, ["A", "B", "C", "D"], trace=trace)
        etats = scan.refresh_local_scans(cfg)
        assert etats == {"A": "rafraichi", "B": "rafraichi",
                         "C": "rafraichi", "D": "rafraichi"}
        lignes = (tmp_path / "intervalles.txt").read_text(encoding="utf-8").split("\n")
        intervalles = [(float(p[1]), float(p[2]))
                       for p in (x.split() for x in lignes if x.strip())]
        assert len(intervalles) == 4, intervalles
        chevauchements = sum(
            1 for i, (d1, f1) in enumerate(intervalles)
            for d2, f2 in intervalles[i + 1:]
            if d1 < f2 and d2 < f1)
        assert chevauchements >= 1, (
            f"aucun chevauchement sur {intervalles} — les scans sont séquentiels")

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
        """Le scan ne doit jamais échouer à cause d'un projet : None, pas d'exception."""
        assert scan.git_etat(str(tmp_path)) == {"non_commite": None, "branches": None}

    def test_chemin_inexistant_fail_open(self, tmp_path):
        assert scan.git_etat(str(tmp_path / "nulle-part")) == {
            "non_commite": None, "branches": None}
