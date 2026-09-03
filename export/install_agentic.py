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
from datetime import datetime
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
            # Le nom seul suffit POUR LES HOOKS DU KIT, qui vivent tous sous
            # `.claude/hooks/` : c est ce qui permet de reconnaitre
            # `${CLAUDE_PROJECT_DIR}/...` et `$CLAUDE_PROJECT_DIR/...` comme
            # un seul hook (6 a 7 doublons corriges le 2026-08-31). Mais un
            # script HOMONYME range ailleurs — `tools/guard_destructive_git.py`
            # chez la cible — n est pas le meme programme : le confondre
            # faisait que le garde-fou BLOQUANT du kit etait copie sur disque,
            # donc compte « installe » par tout inventaire de presence, et
            # jamais enregistre. C est le corollaire de R6 pris en defaut par
            # le kit lui-meme (revue de securite du 2026-09-01).
            if "/.claude/hooks/" in morceau or morceau.startswith(".claude/hooks/"):
                return morceau.rsplit("/", 1)[-1]
            return morceau
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
            # `utf-8-sig` : PowerShell 5.1 — le shell PRIMAIRE de ce poste — ecrit avec
            # un BOM. Un settings.json parfaitement valide etait donc declare
            # « illisible », et le message orientait vers --force, lequel repart de {}
            # et fait disparaitre les deny, allow et hooks propres de la cible. Le kit
            # lisait deja en utf-8-sig ailleurs (log_run.py, log_usage.py) : c est
            # l incoherence qui coutait, pas la difficulte.
            with open(chemin, encoding="utf-8-sig") as fh:
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
    # SAUVEGARDE AVANT REECRITURE. Ce fichier porte les permissions de la
    # cible : c est le seul ecrit du kit qui n avait ni copie prealable ni
    # ecriture atomique, alors que log_run, write_diagnostic,
    # refuser_arbitrage et save_state utilisent tous temporaire+replace.
    # `--force` reste destructeur par nature ; ce qui n allait pas, c est
    # qu il le soit SANS FILET (revue de securite du 2026-09-01).
    sauvegarde = ""
    if os.path.isfile(chemin):
        horodate = datetime.now().strftime("%Y%m%d-%H%M%S")
        copie = f"{chemin}.{horodate}.avant-installation"
        try:
            shutil.copy2(chemin, copie)
            sauvegarde = f", copie dans {os.path.basename(copie)}"
        except OSError as err:
            return (f"ECHEC   .claude/settings.json : sauvegarde impossible "
                    f"({err}) - rien fusionne, le fichier de la cible est "
                    "laisse intact")
    temporaire = chemin + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as fh:
        json.dump(existant, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temporaire, chemin)
    return (f"FUSION  .claude/settings.json ({ajoutes} hook(s) ajoute(s)"
            f"{sauvegarde})")


_GITIGNORE_MARQUEUR = "# --- dispositif de supervision (genere par install_agentic) ---"
_GITIGNORE_LIGNES = [
    "orchestration/prompts.jsonl",
    "supervision/usage.jsonl",
    "supervision/jobs.jsonl",
    "supervision/vues.jsonl",
    "supervision/scan_incidents.jsonl",
    "supervision/state.json",
]


def _poser_gitignore(cible: str, dry_run: bool) -> str:
    """Ignore ce qui est MACHINE-LOCAL, sans toucher au journal ni aux arbitrages.

    Le kit installe dans `.claude/` de la cible des fichiers qui portent du texte
    libre, des identifiants de session et des chemins absolus du poste, et sa propre
    checklist demande a l etape 7 de committer l installation : sur un depot a remote
    externe, c est un canal de divulgation que personne n annoncait (revue de securite
    du 2026-09-01). `write_diagnostic.py` affirmait meme « Gitignore — donnee
    machine » : vrai au hub, jamais etabli chez la cible.

    CE QU ON N IGNORE PAS, et c est deliberе : `runs.jsonl` et `arbitrages.json` sont
    le JOURNAL et les DECISIONS du dispositif — R5 en fait la verite opposable, le hub
    les versionne a dessein. Les ignorer casserait la doctrine au lieu de proteger.
    Le finding melangeait les deux ; on les separe, et ce qu on ne peut pas ignorer,
    on l annonce.

    Un `.gitignore` existant appartient a la cible : on AJOUTE un bloc marque, une
    seule fois, jamais on n ecrase.
    """
    chemin = os.path.join(cible, ".claude", ".gitignore")
    existant = ""
    if os.path.isfile(chemin):
        try:
            with open(chemin, encoding="utf-8-sig") as fh:
                existant = fh.read()
        except OSError as err:
            return f"ECHEC   .claude/.gitignore illisible ({err})"
    if _GITIGNORE_MARQUEUR in existant:
        return "garde   .claude/.gitignore (bloc du dispositif deja present)"
    bloc = _GITIGNORE_MARQUEUR + "\n" + "\n".join(_GITIGNORE_LIGNES) + "\n"
    if dry_run:
        return f"ecrit   .claude/.gitignore ({len(_GITIGNORE_LIGNES)} regle(s))"
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        separateur = "" if not existant or existant.endswith("\n") else "\n"
        with open(chemin, "a", encoding="utf-8") as fh:
            fh.write(separateur + bloc)
    except OSError as err:
        return f"ECHEC   .claude/.gitignore : {err}"
    return f"ecrit   .claude/.gitignore ({len(_GITIGNORE_LIGNES)} regle(s) ajoutee(s))"


def _sous_la_cible(cible: str, chemin: str) -> bool:
    """Le chemin resolu reste-t-il SOUS le repertoire cible ?

    `os.path.abspath` normalise les « .. » avant comparaison : c'est ce qui distingue
    une destination legitime d'une remontee. `os.path.commonpath` leve ValueError quand
    les deux chemins sont sur des volumes differents sous Windows (C: vs D:) — c'est
    justement un cas a refuser, d'ou le False.
    """
    # `realpath` et non `abspath` : `abspath` normalise les « .. » mais NE SUIT PAS les
    # liens. Une jonction de repertoire dans l arbre cible — creable sans droits
    # d administrateur — satisfaisait donc `commonpath` tout en faisant ecrire ailleurs
    # (revue de securite du 2026-09-01, reproduit : `mklink /J` sur `.claude/hooks`,
    # les 5 hooks poses hors de la cible, lignes « ecrit » ordinaires, exit 0).
    try:
        return os.path.commonpath([os.path.realpath(cible),
                                   os.path.realpath(chemin)]) == os.path.realpath(cible)
    except ValueError:
        return False


def _skills_bmad_routees() -> list[str]:
    """Les skills BMAD que la table de routage du kit designe, dans l ordre du fichier.

    Le kit installe une skill d orchestration qui route 46 skills BMAD par besoin
    detecte, dont une bonne part « d office » — c est-a-dire sans demander. Mais BMAD
    ne fait PAS partie du kit : il s installe par son propre installateur. Rien ne
    garantissait donc que la cible possede ce que la table lui prescrit, et rien ne le
    disait : un routage vers le vide ressemble exactement a un routage qui marche.

    Mesure du 2026-09-02 : VSCode2 porte 39 des 46 skills, il lui manque
    bmad-create-architecture, bmad-create-prd, bmad-edit-prd, bmad-qa-generate-e2e-tests,
    bmad-quick-dev, bmad-spec et bmad-validate-prd — sept noms que sa table route quand
    meme.

    On lit la source du kit (EXPORT_DIR) et non la copie posee chez la cible : c est le
    seul chemin qui existe AUSSI en --dry-run, et la simulation est justement le moment
    ou l on veut apprendre ce qui manquera. Fail-open : pas de skill, pas de bloc, ou
    fichier illisible rendent une liste vide — un inventaire est une information, il ne
    doit jamais empecher une installation d aboutir.
    """
    chemin = os.path.join(EXPORT_DIR, "skills", "agent-orchestrator", "SKILL.md")
    try:
        with open(chemin, encoding="utf-8-sig") as fh:
            texte = fh.read()
    except OSError:
        return []
    debut = texte.find("BMAD-ROUTAGE:START")
    fin = texte.find("BMAD-ROUTAGE:END")
    if debut < 0 or fin <= debut:
        return []
    # SEULE LA COLONNE 2 DES VRAIES RANGEES. Deux faux positifs mesures le 2026-09-02 en
    # lancant cette verification sur la flotte reelle, avant correction :
    #   - la colonne 3 porte le SOUS-AGENT (`bmad-revue`, `bmad-recherche`), qui vit dans
    #     .claude/agents/ et non .claude/skills/ : les y chercher les declarait absents
    #     chez TOUTE cible, VSCode1 compris, qui possede pourtant les 46 ;
    #   - la prose de fin de bloc nomme les skills DEPRECIEES par BMAD pour dire de ne
    #     pas les router : les reclamer envoyait installer ce que l editeur a retire.
    # D ou la double contrainte : une ligne de tableau (elle commence par « | ») ET la
    # deuxieme cellule seulement. Un garde-fou qui inspecte autre chose que ce qu il
    # protege est la famille de defaut la plus repetee de ce depot.
    vus: list[str] = []
    for ligne in texte[debut:fin].splitlines():
        ligne = ligne.strip()
        if not ligne.startswith("|"):
            continue
        cellules = [c.strip() for c in ligne.strip("|").split("|")]
        if len(cellules) < 2:
            continue
        nom = cellules[1].strip("`").strip()
        if nom.startswith("bmad-") and nom not in vus:
            vus.append(nom)
    return vus


def _skills_bmad_absentes(cible: str) -> list[str]:
    """Parmi les skills routees, celles que la cible n a pas sur disque."""
    absentes = []
    for nom in _skills_bmad_routees():
        if not os.path.isdir(os.path.join(cible, ".claude", "skills", nom)):
            absentes.append(nom)
    return absentes


def installer(cible: str, nom: str, force: bool, dry_run: bool) -> int:
    manifeste = _lire_manifeste()
    fichiers = manifeste.get("fichiers", [])
    if not fichiers:
        sys.exit("MANIFESTE.json ne liste aucun fichier - export/ est vide ou corrompu.")

    cible = os.path.abspath(cible)
    prefixe = "[dry-run] " if dry_run else ""
    lignes: list[str] = []
    ecrits = conserves = manquants = 0
    # Compte a part : un REFUS de securite n est PAS un fichier absent
    # d export/. Les melanger faisait conclure « regenerer au hub », donc
    # corriger la mauvaise chose (revue de securite du 2026-09-01).
    refuses = 0

    for entree in fichiers:
        src = os.path.join(EXPORT_DIR, entree["export"].replace("/", os.sep))
        dst = os.path.join(cible, entree["destination"].replace("/", os.sep))
        # MANIFESTE.json VOYAGE AVEC LE KIT : il n'est pas forcement celui que le hub a
        # ecrit. Une destination « ../DEPOT_VOISIN/... » ou absolue sortait du
        # repertoire cible, en rapportant une ligne « ecrit » ordinaire et en sortant
        # avec 0 (audit technique du 2026-09-01). On refuse ce qui ne reste pas SOUS la
        # cible ; l'installateur n'a aucune raison legitime d'ecrire ailleurs.
        # LA SOURCE AUSSI. `destination` etait confinee, `export` ne l etait par rien :
        # un manifeste pointant `C:/Windows/win.ini` ou `../secret.txt` faisait copier
        # n importe quel fichier lisible du poste DANS le depot cible, en ligne
        # « ecrit » ordinaire et exit 0 — et la checklist demande ensuite de committer
        # l installation. Le sha256 ne referme rien ici : l empreinte vient du MEME
        # manifeste que le chemin (revue de securite du 2026-09-01).
        if not _sous_la_cible(EXPORT_DIR, src):
            lignes.append(f"REFUS   {entree['export']} : source hors du kit - "
                          f"entree ignoree")
            refuses += 1
            continue
        if not _sous_la_cible(cible, dst):
            lignes.append(f"REFUS   {entree['destination']} : destination hors du "
                          f"repertoire cible - entree ignoree")
            refuses += 1
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
                refuses += 1
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

    lignes.append(_poser_gitignore(cible, dry_run))
    lignes.append("note    runs.jsonl et arbitrages.json restent VERSIONNES "
                  "(journal et decisions, R5) : ils contiennent du texte libre "
                  "- demandes, notes - relire avant de pousser sur un remote "
                  "externe")

    gabarit = manifeste.get("settings_template", {})
    if gabarit:
        # MONTRER CE QU ON S APPRETE A EXECUTER. Les commandes de hook du gabarit sont
        # recopiees verbatim dans le settings.json de la cible, donc lancees a CHAQUE
        # session — et jusqu ici elles n etaient affichees nulle part, pas meme en
        # --dry-run, qui se contentait de « FUSION (simule) ». Le seul fichier qui
        # accorde des droits d execution etait le seul dont le contenu n etait jamais
        # montre avant ecriture (revue de securite du 2026-09-01).
        for evenement, groupes in (gabarit.get("hooks") or {}).items():
            for groupe in (groupes if isinstance(groupes, list) else []):
                for h in (groupe or {}).get("hooks", []):
                    lignes.append(f"hook    {evenement} : "
                                  f"{(h or {}).get('command', '?')}")
        for regle in (gabarit.get("permissions") or {}).get("deny", []):
            lignes.append(f"deny    {regle}")
        if dry_run:
            lignes.append("FUSION  .claude/settings.json (simule - rien ecrit)")
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
        chemin_propose = chemin_md + ".propose"
        # `.propose` lui-meme n'est pas un fichier du kit : une reinstallation qui
        # l'ecrasait sans condition ni --force a deja fait disparaitre un brouillon
        # humain en cours (« MON TRAVAIL EN COURS ») sous le squelette, mesure par
        # l'audit du 2026-09-01 -- meme defaut que CLAUDE.md deux lignes plus haut,
        # simplement reintroduit un fichier plus loin. Meme garde : n'ecrire que s'il
        # n'existe pas encore, ou sur --force explicite.
        if not os.path.exists(chemin_propose) or force:
            if not dry_run:
                with open(chemin_propose, "w", encoding="utf-8") as fh:
                    fh.write(gabarit_md.replace("{nom}", nom or os.path.basename(cible)))
            lignes.append("garde   CLAUDE.md (redige par le projet - jamais ecrase, meme "
                          "avec --force ; squelette pose en CLAUDE.md.propose)")
        else:
            lignes.append("garde   CLAUDE.md (redige par le projet) et CLAUDE.md.propose "
                          "existant (brouillon deja pose, non ecrase - --force pour le "
                          "rafraichir)")
        conserves += 1

    print(f"{prefixe}Installation du dispositif agentic dans : {cible}")
    print(f"{prefixe}Source : export/ genere le {manifeste.get('genere_le', '?')}")
    print()
    for ligne in lignes:
        print(f"  {prefixe}{ligne}")
    print()
    print(f"{prefixe}{ecrits} ecrit(s), {conserves} conserve(s), "
          f"{manquants} absent(s), {refuses} refus(es)")

    if refuses:
        print("\nATTENTION : des entrees du manifeste ont ete REFUSEES (source ou")
        print("destination hors perimetre, ou empreinte non conforme). Ce n est PAS un")
        print("defaut d empaquetage : relire le manifeste avant de le croire.")
    if manquants:
        print("\nATTENTION : des fichiers du manifeste manquent dans export/ -")
        print("regenerer au hub avec  py .claude/dispositif/export_agentic.py")

    # LE RACCORD BMAD. La skill d orchestration qu on vient d installer route des skills
    # BMAD par besoin detecte ; BMAD, lui, ne fait pas partie du kit. On le DIT plutot
    # que de laisser la table designer des skills absentes. Volontairement hors du code
    # de sortie : ce n est pas un defaut d installation, c est un etat de la cible.
    absentes = _skills_bmad_absentes(cible)
    if absentes:
        print(f"\nATTENTION : la table de routage du kit designe {len(absentes)} "
              "skill(s) BMAD que ce depot n a pas :")
        for nom in absentes:
            print(f"  - {nom}")
        print("Le routage les nommera sans qu elles existent. BMAD s installe par son")
        print("propre installateur (bmad-method) - le kit ne les embarque pas.")

    if not dry_run:
        print("\n--- Checklist apres installation (rien de ceci n'est automatique) ---")
        for i, etape in enumerate(manifeste.get("checklist", []), 1):
            print(f"  {i}. {etape}")

    # `_fusionner_settings` peut rendre une ligne "ECHEC ..." (settings.json illisible,
    # de forme inattendue) SANS lever : l'echec vivait dans `lignes`, jamais dans le
    # code de sortie -- un playbook ou une CI qui ne lit que le retour concluait
    # « installe » sur une cible ou AUCUN hook du dispositif n'a ete pose (audit du
    # 2026-09-01). Un settings.json non fusionne est aussi grave qu'un fichier manquant.
    echecs_settings = sum(1 for l in lignes if l.startswith("ECHEC"))
    return 1 if (manquants or refuses or echecs_settings) else 0


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
