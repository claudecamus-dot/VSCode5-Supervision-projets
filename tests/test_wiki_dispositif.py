"""Non-régression de l'onglet Dispositif du wiki (demande utilisateur 2026-07-30) :
le schéma de fonctionnement des deux agents, ce qu'ils lancent, les playbooks, les
règles, et le pilotage du duo projet par projet.

L'intérêt du test n'est pas « le HTML contient un titre » mais l'invariant qui fait
la valeur de la page : le schéma est **dérivé de l'état réel du dépôt**. S'il se
mettait à recopier une liste en dur, il décrirait un dispositif qui n'existe plus —
et un schéma faux coûte plus cher que pas de schéma.
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def projets_factices():
    """Deux projets : le hub lui-même (transverse, détecté par son chemin) et un
    projet de flotte sans le duo. Aucun accès aux vrais dépôts de la flotte."""
    return [
        {"nom": "VScode5", "chemin": HUB, "existe": True,
         "skills": ["agent-orchestrator", "agent-supervisor", "veille-agentic"],
         "agents": ["bmad-revue", "veille-agentic"], "playbooks": ["evolution-flotte"],
         "skills_utilises": [("agent-orchestrator", 91), ("agent-supervisor", 10)],
         "diag_date": "2026-07-30T14:00:00+02:00"},
        {"nom": "VSCodeX", "chemin": r"C:\ailleurs\VSCodeX", "existe": True,
         "skills": ["pptx-deck"], "agents": [], "playbooks": [],
         "skills_utilises": [], "diag_date": None},
        {"nom": "VSCodeDisparu", "chemin": r"C:\nulle-part", "existe": False,
         "skills": [], "agents": [], "playbooks": [], "skills_utilises": []},
    ]


class TestFrontmatterAgent:
    def test_lit_les_quatre_cles(self, tmp_path):
        f = tmp_path / "a.md"
        f.write_text('---\nname: a\ndescription: "x — y"\ntools: Skill, Read\n'
                     "model: opus\n---\n\ncorps\n", encoding="utf-8")
        fm = scan.lire_frontmatter_agent(str(f))
        assert fm == {"name": "a", "description": "x — y", "tools": "Skill, Read",
                      "model": "opus"}

    def test_fichier_absent_ne_plante_pas(self, tmp_path):
        """Fail-open : un agent illisible ne doit pas faire échouer la génération du
        wiki entier — la page se rend sans lui."""
        assert scan.lire_frontmatter_agent(str(tmp_path / "rien.md")) == {}

    def test_sans_frontmatter_rend_vide(self, tmp_path):
        f = tmp_path / "b.md"
        f.write_text("# juste du markdown\n", encoding="utf-8")
        assert scan.lire_frontmatter_agent(str(f)) == {}

    def test_ignore_les_cles_hors_liste(self, tmp_path):
        f = tmp_path / "c.md"
        f.write_text("---\nname: c\ncolor: rouge\n---\n\n", encoding="utf-8")
        assert scan.lire_frontmatter_agent(str(f)) == {"name": "c"}


class TestSousAgentsReels:
    def test_liste_les_agents_du_depot(self):
        noms = {a["nom"] for a in scan.lister_sous_agents()}
        assert {"agent-orchestrator", "agent-supervisor", "bmad-revue",
                "veille-agentic"} <= noms

    def test_chaque_agent_porte_ses_outils_et_son_modele(self):
        par_nom = {a["nom"]: a for a in scan.lister_sous_agents()}
        assert "Skill" in par_nom["bmad-revue"]["outils"]
        assert par_nom["bmad-revue"]["modele"] == "opus"
        # frontmatter sans `model:` → hérité du modèle de session, pas vide
        assert par_nom["agent-orchestrator"]["modele"] == "hérité"


class TestReglesLuesDansClaudeMd:
    def test_les_regles_viennent_du_fichier_source(self):
        regles = scan.regles_absolues()
        codes = [c for c, _ in regles]
        assert codes == ["R1", "R2", "R3", "R4", "R5"], codes
        assert all(titre.strip() for _, titre in regles)


class TestPilotageDuDuo:
    def test_ignore_les_projets_inexistants(self):
        noms = {d["nom"] for d in scan.pilotage_duo(projets_factices())}
        assert noms == {"VScode5", "VSCodeX"}

    def test_marque_le_hub_comme_transverse_par_son_chemin(self):
        """Détection par chemin, pas par nom en dur : renommer le dossier du hub ne
        doit pas faire perdre le repère du projet transverse."""
        duo = {d["nom"]: d for d in scan.pilotage_duo(projets_factices())}
        assert duo["VScode5"]["transverse"] is True
        assert duo["VSCodeX"]["transverse"] is False

    def test_distingue_presence_et_usage(self):
        """Le cœur du pilotage : une skill présente mais à 0 invocation n'est pas
        une skill qui sert — c'est le signal `agent-mort` du superviseur."""
        duo = {d["nom"]: d for d in scan.pilotage_duo(projets_factices())}
        assert duo["VScode5"]["orchestrateur"] is True
        assert duo["VScode5"]["n_orchestrateur"] == 91
        assert duo["VSCodeX"]["orchestrateur"] is False
        assert duo["VSCodeX"]["n_orchestrateur"] == 0

    def test_date_de_diagnostic_tronquee_au_jour(self):
        duo = {d["nom"]: d for d in scan.pilotage_duo(projets_factices())}
        assert duo["VScode5"]["diag_date"] == "2026-07-30"
        assert duo["VSCodeX"]["diag_date"] == ""

    def test_un_projet_ajoute_a_projets_json_entre_automatiquement(self):
        """La promesse faite dans la page : tout nouveau projet transverse pris en
        charge par le hub apparaît sans toucher au code."""
        projets = projets_factices()
        projets.append({"nom": "VSCode6", "chemin": r"C:\neuf", "existe": True,
                        "skills": ["agent-orchestrator"], "agents": [],
                        "playbooks": [], "skills_utilises": []})
        duo = {d["nom"]: d for d in scan.pilotage_duo(projets)}
        assert "VSCode6" in duo
        assert duo["VSCode6"]["superviseur"] is False


class TestRenduHtml:
    def test_le_schema_cite_les_agents_reellement_installes(self):
        """L'invariant de la page : les noms affichés viennent du disque."""
        h = scan.render_dispositif_html(projets_factices())
        for nom in (a["nom"] for a in scan.lister_sous_agents()):
            assert nom in h, nom

    def test_le_schema_signale_un_porteur_manquant_au_lieu_de_mentir(self, monkeypatch):
        """Si DISPOSITIF_LANCE cite un agent supprimé, la page doit le DIRE — un
        schéma qui affiche silencieusement un agent absent est un schéma faux."""
        monkeypatch.setitem(scan.DISPOSITIF_LANCE, "agent-supervisor",
                            ["bmad-revue", "agent-fantome"])
        h = scan.render_dispositif_html(projets_factices())
        assert "agent-fantome — absent de .claude/agents/" in h

    def test_les_playbooks_et_les_regles_sont_rendus(self):
        h = scan.render_dispositif_html(projets_factices())
        assert "evolution-flotte" in h
        for code in ("R1", "R2", "R3", "R4", "R5"):
            assert f'<span class="regle-chip">{code}</span>' in h

    def test_le_pilotage_pointe_les_projets_a_equiper(self):
        h = scan.render_dispositif_html(projets_factices())
        assert "À équiper" in h and "VSCodeX" in h

    def test_le_pilotage_signale_un_duo_installe_mais_dormant(self):
        projets = projets_factices()
        projets[0]["skills_utilises"] = []   # duo présent, jamais invoqué
        h = scan.render_dispositif_html(projets)
        assert "installé mais jamais invoqué" in h

    def test_sans_projet_la_page_le_dit_au_lieu_de_rendre_un_tableau_vide(self):
        h = scan.render_dispositif_html([])
        assert "Aucun projet existant" in h

    def test_l_onglet_est_cable_dans_la_page_livree(self):
        """Contrôle sur l'ARTEFACT que l'utilisateur ouvre (docs/wiki.html), pas sur
        une fonction de démo : le bouton, le panneau et leur liaison ARIA doivent y
        être. Un onglet sans aria-controls/aria-labelledby est invisible au lecteur
        d'écran (finding wiki:accessibilite-onglets). Ce test échoue aussi si le
        générateur a changé sans que la page soit régénérée — c'est voulu."""
        with open(os.path.join(HUB, "docs", "wiki.html"), encoding="utf-8") as fh:
            page = fh.read()
        for marqueur in ('id="tab-dispositif"', 'aria-controls="pane-dispositif"',
                         'id="pane-dispositif"', 'aria-labelledby="tab-dispositif"',
                         "Pilotage du duo sur la flotte", "Les règles absolues"):
            assert marqueur in page, marqueur
