"""Les chiffres de CLAUDE.md sont générés, plus recopiés.

Finding `VScode5:CLAUDE.md`, arbitré le 2026-09-01 (« traite tous les points de la page
pilotage »). CLAUDE.md prêche R6 — « tout chiffre s'écrit avec la commande qui l'a
produit » — et portait pourtant quatre chiffres écrits à la main :

* les tailles des cinq fichiers générés volumineux, mesurées le 2026-08-31 et déjà
  fausses de +9 à +36 % le lendemain ;
* le taux de reprise par playbook, invoqué pour justifier R6, dont l'écart avait
  entièrement disparu (0,60 contre 0,62 par run) sans que personne le relise ;
* une « dette assumée » de tests éteinte depuis longtemps ;
* « 9 salles » dans le kit publié, contre 12 réellement déclarées dans le TOML.

Ces tests verrouillent le mécanisme : le bloc se régénère, il est idempotent, et il
mesure la réalité plutôt qu'une constante recopiée.
"""

import importlib.util
import os
import re

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "scan_projets_chiffres", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

_spec_ea = importlib.util.spec_from_file_location(
    "export_agentic_chiffres", os.path.join(HUB, ".claude", "dispositif", "export_agentic.py"))
ea = importlib.util.module_from_spec(_spec_ea)
_spec_ea.loader.exec_module(ea)


def _claudemd_octets():
    with open(scan.CLAUDEMD_PATH, "rb") as fh:
        return fh.read()


class TestLeBlocEstRegenere:
    def test_les_marqueurs_existent_dans_claudemd(self):
        """Sans marqueurs, la fonction ne trouve pas sa place et ne dit rien —
        elle échouerait en silence, ce qui est pire qu'un chiffre faux."""
        texte = scan.read_text(scan.CLAUDEMD_PATH)
        for cle in ("VOLUMINEUX", "REPRISES"):
            assert f"<!-- CHIFFRES-MESURES:{cle}:START" in texte
            assert f"<!-- CHIFFRES-MESURES:{cle}:END -->" in texte

    def test_une_deuxieme_passe_ne_change_rien(self):
        """Idempotence — proposition (d) du finding. Un bloc régénéré qui bouge à
        chaque scan produirait un diff permanent : le fichier deviendrait du bruit
        dans `git status`, et R2 (commit scopé) impossible à tenir."""
        scan.regenerer_chiffres_claudemd()
        apres_1 = _claudemd_octets()
        change = scan.regenerer_chiffres_claudemd()
        apres_2 = _claudemd_octets()
        assert change is False, "la 2e passe se déclare modifiante"
        assert apres_1 == apres_2, "le bloc régénéré n'est pas idempotent"

    def test_les_fins_de_ligne_sont_preservees(self):
        """CLAUDE.md est en LF ; le mode texte par défaut de Windows le repasserait en
        CRLF, soit un diff de tout le fichier à chaque scan pour deux chiffres."""
        avant = _claudemd_octets()
        assert avant.count(b"\r\n") == 0, (
            "ce test perd son objet si CLAUDE.md est déjà en CRLF")
        scan.regenerer_chiffres_claudemd()
        assert _claudemd_octets().count(b"\r\n") == 0, "le scan a converti CLAUDE.md en CRLF"


class TestLesChiffresSontMesures:
    def test_les_tailles_sont_celles_du_disque(self):
        """Le cœur du finding : la taille annoncée doit être celle du fichier, pas
        celle du jour où quelqu'un l'a recopiée."""
        bloc = scan.bloc_volumineux()
        for rel in scan.VOLUMINEUX:
            chemin = os.path.join(HUB, rel.replace("/", os.sep))
            if not os.path.isfile(chemin):
                continue
            attendu = round(os.path.getsize(chemin) / 1024)
            m = re.search(re.escape(f"`{rel}` (") + r"(\d+) Ko\)", bloc)
            assert m, f"{rel} absent du bloc régénéré"
            assert int(m.group(1)) == attendu, (
                f"{rel} : bloc annonce {m.group(1)} Ko, disque {attendu} Ko")

    def test_les_cinq_fichiers_volumineux_sont_tous_couverts(self):
        bloc = scan.bloc_volumineux()
        for rel in scan.VOLUMINEUX:
            assert rel in bloc, f"{rel} manque à la consigne de tokens"

    def test_le_plus_gros_est_annonce_en_premier(self):
        """C'est le plus gros qui coûte le plus cher à ouvrir : c'est lui qu'on doit
        lire en premier dans une consigne d'économie de tokens."""
        tailles = [int(n) for n in re.findall(r"\((\d+) Ko\)", scan.bloc_volumineux())]
        assert tailles == sorted(tailles, reverse=True), "bloc non trié par taille"

    def test_les_reprises_viennent_des_hints_et_non_du_texte(self):
        """Le ratio qui justifiait R6 a changé sans que la page bouge. Il doit
        désormais être lu dans routing-hints.json, pas écrit."""
        stats = (scan.read_json(scan.HINTS_PATH) or {}).get("playbooks") or {}
        bloc = scan.bloc_reprises()
        for nom, s in stats.items():
            if not (s.get("n") or 0):
                continue
            assert f"`{nom}`" in bloc, f"{nom} absent du bloc reprises"
            assert f"sur {s['n']} run(s)" in bloc, f"{nom} : n incohérent avec les hints"


class TestLeKitNAnnoncePlusUnCompteFaux:
    """« 9 salles » vivait en dur dans le README publié pendant que le TOML en
    déclarait 12 — un projet cible lisait un compte faux dans le kit qu'il installait."""

    def test_le_compte_de_salles_vient_du_toml(self):
        attendu = sum(
            1 for ligne in open(ea.SALLES_TOML, encoding="utf-8")
            if ligne.strip() == "[[workflow.party_groups]]")
        assert attendu > 0, "ce test perd son objet si le TOML ne déclare aucune salle"
        assert ea.nb_salles() == attendu

    def test_le_readme_rendu_annonce_le_compte_reel(self):
        """L'artefact que lit le projet cible — c'est LUI qui annonçait 9 pour 12.

        La vérification porte sur le README rendu, pas sur le source du générateur :
        les commentaires y racontent le défaut historique (« le kit a publié 9 salles »)
        et une assertion sur le source les prendrait pour la faute qu'ils décrivent.
        """
        rendu = ea.readme("2026-01-01")
        m = re.search(r"Les (\d+) salles arrivent", rendu)
        assert m, "la ligne des salles a disparu du README publié"
        assert int(m.group(1)) == ea.nb_salles()

    def test_le_readme_publie_sur_disque_est_a_jour(self):
        """Le kit réellement installé chez une cible, pas seulement le rendu en mémoire."""
        chemin = os.path.join(HUB, "export", "README.md")
        if not os.path.isfile(chemin):
            return
        publie = open(chemin, encoding="utf-8").read()
        m = re.search(r"Les (\d+) salles arrivent", publie)
        assert m, "la ligne des salles a disparu du README publié sur disque"
        assert int(m.group(1)) == ea.nb_salles(), (
            "export/README.md annonce un compte périmé — régénérer le kit")
