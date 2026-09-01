"""Propage le SOCLE de `agent-orchestrator` vers la flotte sans écraser le local.

Finding `flotte:agent-orchestrator-socle-vs-local`, arbitré le 2026-09-01. Le fichier
était UNE seule masse : impossible de le mettre à jour sans écraser la spécialisation
locale, impossible de garder le local sans figer la copie à sa génération d'origine.
Mesure du 2026-08-31 : les 5 sections de capacité étaient absentes de 6 copies sur 6,
pendant que 3 copies portaient du texte introuvable au hub — de la R3 correctement
appliquée, qu'un `copy` aurait détruite.

LA COUPE. Chaque copie devient deux morceaux aux régimes opposés :

* le **SOCLE** — tout ce que le hub publie dans `export/` — est une donnée GÉNÉRÉE :
  réécrite intégralement à chaque propagation, jamais éditée chez la cible ;
* le chapitre **« Portée sur ce projet »** est du travail HUMAIN : lu, préservé
  octet pour octet, et re-collé tel quel. `propager()` ne le compose jamais.

Sans cette coupe, la question « dérive ou spécialisation ? » devait être ré-instruite à
la main à chaque fois — elle avait coûté un sous-agent et 34 appels d'outils.

LA LIGNE DE PROVENANCE (proposition (d)) répond à l'autre moitié du problème : aucune
des 8 copies ne disait de quelle génération elle descendait. Chacune porte désormais
`socle : <hash court du hub> du <date>` — de quoi répondre sans relire 8 fichiers.

GARDE-FOU CENTRAL : une cible dont le chapitre local est introuvable n'est PAS écrasée.
Le script refuse et le signale, parce que le seul cas où l'écrasement détruit vraiment
quelque chose est aussi celui où l'on ne peut pas le deviner. `--dry-run` est le mode
par défaut de la prudence : il montre le diff sans écrire.

Usage :
  py .claude/dispositif/propager_socle.py --dry-run          # tous les projets
  py .claude/dispositif/propager_socle.py --projet VSCode3   # une cible
  py .claude/dispositif/propager_socle.py --appliquer        # écrit vraiment
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import subprocess

DISPOSITIF = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(DISPOSITIF))
SOCLE_SRC = os.path.join(HUB, "export", "skills", "agent-orchestrator", "SKILL.md")
REL_CIBLE = os.path.join(".claude", "skills", "agent-orchestrator", "SKILL.md")

TITRE_LOCAL = "## Portée sur ce projet"
MARQUEUR_PROVENANCE = "<!-- SOCLE-PROVENANCE:"


def projets() -> list[tuple[str, str]]:
    chemin = os.path.join(HUB, "projets.json")
    with io.open(chemin, encoding="utf-8") as fh:
        data = json.load(fh)
    return [(p["nom"], p["chemin"]) for p in data.get("projets", [])
            if p.get("nom") and p.get("chemin") and os.path.abspath(p["chemin"]) != HUB]


def hash_hub() -> str:
    """Hash court du hub — la génération dont descend le socle propagé."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HUB,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() or "inconnu"
    except (OSError, subprocess.SubprocessError):
        return "inconnu"


def extraire_chapitre_local(texte: str) -> str | None:
    """Le chapitre « Portée sur ce projet », rendu OCTET POUR OCTET.

    Renvoie None s'il n'y en a pas — et c'est un cas d'arrêt, pas un cas par défaut :
    trois copies portent du texte local TISSÉ dans les sections du socle (le journal
    en deux temps de VSCode, la ligne `slides_diagnostic.py` de VSCode2). Ce texte-là
    ne s'extrait pas mécaniquement ; il doit être déplacé à la main dans un chapitre
    « Portée sur ce projet » AVANT la première propagation. Deviner à sa place, c'est
    exactement l'écrasement que le finding interdit.
    """
    i = texte.find(TITRE_LOCAL)
    if i == -1:
        return None
    reste = texte[i:]
    fin = len(reste)
    for ligne in ("\n## ", "\n# "):
        j = reste.find(ligne, 1)
        if j != -1:
            fin = min(fin, j)
    return reste[:fin].rstrip() + "\n"


def composer(socle: str, chapitre_local: str, provenance: str) -> str:
    """Socle généré + provenance + chapitre local, dans l'ordre de VSCode1.

    Le chapitre local se place APRÈS l'introduction et AVANT « ## Méthode » : c'est
    la place qu'il occupe déjà dans VSCode1, la seule copie qui avait résolu le
    problème avant nous. Un lecteur qui ouvre le fichier voit donc ce qui est propre
    à SON projet avant la méthode générique.
    """
    ancre = "## Méthode — 5 étapes"
    if ancre not in socle:
        raise ValueError("socle inattendu : ancre « %s » absente" % ancre)
    tete, suite = socle.split(ancre, 1)
    return tete + provenance + "\n" + chapitre_local + "\n" + ancre + suite


def ligne_provenance(hash_court: str, jour: str) -> str:
    return (f"{MARQUEUR_PROVENANCE} socle : {hash_court} du {jour} -->\n"
            f"> **Socle généré** — tout ce qui suit `## Méthode` vient du hub de "
            f"supervision (`{hash_court}`, {jour}) et sera **réécrit** à la prochaine "
            f"propagation.\n> Le chapitre « Portée sur ce projet » ci-dessous, lui, "
            f"n'est jamais réécrit : c'est le travail local.\n")


def traiter(nom: str, racine: str, socle: str, provenance: str, appliquer: bool) -> dict:
    cible = os.path.join(racine, REL_CIBLE)
    if not os.path.isfile(cible):
        return {"projet": nom, "etat": "absent", "detail": "pas de copie installée"}
    actuel = io.open(cible, encoding="utf-8").read()
    local = extraire_chapitre_local(actuel)
    if local is None:
        return {"projet": nom, "etat": "sans-chapitre-local",
                "detail": ("aucun « Portée sur ce projet » : le local doit y être "
                           "déplacé à la main avant propagation — refus d'écraser")}
    nouveau = composer(socle, local, provenance)
    if nouveau == actuel:
        return {"projet": nom, "etat": "a-jour", "detail": f"{len(local.splitlines())} l. locales"}
    if appliquer:
        io.open(cible, "w", encoding="utf-8", newline="\n").write(nouveau)
    return {"projet": nom, "etat": "applique" if appliquer else "a-propager",
            "detail": (f"{len(actuel.splitlines())} l. -> {len(nouveau.splitlines())} l., "
                       f"chapitre local de {len(local.splitlines())} l. préservé")}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Propage le socle agent-orchestrator vers la flotte.")
    p.add_argument("--appliquer", action="store_true", help="écrit vraiment (défaut : dry-run)")
    p.add_argument("--dry-run", action="store_true", help="montre sans écrire (défaut)")
    p.add_argument("--projet", help="limiter à un projet")
    args = p.parse_args(argv)
    appliquer = args.appliquer and not args.dry_run

    if not os.path.isfile(SOCLE_SRC):
        print("socle introuvable : regenerer export/ d'abord")
        return 1
    socle = io.open(SOCLE_SRC, encoding="utf-8").read()
    prov = ligne_provenance(hash_hub(), dt.date.today().isoformat())

    cibles = [(n, c) for n, c in projets() if not args.projet or n == args.projet]
    if not cibles:
        print("aucune cible")
        return 1

    resultats = [traiter(n, c, socle, prov, appliquer) for n, c in cibles]
    for r in resultats:
        print(f"  {r['etat']:<20} {r['projet']:<9} {r['detail']}")
    bloques = [r for r in resultats if r["etat"] == "sans-chapitre-local"]
    print(f"\n{len(resultats)} cible(s) — mode {'ECRITURE' if appliquer else 'dry-run'}")
    if bloques:
        print("REFUS d'ecraser " + ", ".join(r["projet"] for r in bloques) +
              " : creer leur chapitre « Portee sur ce projet » a la main d'abord.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
