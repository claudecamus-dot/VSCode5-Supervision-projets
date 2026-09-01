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
        divergerait au premier projet ajouté."""
        with open(os.path.join(HUB, "projets.json"), encoding="utf-8") as fh:
            projets = json.load(fh)["projets"]
        _code, sortie = _sortie(["--check-flotte"])
        for p in projets:
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
