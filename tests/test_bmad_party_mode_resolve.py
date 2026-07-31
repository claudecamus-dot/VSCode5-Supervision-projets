"""Non-régression du fork local de `bmad-party-mode/scripts/resolve_party.py`
(2026-07-31, tracé dans `.claude/patches/bmad-party-mode-resolve_party.md`).

Le fichier est livré par BMAD (SHA au manifeste `_bmad/_config/files-manifest.csv`) :
une mise à jour de la skill l'écrase et perd silencieusement notre correctif. Deux
angles, parce qu'un seul ne suffit pas :

  * un test SOURCE (canari, marche sur toute plateforme) qui échoue dès que le
    correctif disparaît du fichier, même si l'environnement d'exécution ne
    reproduit pas le bug d'origine (celui-ci n'apparaît que sur une console non
    UTF-8 — typiquement Windows/cp1252 — donc une CI Linux par défaut ne le
    verrait pas planter et laisserait passer une régression) ;
  * un test D'EXÉCUTION RÉELLE qui lance le script pour de vrai et vérifie qu'il
    résout effectivement les 6 agents installés — la preuve que ça marche, pas
    seulement que le code source contient les bons mots.
"""

import json
import os
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, ".claude", "skills", "bmad-party-mode", "scripts", "resolve_party.py")
SKILL_ROOT = os.path.join(HUB, ".claude", "skills", "bmad-party-mode")


def _source():
    with open(SCRIPT, encoding="utf-8") as fh:
        return fh.read()


def _corps_run_json():
    """Le corps de `_run_json` SEUL.

    Chercher les marqueurs du fork dans le fichier entier ne marche pas : vérifié
    en simulant l'écrasement du fork, le canari restait vert parce que
    `encoding="utf-8"` apparaît aussi dans le `reconfigure()` de `main()`, tout en
    bas du fichier. Un canari qui ne peut pas virer au rouge ne garde rien.
    """
    src = _source()
    debut = src.index("def _run_json(")
    fin = src.index("\ndef ", debut + 1)
    return src[debut:fin]


class TestCanariSource:
    """Échoue si une mise à jour BMAD écrase le fork sans qu'on le remarque."""

    def test_run_json_force_l_encodage_utf8(self):
        src = _corps_run_json()
        assert 'encoding="utf-8"' in src, (
            "resolve_party.py:_run_json a perdu encoding=\"utf-8\" — le fork "
            "2026-07-31 (crash UnicodeDecodeError sur console cp1252) a été "
            "écrasé, probablement par une mise à jour BMAD. Revoir "
            ".claude/patches/bmad-party-mode-resolve_party.md.")

    def test_run_json_force_pythonioencoding_pour_l_enfant(self):
        src = _corps_run_json()
        assert "PYTHONIOENCODING" in src, (
            "resolve_party.py a perdu le PYTHONIOENCODING passé à resolve_config.py "
            "— sans lui, le producteur replante en UnicodeEncodeError sur une "
            "console cp1252 (0 agent résolu, silencieusement).")

    def test_le_none_de_stdout_est_garde_avant_strip(self):
        src = _corps_run_json()
        assert "out.stdout is None" in src, (
            "la garde explicite sur out.stdout doit rester : sans elle, tout futur "
            "mode d'échec laissant stdout à None refait planter _run_json en "
            "AttributeError (c'était le crash réel observé, hors du bloc try).")


class TestExecutionReelle:
    """La preuve par l'exécution, pas seulement par la lecture du source."""

    def _resoudre(self, *extra_args):
        return subprocess.run(
            [sys.executable, SCRIPT, "--project-root", HUB, "--skill", SKILL_ROOT, *extra_args],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace",
        )

    def test_sort_en_succes_avec_un_json_valide(self):
        out = self._resoudre()
        assert out.returncode == 0, f"stderr: {out.stderr}"
        json.loads(out.stdout)  # ne doit pas lever

    def test_les_6_agents_installes_sont_resolus(self):
        data = json.loads(self._resoudre().stdout)
        assert data.get("installed_agents_resolved") is True, (
            "installed_agents_resolved=False : le producteur (resolve_config.py) a "
            "replanté — vérifier que PYTHONIOENCODING est bien passé à son env.")
        codes = {m["code"] for m in data.get("members", [])}
        assert codes == {
            "bmad-agent-analyst", "bmad-agent-tech-writer", "bmad-agent-pm",
            "bmad-agent-ux-designer", "bmad-agent-architect", "bmad-agent-dev",
        }

    def test_les_icones_emoji_ne_sont_pas_corrompues(self):
        """errors="replace" ne doit remplacer que des octets réellement invalides,
        jamais un emoji multi-code-point valide (ex. Winston = U+1F3D7 U+FE0F)."""
        data = json.loads(self._resoudre().stdout)
        winston = next(m for m in data["members"] if m["code"] == "bmad-agent-architect")
        assert "�" not in winston["icon"], (
            "caractère de remplacement U+FFFD dans une icône : errors=\"replace\" "
            "a corrompu des octets UTF-8 valides plutôt que de gérer un vrai défaut "
            "d'encodage — l'appel devrait décoder proprement, pas juste ne pas planter.")

    def test_list_groups_fonctionne_aussi(self):
        out = self._resoudre("--list-groups")
        assert out.returncode == 0, f"stderr: {out.stderr}"
        data = json.loads(out.stdout)
        assert {g["id"] for g in data["groups"]} >= {"code-review-crew", "anti-consensus-club"}
