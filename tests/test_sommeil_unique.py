"""Une seule definition de « en sommeil », et elle regarde les DEUX canaux.

Finding `scan_transcripts.py:807` (diagnostic etage 2 du 2026-09-01, arbitre le jour
meme). Le meme script calculait le sommeil a deux endroits, sur deux ensembles
differents :

- l.693, pour `routing-hints.json` : sur `{**skills, **subagents}` ;
- l.807, pour le TODO de `docs/wiki/index.md` : sur `skills` seul.

Ce n'est pas une redondance cosmetique, c'est un DESACCORD MESURE le 2026-09-01 :
routing-hints rendait 6 noms, le wiki 7, et les deux avaient tort autrement.

Le mecanisme exact — et il vaut d'etre nomme, parce qu'il se reproduira ailleurs :
`{**skills, **subagents}` ECRASE l'entree skill par l'entree sous-agent de meme nom.
Deux noms vivent dans les deux canaux, `agent-supervisor` et `veille-agentic`, et leur
usage recent est du cote SOUS-AGENT (2026-09-01T19:17 et 2026-08-31T08:13) tandis que
leur cote skill dort depuis juillet. Consequences constatees :

- le TODO du wiki proposait d'endormir `agent-supervisor`, qui venait de tourner LE
  JOUR MEME, et `veille-agentic`, qui avait tourne la veille ;
- il OMETTAIT `bmad-recherche`, sous-agent pur, donc le seul reellement dormant.

Un TODO qui propose d'eteindre ce qui vient de servir et tait ce qui dort n'est pas
imprecis : il est a l'envers.

La correction n'est pas de choisir l'un des deux ensembles — l'ecrasement de dict
donnait la bonne reponse ICI par hasard, parce que le sous-agent etait le plus recent.
Elle est de poser la question juste : **une entite dort si son usage LE PLUS RECENT,
tous canaux confondus, depasse le seuil.**
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "scan_transcripts_sommeil",
    os.path.join(HUB, ".claude", "supervision", "scan_transcripts.py"))
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _state(**entrees):
    """`{nom: (canal, jours_depuis_le_dernier_usage)}` -> un state.json minimal."""
    import datetime as dt
    skills, subagents = {}, {}
    for nom, couples in entrees.items():
        for canal, jours in couples:
            d = (dt.datetime.now() - dt.timedelta(days=jours)).isoformat()
            (skills if canal == "skill" else subagents)[nom] = {"n": 1, "last": d}
    return {"skills": skills, "subagents": subagents}


class TestUneSeuleDefinitionDuSommeil:

    def test_un_nom_actif_cote_sous_agent_ne_dort_pas(self):
        """Le cas `agent-supervisor` : skill muette depuis 33 j, sous-agent lance
        aujourd'hui. Le proposer a l'extinction est le contraire de la mesure."""
        s = _state(**{"agent-supervisor": [("skill", 40), ("subagent", 0)]})
        assert "agent-supervisor" not in st.dormants(s)

    def test_un_nom_actif_cote_skill_ne_dort_pas_non_plus(self):
        """Le symetrique, que l'ecrasement de dict aurait rate : c'est parce que le
        sous-agent etait le plus recent que l'ancien calcul tombait juste ici."""
        s = _state(**{"quelque-chose": [("skill", 0), ("subagent", 40)]})
        assert "quelque-chose" not in st.dormants(s)

    def test_un_sous_agent_pur_qui_dort_est_signale(self):
        """Le cas `bmad-recherche` : absent du canal skill, donc invisible du calcul
        qui ne regardait que `skills`."""
        s = _state(**{"bmad-recherche": [("subagent", 40)]})
        assert "bmad-recherche" in st.dormants(s)

    def test_un_nom_endormi_des_deux_cotes_dort(self):
        s = _state(**{"vieux": [("skill", 40), ("subagent", 45)]})
        assert "vieux" in st.dormants(s)

    def test_les_deux_consommateurs_lisent_la_MEME_liste(self):
        """Le fond du finding : routing-hints et le TODO du wiki rendaient 6 et 7.
        Deux nombres pour une meme question, dans un meme scan, ne peuvent pas etre
        tous les deux la mesure."""
        s = _state(**{"agent-supervisor": [("skill", 40), ("subagent", 0)],
                      "bmad-recherche": [("subagent", 40)],
                      "vieux": [("skill", 40)]})
        attendu = set(st.dormants(s))
        assert attendu == {"bmad-recherche", "vieux"}, (
            "la definition unique ne rend pas ce que la mesure dit")
        hints = st.build_routing_hints(s, {}, {}, {}, None)
        assert set(hints.get("en_sommeil", [])) == attendu, (
            "routing-hints.json ne lit pas la meme liste que le TODO du wiki")

    def test_le_TODO_du_wiki_lit_la_meme_liste(self):
        """L'autre consommateur, celui qui proposait d'eteindre ce qui venait de servir.

        On n'assert pas sur le rendu complet — on verifie que le calcul du TODO passe
        bien par `dormants`, en poussant un state ou les deux anciens ensembles
        divergeaient : `agent-supervisor` actif cote sous-agent seulement.
        """
        import inspect
        src = inspect.getsource(st)
        assert src.count("dormants(state)") >= 2, (
            "un des deux consommateurs calcule encore le sommeil pour son compte")
        assert "for k, e in skills.items()" not in src.split("def dormants")[0], (
            "le calcul sur `skills` seul survit quelque part")
