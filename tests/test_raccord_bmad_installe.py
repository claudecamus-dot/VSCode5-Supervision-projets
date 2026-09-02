"""Le raccord BMAD : la table route 46 skills, l'installateur ne vérifiait pas qu'elles existent.

Demande utilisateur du 2026-09-02 : « sur le site il est indiqué que des skills bmad ne
sont jamais utilisées, vérifie cette info et fais en sorte qu'elles soient bien utilisées
lorsque demandées au niveau de ce projet, que ce raccord soit bien en place dans le
répertoire export dans la structure agentic ».

CE QUE LA MESURE A DIT (étage 1 cumulatif, `state.json`, le 2026-09-02). L'information du
site est EXACTE : sur 46 skills BMAD installées, **2 seulement** ont jamais été invoquées
— `bmad-party-mode` (7 fois, par les salles) et `bmad-customize` (1 fois, en direct). Les
44 autres sont à zéro. Et le sous-agent porteur `bmad-revue`, dont le mandat dit
explicitement « invoque via l'outil Skill », a tourné **5 fois sans en charger une seule**.

CE QUE LA MESURE A AUSSI DIT, et qui déplace le défaut : les skills ne manquent PAS. Elles
sont installées partout — hub 46, VSCode 71, VSCode1 46, VSCode3 46, VSCode4 46. Une seule
cible est incomplète, **VSCode2 avec 39** : il lui manque `bmad-create-architecture`,
`bmad-create-prd`, `bmad-edit-prd`, `bmad-qa-generate-e2e-tests`, `bmad-quick-dev`,
`bmad-spec`, `bmad-validate-prd`. Le kit publié lui installe pourtant une table qui route
ces sept noms « d'office » : le routage désigne des skills que la cible n'a pas, et rien
ne le dit — ni à l'installation, ni à l'usage. Un routage vers le vide ressemble
exactement à un routage qui marche.

CE QUE CES TESTS VERROUILLENT, en trois gestes distincts :

1. **L'installateur vérifie la présence** des skills que la table route chez la cible, et
   NOMME celles qui manquent. Il n'échoue pas pour autant : BMAD s'installe par son propre
   installateur, l'absence est une information, pas une faute du kit.
2. **Le porteur prouve son invocation** — son rapport doit nommer la skill qu'il a
   réellement chargée. C'est le seul contrat de sortie qu'un appelant puisse vérifier
   sans relire un transcript.
3. **Le brief nomme la skill** — la table dit « d'office », ce qui n'est une consigne pour
   personne tant que le brief envoyé au porteur ne porte pas le nom exact à invoquer.

Les tests installent depuis une COPIE jetable du kit et n'écrivent que sous `tmp_path`.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(HUB, "export", "install_agentic.py")
SKILL_ORCHESTRATEUR = os.path.join(
    HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")
AGENTS = os.path.join(HUB, ".claude", "agents")

# Un bloc de routage minimal, de la même forme que celui du socle : c'est lui que
# l'installateur doit savoir lire chez la cible.
BLOC_ROUTAGE = """\
<!-- BMAD-ROUTAGE:START -->

| Besoin | Skill BMAD | Sous-agent porteur | Déclenchement |
| --- | --- | --- | --- |
| Revoir un diff | `bmad-code-review` | `bmad-revue` | d'office |
| Chasser les cas limites | `bmad-review-edge-case-hunter` | `bmad-revue` | d'office |
| Écrire une story | `bmad-create-story` | `inline` | proposé |

**Jamais routées** — dépréciées par BMAD : `bmad-create-prd`, `bmad-edit-prd` →
utiliser `bmad-prd`.

<!-- BMAD-ROUTAGE:END -->
"""


def _kit(tmp_path, contenu_skill=BLOC_ROUTAGE):
    """Une copie jetable du kit qui embarque la skill d'orchestration et son routage."""
    kit = tmp_path / "kit"
    (kit / "skills" / "agent-orchestrator").mkdir(parents=True)
    io.open(kit / "skills" / "agent-orchestrator" / "SKILL.md", "w",
            encoding="utf-8", newline="\n").write(contenu_skill)
    io.open(kit / "MANIFESTE.json", "w", encoding="utf-8").write(json.dumps({
        "fichiers": [{"export": "skills/agent-orchestrator/SKILL.md",
                      "destination": ".claude/skills/agent-orchestrator/SKILL.md"}],
        "settings_template": {}, "claude_md_template": "", "checklist": [],
    }))
    shutil.copy2(SOURCE, str(kit / "install_agentic.py"))
    return kit


def _run(kit, cible, *args):
    return subprocess.run(
        [sys.executable, str(kit / "install_agentic.py"), str(cible), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def _poser_skills(cible, noms):
    for nom in noms:
        d = cible / ".claude" / "skills" / nom
        d.mkdir(parents=True, exist_ok=True)
        io.open(d / "SKILL.md", "w", encoding="utf-8").write("# " + nom + "\n")


class TestLInstallateurVerifieLesSkillsRoutees:
    """Le kit installe une table de routage : il doit dire si la cible peut l'honorer."""

    def test_les_skills_routees_absentes_sont_signalees(self, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        r = _run(_kit(tmp_path), cible)
        assert "bmad-code-review" in r.stdout, (
            "l'installateur n'a pas signalé la skill routée absente de la cible ; "
            "sortie :\n" + r.stdout)

    def test_l_avertissement_NOMME_les_manquantes_pas_seulement_leur_nombre(self, tmp_path):
        """Un compte n'est pas actionnable : on ne sait pas quoi installer."""
        cible = tmp_path / "projet"
        cible.mkdir()
        r = _run(_kit(tmp_path), cible)
        for nom in ("bmad-code-review", "bmad-review-edge-case-hunter",
                    "bmad-create-story"):
            assert nom in r.stdout, nom + " manquant chez la cible et jamais nommé"

    def test_aucun_avertissement_quand_la_cible_les_a_toutes(self, tmp_path):
        """Assertion volontairement totale : pas « ce nom-là est absent de la sortie »,
        mais « aucun avertissement n'a été émis ». La première version de ce test ne
        cherchait qu'un nom, et elle est restée VERTE pendant que le garde-fou criait
        sur une cible saine — un test à assertion partielle vaut un test absent."""
        cible = tmp_path / "projet"
        cible.mkdir()
        _poser_skills(cible, ["bmad-code-review", "bmad-review-edge-case-hunter",
                              "bmad-create-story"])
        r = _run(_kit(tmp_path), cible)
        assert "table de routage" not in r.stdout, (
            "la cible porte les trois skills routées, l'installateur avertit quand "
            "même :\n" + r.stdout)

    def test_la_colonne_PORTEUR_n_est_pas_prise_pour_une_skill(self, tmp_path):
        """`bmad-revue` et `bmad-recherche` sont des SOUS-AGENTS (`.claude/agents/`),
        pas des skills. Les chercher dans `.claude/skills/` les déclare absents chez
        TOUTE cible, y compris celles qui ont les 46 — mesuré sur VSCode1 le 2026-09-02,
        avant correction : la table ne route que la colonne 2."""
        cible = tmp_path / "projet"
        cible.mkdir()
        _poser_skills(cible, ["bmad-code-review", "bmad-review-edge-case-hunter",
                              "bmad-create-story"])
        r = _run(_kit(tmp_path), cible)
        assert "bmad-revue" not in r.stdout, (
            "le porteur (colonne 3) est compté comme une skill manquante :\n" + r.stdout)

    def test_les_depreciees_ne_sont_pas_reclamees(self, tmp_path):
        """La table nomme en prose les skills que BMAD a dépréciées pour dire de NE PAS
        les router. Les réclamer envoie installer ce que l'éditeur vient de retirer."""
        cible = tmp_path / "projet"
        cible.mkdir()
        _poser_skills(cible, ["bmad-code-review", "bmad-review-edge-case-hunter",
                              "bmad-create-story"])
        r = _run(_kit(tmp_path), cible)
        for depreciee in ("bmad-create-prd", "bmad-edit-prd"):
            assert depreciee not in r.stdout, (
                depreciee + " est dépréciée et pourtant réclamée :\n" + r.stdout)

    def test_l_installation_ne_lie_pas_son_code_de_sortie_a_cette_absence(self, tmp_path):
        """BMAD s'installe par son propre installateur : l'absence informe, elle n'échoue pas."""
        cible = tmp_path / "projet"
        cible.mkdir()
        r = _run(_kit(tmp_path), cible)
        assert r.returncode == 0, (
            "code " + str(r.returncode)
            + " alors que seules des skills BMAD manquaient\n" + r.stdout + "\n" + r.stderr)

    def test_fail_open_sur_un_routage_illisible(self, tmp_path):
        """Pas de bloc de routage du tout : on n'avertit pas, et surtout on ne plante pas."""
        cible = tmp_path / "projet"
        cible.mkdir()
        r = _run(_kit(tmp_path, contenu_skill="# une skill sans table de routage\n"), cible)
        assert r.returncode == 0, "exit " + str(r.returncode) + "\n" + r.stderr
        assert "Traceback" not in r.stderr, r.stderr

    def test_le_dry_run_signale_aussi(self, tmp_path):
        """C'est en simulation qu'on veut apprendre ce qui manquera."""
        cible = tmp_path / "projet"
        cible.mkdir()
        r = _run(_kit(tmp_path), cible, "--dry-run")
        assert "bmad-code-review" in r.stdout, r.stdout


class TestLePorteurProuveSonInvocation:
    """`bmad-revue` a tourné 5 fois sans charger une skill : le mandat doit l'exiger."""

    def _mandat(self, nom):
        with io.open(os.path.join(AGENTS, nom), encoding="utf-8") as fh:
            return fh.read()

    def test_bmad_revue_exige_de_nommer_la_skill_invoquee(self):
        texte = self._mandat("bmad-revue.md").lower()
        assert "preuve d'invocation" in texte or "preuve d’invocation" in texte, (
            "le mandat de bmad-revue ne fait pas de la preuve d'invocation un contrat "
            "de sortie : rien ne distingue un rapport produit PAR la skill d'un rapport "
            "improvisé à la main, et c'est exactement ce qui s'est produit 5 fois")

    def test_bmad_recherche_exige_la_meme_preuve(self):
        texte = self._mandat("bmad-recherche.md").lower()
        assert "preuve d'invocation" in texte or "preuve d’invocation" in texte, (
            "même trou dans le porteur de la famille recherche")


class TestLeBriefNommeLaSkill:
    """« d'office » dans une table n'est une consigne pour personne si le brief se tait."""

    def test_la_skill_d_orchestration_impose_de_nommer_la_skill_dans_le_brief(self):
        with io.open(SKILL_ORCHESTRATEUR, encoding="utf-8") as fh:
            texte = fh.read()
        bloc = re.search(r"### 2 quinquies(.+?)### 2 sexies", texte, re.S)
        assert bloc, "le paragraphe 2 quinquies a disparu de la skill d'orchestration"
        corps = bloc.group(1).lower()
        assert "le brief nomme la skill" in corps, (
            "le paragraphe qui route les 46 skills BMAD n'impose nulle part que le brief "
            "envoyé au porteur porte le NOM exact de la skill à invoquer — mesuré le "
            "2026-09-02 : 44 des 46 skills à zéro invocation, porteur compris")
