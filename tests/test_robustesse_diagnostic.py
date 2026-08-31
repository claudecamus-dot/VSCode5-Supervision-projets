"""Tests de robustesse pour trois defauts REPRODUITS par une revue adversariale
(2026-08-31) sur le dispositif de supervision.

Finding 1 -- point_du_jour.py lisait la cle "genere" (ou "date") alors que
write_diagnostic.py ecrit "generated" : `posterieur_a` valait donc toujours "", ce
qui coupait court `finding_arbitre()` (jour="" -> False) et laissait indefiniment
OUVERT un finding re_challenge deja arbitre le jour meme.

Finding 2 -- write_diagnostic.py reecrit diagnostic.json en entier sans comparer aux
findings ouverts precedents (une regeneration partielle en perd silencieusement, sans
message) et acceptait un finding sans cible non vide, alors que point_du_jour.py saute
justement les findings sans cible -- un constat valide devenait structurellement
invisible.

Finding 3 -- log_run.py (canon .claude/dispositif/canon/log_run.py) reecrivait
runs.jsonl en mode "w" direct dans `solder()` : une interruption pendant l'ecriture
(Ctrl-C, coupure, disque plein) tronque le journal a mi-parcours.

Tous les tests travaillent sur des fichiers jetables (tmp_path) ; aucun ne touche aux
fichiers reels du depot (diagnostic.json, runs.jsonl). Modules charges par chemin via
importlib, comme tests/test_export_agentic.py -- ces trois scripts sont des
executables autonomes, pas un package importable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POINT_DU_JOUR = os.path.join(RACINE, ".claude", "hooks", "point_du_jour.py")
WRITE_DIAGNOSTIC = os.path.join(RACINE, ".claude", "supervision", "write_diagnostic.py")
LOG_RUN_CANON = os.path.join(RACINE, ".claude", "dispositif", "canon", "log_run.py")


def _charger(chemin: str, nom: str):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)
    return module


class TestFinding1ClePosterieurA:
    """point_du_jour.py doit lire la cle que write_diagnostic.py ecrit reellement."""

    def test_re_challenge_arbitre_le_jour_meme_est_reconnu_clos(self, tmp_path):
        pdj = _charger(POINT_DU_JOUR, "pdj_finding1")
        diag = tmp_path / "diagnostic.json"
        diag.write_text(json.dumps({
            "generated": "2026-08-31T09:00:00+02:00",
            "findings": [
                {"cible": "skill-z", "categorie": "ko-repete", "re_challenge": True},
            ],
        }), encoding="utf-8")
        arb = tmp_path / "arbitrages.json"
        arb.write_text(json.dumps({
            "arbitrages": [
                {"cible": "skill-z", "categories": ["ko-repete"],
                 "date": "2026-08-31T10:00:00+02:00"},
            ],
        }), encoding="utf-8")
        pdj.DIAGNOSTIC = str(diag)
        pdj.ARBITRAGES = str(arb)
        assert pdj.findings_non_arbitres() == [], (
            "un re_challenge arbitre le jour meme doit etre reconnu clos, pas laisse "
            "ouvert par une lecture de cle qui rate toujours 'generated'")


class TestFinding2EcritureDiagnostic:
    """write_diagnostic.py doit avertir des findings ouverts qui disparaissent, et
    refuser un finding sans cible non vide."""

    def test_avertit_des_findings_ouverts_qui_disparaissent(self, tmp_path, capsys):
        diag_path = tmp_path / "diagnostic.json"
        diag_path.write_text(json.dumps({
            "generated": "2026-08-30T10:00:00+02:00",
            "findings": [
                {"categorie": "ko-repete", "titre": "Ancien A", "preuve": "p1", "cible": "x"},
                {"categorie": "agent-mort", "titre": "Ancien B", "preuve": "p2", "cible": "y"},
            ],
        }), encoding="utf-8")
        wd = _charger(WRITE_DIAGNOSTIC, "wd_finding2a")
        wd.DIAGNOSTIC_PATH = str(diag_path)
        nouveau = json.dumps({"findings": [
            {"categorie": "ko-repete", "titre": "Nouveau C", "preuve": "p3", "cible": "z"},
        ]})
        rc = wd.main([nouveau])
        sortie = capsys.readouterr().out
        assert rc == 0, sortie
        assert "AVERTISSEMENT" in sortie
        assert "Ancien A" in sortie and "Ancien B" in sortie
        relu = json.loads(diag_path.read_text(encoding="utf-8"))
        assert [f["titre"] for f in relu["findings"]] == ["Nouveau C"], (
            "la reecriture integrale reste le mode normal : avertir, pas bloquer")

    def test_precedent_illisible_avertit_bruyamment(self, tmp_path, capsys):
        """Correctif 6 (2026-08-31) : `except (OSError, ValueError): anciens = []`
        rendait le garde-fou anti-perte MUET quand il servait le plus. Avec un
        precedent SAIN il avertit ; avec un precedent TRONQUE il ne disait plus rien,
        et comme le fichier est reecrit en entier de facon non atomique il pouvait se
        tronquer lui-meme puis neutraliser sa propre alarme au tour suivant."""
        diag_path = tmp_path / "diagnostic.json"
        sain = json.dumps({
            "generated": "2026-08-30T10:00:00+02:00",
            "findings": [
                {"categorie": "ko-repete", "titre": "Ancien A", "preuve": "p1", "cible": "x"},
                {"categorie": "agent-mort", "titre": "Ancien B", "preuve": "p2", "cible": "y"},
            ],
        }, ensure_ascii=False)
        diag_path.write_text(sain[:120], encoding="utf-8")   # tronque, comme sur disque
        wd = _charger(WRITE_DIAGNOSTIC, "wd_finding6a")
        wd.DIAGNOSTIC_PATH = str(diag_path)
        rc = wd.main([json.dumps({"findings": [
            {"categorie": "ko-repete", "titre": "Nouveau C", "preuve": "p3", "cible": "z"},
        ]})])
        sortie = capsys.readouterr().out
        assert rc == 0, sortie
        assert "AVERTISSEMENT" in sortie and "illisible" in sortie.lower(), (
            "un precedent illisible doit s'entendre, pas s'effacer en silence : "
            f"sortie {sortie!r}")
        relu = json.loads(diag_path.read_text(encoding="utf-8"))
        assert [f["titre"] for f in relu["findings"]] == ["Nouveau C"]

    def test_precedent_absent_nnavertit_pas(self, tmp_path, capsys):
        """Absence != corruption : un premier diagnostic ne doit rien annoncer."""
        diag_path = tmp_path / "diagnostic.json"
        wd = _charger(WRITE_DIAGNOSTIC, "wd_finding6b")
        wd.DIAGNOSTIC_PATH = str(diag_path)
        rc = wd.main([json.dumps({"findings": [
            {"categorie": "ko-repete", "titre": "Premier", "preuve": "p", "cible": "z"},
        ]})])
        sortie = capsys.readouterr().out
        assert rc == 0
        assert "AVERTISSEMENT" not in sortie, sortie

    def test_ecriture_atomique_une_coupure_ne_tronque_pas(self, tmp_path, monkeypatch):
        """L. 107 ecrivait en "w" direct : une coupure tronquait diagnostic.json, qui
        neutralisait ensuite sa propre alarme au tour suivant."""
        diag_path = tmp_path / "diagnostic.json"
        avant = json.dumps({
            "generated": "2026-08-30T10:00:00+02:00",
            "findings": [{"categorie": "ko-repete", "titre": "Ancien A",
                          "preuve": "p1", "cible": "x"}],
        }, ensure_ascii=False, indent=1)
        diag_path.write_text(avant, encoding="utf-8")
        wd = _charger(WRITE_DIAGNOSTIC, "wd_finding6c")
        wd.DIAGNOSTIC_PATH = str(diag_path)

        def dump_qui_casse(*a, **k):
            raise RuntimeError("coupure simulee pendant l'ecriture")

        monkeypatch.setattr(wd.json, "dump", dump_qui_casse)
        with pytest.raises(RuntimeError):
            wd.main([json.dumps({"findings": [
                {"categorie": "ko-repete", "titre": "Nouveau C", "preuve": "p3", "cible": "z"},
            ]})])
        assert diag_path.read_text(encoding="utf-8") == avant, (
            "une ecriture interrompue ne doit jamais tronquer diagnostic.json")

    def test_docstring_ne_reference_pas_de_document_inexistant(self):
        """`docs/reflexions/agent-superviseur.md` n'existe pas et n'a jamais existe."""
        source = open(WRITE_DIAGNOSTIC, encoding="utf-8").read()
        assert "docs/reflexions/agent-superviseur.md" not in source

    def test_refuse_un_finding_sans_cible(self, tmp_path, capsys):
        diag_path = tmp_path / "diagnostic.json"
        wd = _charger(WRITE_DIAGNOSTIC, "wd_finding2b")
        wd.DIAGNOSTIC_PATH = str(diag_path)
        raw = json.dumps({"findings": [
            {"categorie": "ko-repete", "titre": "Sans cible", "preuve": "preuve mesuree"},
        ]})
        rc = wd.main([raw])
        sortie = capsys.readouterr().out
        assert rc == 1
        assert "cible" in sortie
        assert not diag_path.exists(), "un finding refuse ne doit rien ecrire"


class TestFinding3EcritureAtomiqueSolder:
    """log_run.py (canon) : solder() ne doit jamais laisser runs.jsonl tronque si
    l'ecriture est interrompue en cours de route."""

    def test_une_ecriture_interrompue_ne_tronque_pas_le_journal(self, tmp_path, monkeypatch):
        lr = _charger(LOG_RUN_CANON, "lr_finding3")
        runs_path = tmp_path / "runs.jsonl"
        lignes = [
            {"ts": "2026-08-30T10:00:00+02:00", "demande": "premier run",
             "qualification": "orchestre", "resultat": "en-cours"},
            {"ts": "2026-08-31T09:00:00+02:00", "demande": "run a solder",
             "qualification": "orchestre", "resultat": "en-cours"},
        ]
        contenu_avant = "\n".join(json.dumps(r, ensure_ascii=False) for r in lignes) + "\n"
        runs_path.write_text(contenu_avant, encoding="utf-8")
        lr.RUNS_PATH = str(runs_path)

        appels = {"n": 0}
        vrai_dumps = json.dumps

        def dumps_qui_casse(obj, **kwargs):
            appels["n"] += 1
            if appels["n"] == 2:
                raise RuntimeError("coupure simulee pendant l'ecriture")
            return vrai_dumps(obj, **kwargs)

        with monkeypatch.context() as mp:
            mp.setattr(json, "dumps", dumps_qui_casse)
            with pytest.raises(RuntimeError):
                lr.solder(["2026-08-31T09", "succes", "note"])

        assert runs_path.read_text(encoding="utf-8") == contenu_avant, (
            "une ecriture interrompue ne doit jamais tronquer le journal reel : elle "
            "doit rester dans un fichier temporaire jusqu'a l'os.replace final")

        # Chemin normal (non interrompu) : solder() doit toujours fonctionner ensuite.
        rc = lr.solder(["2026-08-31T09", "succes", "note ok"])
        assert rc == 0
        requalifie = [json.loads(l) for l in runs_path.read_text(encoding="utf-8").splitlines()]
        assert requalifie[1]["resultat"] == "succes"
