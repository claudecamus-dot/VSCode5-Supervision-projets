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
import io
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

    def _git(self, monkeypatch, blob=None, exc=None, rev="0f4e632"):
        """Ces trois tests simulaient `git status --porcelain`, l'oracle de la PREMIERE
        version de la porte. Le diagnostic du soir a montre que cet oracle confondait
        « propre » avec « la commande a echoue », ignorait `assume-unchanged` et
        pouvait fabriquer une impasse sous `core.autocrlf=true` : la porte compare
        desormais le CONTENU au blob HEAD. Les simulations suivent — un test qui
        continue de simuler l'ancien oracle ne mesure plus le code.
        """
        def faux_run(cmd, **kw):
            if exc is not None:
                raise exc
            if "rev-parse" in cmd:
                return types.SimpleNamespace(stdout=rev + "\n", stderr="", returncode=0)
            return types.SimpleNamespace(stdout=blob or "", stderr="", returncode=0)
        monkeypatch.setattr(ps.subprocess, "run", faux_run)

    def test_la_sonde_voit_un_socle_non_commite(self, monkeypatch):
        self._git(monkeypatch, blob="un socle qui n'est pas celui du disque")
        raison = ps._socle_non_commite()
        assert raison, "un socle modifie et non commite passe pour propageable"
        assert "agent-orchestrator" in raison, (
            "le refus ne nomme pas le fichier en cause")

    def test_un_socle_propre_ne_bloque_rien(self, monkeypatch):
        self._git(monkeypatch, blob=io.open(ps.SOCLE_SRC, encoding="utf-8").read())
        assert ps._socle_non_commite() is None

    def test_git_muet_BLOQUE_desormais(self, monkeypatch):
        """Changement de comportement assume le 2026-09-01, apres le diagnostic.

        La v1 faisait fail-open « comme `_socle_perime` ». Mais les deux ne repondent
        pas a la meme question : `_socle_perime` compare deux fichiers du disque et
        peut donc s'abstenir sans consequence, tandis que celle-ci decide s'il est
        licite d'ECRIRE une affirmation chez cinq tiers. Git injoignable, `hash_hub()`
        rend « inconnu » : la ligne de provenance designerait litteralement rien, et
        les copies porteraient cette phrase pour toute leur duree de vie. Ne pas
        propager coute une commande ; propager une provenance vide coute cinq depots
        dont plus personne ne sait de quoi ils descendent.
        """
        self._git(monkeypatch, exc=OSError("git absent"))
        raison = ps._socle_non_commite()
        assert raison and "inconnu" in raison, (
            "git injoignable laissait ecrire une provenance qui ne designe rien")

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


class TestLeCheminQuiEcritChezAutruiEstLeMoinsProtege:
    """Finding `propager_socle.py::traiter` (diagnostic du 2026-09-01, arbitre le jour
    meme). Trouve par `bmad-review-edge-case-hunter` en contexte frais, et PLUS GRAVE
    que le defaut de provenance qu'il accompagnait — le hunter a contredit la
    proposition du superviseur qui l'avait dispatche.

    Trois trous sur le seul chemin de ce depot qui ECRIT dans les dossiers d'autrui :

    1. `--accepter-pertes` DETRUIT SANS RIEN IMPRIMER. La cle `perdues` n'existe que
       dans le retour de refus ; le retour applique ne la porte pas, donc
       `main()` fait `r.get("perdues", [])` et affiche une liste vide pendant que des
       lignes disparaissent. Pire, son detail affirme « chapitre local preserve » au
       moment meme ou l'on vient de tolerer sa mutilation. Un drapeau qui existe pour
       ASSUMER une perte doit d'abord la MONTRER.
    2. Aucune verification de l'etat de la cible. Ecraser le fichier d'un depot ou une
       autre session a du travail non commite est la faute que R2 nomme, et rien ne
       l'empeche ici.
    3. Une seule cible illisible (encodage cp1252) fait exploser la boucle de `main()`
       APRES avoir deja reecrit les depots precedents et sans jamais atteindre les
       suivants — une propagation a moitie faite, dont personne n'a la liste.
    """

    def _cible(self, tmp_path, nom, socle, local_txt):
        racine = tmp_path / nom
        d = racine / ".claude" / "skills" / "agent-orchestrator"
        d.mkdir(parents=True)
        prov = ps.ligne_provenance("abc1234", "2026-09-01")
        io.open(d / "SKILL.md", "w", encoding="utf-8", newline="\n").write(
            ps.composer(socle, local_txt, prov))
        return str(racine)

    SOCLE = "# Titre\n\ntete du socle\n\n## Méthode — 5 étapes\n\ncorps du socle\n"

    def _cible_ligne_tissee(self, tmp_path, nom, local_txt, tissee):
        """Le cas reel du `--retrait-citation-mm 3.53` de VSCode2 : une ligne locale
        vit HORS du chapitre, tissee dans une section du socle. `composer()`
        reconstruit cette zone depuis le socle du hub, donc la ligne disparait sans
        etre reclamee — c'est la moitie du garde-fou qui compte vraiment.

        Ma premiere version de ces deux tests monkeypatchait `extraire_chapitre_local`
        pour fabriquer la perte. Elle ne pouvait pas marcher : `lignes_perdues` appelle
        elle-meme cette fonction sur l'avant ET sur l'apres, donc le patch rendait les
        deux chapitres identiques et la difference vide. Le test mesurait le patch, pas
        le code — la faute meme que la journee corrige.
        """
        racine = tmp_path / nom
        d = racine / ".claude" / "skills" / "agent-orchestrator"
        d.mkdir(parents=True)
        prov = ps.ligne_provenance("abc1234", "2026-09-01")
        contenu = ps.composer(self.SOCLE, local_txt, prov).replace(
            "tete du socle", "tete du socle\n" + tissee, 1)
        io.open(d / "SKILL.md", "w", encoding="utf-8", newline="\n").write(contenu)
        return str(racine)

    def test_le_chemin_applique_RECENSE_ce_qu_il_detruit(self, tmp_path, monkeypatch):
        racine = self._cible_ligne_tissee(
            tmp_path, "cible", "## Portée sur ce projet\n\nchapitre\n",
            "--retrait-citation-mm 3.53")
        monkeypatch.setattr(ps, "_cible_sale", lambda r: None)
        r = ps.traiter("cible", racine, self.SOCLE,
                       ps.ligne_provenance("abc1234", "2026-09-01"),
                       appliquer=True, tolerer_pertes=True)
        assert r["etat"] == "applique"
        assert r.get("perdues"), (
            "le chemin qui ECRIT ne rend pas la liste de ce qu'il a detruit : "
            "main() imprime une liste vide pendant que des lignes disparaissent")
        assert any("3.53" in l for l in r["perdues"])

    def test_le_detail_ne_ment_pas_en_annoncant_preserve(self, tmp_path, monkeypatch):
        racine = self._cible_ligne_tissee(
            tmp_path, "cible", "## Portée sur ce projet\n\nchapitre\n",
            "--retrait-citation-mm 3.53")
        monkeypatch.setattr(ps, "_cible_sale", lambda r: None)
        r = ps.traiter("cible", racine, self.SOCLE,
                       ps.ligne_provenance("abc1234", "2026-09-01"),
                       appliquer=True, tolerer_pertes=True)
        assert "perdue" in r["detail"].lower(), (
            "le detail dit « chapitre local preserve » juste apres l'avoir ampute")

    def test_une_cible_sale_bloque_l_ecriture(self, tmp_path, monkeypatch):
        """R2 : ne jamais ecraser du travail non commite qui n'est pas le notre."""
        local = "## Portée sur ce projet\n\nchapitre\n"
        racine = self._cible(tmp_path, "cible", self.SOCLE, local)
        monkeypatch.setattr(ps, "_cible_sale",
                            lambda r: "SKILL.md modifie et non commite chez la cible")
        r = ps.traiter("cible", racine, self.SOCLE + "ajout\n",
                       ps.ligne_provenance("abc1234", "2026-09-01"),
                       appliquer=True)
        assert r["etat"] == "CIBLE-SALE", (
            "on ecrase le travail non commite d'une autre session")

    def test_une_cible_illisible_n_interrompt_pas_les_suivantes(self, tmp_path,
                                                               monkeypatch):
        local = "## Portée sur ce projet\n\nchapitre\n"
        bonne = self._cible(tmp_path, "bonne", self.SOCLE, local)
        cassee = tmp_path / "cassee" / ".claude" / "skills" / "agent-orchestrator"
        cassee.mkdir(parents=True)
        # octets non decodables en utf-8 : le cas cp1252 du rapport
        io.open(cassee / "SKILL.md", "wb").write(b"## Port\xe9e sur ce projet\n")
        monkeypatch.setattr(ps, "_socle_perime", lambda: None)
        monkeypatch.setattr(ps, "_socle_non_commite", lambda: None)
        monkeypatch.setattr(ps, "_cible_sale", lambda r: None)
        monkeypatch.setattr(ps, "projets",
                            lambda: [("cassee", str(tmp_path / "cassee")),
                                     ("bonne", bonne)])
        code = ps.main(["--dry-run"])
        assert code == 1, "une cible illisible doit rendre la propagation incomplete"
        # la bonne cible a bien ete traitee malgre la cassee qui la precede
        r = ps.traiter("bonne", bonne, self.SOCLE,
                       ps.ligne_provenance("abc1234", "2026-09-01"), appliquer=False)
        assert r["etat"] in ("a-jour", "a-propager")

    def test_la_sonde_de_cible_sale_voit_un_fichier_modifie(self, monkeypatch):
        def faux_run(cmd, **kw):
            return types.SimpleNamespace(
                stdout=" M .claude/skills/agent-orchestrator/SKILL.md\n",
                stderr="", returncode=0)
        monkeypatch.setattr(ps.subprocess, "run", faux_run)
        assert ps._cible_sale("c:/peu/importe")

    def test_la_sonde_de_cible_sale_ne_bloque_pas_un_depot_propre(self, monkeypatch):
        def faux_run(cmd, **kw):
            return types.SimpleNamespace(stdout="", stderr="", returncode=0)
        monkeypatch.setattr(ps.subprocess, "run", faux_run)
        assert ps._cible_sale("c:/peu/importe") is None


class TestLaPorteNeConfondPasPropreEtEchoue:
    """5e occurrence de la famille, dans ma propre porte du matin (diagnostic du
    2026-09-01, arbitre le jour meme).

    `_socle_non_commite` v1 lisait `git status --porcelain` et ne regardait que
    `stdout`. Trois trous, tous du meme genre — la sonde ne mesure pas ce qu'elle dit :

    1. **Hors depot git**, `rc=128` et `stdout` vide : la porte repond « propre » et
       laisse ecrire une provenance qui ne designe rien. `hash_hub()` rend alors
       « inconnu », qui n'est pas une revision.
    2. **`git update-index --assume-unchanged`** : `status` reste vide alors que le
       fichier copie differe du blob HEAD. La porte laisse passer exactement le cas
       qu'elle existe pour attraper.
    3. **`core.autocrlf=true`** — la configuration REELLE de ce depot : le fichier de
       travail en CRLF pouvait faire crier `status` alors que son texte EST le blob, et
       le remede imprime (`git commit --`) sort « nothing to commit ». Refus non
       levable : une impasse, pire qu'un trou.

    Le correctif ne raffine pas la lecture de `status`, il change d'oracle : comparer le
    CONTENU au blob HEAD. C'est la seule question qui compte — « ce que je m'apprete a
    copier est-il ce que la provenance dira qu'il est ? » — et elle est insensible aux
    trois cas ci-dessus.
    """

    def _git(self, monkeypatch, rev="0f4e632", show=None, rc=0):
        def faux_run(cmd, **kw):
            if "rev-parse" in cmd:
                return types.SimpleNamespace(stdout=rev + "\n", stderr="", returncode=0)
            return types.SimpleNamespace(stdout=show or "", stderr="", returncode=rc)
        monkeypatch.setattr(ps.subprocess, "run", faux_run)

    def test_hors_depot_git_la_porte_refuse_au_lieu_de_dire_propre(self, monkeypatch):
        self._git(monkeypatch, rev="inconnu")
        raison = ps._socle_non_commite()
        assert raison, ("rc=128 + stdout vide se lisait « propre » : "
                        "la provenance aurait designe « inconnu »")

    def test_git_show_en_echec_refuse(self, monkeypatch):
        self._git(monkeypatch, rc=128, show="")
        assert ps._socle_non_commite(), "un git en echec ne prouve pas que le socle est commite"

    def test_un_socle_qui_differe_du_blob_HEAD_refuse(self, monkeypatch):
        self._git(monkeypatch, show="un contenu qui n'est pas celui du fichier")
        assert ps._socle_non_commite(), (
            "assume-unchanged rend status vide : seul le CONTENU tranche")

    def test_un_socle_identique_au_blob_HEAD_passe(self, monkeypatch):
        vivant = io.open(ps.SOCLE_SRC, encoding="utf-8").read()
        self._git(monkeypatch, show=vivant)
        assert ps._socle_non_commite() is None

    def test_le_CRLF_seul_ne_fabrique_pas_une_impasse(self, monkeypatch):
        """core.autocrlf=true est la config reelle du hub. Un refus dont le remede
        imprime sort « nothing to commit » est pire qu'un trou : on ne peut pas en
        sortir."""
        vivant = io.open(ps.SOCLE_SRC, encoding="utf-8").read()
        self._git(monkeypatch, show=vivant.replace("\n", "\r\n"))
        assert ps._socle_non_commite() is None, (
            "seules les fins de ligne different : refus sans remede possible")
