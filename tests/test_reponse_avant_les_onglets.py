"""La réponse passe avant la structure : les 11 onglets se subordonnent.

Seconde moitié de la **rupture A** de `docs/reflexions/approche-disruptive-wiki-2026-07-31.md`,
arbitrée par l'utilisateur le 2026-09-01 (« B puis A, l'ordre de la salle »).

CE QUI ÉTAIT DÉJÀ FAIT, et qu'on ne refait pas (R1). Le bloc « Ce qui a cassé / Ce qui
attend votre décision / Depuis le scan précédent » existe depuis le 2026-07-31, et la
rupture B — le dispositif vient à l'utilisateur, via `point_du_jour.py` au démarrage de
session — était appliquée le même jour. La proposition disait « rien n'a été appliqué » :
c'était son état à la rédaction, plus le nôtre.

CE QUI NE L'ÉTAIT PAS, et que la mesure établit sans discussion. La salle demandait que
« les 11 onglets se subordonnent » et que « le reste devienne une archive consultable,
pas une façade à parcourir ». Mesuré le 2026-09-01, contre la mesure de la salle :

| | salle (2026-07-31) | aujourd'hui |
| --- | --- | --- |
| onglets | 11 | **11** |
| taille | 278 Ko | **458 Ko** |
| mots | 26 230 | **49 345** |

La page a presque DOUBLÉ pendant qu'on demandait qu'elle se subordonne, et le bloc de
réponse vivait à l'intérieur du panneau « Pilotage », donc APRÈS la barre d'onglets et
invisible depuis les dix autres. On ouvrait toujours sur l'organigramme du dispositif.

CE QUE CE TEST VERROUILLE. La réponse est au niveau de la PAGE, avant la navigation et
hors des panneaux : elle est la première chose lue, et elle reste lisible quel que soit
l'onglet ouvert. C'est la subordination, prise au mot — au 2026-09-01 on ne réduisait pas
le nombre d'onglets (« ce serait une autre décision, que personne n'a arbitrée »), on
cessait seulement de les présenter en premier.

MISE À JOUR 2026-09-03 : cette autre décision vient d'être arbitrée par l'utilisateur —
11 onglets -> 4 primaires + 1 Archive (5 boutons `role="tab"` au premier niveau). Fusionner
n'est pas supprimer : les 11 anciennes destinations restent toutes des ancres réelles de la
page (⚡ Analyser et 🩹 Arbitrer dans un même panneau à sous-navigation ; 🔭 Veille,
🚀 Déploiement, 📤 Exports, 📊 Tokens, 📚 Tutoriel, 🧩 Dispositif dans l'onglet 🗄 Archive).
Le plancher `>= 11` sur `role="tab"` mesurait l'hypothèse d'avant cet arbitrage ; il est
remplacé par un compte exact (5) plus une preuve que rien n'a disparu (les 11 id
`pane-*` d'origine).
"""

import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "scan_projets_reponse", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

PAGE = os.path.join(HUB, "docs", "wiki.html")


def _page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


class TestLaReponsePasseAvantLaStructure:

    def test_la_reponse_est_rendue_avant_la_barre_d_onglets(self):
        h = _page()
        i_reponse = h.find("Ce qui a cassé")
        i_onglets = h.find('role="tablist"')
        assert i_reponse != -1, "le bloc de reponse a disparu de la page"
        assert i_onglets != -1
        assert i_reponse < i_onglets, (
            "la page ouvre sur l'organigramme du dispositif (11 onglets) et non sur la "
            "reponse : c'est exactement ce que la rupture A demandait de renverser")

    def test_la_reponse_n_est_dans_aucun_panneau_d_onglet(self):
        """Sinon elle disparait des qu'on quitte Pilotage — donc dans 10 cas sur 11."""
        h = _page()
        i_reponse = h.find("Ce qui a cassé")
        i_premier_pane = h.find('class="pane')
        assert i_premier_pane == -1 or i_reponse < i_premier_pane, (
            "la reponse vit dans un panneau : invisible depuis les dix autres onglets")

    def test_la_reponse_porte_les_questions_de_la_salle(self):
        """« ce qui a casse, ce qui attend une decision, ce qui a bouge depuis la
        derniere visite » — trois lignes, pas une de plus : un point du jour qui
        deborde redevient le tableau de bord qu'on cesse de lire.

        La TROISIEME est conditionnelle, et ce test l'a appris en echouant : entre deux
        scans consecutifs rien ne bouge, donc « Depuis le scan precedent » ne s'affiche
        pas — a juste titre, une ligne qui dirait « rien n'a bouge » serait du bruit.
        Exiger sa presence, c'etait asserter une propriete qui n'est pas vraie ; on
        verifie donc les deux lignes inconditionnelles sur la page, et la capacite du
        generateur a produire la troisieme.
        """
        h = _page()
        for attendu in ("Ce qui a cassé", "Ce qui attend votre décision"):
            assert attendu in h, f"« {attendu} » manque a la reponse"
        import inspect
        assert "Depuis le scan " in inspect.getsource(scan.render_reponse_du_jour), (
            "la troisieme ligne a disparu du generateur, pas seulement de ce rendu")

    def test_six_onglets_primaires(self):
        """Arbitrage du 2026-09-03 : 11 -> 5 boutons role="tab" au premier niveau
        (Pilotage, Projets, Pratiques, Arbitrer, Archive), puis -> 6 le jour même
        (retour utilisateur après avoir regardé le rendu réel : Tutoriel/Dispositif
        ressortis de l'Archive vers un onglet Guide séparé — nature différente,
        référence vs journal/historique). Un compte exact, pas un plancher : au-delà
        de 6, un onglet serait ressorti du groupement sans arbitrage ; en-deçà, un
        des six aurait disparu."""
        h = _page()
        assert len(re.findall(r'role="tab"', h)) == 6, (
            "le nombre d'onglets primaires a changé sans passer par cet arbitrage")
        assert 'role="tabpanel"' in h

    def test_fusionner_n_est_pas_supprimer_les_onze_destinations_survivent(self):
        """Les 11 anciens panneaux restent des ancres réelles de la page, regroupés
        sous 🩹 Arbitrer (Analyser + Arbitrer) et 🗄 Archive (Veille, Déploiement,
        Exports, Tokens, Tutoriel, Dispositif) plutôt que retirés."""
        h = _page()
        for pane in ("pilotage", "projets", "pratiques", "veille", "deploiement",
                     "actions", "correctifs", "exports", "tokens", "tutoriel",
                     "dispositif"):
            assert f'id="pane-{pane}"' in h, (
                f"pane-{pane} a disparu — un onglet fusionné n'est pas un onglet "
                "supprimé")


class TestLeGenerateurEtLaPageDisentLaMemeChose:
    """Le rendu servi doit venir du generateur, pas d'une edition a la main.

    Le hub a deja paye cette confusion : `docs/wiki.html` est genere, et le corriger
    directement est perdu au scan suivant.
    """

    def test_le_generateur_place_bien_la_reponse_avant_la_nav(self):
        import inspect
        src = inspect.getsource(scan.render_html)
        i_reponse = src.find("render_reponse_du_jour(")
        i_nav = src.find('<nav class="tabs"')
        assert i_reponse != -1 and i_nav != -1
        assert i_reponse < i_nav, (
            "la page rendue peut etre juste par accident : c'est le GENERATEUR qui doit "
            "poser la reponse avant la navigation")
