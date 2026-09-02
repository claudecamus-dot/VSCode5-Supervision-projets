"""Le kit pose un `.gitignore` pour ce qui est machine-local, et le DIT pour le reste.

Revue de sécurité du 2026-09-01, finding « journaux à texte libre sans règle d'ignore »,
arbitré le jour même.

CE QUE LE KIT INSTALLE dans `.claude/` de la cible : des journaux qui contiennent du
texte libre (la `description` d'une tâche, la `demande` de l'utilisateur), des
identifiants de session et des chemins absolus du poste. Il n'installait aucune règle
d'ignore, et sa propre checklist demande à l'étape 7 de committer l'installation. Sur un
dépôt à remote externe, c'est un canal de divulgation que personne n'a annoncé.
`write_diagnostic.py` affirme même « Gitignoré — donnée machine » : vrai au hub, jamais
établi chez la cible.

CE QU'ON NE FAIT PAS, et c'est le point délicat. `runs.jsonl` et `arbitrages.json` sont
le JOURNAL et les DÉCISIONS du dispositif : le hub les versionne à dessein, R5 en fait la
vérité opposable. Les gitignorer chez la cible casserait la doctrine au lieu de protéger
quoi que ce soit. On sépare donc deux choses que le finding mélangeait : ce qui est
machine-local (état, mesures, incidents) et ce qui est une trace de décision. Le premier
est ignoré ; le second est **signalé** à l'installation, pour que la cible décide en
sachant ce que ces fichiers contiennent.
"""

import io
import json
import os
import shutil
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(HUB, "export", "install_agentic.py")

MACHINE_LOCAL = ("usage.jsonl", "jobs.jsonl", "vues.jsonl", "scan_incidents.jsonl",
                 "state.json")


def _kit(tmp_path):
    kit = tmp_path / "kit"
    (kit / "supervision").mkdir(parents=True)
    io.open(kit / "supervision" / "ok.py", "w", encoding="utf-8",
            newline="\n").write("# x\n")
    io.open(kit / "MANIFESTE.json", "w", encoding="utf-8").write(json.dumps({
        "fichiers": [{"export": "supervision/ok.py",
                      "destination": ".claude/supervision/ok.py"}],
        "settings_template": {}, "claude_md_template": "", "checklist": [],
    }))
    shutil.copy2(SOURCE, str(kit / "install_agentic.py"))
    return kit


def _run(kit, cible, *args):
    return subprocess.run(
        [sys.executable, str(kit / "install_agentic.py"), str(cible), *args],
        capture_output=True, text=True, encoding="utf-8")


class TestLeKitPoseUnGitignore:

    def test_les_journaux_machine_locaux_sont_ignores(self, tmp_path):
        kit = _kit(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _run(kit, cible)
        chemin = cible / ".claude" / ".gitignore"
        assert chemin.exists(), (
            "aucune regle d'ignore posee, alors que la checklist demande de committer")
        contenu = io.open(chemin, encoding="utf-8").read()
        for nom in MACHINE_LOCAL:
            assert nom in contenu, f"{nom} n'est pas ignore"

    def test_le_journal_et_les_arbitrages_ne_sont_PAS_ignores(self, tmp_path):
        """R5 : le journal est la verite opposable du dispositif. L'ignorer chez la
        cible casserait la doctrine au lieu de proteger quoi que ce soit."""
        kit = _kit(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _run(kit, cible)
        contenu = io.open(cible / ".claude" / ".gitignore", encoding="utf-8").read()
        assert "runs.jsonl" not in contenu
        assert "arbitrages.json" not in contenu

    def test_l_installation_DIT_ce_que_les_journaux_versionnes_contiennent(self, tmp_path):
        """Ce qu'on ne peut pas ignorer, on doit au moins l'annoncer."""
        kit = _kit(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible)
        assert "texte libre" in r.stdout.lower(), (
            "la cible committe des journaux a texte libre sans en etre avertie")

    def test_un_gitignore_existant_n_est_pas_ecrase(self, tmp_path):
        """Un fichier de la cible appartient a la cible : on ajoute, on n'ecrase pas."""
        kit = _kit(tmp_path)
        cible = tmp_path / "cible"
        (cible / ".claude").mkdir(parents=True)
        io.open(cible / ".claude" / ".gitignore", "w", encoding="utf-8").write(
            "# regle maison\nsecrets.local\n")
        _run(kit, cible)
        contenu = io.open(cible / ".claude" / ".gitignore", encoding="utf-8").read()
        assert "secrets.local" in contenu, "la regle de la cible a ete ecrasee"
        assert "usage.jsonl" in contenu, "la regle du kit n'a pas ete ajoutee"

    def test_l_ajout_n_est_pas_repete_a_chaque_installation(self, tmp_path):
        kit = _kit(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _run(kit, cible)
        _run(kit, cible, "--force")
        contenu = io.open(cible / ".claude" / ".gitignore", encoding="utf-8").read()
        assert contenu.count("usage.jsonl") == 1, "regles empilees a chaque passage"
