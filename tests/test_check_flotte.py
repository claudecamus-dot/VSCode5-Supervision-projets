"""`--check-flotte` : poser le garde-fou là où la dérive peut réellement se produire.

Finding `flotte:agent-orchestrator-socle-vs-local`, arbitré le 2026-09-01. `--check`
ne comparait que le hub à son propre `export/` — or les deux sont régénérés par la
même commande, donc c'est **le seul endroit où la dérive est impossible**. Pendant ce
temps les 6 copies de la flotte divergeaient sans que rien ne le dise : les 5 sections
de capacité ajoutées après le 2026-07-29 étaient absentes des 6, sans une exception.

Ce que la commande doit faire, et ne pas faire :

* **Rapporter trois états** — `identique`, `différent`, `absent` — par dépôt.
* **Ne jamais juger.** Un écart peut être une spécialisation R3 légitime : trois copies
  portent du texte local introuvable au hub, et les écraser détruirait ce travail. La
  commande informe, l'humain tranche.
* **Ne jamais écrire.** Elle lit des dépôts tiers ; une écriture y serait exactement la
  dette invisible que `flotte:canon-ecrit-jamais-commite` dénonce.
"""

import importlib.util
import io
import json
import os
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "export_agentic_flotte", os.path.join(HUB, ".claude", "dispositif", "export_agentic.py"))
ea = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ea)


def _sortie(argv):
    """Lance main(argv) en capturant stdout — la sortie EST le livrable ici."""
    tampon = io.StringIO()
    vrai = sys.stdout
    sys.stdout = tampon
    try:
        code = ea.main(argv)
    finally:
        sys.stdout = vrai
    return code, tampon.getvalue()


class TestLaCommandeExiste:
    def test_check_flotte_est_une_option(self):
        code, sortie = _sortie(["--check-flotte"])
        assert code == 0
        assert "total flotte" in sortie

    def test_elle_couvre_les_projets_declares(self):
        """Le périmètre vient de projets.json, pas d'une liste recopiée qui
        divergerait au premier projet ajouté.

        Le HUB est la seule exception, et elle est délibérée depuis le 2026-09-01 : il
        n'est pas une cible de propagation, se comparer à son propre `export/` est le
        travail de `--check`, et deux de ces écarts étaient structurellement insolubles
        (cf. `TestLeHubNEstPasSaPropreCible`).
        """
        with open(os.path.join(HUB, "projets.json"), encoding="utf-8") as fh:
            projets = json.load(fh)["projets"]
        _code, sortie = _sortie(["--check-flotte"])
        for p in projets:
            if os.path.abspath(p["chemin"]) == os.path.abspath(HUB):
                assert p["nom"] not in sortie, "le hub ne doit pas etre sa propre cible"
                continue
            assert p["nom"] in sortie, f"{p['nom']} absent du rapport"

    def test_elle_ignore_les_entrees_sans_destination(self):
        """Une entrée du manifeste peut être publiée sans être installable ;
        la comparer chez une cible plantait sur un dst à None."""
        assert len(ea.entrees_avec_destination()) < len(ea.MANIFESTE), (
            "ce test perd son objet si toutes les entrées ont une destination")
        code, _s = _sortie(["--check-flotte"])
        assert code == 0


class TestElleRapporteSansJuger:
    def test_les_trois_etats_sont_distingues(self):
        _code, sortie = _sortie(["--check-flotte"])
        assert "identique(s)" in sortie
        assert "different(s)" in sortie
        assert "absent(s)" in sortie

    def test_un_ecart_ne_vaut_pas_condamnation(self):
        """Le garde-fou doit DIRE qu'un écart peut être une spécialisation, sinon
        le prochain lecteur écrasera une copie locale en croyant corriger."""
        _code, sortie = _sortie(["--check-flotte"])
        assert "n'est PAS forcement une derive" in sortie

    def test_le_different_chiffre_les_deux_cotes(self):
        """« différent » sans volume ne dit pas s'il manque une ligne ou 400 :
        c'est cette différence-là qui distingue un patch d'un écart de génération."""
        _code, sortie = _sortie(["--check-flotte"])
        assert "chez la cible /" in sortie and "au hub)" in sortie

    def test_elle_n_ecrit_rien_chez_les_cibles(self):
        """Lecture seule : aucune mtime de dépôt tiers ne bouge."""
        with open(os.path.join(HUB, "projets.json"), encoding="utf-8") as fh:
            projets = [p for p in json.load(fh)["projets"]
                       if os.path.isdir(p["chemin"]) and p["chemin"] != HUB]
        cibles = []
        for p in projets[:3]:
            claude = os.path.join(p["chemin"], ".claude")
            if os.path.isdir(claude):
                cibles.append((claude, os.stat(claude).st_mtime))
        assert cibles, "aucune cible mesurable : le test perdrait son objet"
        _sortie(["--check-flotte"])
        for chemin, avant in cibles:
            assert os.stat(chemin).st_mtime == avant, f"{chemin} touche"


class TestLeCasQuiAJustifieLaCommande:
    def test_l_orchestrateur_de_la_flotte_est_bien_mesure(self):
        """Le fait qui a ouvert le finding : les copies flotte de la skill sont
        très en retard sur le hub. La commande doit le rendre visible — sans quoi
        elle n'aurait rien apporté de plus que `--check`."""
        _code, sortie = _sortie(["--check-flotte"])
        assert "agent-orchestrator/SKILL.md" in sortie


class TestSocleAJourNEstPasUneDerive:
    """Le piège que la propagation du 2026-09-01 a créé, et que ce test ferme.

    Une fois le fichier coupé socle/local, la copie cible ne peut PLUS être identique
    au kit publié : elle porte en plus son chapitre « Portée sur ce projet » et sa ligne
    de provenance. Sans distinction, `--check-flotte` classerait « différent » les cinq
    copies pour toujours — un signal constant, donc muet, et on reperdrait exactement ce
    qu'on venait de gagner : savoir si le socle est à jour ou en retard d'une génération.

    `_socle_a_jour` compare donc la seule partie que le hub possède — tout ce qui suit
    `## Méthode`. Le chapitre local, lui, n'a aucune raison de ressembler au hub.
    """

    def test_un_fichier_coupe_socle_local_est_classe_a_part(self):
        _code, sortie = _sortie(["--check-flotte"])
        assert "socle-a-jour+local" in sortie
        assert "SOCLE A JOUR" in sortie, (
            "aucune copie reconnue socle-à-jour : la coupe socle/local n'est pas vue")

    def test_la_skill_propagee_est_reconnue_a_jour_partout(self):
        """Les 5 dépôts ont reçu le socle : aucun ne doit apparaître en dérive sur ce
        fichier, sinon la propagation n'a pas fait ce qu'elle annonce."""
        _code, sortie = _sortie(["--check-flotte"])
        for bloc in sortie.split("\n\n"):
            if not bloc.strip().startswith(("VSCode", "VScode")):
                continue
            nom = bloc.split(" :")[0].strip()
            if nom == "VScode5":
                continue  # le hub n'est pas une cible de propagation
            lignes = [l for l in bloc.splitlines()
                      if "agent-orchestrator/SKILL.md" in l]
            assert lignes, f"{nom} : la skill n'apparaît pas au rapport"
            assert any("SOCLE A JOUR" in l for l in lignes), (
                f"{nom} : socle en retard ou dérive réelle sur agent-orchestrator")

    def test_un_socle_reellement_en_retard_reste_signale(self):
        """Le test qui empêche la distinction de devenir un blanchiment : si la partie
        générée diffère, le fichier retombe en DIFFERENT même s'il porte la provenance."""
        import importlib.util as _iu, os as _os
        s = _iu.spec_from_file_location("ea_probe", _os.path.join(
            HUB, ".claude", "dispositif", "export_agentic.py"))
        m = _iu.module_from_spec(s)
        s.loader.exec_module(m)
        publie = _os.path.join(HUB, "export", "skills", "agent-orchestrator", "SKILL.md")
        faux = _os.path.join(os.environ.get("TEMP", "."), "faux_socle.md")
        contenu = open(publie, encoding="utf-8").read()
        tete, suite = contenu.split(m.ANCRE_SOCLE, 1)
        with open(faux, "w", encoding="utf-8") as fh:
            fh.write(m.MARQUEUR_SOCLE + " socle : vieux -->\n" + tete
                     + m.ANCRE_SOCLE + suite.replace("Qualifier", "QUALIFIER", 1)
                     + "\nligne de retard\n")
        try:
            assert m._socle_a_jour(publie, faux) is False
        finally:
            _os.remove(faux)


class TestLaSignatureDePropagationNEstPasUneDerive:
    """Finding `.claude/dispositif/export_agentic.py --check-flotte`, arbitré le
    2026-09-01 (« traite tous les points de la page pilotage »).

    Le détecteur comptait en dérive la trace que la propagation écrit elle-même. Deux
    causes, et le finding n'en avait vu qu'une :

    1. le **bandeau « GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT »** (8 lignes, bandeau + ligne
       vide) que `sync_dispositif.build_content` ajoute en tête de chaque copie cible ;
    2. les **fins de ligne** : `sync_dispositif.write_crlf` écrit la cible en CRLF alors
       que le canon et `export/` sont en LF. Retirer le seul bandeau ne suffit donc pas —
       mesuré le 2026-09-01, la comparaison reste fausse sur les 5 dépôts.

    Classement mesuré des 104 « différents » annoncés avant correction : 12 bandeau+CRLF,
    4 CRLF seul, 88 dérives réelles — soit 16 faux positifs (15,4 %). Effet pervers : les
    deux seuls fichiers du canon (`scan_transcripts.py`, `log_run.py`) étaient DIFFERENT
    en permanence sur les 6 dépôts, donc une vraie dérive sur eux — les plus critiques —
    se serait noyée dans son propre bruit.

    Ces tests verrouillent la normalisation ET son garde-fou : elle ne doit pas devenir
    un blanchiment (`test_une_vraie_derive_reste_signalee`).
    """

    @staticmethod
    def _sync():
        s = importlib.util.spec_from_file_location(
            "sync_dispositif_probe",
            os.path.join(HUB, ".claude", "dispositif", "sync_dispositif.py"))
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        return m

    @staticmethod
    def _tmp(nom):
        """Chemin COURT : le scratchpad de session dépasse MAX_PATH et fabrique de
        faux échecs sous Windows."""
        base = r"C:\tmp"
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, nom)

    def _copie_propagee(self, nom_canon, nom_tmp, mutation=None):
        """Reproduit EXACTEMENT ce que la propagation écrit chez une cible : le
        bandeau au format de `sync_dispositif`, puis le canon, le tout en CRLF."""
        sync = self._sync()
        contenu = sync.build_content(nom_canon)      # bandeau + canon, en LF
        if mutation:
            contenu = mutation(contenu)
        chemin = self._tmp(nom_tmp)
        sync.write_crlf(chemin, contenu)             # ... puis CRLF, comme chez la cible
        return chemin

    def test_une_copie_fraichement_propagee_n_est_pas_une_derive(self):
        """Le cas que le détecteur maîtrise parfaitement — un fichier qu'il vient
        lui-même de synchroniser — et sur lequel il se trompait."""
        publie = os.path.join(HUB, "export", "supervision", "scan_transcripts.py")
        copie = self._copie_propagee("scan_transcripts.py", "sonde_propagee.py")
        try:
            assert ea._identiques(publie, copie) is False, (
                "ce test perd son objet si la comparaison octet les dit déjà égaux")
            assert ea._signature_propagation(publie, copie) is True, (
                "une copie fraîchement propagée est comptée en dérive")
        finally:
            os.remove(copie)

    def test_le_crlf_seul_suffit_a_fausser_le_verdict(self):
        """4 des 16 faux positifs mesurés n'ont PAS de bandeau : seules leurs fins
        de ligne diffèrent. Corriger le bandeau sans corriger le CRLF les laisserait."""
        sync = self._sync()
        publie = os.path.join(HUB, "export", "orchestration", "playbooks", "FORMAT.md")
        copie = self._tmp("sonde_crlf.md")
        sync.write_crlf(copie, sync.read_lf(publie))
        try:
            assert ea._identiques(publie, copie) is False
            assert ea._signature_propagation(publie, copie) is True
        finally:
            os.remove(copie)

    def test_une_vraie_derive_reste_signalee(self):
        """Le garde-fou du garde-fou : la normalisation ne doit blanchir que la
        signature de propagation, jamais une ligne de code réellement changée."""
        publie = os.path.join(HUB, "export", "supervision", "scan_transcripts.py")
        copie = self._copie_propagee(
            "scan_transcripts.py", "sonde_derive.py",
            mutation=lambda t: t + "\n# ligne ajoutee localement\n")
        try:
            assert ea._signature_propagation(publie, copie) is False, (
                "une dérive réelle est blanchie par la normalisation")
        finally:
            os.remove(copie)

    def test_le_rapport_distingue_la_signature_du_different(self):
        """Un 4e état affiché : sans lui, le total continuerait de mélanger
        signature de propagation et dérive réelle."""
        _code, sortie = _sortie(["--check-flotte"])
        assert "signature(s)" in sortie, "le 4e état n'est pas compté au rapport"
        assert "SIGNATURE" in sortie, "aucune ligne SIGNATURE : rien n'est reclassé"

    def test_les_deux_fichiers_du_canon_ne_sont_plus_en_derive(self):
        """Le fait mesuré du finding : `scan_transcripts.py` et `log_run.py` étaient
        DIFFERENT sur les 6 dépôts (12 entrées) alors que leur corps est identique."""
        _code, sortie = _sortie(["--check-flotte"])
        for ligne in sortie.splitlines():
            if not ligne.strip().startswith("DIFFERENT"):
                continue
            for canon in ("supervision/scan_transcripts.py", "orchestration/log_run.py"):
                assert canon not in ligne, (
                    f"le canon {canon} est encore compté en dérive : {ligne.strip()}")


class TestLeHubNEstPasSaPropreCible:
    """Défaut `export_agentic.py:370-378`, audit du 2026-09-01.

    `_projets_flotte()` n'excluait pas le hub, contrairement à `propager_socle.projets()`
    qui le fait depuis toujours (`os.path.abspath(p["chemin"]) != HUB`). `--check-flotte`
    comparait donc le hub à son propre `export/` — c'est-à-dire une chose à sa propre
    copie, ce que `--check` fait déjà et mieux.

    Pire, deux de ces écarts sont **structurellement insolubles** : `remind_revue_increment`
    et `warn_verif_before_commit` sont sourcés depuis VSCode3 parce que la version du hub
    est spécialisée « canal hub ». Le hub apparaissait donc éternellement en dérive de
    lui-même sur deux fichiers qu'aucune correction ne pourra jamais aligner — du bruit
    permanent dans le compteur, la même famille que les 16 faux positifs corrigés le
    matin même.
    """

    def test_le_hub_est_absent_du_rapport_de_flotte(self):
        noms = [n for n, _c in ea._projets_flotte()]
        assert "VScode5" not in noms, (
            "le hub se compare a son propre export/ : c'est --check qui fait ca")

    def test_les_cibles_reelles_restent_toutes_couvertes(self):
        """Exclure le hub ne doit pas amputer la flotte."""
        with open(os.path.join(HUB, "projets.json"), encoding="utf-8") as fh:
            declares = [p["nom"] for p in json.load(fh)["projets"]]
        couverts = [n for n, _c in ea._projets_flotte()]
        assert set(couverts) == set(declares) - {"VScode5"}

    def test_les_deux_scripts_excluent_le_hub_de_la_meme_facon(self):
        """La divergence venait de ce que deux scripts répondaient différemment à la
        même question. Ce test les lie."""
        s = importlib.util.spec_from_file_location(
            "propager_socle_ref",
            os.path.join(HUB, ".claude", "dispositif", "propager_socle.py"))
        ps = importlib.util.module_from_spec(s)
        s.loader.exec_module(ps)
        assert {n for n, _c in ea._projets_flotte()} == {n for n, _c in ps.projets()}


class TestLesCodesDeSortieSontExploitables:
    """Défaut `export_agentic.py:456`, audit du 2026-09-01.

    `verifier_flotte()` rendait 0 en TOUTES circonstances — y compris quand aucun projet
    de flotte n'était déclaré, c'est-à-dire quand il n'avait rien pu comparer. « Je n'ai
    rien vérifié » et « tout va bien » sortaient le même code, donc aucun appelant ne
    pouvait les distinguer.

    Le code reste 0 quand un RAPPORT a été produit, même avec des écarts : la commande
    informe, elle ne juge pas (« un écart n'est PAS forcément une dérive »). En faire un
    portail ferait échouer 88 fois sur des spécialisations R3 légitimes.
    """

    def test_un_rapport_produit_sort_a_zero_meme_avec_des_ecarts(self):
        code, sortie = _sortie(["--check-flotte"])
        assert "different(s)" in sortie
        assert code == 0, "un ecart legitime ne doit pas faire echouer la commande"

    def test_ne_rien_avoir_a_comparer_n_est_pas_un_succes(self, monkeypatch):
        monkeypatch.setattr(ea, "_projets_flotte", lambda: [])
        code, sortie = _sortie(["--check-flotte"])
        assert code != 0, (
            "aucune cible a comparer sort a 0 : « rien verifie » se lit « tout va bien »")
        # Le message part sur stderr — c'est une condition d'erreur, pas un rapport ;
        # `_sortie` ne capte que stdout, d'où la vérification par la négative.
        assert "total flotte" not in sortie, (
            "un rapport de flotte est affiche alors qu'il n'y avait rien a comparer")
