"""L'installateur du kit : cinq trous élevés, tous reproduits avant d'être fermés.

Revue de sécurité du 2026-09-01 (`bmad-revue` → `bmad-code-review` +
`bmad-review-edge-case-hunter`, 18 findings, 18 reproductions exécutées sur dépôts
jetables), arbitrée le jour même. `export/install_agentic.py` est le chemin par lequel
le kit s'installe dans CINQ dépôts : il copie des fichiers, écrit dans `.claude/` et
fusionne le `settings.json` de la cible — donc il pose des permissions et des hooks qui
s'exécuteront à chaque session.

LES CINQ, dans l'ordre où la revue les a prouvés :

1. **La SOURCE n'est pas confinée alors que la destination l'est.** `destination` passe
   par `_sous_la_cible` ; `export` ne passe par rien. Un manifeste pointant
   `C:/Windows/win.ini` ou `../secret.txt` fait copier n'importe quel fichier lisible du
   poste DANS le dépôt cible, en ligne « ecrit » ordinaire, exit 0 — et la checklist
   demande ensuite de committer l'installation. Le sha256 ajouté le même jour ne referme
   rien : l'empreinte vient du MÊME manifeste que le chemin.

2. **Le confinement compare des chaînes, pas des chemins résolus.** Une jonction de
   répertoire dans l'arbre cible — créable sans droits d'administrateur — fait écrire
   hors de la cible tout en satisfaisant `commonpath`.

3. **Les commandes de hook ne sont jamais montrées.** Elles sont recopiées verbatim
   dans le `settings.json` de la cible, donc exécutées à chaque session, et `--dry-run`
   n'imprime que « FUSION (simule) ». Le seul fichier qui accorde des droits d'exécution
   est le seul dont le contenu n'est pas affiché avant écriture.

4. **Un `settings.json` avec BOM est déclaré illisible**, et le message oriente vers
   `--force` — lequel repart de `{}` : `deny`, `allow` et hooks propres de la cible
   disparaissent, sans sauvegarde. Le kit sait pourtant lire en `utf-8-sig` ailleurs.

5. **La déduplication des hooks se fait sur le nom de fichier.** Si la cible déclare
   déjà un `guard_destructive_git.py` ailleurs — fût-il un no-op — le garde-fou
   BLOQUANT du kit est copié sur disque, donc compté « installé » par tout inventaire
   de présence, et jamais enregistré. C'est le corollaire de R6 pris en défaut par le
   kit lui-même : l'étage 1 mesure la présence, jamais le fonctionnement.

Les tests installent depuis une COPIE jetable du kit, jamais depuis `export/`, et
n'écrivent que sous `tmp_path`.
"""

import io
import json
import os
import shutil
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(HUB, "export", "install_agentic.py")


def _kit(tmp_path, fichiers=None, settings_template=None):
    """Une copie jetable du kit, avec le manifeste qu'on veut lui faire porter."""
    kit = tmp_path / "kit"
    (kit / "supervision").mkdir(parents=True)
    io.open(kit / "supervision" / "ok.py", "w", encoding="utf-8",
            newline="\n").write("# fichier legitime\n")
    io.open(kit / "MANIFESTE.json", "w", encoding="utf-8").write(json.dumps({
        "fichiers": fichiers if fichiers is not None else [
            {"export": "supervision/ok.py", "destination": ".claude/supervision/ok.py"}],
        "settings_template": settings_template or {},
        "claude_md_template": "", "checklist": [],
    }))
    shutil.copy2(SOURCE, str(kit / "install_agentic.py"))
    return kit


def _run(kit, cible, *args):
    return subprocess.run(
        [sys.executable, str(kit / "install_agentic.py"), str(cible), *args],
        capture_output=True, text=True, encoding="utf-8")


class TestLaSourceEstConfineeCommeLaDestination:

    def test_un_chemin_source_absolu_hors_du_kit_est_refuse(self, tmp_path):
        secret = tmp_path / "secret.txt"
        io.open(secret, "w", encoding="utf-8").write("MOT-DE-PASSE=hunter2\n")
        kit = _kit(tmp_path, fichiers=[
            {"export": str(secret).replace("\\", "/"),
             "destination": ".claude/hooks/vole.txt"}])
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible)
        assert not (cible / ".claude" / "hooks" / "vole.txt").exists(), (
            "un fichier arbitraire du poste a ete copie dans le depot cible")
        assert "REFUS" in r.stdout, r.stdout

    def test_une_remontee_dans_le_chemin_source_est_refusee(self, tmp_path):
        io.open(tmp_path / "voisin.txt", "w", encoding="utf-8").write("hors kit\n")
        kit = _kit(tmp_path, fichiers=[
            {"export": "../voisin.txt", "destination": ".claude/hooks/v.txt"}])
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible)
        assert not (cible / ".claude" / "hooks" / "v.txt").exists(), r.stdout
        assert "REFUS" in r.stdout

    def test_un_refus_de_securite_ne_se_lit_pas_comme_un_defaut_d_empaquetage(
            self, tmp_path):
        """Nuance relevee par la revue : les REFUS etaient comptes dans `manquants`,
        donc le rapport concluait « des fichiers du manifeste manquent dans export/ —
        regenerer au hub », ce qui envoie corriger la mauvaise chose."""
        kit = _kit(tmp_path, fichiers=[
            {"export": "../ailleurs.txt", "destination": ".claude/hooks/v.txt"}])
        io.open(tmp_path / "ailleurs.txt", "w", encoding="utf-8").write("x\n")
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible)
        assert "regenerer au hub" not in r.stdout.lower(), (
            "un refus de securite est presente comme un defaut d'empaquetage")


class TestLeConfinementResoutLesLiens:

    def test_une_jonction_de_repertoire_ne_fait_pas_sortir_de_la_cible(self, tmp_path):
        dehors = tmp_path / "DEHORS"
        dehors.mkdir()
        cible = tmp_path / "cible"
        (cible / ".claude").mkdir(parents=True)
        lien = cible / ".claude" / "supervision"
        code = subprocess.run(["cmd", "/c", "mklink", "/J", str(lien), str(dehors)],
                              capture_output=True, text=True).returncode
        if code != 0 or not lien.exists():
            import pytest
            pytest.skip("jonction de repertoire indisponible sur ce poste")
        kit = _kit(tmp_path)
        r = _run(kit, cible, "--force")
        assert not (dehors / "ok.py").exists(), (
            "le confinement compare des chaines : une jonction fait ecrire hors cible")
        assert "REFUS" in r.stdout, r.stdout


class TestLesCommandesDeHookSontMontreesAvantDEtreEcrites:

    _TEMPLATE = {"hooks": {"SessionStart": [
        {"hooks": [{"type": "command", "command": "py -c \"print('coucou')\""}]}]}}

    def test_la_commande_est_affichee_a_l_installation(self, tmp_path):
        kit = _kit(tmp_path, settings_template=self._TEMPLATE)
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible)
        assert "print('coucou')" in r.stdout, (
            "le seul fichier qui accorde des droits d'execution est le seul dont le "
            "contenu n'est pas montre avant ecriture")

    def test_la_commande_est_affichee_AUSSI_en_dry_run(self, tmp_path):
        """C'est le mode qu'on lance justement pour voir ce qui va se passer."""
        kit = _kit(tmp_path, settings_template=self._TEMPLATE)
        cible = tmp_path / "cible"
        cible.mkdir()
        r = _run(kit, cible, "--dry-run")
        assert "print('coucou')" in r.stdout, r.stdout


class TestLeSettingsDeLaCibleNEstJamaisPerdu:

    _EXISTANT = {
        "permissions": {"deny": ["Read(./.env)", "WebFetch"],
                        "allow": ["Bash(npm test)"]},
        "hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "py tools/garde_maison.py"}]}]},
    }

    def _cible_avec_settings(self, tmp_path, encodage):
        cible = tmp_path / "cible"
        (cible / ".claude").mkdir(parents=True)
        io.open(cible / ".claude" / "settings.json", "w",
                encoding=encodage).write(json.dumps(self._EXISTANT))
        return cible

    def test_un_settings_avec_BOM_est_lu_et_non_declare_illisible(self, tmp_path):
        """PowerShell 5.1 ecrit en utf-8-sig sur ce poste : le cas est ordinaire, pas
        exotique. Et le kit sait deja lire en utf-8-sig ailleurs (log_run, log_usage)."""
        kit = _kit(tmp_path)
        cible = self._cible_avec_settings(tmp_path, "utf-8-sig")
        r = _run(kit, cible)
        assert "illisible" not in r.stdout.lower(), r.stdout
        apres = json.load(io.open(cible / ".claude" / "settings.json",
                                  encoding="utf-8-sig"))
        assert "WebFetch" in apres["permissions"]["deny"]
        assert apres["permissions"].get("allow") == ["Bash(npm test)"]

    def test_force_sauvegarde_avant_de_reecrire(self, tmp_path):
        """`--force` reste destructeur par nature ; ce qui ne va pas, c'est qu'il le
        soit SANS FILET sur le fichier qui porte les permissions.

        Premiere version de ce test : elle installait un kit SANS `settings_template`,
        donc `_fusionner_settings` n'etait jamais appele et il n'y avait rien a
        sauvegarder. Elle mesurait un chemin que le scenario n'empruntait pas — la
        faute que cette journee entiere corrige.
        """
        kit = _kit(tmp_path, settings_template={
            "hooks": {"SessionStart": [
                {"hooks": [{"type": "command",
                            "command": "py .claude/hooks/x.py"}]}]}})
        cible = self._cible_avec_settings(tmp_path, "utf-8")
        _run(kit, cible, "--force")
        sauvegardes = [f for f in os.listdir(cible / ".claude")
                       if f.startswith("settings.json.")]
        assert sauvegardes, (
            "le fichier de permissions est reecrit sans qu'aucune copie ne subsiste")


class TestLaDeduplicationDesHooksRegardeLeCheminEtPasLeNom:

    def test_un_homonyme_ailleurs_n_empeche_pas_l_enregistrement_du_garde_fou(
            self, tmp_path):
        """Le fichier est copie sur disque — donc compte « installe » par tout
        inventaire de presence — et rien ne s'execute. C'est le corollaire de R6 pris
        en defaut par le kit lui-meme."""
        template = {"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command",
                 "command": "py .claude/hooks/guard_destructive_git.py"}]}]}}
        kit = _kit(tmp_path, settings_template=template)
        cible = tmp_path / "cible"
        (cible / ".claude").mkdir(parents=True)
        io.open(cible / ".claude" / "settings.json", "w", encoding="utf-8").write(
            json.dumps({"hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command",
                     "command": "py tools/guard_destructive_git.py"}]}]}}))
        _run(kit, cible)
        apres = json.load(io.open(cible / ".claude" / "settings.json",
                                  encoding="utf-8"))
        commandes = [h["command"]
                     for bloc in apres["hooks"]["PreToolUse"]
                     for h in bloc.get("hooks", [])]
        assert any(".claude/hooks/guard_destructive_git.py" in c for c in commandes), (
            "un homonyme ailleurs a suffi a ne PAS enregistrer le garde-fou bloquant, "
            f"alors que son fichier est bien copie ; hooks reels : {commandes}")
