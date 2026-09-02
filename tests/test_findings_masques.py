"""Le hub s'était écrit une seconde version, naïve, d'une règle que le canon tenait déjà.

Demande utilisateur du 2026-09-02 (« beaucoup de projets sont notés critiques, est-ce
normal ? »), arbitrage « les deux » : comparer les dates ET signaler ce qui était masqué.

CE QUE LE HUB FAISAIT. `scan_projets.py` construisait l'ensemble de TOUTES les cibles
jamais arbitrées et écartait tout finding dont la cible s'y trouvait — sans regarder ni la
catégorie, ni la date, ni le drapeau `re_challenge`. `diag_date` était lu deux lignes plus
haut et jamais utilisé. Conséquence : **un finding dont la cible a été arbitrée une fois
devenait invisible pour toujours**, et plus un sujet récidivait, plus sûrement ses nouveaux
constats disparaissaient — l'inverse exact de ce qu'on attend d'un tableau de bord.

Mesuré sur la flotte le 2026-09-02, avant correction : 3 findings invisibles, dont un p5.
`revue-increment` chez VSCode2 portait **10 arbitrages, tous de juillet** ; son constat du
2026-09-01 (« 33 jours sans une seule invocation ») était éteint par eux.

CE QUE LE CANON TENAIT DÉJÀ, et qui rend ce correctif petit. `finding_arbitre()`
(`.claude/dispositif/canon/scan_transcripts.py`) compare la cible ET la couverture de
catégorie, et traite le drapeau `re_challenge` : un constat re-challengé n'est refermé que
par un arbitrage du JOUR du diagnostic ou postérieur — la comparaison est à la journée
parce que les arbitrages ne portent qu'une date là où le diagnostic porte un horodatage.
`diagnostic_masques()` rend en plus VISIBLES les constats écartés, « le filtrage était
silencieux » (2026-07-28). Les deux moitiés de l'arbitrage existaient donc déjà.

On ne réécrit pas une troisième version : le hub RÉUTILISE le canon. C'est la leçon que ce
dépôt paie en boucle — deux définitions d'une même chose finissent par diverger, et c'est
la plus récente qui perd, parce que personne ne sait qu'elle existe.

VÉRIFICATION D'INTENTION, faite avant d'écrire : appliquée aux 3 findings masqués, la
règle du canon en rouvre 2 (ceux qui portent `re_challenge: True`) et laisse le 3ᵉ fermé
(VSCode4/`export-ppt-verifie`, sans re-challenge). Le correctif ne rouvre donc pas tout :
il rouvre ce que le superviseur avait explicitement re-challengé.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets_masques", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

DIAG = {
    "generated": "2026-09-01T22:04:53+02:00",
    "findings": [
        {"cible": "revue-increment", "categorie": "verification-manquante",
         "priorite": 5, "titre": "33 jours sans une seule invocation",
         "re_challenge": True},
        {"cible": "export-ppt-verifie", "categorie": "verification-manquante",
         "priorite": 1, "titre": "les chiffres derivent"},
        {"cible": "jamais-arbitre", "categorie": "verification-manquante",
         "priorite": 3, "titre": "constat neuf"},
    ],
}
ARBITRAGES = [
    {"cible": "revue-increment", "date": "2026-07-31", "decision": "ACCEPTE : ancien"},
    {"cible": "export-ppt-verifie", "date": "2026-07-23", "decision": "ACCEPTE : ancien"},
]


class TestUnReChallengeNestPasEteintParUnArbitrageAnterieur:
    def test_le_constat_re_challenge_reste_ouvert(self):
        ouverts, _ = scan.findings_ouverts(DIAG, ARBITRAGES)
        cibles = {f["cible"] for f in ouverts}
        assert "revue-increment" in cibles, (
            "un constat explicitement re-challengé par le superviseur, avec des données "
            "nouvelles, reste éteint par un arbitrage de juillet — c'est le tableau de "
            f"bord qui cache une alerte. Ouverts : {sorted(cibles)}")

    def test_un_constat_SANS_re_challenge_reste_ferme(self):
        """Le correctif ne rouvre pas tout : sans re-challenge, un arbitrage couvrant
        ferme légitimement. Sinon on remplacerait un tableau qui cache par un tableau
        qui crie, et les deux se lisent aussi mal."""
        ouverts, _ = scan.findings_ouverts(DIAG, ARBITRAGES)
        assert "export-ppt-verifie" not in {f["cible"] for f in ouverts}

    def test_un_constat_jamais_arbitre_reste_ouvert(self):
        ouverts, _ = scan.findings_ouverts(DIAG, ARBITRAGES)
        assert "jamais-arbitre" in {f["cible"] for f in ouverts}


class TestCeQuiEstMasqueEstNomme:
    """« Le filtrage était silencieux » — deuxième moitié de l'arbitrage."""

    def test_les_masques_sont_rendus(self):
        _, masques = scan.findings_ouverts(DIAG, ARBITRAGES)
        assert masques, "aucun constat masqué n'est remonté : le filtrage reste muet"
        assert "export-ppt-verifie" in {f.get("cible") for f in masques}

    def test_un_constat_ouvert_n_est_pas_compte_comme_masque(self):
        ouverts, masques = scan.findings_ouverts(DIAG, ARBITRAGES)
        assert not ({f["cible"] for f in ouverts} & {f.get("cible") for f in masques}), (
            "un même constat est à la fois ouvert et masqué : le lecteur ne peut plus "
            "savoir lequel des deux compteurs croire")


class TestFailOpen:
    def test_sans_arbitrage_tout_est_ouvert(self):
        ouverts, masques = scan.findings_ouverts(DIAG, [])
        assert len(ouverts) == 3 and not masques

    def test_un_diagnostic_vide_ne_leve_pas(self):
        ouverts, masques = scan.findings_ouverts({}, ARBITRAGES)
        assert ouverts == [] and masques == []
