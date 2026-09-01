"""Le manifeste de fonctionnement, et les deux salles neuves qui ne doublent personne.

Demandes utilisateur du 2026-09-01, dans l'ordre où elles sont arrivées :
  1. « une salle pour inspecter régulièrement le code pour les possibilités de bug ou
     fournir un regard critique sur le code » ;
  2. « le regard critique doit aussi porter sur le design, sur l'expérience utilisateur,
     sur les fonctionnalités jamais utilisées » ;
  3. « une nouvelle salle pour gérer le déploiement en prod et autres environnements
     nécessaires ainsi que toute la gestion de l'infrastructure » ;
  4. « ajoute pour chaque salle un manifeste de fonctionnement ».

LE RISQUE PRINCIPAL ÉTAIT LA DUPLICATION, pas l'absence. Deux salles existaient déjà
tout près : `code-review-crew` (regard critique sur du code) et `mise-en-service`
(déploiement, environnements). Une salle qui double sa voisine est pire qu'une salle
manquante — elle se convoque au hasard de l'humeur et personne ne sait laquelle
choisir. Les tests ci-dessous exigent donc que la FRONTIÈRE soit écrite dans la scène,
pas seulement dans la tête de celui qui a créé la salle :

  * `code-review-crew` part d'un DIFF ; `inspection-critique` part d'un PÉRIMÈTRE et de
    mesures d'usage, et couvre trois axes qu'aucune salle ne portait — design, UX, et
    ce qui n'est jamais utilisé.
  * `mise-en-service` est un GUICHET, une fois, par release ; `socle-technique` tient
    l'infrastructure dans la durée.

Le manifeste, lui, répond à ce que ni la scène ni le contrat ne disaient : COMMENT la
salle siège. Il est vérifié STRUCTURELLEMENT (les cinq rubriques) et non sur sa
longueur — un manifeste qui n'aurait pas de règle d'arrêt laisserait la salle tourner.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")

_spec = importlib.util.spec_from_file_location(
    "scan_projets_manifeste", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

RUBRIQUES = ("MODE", "DÉROULÉ", "DÉSACCORD", "ARRÊT", "JAMAIS")


def _salles():
    _membres, groupes = scan.party_collectif()
    return {g["id"]: g for g in groupes}


class TestManifestePourChaqueSalle:
    def test_toutes_les_salles_en_portent_un(self):
        sans = sorted(sid for sid, g in _salles().items() if not g.get("manifeste"))
        assert not sans, f"salle(s) sans manifeste de fonctionnement : {sans}"

    def test_les_cinq_rubriques_y_sont_toutes(self):
        """La même charpente partout : c'est ce qui permet de comparer deux salles
        et de repérer celle qui dérive de son propre mode d'emploi."""
        for sid, g in _salles().items():
            joint = " ".join(g["manifeste"])
            manquantes = [r for r in RUBRIQUES if r not in joint]
            assert not manquantes, f"{sid} : rubrique(s) manquante(s) {manquantes}"

    def test_chaque_salle_a_une_regle_d_arret(self):
        """Sans règle d'arrêt, une salle tourne — la panne que Killjoy existe pour
        couper. La rubrique doit dire QUAND on s'arrête, pas seulement qu'on s'arrête."""
        for sid, g in _salles().items():
            ligne = next(l for l in g["manifeste"] if l.startswith("ARRÊT"))
            assert len(ligne.split()) >= 8, f"{sid} : règle d'arrêt trop vague"

    def test_chaque_salle_declare_ses_interdits(self):
        for sid, g in _salles().items():
            ligne = next(l for l in g["manifeste"] if l.startswith("JAMAIS"))
            assert len(ligne.split()) >= 6, f"{sid} : interdits non formulés"

    def test_aucune_salle_ne_s_autorise_a_ecrire(self):
        """L'invariant R4 doit survivre à l'arrivée de deux salles neuves : aucun
        manifeste ne doit autoriser la salle à modifier, déployer ou supprimer."""
        for sid, g in _salles().items():
            interdits = next(l for l in g["manifeste"] if l.startswith("JAMAIS")).lower()
            assert any(v in interdits for v in
                       ("ne modifie", "ne corrige", "ne touche", "ne supprime",
                        "ne déploie", "ne génère", "n'adopte", "ne vote", "n'affirme",
                        "n'efface", "ne coupe", "aucun diff", "aucun fichier")), (
                f"{sid} : les interdits ne ferment aucune porte d'écriture")


class TestLesDeuxSallesNeuves:
    def test_elles_existent_et_sont_routees(self):
        salles = _salles()
        bloc = open(SKILL, encoding="utf-8").read()
        for sid in ("inspection-critique", "socle-technique"):
            assert sid in salles, f"{sid} absente du TOML"
            assert f"`{sid}`" in bloc, f"{sid} non routée dans la skill"

    def test_elles_tiennent_le_plafond_de_cinq_voix(self):
        for sid in ("inspection-critique", "socle-technique"):
            assert len(_salles()[sid]["members"]) == 5

    def test_inspection_couvre_les_quatre_axes_demandes(self):
        """La demande a été précisée en deux temps ; les trois axes ajoutés après coup
        (design, UX, jamais utilisé) sont ceux qu'aucune salle ne portait."""
        g = _salles()["inspection-critique"]
        texte = (g["scene"] + " " + " ".join(g["redevabilites"]) + " "
                 + " ".join(g["entrants"])).lower()
        for axe in ("bug", "design", "utilis"):
            assert axe in texte, f"axe « {axe} » absent de la salle d'inspection"
        assert "jamais" in texte, "l'axe des fonctionnalités jamais utilisées manque"

    def test_socle_couvre_environnements_et_infrastructure(self):
        g = _salles()["socle-technique"]
        texte = (g["scene"] + " " + " ".join(g["redevabilites"])).lower()
        for mot in ("environnement", "secret", "coût"):
            assert mot in texte, f"« {mot} » absent du socle technique"


class TestPasDeDoublonAvecLesVoisines:
    """Le vrai risque de ces deux ajouts. Une frontière non écrite est une frontière
    qui n'existe pas : le prochain lecteur convoquera la salle au hasard."""

    def test_l_inspection_ecrit_sa_frontiere_avec_la_code_review(self):
        scene = _salles()["inspection-critique"]["scene"]
        assert "code-review-crew" in scene, (
            "la scène ne dit pas en quoi elle diffère de la revue de code")
        assert "diff" in scene.lower(), "la frontière (diff vs périmètre) n'est pas écrite"

    def test_le_socle_ecrit_sa_frontiere_avec_la_mise_en_service(self):
        scene = _salles()["socle-technique"]["scene"]
        assert "mise-en-service" in scene
        assert "durée" in scene or "guichet" in scene

    def test_les_castings_ne_sont_pas_les_memes(self):
        """Deux salles au casting identique sont une seule salle avec deux noms."""
        s = _salles()
        for neuve, voisine in (("inspection-critique", "code-review-crew"),
                               ("socle-technique", "mise-en-service")):
            a, b = set(s[neuve]["members"]), set(s[voisine]["members"])
            assert a != b, f"{neuve} a le casting de {voisine}"
            assert len(a & b) <= 2, (
                f"{neuve} et {voisine} partagent {len(a & b)} voix sur 5 : doublon")


class TestLeManifesteEstLuEtRendu:
    def test_il_est_rendu_dans_la_page(self):
        html = scan.render_party_html()
        assert "Manifeste de fonctionnement" in html
        ligne = _salles()["socle-technique"]["manifeste"][0]
        assert ligne[:40] in html, "le contenu du manifeste n'est pas rendu"

    def test_la_skill_dit_de_le_lire_avant_de_convoquer(self):
        source = open(SKILL, encoding="utf-8").read()
        section = source[source.index("### 2 septies."):source.index("### 3. Valider")]
        assert "manifeste" in section.lower(), (
            "la skill ne mentionne pas le manifeste : il ne servirait qu'au wiki")

    def test_les_deux_salles_ont_un_destinataire_declare(self):
        for sid in ("inspection-critique", "socle-technique"):
            assert sid in scan.PARTY_DESTINATAIRES
