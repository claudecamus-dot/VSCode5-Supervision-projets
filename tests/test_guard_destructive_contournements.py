"""Trois contournements du garde-fou git, tous reproduits avant d'être fermés.

Revue de sécurité du 2026-09-01 (`bmad-review-edge-case-hunter`), arbitrée le jour même.
`guard_destructive_git.py` est le seul hook **bloquant** du dispositif : il refuse
`git push --force` et `git reset --hard`. Trois façons de passer à côté, chacune vérifiée
non seulement sur le hook mais sur son EFFET RÉEL dans un dépôt jetable.

1. **L'opérateur d'appel PowerShell `&`.** PowerShell est le shell **primaire** de cet
   environnement et le hook est enregistré sur le matcher `Bash|PowerShell` — mais `&`
   n'est ni un wrapper connu ni le mot `git`, donc `& git push --force` passait. La revue
   a vérifié que l'opérateur lance bien git (`& git log --oneline -1` rend un commit) :
   ce n'est pas une syntaxe théorique.

2. **L'abréviation d'option longue.** Le test littéral `"--hard" in rest` ignore que git
   accepte les préfixes non ambigus : `git reset --har` — et même `--h` — fait un reset
   dur complet. Reproduit : travail non commité détruit, hook muet.

3. **Le `+` de refspec.** La forme la plus courante du push forcé ne contient pas le mot
   `--force` : `git push origin +main` force la mise à jour. Reproduit sur un remote
   jetable : `git push origin master` refusé (non fast-forward), `git push origin
   +master` accepté avec `(forced update)`.

Le point commun des trois : le garde-fou cherchait des CHAÎNES précises là où git accepte
des variantes. C'est la même famille que le reste de la journée — un contrôle qui compare
autre chose que ce qu'il prétend interdire.
"""

import importlib.util
import json
import os
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(HUB, ".claude", "hooks", "guard_destructive_git.py")

_spec = importlib.util.spec_from_file_location("guard_test", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _bloque(commande):
    """Le hook refuse-t-il ? On passe par le CHEMIN REEL : stdin JSON, stdout JSON."""
    r = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_input": {"command": commande}}),
        capture_output=True, text=True, encoding="utf-8")
    return "deny" in r.stdout


class TestLOperateurDAppelPowerShell:
    """PowerShell est le shell PRIMAIRE ici, et le hook est monte sur ce matcher."""

    def test_et_commercial_devant_git_push_force(self):
        assert _bloque("& git push --force"), (
            "`& git push --force` passe : l'operateur d'appel PowerShell n'est ni un "
            "wrapper connu ni le mot `git`")

    def test_et_commercial_devant_git_reset_hard(self):
        assert _bloque("& git reset --hard HEAD~1")

    def test_le_cas_nu_reste_bloque(self):
        """Controle : on n'a pas casse ce qui marchait."""
        assert _bloque("git push --force")
        assert _bloque("git reset --hard HEAD~1")

    def test_une_commande_inoffensive_passe_toujours(self):
        assert not _bloque("git status")
        assert not _bloque("& git log --oneline -1")


class TestLesAbreviationsDOptionsLongues:
    """git accepte tout prefixe non ambigu : `--har`, `--ha`, `--h` valent `--hard`."""

    def test_reset_har(self):
        assert _bloque("git reset --har HEAD~1"), (
            "`git reset --har` detruit le travail non commite sans etre vu")

    def test_reset_h_minimal(self):
        assert _bloque("git reset --h HEAD~1")

    def test_une_option_qui_n_est_PAS_un_prefixe_de_hard_passe(self):
        """`--hi` n'est pas un prefixe de `--hard` : le bloquer serait un faux positif,
        et un garde-fou qui crie a tort finit desarme."""
        assert not _bloque("git reset --hi HEAD~1")

    def test_le_reset_doux_reste_autorise(self):
        assert not _bloque("git reset --soft HEAD~1")
        assert not _bloque("git reset HEAD~1")


class TestLePlusDeRefspec:
    """La forme la plus courante du push force ne contient pas le mot `--force`."""

    def test_push_avec_refspec_forcee(self):
        assert _bloque("git push origin +main"), (
            "`+main` force la mise a jour du remote sans le mot --force")

    def test_push_avec_refspec_forcee_complete(self):
        assert _bloque("git push origin +refs/heads/master:refs/heads/master")

    def test_un_push_ordinaire_passe(self):
        assert not _bloque("git push origin main")
        assert not _bloque("git push")

    def test_force_with_lease_reste_autorise(self):
        """Le garde-fou vise le force AVEUGLE, pas le force verifie."""
        assert not _bloque("git push --force-with-lease origin main")


class TestLEffetReelEstBienCeluiQuOnCroit:
    """Les trois contournements ont ete prouves par leur EFFET, pas par lecture.

    On re-verifie ici le seul point qui ne depend pas de PowerShell : qu'une
    abreviation fait bien ce que le garde-fou pretend interdire. Sans cette
    verification, on bloquerait une syntaxe sur la foi d'un raisonnement.
    """

    def test_reset_har_detruit_reellement_le_travail(self, tmp_path):
        depot = tmp_path / "d"
        depot.mkdir()
        def git(*a):
            return subprocess.run(["git", *a], cwd=str(depot), capture_output=True,
                                  text=True, encoding="utf-8")
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (depot / "f.txt").write_text("v1\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-qm", "c1")
        (depot / "f.txt").write_text("TRAVAIL-NON-COMMITE\n", encoding="utf-8")
        r = git("reset", "--har", "HEAD")
        assert r.returncode == 0, f"git a refuse l'abreviation : {r.stderr}"
        assert (depot / "f.txt").read_text(encoding="utf-8") == "v1\n", (
            "l'abreviation ne detruit rien — le garde-fou n'aurait pas a la bloquer")
