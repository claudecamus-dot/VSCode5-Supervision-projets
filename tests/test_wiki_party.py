"""Non-régression du schéma de la table ronde élargie au wiki (demande utilisateur
2026-07-31, après l'écriture de `_bmad/custom/bmad-party-mode.toml`).

L'invariant qui fait la valeur de ce schéma est le même que celui de l'onglet
Dispositif : il est **dérivé des TOML réels**, jamais recopié. Un casting codé en
dur mentirait dès le premier rôle ajouté ou renommé — et un schéma faux coûte plus
cher que pas de schéma.

Le test le plus utile ici est celui de la RÉSOLUTION : le schéma doit résoudre les
membres d'une salle exactement comme `resolve_party.py`, y compris les agents BMAD
installés (Sally, Winston) qu'une salle peut convoquer sans qu'ils soient des
personas de l'override. La première version du rendu les affichait « non résolu ».
"""

import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class TestCollectif:
    def test_les_trois_sources_sont_empilees(self):
        """Agents installés, personas livrés, rôles maison — dans cet ordre."""
        membres, _ = scan.party_collectif()
        sources = {m["source"] for m in membres}
        assert sources == {"installé", "livré", "maison"}

    def test_les_personas_livres_survivent_a_l_override(self):
        """Le merge est keyé : notre override AJOUTE, il ne remplace pas la liste.
        Si ces 9 disparaissaient, c'est que le merge est devenu un écrasement."""
        membres, _ = scan.party_collectif()
        codes = {m["code"] for m in membres}
        assert {"sec-hawk", "adversary", "edge-hunter", "craftsman", "shipper",
                "option-generator", "claim-checker", "loop-stopper",
                "consensus-challenger"} <= codes

    def test_les_groupes_livres_survivent_aussi(self):
        _, groupes = scan.party_collectif()
        ids = {g["id"] for g in groupes}
        assert {"code-review-crew", "anti-consensus-club"} <= ids

    def test_aucun_code_de_role_maison_n_ecrase_un_agent_installe(self):
        """Une collision de `code` écrase silencieusement l'agent installé
        (resolve_party.py:112-119). Personne ne doit perdre Mary ou Amelia sans
        l'avoir voulu — ce test le rendrait bruyant."""
        membres, _ = scan.party_collectif()
        installes = {m["code"] for m in membres if m["source"] == "installé"}
        assert installes == {
            "bmad-agent-analyst", "bmad-agent-tech-writer", "bmad-agent-pm",
            "bmad-agent-ux-designer", "bmad-agent-architect", "bmad-agent-dev",
        }

    def test_les_salles_respectent_le_plafond_de_cinq_voix(self):
        """Plafond 3-5 adopté par la flotte (arbitrage veille:agent-teams du
        2026-07-29). Au-delà, la salle « se lit comme une foule, pas une
        conversation » — et chaque voix de plus est une session facturée."""
        _, groupes = scan.party_collectif()
        trop = {g["id"]: len(g.get("members") or []) for g in groupes
                if len(g.get("members") or []) > 5}
        assert not trop, f"salles au-dessus de 5 voix : {trop}"


class TestRendu:
    def test_tous_les_membres_de_toutes_les_salles_se_resolvent(self):
        """LE test du schéma : aucune salle ne doit afficher « non résolu ».
        Cela couvre le cas qui a réellement échoué — une salle qui convoque un
        agent BMAD installé (Sally dans atelier-deck) plutôt qu'un persona."""
        h = scan.render_party_html()
        assert "non résolu" not in h, (
            "un membre de salle ne se résout pas : soit un code a été mal écrit "
            "dans _bmad/custom/bmad-party-mode.toml, soit party_collectif() a "
            "cessé de charger une des trois sources.")

    def test_le_casting_est_derive_et_non_code_en_dur(self):
        """Si le rendu recopiait une liste, renommer un rôle dans le TOML ne
        changerait rien à la page. On vérifie que le nom rendu vient bien du TOML."""
        membres, _ = scan.party_collectif()
        argus = next(m for m in membres if m["code"] == "supervision")
        assert argus["name"] in scan.render_party_html()

    def test_la_boucle_dit_que_la_salle_ne_produit_pas_de_diff(self):
        """Le principe qui protège R4 : une table ronde qui écrirait du code serait
        une auto-application collective. Il doit rester visible sur la page."""
        h = scan.render_party_html()
        assert "jamais un diff" in h

    def test_chaque_salle_montre_comment_l_ouvrir(self):
        _, groupes = scan.party_collectif()
        h = scan.render_party_html()
        for g in groupes:
            assert f"--party {g['id']}" in h

    def test_absence_d_override_ne_casse_pas_le_rendu(self, monkeypatch, tmp_path):
        """Fail-open : sur un projet de la flotte sans override de party, la page
        doit se rendre quand même (le wiki entier ne tombe pas pour ça)."""
        monkeypatch.setattr(scan, "PARTY_OVERRIDE", str(tmp_path / "absent.toml"))
        h = scan.render_party_html()
        assert "non résolu" not in h
        assert "Code Review Crew" in h  # les salles livrées restent


class TestSituations:
    """Les exemples d'usage sont curatés (une situation est un jugement), mais leur
    cible ne l'est pas : chacun doit pointer une salle qui existe VRAIMENT."""

    def test_chaque_situation_pointe_une_salle_reelle(self):
        _, groupes = scan.party_collectif()
        ids = {g["id"] for g in groupes}
        orphelines = sorted({s for _, s, _, _ in scan.PARTY_SITUATIONS} - ids)
        assert not orphelines, (
            f"situations pointant une salle inexistante : {orphelines} — un mode "
            "d'emploi qui ne marche pas est pire que pas de mode d'emploi.")

    def test_chaque_salle_a_au_moins_une_situation(self):
        """L'inverse : une salle sans cas d'usage écrit est une salle que personne ne
        saura quand convoquer — c'est ainsi qu'un dispositif devient décoratif."""
        _, groupes = scan.party_collectif()
        couvertes = {s for _, s, _, _ in scan.PARTY_SITUATIONS}
        sans_exemple = sorted({g["id"] for g in groupes} - couvertes)
        assert not sans_exemple, (
            f"salles sans exemple d'usage au tutoriel : {sans_exemple}")

    def test_les_situations_sont_rendues(self):
        h = scan.render_party_html()
        for _, salle, _, _ in scan.PARTY_SITUATIONS:
            assert f"--party {salle}" in h


class TestPageLivree:
    def test_le_schema_est_dans_l_onglet_tutoriel(self):
        h = scan.render_tutoriel_html()
        assert 'id="party"' in h
        assert "Conseil de flotte" in h

    def test_le_tutoriel_ne_dit_plus_que_bmad_attend_la_v7(self):
        """Le gel de customisation a été levé le 2026-07-31 : la carte « Skills
        BMAD » affirmait « statu quo décidé jusqu'à la v7 », ce qui est devenu faux.
        Une doc qui ment est pire qu'une doc absente."""
        h = scan.render_tutoriel_html()
        assert "jusqu'à la v7" not in h
        assert "aucune invocation mesurée" not in h
