"""Un audit ne périme pas au calendrier — il périme au code écrit.

Finding `VScode5:audit-technique-perime`, arbitré le 2026-09-01 (« traite tous les points
de la page pilotage »). L'audit qualitatif du hub datait du 2026-07-29 et couvrait, de
son propre aveu, trois scripts. Depuis : 33 fichiers, 6 781 insertions, et neuf scripts
Python créés puis jamais audités — dont les deux qui ont produit les défauts du
2026-09-01. Rien ne le signalait : la péremption de l'audit était la seule cadence du
dispositif à n'être rappelée par aucun hook, contrairement à la veille (3 j), à la revue
d'incrément et au diagnostic étage 2 (14 j).

La règle retenue est une **double condition**, et les deux moitiés comptent :

* le **temps** seul crierait sur un dépôt gelé, qui n'a aucune raison de repayer un
  audit LLM tous les 30 jours ;
* les **lignes** seules laisseraient passer un audit très ancien sur un dépôt calme.

Mesuré le 2026-09-01, le détecteur discrimine réellement : VSCode (33 j, 669 lignes) n'est
pas signalé, les cinq autres le sont — de 5 750 à 42 647 lignes changées depuis leur audit.
"""

import datetime as dt
import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "scan_projets_audit", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

MAINTENANT = dt.datetime(2026, 9, 1, 12, 0, 0)

# Chemin COURT : le scratchpad de session dépasse MAX_PATH sous Windows et fabrique
# de faux échecs (mémoire `feedback-pytest-basetemp-jonction-morte`). Le helper le rend
# PORTABLE — une lettre de lecteur écrite en dur dans un fichier versionné est fausse
# partout ailleurs, la dette que `test_propager_socle._lire` avait déjà eu à corriger.
from conftest import tmp_court

TMP = tmp_court()


def _depot_temoin(nom, lignes):
    """Petit dépôt git réel, avec un unique commit de `lignes` lignes.

    Fabriqué plutôt qu'emprunté à la flotte : un test adossé à un dépôt vivant
    changerait de verdict au gré de l'activité du jour.
    """
    import shutil
    import subprocess
    chemin = os.path.join(TMP, nom)
    shutil.rmtree(chemin, ignore_errors=True)
    os.makedirs(chemin, exist_ok=True)
    with open(os.path.join(chemin, "fichier.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(f"ligne {i}" for i in range(lignes)) + "\n")
    for args in (("init", "-q"),
                 ("-c", "user.email=t@t", "-c", "user.name=t", "add", "."),
                 ("-c", "user.email=t@t", "-c", "user.name=t",
                  "commit", "-q", "-m", "temoin")):
        subprocess.run(["git", "-C", chemin, *args], capture_output=True, timeout=30)
    return chemin


def _projet(date_audit, chemin=None):
    return {
        "nom": "sonde",
        "chemin": chemin or HUB,
        "audit": None if date_audit is None else {"date": date_audit, "dimensions": {}},
    }


class TestLaDoubleCondition:
    def test_un_audit_recent_n_est_jamais_perime(self):
        """Même sur le hub, où des milliers de lignes bougent : la fraîcheur prime."""
        perime, jours, _l = scan.audit_perime(
            _projet(MAINTENANT.strftime("%Y-%m-%d")), MAINTENANT)
        assert perime is False
        assert jours == 0

    def test_un_depot_gele_ne_perime_pas_malgre_l_age(self):
        """La moitié « code » de la condition, sur un dépôt git RÉEL et minuscule.

        Sans elle, un projet qu'on ne touche plus réclamerait un audit LLM facturé
        tous les 30 jours pour rien. Le dépôt témoin est fabriqué ici plutôt que pris
        dans la flotte : un test adossé à un dépôt vivant vire au vert ou au rouge
        selon l'activité du jour, ce qui n'est pas un test.
        """
        depot = _depot_temoin("sonde_audit_gele", lignes=5)
        vieux = (dt.datetime.now() - dt.timedelta(days=400)).strftime("%Y-%m-%d")
        perime, jours, lignes = scan.audit_perime(
            _projet(vieux, chemin=depot), dt.datetime.now())
        assert jours >= 399, "l'âge n'est pas mesuré"
        assert lignes is not None and lignes < scan.AUDIT_LIGNES_SEUIL, (
            f"le dépôt témoin doit rester sous le seuil ({lignes} lignes)")
        assert perime is False, "un dépôt gelé est signalé alors que rien n'a bougé"

    def test_le_meme_depot_perime_des_que_le_code_bouge(self):
        """L'autre moitié : même âge, mais du code écrit → l'audit doit être rejoué.
        C'est la paire qui prouve que la double condition discrimine vraiment."""
        depot = _depot_temoin("sonde_audit_actif", lignes=scan.AUDIT_LIGNES_SEUIL + 50)
        vieux = (dt.datetime.now() - dt.timedelta(days=400)).strftime("%Y-%m-%d")
        perime, _j, lignes = scan.audit_perime(
            _projet(vieux, chemin=depot), dt.datetime.now())
        assert lignes > scan.AUDIT_LIGNES_SEUIL
        assert perime is True, "un dépôt très modifié n'est pas signalé"

    def test_git_absent_ne_fait_pas_echouer_le_scan(self):
        """Fail-open : hors dépôt git, on ne signale rien plutôt qu'un faux retard."""
        hors_git = os.path.join(TMP, "sonde_hors_git")
        os.makedirs(hors_git, exist_ok=True)
        vieux = (dt.datetime.now() - dt.timedelta(days=400)).strftime("%Y-%m-%d")
        perime, jours, lignes = scan.audit_perime(
            _projet(vieux, chemin=hors_git), dt.datetime.now())
        assert perime is False and lignes is None
        assert jours >= 399, "l'âge doit rester mesuré même quand git ne répond pas"

    def test_un_projet_jamais_audite_n_est_pas_un_retard(self):
        """« Pas encore audité » et « audit périmé » sont deux états distincts :
        les confondre ferait afficher un retard permanent sur tout projet neuf."""
        perime, jours, lignes = scan.audit_perime(_projet(None), MAINTENANT)
        assert (perime, jours, lignes) == (False, None, None)

    def test_une_date_illisible_ne_fait_pas_echouer_le_scan(self):
        """Règle du scan : jamais échouer pour un fichier."""
        perime, jours, _l = scan.audit_perime(_projet("pas-une-date"), MAINTENANT)
        assert perime is False and jours is None

    def test_les_deux_seuils_sont_declares_et_coherents(self):
        assert scan.CADENCE_AUDIT_J > 0 and scan.AUDIT_LIGNES_SEUIL > 0
        assert scan.CADENCE_AUDIT_J > scan.CADENCE_DIAGNOSTIC_J, (
            "un audit qualitatif se relance moins souvent qu'un diagnostic étage 2")


class TestLeSignalArriveAuPosteDePilotage:
    """Un détecteur qui n'atteint pas la page ne sert à rien : c'est exactement ce
    qui manquait — la cadence d'audit n'était rappelée nulle part."""

    def test_le_retard_d_audit_est_rendu_avec_ses_deux_chiffres(self):
        """« périmé depuis 34 j » seul ne dit pas s'il y a de quoi le repayer ;
        le volume de code changé est la moitié de l'information.

        Corrigé le 2026-09-04 (finding diagnostic `suite-rouge-requalifiee-explicable`) :
        cette assertion dépendait de l'état RÉEL des 6 projets — vrai le jour où elle a
        été écrite (le hub avait un audit périmé), faux dès que les 6 audits sont
        redevenus frais (mesuré le 2026-09-04 : aucun n'a plus de 3 jours). Un test qui
        change de verdict au gré du calendrier n'est pas un test, c'est la même leçon
        que `test_un_depot_gele_ne_perime_pas_malgre_l_age` capitalise déjà juste
        au-dessus dans ce fichier. On construit ici un projet synthétique (même moule
        que `_depot_temoin`) au lieu de lire la config/les audits réels — le signal
        testé reste le VRAI `compute_pilotage`, seule la matière d'entrée devient
        déterministe."""
        depot = _depot_temoin("sonde_pilotage_audit", lignes=scan.AUDIT_LIGNES_SEUIL + 50)
        vieux = (dt.datetime.now() - dt.timedelta(days=scan.CADENCE_AUDIT_J + 5)) \
            .strftime("%Y-%m-%d")
        projects = [{
            "nom": "sonde", "chemin": depot, "existe": True, "alerte": None,
            "audit": {"date": vieux, "dimensions": {}},
            "last_scan": None, "diag_date": None, "dernier_commit": None,
            "runs_en_attente": [],
        }]
        pil = scan.compute_pilotage(projects, scan.load_veille(), dt.datetime.now())
        lignes_audit = [r for r in pil["retards"] if "audit technique" in r]
        assert lignes_audit, (
            "aucun retard d'audit remonté au pilotage sur un projet sciemment périmé")
        for ligne in lignes_audit:
            assert "lignes changées depuis" in ligne, (
                f"retard d'audit sans volume de code : {ligne}")

    def test_le_volume_est_mesure_sur_un_depot_reel_de_la_flotte(self):
        """Le détecteur doit répondre sur un vrai dépôt, pas seulement sur un témoin.

        On vérifie que le volume est MESURÉ (`lignes is not None`), pas qu'il est non
        nul : zéro ligne depuis un audit du jour est une mesure juste. Confondre les
        deux rendait ce test rouge dès que l'audit du hub était rafraîchi — c'est-à-dire
        dès qu'il faisait son travail.
        """
        projet = _projet(None)
        projet["audit"] = scan.load_audit("VScode5")
        if not projet["audit"]:
            return          # audit pas encore écrit : rien à vérifier
        perime, jours, lignes = scan.audit_perime(projet, dt.datetime.now())
        assert jours is not None, "l'âge de l'audit du hub n'est pas lu"
        assert lignes is not None, "git n'a pas répondu sur un dépôt réel de la flotte"
        assert perime == (jours > scan.CADENCE_AUDIT_J
                          and lignes > scan.AUDIT_LIGNES_SEUIL), (
            f"verdict incohérent avec ses propres seuils : {jours} j, {lignes} lignes")
