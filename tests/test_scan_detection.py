"""Non-régression des MARQUEURS de détection du scan (test fonctionnel, coverage).

Corrige un artefact de mesure trouvé au cadrage 2026-07-24 : le scan ne reconnaissait
ni c8 (coverage réel de VSCode1) ni les tests montant un vrai serveur HTTP (VScode5
test_serve_wiki) — les deux existaient mais la mesure les ignorait. Ces règles n'avaient
aucun test (finding recurrent : les règles du scan ne sont pas couvertes).
"""

import importlib.util
import os
import time

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

    def _projets(self, tmp_path, noms, avec_script=True):
        cfg = []
        for n in noms:
            d = tmp_path / n / ".claude" / "supervision"
            if avec_script:
                d.mkdir(parents=True)
                # scan factice : dort un peu, sort 0 — on mesure l'ordonnancement,
                # jamais les vrais dépôts de la flotte.
                (d / "scan_transcripts.py").write_text(
                    "import time\ntime.sleep(0.4)\n", encoding="utf-8")
            cfg.append({"nom": n, "chemin": str(tmp_path / n)})
        return cfg

    def test_les_scans_tournent_bien_en_parallele(self, tmp_path):
        """Le test qui prouve le gain : 4 scans de 0,4 s doivent prendre ~0,4 s au
        total, pas 1,6 s. Seuil à 1,2 s — largement au-dessus du parallèle, largement
        en dessous du séquentiel : ni faux positif sur machine lente, ni faux négatif."""
        cfg = self._projets(tmp_path, ["A", "B", "C", "D"])
        t0 = time.time()
        etats = scan.refresh_local_scans(cfg)
        duree = time.time() - t0
        assert etats == {"A": "rafraichi", "B": "rafraichi",
                         "C": "rafraichi", "D": "rafraichi"}
        assert duree < 1.2, f"{duree:.2f}s — les scans semblent encore séquentiels"

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
