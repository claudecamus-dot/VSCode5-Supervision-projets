"""Écarte une trouvaille de veille — le pendant déterministe (0 token) du bouton
« Écarter » du judas (onglet Actions du wiki), symétrique de `refuser_arbitrage.py`
pour les findings du diagnostic.

Écarter est un FAIT (une décision humaine), pas une tâche qui a besoin d'un LLM.
Le geste trace les DEUX écritures que § 2 quater de la skill orchestrateur exige —
sans la seconde, le wiki et le point du jour continueraient d'afficher la trouvaille
comme en attente de décision (panne mécanique mesurée le 2026-08-31 : 3 trouvailles
sur 4 annoncées « en attente » portaient déjà une décision tracée) :

1. l'entrée de `veille.json` passe en `statut: ecarte`, avec la raison datée
   ajoutée en fin de `pertinence` ;
2. une ligne d'arbitrage `ECARTE : <raison>` est ajoutée à `arbitrages.json`, à la
   cible `veille:<slug>` — le slug est dérivé du titre par la MÊME réduction
   alphanumérique que `point_du_jour._veille_arbitree` fait au matching, donc la
   fermeture est garantie par construction, pas par convention.

Ordre des écritures : l'arbitrage d'abord, le statut ensuite — jamais d'état sans
trace. Les deux fichiers sont validés AVANT la première écriture : un arbitrage
illisible bloque tout (corrompu n'est PAS absent — même leçon que
`refuser_arbitrage.py`, où la confusion a failli remplacer 94 arbitrages par un
fichier à une entrée).

Usage : py .claude/supervision/ecarter_trouvaille.py "<titre exact>" ["raison"]
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VEILLE_PATH = os.environ.get("AGENT_SUPERVISION_VEILLE") or os.path.join(
    ROOT, ".claude", "veille", "veille.json")
ARBITRAGES_PATH = os.environ.get("AGENT_SUPERVISION_ARBITRAGES") or os.path.join(
    ROOT, ".claude", "supervision", "arbitrages.json")
SCAN_SCRIPT = os.path.join(ROOT, "scripts", "scan_projets.py")


def _slug(titre: str) -> str:
    """Slug de cible `veille:<slug>` dérivé du titre.

    Contrainte de construction : `point_du_jour._veille_arbitree` réduit slug et
    titre en `[a-z0-9]` puis teste « slug contenu dans titre ». En dérivant le slug
    du titre par la même réduction (les caractères hors table — accents, tirets
    cadratins — tombent des DEUX côtés), le contenu est garanti. Tronqué à 60 :
    un préfixe reste contenu."""
    s = re.sub(r"[^a-z0-9]+", "-", (titre or "").lower()).strip("-")
    return s[:60].strip("-")


def _charge_stricte(path, quoi):
    """(data, code) — code 2 = illisible (on n'écrit RIEN), data=None si absent
    n'est pas tolérable pour ce fichier (l'appelant décide)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), 0
    except FileNotFoundError:
        return None, 1
    except (OSError, ValueError) as exc:
        print(f"ecarter_trouvaille : ABANDON — {path} est illisible ({exc}). "
              f"Rien n'a été écrit : {quoi} ne se répare pas en l'écrasant. "
              "Restaurer la dernière version saine avant de relancer.",
              file=sys.stderr)
        return None, 2


def _ecrire_atomique(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main(argv=None, veille_path=None, arbitrages_path=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    veille_path = veille_path or VEILLE_PATH
    arbitrages_path = arbitrages_path or ARBITRAGES_PATH
    if not argv or not argv[0].strip():
        print("ecarter_trouvaille : usage : \"<titre exact>\" [\"raison\"]")
        return 1
    titre = argv[0].strip()
    raison = argv[1].strip() if len(argv) > 1 and argv[1].strip() else \
        "écarté via le bouton du wiki, sans raison précisée"
    slug = _slug(titre)
    if not slug:
        print("ecarter_trouvaille : titre sans caractère alphanumérique — "
              "impossible d'en dériver une cible d'arbitrage.")
        return 1

    # Valider LES DEUX fichiers avant la PREMIÈRE écriture : un état modifié sans
    # trace d'arbitrage (ou l'inverse) est pire que rien.
    veille, code_v = _charge_stricte(veille_path, "le journal de veille")
    if code_v == 2:
        return 2
    if veille is None or not isinstance(veille.get("entrees"), list):
        print(f"ecarter_trouvaille : {veille_path} absent ou sans clé 'entrees' — "
              "rien à écarter.", file=sys.stderr)
        return 2
    arb, code_a = _charge_stricte(arbitrages_path, "la mémoire d'arbitrage (R4)")
    if code_a == 2:
        return 2
    if arb is None:
        arb = {"arbitrages": []}
    if not isinstance(arb, dict) or not isinstance(arb.get("arbitrages", []), list):
        print(f"ecarter_trouvaille : ABANDON — {arbitrages_path} a une structure "
              "inattendue ({\"arbitrages\": [...]} attendu). Rien n'a été écrit.",
              file=sys.stderr)
        return 2
    arb.setdefault("arbitrages", [])

    entrees = [e for e in veille["entrees"]
               if isinstance(e, dict) and (e.get("titre") or "").strip() == titre]
    if not entrees:
        candidates = [e.get("titre") for e in veille["entrees"]
                      if isinstance(e, dict)
                      and e.get("statut") in ("nouveau", "etudie")]
        print(f"ecarter_trouvaille : aucune entrée au titre exact « {titre} ». "
              f"En attente actuellement : {candidates}")
        return 1
    if len(entrees) > 1:
        print(f"ecarter_trouvaille : {len(entrees)} entrées portent ce titre — "
              "ambigu, rien n'a été écrit.")
        return 1
    entree = entrees[0]

    date = dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    arb["arbitrages"].append({
        "cible": f"veille:{slug}",
        "date": date,
        "decision": f"ECARTE : {raison}",
    })
    _ecrire_atomique(arbitrages_path, arb)

    entree["statut"] = "ecarte"
    entree["pertinence"] = (str(entree.get("pertinence") or "").rstrip()
                            + f" [ecarte le {date} : {raison}]").strip()
    _ecrire_atomique(veille_path, veille)
    print(f"ecarter_trouvaille : « {titre} » écarté ({date}) — {raison} "
          f"[cible veille:{slug}]")

    if os.environ.get("AGENT_SUPERVISION_SKIP_SCAN"):
        return 0   # tests : la régénération du wiki n'est pas leur objet
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", SCAN_SCRIPT,
                            "--no-refresh"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ecarter_trouvaille : wiki non régénéré ({exc}) — relancer "
              "scripts/scan_projets.py", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
