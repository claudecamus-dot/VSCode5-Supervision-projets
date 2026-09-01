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
import types

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


class TestLeGardeFouNeCriePasSurLeHubLuiMeme:
    """Régression introduite le 2026-09-01 par la correction du garde-fou, trouvée par
    la re-cotation d'audit du même jour.

    En ajoutant la comparaison HORS-chapitre — nécessaire, c'était le vrai trou — j'ai
    recréé le défaut symétrique que le code d'origine documentait : la copie cible est
    `ancien_socle + provenance + chapitre`, donc « ce qui est dans l'avant et pas dans
    l'après » contient TOUTE phrase que le hub a reformulée entre-temps. Reproduit : le
    hub réécrit UNE ligne de son propre socle → `PERTE-LOCALE`, et la ligne déclarée
    perdue est une phrase du hub. Les 5 propagations seraient bloquées.

    Un garde-fou muet et un garde-fou qui crie à tort sont le même défaut vu des deux
    côtés — et c'est la troisième fois que ce fichier l'apprend.

    CE QUI MANQUAIT : l'ANCIEN socle. Il est récupérable — la copie porte son hash dans
    sa propre ligne de provenance (`<!-- SOCLE-PROVENANCE: socle : <hash> du <jour> -->`),
    et `git show <hash>:export/…/SKILL.md` le rend. Une ligne présente dans l'ancien
    socle est attribuable au hub, donc jamais une perte locale.
    """

    SOCLE_V1 = ("intro du socle\nune phrase que le hub va reformuler\n"
                "## Méthode — 5 étapes\nune étape générique.\n")
    SOCLE_V2 = ("intro du socle\nla même idée, reformulée par le hub\n"
                "## Méthode — 5 étapes\nune étape générique.\n")
    CHAP = "## Portée sur ce projet\nle chapitre local\n"

    def _copie_cible(self, socle):
        return ps.composer(socle, self.CHAP,
                           ps.MARQUEUR_PROVENANCE + " socle : deadbee du 2026-09-01 -->\n")

    def test_une_reformulation_du_hub_n_est_pas_une_perte_locale(self):
        avant = self._copie_cible(self.SOCLE_V1)
        apres = self._copie_cible(self.SOCLE_V2)
        perdues = ps.lignes_perdues(avant, apres, self.SOCLE_V2,
                                    socle_origine=self.SOCLE_V1)
        assert perdues == [], (
            f"le hub reformule sa propre phrase et le garde-fou la declare perdue : {perdues}")

    def test_une_vraie_ligne_locale_reste_signalee_malgre_l_ancien_socle(self):
        """Le garde-fou du garde-fou : connaître l'ancien socle ne doit pas devenir
        un blanchiment. Une ligne qui n'est dans AUCUN des deux socles est locale."""
        avant = ("intro du socle\n--retrait-citation-mm 3.53 arbitré\n"
                 "une phrase que le hub va reformuler\n" + self.CHAP
                 + "## Méthode — 5 étapes\nune étape générique.\n")
        apres = self._copie_cible(self.SOCLE_V2)
        perdues = ps.lignes_perdues(avant, apres, self.SOCLE_V2,
                                    socle_origine=self.SOCLE_V1)
        assert any("3.53" in l for l in perdues), (
            "une ligne locale hors chapitre passe inapercue")
        assert not any("reformuler" in l for l in perdues), (
            "la phrase du hub est encore comptee comme perdue")

    def test_l_ancien_socle_se_retrouve_par_la_provenance_de_la_copie(self):
        """Le mécanisme, sur une copie RÉELLE de la flotte — pas sur une chaîne
        fabriquée : c'est là que le format de la ligne de provenance compte."""
        cibles = ps.projets()
        if not cibles:
            return
        chemin = os.path.join(cibles[0][1], ps.REL_CIBLE)
        if not os.path.isfile(chemin):
            return
        texte = open(chemin, encoding="utf-8").read()
        origine = ps.socle_d_origine(texte)
        assert origine, "l'ancien socle n'est pas retrouvable depuis la copie installee"
        assert ps.ANCRE_SOCLE in origine, "ce qui a ete recupere n'est pas un socle"

    def test_la_soustraction_du_socle_est_reellement_exercee(self):
        """Trou signalé par la re-cotation (mutation M2) : retirer `- util(socle)` de la
        comparaison hors-chapitre ne faisait échouer AUCUN test, parce que le seul cas
        couvert ne faisait que GROSSIR le socle. Ici le socle CHANGE — une phrase du
        nouveau socle remplace une ancienne — donc la soustraction est exercée."""
        avant = ("phrase A\n" + self.CHAP + "## Méthode — 5 étapes\ncorps.\n")
        socle_neuf = ("phrase A\n## Méthode — 5 étapes\ncorps.\n")
        apres = ps.composer(socle_neuf, self.CHAP, "prov\n")
        assert ps.lignes_perdues(avant, apres, socle_neuf) == [], (
            "une ligne reprise par le NOUVEAU socle est comptee comme perdue")


class TestLaFraicheurDuSocleNEstPasNegociable:
    """Régression signalée par la re-cotation d'audit du 2026-09-01.

    En ajoutant `_socle_perime()`, je l'avais adossé au drapeau existant :

        if perime and not args.accepter_pertes:

    Or `--accepter-pertes` parle des **lignes locales qui disparaissent** — un
    arbitrage humain sur du contenu de la cible. La **fraîcheur du socle** est une
    autre question : un `export/` non régénéré, c'est propager aux 5 dépôts une
    version périmée de la skill. Conflondre les deux faisait qu'un utilisateur
    forçant une perte locale assumée désactivait au passage, sans en être averti,
    un contrôle qu'il n'avait pas eu l'intention de lever.

    La fraîcheur est donc BLOQUANTE sans exception : la lever coûterait un dépôt
    faux, alors que la réparer coûte une commande.
    """

    def test_un_socle_perime_bloque_meme_avec_accepter_pertes(self, monkeypatch,
                                                              capsys):
        monkeypatch.setattr(ps, "_socle_perime",
                            lambda: "export/ differe de la source vivante (sonde)")
        code = ps.main(["--accepter-pertes", "--dry-run"])
        sortie = capsys.readouterr().out
        assert code == 1, "un socle perime passe des qu'on force les pertes locales"
        assert "PERIME" in sortie
        assert "export_agentic" in sortie, (
            "le refus ne dit pas la commande qui le repare")

    def test_un_socle_frais_ne_bloque_rien(self, monkeypatch):
        monkeypatch.setattr(ps, "_socle_perime", lambda: None)
        assert ps.main(["--dry-run", "--projet", "VSCode"]) == 0


class TestLaProvenanceNeMentJamaisSurCeQuElleDesigne:
    """La 4e occurrence, dans ce fichier, du garde-fou qui compare autre chose.

    Défaut mesuré le 2026-09-01, après le correctif `socle_d_origine()` du même jour :
    `hash_hub()` estampille **HEAD**, alors que le socle réellement copié est lu dans
    **l'arbre de travail** (`SOCLE_SRC`). Propager sur un socle non commité inscrit
    donc chez les 5 cibles une provenance qui désigne une révision où ce socle-là
    n'a jamais existé.

    Reproduit sur les copies réelles : les 5 dépôts portaient `SOCLE-PROVENANCE:
    604fc7c`, alors que le paragraphe des porteurs endormis qu'ils contiennent
    n'entre dans l'histoire qu'en `0f4e632` — `git show 604fc7c:<socle> | grep -c`
    rendait 0, `0f4e632` rendait 1, la copie rendait 1. Conséquence à la propagation
    SUIVANTE : `socle_d_origine()` remonte un socle amputé, et `lignes_perdues()`
    classe en PERTE-LOCALE **chaque phrase que le hub a ajoutée depuis HEAD** — 10
    lignes sur 5 cibles, propagation bloquée, 3 tests rouges.

    `socle_d_origine()` avait fermé le cas symétrique (une ligne du hub *reformulée*
    comptée comme perdue) en faisant confiance à la provenance. Ce test verrouille la
    condition sans laquelle cette confiance n'est pas fondée : **la provenance ne
    s'écrit que si le socle qu'elle désigne est déjà dans git**. Arbitré le
    2026-09-01 (option « refuser de propager sur socle sale ») : la ligne affirme
    « cette copie = le hub à la révision X » ; sur un arbre sale cette phrase est
    fausse par construction, et on ne répare pas une affirmation fausse, on
    s'interdit de l'écrire.
    """

    def _git(self, monkeypatch, sortie="", exc=None):
        def faux_run(cmd, **kw):
            if exc is not None:
                raise exc
            return types.SimpleNamespace(stdout=sortie, stderr="", returncode=0)
        monkeypatch.setattr(ps.subprocess, "run", faux_run)

    def test_la_sonde_voit_un_socle_non_commite(self, monkeypatch):
        self._git(monkeypatch, sortie=" M export/skills/agent-orchestrator/SKILL.md\n")
        raison = ps._socle_non_commite()
        assert raison, "un socle modifie et non commite passe pour propageable"
        assert "agent-orchestrator" in raison, (
            "le refus ne nomme pas le fichier en cause")

    def test_un_socle_propre_ne_bloque_rien(self, monkeypatch):
        self._git(monkeypatch, sortie="")
        assert ps._socle_non_commite() is None

    def test_git_muet_ne_bloque_pas(self, monkeypatch):
        """Fail-open, comme `_socle_perime` : on bloque sur une PREUVE, pas sur un doute."""
        self._git(monkeypatch, exc=OSError("git absent"))
        assert ps._socle_non_commite() is None

    def test_le_refus_dit_la_commande_qui_le_repare(self, monkeypatch, capsys):
        monkeypatch.setattr(ps, "_socle_perime", lambda: None)
        monkeypatch.setattr(ps, "_socle_non_commite",
                            lambda: "export/skills/agent-orchestrator/SKILL.md (sonde)")
        code = ps.main(["--dry-run"])
        sortie = capsys.readouterr().out
        assert code == 1, "la propagation part sur un socle absent de l'histoire"
        assert "git commit" in sortie, (
            "le refus laisse le lecteur sans le geste qui le leve")

    def test_le_refus_est_bloquant_meme_avec_accepter_pertes(self, monkeypatch):
        """`--accepter-pertes` arbitre des lignes LOCALES ; il n'arbitre pas une
        provenance mensongère inscrite chez cinq tiers. La regression du 2026-09-01
        sur `_socle_perime` est exactement celle-la, et elle ne se recommet pas."""
        monkeypatch.setattr(ps, "_socle_perime", lambda: None)
        monkeypatch.setattr(ps, "_socle_non_commite", lambda: "sonde")
        assert ps.main(["--dry-run", "--accepter-pertes"]) == 1

    def test_le_refus_tombe_AVANT_que_la_provenance_soit_fabriquee(self, monkeypatch):
        """L'ordre est le fond du correctif : une provenance calculee puis jetee
        laisserait la porte ouverte a un futur appelant qui la lirait plus tot."""
        monkeypatch.setattr(ps, "_socle_perime", lambda: None)
        monkeypatch.setattr(ps, "_socle_non_commite", lambda: "sonde")

        def jamais(*a, **k):
            raise AssertionError("la provenance a ete fabriquee malgre le refus")

        monkeypatch.setattr(ps, "ligne_provenance", jamais)
        assert ps.main(["--dry-run"]) == 1
