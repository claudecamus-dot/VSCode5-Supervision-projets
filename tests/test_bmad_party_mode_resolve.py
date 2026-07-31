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

# Tous les porteurs de la MÊME signature fautive. Le fork du 2026-07-31 n'avait
# corrigé que resolve_party.py ; le diagnostic étage 2 a montré le lendemain que
# resolve_personas.py était un jumeau exact, non patché et non gardé — la correction
# valait pour l'instance, pas pour la classe. Ce tuple est le garde de la classe :
# tout script qui shelle vers un résolveur BMAD doit y figurer.
CONSOMMATEURS = [
    os.path.join(HUB, ".claude", "skills", "bmad-party-mode", "scripts", "resolve_party.py"),
    os.path.join(HUB, ".claude", "skills", "bmad-forge-idea", "scripts", "resolve_personas.py"),
]
# Le producteur : il écrit du JSON non-ASCII sur stdout. resolve_customization.py
# porte déjà le geste (helper write_json_stdout) ; resolve_config.py l'avait oublié,
# ce qui faisait sortir 4 skills sur 46 en exit 1 sur un poste cp1252.
PRODUCTEURS = [
    os.path.join(HUB, "_bmad", "scripts", "resolve_config.py"),
    os.path.join(HUB, "_bmad", "scripts", "resolve_customization.py"),
]


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


class TestCanariDeClasse:
    """Le garde de la CLASSE, pas de l'instance.

    Écrit après le finding `bmad-forge-idea` du 2026-07-31 : le premier canari ne
    surveillait qu'un fichier, et son jumeau exact est resté cassé un jour de plus.
    Ces tests parcourent TOUS les porteurs de la signature — ajouter un fichier au
    tuple suffit à l'inclure dans la garde.
    """

    def _corps_run_json_de(self, chemin):
        with open(chemin, encoding="utf-8") as fh:
            src = fh.read()
        debut = src.index("def _run_json(")
        fin = src.index("\ndef ", debut + 1)
        return src[debut:fin]

    def test_tous_les_consommateurs_forcent_l_encodage(self):
        for chemin in CONSOMMATEURS:
            corps = self._corps_run_json_de(chemin)
            assert 'encoding="utf-8"' in corps, (
                f"{os.path.basename(chemin)}:_run_json décode avec la codepage de la "
                "console — le fork a été écrasé, ou un nouveau jumeau est apparu.")
            assert "PYTHONIOENCODING" in corps, f"{os.path.basename(chemin)} : env enfant non forcé"
            assert "out.stdout is None" in corps, f"{os.path.basename(chemin)} : garde None absente"

    def test_tous_les_producteurs_reconfigurent_leur_stdout(self):
        """Un producteur qui écrit `ensure_ascii=False` sur un stdout non reconfiguré
        lève UnicodeEncodeError dès qu'une icône d'agent traverse."""
        for chemin in PRODUCTEURS:
            with open(chemin, encoding="utf-8") as fh:
                src = fh.read()
            if "ensure_ascii=False" not in src:
                continue
            assert 'reconfigure(encoding="utf-8")' in src, (
                f"{os.path.basename(chemin)} écrit du JSON non-ASCII sans reconfigurer "
                "stdout : il replantera sur une console cp1252.")

    def test_aucun_jumeau_non_garde_n_existe(self):
        """Le vrai garde de classe : si un script BMAD porte la signature fautive et
        n'est pas dans CONSOMMATEURS, il est cassé sans que personne le sache."""
        import glob
        suspects = []
        for motif in (os.path.join(HUB, ".claude", "skills", "bmad-*", "scripts", "*.py"),
                      os.path.join(HUB, "_bmad", "scripts", "*.py")):
            for chemin in glob.glob(motif):
                with open(chemin, encoding="utf-8") as fh:
                    src = fh.read()
                if "capture_output=True, text=True" in src and "def _run_json(" in src:
                    if os.path.abspath(chemin) not in {os.path.abspath(c) for c in CONSOMMATEURS}:
                        suspects.append(os.path.relpath(chemin, HUB))
        assert not suspects, (
            f"scripts portant la signature fautive et non gardés : {suspects} — "
            "les ajouter à CONSOMMATEURS et leur appliquer le même correctif.")


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


class TestSmokeDesResolveurs:
    """Le finding `dispositif:presence-vs-fonctionnement` (diagnostic du 2026-07-31) :
    l'étage 1 mesure la PRÉSENCE d'une skill et son APPEL, jamais son DÉMARRAGE.
    `bmad-party-mode` a été comptée « installée » et invoquée alors qu'elle ne
    démarrait pas ; 4 skills sur 46 sortaient en exit 1 pour la même cause.

    Compter n'est pas essayer. Ces tests ESSAIENT — ils exécutent les points d'entrée
    et exigent un exit 0 avec du JSON parsable, ce qu'aucun compteur ne peut voir.
    """

    def _exec(self, chemin, *args):
        return subprocess.run(
            [sys.executable, chemin, *args],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )

    def test_les_producteurs_demarrent_et_rendent_du_json(self):
        for chemin in PRODUCTEURS:
            nom = os.path.basename(chemin)
            if nom == "resolve_customization.py":
                out = self._exec(chemin, "--skill", SKILL_ROOT, "--key", "workflow")
            else:
                out = self._exec(chemin, "--project-root", HUB, "--key", "agents")
            assert out.returncode == 0, f"{nom} sort en {out.returncode} : {out.stderr[:300]}"
            json.loads(out.stdout)

    def test_les_consommateurs_demarrent_et_rendent_du_json(self):
        for chemin in CONSOMMATEURS:
            nom = os.path.basename(chemin)
            skill = os.path.dirname(os.path.dirname(chemin))
            out = self._exec(chemin, "--project-root", HUB, "--skill", skill)
            assert out.returncode == 0, f"{nom} sort en {out.returncode} : {out.stderr[:300]}"
            json.loads(out.stdout)
