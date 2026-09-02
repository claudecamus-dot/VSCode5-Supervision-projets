"""Les salles portent les skills BMAD qu'elles doivent réellement charger.

Demande utilisateur du 2026-09-02 : « dans l'onglet pilotage 44 sur 46 skills ne sont
jamais utilisées, raccorde aux salles et fais en sorte que l'agent orchestre puisse les
déclencher ».

CE QUE LE CHIFFRE MÉLANGE, et pourquoi « 44 → 0 » n'est pas la cible. Les 46 skills BMAD
se répartissent en trois familles que le compteur traite pareil :

- **13 « d'office »** — bornées, ne rendant qu'un rapport, n'écrivant aucun fichier. Ce
  sont les SEULES qui peuvent vivre dans une salle : une table ronde ne modifie aucun
  fichier, y router une skill qui écrit casserait son invariant, c'est-à-dire la garde de
  R4 contre une auto-application collective.
- **29 « proposé »** — elles coûtent cher ou écrivent un fichier réel (PRD, architecture,
  epics, stories, code). Elles restent atteignables par le porteur ou en inline, sur
  arbitrage. Beaucoup n'ont simplement aucun objet sur ce hub, qui ne produit pas de
  livrable applicatif : `bmad-sprint-planning` y produirait un artefact sans lecteur.
- **4 dépréciées par BMAD** — les compter « jamais utilisées » est un faux négatif : elles
  ne doivent JAMAIS partir.

Forcer une skill à s'exécuter pour faire tomber un compteur serait du théâtre, et le
compteur mesurerait alors sa propre complaisance. Ce qui se corrige ici est autre chose :
qu'aucune des 13 utilisables ne soit ORPHELINE — sans salle qui la nomme, donc sans chemin
par lequel elle puisse partir.

POURQUOI PAR LES SALLES. La mesure du 2026-09-02 est sans appel sur le mécanisme qui
marche : les 2 seules skills BMAD jamais invoquées le sont **sans porteur** —
`bmad-party-mode` 7 fois (par les salles) et `bmad-customize` 1 fois. Le porteur
`bmad-revue`, lui, a tourné 5 fois sans en charger une seule. Les salles sont donc le seul
canal dont l'usage soit prouvé ; c'est là qu'on raccorde.

LIMITE ASSUMÉE, écrite ici pour qu'on ne la redécouvre pas : `resolve_party.py` (script
livré par BMAD) ne remonte PAS `skills_bmad` — il ne rend qu'un jeu de clés fixe. C'est
l'orchestrateur qui lit le TOML, ce que le § 2 septies lui impose déjà pour le manifeste
de la salle. Patcher le résolveur aurait été plus direct et se serait perdu à la première
mise à jour de la skill.
"""

import io
import os
import re
import tomllib

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOML = os.path.join(HUB, "_bmad", "custom", "bmad-party-mode.toml")
SKILL_ORCHESTRATEUR = os.path.join(
    HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")
SKILLS_DIR = os.path.join(HUB, ".claude", "skills")


def salles():
    with open(TOML, "rb") as fh:
        data = tomllib.load(fh)
    return {g["id"]: g for g in data["workflow"]["party_groups"]}


def skills_d_office():
    """Les skills que la table de routage déclare « d'office » — colonne 2 des rangées."""
    texte = io.open(SKILL_ORCHESTRATEUR, encoding="utf-8").read()
    debut = texte.find("BMAD-ROUTAGE:START")
    fin = texte.find("BMAD-ROUTAGE:END")
    noms = set()
    for ligne in texte[debut:fin].splitlines():
        ligne = ligne.strip()
        if not ligne.startswith("|"):
            continue
        cellules = [c.strip() for c in ligne.strip("|").split("|")]
        if len(cellules) < 4:
            continue
        nom = cellules[1].strip("`").strip()
        if nom.startswith("bmad-") and "d'office" in cellules[3]:
            noms.add(nom)
    # Sans cette garde, un marqueur renommé rend `texte[-1:-1]` = "" et un ensemble vide :
    # « aucune orpheline » devenait vrai en ne vérifiant plus rien (revue du 2026-09-02).
    assert noms, "table BMAD-ROUTAGE introuvable ou sans rangée « d'office »"
    return noms


class TestLaMatiereDuTestEstLa:
    """Les classes paramétrées sur `salles()` disparaissent sans échouer si le TOML se
    vide ; le dictionnaire par `id` fusionne deux salles homonymes en silence."""

    def test_douze_salles_distinctes(self):
        with open(TOML, "rb") as fh:
            groupes = tomllib.load(fh)["workflow"]["party_groups"]
        ids = [g["id"] for g in groupes]
        assert len(ids) == len(set(ids)), f"identifiants de salle en double : {ids}"
        assert len(ids) == 12, f"{len(ids)} salles, la skill d'orchestration en annonce 12"

    def test_treize_skills_d_office(self):
        """Le « 13 » du paragraphe de SKILL.md est mesuré ici, pas affirmé."""
        assert len(skills_d_office()) == 13, sorted(skills_d_office())


class TestChaqueSalleNommeSesSkills:
    @pytest.mark.parametrize("salle", sorted(salles()))
    def test_la_salle_declare_au_moins_une_skill(self, salle):
        """Une salle sans skill nommée ne peut en charger aucune : ses voix partent avec
        un contexte vierge et n'ont pas la table de routage."""
        declarees = salles()[salle].get("skills_bmad")
        assert declarees, f"{salle} ne nomme aucune skill BMAD"

    @pytest.mark.parametrize("salle", sorted(salles()))
    def test_les_skills_nommees_sont_installees(self, salle):
        for nom in salles()[salle].get("skills_bmad") or []:
            assert os.path.isdir(os.path.join(SKILLS_DIR, nom)), (
                f"{salle} route {nom}, qui n'est pas installée ici")


class TestUneSalleNeRouteQueDuRapport:
    """La salle ne modifie AUCUN fichier — c'est son invariant, et la garde de R4 contre
    une auto-application collective. Y router une skill qui écrit le casserait."""

    @pytest.mark.parametrize("salle", sorted(salles()))
    def test_aucune_skill_qui_ecrit_un_fichier(self, salle):
        office = skills_d_office()
        for nom in salles()[salle].get("skills_bmad") or []:
            assert nom in office, (
                f"{salle} route {nom}, qui n'est pas en régime « d'office » : elle coûte "
                "cher ou écrit un fichier réel, et une salle ne produit qu'un compte rendu")


class TestAucuneSkillUtilisableNestOrpheline:
    def test_les_13_d_office_sont_toutes_atteignables_par_une_salle(self):
        """C'est la cible réelle de la demande — pas « 44 → 0 », mais « aucune des
        utilisables sans chemin »."""
        couvertes = set()
        for g in salles().values():
            couvertes |= set(g.get("skills_bmad") or [])
        orphelines = sorted(skills_d_office() - couvertes)
        assert not orphelines, (
            "ces skills ne rendent qu'un rapport, donc elles POURRAIENT vivre dans une "
            f"salle, et aucune ne les nomme : {orphelines}")


class TestLOrchestrateurSaitLesDeclencher:
    def test_le_paragraphe_des_salles_impose_de_passer_les_skills_au_brief(self):
        """Déclarer une skill dans le TOML ne la fait pas partir : ce sont les voix qui
        l'invoquent, et elles ne lisent que le brief qu'on leur écrit."""
        texte = io.open(SKILL_ORCHESTRATEUR, encoding="utf-8").read()
        bloc = re.search(r"### 2 septies(.+?)(?:### 3\.|\Z)", texte, re.S)
        assert bloc, "le paragraphe 2 septies a disparu"
        corps = bloc.group(1).lower()
        assert "skills_bmad" in corps, (
            "le paragraphe qui convoque les salles ne dit nulle part de lire "
            "`skills_bmad` ni de le passer dans le brief des voix — la donnée serait "
            "écrite et jamais lue, exactement le défaut qu'on corrige")
