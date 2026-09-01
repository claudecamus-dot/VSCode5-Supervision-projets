"""Superviseur d'agents — étage 1 : journal temps réel des invocations Skill/Agent.

Branché sur le hook PostToolUse (matcher Skill|Agent|Task). Append une ligne JSON dans
.claude/supervision/usage.jsonl à chaque invocation — couvre la session en cours, que le
scan différé des transcripts (scan_transcripts.py) ne verra qu'à la prochaine session.
Ne bloque jamais l'outil (exit 0 en toutes circonstances), mais ne perd plus rien
en silence : une invocation non journalisée est signalée sur stderr.
"""
import datetime
import json
import os
import sys

# Windows : la console par defaut est cp1252 — un payload de hook accentué lu tel quel
# part en mojibake dans le journal. Mesuré sur le fichier réel : 57 lignes sur 233
# contiennent « Ã » ou « â€ ». Pire, un UnicodeDecodeError est une sous-classe de
# ValueError : il était avalé par le `except` ci-dessous, l'invocation disparaissait en
# silence et l'étage 1 sous-comptait. Même reconfiguration que le canon log_run.py.
# stdin en utf-8-sig : un pipe PowerShell 5.1 préfixe un BOM qui casserait json.loads
# (vécu 2026-07-23) ; sans BOM, utf-8-sig == utf-8.
for _flux, _enc in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"), (sys.stderr, "utf-8")):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(encoding=_enc)

# Surchargeable pour les tests : le journal d'usage REEL ne doit jamais etre pollue
# par la suite (meme motif que AGENT_SUPERVISION_JOBS_JOURNAL, cf. tests/conftest.py).
USAGE_PATH = os.environ.get("AGENT_SUPERVISION_USAGE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "usage.jsonl"
)


def main() -> int:
    # Ne bloque jamais (exit 0), mais ne perd plus rien en SILENCE : une invocation
    # non journalisée est un sous-comptage de l'étage 1, elle doit se voir.
    try:
        brut = sys.stdin.read()
    except UnicodeDecodeError as exc:
        print(f"log_usage : payload non décodable en UTF-8 ({exc}) — invocation NON "
              "journalisée, l'étage 1 sous-compte d'autant.", file=sys.stderr)
        return 0
    except OSError as exc:
        print(f"log_usage : stdin illisible ({exc}) — invocation non journalisée.",
              file=sys.stderr)
        return 0
    try:
        data = json.loads(brut)
    except ValueError as exc:
        print(f"log_usage : payload JSON invalide ({exc}) — invocation non "
              "journalisée.", file=sys.stderr)
        return 0
    if not isinstance(data, dict):
        print("log_usage : payload inattendu (objet JSON attendu) — invocation non "
              "journalisée.", file=sys.stderr)
        return 0
    horodate = datetime.datetime.now().astimezone().isoformat(timespec="seconds")

    # SubagentStop — la FIN d'un sous-agent, et non plus seulement son lancement.
    # Adoption de la trouvaille `veille:disler-observabilite` (2026-09-01). L'écart
    # mesuré chez eux : 12 types d'événements captés contre UN SEUL ici. Celui-ci est
    # le plus utile au hub, parce qu'il ferme une question que l'étage 1 ne savait pas
    # poser : un sous-agent DISPATCHÉ et un sous-agent REVENU s'écrivaient pareil.
    # Sans lui, un fan-out dont une branche meurt est indiscernable d'un fan-out
    # complet — exactement le genre de non-convergence que le superviseur cherche.
    if data.get("hook_event_name") == "SubagentStop":
        entry = {"ts": horodate, "session_id": data.get("session_id"),
                 "event": "subagent-stop"}
        _ecrire(entry)
        return 0

    tool = data.get("tool_name", "")
    if tool not in ("Skill", "Agent", "Task"):
        return 0
    tool_input = data.get("tool_input") or {}
    entry = {
        "ts": horodate,
        "session_id": data.get("session_id"),
        "tool": tool,
        "skill": tool_input.get("skill"),
        "subagent_type": tool_input.get("subagent_type")
        or (None if tool == "Skill" else "(defaut)"),
        "description": tool_input.get("description"),
    }
    # L'échec n'est marqué que s'il est POSITIVEMENT détecté. Les formes de réponse
    # varient d'un outil à l'autre : deviner « pas de succès donc échec » fabriquerait
    # des KO qui n'ont pas eu lieu, et le superviseur compte les `ko-repete`. Absence
    # de marque = on ne sait pas, pas « ça a marché ».
    if _echec_avere(data.get("tool_response")):
        entry["echec"] = True
    _ecrire(entry)
    return 0


def _echec_avere(reponse) -> bool:
    """True seulement si la réponse DIT qu'elle a échoué."""
    if isinstance(reponse, dict):
        if reponse.get("is_error") is True or reponse.get("success") is False:
            return True
        statut = str(reponse.get("status", "")).lower()
        return statut in ("error", "failed", "failure")
    return False


def _ecrire(entry: dict) -> None:
    with open(USAGE_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
