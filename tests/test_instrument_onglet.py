"""L'instrument qui sépare « boutons introuvables » de « boutons inutiles ».

Arbitré par l'utilisateur le 2026-09-02 (« poser l'instrument d'abord »), sur demande de
la salle `inspection-critique`.

CE QUE LE ZÉRO NE DIT PAS. `jobs.jsonl` n'a pas reçu une seule action en 32 jours et
14 heures. `vues.jsonl` compte 24 ouvertures de page sur la même période. Le second
compteur, posé le 2026-08-31, a éliminé une des trois lectures du zéro — « la page ne
s'ouvre jamais » est faux. Il n'a pas séparé les deux autres, et c'est exactement là que
la salle s'est divisée :

- **Jamais atteint** — l'onglet qui porte les boutons n'est pas ouvert : Portevoix a
  raison, c'est un problème de porte, et retirer la console reviendrait à condamner une
  pièce que personne n'a trouvée.
- **Atteint et jamais cliqué** — Quincaillier a raison, c'est un problème d'utilité, et
  la Rupture C se décide sur une mesure.

Sans cet instrument, l'arbitrage de la Rupture C se fait sur une conviction. Avec lui, il
se fait sur un chiffre — et c'est la seule chose que la salle a demandée AVANT l'arbitrage
plutôt qu'à sa place.

CE QUE L'INSTRUMENT NE PRÉTEND PAS MESURER. Il ne compte que le canal SERVI. Une page
ouverte en `file://` n'atteint pas ce serveur pour ses changements d'onglet, donc le
dénominateur reste partiel. C'est pourquoi la règle de vérification de `CLAUDE.md` a été
corrigée le même jour : elle prescrivait d'ouvrir `docs/wiki.html` directement, c'est-à-dire
le canal où la console est morte par construction.

BORNAGE, ET POURQUOI IL COMPTE. La route accepte un identifiant d'onglet de forme
contrainte, jamais du texte libre : le filtre CORS autorise encore `origin == "null"`
(décision instruite, conservée pour ne pas casser le canal `file://`), donc n'importe
quelle page locale peut poster ici. Un journal de mesure qu'on peut remplir de texte
arbitraire ne mesure plus rien — ce serait reproduire, dans l'instrument, le défaut qu'il
vient corriger.
"""

import importlib.util
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "serve_wiki.py")


@pytest.fixture(scope="module")
def serveur_et_journal(tmp_path_factory):
    """Vrai serveur sur port éphémère, journal des vues DÉTOURNÉ vers un fichier jetable.

    Le détournement est la condition d'existence de ce test : la mesure d'usage réelle a
    déjà été polluée une fois par sa propre vérification (une ligne `valider`/`annule`
    écrite en production le 2026-09-02 à 09:51:55 par la reproduction d'un défaut). Un
    test qui écrirait dans `vues.jsonl` corromprait le chiffre qu'il sert à produire.
    """
    tmp = tmp_path_factory.mktemp("instrument_onglet")
    journal = tmp / "vues.jsonl"
    os.environ["AGENT_SUPERVISION_VUES_JOURNAL"] = str(journal)
    os.environ["AGENT_SUPERVISION_ARBITRAGES"] = str(tmp / "arbitrages.json")
    os.environ["AGENT_SUPERVISION_SKIP_SCAN"] = "1"

    spec = importlib.util.spec_from_file_location("serve_wiki_onglet", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert str(journal) == mod.VUES_JOURNAL, (
        "le journal des vues n'a pas été détourné : ce test écrirait dans la mesure réelle")

    srv = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/ping", timeout=1)
            break
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.05)
    else:
        pytest.fail("serveur de test jamais monté")
    try:
        yield base, journal, mod
    finally:
        srv.shutdown()
        srv.server_close()
        os.environ.pop("AGENT_SUPERVISION_VUES_JOURNAL", None)


def _post(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def _lignes(journal):
    if not os.path.exists(journal):
        return []
    with io.open(journal, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


class TestLOngletEstJournalise:
    def test_un_changement_d_onglet_ecrit_une_ligne_qui_le_nomme(self, serveur_et_journal):
        base, journal, _ = serveur_et_journal
        avant = len(_lignes(journal))
        status, _ = _post(base, "/api/onglet", {"onglet": "pilotage"})
        assert status == 200
        lignes = _lignes(journal)
        assert len(lignes) == avant + 1, "aucune ligne écrite"
        assert lignes[-1].get("onglet") == "pilotage"
        assert lignes[-1].get("ts"), "une mesure sans horodatage ne sert à rien"

    def test_deux_onglets_differents_sont_distingues(self, serveur_et_journal):
        base, journal, _ = serveur_et_journal
        _post(base, "/api/onglet", {"onglet": "analyser"})
        _post(base, "/api/onglet", {"onglet": "arbitrer"})
        vus = [l.get("onglet") for l in _lignes(journal)]
        assert "analyser" in vus and "arbitrer" in vus

    def test_l_ouverture_de_page_reste_distinguable_d_un_changement_d_onglet(
            self, serveur_et_journal):
        """Les 24 ouvertures déjà mesurées ne portent pas de champ `onglet` : la lecture
        du journal historique ne doit pas être cassée par le nouveau champ."""
        base, journal, _ = serveur_et_journal
        urllib.request.urlopen(base + "/", timeout=10).read()
        ouvertures = [l for l in _lignes(journal) if "onglet" not in l]
        assert ouvertures, "l'ouverture de page n'écrit plus de ligne sans onglet"
        assert ouvertures[-1].get("chemin") == "/"


class TestLInstrumentEstBorne:
    """Le filtre CORS autorise encore `origin == \"null\"` : toute page locale peut poster
    ici. Un journal de mesure remplissable de texte arbitraire ne mesure plus rien."""

    @pytest.mark.parametrize("valeur", [
        "a" * 200,                      # trop long
        "pilotage; rm -rf /",           # ponctuation libre
        "../../../etc/passwd",          # chemin
        "onglet avec espaces",
        "ONGLET",                       # casse non prévue
        "",                             # vide
        None,                           # absent
        {"pas": "une chaine"},
    ])
    def test_une_valeur_hors_forme_n_ecrit_rien(self, serveur_et_journal, valeur):
        base, journal, _ = serveur_et_journal
        avant = len(_lignes(journal))
        status, _ = _post(base, "/api/onglet", {"onglet": valeur})
        assert status == 400, f"valeur acceptée : {valeur!r}"
        assert len(_lignes(journal)) == avant, (
            f"une ligne a été écrite pour une valeur hors forme : {valeur!r}")

    def test_un_corps_trop_volumineux_est_refuse(self, serveur_et_journal):
        base, journal, _ = serveur_et_journal
        avant = len(_lignes(journal))
        status, _ = _post(base, "/api/onglet", {"onglet": "pilotage", "bourrage": "x" * 70000})
        assert status == 400
        assert len(_lignes(journal)) == avant


class TestFailOpen:
    """Mesurer l'usage ne doit jamais empêcher l'usage — même promesse que les deux
    autres journaux du fichier."""

    def test_un_journal_inecrivable_ne_fait_pas_echouer_la_requete(
            self, serveur_et_journal, monkeypatch, tmp_path):
        """La première version de ce test monkeypatchait `_journaliser_ligne`, que
        `_journaliser_vue` n'appelle PAS — elle ouvre le fichier elle-même. Il passait
        sans rien exercer : vert par construction, exactement le défaut que ce dépôt a
        déjà payé. On rend donc le journal RÉELLEMENT inécrivable, en plaçant son
        répertoire parent sur un fichier ordinaire : `os.makedirs` lève alors une
        `OSError` (`FileExistsError` sur Windows, mesuré ; `NotADirectoryError` ailleurs),
        et c'est le vrai chemin d'erreur qui est mesuré.

        Vérifié par injection de faute le 2026-09-02 : en remplaçant le
        `except (OSError, TypeError, ValueError)` de `_journaliser_vue` par un
        `except (TypeError,)`, ce test passe au ROUGE. Il peut donc échouer."""
        base, _, mod = serveur_et_journal
        obstacle = tmp_path / "pas-un-dossier"
        obstacle.write_text("je suis un fichier", encoding="utf-8")
        monkeypatch.setattr(mod, "VUES_JOURNAL", str(obstacle / "vues.jsonl"))

        # Le garde-fou du garde-fou : on prouve que le chemin choisi échoue vraiment,
        # sinon ce test mesurerait à nouveau une écriture qui réussit.
        with pytest.raises(OSError):
            os.makedirs(os.path.dirname(mod.VUES_JOURNAL), exist_ok=True)

        status, _ = _post(base, "/api/onglet", {"onglet": "pilotage"})
        assert status == 200, "l'échec du journal a été rendu visible au client"
