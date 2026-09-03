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


class TestLeJournalNePerdRienEnSilence:
    """Défaut `log_usage.py:109-112`, audit technique du 2026-09-01, gravité critique.

    Le docstring du module promet : « Ne bloque jamais l'outil (exit 0 en toutes
    circonstances), mais **ne perd plus rien en silence** : une invocation non
    journalisée est signalée sur stderr. » Le garde-fou final disait le contraire :

        except Exception:
            sys.exit(0)

    Toute panne d'écriture — répertoire absent, disque plein, permission refusée —
    sortait 0 avec stderr VIDE. L'étage 1 sous-comptait sans trace, et le superviseur
    bâtissait ses findings « agent mort » sur un journal troué sans le savoir.
    Reproduit par l'audit : `AGENT_SUPERVISION_USAGE=<dir inexistant>` → exit 0,
    stderr vide.

    Les deux moitiés de la promesse sont indissociables et sont testées ensemble :
    exit 0 (ne jamais bloquer l'outil de l'utilisateur) **et** un mot sur stderr.
    """

    @staticmethod
    def _lancer(usage_path, payload):
        import subprocess
        import sys as _sys
        hub = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, AGENT_SUPERVISION_USAGE=str(usage_path),
                   PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [_sys.executable, os.path.join(hub, ".claude", "supervision", "log_usage.py")],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True, timeout=30, env=env, cwd=hub)

    def _payload(self):
        return {"tool_name": "Skill", "tool_input": {"skill": "agent-orchestrator"},
                "tool_response": {"success": True}}

    def test_une_ecriture_impossible_ne_bloque_jamais_l_outil(self, tmp_path):
        """La moitié qui marchait déjà : un hook PostToolUse qui casse casserait
        l'outil de l'utilisateur. Elle doit survivre à la correction."""
        r = self._lancer(tmp_path / "absent" / "profond" / "usage.jsonl", self._payload())
        assert r.returncode == 0, (
            f"le hook a bloque l'outil (exit {r.returncode})")

    def test_une_ecriture_impossible_est_signalee_sur_stderr(self, tmp_path):
        """La moitié qui manquait. Sans elle, « exit 0 » veut dire aussi bien
        « journalisé » que « perdu » — et personne ne peut distinguer les deux."""
        r = self._lancer(tmp_path / "absent" / "profond" / "usage.jsonl", self._payload())
        assert r.stderr.strip(), (
            "une invocation perdue ne laisse aucune trace sur stderr")

    def test_le_cas_nominal_reste_silencieux_et_ecrit(self, tmp_path):
        """Un garde-fou qui parle aussi quand tout va bien finit ignoré."""
        usage = tmp_path / "usage.jsonl"
        r = self._lancer(usage, self._payload())
        assert r.returncode == 0
        assert usage.is_file(), "l'invocation nominale n'a pas ete journalisee"
        assert not r.stderr.strip(), f"bruit sur le cas nominal : {r.stderr!r}"


def _charger_log_usage(nom):
    spec = importlib.util.spec_from_file_location(nom, LOG_USAGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _agent_line(session_id, ts):
    return json.dumps({"ts": ts, "session_id": session_id, "tool": "Agent",
                       "subagent_type": "Explore", "skill": None, "description": None})


def _stop_line(session_id, ts):
    return json.dumps({"ts": ts, "session_id": session_id, "event": "subagent-stop"})


class TestDureeAppareeSeulementSansAmbiguite:
    """Veille adoptée 2026-09-03 : aucune durée n'était calculable (SubagentStop
    capte la fin, jamais le couple lancement/fin), donc aucun seuil de
    non-convergence n'était mesurable — incident source : un sous-agent resté
    `running` 4h+ contre 8-17 min pour des tâches comparables, arrêté sans résultat.
    Une durée FAUSSE est pire qu'aucune durée (même principe que `_echec_avere`,
    qui ne marque un échec que positivement détecté) : ces tests verrouillent
    qu'un fan-out concurrent (le cas courant de ce dispatcher, ≤ 4 sous-agents en
    parallèle) ne produit JAMAIS une durée devinée."""

    def test_un_seul_agent_lance_puis_arrete_recoit_une_duree(self, tmp_path):
        j = tmp_path / "u.jsonl"
        mod = _charger_log_usage("log_usage_duree1")
        mod.USAGE_PATH = str(j)
        j.write_text(_agent_line("s1", "2026-09-03T10:00:00+02:00") + "\n", encoding="utf-8")
        duree = mod._duree_appariee("s1", "2026-09-03T10:05:00+02:00")
        assert duree == 300.0

    def test_deux_agents_concurrents_ne_produisent_aucune_duree(self, tmp_path):
        j = tmp_path / "u.jsonl"
        mod = _charger_log_usage("log_usage_duree2")
        mod.USAGE_PATH = str(j)
        contenu = (_agent_line("s1", "2026-09-03T10:00:00+02:00") + "\n"
                  + _agent_line("s1", "2026-09-03T10:00:01+02:00") + "\n")
        j.write_text(contenu, encoding="utf-8")
        # DEUX lancements ouverts, aucun SubagentStop encore vu : ambigu.
        duree = mod._duree_appariee("s1", "2026-09-03T10:05:00+02:00")
        assert duree is None, "deux lancements concurrents ne doivent jamais produire une duree devinee"

    def test_le_premier_ferme_le_second_reste_ouvert_et_recoit_sa_duree(self, tmp_path):
        j = tmp_path / "u.jsonl"
        mod = _charger_log_usage("log_usage_duree3")
        mod.USAGE_PATH = str(j)
        contenu = (_agent_line("s1", "2026-09-03T10:00:00+02:00") + "\n"
                  + _agent_line("s1", "2026-09-03T10:00:01+02:00") + "\n"
                  + _stop_line("s1", "2026-09-03T10:03:00+02:00") + "\n")
        j.write_text(contenu, encoding="utf-8")
        # le premier lancement (10:00:00) a ete apparie au stop de 10:03:00 (FIFO) ;
        # il ne reste que le second (10:00:01) ouvert -> non ambigu desormais.
        duree = mod._duree_appariee("s1", "2026-09-03T10:05:00+02:00")
        assert duree == round(299.0, 1)

    def test_le_hook_reel_ecrit_une_duree_sur_un_arret_non_ambigu(self, tmp_path):
        j = tmp_path / "u.jsonl"
        _lancer({"hook_event_name": "PostToolUse", "session_id": "s2", "tool_name": "Agent",
                "tool_input": {"subagent_type": "Explore"}}, j)
        _lancer({"hook_event_name": "SubagentStop", "session_id": "s2"}, j)
        lignes = _lignes(j)
        stop = [l for l in lignes if l.get("event") == "subagent-stop"][0]
        assert "duree_s" in stop and stop["duree_s"] >= 0


