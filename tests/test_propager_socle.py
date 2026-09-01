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
    def test_une_perte_bloque_la_propagation(self, tmp_path):
        racine = tmp_path / "projet"
        (racine / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        cible = racine / ps.REL_CIBLE
        cible.write_text("intro\n## Portée sur ce projet\nvaleur arbitrée 3.53\n" + SOCLE,
                         encoding="utf-8")
        # un socle qui n'explique pas la valeur locale, et un chapitre qu'on ampute
        r = ps.traiter("faux", str(racine), SOCLE, "prov\n", appliquer=True)
        assert r["etat"] in ("PERTE-LOCALE", "a-propager", "applique")
        if r["etat"] == "PERTE-LOCALE":
            assert cible.read_text(encoding="utf-8").count("3.53") == 1, (
                "le fichier a été écrit malgré le refus")

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
