"""Verrou du routage des salles vers l'orchestrateur (demande utilisateur 2026-08-31).

Pourquoi ce fichier existe. Les 9 salles de table ronde étaient parfaitement décrites
dans l'onglet Dispositif du wiki — casting résolu, commande à taper, situation d'usage —
et **totalement invisibles de l'orchestrateur** : sa seule mention était la ligne
générique `bmad-party-mode` de la table BMAD, en régime « proposé ». Le mode d'emploi
vivait donc dans le GÉNÉRATEUR DU WIKI (`PARTY_SITUATIONS`), c'est-à-dire dans un
producteur de HTML que le plan ne lit jamais. Constat de l'utilisateur : « je n'ai pas
l'impression qu'elles soient lancées lors de mes demandes ».

L'invariant gardé ici est celui qui a manqué : **le routage de la skill et les salles
réelles ne doivent pas pouvoir diverger.** Une salle citée par la skill mais absente du
TOML est un mode d'emploi mort ; une salle du TOML absente de la skill est une salle
inatteignable depuis une demande — exactement l'état d'avant. C'est la même leçon que
`referentiel:deux-sources-qui-se-contredisent`, corrigé le même jour : deux exemplaires
d'une même vérité divergent dès que l'un bouge.

Ces tests interrogent l'OBJET CHARGÉ (le TOML résolu comme le fait le vrai résolveur,
via `party_collectif()`), jamais une sous-chaîne du fichier entier — règle générale
retenue de l'arbitrage sur les tests vacants du 2026-08-31.
"""

import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")
MARQUEUR_DEBUT = "<!-- SALLES-ROUTAGE:START"
MARQUEUR_FIN = "<!-- SALLES-ROUTAGE:END -->"

spec = importlib.util.spec_from_file_location(
    "scan_projets_salles", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _bloc_routage():
    """Le contenu ENTRE les marqueurs — pas le fichier entier.

    Cibler le bloc et non le fichier est ce qui empêche le test d'être vert par
    accident : `atelier-idees` apparaît aussi dans la prose de la section, et un test
    qui chercherait dans tout SKILL.md resterait vert après suppression de la table.
    """
    source = open(SKILL, encoding="utf-8").read()
    debut = source.index(MARQUEUR_DEBUT)
    fin = source.index(MARQUEUR_FIN)
    return source[debut:fin]


def _section_salles():
    """La section « 2 septies » entière (prose + table), sans le reste de la skill."""
    source = open(SKILL, encoding="utf-8").read()
    debut = source.index("### 2 septies.")
    return source[debut:source.index("### 3. Valider")]


def _salles_reelles():
    """Les identifiants de salle résolus comme le fait `resolve_party.py`."""
    _membres, groupes = scan.party_collectif()
    return {g["id"] for g in groupes}


def _salles_routees():
    """Les identifiants cités dans la table de routage de la skill."""
    return set(re.findall(r"`([a-z0-9-]+)`", _bloc_routage()))


class TestPasDeDivergence:
    def test_toute_salle_citee_par_la_skill_existe_vraiment(self):
        """Un routage vers une salle supprimée enverrait l'orchestrateur dans le vide."""
        reelles = _salles_reelles()
        fantomes = sorted(_salles_routees() - reelles)
        assert not fantomes, (
            f"salle(s) routee(s) mais absente(s) du TOML : {fantomes} "
            f"(salles reelles : {sorted(reelles)})")

    def test_toute_salle_reelle_est_atteignable_depuis_une_demande(self):
        """Le defaut d'origine : une salle qui existe mais que rien ne declenche."""
        orphelines = sorted(_salles_reelles() - _salles_routees())
        assert not orphelines, (
            f"salle(s) du TOML jamais routee(s), donc inatteignable(s) depuis une "
            f"demande utilisateur : {orphelines}")

    def test_le_compte_correspond_a_ce_que_le_wiki_affiche(self):
        """La skill et l'onglet Dispositif parlent des memes salles, en meme nombre."""
        assert len(_salles_routees()) == len(_salles_reelles())


class TestLaRegleEstUtilisable:
    def test_la_commande_est_celle_que_le_wiki_affiche(self):
        """Une commande qui differe de celle du wiki, c'est deja deux sources."""
        section = _section_salles()
        assert "/bmad-party-mode --party" in section
        assert "--mode subagent" in section

    def test_le_mode_subagent_est_justifie_et_pas_seulement_prescrit(self):
        """`session` fait jouer toutes les voix par une seule : aucun debat reel.

        Sans cette justification, la consigne « --mode subagent » est un rituel que le
        premier souci de cout fera sauter.
        """
        section = _section_salles().lower()
        assert "session" in section and "une seule" in section

    def test_la_regle_dit_AUSSI_quand_ne_pas_convoquer(self):
        """Une regle qui ne dit que « convoque » fait convoquer sur « regenere le wiki ».

        Le cas negatif est ce qui rend la regle applicable : sans lui, elle est soit
        ignoree, soit appliquee partout.
        """
        section = _section_salles()
        assert "ne pas convoquer" in section

    def test_le_garde_fou_la_salle_n_ecrit_rien_est_ecrit(self):
        """Une salle qui produirait un diff serait un sous-agent mal brief."""
        section = _section_salles()
        assert "ne modifie aucun fichier" in section

    def test_la_sortie_de_la_salle_doit_etre_reprise_dans_le_plan(self):
        """Une salle tenue puis oubliee est une depense sans achat."""
        section = _section_salles()
        assert "compte rendu" in section and "plan" in section


class TestSituationsDuWiki:
    def test_chaque_situation_du_wiki_pointe_une_salle_routee(self):
        """Le wiki et la skill doivent envoyer au meme endroit pour une meme situation.

        `PARTY_SITUATIONS` est la table curatee que l'onglet Dispositif affiche ; si
        elle proposait une salle que l'orchestrateur ne route pas, l'humain et l'agent
        n'ouvriraient pas la meme porte.
        """
        routees = _salles_routees()
        manquantes = sorted({salle for _sit, salle, _p, _s in scan.PARTY_SITUATIONS}
                            - routees)
        assert not manquantes, (
            f"situation(s) du wiki pointant une salle non routee : {manquantes}")
