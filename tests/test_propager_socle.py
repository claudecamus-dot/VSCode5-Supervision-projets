"""`propager_socle` : le local survit, et on le PROUVE ligne à ligne.

Le garde-fou d'origine vérifiait que le chapitre « Portée sur ce projet » EXISTAIT.
Il ne vérifiait pas qu'il était COMPLET — et la différence a coûté un vrai défaut, le
jour même de la première propagation (2026-09-01).

CE QUI EST ARRIVÉ. Quatre copies sur cinq portaient leur texte local tissé dans les
sections du socle. Je l'ai déplacé à la main dans un chapitre dédié, en gardant les
IDÉES et en laissant partir l'OPÉRATIONNEL : les commandes exactes de journalisation
(VSCode), les lignes de table de vérification avec leurs chemins réels (VSCode1,
VSCode3, VSCode4), et sur VSCode2 le paramètre `--retrait-citation-mm 3.53`,
explicitement marqué « arbitré et conservé ». Sans lui, `pdf_verify.py` signale à tort
un bord gauche multiple : la session suivante aurait chassé un faux défaut bloquant sur
un PDF correct. C'est la session qui travaille dans ce dépôt qui l'a vu, en diffant son
avant/après — pas le hub, qui ne mesurait que la présence du chapitre.

LA LEÇON, et c'est celle que ce fichier garde : **« le chapitre existe » n'est pas
« rien n'a disparu »**. Une idée ne se lance pas, une commande si. `lignes_perdues`
compare donc l'avant et l'après ligne à ligne, en retirant ce que le socle explique ;
ce qui reste n'est attribuable à personne, donc perdu, et la propagation refuse d'écrire.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "propager_socle_test", os.path.join(HUB, ".claude", "dispositif", "propager_socle.py"))
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

SOCLE = "## Méthode — 5 étapes\nUne étape générique du socle.\n"


class TestLignesPerdues:
    def test_une_ligne_locale_qui_disparait_est_signalee(self):
        avant = "## Portée sur ce projet\n--retrait-citation-mm 3.53 arbitré\n" + SOCLE
        apres = "## Portée sur ce projet\n" + SOCLE
        perdues = ps.lignes_perdues(avant, apres, SOCLE)
        assert any("3.53" in l for l in perdues)

    def test_une_ligne_reprise_par_le_socle_n_est_pas_une_perte(self):
        """Le socle change de génération : son ancien texte disparaît légitimement.
        Le compter comme perdu rendrait le garde-fou inutilisable."""
        avant = "vieille phrase du socle\n" + SOCLE
        apres = SOCLE + "vieille phrase du socle\n"
        assert ps.lignes_perdues(avant, apres, SOCLE + "vieille phrase du socle\n") == []

    def test_la_ligne_de_provenance_n_est_jamais_comptee(self):
        """Elle change à chaque propagation (hash + date). Un garde-fou qui crie à
        chaque passage ne se lit plus."""
        avant = ps.MARQUEUR_PROVENANCE + " socle : aaaaaaa du 2026-09-01 -->\n" + SOCLE
        apres = ps.MARQUEUR_PROVENANCE + " socle : bbbbbbb du 2026-09-02 -->\n" + SOCLE
        assert ps.lignes_perdues(avant, apres, SOCLE) == []

    def test_les_lignes_vides_et_l_indentation_ne_font_pas_de_bruit(self):
        avant = "  une ligne\n\n\n" + SOCLE
        apres = "une ligne\n" + SOCLE
        assert ps.lignes_perdues(avant, apres, SOCLE) == []


class TestLeRefusDEcrire:
    def test_une_valeur_arbitree_dans_le_chapitre_survit_a_la_propagation(self, tmp_path):
        """Ce test acceptait `("PERTE-LOCALE", "a-propager", "applique")` — les TROIS
        états atteignables — donc il ne pouvait pas échouer (défaut
        `tests/test_propager_socle.py:64-75`, audit du 2026-09-01). Son scénario place
        la valeur DANS le chapitre local : la propagation doit donc réussir et la
        préserver, pas refuser. C'est cela qu'il vérifie maintenant, sans alternative.
        """
        racine = tmp_path / "projet"
        (racine / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        cible = racine / ps.REL_CIBLE
        # Pas de ligne parasite hors chapitre : depuis que le garde-fou compare aussi
        # le HORS-chapitre, une « intro » locale serait — à juste titre — signalée
        # comme perdue, et ce test ne parlerait plus de ce qu'il prétend tester.
        cible.write_text("## Portée sur ce projet\nvaleur arbitrée 3.53\n" + SOCLE,
                         encoding="utf-8")
        r = ps.traiter("faux", str(racine), SOCLE, "prov\n", appliquer=True)
        assert r["etat"] == "applique", (
            f"une valeur rangée dans le chapitre local devrait passer (« {r['etat']} »)")
        assert cible.read_text(encoding="utf-8").count("3.53") == 1, (
            "la valeur arbitrée n'a pas survécu à la propagation")

    def test_sans_chapitre_local_la_cible_n_est_pas_ecrasee(self, tmp_path):
        racine = tmp_path / "p2"
        (racine / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        cible = racine / ps.REL_CIBLE
        avant = "du contenu local sans chapitre\n" + SOCLE
        cible.write_text(avant, encoding="utf-8")
        r = ps.traiter("faux", str(racine), SOCLE, "prov\n", appliquer=True)
        assert r["etat"] == "sans-chapitre-local"
        assert cible.read_text(encoding="utf-8") == avant, "cible écrasée malgré le refus"


class TestLeLocalReellementEnPlaceDansLaFlotte:
    """Le cas qui a motivé tout ça, vérifié sur les vrais dépôts."""

    def _lire(self, projet):
        """Le chemin vient de `projets.json`, jamais d'une racine codée en dur.

        Corrigé à la revue du 2026-09-01 : la première version portait
        `c:\\Users\\claude.camus\\Documents` en clair — un chemin machine-spécifique
        dans un fichier versionné, qui aurait fait échouer la suite sur tout autre
        poste et sur la CI. `propager_socle.projets()` lit déjà la config : la
        réutiliser est la correction minimale (R1).
        """
        racine = dict(ps.projets()).get(projet)
        if not racine:
            return None
        chemin = os.path.join(racine, ps.REL_CIBLE)
        return open(chemin, encoding="utf-8").read() if os.path.isfile(chemin) else None

    def test_la_valeur_arbitree_de_vscode2_est_presente(self):
        t = self._lire("VSCode2")
        if t is None:
            return  # dépôt absent de ce poste : le test ne prétend rien
        assert "--retrait-citation-mm 3.53" in t, (
            "valeur ARBITRÉE perdue : pdf_verify signalerait un faux bord gauche multiple")

    def test_chaque_copie_porte_un_chapitre_local_non_vide(self):
        for projet in ("VSCode", "VSCode1", "VSCode2", "VSCode3", "VSCode4"):
            t = self._lire(projet)
            if t is None:
                continue
            local = ps.extraire_chapitre_local(t)
            assert local and len(local.splitlines()) >= 10, (
                f"{projet} : chapitre local absent ou réduit à un titre")


class TestLeGardeFouPeutReellementSeDeclencher:
    """Défaut `propager_socle.py:151-154`, audit technique du 2026-09-01.

    Le garde-fou anti-perte ne pouvait PAS se déclencher depuis `traiter()`. La chaîne :
    `traiter()` extrait le chapitre local, `composer()` le recolle **verbatim**, donc
    `extraire_chapitre_local(nouveau)` est toujours égal à `chap_avant` — la
    soustraction chapitre-à-chapitre est vide par construction, et la branche
    fichier-entier était inatteignable (le cas `local is None` sort avant). Reproduit
    sur les 5 copies réelles : `perdues=0` partout.

    Le contrôle protégeait donc la seule chose qui ne risquait rien, et laissait passer
    la seule qui risquait quelque chose : **le texte local tissé HORS du chapitre**,
    que `composer()` jette en reconstruisant le fichier depuis le socle du hub. C'est
    exactement le cas qui a coûté le `--retrait-citation-mm 3.53` de VSCode2.

    Troisième occurrence en un jour du même motif : un garde-fou qui compare autre
    chose que ce qu'il prétend comparer.
    """

    def test_une_ligne_locale_hors_chapitre_est_signalee(self):
        """Le trou réel : le chapitre est intact, mais une ligne locale tissée dans
        l'introduction disparaît — et personne ne le disait."""
        avant = ("intro du socle\n"
                 "--retrait-citation-mm 3.53 arbitré et conservé\n"
                 "## Portée sur ce projet\nle chapitre local\n" + SOCLE)
        apres = ps.composer(SOCLE, "## Portée sur ce projet\nle chapitre local\n", "prov\n")
        perdues = ps.lignes_perdues(avant, apres, SOCLE)
        assert any("3.53" in l for l in perdues), (
            "une ligne locale hors chapitre disparaît sans être signalée")

    def test_le_chemin_reel_de_traiter_declenche_le_garde_fou(self, tmp_path):
        """Le test précédent appelle la fonction ; celui-ci passe par `traiter()`,
        c'est-à-dire par le chemin que la propagation emprunte vraiment. C'est là que
        la tautologie vivait."""
        racine = tmp_path / "cible"
        (racine / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        cible = racine / ps.REL_CIBLE
        avant = ("intro\n--retrait-citation-mm 3.53 arbitré\n"
                 "## Portée sur ce projet\nchapitre local\n" + SOCLE)
        cible.write_text(avant, encoding="utf-8")
        r = ps.traiter("sonde", str(racine), SOCLE, "prov\n", appliquer=True)
        assert r["etat"] == "PERTE-LOCALE", (
            f"la propagation n'a pas refusé d'écrire (état « {r['etat']} »)")
        assert any("3.53" in l for l in r["perdues"])
        assert cible.read_text(encoding="utf-8") == avant, (
            "la cible a été écrasée malgré le refus")

    def test_accepter_pertes_reste_la_seule_facon_de_forcer(self, tmp_path):
        """Le refus doit être franchissable EXPLICITEMENT — sinon la première perte
        légitime rend l'outil inutilisable et quelqu'un le contournera autrement."""
        racine = tmp_path / "cible2"
        (racine / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        cible = racine / ps.REL_CIBLE
        cible.write_text("intro\nligne locale perdue\n"
                         "## Portée sur ce projet\nchapitre\n" + SOCLE, encoding="utf-8")
        r = ps.traiter("sonde", str(racine), SOCLE, "prov\n", appliquer=True,
                       tolerer_pertes=True)
        assert r["etat"] == "applique"
        assert "ligne locale perdue" not in cible.read_text(encoding="utf-8")

    def test_un_socle_qui_grossit_ne_declenche_rien(self):
        """Le garde-fou ne doit pas redevenir bruyant : ajouter du texte au socle ne
        perd rien. Mesuré le 2026-09-01 sur les 5 dépôts réels — 0 ligne signalée."""
        chap = "## Portée sur ce projet\nchapitre local\n"
        avant = ps.composer(SOCLE, chap, "prov\n")
        socle_grossi = SOCLE + "une phrase ajoutée au hub\n"
        apres = ps.composer(socle_grossi, chap, "prov\n")
        assert ps.lignes_perdues(avant, apres, socle_grossi) == []


class TestLAncreEstLaMemePartout:
    """Défaut « ancre recopiée dans 3 fichiers », audit technique du 2026-09-01.

    `"## Méthode — 5 étapes"` vivait en littéral dans `propager_socle.composer`,
    dans `export_agentic.ANCRE_SOCLE` et dans la constante de ce fichier de test —
    sans constante partagée ni test qui les lie. Renommer ce titre de section dans la
    skill aurait cassé la coupe socle/local en silence, sur les 5 cibles à la fois :
    `composer()` lève, `_socle_a_jour()` rend False, et le seul symptôme aurait été un
    « DIFFERENT » de plus dans un rapport qui en compte déjà 88.

    Ce test ne supprime pas la duplication (trois scripts autonomes, pas un package) :
    il la rend impossible à laisser diverger.
    """

    def test_les_trois_copies_de_l_ancre_coincident(self):
        s = importlib.util.spec_from_file_location(
            "export_agentic_ancre",
            os.path.join(HUB, ".claude", "dispositif", "export_agentic.py"))
        ea = importlib.util.module_from_spec(s)
        s.loader.exec_module(ea)
        assert ps.ANCRE_SOCLE == ea.ANCRE_SOCLE, (
            f"les deux scripts coupent a des endroits differents : "
            f"{ps.ANCRE_SOCLE!r} vs {ea.ANCRE_SOCLE!r}")
        assert ps.ANCRE_SOCLE in SOCLE, (
            "la constante du test a divergé des scripts qu'elle exerce")

    def test_l_ancre_existe_vraiment_dans_le_socle_publie(self):
        """Le test qui aurait crié : l'ancre doit se trouver dans le fichier RÉEL que
        la propagation découpe, pas seulement dans les constantes qui la décrivent."""
        if not os.path.isfile(ps.SOCLE_SRC):
            return          # export/ pas encore généré : rien à vérifier
        socle = open(ps.SOCLE_SRC, encoding="utf-8").read()
        assert ps.ANCRE_SOCLE in socle, (
            f"l'ancre {ps.ANCRE_SOCLE!r} est absente du socle publié — la coupe "
            "socle/local casserait sur les 5 cibles au prochain passage")
