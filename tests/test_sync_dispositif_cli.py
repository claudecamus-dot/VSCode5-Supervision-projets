"""Un flag inconnu ne doit plus déclencher l'écriture par défaut, et une cible qui
porte un travail non commité ne doit plus être écrasée sans confirmation.

Finding `sync_dispositif.py::argv-flag-inconnu` (diagnostic du 2026-09-04), incident
de première main : `py .claude/dispositif/sync_dispositif.py --help`, tapé pour lire
une aide, a exécuté la synchronisation RÉELLE par défaut (le flag, non reconnu, était
ignoré) sur 6 dépôts — dont 5 cibles externes qui portaient chacune 3 à 12 fichiers
non commités, aucune vérifiée avant écriture.

Deux verrous distincts, testés séparément :
1. tout token `--xxx` hors de `FLAGS_CONNUS` arrête le script (rien n'est lu, rien
   n'est écrit) ; `--help`/`-h` affiche une aide réelle et n'écrit rien non plus ;
2. avant d'écrire chez une cible, `--check` mis à part, une cible dont
   `git status --porcelain` n'est pas vide est ignorée (pas d'écriture), sauf
   `--meme-si-sale` — fail-open si la cible n'est pas un dépôt git (même contrat que
   `_canon_non_commite`, pour ne jamais bloquer une propagation sur un doute).
"""

import importlib.util
import os
import subprocess

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, ".claude", "dispositif", "sync_dispositif.py")


def _load():
    spec = importlib.util.spec_from_file_location("sync_dispositif_cli", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = _load()

NOM_CANON = "log_run.py"
CORPS_V1 = "# canon v1\nprint('bonjour du canon')\n"


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


def _hub_git_avec_canon(tmp_path):
    hub = tmp_path / "hub"
    canon_dir = hub / ".claude" / "dispositif" / "canon"
    canon_dir.mkdir(parents=True)
    (canon_dir / NOM_CANON).write_text(CORPS_V1, encoding="utf-8")
    _git(hub, "init", "-q")
    _git(hub, "config", "user.email", "t@t")
    _git(hub, "config", "user.name", "t")
    _git(hub, "add", "-A")
    _git(hub, "commit", "-qm", "canon initial")
    return hub, canon_dir


def _viser(monkeypatch, hub, canon_dir, cible):
    monkeypatch.setattr(sync, "ROOT", str(hub))
    monkeypatch.setattr(sync, "CANON_DIR", str(canon_dir))
    monkeypatch.setattr(sync, "MAPPING", {NOM_CANON: sync.MAPPING[NOM_CANON]})
    monkeypatch.setattr(sync, "read_config",
                        lambda: [{"nom": "sonde", "chemin": str(cible)}])


class TestUnFlagInconnuNEcritPlusParDefaut:
    """LE cas de l'incident : `--help` n'existait pas, argv testé par appartenance,
    défaut = écriture. Reproduit puis verrouillé."""

    def test_help_inexistant_avant_le_correctif_naurait_rien_arrete(
            self, tmp_path, monkeypatch, capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _viser(monkeypatch, hub, canon_dir, cible)

        rc = sync.main(["--help"])
        sortie = capsys.readouterr().out

        assert rc == 0
        assert not (cible / sync.MAPPING[NOM_CANON]).exists(), (
            "--help a écrit chez la cible — régression exacte de l'incident")
        assert "synchronisation :" not in sortie, (
            "--help a exécuté le corps de la synchronisation")
        assert "Usage" in sortie or "usage" in sortie.lower()

    def test_un_flag_vraiment_inconnu_arrete_tout_sans_ecrire(
            self, tmp_path, monkeypatch, capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _viser(monkeypatch, hub, canon_dir, cible)

        rc = sync.main(["--applique"])   # jamais existé sous ce nom (c'est celui de propager_socle)
        sortie_err = capsys.readouterr().err

        assert rc != 0
        assert not (cible / sync.MAPPING[NOM_CANON]).exists()
        assert "inconnue" in sortie_err.lower()

    def test_les_flags_reels_restent_tous_acceptes(self, tmp_path, monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _viser(monkeypatch, hub, canon_dir, cible)
        for combo in (["--check"], ["--dry-run"], ["--projet", "sonde"],
                      ["--accepter-derive"], ["--meme-si-sale"],
                      ["--check", "--projet", "sonde"]):
            assert sync._options_inconnues(combo) == [], combo


class TestCibleNonAuRepos:
    """La règle « dépôt au repos avant d'écrire » (veille adoptée 2026-09-03) existait
    seulement en prose avant ce correctif — le script qui écrit ne la connaissait pas."""

    def test_une_cible_avec_du_travail_non_commite_nest_pas_ecrasee(
            self, tmp_path, monkeypatch, capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _git(cible, "init", "-q")
        _git(cible, "config", "user.email", "t@t")
        _git(cible, "config", "user.name", "t")
        (cible / "app.txt").write_text("travail en cours\n", encoding="utf-8")
        # non commité, volontairement : c'est le signal à détecter
        _viser(monkeypatch, hub, canon_dir, cible)

        rc = sync.main([])
        sortie = capsys.readouterr().out

        assert not (cible / sync.MAPPING[NOM_CANON]).exists(), (
            "une cible non au repos a été écrite malgré le garde-fou")
        assert "NON AU REPOS" in sortie
        assert rc == 1

    def test_meme_si_sale_force_lecriture(self, tmp_path, monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _git(cible, "init", "-q")
        _git(cible, "config", "user.email", "t@t")
        _git(cible, "config", "user.name", "t")
        (cible / "app.txt").write_text("travail en cours\n", encoding="utf-8")
        _viser(monkeypatch, hub, canon_dir, cible)

        assert sync.main(["--meme-si-sale"]) == 0
        assert (cible / sync.MAPPING[NOM_CANON]).exists()

    def test_une_cible_au_repos_est_ecrite_normalement(self, tmp_path, monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _git(cible, "init", "-q")
        _git(cible, "config", "user.email", "t@t")
        _git(cible, "config", "user.name", "t")
        (cible / "app.txt").write_text("stable\n", encoding="utf-8")
        _git(cible, "add", "-A")
        _git(cible, "commit", "-qm", "stable")
        _viser(monkeypatch, hub, canon_dir, cible)

        assert sync.main([]) == 0
        assert (cible / sync.MAPPING[NOM_CANON]).exists()

    def test_une_cible_qui_nest_pas_un_depot_git_reste_fail_open(
            self, tmp_path, monkeypatch):
        """Même contrat que `_canon_non_commite` : un doute ne bloque pas — la
        plupart des tests existants du dispositif fabriquent une « cible » qui n'est
        qu'un dossier ordinaire, jamais initialisé en dépôt git."""
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _viser(monkeypatch, hub, canon_dir, cible)

        assert sync.main([]) == 0
        assert (cible / sync.MAPPING[NOM_CANON]).exists()

    def test_check_ignore_le_garde_fou_lecture_seule(self, tmp_path, monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path)
        cible = tmp_path / "cible"
        cible.mkdir()
        _git(cible, "init", "-q")
        _git(cible, "config", "user.email", "t@t")
        _git(cible, "config", "user.name", "t")
        (cible / "app.txt").write_text("travail en cours\n", encoding="utf-8")
        _viser(monkeypatch, hub, canon_dir, cible)

        # --check ne doit jamais être bloqué par le garde-fou d'écriture : il ne
        # touche rien, la cible sale ou pas.
        assert sync.main(["--check"]) in (0, 1)
        assert not (cible / sync.MAPPING[NOM_CANON]).exists()
