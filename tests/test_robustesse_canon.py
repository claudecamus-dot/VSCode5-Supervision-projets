"""Robustesse du CANON du dispositif — 4 défauts reproduits par revue adversariale
(2026-08-31), un test par défaut, tous sur des fichiers jetables (`tmp_path`).

Le canon (`.claude/dispositif/canon/scan_transcripts.py`) est propagé aux 6 projets
par `sync_dispositif.py` : chacun de ces défauts s'exécutait donc six fois par jour,
à chaque démarrage de session. Ce que ces tests tiennent :

1. la commande de solde imprimée au démarrage **solde vraiment** (elle rendait rc=1,
   ce qui poussait vers l'édition manuelle du journal — que R5 interdit) ;
2. un échec de LECTURE de `docs/wiki/index.md` ne devient **jamais** un écrasement
   de la page rédigée à la main (reproduit : 1466 -> 422 octets, sans un message) ;
3. un journal JSONL abîmé (octet non-UTF-8 d'`Add-Content`, ligne corrompue) ne fait
   plus tomber TOUT le scan de démarrage, et ne disparaît plus en silence ;
4. `state.json` s'écrit atomiquement : une écriture interrompue ne détruit plus
   l'état accumulé.

Chacun a été vérifié DISCRIMINANT : correctif annulé, le test passe au rouge.
Lancer : py -m pytest tests/test_robustesse_canon.py -q --basetemp=C:/tmp/pt/canon
"""

import builtins
import datetime as dt
import importlib.util
import json
import os
import re

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(HUB, ".claude", "dispositif", "canon")


def _load(nom, chemin):
    """Charge un module du canon par chemin (ce n'est pas un package)."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = _load("robustesse_scan_transcripts", os.path.join(CANON, "scan_transcripts.py"))
log_run = _load("robustesse_log_run", os.path.join(CANON, "log_run.py"))


@pytest.fixture
def scan_isole(tmp_path, monkeypatch):
    """Redirige TOUS les chemins du scan vers `tmp_path` — aucun fichier réel du dépôt
    n'est lu ni écrit par ces tests. Rend le dossier de travail."""
    boite = tmp_path / "isole"
    (boite / "docs" / "wiki" / "technical").mkdir(parents=True)
    (boite / "transcripts").mkdir()
    monkeypatch.setenv("AGENT_SUPERVISION_TRANSCRIPTS", str(boite / "transcripts"))
    for attr, rel in (("STATE_PATH", "state.json"),
                      ("WIKI_PAGE", "docs/wiki/technical/agents-supervision.md"),
                      ("WIKI_INDEX", "docs/wiki/index.md"),
                      ("WIKI_HTML", "docs/wiki.html"),
                      ("RUNS_PATH", "runs.jsonl"),
                      ("ROUTING_HINTS_PATH", "routing-hints.json"),
                      ("DIAGNOSTIC_PATH", "diagnostic.json"),
                      ("OPENHUB_DB", "app.db"),
                      ("ARBITRAGES_PATH", "arbitrages.json")):
        monkeypatch.setattr(scan, attr, str(boite / rel))
    # `git status` sur le vrai dépôt n'a rien à faire ici (et trois agents y écrivent).
    monkeypatch.setattr(scan, "arbre_sale", lambda: [])
    return boite


# --- Finding 1 (HAUT) : le prefixe de solde imprime doit identifier UN run ----------
class TestFinding1PrefixeDeSoldeUnique:
    """`solder()` exige EXACTEMENT une correspondance de préfixe. La commande imprimée
    tronquait le ts à 13 caractères (l'heure) : mesuré sur le journal réel, 24 préfixes
    horaires sur 36 sont partagés par au moins deux runs — la commande officielle
    rendait donc rc=1 « 2 run(s) pour le prefixe », et le seul chemin autorisé par R5
    était inutilisable."""

    def _journal_deux_runs_meme_heure(self, chemin):
        vieux = dt.datetime.now().astimezone() - dt.timedelta(days=3)
        ts_a = vieux.replace(minute=5, second=0, microsecond=0).isoformat(timespec="seconds")
        ts_b = vieux.replace(minute=47, second=0, microsecond=0).isoformat(timespec="seconds")
        with open(chemin, "w", encoding="utf-8") as fh:
            for ts, demande in ((ts_a, "livrable A"), (ts_b, "livrable B")):
                fh.write(json.dumps({"ts": ts, "demande": demande, "qualification": "orchestre",
                                     "resultat": "en-attente-validation", "plan": []},
                                    ensure_ascii=False) + "\n")
        return ts_a, ts_b

    def test_la_commande_imprimee_solde_reellement_le_run(self, scan_isole, capsys, monkeypatch):
        journal = scan_isole / "runs.jsonl"
        ts_a, ts_b = self._journal_deux_runs_meme_heure(journal)

        assert scan.main([]) == 0
        sortie = capsys.readouterr().out

        # Le préfixe est extrait de la commande RÉELLEMENT imprimée, guillemets ou non :
        # le test porte sur le comportement (est-elle exécutable ?), pas sur la mise en forme.
        prefixes = re.findall(r'--solde\s+"?([^"\s]+)"?\s+succes', sortie)
        assert len(prefixes) == 2, f"2 runs a solder attendus, sortie : {sortie!r}"

        # On exécute la commande proposée, comme le ferait l'utilisateur.
        monkeypatch.setattr(log_run, "RUNS_PATH", str(journal))
        assert log_run.solder([prefixes[0], "succes", "OK utilisateur"]) == 0

        runs = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]
        soldes = {r["ts"]: r["resultat"] for r in runs}
        assert soldes[ts_a] == "succes", "le run cible n'a pas ete requalifie"
        assert soldes[ts_b] == "en-attente-validation", "l'autre run devait rester intact"


# --- Finding 2 (HAUT) : un echec de lecture n'ecrase jamais index.md ---------------
class TestFinding2IndexJamaisEcraseSurEchecDeLecture:
    """`update_index` rabattait le texte lu sur `""` en cas d'OSError puis réécrivait le
    fichier ENTIER en mode "w" : un échec de lecture détruisait silencieusement une page
    rédigée à la main."""

    REDIGE = (
        "# Wiki du hub de supervision\n\n"
        "Section ecrite a la main, la seule chose que ce fichier contienne de precieux.\n\n"
        + "Paragraphe de contenu redige, a ne perdre sous aucun pretexte.\n" * 20
    )

    def _index(self, tmp_path, monkeypatch, avec_marqueurs=True):
        index = tmp_path / "index.md"
        txt = self.REDIGE
        if avec_marqueurs:
            txt += f"\n{scan.MARK_START} -->\n## TODO agents\n\n- ancien\n{scan.MARK_END}\n"
        index.write_text(txt, encoding="utf-8")
        monkeypatch.setattr(scan, "WIKI_INDEX", str(index))
        return index

    def test_lecture_impossible_ne_reecrit_pas_le_fichier(self, tmp_path, monkeypatch, capsys):
        index = self._index(tmp_path, monkeypatch)
        avant = index.read_bytes()
        vrai_open = builtins.open

        def open_qui_echoue_en_lecture(fichier, mode="r", *a, **k):
            if os.path.abspath(str(fichier)) == str(index) and "w" not in mode and "a" not in mode:
                raise PermissionError(13, "acces refuse")
            return vrai_open(fichier, mode, *a, **k)

        monkeypatch.setattr(builtins, "open", open_qui_echoue_en_lecture)
        scan.update_index(["constat 1", "constat 2"])   # ne doit jamais lever : fail-open
        monkeypatch.undo()                              # avant toute relecture disque

        assert index.read_bytes() == avant, "un echec de LECTURE a ecrase le fichier"
        assert "index.md non mis a jour" in capsys.readouterr().out, "echec passe sous silence"

    def test_le_cas_nominal_met_toujours_a_jour_le_bloc(self, tmp_path, monkeypatch):
        """Garde-fou du correctif lui-même : renoncer sur OSError ne doit pas
        empêcher la mise à jour normale."""
        index = self._index(tmp_path, monkeypatch)
        scan.update_index(["constat frais"])
        txt = index.read_text(encoding="utf-8")
        assert "constat frais" in txt and "- ancien" not in txt
        assert self.REDIGE.split("\n")[2] in txt   # le texte redige a la main survit

    def test_fichier_absent_toujours_cree(self, tmp_path, monkeypatch):
        """L'autre garde-fou : le premier passage (page inexistante) doit encore créer."""
        index = tmp_path / "index.md"
        monkeypatch.setattr(scan, "WIKI_INDEX", str(index))
        scan.update_index(["constat 1"])
        assert scan.MARK_START in index.read_text(encoding="utf-8")


# --- Finding 3 (MOYEN) : journal JSONL abime, lecture toleree et comptee -----------
class TestFinding3JournalJsonlAbime:
    """Deux échecs silencieux cumulés : `UnicodeDecodeError` échappait au `except
    OSError` (un seul octet non-UTF-8 — ce que produit `Add-Content` en PowerShell —
    faisait remonter l'exception jusqu'au `except Exception` de `main()`, qui annulait
    TOUT le scan avec pour seule trace « scan ignore »), et une ligne corrompue était
    sautée sans compteur ni avertissement."""

    OCTETS = (
        b'{"ts": "2026-08-28T10:00:00", "demande": "run lisible", "qualification": "orchestre"}\n'
        b'{"ts": "2026-08-28T11:00:00", "demande": "caf\xe9 ecrit par Add-Content", "qualification": "orchestre"}\n'
        b'{ceci n est pas du json\n'
    )

    def test_octet_non_utf8_lu_et_ligne_corrompue_comptee(self, tmp_path):
        journal = tmp_path / "runs.jsonl"
        journal.write_bytes(self.OCTETS)

        runs = scan.load_jsonl(str(journal))   # levait UnicodeDecodeError

        assert len(runs) == 2, "la ligne a l'octet invalide doit etre lue, pas perdue"
        assert runs[0]["demande"] == "run lisible"
        assert runs[1]["demande"].startswith("caf")
        assert scan.LIGNES_ILLISIBLES[str(journal)] == 1, "ligne corrompue non comptee"

    def test_le_scan_survit_et_signale_la_ligne_illisible(self, scan_isole, capsys):
        (scan_isole / "runs.jsonl").write_bytes(self.OCTETS)
        assert scan.main([]) == 0
        sortie = capsys.readouterr().out
        assert "1 ligne(s) illisible(s)" in sortie, f"echec tu, sortie : {sortie!r}"
        assert "2 run(s) orchestrateur" in sortie   # le scan a bien tourne, pas « ignore »


# --- Finding 4 (FAIBLE) : state.json ecrit atomiquement ---------------------------
class TestFinding4EtatEcritAtomiquement:
    """`open(STATE_PATH, "w")` tronque AVANT d'écrire : une interruption en cours
    d'écriture laissait un state.json illisible, que `load_state` rabat sur `{}` — le
    scan repart de zéro sans le dire."""

    def test_ecriture_interrompue_ne_detruit_pas_letat_precedent(self, tmp_path, monkeypatch):
        etat = tmp_path / "state.json"
        precedent = {"files": {"a.jsonl": 1234}, "skills": {"pptx-deck": {"n": 3}}}
        etat.write_text(json.dumps(precedent), encoding="utf-8")
        monkeypatch.setattr(scan, "STATE_PATH", str(etat))

        class NonSerialisable:
            pass

        casse = dict(precedent)
        casse["bourrage"] = "x" * 20000        # depasse le tampon : des octets partent sur le disque
        casse["poison"] = NonSerialisable()    # ... puis json.dump leve, ecriture a moitie faite

        with pytest.raises(TypeError):
            scan.save_state(casse)

        assert scan.load_state() == precedent, "l'etat precedent a ete detruit"
        assert not list(tmp_path.glob("*.tmp")), "fichier temporaire laisse derriere"

    def test_ecriture_nominale_publie_bien_letat(self, tmp_path, monkeypatch):
        """Garde-fou du correctif : l'écriture atomique doit toujours publier."""
        etat = tmp_path / "state.json"
        monkeypatch.setattr(scan, "STATE_PATH", str(etat))
        scan.save_state({"files": {"b.jsonl": 7}})
        assert scan.load_state() == {"files": {"b.jsonl": 7}}
        assert not list(tmp_path.glob("*.tmp"))
