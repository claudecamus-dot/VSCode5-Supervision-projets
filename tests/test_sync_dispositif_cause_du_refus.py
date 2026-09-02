"""Le refus de `sync_dispositif.py` accusait la CIBLE alors que c'est parfois le
CANON qui a bougé. Finding arbitré le 2026-09-02.

LE MÉCANISME CASSÉ. Une copie déployée diffère du canon courant pour deux raisons
possibles, que l'ancien code ne distinguait pas :

1. la cible a réellement divergé — quelqu'un a édité le script SUR PLACE ;
2. le CANON a avancé au hub depuis que cette copie a été écrite — la cible, elle,
   n'a pas bougé, elle est seulement en retard.

Le message imprimé dans les deux cas était le même : « le script a été modifié
ici ». Dans le cas 2, c'est une fausse accusation : ça envoie chercher une
modification locale qui n'existe pas.

LE CORRECTIF s'inspire du mécanisme de provenance de `propager_socle.py`
(`socle_d_origine`, qui retrouve l'ancien socle par le hash que la copie porte dans
sa propre ligne de provenance, puis compare CE hash-là — pas le hash courant). Ici :
chaque copie synchronisée embarque désormais, dans son en-tête généré, la révision
du canon dont elle descend (`# | Provenance canon : <hash> du <date>`).
`determiner_cause()` récupère le canon TEL QU'IL ÉTAIT à cette révision (`git show
<hash>:.claude/dispositif/canon/<nom>`, sur le modèle exact de
`propager_socle.socle_d_origine`) et compare :

- corps actuel == canon à la révision de provenance  -> la cible n'a pas bougé,
  c'est le canon qui a avancé ("canon-avance") ;
- sinon -> la cible a réellement divergé ("cible-divergee") ;
- provenance absente/irrésolvable (copie antérieure au mécanisme, hash hors de
  l'histoire, git injoignable) -> "indéterminé" : le message ne doit alors accuser
  NI la cible NI trancher sur le canon, faute de preuve.

CE QUI N'EST PAS TESTÉ MONKEYPATCHÉ : le canon avance réellement (deux vraies
révisions git successives, `git show` réellement appelé) — un faux `subprocess.run`
qui rendrait la chaîne voulue ne mesurerait rien, exactement le écueil documenté
dans `tests/test_encodage_des_sous_processus.py` et dans `test_propager_socle.py`
(`TestLaPorteLitLeBlobDansLE_BON_ENCODAGE`).

PIÈGE ENCODAGE (payé ici le 2026-09-01, une heure de propagation bloquée) : tout
`subprocess.run(..., text=True)` qui lit le canon ou une copie doit porter
`encoding="utf-8", errors="replace"` — sans ça, `text=True` décode avec l'encodage
LOCAL (cp1252 sur ce poste), et un seul caractère accentué rend la comparaison
fausse. Le canon réel (`scan_transcripts.py`, `log_run.py`) est plein d'accents :
un des deux scénarios ci-dessous en introduit délibérément pour vérifier que le
nouveau mécanisme de provenance résiste à ce piège précis.
"""

import importlib.util
import os
import subprocess

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, ".claude", "dispositif", "sync_dispositif.py")


def _load():
    spec = importlib.util.spec_from_file_location("sync_dispositif_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = _load()

NOM_CANON = "log_run.py"
CORPS_V1 = "# canon v1\nprint('bonjour du canon')\n"
CORPS_V2_ACCENTUE = "# canon v2\nprint('bonjour du canon, révision accentuée : été')\n"


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _hub_git_avec_canon(tmp_path, corps_initial):
    """Un HUB jetable, VRAI dépôt git, avec `.claude/dispositif/canon/log_run.py`
    déjà commité — condition nécessaire pour que `git show <hash>:...` puisse
    ensuite retrouver une révision passée du canon."""
    hub = tmp_path / "hub"
    canon_dir = hub / ".claude" / "dispositif" / "canon"
    canon_dir.mkdir(parents=True)
    (canon_dir / NOM_CANON).write_text(corps_initial, encoding="utf-8")
    r = str(hub)
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "canon initial")
    return hub, canon_dir


def _viser_hub(monkeypatch, hub, canon_dir):
    monkeypatch.setattr(sync, "ROOT", str(hub))
    monkeypatch.setattr(sync, "CANON_DIR", str(canon_dir))
    # Le hub jetable ne porte qu'UN fichier canon (log_run.py) : restreindre le
    # MAPPING sinon `main()` refuse tout de suite avec « canon introuvable :
    # ['scan_transcripts.py'] » avant d'atteindre le mécanisme testé.
    monkeypatch.setattr(sync, "MAPPING", {NOM_CANON: sync.MAPPING[NOM_CANON]})


def _hash_head(repo):
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(repo),
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    return out.stdout.strip()


class TestLaCibleADivergeVraiment:
    """Cas 1 : la copie déployée a été éditée SUR PLACE, le canon n'a pas bougé
    depuis. Le message doit continuer à dire « le script a été modifié ici »."""

    def test_le_message_accuse_bien_la_cible(self, tmp_path, monkeypatch, capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V1)
        _viser_hub(monkeypatch, hub, canon_dir)
        h1 = _hash_head(hub)

        cible = tmp_path / "cible"
        dest = cible / sync.MAPPING[NOM_CANON]
        dest.parent.mkdir(parents=True)
        deploye = sync.build_content(NOM_CANON, hash_court=h1, jour="2026-09-01")
        # la cible EDITE le corps déployé, sans que le canon ait bougé
        modifie = deploye.replace("print('bonjour du canon')",
                                  "print('correctif local urgent')")
        sync.write_crlf(str(dest), modifie)

        monkeypatch.setattr(sync, "read_config",
                            lambda: [{"nom": "sonde", "chemin": str(cible)}])
        sync.main([])
        sortie = capsys.readouterr().out

        assert "le script a été modifié ici" in sortie, (
            f"la vraie divergence locale n'est plus signalee comme telle : {sortie!r}")
        assert "le canon a avancé" not in sortie
        assert "correctif local urgent" in dest.read_text(encoding="utf-8"), (
            "la modification locale a ete ecrasee malgre le refus")


class TestLeCanonAAvanceLaCibleEstIntacte:
    """Cas 2, celui du finding : la cible n'a jamais été touchée, c'est le canon qui
    a avancé au hub depuis que cette copie a été synchronisée. Le message ne doit
    plus dire « le script a été modifié ici »."""

    def test_le_message_accuse_le_canon_pas_la_cible(self, tmp_path, monkeypatch,
                                                      capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V1)
        _viser_hub(monkeypatch, hub, canon_dir)
        h1 = _hash_head(hub)

        cible = tmp_path / "cible"
        dest = cible / sync.MAPPING[NOM_CANON]
        dest.parent.mkdir(parents=True)
        # La cible recoit EXACTEMENT ce que la revision h1 du canon produisait :
        # aucune trace d'edition locale.
        deploye = sync.build_content(NOM_CANON, hash_court=h1, jour="2026-09-01")
        sync.write_crlf(str(dest), deploye)

        # Le canon avance ENSUITE au hub — une vraie 2e revision, avec un contenu
        # accentue pour croiser le piege d'encodage.
        (canon_dir / NOM_CANON).write_text(CORPS_V2_ACCENTUE, encoding="utf-8")
        _git(str(hub), "add", "-A")
        _git(str(hub), "commit", "-qm", "canon avance, revision accentuee")

        monkeypatch.setattr(sync, "read_config",
                            lambda: [{"nom": "sonde", "chemin": str(cible)}])
        sync.main([])
        sortie = capsys.readouterr().out

        assert "le script a été modifié ici" not in sortie, (
            f"la cible intacte est accusee a tort d'une modification locale : {sortie!r}")
        assert "le canon a avancé" in sortie, (
            f"la vraie cause (canon avance) n'est pas nommee : {sortie!r}")
        # et rien n'a ete perdu : la cible n'a pas ete ecrasee sans confirmation
        assert "bonjour du canon" in dest.read_text(encoding="utf-8")

    def test_accepter_derive_synchronise_bien_sur_le_nouveau_canon(self, tmp_path,
                                                                    monkeypatch):
        """Le contournement existant doit continuer a fonctionner independamment
        de la cause identifiee."""
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V1)
        _viser_hub(monkeypatch, hub, canon_dir)
        h1 = _hash_head(hub)

        cible = tmp_path / "cible"
        dest = cible / sync.MAPPING[NOM_CANON]
        dest.parent.mkdir(parents=True)
        sync.write_crlf(str(dest), sync.build_content(NOM_CANON, hash_court=h1,
                                                       jour="2026-09-01"))

        (canon_dir / NOM_CANON).write_text(CORPS_V2_ACCENTUE, encoding="utf-8")
        _git(str(hub), "add", "-A")
        _git(str(hub), "commit", "-qm", "canon avance")

        monkeypatch.setattr(sync, "read_config",
                            lambda: [{"nom": "sonde", "chemin": str(cible)}])
        sync.main(["--accepter-derive"])
        assert "révision accentuée" in dest.read_text(encoding="utf-8")


class TestLaProvenanceEstIrresolvable:
    """Une copie antérieure à ce mécanisme (pas de ligne de provenance) ou dont le
    hash ne se retrouve pas dans l'histoire ne doit ni accuser la cible à tort, ni
    inventer une avance du canon qu'on ne peut pas prouver."""

    def test_sans_ligne_de_provenance_le_message_ne_tranche_pas(self, tmp_path,
                                                                 monkeypatch, capsys):
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V1)
        _viser_hub(monkeypatch, hub, canon_dir)

        cible = tmp_path / "cible"
        dest = cible / sync.MAPPING[NOM_CANON]
        dest.parent.mkdir(parents=True)
        # Une copie "ancienne generation" : un corps qui differe du canon actuel,
        # mais SANS aucun en-tete (donc sans ligne de provenance).
        sync.write_crlf(str(dest), "# une tres vieille copie, jamais mise a jour\n")

        monkeypatch.setattr(sync, "read_config",
                            lambda: [{"nom": "sonde", "chemin": str(cible)}])
        sync.main([])
        sortie = capsys.readouterr().out

        # On distingue les TROIS messages par leur fragment propre plutôt que par
        # simple présence de "modifié ici" / "canon a avancé" : le message prudent
        # (indéterminé) mentionne légitimement les deux hypothèses sans trancher,
        # donc une simple recherche de sous-chaîne les confondrait.
        assert "Relire le diff, remonter le correctif au canon du hub" not in sortie, (
            f"provenance absente : le message affirme quand meme la divergence "
            f"comme un fait etabli : {sortie!r}")
        assert "pour l'aligner sur le canon actuel" not in sortie, (
            f"provenance absente : le message affirme quand meme l'avance du "
            f"canon comme un fait etabli : {sortie!r}")
        assert "impossible de déterminer si le script a été modifié ici ou si le " \
               "canon a avancé" in sortie, (
            f"provenance absente : le message tranche alors qu'il ne devrait "
            f"pas pouvoir le faire : {sortie!r}")
        assert "--accepter-derive" in sortie, (
            "meme indetermine, le refus doit rester franchissable explicitement")


class TestEncodageDesAppelsGit:
    """Piège payé le 2026-09-01 sur `propager_socle._socle_non_commite` : un
    `subprocess.run(text=True)` sans `encoding=` explicite decode en cp1252 sur ce
    poste, et un seul caractere accentue rend le contenu recupere par `git show`
    incomparable a la copie reelle (qui, elle, est lue en UTF-8)."""

    def test_le_canon_accentue_a_sa_revision_de_provenance_est_lu_en_utf8(
            self, tmp_path, monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V2_ACCENTUE)
        _viser_hub(monkeypatch, hub, canon_dir)
        h = _hash_head(hub)

        corps = sync.canon_a_revision(NOM_CANON, h)
        assert corps is not None, "la revision existe pourtant dans l'historique"
        assert corps == CORPS_V2_ACCENTUE, (
            f"contenu recupere abime par un mauvais decodage : {corps!r}")

    def test_une_revision_hors_de_l_histoire_rend_none_sans_lever(self, tmp_path,
                                                                   monkeypatch):
        hub, canon_dir = _hub_git_avec_canon(tmp_path, CORPS_V1)
        _viser_hub(monkeypatch, hub, canon_dir)
        assert sync.canon_a_revision(NOM_CANON, "0000000") is None
