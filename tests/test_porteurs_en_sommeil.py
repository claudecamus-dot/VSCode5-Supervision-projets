"""« Absent » et « en sommeil » ne sont pas la même chose, et la page les confondait.

Demande utilisateur du 2026-09-02 : « il est indiqué que agent-orchestrateur lance
bmad-revue, bmad-recherche, veille-agentic, agent-supervisor, bmad-doc — absent de
.claude/agents/, bmad-cadrage — absent, bmad-livraison — absent ; avec des absents,
peux-tu inscrire au TODO des corrections ».

CE QUE LA MESURE DIT. Les trois « absents » ne manquent pas : ils ont été **mis en
sommeil le 2026-09-01**, sur décision tracée, et déplacés dans `.claude/agents-en-sommeil/`
— un répertoire qui porte leur mesure et la façon de les réveiller. La skill
d'orchestration a suivi : les rangées de la table BMAD qui les nommaient portent `inline`,
c'est-à-dire que la skill reste routée et part dans la conversation courante.

LE DÉFAUT EST DONC UNE ÉTIQUETTE, PAS UN TROU. Rendre une décision comme une panne coûte
deux fois : on va chercher à réparer ce qui a été retiré exprès, et on cesse de croire
l'étiquette quand elle désignera un vrai manque. C'est la même famille que les trois
pastilles vertes qui mesuraient trois choses différentes, ou que `cadence-perime` recyclé
sur un compteur de fichiers non commités.

CE QUE CES TESTS VERROUILLENT : un porteur endormi est nommé « en sommeil », un porteur
qui n'existe NULLE PART est nommé « absent » — et seul ce dernier mérite un TODO, parce
que lui seul est un travail à faire.
"""

import importlib.util
import io
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets_sommeil", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

AGENTS = os.path.join(HUB, ".claude", "agents")
SOMMEIL = os.path.join(HUB, ".claude", "agents-en-sommeil")


# L'attendu est FIGÉ, pas recalculé : la revue du 2026-09-02 a montré que `_noms()`
# réimplémentait `agents_en_sommeil()` ligne pour ligne, donc comparait la fonction à
# elle-même — et que « les trois endormis » du docstring étaient quatre sur disque.
ENDORMIS = frozenset({"agent-orchestrator", "bmad-cadrage", "bmad-doc", "bmad-livraison"})


def _noms(dossier):
    if not os.path.isdir(dossier):
        return set()
    return {f[:-3] for f in os.listdir(dossier)
            if f.endswith(".md") and f != "README.md"}


class TestLeRepertoireDuSommeilEstLu:
    def test_il_existe_et_porte_les_quatre_endormis(self):
        """Si ce répertoire disparaît, le test suivant deviendrait vert pour une mauvaise
        raison — on vérifie donc d'abord que la matière du test est là, nom par nom."""
        endormis = _noms(SOMMEIL)
        assert endormis == set(ENDORMIS), (
            f"agents-en-sommeil/ porte {sorted(endormis)}, attendu {sorted(ENDORMIS)} — "
            "si un porteur a été réveillé ou endormi, mettre ENDORMIS à jour ici")

    def test_le_scan_sait_les_lire(self):
        assert hasattr(scan, "agents_en_sommeil"), (
            "le générateur n'a aucun moyen de distinguer un porteur endormi d'un porteur "
            "manquant : il les rendra tous « absent »")
        assert set(scan.agents_en_sommeil()) == set(ENDORMIS)

    def test_le_readme_n_est_pas_un_porteur(self):
        assert "README" not in scan.agents_en_sommeil()


class TestLaPageNeConfondPlusLesDeux:
    def test_aucun_endormi_n_est_rendu_absent(self):
        html = scan.render_dispositif_html() if hasattr(scan, "render_dispositif_html") else ""
        if not html:
            # le nom de la fonction de rendu peut changer : on retombe sur la page servie
            html = io.open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8").read()
        for nom in _noms(SOMMEIL):
            assert f"{nom} — absent de .claude/agents/" not in html, (
                f"{nom} est en sommeil sur décision tracée, la page le déclare absent : "
                "une décision rendue comme une panne fait réparer ce qu'on a retiré exprès")

    def test_un_endormi_est_nomme_en_sommeil(self):
        """Assertion sur le BADGE exact, sur le HTML rendu par la fonction — pas sur
        « en sommeil » quelque part dans 459 Ko de page : la prose des arbitrages contenait
        déjà 8 fois ces mots AVANT le correctif, le test était vert par construction
        (revue du 2026-09-02, badges retirés à la main : les assertions restaient vraies)."""
        html = scan.render_dispositif_html()
        declares = set()
        for noms in scan.DISPOSITIF_LANCE.values():
            declares |= set(noms)
        attendus = sorted(ENDORMIS & declares)
        assert attendus, "aucun endormi n'est déclaré par le schéma : rien à vérifier"
        for nom in attendus:
            assert f"{nom} — en sommeil" in html, (
                f"{nom} est endormi et déclaré par le schéma, la page ne porte pas son badge")


class TestSeulUnVRAIManqueVaAuTODO:
    def test_aucun_porteur_n_est_reellement_manquant_aujourd_hui(self):
        """Mesure du jour, et c'est elle qui répond à la demande : il n'y a AUCUN
        porteur à corriger. Si ce test devient rouge, un porteur manque vraiment et
        mérite alors un TODO — c'est à ce moment-là que la correction est un travail."""
        declares = set()
        for noms in getattr(scan, "DISPOSITIF_LANCE", {}).values():
            declares |= set(noms)
        manquants = sorted(declares - _noms(AGENTS) - _noms(SOMMEIL))
        assert not manquants, (
            f"porteurs déclarés par le schéma et introuvables partout : {manquants} — "
            "ceux-là sont un vrai trou et doivent aller au TODO")
