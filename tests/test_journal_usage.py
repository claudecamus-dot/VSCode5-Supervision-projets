"""Adoption de `veille:disler-observabilite` : capter plus, et surtout LIRE.

Trouvaille arbitrée « adopte » le 2026-09-01. L'écart mesuré à la source : le projet
capte 12 types d'événements (dont `SubagentStop`, échecs d'outil, demandes de
permission) contre UN SEUL ici — `log_usage.py`, hook `PostToolUse` sur `Skill|Agent|Task`.

CE QUI A ÉTÉ ÉCARTÉ, et pourquoi. La pile Bun + SQLite + Vue avec flux WebSocket : un
process persistant contredit un hub qui régénère un wiki statique à 0 token. Et le dépôt
est dormant (dernier push 2026-02-08, ~5,7 mois) — on lit l'idée, jamais le code.

CE QUI A ÉTÉ ADOPTÉ, en deux moitiés indissociables :

1. **Capter la FIN d'un sous-agent** (`SubagentStop`). C'est l'événement qui ferme une
   question que l'étage 1 ne savait pas poser : un sous-agent DISPATCHÉ et un sous-agent
   REVENU s'écrivaient pareil, donc un fan-out dont une branche meurt était indiscernable
   d'un fan-out complet. Plus le marquage d'un échec, mais UNIQUEMENT quand l'outil le
   dit — deviner « pas de succès donc échec » fabriquerait des KO qui n'ont pas eu lieu,
   et le superviseur compte les `ko-repete`.

2. **Donner un LECTEUR au journal.** Mesuré en instruisant l'adoption : `usage.jsonl`
   portait **250 lignes et aucun lecteur** — écrit depuis le 2026-07-23, jamais ouvert,
   les compteurs de l'étage 1 venant de `state.json`. Élargir ce qu'on capte sans le
   lire aurait doublé la dépense sans rien acheter : une adoption d'observabilité qui
   n'observe rien, exactement « l'outil qui tourne pour rien » que la salle
   `revue-consommation` existe pour nommer.
"""

import importlib.util
import json
import os
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_USAGE = os.path.join(HUB, ".claude", "supervision", "log_usage.py")

_spec = importlib.util.spec_from_file_location(
    "scan_journal_usage", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)


def _lancer(payload, journal):
    """Lance le hook comme Claude Code le lance : un JSON sur stdin."""
    env = dict(os.environ, AGENT_SUPERVISION_USAGE=str(journal))
    p = subprocess.run([sys.executable, LOG_USAGE], input=json.dumps(payload),
                       text=True, capture_output=True, env=env, timeout=60)
    assert p.returncode == 0, "le hook doit TOUJOURS rendre 0 : il ne bloque jamais l'outil"
    return p


def _lignes(journal):
    if not os.path.isfile(journal):
        return []
    with open(journal, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


class TestCeQuiEstCapteEnPlus:
    def test_la_fin_d_un_sous_agent_est_journalisee(self, tmp_path):
        j = tmp_path / "u.jsonl"
        _lancer({"hook_event_name": "SubagentStop", "session_id": "s1"}, j)
        lignes = _lignes(j)
        assert len(lignes) == 1 and lignes[0]["event"] == "subagent-stop"

    def test_un_echec_marque_par_l_outil_est_retenu(self, tmp_path):
        j = tmp_path / "u.jsonl"
        _lancer({"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Agent",
                 "tool_input": {"subagent_type": "Explore"},
                 "tool_response": {"is_error": True}}, j)
        assert _lignes(j)[0]["echec"] is True

    def test_une_reponse_muette_n_est_PAS_comptee_comme_echec(self, tmp_path):
        """L'invariant qui protège les chiffres du superviseur : absence de marque
        signifie « on ne sait pas », jamais « ça a marché » — et surtout jamais
        « ça a échoué ». Inventer des KO fausserait les findings `ko-repete`."""
        j = tmp_path / "u.jsonl"
        for reponse in ({}, None, "texte libre", {"status": "ok"}):
            _lancer({"hook_event_name": "PostToolUse", "session_id": "s",
                     "tool_name": "Skill", "tool_input": {"skill": "x"},
                     "tool_response": reponse}, j)
        assert all("echec" not in l for l in _lignes(j))

    def test_la_forme_des_lignes_existantes_ne_change_pas(self, tmp_path):
        """250 lignes déjà écrites : changer leur forme casserait leur relecture."""
        j = tmp_path / "u.jsonl"
        _lancer({"hook_event_name": "PostToolUse", "session_id": "s",
                 "tool_name": "Skill", "tool_input": {"skill": "agent-orchestrator"}}, j)
        l = _lignes(j)[0]
        assert set(l) == {"ts", "session_id", "tool", "skill", "subagent_type",
                          "description"}

    def test_un_outil_hors_perimetre_n_ecrit_rien(self, tmp_path):
        j = tmp_path / "u.jsonl"
        _lancer({"hook_event_name": "PostToolUse", "session_id": "s",
                 "tool_name": "Bash", "tool_input": {}}, j)
        assert _lignes(j) == []

    def test_le_hook_ne_bloque_jamais_meme_sur_payload_casse(self, tmp_path):
        j = tmp_path / "u.jsonl"
        env = dict(os.environ, AGENT_SUPERVISION_USAGE=str(j))
        p = subprocess.run([sys.executable, LOG_USAGE], input="{ pas du json",
                           text=True, capture_output=True, env=env, timeout=60)
        assert p.returncode == 0


class TestLeJournalEstEnfinLu:
    """La moitié sans laquelle l'autre ne vaut rien."""

    def test_le_lecteur_existe_et_agrege(self):
        a = scan.lire_journal_usage()
        assert set(a) >= {"invocations", "fins_sous_agent", "echecs", "sessions"}

    def test_il_lit_le_journal_reel_du_hub(self):
        """Le journal porte des semaines d'invocations : un lecteur qui rendrait zéro
        signalerait qu'il ne lit pas le bon fichier."""
        a = scan.lire_journal_usage()
        assert a["invocations"] > 0
        assert len(a["sessions"]) > 0

    def test_une_ligne_illisible_ne_fait_pas_mentir_le_reste(self, tmp_path, monkeypatch):
        chemin = tmp_path / ".claude" / "supervision"
        chemin.mkdir(parents=True)
        (chemin / "usage.jsonl").write_text(
            '{"ts":"2026-09-01T10:00:00","session_id":"a","tool":"Skill","skill":"x"}\n'
            "{ ligne cassee\n"
            '{"ts":"2026-09-01T10:01:00","session_id":"a","event":"subagent-stop"}\n',
            encoding="utf-8")
        monkeypatch.setattr(scan, "ROOT", str(tmp_path))
        a = scan.lire_journal_usage()
        assert a["invocations"] == 1 and a["fins_sous_agent"] == 1

    def test_le_rendu_est_branche_dans_la_page(self):
        source = open(os.path.join(HUB, "scripts", "scan_projets.py"),
                      encoding="utf-8").read()
        assert "parts.append(render_journal_usage_html())" in source, (
            "le rendu existe mais n'est pas appelé : le journal resterait non lu")

    def test_le_rendu_dit_quoi_faire_du_zero_de_fins_de_sous_agent(self):
        """Un zéro admet deux lectures — aucun sous-agent, ou hook muet — et le rendu
        doit dire comment les départager, pas laisser le lecteur conclure."""
        h = scan.render_journal_usage_html()
        a = scan.lire_journal_usage()
        if a["fins_sous_agent"] == 0:
            assert "dispatchant" in h and "supposant" in h

    def test_le_hook_subagentstop_est_reellement_cable(self):
        with open(os.path.join(HUB, ".claude", "settings.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        cmds = [h.get("command", "") for c in hooks.get("SubagentStop", [])
                for h in c.get("hooks", [])]
        assert any("log_usage" in c for c in cmds), (
            "capter SubagentStop dans le code sans le câbler ne capte rien")
