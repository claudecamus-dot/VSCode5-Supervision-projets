"""Les salles partent dans le kit d'export, et l'atelier de dev monte en qualité.

Demande utilisateur du 2026-08-31 : « rajoute dans le répertoire export le
déploiement des salles vers les autres projets, avec un focus pour la salle de dev
à structurer en augmentant le niveau de qualité, en ajoutant un expert en revue de
code et un expert en architecture de code ».

État mesuré avant le chantier : `export/` publiait 47 fichiers — skills de pilotage,
sous-agents, hooks, playbooks, canon — mais AUCUNE salle. Les 9 tables rondes du hub
vivaient dans `_bmad/custom/bmad-party-mode.toml`, un fichier hors manifeste : un
projet qui installait le kit héritait de l'orchestrateur ET de sa section 2 septies
(« convoquer une salle »), donc d'une skill qui référence des salles introuvables
chez lui. Le même défaut, un cran plus loin, que celui corrigé le 2026-08-31 quand
la table situation→salle vivait dans un générateur que le plan ne lisait jamais.

Deux invariants tenus ici :

1. **Le TOML est dans le manifeste, à une destination hors `.claude/`** — c'est le
   premier fichier du kit dans ce cas (`_bmad/custom/`), et l'installateur doit le
   poser là sans le replier sous `.claude/`.
2. **L'atelier de dev reste à 5 voix** malgré ses deux experts neufs : le plafond
   3-5 (arbitrage `veille:agent-teams` du 2026-07-29) n'est pas négociable — une
   6e voix serait une session facturée de plus à chaque tour. La place se prend
   donc sur une voix dont le mandat est déjà porté, pas en poussant le mur.
"""

import importlib.util
import json
import os
import tomllib

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOML = os.path.join(HUB, "_bmad", "custom", "bmad-party-mode.toml")

_spec = importlib.util.spec_from_file_location(
    "export_agentic_salles", os.path.join(HUB, ".claude", "dispositif", "export_agentic.py"))
export_agentic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_agentic)

_spec2 = importlib.util.spec_from_file_location(
    "scan_projets_salles", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(scan)


def _toml():
    with open(TOML, "rb") as fh:
        return tomllib.load(fh)["workflow"]


def _salle(sid):
    return next(g for g in _toml()["party_groups"] if g["id"] == sid)


def _membre(code):
    return next(m for m in _toml()["party_members"] if m["code"] == code)


class TestSallesDansLeKit:
    def test_le_toml_des_salles_est_au_manifeste(self):
        rels = [rel for _src, rel, _dst in export_agentic.MANIFESTE]
        assert "party/bmad-party-mode.toml" in rels

    def test_la_destination_sort_de_claude_et_vise_bmad_custom(self):
        """Un override BMAD ne vit PAS sous .claude/ : la skill le cherche dans
        _bmad/custom/. Le poser ailleurs le rendrait inerte en silence."""
        dst = next(d for _s, rel, d in export_agentic.MANIFESTE
                   if rel == "party/bmad-party-mode.toml")
        assert dst == "_bmad/custom/bmad-party-mode.toml"

    def test_la_source_est_le_fichier_vivant_du_hub(self):
        src = next(s for s, rel, _d in export_agentic.MANIFESTE
                   if rel == "party/bmad-party-mode.toml")
        assert os.path.isfile(src)
        assert os.path.samefile(src, TOML), (
            "la source doit être le TOML que le hub fait vivre, pas une copie")

    def test_le_kit_publie_porte_le_fichier_a_jour(self):
        """Le kit publié doit être régénéré : `--check` est le garde-fou, ce test
        est sa version qui échoue AVANT le commit."""
        publie = os.path.join(HUB, "export", "party", "bmad-party-mode.toml")
        assert os.path.isfile(publie), "export/ non régénéré après ajout au manifeste"
        with open(publie, "rb") as a, open(TOML, "rb") as b:
            assert a.read() == b.read()

    def test_le_manifeste_json_publie_liste_la_salle(self):
        chemin = os.path.join(HUB, "export", "MANIFESTE.json")
        with open(chemin, encoding="utf-8") as fh:
            data = json.load(fh)
        dests = {f["destination"] for f in data["fichiers"]}
        assert "_bmad/custom/bmad-party-mode.toml" in dests

    def test_le_readme_dit_que_les_salles_exigent_bmad_party_mode(self):
        """Sans la skill bmad-party-mode installée chez la cible, le TOML est un
        override sans base : inerte, et silencieusement. Le dire est la moitié du
        livrable."""
        readme = export_agentic.readme("2026-08-31")
        assert "bmad-party-mode" in readme
        assert "salle" in readme.lower()

    def test_la_checklist_fait_verifier_les_salles_chez_la_cible(self):
        joint = " ".join(export_agentic.CHECKLIST).lower()
        assert "party" in joint or "salle" in joint


class TestAtelierDevStructure:
    def test_les_deux_experts_existent(self):
        for code in ("archi-code", "revue-code"):
            m = _membre(code)
            assert m["name"] and m["persona"].strip()

    def test_les_deux_experts_siegent_a_l_atelier_dev(self):
        membres = _salle("atelier-dev")["members"]
        assert "archi-code" in membres and "revue-code" in membres

    def test_la_salle_reste_a_cinq_voix(self):
        """Le plafond est un arbitrage, pas une préférence : ajouter deux experts
        se paie sur une place, jamais sur le plafond."""
        assert len(_salle("atelier-dev")["members"]) == 5

    def test_les_trois_couches_de_dev_restent(self):
        """C'est la différenciation par COUCHE qui rend la partition de fichiers
        vérifiable — la perdre viderait la salle de son objet."""
        membres = _salle("atelier-dev")["members"]
        for couche in ("dev-noyau", "dev-bord", "dev-preuve"):
            assert couche in membres

    def test_le_depart_de_garde_fou_est_justifie_dans_le_fichier(self):
        """Retirer une voix sans écrire pourquoi, c'est une régression qui a l'air
        d'un choix. Le fichier doit porter la raison ET la voix qui reprend le
        mandat."""
        texte = open(TOML, encoding="utf-8").read()
        i = texte.find('id = "atelier-dev"')
        assert i > -1
        contexte = texte[max(0, i - 2500):i]
        assert "qualite" in contexte and "dev-preuve" in contexte

    def test_garde_fou_reste_convocable_ailleurs(self):
        """Sortir Garde-fou de l'atelier ne doit pas le rendre orphelin."""
        salles = [g["id"] for g in _toml()["party_groups"]
                  if "qualite" in (g.get("members") or [])]
        assert salles, "Garde-fou ne siège plus nulle part"

    def test_l_expert_archi_ne_double_pas_winston(self):
        """Winston (bmad-agent-architect) conçoit l'architecture d'un système à
        bâtir ; le Charpentier lit la structure du code qui EXISTE. Si la persona
        ne dit pas en quoi elle diffère, c'est un doublon bavard — la faute que le
        TOML reproche déjà aux personas adossés à un agent."""
        assert "Winston" in _membre("archi-code")["persona"]

    def test_l_expert_revue_ne_double_pas_la_code_review_crew(self):
        """`code-review-crew` critique un livrable FINI ; le Relecteur siège en
        amont et dit ce qui rendra le diff relisible. Sans cette distinction
        écrite, les deux se marchent dessus."""
        persona = _membre("revue-code")["persona"]
        assert "code-review-crew" in persona or "bmad-code-review" in persona

    def test_le_deroule_de_la_salle_est_ordonne(self):
        """« À structurer » : la salle doit porter un déroulé numéroté, comme
        atelier-idees — un ordre de parole est ce qui distingue une table ronde
        d'un sondage à quatre voix."""
        scene = _salle("atelier-dev")["scene"]
        for etape in ("(1)", "(2)", "(3)", "(4)"):
            assert etape in scene, f"déroulé sans étape {etape}"

    def test_la_salle_ne_produit_toujours_pas_de_diff(self):
        """L'invariant qui protège R4 : une salle qui écrirait du code serait une
        auto-application collective."""
        scene = _salle("atelier-dev")["scene"].lower()
        assert "jamais un diff" in scene or "aucun fichier" in scene

    def test_la_structure_precede_les_couches_dans_le_deroule(self):
        """L'ordre EST la montée en qualité : arbitrer les frontières après avoir
        réparti les fichiers, c'est ratifier un découpage qu'on n'a pas choisi."""
        scene = _salle("atelier-dev")["scene"]
        assert scene.index("(1)") < scene.index("(2)")
        assert "Charpentier" in scene[:scene.index("(2)")]


class TestRenduEtRoutage:
    def test_toutes_les_voix_se_resolvent_encore(self):
        """Le test qui a réellement attrapé un bug : un code mal écrit rend
        « non résolu » dans la page, sans erreur."""
        assert "non résolu" not in scan.render_party_html()

    def test_les_deux_experts_apparaissent_dans_la_page(self):
        html = scan.render_party_html()
        for code in ("archi-code", "revue-code"):
            assert _membre(code)["name"] in html

    def test_le_routage_de_l_atelier_dev_tient_toujours(self):
        """La table SALLES-ROUTAGE de la skill orchestrateur est verrouillée par
        test_salles_routage.py ; on vérifie ici que la ligne atelier-dev décrit
        bien la salle telle qu'elle est devenue."""
        skill = open(os.path.join(HUB, ".claude", "skills", "agent-orchestrator",
                                  "SKILL.md"), encoding="utf-8").read()
        i = skill.find("| `atelier-dev` |")
        assert i > -1
        ligne = skill[i:skill.find("\n", i)]
        assert "architecture" in ligne.lower() or "structure" in ligne.lower(), (
            "la ligne de routage doit refléter la montée en qualité de la salle")
