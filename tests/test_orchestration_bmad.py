"""Verrou de l'intégration BMAD au workflow de l'orchestrateur (2026-07-30).

Le TODO `agent-mort` du wiki disait : 46 skills BMAD installées, **0 invocation sur
113 sessions**. Cause mesurée : la règle « uniquement sur demande explicite, via
bmad-help » — une skill que personne ne nomme n'est jamais invoquée. L'arbitrage
utilisateur a remplacé cette règle par une table de routage besoin → skill →
sous-agent porteur → régime de déclenchement.

Ces tests protègent l'invariant qui fait vivre la table : **toute skill bmad-*
installée y figure** (sinon elle retombe silencieusement dans l'oubli qu'on vient de
corriger), et **tout sous-agent cité existe** (une table qui route vers un agent
absent est une panne à l'exécution). Ils testent des FICHIERS de configuration, ce
qui est le seul moyen de tester du dispositif déclaratif.
"""

import os
import re

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(HUB, ".claude", "skills")
AGENTS_DIR = os.path.join(HUB, ".claude", "agents")
ORCHESTRATEUR = os.path.join(SKILLS_DIR, "agent-orchestrator", "SKILL.md")
MARQUEUR_DEBUT = "<!-- BMAD-ROUTAGE:START"
MARQUEUR_FIN = "<!-- BMAD-ROUTAGE:END -->"

MODELES_VALIDES = {"haiku", "sonnet", "opus", "fable", "inherit"}


def lire(chemin):
    with open(chemin, encoding="utf-8") as fh:
        return fh.read()


def bmad_installees():
    """Les skills bmad-* réellement présentes sur le disque."""
    return sorted(
        d for d in os.listdir(SKILLS_DIR)
        if d.startswith("bmad-")
        and os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md")))


def bloc_routage():
    txt = lire(ORCHESTRATEUR)
    debut = txt.index(MARQUEUR_DEBUT)
    fin = txt.index(MARQUEUR_FIN)
    return txt[debut:fin]


def lignes_routage():
    """(besoin, skill, sous-agent porteur, déclenchement) par ligne de la table."""
    out = []
    for ligne in bloc_routage().splitlines():
        cols = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cols) != 4 or cols[0].startswith("---") or cols[0] == "Besoin détecté dans la demande":
            continue
        skill = re.fullmatch(r"`([a-z0-9-]+)`", cols[1])
        porteur = re.fullmatch(r"`([a-z0-9-]+)`", cols[2])
        if not (skill and porteur):
            continue
        out.append((cols[0], skill.group(1), porteur.group(1), cols[3]))
    return out


def depreciees():
    """Les skills que BMAD a consolidées : présentes mais jamais routées."""
    txt = bloc_routage()
    zone = txt.split("**Dépréciées")[-1]
    return set(re.findall(r"`(bmad-[a-z0-9-]+)`", zone))


def agents_installes():
    return sorted(f[:-3] for f in os.listdir(AGENTS_DIR) if f.endswith(".md"))


def frontmatter(chemin):
    txt = lire(chemin)
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    assert m, f"{chemin} : pas de frontmatter YAML"
    out = {}
    for ligne in m.group(1).splitlines():
        cle, sep, val = ligne.partition(":")
        if not sep or cle != cle.strip():
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[cle.strip()] = val
    return out


class TestTableDeRoutage:
    def test_toute_skill_bmad_installee_est_routee_ou_declaree_depreciee(self):
        """LE test de l'incrément : une skill installée hors table est une skill
        qui redevient invisible — exactement le trou de 46/46 qu'on vient de fermer."""
        routees = {skill for _, skill, _, _ in lignes_routage()}
        couvertes = routees | depreciees()
        oubliees = sorted(set(bmad_installees()) - couvertes)
        assert not oubliees, (
            "skills BMAD installées mais absentes de la table de routage de "
            f"agent-orchestrator/SKILL.md : {oubliees}")

    def test_aucune_skill_fantome_dans_la_table(self):
        """Router vers une skill non installée casse à l'invocation."""
        installees = set(bmad_installees())
        fantomes = sorted(
            {s for _, s, _, _ in lignes_routage()} - installees) + sorted(
            depreciees() - installees)
        assert not fantomes, f"skills routées mais absentes du disque : {fantomes}"

    def test_chaque_porteur_existe_dans_claude_agents(self):
        presents = set(agents_installes())
        manquants = sorted({p for _, _, p, _ in lignes_routage()} - presents)
        assert not manquants, f"sous-agents porteurs cités mais absents : {manquants}"

    def test_les_deux_regimes_seulement(self):
        regimes = {d for _, _, _, d in lignes_routage()}
        assert regimes == {"d'office", "proposé"}, regimes

    def test_les_46_sont_bien_46(self):
        """Si BMAD est mis à jour, ce compte bouge — et la table doit bouger avec
        (le test précédent le dira). Le nombre est ici pour rendre l'écart visible."""
        assert len(bmad_installees()) == 46

    def test_les_structurantes_ne_sont_jamais_en_declenchement_d_office(self):
        """Garde-fou de coût : PRD, architecture, stories, code et party-mode
        engagent des minutes et une facture — ils s'annoncent avant de partir."""
        structurantes = {
            "bmad-prd", "bmad-architecture", "bmad-dev-story", "bmad-dev-auto",
            "bmad-quick-dev", "bmad-create-epics-and-stories", "bmad-party-mode",
        }
        fautives = [s for _, s, _, d in lignes_routage()
                    if s in structurantes and d != "proposé"]
        assert not fautives, fautives

    def test_l_ancienne_regle_de_blocage_a_disparu(self):
        """Non-régression du changement demandé : la mention qui produisait
        0 invocation ne doit pas revenir par un copier-coller."""
        txt = lire(ORCHESTRATEUR)
        assert "Uniquement sur demande explicite" not in txt


class TestFrontmatterDesSousAgents:
    def test_il_y_a_des_sous_agents(self):
        assert agents_installes(), ".claude/agents/ est vide"

    def test_nom_du_frontmatter_egale_nom_du_fichier(self):
        """Claude Code résout un subagent_type par son `name` : un décalage avec le
        nom de fichier rend l'agent introuvable alors qu'il est là."""
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            assert fm.get("name") == nom, (nom, fm.get("name"))

    def test_description_non_vide(self):
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            assert len(fm.get("description", "")) > 40, nom

    def test_modele_dans_le_vocabulaire_connu_ou_absent(self):
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            if "model" in fm:
                assert fm["model"] in MODELES_VALIDES, (nom, fm["model"])

    @pytest.mark.parametrize("nom", [
        "bmad-revue", "bmad-doc", "bmad-recherche", "bmad-cadrage", "bmad-livraison",
        "veille-agentic", "agent-supervisor", "agent-orchestrator",
    ])
    def test_les_porteurs_ont_bien_l_outil_skill(self, nom):
        """Sans l'outil `Skill`, un sous-agent ne peut pas invoquer la skill qu'il
        porte — et l'étage 1 ne compterait rien (c'est le cas connu de ppt-designer)."""
        fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
        outils = [o.strip() for o in fm.get("tools", "").split(",")]
        assert "Skill" in outils, (nom, outils)

    def test_le_superviseur_n_a_ni_write_ni_edit(self):
        """Garde-fou STRUCTUREL de R4 : le superviseur propose, il n'applique pas.
        Sans outil d'écriture, il ne peut ni éditer diagnostic.json à la main, ni
        toucher au wiki généré, ni « corriger » au passage. Retirer cette contrainte
        rend la gouvernance déclarative au lieu d'effective."""
        fm = frontmatter(os.path.join(AGENTS_DIR, "agent-supervisor.md"))
        outils = {o.strip() for o in fm.get("tools", "").split(",")}
        assert "Write" not in outils and "Edit" not in outils, outils

    def test_aucun_sous_agent_ne_recoit_l_outil_de_commit(self):
        """L'irréversible reste à la session principale : aucun sous-agent n'a de
        raison de porter un outil dédié au commit."""
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            outils = {o.strip() for o in fm.get("tools", "").split(",")}
            assert not (outils & {"Commit", "Git"}), (nom, outils)


class TestCommandeOrchestre:
    def test_la_commande_existe_et_charge_la_skill(self):
        chemin = os.path.join(HUB, ".claude", "commands", "orchestre.md")
        assert os.path.isfile(chemin)
        txt = lire(chemin)
        assert "agent-orchestrator" in txt
        assert "$ARGUMENTS" in txt
