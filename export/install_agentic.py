"""Installateur du dispositif agentic — à exécuter DEPUIS le répertoire `export/`.

Ce script est la contrepartie de `export_agentic.py` : celui-ci *produit* `export/`
depuis les sources vivantes du hub, celui-là *installe* le contenu d'`export/` dans
un projet cible. Il est **auto-portant** : il ne lit que les fichiers posés à côté de
lui, jamais `~/Documents/VSCodeN`. Un `export/` copié ailleurs s'installe donc sur une
machine qui n'a pas le hub.

C'est la différence avec `deploy_nouveau_projet.py`, qui matérialise un manifeste de
sources vivantes réparties sur plusieurs dépôts de la flotte : pratique tant qu'on est
sur la machine du hub, inutilisable ailleurs, et silencieusement périmé si l'un des
dépôts sources dérive (mesuré le 2026-08-31 : la skill orchestrateur servie aux
nouveaux projets faisait 120 lignes contre 467 au hub).

Usage :
  py install_agentic.py --liste
  py install_agentic.py --dry-run "C:/chemin/ProjetCible"
  py install_agentic.py "C:/chemin/ProjetCible" --nom MonProjet
  py install_agentic.py "C:/chemin/ProjetCible" --nom MonProjet --force

Sans --force, aucun fichier existant n'est écrasé : il est signalé « garde » et
l'installation continue. `settings.json` n'est JAMAIS écrasé — il est fusionné (les
hooks du dispositif sont ajoutés, ceux du projet cible sont préservés).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

EXPORT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFESTE = os.path.join(EXPORT_DIR, "MANIFESTE.json")


def _lire_manifeste() -> dict:
    if not os.path.isfile(MANIFESTE):
        sys.exit(
            "MANIFESTE.json introuvable a cote de ce script.\n"
            "Ce script doit etre execute depuis le repertoire export/ genere par :\n"
            "  py .claude/dispositif/export_agentic.py"
        )
    with open(MANIFESTE, encoding="utf-8") as fh:
        return json.load(fh)


def _script_du_hook(commande: str) -> str:
    """Identifie un hook par le NOM DU SCRIPT qu'il lance, pas par sa ligne de commande.

    Deux projets ecrivent la meme chose differemment : `${CLAUDE_PROJECT_DIR}/...` avec
    accolades ici, `$CLAUDE_PROJECT_DIR/...` sans accolades la, `py` ou `python`. Comparer
    les chaines completes fait donc croire a deux hooks distincts et les installe en
    double : mesure du 2026-08-31 sur VSCode2 et VSCode3, 6 a 7 hooks dupliques, chacun
    execute deux fois a chaque session. Le script lance, lui, est le meme.
    """
    commande = (commande or "").replace("\\", "/").strip()
    for morceau in reversed(commande.replace('"', " ").replace("'", " ").split()):
        if morceau.endswith(".py"):
            return morceau.rsplit("/", 1)[-1]
    return commande


def _fusionner_settings(cible: str, gabarit: dict, force: bool) -> str:
    """Fusionne les hooks/permissions du dispositif dans le settings.json cible.

    Un settings.json existant appartient au projet cible : on ajoute ce qui manque,
    on ne retire jamais. Deux hooks sont réputés identiques s'ils portent la même
    commande — le dispositif est donc réinstallable sans dupliquer ses propres hooks.
    """
    chemin = os.path.join(cible, ".claude", "settings.json")
    existant: dict = {}
    if os.path.isfile(chemin):
        try:
            with open(chemin, encoding="utf-8") as fh:
                existant = json.load(fh)
        except (OSError, ValueError) as err:
            if not force:
                return f"ECHEC   .claude/settings.json illisible ({err}) - relancer avec --force pour l'ecraser"
            existant = {}

    # « JSON valide » n'est pas « de la forme attendue ». Un settings.json contenant
    # une LISTE passait json.load puis explosait en AttributeError sur .setdefault —
    # et le crash survenait APRES la copie des 47 fichiers, sans rollback, la
    # checklist finale jamais affichee (audit du 2026-09-01). Le try/except ne
    # couvrait que la lecture ; il couvre desormais la forme.
    if not isinstance(existant, dict):
        if not force:
            return ("ECHEC   .claude/settings.json de forme inattendue "
                    f"({type(existant).__name__} au lieu d'un objet) - rien fusionne, "
                    "relancer avec --force pour repartir d'un settings neuf")
        existant = {}

    # Meme prudence un cran plus bas : `permissions` ou `hooks` d'une forme inattendue
    # relancerait l'AttributeError. On REFUSE plutot que d'ecraser — ces cles
    # appartiennent au projet cible, pas au kit.
    for cle, attendu in (("permissions", dict), ("hooks", dict)):
        if cle in existant and not isinstance(existant[cle], attendu):
            return (f"ECHEC   .claude/settings.json : « {cle} » est un "
                    f"{type(existant[cle]).__name__}, un objet etait attendu - rien "
                    "fusionne, le fichier de la cible est laisse intact")
    permissions = existant.setdefault("permissions", {})
    if not isinstance(permissions.get("deny", []), list):
        return ("ECHEC   .claude/settings.json : « permissions.deny » n'est pas une "
                "liste - rien fusionne, le fichier de la cible est laisse intact")

    deny = permissions.setdefault("deny", [])
    for regle in gabarit.get("permissions", {}).get("deny", []):
        if regle not in deny:
            deny.append(regle)

    hooks = existant.setdefault("hooks", {})
    ajoutes = 0
    for evenement, groupes in gabarit.get("hooks", {}).items():
        cibles = hooks.setdefault(evenement, [])
        deja = {
            _script_du_hook(h.get("command", ""))
            for groupe in cibles
            if isinstance(groupe, dict)
            for h in groupe.get("hooks", [])
            if isinstance(h, dict)
        }
        for groupe in groupes:
            neufs = [h for h in groupe.get("hooks", [])
                     if _script_du_hook(h.get("command", "")) not in deja]
            if neufs:
                cibles.append({**groupe, "hooks": neufs})
                ajoutes += len(neufs)

    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(existant, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return f"FUSION  .claude/settings.json ({ajoutes} hook(s) ajoute(s))"


def _sous_la_cible(cible: str, chemin: str) -> bool:
    """Le chemin resolu reste-t-il SOUS le repertoire cible ?

    `os.path.abspath` normalise les « .. » avant comparaison : c'est ce qui distingue
    une destination legitime d'une remontee. `os.path.commonpath` leve ValueError quand
    les deux chemins sont sur des volumes differents sous Windows (C: vs D:) — c'est
    justement un cas a refuser, d'ou le False.
    """
    try:
        return os.path.commonpath([os.path.abspath(cible),
                                   os.path.abspath(chemin)]) == os.path.abspath(cible)
    except ValueError:
        return False


def installer(cible: str, nom: str, force: bool, dry_run: bool) -> int:
    manifeste = _lire_manifeste()
    fichiers = manifeste.get("fichiers", [])
    if not fichiers:
        sys.exit("MANIFESTE.json ne liste aucun fichier - export/ est vide ou corrompu.")

    cible = os.path.abspath(cible)
    prefixe = "[dry-run] " if dry_run else ""
    lignes: list[str] = []
    ecrits = conserves = manquants = 0

    for entree in fichiers:
        src = os.path.join(EXPORT_DIR, entree["export"].replace("/", os.sep))
        dst = os.path.join(cible, entree["destination"].replace("/", os.sep))
        # MANIFESTE.json VOYAGE AVEC LE KIT : il n'est pas forcement celui que le hub a
        # ecrit. Une destination « ../DEPOT_VOISIN/... » ou absolue sortait du
        # repertoire cible, en rapportant une ligne « ecrit » ordinaire et en sortant
        # avec 0 (audit technique du 2026-09-01). On refuse ce qui ne reste pas SOUS la
        # cible ; l'installateur n'a aucune raison legitime d'ecrire ailleurs.
        if not _sous_la_cible(cible, dst):
            lignes.append(f"REFUS   {entree['destination']} : destination hors du "
                          f"repertoire cible - entree ignoree")
            manquants += 1
            continue
        if not os.path.isfile(src):
            lignes.append(f"ABSENT  {entree['export']} (manque dans export/)")
            manquants += 1
            continue
        # INTEGRITE (arbitrage « securise les fichiers de export », 2026-09-01).
        # Le manifeste voyage avec le kit : il liste ce que le hub a publie, et
        # l empreinte permet enfin de verifier que le fichier pose a cote est bien
        # celui-la. Sans empreinte (kit publie avant ce volet), on installe comme
        # avant — refuser transformerait une amelioration en panne de deploiement.
        attendue = entree.get("sha256")
        if attendue:
            try:
                with open(src, "rb") as fh:
                    reelle = hashlib.sha256(fh.read()).hexdigest()
            except OSError as err:
                lignes.append(
                    f"ECHEC   {entree['destination']} : illisible ({err})")
                manquants += 1
                continue
            if reelle != attendue:
                lignes.append(
                    f"REFUS   {entree['destination']} : empreinte non conforme "
                    f"(attendue {attendue[:12]}..., lue {reelle[:12]}...) - le fichier "
                    f"du kit n est pas celui que le hub a publie")
                manquants += 1
                continue
        if os.path.exists(dst) and not force:
            lignes.append(f"garde   {entree['destination']} (existe deja)")
            conserves += 1
            continue
        if not dry_run:
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            except OSError as err:
                # Cas mesuré sous Windows : au-delà de 260 caractères, CopyFile2 rend
                # « chemin introuvable » alors que le répertoire vient d'être créé.
                indice = " (chemin > 260 caracteres : cible trop profonde pour Windows)" \
                    if len(dst) > 245 else ""
                lignes.append(f"ECHEC   {entree['destination']} : {err}{indice}")
                manquants += 1
                continue
        lignes.append(f"ecrit   {entree['destination']}")
        ecrits += 1

    gabarit = manifeste.get("settings_template", {})
    if gabarit:
        if dry_run:
            lignes.append("FUSION  .claude/settings.json (simule)")
        else:
            lignes.append(_fusionner_settings(cible, gabarit, force))

    # CLAUDE.md N'APPARTIENT PAS AU KIT. `--force` sert a rafraichir les fichiers du
    # dispositif ; les regles projet de la cible sont du travail humain. La version
    # precedente les ecrasait par le squelette vide, sans sauvegarde, en rapportant
    # « ecrit CLAUDE.md (squelette a completer) » — mesure par l'audit du 2026-09-01 :
    # 3 lignes de regles metier remplacees par 30 lignes de gabarit, exit 0.
    # Refuser n'est pas perdre : le squelette est pose a cote, en .propose.
    gabarit_md = manifeste.get("claude_md_template", "")
    chemin_md = os.path.join(cible, "CLAUDE.md")
    if gabarit_md and not os.path.exists(chemin_md):
        if not dry_run:
            with open(chemin_md, "w", encoding="utf-8") as fh:
                fh.write(gabarit_md.replace("{nom}", nom or os.path.basename(cible)))
        lignes.append("ecrit   CLAUDE.md (squelette a completer)")
        ecrits += 1
    elif gabarit_md:
        if not dry_run:
            with open(chemin_md + ".propose", "w", encoding="utf-8") as fh:
                fh.write(gabarit_md.replace("{nom}", nom or os.path.basename(cible)))
        lignes.append("garde   CLAUDE.md (redige par le projet - jamais ecrase, meme "
                      "avec --force ; squelette pose en CLAUDE.md.propose)")
        conserves += 1

    print(f"{prefixe}Installation du dispositif agentic dans : {cible}")
    print(f"{prefixe}Source : export/ genere le {manifeste.get('genere_le', '?')}")
    print()
    for ligne in lignes:
        print(f"  {prefixe}{ligne}")
    print()
    print(f"{prefixe}{ecrits} ecrit(s), {conserves} conserve(s), {manquants} absent(s)")

    if manquants:
        print("\nATTENTION : des fichiers du manifeste manquent dans export/ -")
        print("regenerer au hub avec  py .claude/dispositif/export_agentic.py")

    if not dry_run:
        print("\n--- Checklist apres installation (rien de ceci n'est automatique) ---")
        for i, etape in enumerate(manifeste.get("checklist", []), 1):
            print(f"  {i}. {etape}")

    return 1 if manquants else 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description="Installe le dispositif agentic dans un projet cible.")
    parseur.add_argument("cible", nargs="?", help="repertoire du projet a equiper")
    parseur.add_argument("--nom", default="", help="nom du projet (squelette CLAUDE.md)")
    parseur.add_argument("--force", action="store_true", help="ecraser les fichiers existants")
    parseur.add_argument("--dry-run", action="store_true", help="montrer sans rien ecrire")
    parseur.add_argument("--liste", action="store_true", help="lister le manifeste et sortir")
    args = parseur.parse_args(argv)

    if args.liste:
        manifeste = _lire_manifeste()
        print(f"export/ genere le {manifeste.get('genere_le', '?')}")
        for entree in manifeste.get("fichiers", []):
            print(f"  {entree['export']:<56} -> {entree['destination']}")
        return 0

    if not args.cible:
        parseur.error("indiquer le repertoire cible (ou utiliser --liste)")
    if not os.path.isdir(args.cible):
        sys.exit(f"Repertoire cible introuvable : {args.cible}")
    return installer(args.cible, args.nom, args.force, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
