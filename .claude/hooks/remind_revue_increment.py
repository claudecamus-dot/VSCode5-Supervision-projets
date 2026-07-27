"""SessionStart hook — rappelle la boucle revue-increment du hub.

Le hub enchaîne les orchestrations sur la flotte (39+ runs journalisés) ; sans
rappel systématique, les revues de fin d'incrément restent improvisées
(constat superviseur 2026-07-25, finding pratique-revue). Ce hook réinjecte la
discipline à chaque session, adaptée au canal du hub : vérité du journal
(--solde), arbitrages tracés, wiki régénéré, suite pytest, commits scopés (R2).

Non bloquant : émet seulement un additionalContext. Fail open — toute erreur
rend la main sans injecter, pour ne jamais casser un démarrage de session.
"""
import json
import sys

REMINDER = (
    "Discipline qualité du hub (rappel systématique) : avant de considérer un "
    "incrément « livré » — surtout après une campagne de remédiations flotte — "
    "lancer la boucle `/revue-increment` : vérité du journal (runs soldés via "
    "log_run.py --solde, jamais succes auto-déclaré sur un livrable à valider), "
    "arbitrages tracés à la cible exacte, wiki régénéré et rendu regardé, suite "
    "pytest verte, commits scopés au périmètre (R2) quand d'autres dépôts ont "
    "été touchés. Puis appliquer les correctifs et re-vérifier — pas de revue "
    "constat-seulement. Les actions irréversibles ou non arbitrées se "
    "proposent, ne s'exécutent pas (R4)."
)


def main() -> None:
    try:
        json.load(sys.stdin)
    except Exception:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": REMINDER,
        }
    }))


if __name__ == "__main__":
    main()
