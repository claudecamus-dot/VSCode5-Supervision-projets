"""Robustesse du scanner : un projet abîmé dégrade SA mesure, jamais le scan entier.

Deux défauts reproduits par une revue adversariale le 2026-08-31, tous deux dans
`scripts/scan_projets.py`, tous deux du même genre — un incident local promu en panne
globale :

1. **`read_runs` explosait sur un octet non-UTF-8.** Le décodage se faisait hors du
   `try` interne et le `except` ne couvrait qu'`OSError` : un seul 0xe9 dans le
   `runs.jsonl` d'un projet (ce qu'écrit `Add-Content` en PowerShell 5.1 pour « é »)
   remontait en `UnicodeDecodeError` jusqu'à `main()`, qui n'a aucun handler. Toute la
   régénération du wiki tombait — l'inverse du fail-open que revendique `git_etat`.

2. **La publication tronquait l'artefact avant de savoir quoi écrire.**
   `open(chemin, "w")` vide le fichier à l'ouverture, donc avant l'évaluation du rendu
   passé à `fh.write(...)` : une exception pendant le rendu laissait publié un
   `docs/wiki.html` de 0 octet à la place des 230 013 de la page servie.

Les deux tests reproduisent le scénario sur des fichiers jetables (`tmp_path`) et sur
des globales monkeypatchées — jamais sur le wiki, l'historique ou les journaux réels.
"""

import importlib.util
import json
import os

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


# --- Finding 1 : journal d'un projet corrompu ------------------------------------

def test_read_runs_survit_a_un_octet_non_utf8(tmp_path):
    """Un 0xe9 brut au milieu du journal ne doit ni lever, ni arrêter la lecture."""
    journal = tmp_path / ".claude" / "orchestration" / "runs.jsonl"
    journal.parent.mkdir(parents=True)
    # Écriture en binaire : la 2e ligne porte l'octet 0xe9 nu (« café » en cp1252),
    # exactement ce que produit `Add-Content` sous PowerShell 5.1.
    journal.write_bytes(
        b'{"resultat": "succes", "demande": "premier run"}\n'
        b'{"resultat": "succes", "demande": "caf\xe9 corrompu"}\n'
        b'{"resultat": "en-attente-validation", "demande": "livrable a valider"}\n'
    )

    compteurs, en_attente = scan.read_runs(str(tmp_path))

    # Les lignes SUIVANT la corruption sont toujours mesurées : c'est le cœur du
    # correctif. Un `except UnicodeDecodeError` posé autour de la boucle rendrait
    # succes=1 et en_attente=[] — vert sans crash, mais la mesure serait fausse.
    assert compteurs.get("succes") == 2
    assert len(en_attente) == 1
    assert en_attente[0]["demande"] == "livrable a valider"


def test_read_json_et_read_text_degradent_sans_lever(tmp_path):
    """Les deux voisines de `read_runs` étaient déjà fail-open — on le fige ici.

    `read_text` décode déjà en `errors="replace"` ; `read_json` capture `ValueError`,
    dont `UnicodeDecodeError` est une sous-classe. Aucune des deux ne remonte donc
    d'exception sur un octet invalide — mais rien ne l'empêchait de régresser.
    """
    corrompu = tmp_path / "corrompu.json"
    corrompu.write_bytes(b'{"cle": "caf\xe9"}')

    assert scan.read_json(str(corrompu)) is None          # dégradé, pas fatal
    assert "caf" in scan.read_text(str(corrompu))         # lu en remplaçant l'octet
    assert scan.read_json(str(tmp_path / "absent.json")) is None
    assert scan.read_text(str(tmp_path / "absent.txt")) is None


# --- Finding 2 : publication des artefacts ---------------------------------------

@pytest.fixture
def hub_jetable(tmp_path, monkeypatch):
    """Détourne toutes les E/S de `main()` vers tmp_path — jamais le hub réel.

    `projets` vide : le scan n'a rien à lire chez la flotte, seule la mécanique de
    publication est sous test. HISTORY_PATH est détourné aussi, sinon `ecrire_snapshot`
    polluerait l'historique de production à chaque exécution de la suite.
    """
    config = tmp_path / "projets.json"
    config.write_text(json.dumps({"projets": []}), encoding="utf-8")
    out_md = tmp_path / "wiki" / "projets-supervision.md"
    out_html = tmp_path / "wiki.html"
    monkeypatch.setattr(scan, "CONFIG_PATH", str(config))
    monkeypatch.setattr(scan, "VEILLE_PATH", str(tmp_path / "veille.json"))
    monkeypatch.setattr(scan, "HISTORY_PATH", str(tmp_path / "history" / "snap.jsonl"))
    monkeypatch.setattr(scan, "OUT_MD", str(out_md))
    monkeypatch.setattr(scan, "OUT_HTML", str(out_html))
    return out_md, out_html


def test_main_publie_les_deux_artefacts(hub_jetable):
    """Garde-fou : la publication atomique écrit bien, et ne laisse pas de .tmp."""
    out_md, out_html = hub_jetable

    assert scan.main(["--no-refresh"]) == 0

    assert out_md.stat().st_size > 0
    assert out_html.stat().st_size > 0
    assert not (out_md.parent / (out_md.name + ".tmp")).exists()
    assert not (out_html.parent / (out_html.name + ".tmp")).exists()


@pytest.mark.parametrize("rendu, sortie", [("render_md", 0), ("render_html", 1)])
def test_un_rendu_qui_echoue_ne_tronque_pas_l_artefact_publie(
        hub_jetable, monkeypatch, rendu, sortie):
    """Le fichier déjà publié doit survivre intact à une exception pendant le rendu.

    Reproduit tel quel : `docs/wiki.html` passait de 230 013 octets à 0 sur une
    `KeyError` levée dans `render_html`, parce que le "w" avait déjà tronqué le fichier
    avant que le rendu ne soit évalué.
    """
    cible = hub_jetable[sortie]
    cible.parent.mkdir(parents=True, exist_ok=True)
    ancien = "<html>page publiée précédemment</html>\n" * 40
    cible.write_text(ancien, encoding="utf-8")

    def rendu_qui_casse(*args, **kwargs):
        raise KeyError("finding absent du dictionnaire pendant le rendu")

    monkeypatch.setattr(scan, rendu, rendu_qui_casse)

    with pytest.raises(KeyError):
        scan.main(["--no-refresh"])

    assert cible.read_text(encoding="utf-8") == ancien
    assert not (cible.parent / (cible.name + ".tmp")).exists()
