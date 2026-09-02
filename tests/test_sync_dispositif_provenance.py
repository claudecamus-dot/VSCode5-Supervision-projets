"""La provenance désigne le canon COPIÉ, pas le HEAD du moment.

Reproduit par la revue de fin de séance du 2026-09-02, sur le hub lui-même. Le sync
tourne AVANT le commit qui contient le canon — c'est l'ordre normal d'un chantier : on
corrige le canon, on propage, on commite. La ligne de provenance embarquait `HEAD`, donc
la révision d'AVANT le commit : les 6 copies portaient `97c2183`, un canon de 73 lignes
plus court que ce qu'elles avaient réellement reçu. Conséquence mesurée :
`determiner_cause` sur la copie du hub, corps byte-à-byte identique au canon, répondait
« cible-divergee » — la fausse accusation que ce mécanisme, arbitré le matin même,
prétendait avoir éteinte. Second effet : chaque commit du hub faisait dériver les 12
en-têtes (`--check` : « 0 à jour, 12 dérive(s) »), un signal constant, donc muet.

Deux verrous ici :
1. la provenance est le dernier commit qui a TOUCHÉ le canon, pas HEAD — un commit
   du hub sans rapport ne fait plus dériver un en-tête ;
2. un canon non commité REFUSE la synchronisation (pas le `--check`), comme
   `propager_socle` le fait déjà pour le socle : sinon la provenance désignerait une
   révision qui ne contient pas ce qui serait copié.
"""

import importlib.util
import os
import subprocess

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, ".claude", "dispositif", "sync_dispositif.py")


def _load():
    spec = importlib.util.spec_from_file_location("sync_dispositif_prov", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = _load()

NOM_CANON = "log_run.py"
CORPS_V1 = "# canon v1\nprint('bonjour du canon')\n"
CORPS_V2 = "# canon v2\nprint('bonjour du canon, corrigé')\nprint('ligne ajoutée')\n"


def _git(repo, *args):
    out = subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return out.stdout.strip()


def _hub(tmp_path):
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


def _viser(monkeypatch, hub, canon_dir, cible, creer_cible=True):
    monkeypatch.setattr(sync, "ROOT", str(hub))
    monkeypatch.setattr(sync, "CANON_DIR", str(canon_dir))
    monkeypatch.setattr(sync, "MAPPING", {NOM_CANON: sync.MAPPING[NOM_CANON]})
    monkeypatch.setattr(sync, "read_config",
                        lambda: [{"nom": "sonde", "chemin": str(cible)}])
    if creer_cible:
        # `main()` saute un projet dont le répertoire n'existe pas ("projet introuvable")
        # et le sync n'écrit que dans une arborescence déjà présente.
        (cible / sync.MAPPING[NOM_CANON]).parent.mkdir(parents=True, exist_ok=True)


class TestLaProvenanceEstLeCommitDuCanon:
    def test_un_commit_sans_rapport_ne_fait_pas_deriver_l_en_tete(self, tmp_path,
                                                                     monkeypatch, capsys):
        """Le cas mesuré : `--check` disait 12 dérives après des commits qui n'avaient
        pas touché le canon."""
        hub, canon_dir = _hub(tmp_path)
        cible = tmp_path / "cible"
        _viser(monkeypatch, hub, canon_dir, cible)
        h_canon = _git(hub, "log", "-1", "--format=%h", "--", ".claude/dispositif/canon")

        assert sync.main([]) == 0
        dest = cible / sync.MAPPING[NOM_CANON]
        assert f"Provenance canon : {h_canon}" in dest.read_text(encoding="utf-8")

        # un commit du hub qui ne touche PAS le canon
        (hub / "autre.txt").write_text("x", encoding="utf-8")
        _git(hub, "add", "-A")
        _git(hub, "commit", "-qm", "sans rapport")
        assert _git(hub, "rev-parse", "--short", "HEAD") != h_canon

        capsys.readouterr()
        assert sync.main(["--check"]) == 0, capsys.readouterr().out
        assert "dérive (en-tête)" not in capsys.readouterr().out

    def test_la_copie_intacte_n_est_plus_accusee_apres_un_commit_du_hub(self, tmp_path,
                                                                          monkeypatch):
        """Le cœur du défaut : la copie n'a pas bougé, le canon non plus — seule la
        révision de HEAD a changé. `determiner_cause` doit voir un corps identique au
        canon de provenance, donc ne PAS répondre « cible-divergee »."""
        hub, canon_dir = _hub(tmp_path)
        cible = tmp_path / "cible"
        _viser(monkeypatch, hub, canon_dir, cible)
        assert sync.main([]) == 0
        (hub / "autre.txt").write_text("x", encoding="utf-8")
        _git(hub, "add", "-A")
        _git(hub, "commit", "-qm", "sans rapport")

        dest = cible / sync.MAPPING[NOM_CANON]
        actuel = sync.read_lf(str(dest))
        cause = sync.determiner_cause(NOM_CANON, actuel, sync.strip_header(actuel))
        assert cause == "canon-avance", (
            f"une copie intacte est accusée de divergence : {cause!r} — la provenance "
            "désigne un canon qui n'est pas celui qui a été copié")


class TestUnCanonNonCommiteRefuseDeSynchroniser:
    def test_refus_en_ecriture_et_rien_n_est_ecrit(self, tmp_path, monkeypatch, capsys):
        hub, canon_dir = _hub(tmp_path)
        cible = tmp_path / "cible"
        _viser(monkeypatch, hub, canon_dir, cible)
        (canon_dir / NOM_CANON).write_text(CORPS_V2, encoding="utf-8")   # modifié, pas commité

        rc = sync.main([])
        sortie = capsys.readouterr().out
        assert rc == 3, sortie
        assert "NON COMMIT" in sortie and "git commit" in sortie, sortie
        assert not (cible / sync.MAPPING[NOM_CANON]).exists(), (
            "une copie a été écrite avec une provenance fausse par construction")

    def test_le_check_reste_possible_sur_un_canon_sale(self, tmp_path, monkeypatch):
        hub, canon_dir = _hub(tmp_path)
        cible = tmp_path / "cible"
        _viser(monkeypatch, hub, canon_dir, cible)
        (canon_dir / NOM_CANON).write_text(CORPS_V2, encoding="utf-8")
        assert sync.main(["--check"]) in (0, 1)   # il mesure, il ne refuse pas

    def test_la_garde_est_fail_open_sans_git(self, tmp_path, monkeypatch):
        """Un doute (git injoignable) ne bloque pas une propagation : même contrat que
        les autres gardes du dispositif."""
        monkeypatch.setattr(sync, "ROOT", str(tmp_path / "pas-un-depot"))
        assert sync._canon_non_commite() == []
