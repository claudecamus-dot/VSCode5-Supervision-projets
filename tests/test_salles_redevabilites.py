"""Les salles portent un CONTRAT : redevabilités, qualité requise, entrants, sortants.

Demande utilisateur du 2026-09-01 : « ajoute des redevabilités au niveau des salles
comme de la documentation, un niveau de qualité requis, des entrants (spec comme adr)
et des sortants comme des ppt ou du dev ».

Arbitrage rendu le même jour sur la question qui décidait de la forme : les sortants
sont **déclaratifs + recette vérifiable**. La salle NOMME le livrable, son producteur
aval et le niveau de qualité attendu, et elle écrit la RECETTE que ce livrable devra
passer — mais elle ne le produit pas. L'invariant « une salle ne modifie aucun
fichier » tient donc entier, et c'est lui qui protège R4 : une salle qui écrirait du
code serait une auto-application collective. La recette est ce qui empêche le contrat
d'être décoratif — l'orchestrateur ne clôt pas tant qu'elle n'est pas jouée.

DEUX PIÈGES MESURÉS, tous deux gardés ici.

1. **Override partiel = salle vidée.** `_bmad/scripts/resolve_customization.py::
   _merge_by_key` REMPLACE une entrée dont l'`id` matche (`result[i] = dict(item)`),
   alors que `scan_projets.party_collectif` FUSIONNE clé par clé (`{**out[i], **f}`).
   Une entrée d'override qui ne porterait que le contrat s'afficherait complète dans
   le wiki et arriverait VIDE DE SES MEMBRES au vrai résolveur. Les deux salles du
   socle BMAD (`code-review-crew`, `anti-consensus-club`) doivent donc être réécrites
   ENTIÈRES dans l'override. C'est la même leçon que
   `referentiel:deux-sources-qui-se-contredisent`.

2. **Un contrat qu'aucun lecteur ne lit.** La table situation→salle a déjà vécu dans
   un générateur de HTML que le plan ne lisait jamais (corrigé le 2026-08-31). Le
   contrat doit donc être rendu ET la skill orchestrateur doit dire quoi en faire.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")

_spec = importlib.util.spec_from_file_location(
    "scan_projets_redevabilites", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

CHAMPS = ("redevabilites", "qualite_requise", "entrants", "sortants")


def _salles():
    """Les salles telles que le vrai résolveur les voit (socle + override fusionnés)."""
    _membres, groupes = scan.party_collectif()
    return {g["id"]: g for g in groupes}


class TestChaqueSallePorteSonContrat:
    def test_les_neuf_salles_portent_les_quatre_champs(self):
        manquants = {sid: [c for c in CHAMPS if not g.get(c)]
                     for sid, g in _salles().items()}
        manquants = {s: c for s, c in manquants.items() if c}
        assert not manquants, f"salle(s) sans contrat complet : {manquants}"

    def test_les_entrants_sont_une_liste_non_vide(self):
        """Un entrant est ce qui permet de REFUSER de siéger : sans lui la salle
        délibère sur du vide. C'est la seule dent du contrat côté amont."""
        for sid, g in _salles().items():
            assert isinstance(g["entrants"], list) and len(g["entrants"]) >= 2, sid

    def test_les_redevabilites_sont_une_liste_non_vide(self):
        for sid, g in _salles().items():
            assert isinstance(g["redevabilites"], list) and g["redevabilites"], sid

    def test_la_qualite_requise_est_une_phrase_pas_un_mot(self):
        """« qualité : haute » n'est pas un niveau de qualité, c'est un adjectif.
        Le champ doit dire à quoi on RECONNAÎT que la barre est franchie."""
        for sid, g in _salles().items():
            assert len(g["qualite_requise"].split()) >= 8, (
                f"{sid} : niveau de qualité trop court pour être vérifiable")


class TestSortantsDeclaratifsAvecRecette:
    def test_chaque_sortant_nomme_type_producteur_et_recette(self):
        for sid, g in _salles().items():
            s = g["sortants"]
            assert isinstance(s, dict), f"{sid} : sortants doit être une table"
            for cle in ("type", "producteur", "recette"):
                assert s.get(cle), f"{sid} : sortants.{cle} manquant"

    def test_la_recette_est_verifiable_point_par_point(self):
        """Une recette à un seul item est un slogan. L'orchestrateur doit pouvoir
        la cocher ligne à ligne avant de clore."""
        for sid, g in _salles().items():
            recette = g["sortants"]["recette"]
            assert isinstance(recette, list) and len(recette) >= 2, sid

    def test_le_producteur_n_est_jamais_la_salle_elle_meme(self):
        """L'invariant qui protège R4 : la salle nomme QUI produit, et ce n'est
        jamais elle. Un producteur qui serait la salle rouvrirait la porte de
        l'auto-application collective que « ne modifie aucun fichier » ferme."""
        for sid, g in _salles().items():
            producteur = g["sortants"]["producteur"].lower()
            assert "salle" not in producteur and sid not in producteur, (
                f"{sid} : la salle se designe elle-meme comme producteur")

    def test_les_livrables_ppt_et_dev_sont_effectivement_couverts(self):
        """La demande nommait deux sortants concrets — un deck et du dev. Si aucune
        salle ne les porte, le contrat est resté abstrait."""
        types = " ".join(g["sortants"]["type"].lower() for g in _salles().values())
        prods = " ".join(g["sortants"]["producteur"].lower() for g in _salles().values())
        assert "deck" in types, "aucune salle ne produit de deck"
        assert "export-ppt-verifie" in prods, "le producteur de deck n'est pas le playbook"
        assert "dev-verifie" in prods or "evolution-flotte" in prods, (
            "aucune salle ne debouche sur un chantier de dev")

    def test_les_entrants_couvrent_spec_et_adr(self):
        """La demande nommait la spec et l'ADR comme entrants types."""
        joint = " ".join(" ".join(g["entrants"]).lower() for g in _salles().values())
        assert "spec" in joint and "adr" in joint


class TestOverridePartielNeVidePasUneSalle:
    """Le piège n°1 du docstring — mesuré, pas supposé."""

    def test_les_deux_salles_du_socle_sont_reecrites_entieres(self):
        import tomllib
        chemin = os.path.join(HUB, "_bmad", "custom", "bmad-party-mode.toml")
        with open(chemin, "rb") as fh:
            over = tomllib.load(fh)["workflow"]["party_groups"]
        par_id = {g["id"]: g for g in over}
        for sid in ("code-review-crew", "anti-consensus-club"):
            assert sid in par_id, f"{sid} absent de l'override"
            g = par_id[sid]
            for cle in ("name", "members", "scene"):
                assert g.get(cle), (
                    f"{sid} : override partiel — le vrai resolveur REMPLACE, "
                    f"cette salle arriverait sans {cle}")

    def test_aucune_salle_a_roster_ne_perd_ses_membres(self):
        salles = _salles()
        for sid, g in salles.items():
            if sid == "accueil-projet":
                continue  # open-cast assumée : son scène caste les voix
            assert g.get("members"), f"{sid} : salle videe de ses membres"

    def test_toutes_les_voix_se_resolvent_encore(self):
        assert "(non résolu)" not in scan.render_party_html()


class TestLeContratEstLuPasSeulementEcrit:
    """Le piège n°2 : un contrat que ni le wiki ni le plan ne lisent est mort-né."""

    def test_le_contrat_est_rendu_dans_la_page(self):
        html = scan.render_party_html()
        for mot in ("Redevabilit", "Entrants", "Sortants", "Recette"):
            assert mot in html, f"« {mot} » absent du rendu des salles"

    def test_la_recette_d_une_salle_apparait_vraiment(self):
        """Rendre les en-têtes sans le contenu serait un gabarit vide."""
        html = scan.render_party_html()
        recette = _salles()["atelier-deck"]["sortants"]["recette"][0]
        assert recette[:40] in html

    def test_la_skill_orchestrateur_impose_de_jouer_la_recette(self):
        source = open(SKILL, encoding="utf-8").read()
        debut = source.index("### 2 septies.")
        section = source[debut:source.index("### 3. Valider")]
        assert "recette" in section.lower(), (
            "la skill ne dit pas quoi faire de la recette rendue par la salle")
        assert "entrants" in section.lower(), (
            "la skill ne dit pas qu'une salle sans ses entrants ne siege pas")
