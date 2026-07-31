"""Câblage des boutons « En débattre » (demande utilisateur 2026-07-31) : depuis les
onglets Veille, Actions, Actions correctives, Déploiement et Exports, on peut convoquer
la salle adéquate sur le sujet affiché.

Trois invariants valent d'être verrouillés :

  * **la salle est validée contre une allowlist dérivée des TOML réels.** L'identifiant
    vient du clic ; il n'atteint jamais un shell (argv reste une liste), mais il part
    dans un `--party` et dans un prompt facturé. Une salle inventée doit être refusée,
    pas lancée ;
  * **la salle délibère et n'écrit rien.** C'est ce qui rend l'action sûre à câbler sur
    un bouton : au pire elle coûte, elle ne casse rien. Le prompt doit le dire, et le
    run ne doit jamais partir en `--dangerously-skip-permissions` (réservé, par
    arbitrage du 2026-07-24, à la seule action « valider ») ;
  * **`--non-interactive` est obligatoire.** Une party est open-ended par nature : elle
    tourne jusqu'à ce que l'utilisateur dise stop. Derrière un bouton, personne ne peut
    le dire — sans ce drapeau, le job resterait ouvert jusqu'au timeout.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, os.path.join(HUB, chemin))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sw = _charger("serve_wiki", os.path.join("scripts", "serve_wiki.py"))
scan = _charger("scan_projets", os.path.join("scripts", "scan_projets.py"))


class TestAllowlistDesSalles:
    def test_les_salles_valides_viennent_des_toml_reels(self):
        salles = sw._salles_valides()
        assert {"conseil-flotte", "atelier-dev", "atelier-deck", "mise-en-service",
                "revue-consommation", "accueil-projet"} <= salles
        assert {"code-review-crew", "anti-consensus-club"} <= salles  # livrées

    def test_une_salle_inventee_est_refusee(self):
        assert sw.action_party("salle-bidon", "sujet") is None
        assert sw.action_party("", "sujet") is None
        assert sw.action_party(None, "sujet") is None

    def test_une_salle_valide_produit_un_argv_liste(self):
        argv = sw.action_party("conseil-flotte", "un sujet")
        if argv is None:
            import pytest
            pytest.skip("binaire claude absent de ce poste")
        assert isinstance(argv, list)  # jamais une chaîne : pas de shell, pas d'injection


class TestPromptDeLaSalle:
    def _argv(self):
        argv = sw.action_party("atelier-dev", "un sujet de test")
        if argv is None:
            import pytest
            pytest.skip("binaire claude absent de ce poste")
        return argv

    def test_non_interactif_sinon_le_job_ne_se_termine_jamais(self):
        assert "--non-interactive" in self._argv()[-1]

    def test_la_salle_demandee_est_bien_celle_transmise(self):
        assert "--party atelier-dev" in self._argv()[-1]

    def test_le_prompt_interdit_explicitement_d_ecrire(self):
        prompt = self._argv()[-1]
        assert "ne modifie AUCUN fichier" in prompt
        assert "R4" in prompt

    def test_jamais_de_skip_permissions(self):
        """Réservé à « valider » par arbitrage du 2026-07-24. Une salle qui délibère
        n'a aucune raison de contourner le mur de permission."""
        assert "--dangerously-skip-permissions" not in self._argv()

    def test_le_sujet_est_borne(self):
        argv = sw.action_party("conseil-flotte", "x" * 5000)
        if argv is None:
            import pytest
            pytest.skip("binaire claude absent de ce poste")
        assert len(argv[-1]) < 3000


class TestMappingDesContextes:
    def test_chaque_contexte_pointe_une_salle_reelle(self):
        salles = sw._salles_valides()
        for contexte, (salle, _sujet) in scan.PARTY_PAR_CONTEXTE.items():
            assert salle in salles, f"contexte {contexte} -> salle inexistante {salle}"

    def test_un_contexte_inconnu_ne_rend_aucun_bouton(self):
        """Mieux vaut pas de bouton qu'un bouton qui lance une salle inexistante."""
        assert scan.bouton_party("contexte-qui-n-existe-pas") == ""

    def test_le_correctif_choisit_sa_salle_selon_sa_nature(self):
        assert scan.contexte_party_correctif("pratique-test") == "correctif-dev"
        assert scan.contexte_party_correctif("pratique-design") == "correctif-deck"
        assert scan.contexte_party_correctif("pratique-doc") == "deploiement"
        assert scan.contexte_party_correctif("ko-repete") == "correctif"
        assert scan.contexte_party_correctif("") == "correctif"

    def test_le_bouton_porte_la_salle_et_le_sujet(self):
        h = scan.bouton_party("veille")
        assert 'data-action="party"' in h
        assert 'data-salle="conseil-flotte"' in h
        assert "data-sujet=" in h


class TestPageLivree:
    """Le câblage doit être VISIBLE dans la page réellement générée — un helper qui
    marche mais n'est appelé nulle part ne sert à rien."""

    def _page(self):
        with open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8") as fh:
            return fh.read()

    def test_les_cinq_onglets_portent_au_moins_un_bouton(self):
        import re
        h = self._page()
        for pane in ("veille", "actions", "correctifs", "deploiement", "exports"):
            i = h.find(f'id="pane-{pane}"')
            assert i > 0, f"onglet {pane} absent"
            j = h.find('<section class="pane"', i + 10)
            bloc = h[i:j if j > 0 else len(h)]
            assert 'data-action="party"' in bloc, f"onglet {pane} sans bouton de table ronde"

    def test_toutes_les_salles_citees_dans_la_page_existent(self):
        import re
        salles = sw._salles_valides()
        citees = set(re.findall(r'data-action="party" data-salle="([a-z-]+)"', self._page()))
        assert citees, "aucun bouton de table ronde dans la page"
        assert citees <= salles, f"salles inexistantes câblées : {sorted(citees - salles)}"

    def test_le_js_transmet_salle_et_sujet(self):
        with open(os.path.join(HUB, "docs", "wiki_app.js"), encoding="utf-8") as fh:
            js = fh.read()
        assert "corps.salle = b.dataset.salle" in js
        assert "corps.sujet = b.dataset.sujet" in js


class TestDestinatairesDesSalles:
    """« Dans les salles, y a-t-il des salles qui réceptionneront le travail ? »
    (demande du 2026-07-31). Chaque salle doit avoir un destinataire déclaré — un
    travail que personne ne réceptionne est un travail perdu — et tout destinataire
    déclaré doit correspondre à une salle réelle."""

    def test_toute_salle_a_un_destinataire(self):
        _, groupes = scan.party_collectif()
        sans = sorted({g["id"] for g in groupes} - set(scan.PARTY_DESTINATAIRES))
        assert not sans, f"salles sans destinataire déclaré : {sans}"

    def test_aucun_destinataire_orphelin(self):
        _, groupes = scan.party_collectif()
        ids = {g["id"] for g in groupes}
        orphelins = sorted(set(scan.PARTY_DESTINATAIRES) - ids)
        assert not orphelins, f"destinataires pour des salles inexistantes : {orphelins}"

    def test_le_rendu_montre_le_deroule_et_les_destinataires(self):
        h = scan.render_salles_utilisables_html()
        assert "Comment se déroule une table ronde" in h
        assert "Le travail part à" in h
        assert "Autour de la table" in h
