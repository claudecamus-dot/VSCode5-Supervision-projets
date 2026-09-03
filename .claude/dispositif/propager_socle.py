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
import re
import subprocess

DISPOSITIF = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(DISPOSITIF))
SOCLE_SRC = os.path.join(HUB, "export", "skills", "agent-orchestrator", "SKILL.md")
REL_CIBLE = os.path.join(".claude", "skills", "agent-orchestrator", "SKILL.md")

TITRE_LOCAL = "## Portée sur ce projet"
MARQUEUR_PROVENANCE = "<!-- SOCLE-PROVENANCE:"
# L'ancre qui separe le socle genere du chapitre local. Elle vivait en litteral recopie
# dans trois fichiers (ici, `export_agentic.ANCRE_SOCLE`, et la constante du test) sans
# rien qui les lie : renommer le titre de section dans la skill aurait casse la coupe
# en silence, sur les 5 cibles a la fois (audit du 2026-09-01).
# `tests/test_propager_socle.py::TestLAncreEstLaMemePartout` verrouille leur egalite.
ANCRE_SOCLE = "## Méthode — 5 étapes"


def projets() -> list[tuple[str, str]]:
    chemin = os.path.join(HUB, "projets.json")
    with io.open(chemin, encoding="utf-8") as fh:
        data = json.load(fh)
    return [(p["nom"], p["chemin"]) for p in data.get("projets", [])
            if p.get("nom") and p.get("chemin") and os.path.abspath(p["chemin"]) != HUB]


REL_SOCLE_GIT = "export/skills/agent-orchestrator/SKILL.md"


def socle_d_origine(texte_cible: str) -> str | None:
    """Le socle DEPUIS LEQUEL cette copie a été composée, retrouvé par le hash que sa
    propre ligne de provenance porte (`<!-- SOCLE-PROVENANCE: socle : <hash> du … -->`).

    C'est la donnée qui manquait, et sans laquelle le garde-fou ne peut PAS faire son
    travail. Une copie cible vaut `ancien_socle + provenance + chapitre` : « présent
    avant, absent après » y mélange donc deux choses opposées — une phrase que le hub a
    reformulée (légitime, il en est propriétaire) et une ligne locale qui disparaît
    (le défaut à attraper). Les distinguer demande de savoir ce que l'ancien socle
    disait ; le reste n'est que deviner.

    Mesuré le 2026-09-01 : sans cette lecture, réécrire UNE ligne du socle du hub
    faisait passer les 5 cibles en `PERTE-LOCALE`, la ligne « perdue » étant une phrase
    du hub — le garde-fou bloquait la propagation qu'il est censé protéger.

    Rend None si la provenance manque ou si git ne retrouve pas la révision : l'appelant
    dégrade alors vers la comparaison du seul chapitre, et le dit.
    """
    m = re.search(re.escape(MARQUEUR_PROVENANCE) + r" socle : ([0-9a-f]{7,40}) ",
                  texte_cible)
    if not m:
        return None
    try:
        r = subprocess.run(["git", "-C", HUB, "show", f"{m.group(1)}:{REL_SOCLE_GIT}"],
                           capture_output=True, timeout=20)
        return r.stdout.decode("utf-8") if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None


def hash_hub() -> str:
    """Hash court du hub — la génération dont descend le socle propagé."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HUB,
                             capture_output=True, text=True, encoding="utf-8",
                             timeout=15)
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
    bornes = _bornes_chapitre(texte)
    if bornes is None:
        return None
    debut, fin = bornes
    return texte[debut:fin].rstrip() + "\n"


def _bornes_chapitre(texte: str) -> tuple[int, int] | None:
    """Indices (début, fin) du chapitre local, ou None s'il n'y en a pas.

    Une seule découpe, partagée par `extraire_chapitre_local` (ce qu'on garde) et
    `hors_chapitre` (ce que la propagation reconstruit) : deux règles de découpe
    divergentes rouvriraient le trou qu'on ferme.
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
    return (i, i + fin)


def hors_chapitre(texte: str) -> str:
    """Le texte PRIVÉ de son chapitre local.

    C'est la part que `composer()` reconstruit intégralement depuis le socle du hub —
    donc la seule où une ligne locale peut disparaître sans que personne la réclame.
    """
    bornes = _bornes_chapitre(texte)
    if bornes is None:
        return texte
    debut, fin = bornes
    return texte[:debut] + texte[fin:]


def composer(socle: str, chapitre_local: str, provenance: str) -> str:
    """Socle généré + provenance + chapitre local, dans l'ordre de VSCode1.

    Le chapitre local se place APRÈS l'introduction et AVANT « ## Méthode » : c'est
    la place qu'il occupe déjà dans VSCode1, la seule copie qui avait résolu le
    problème avant nous. Un lecteur qui ouvre le fichier voit donc ce qui est propre
    à SON projet avant la méthode générique.
    """
    ancre = ANCRE_SOCLE
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


def lignes_perdues(avant: str, apres: str, socle: str,
                   socle_origine: str | None = None) -> list[str]:
    """Lignes présentes AVANT, absentes APRÈS, et introuvables dans le socle.

    Le garde-fou qui manquait. La première propagation (2026-09-01) a vérifié que le
    chapitre local EXISTAIT — pas qu'il était COMPLET. Résultat : les chapitres ont
    gardé les idées et perdu l'opérationnel. Sur VSCode2, le paramètre
    `--retrait-citation-mm 3.53`, explicitement marqué « arbitré et conservé », a
    disparu ; sans lui `pdf_verify.py` signale à tort un bord gauche multiple, donc la
    session suivante aurait chassé un faux défaut bloquant sur un PDF correct. Les
    quatre autres dépôts avaient perdu des lignes du même genre : commandes exactes,
    lignes de table de vérification, pointeurs de doc de conception.

    « Le chapitre existe » n'est pas « rien n'a disparu ». Une ligne qui n'est ni dans
    l'après ni dans le socle n'est attribuable à personne : elle est perdue.
    """
    def bruit(l: str) -> bool:
        """La ligne de provenance elle-même change à chaque propagation (le hash et la
        date bougent). La compter comme perdue rendrait le garde-fou bruyant à chaque
        passage, et un garde-fou qui crie toujours ne se lit plus."""
        return (MARQUEUR_PROVENANCE in l
                or l.startswith("> **Socle généré**")
                or l.startswith("> Le chapitre « Portée sur ce projet »"))

    def util(t):
        return {l.strip() for l in t.splitlines() if l.strip() and not bruit(l.strip())}

    # Une fois la coupe faite, le seul texte que la propagation doit garantir est le
    # CHAPITRE LOCAL — le reste est du socle, dont le hub est propriétaire et qu'il a
    # le droit de reformuler. Comparer les fichiers ENTIERS faisait donc remonter en
    # « perte » toute phrase du socle réécrite au hub : mesuré le 2026-09-01, deux
    # reformulations de références hub-centriques ont bloqué la propagation sur les
    # cinq cibles. Un garde-fou qui crie au loup sur le travail légitime finit
    # désarmé — c'est exactement le défaut qu'on venait de corriger sur le hook
    # pré-commit. On compare donc chapitre à chapitre dès qu'il y en a un des deux
    # côtés, et fichier entier seulement lors de la toute première migration.
    # DEUX comparaisons, et il fallait les deux (défaut trouvé par l'audit technique
    # du 2026-09-01, corrigé le jour même) :
    #
    # 1. chapitre à chapitre — invariant de structure. `composer()` recolle le
    #    chapitre VERBATIM, donc cette différence est vide par construction ; elle ne
    #    coûte rien et crierait si `composer()` cessait un jour de le faire.
    # 2. HORS chapitre — le trou réel. C'est la part que `composer()` reconstruit
    #    depuis le socle du hub, donc celle où une ligne locale tissée dans
    #    l'introduction ou dans une section du socle disparaît sans être réclamée.
    #    C'est exactement ce qui a coûté le `--retrait-citation-mm 3.53` de VSCode2.
    #
    # La version précédente ne faisait que la (1). Le garde-fou ne pouvait donc PAS se
    # déclencher depuis `traiter()` — vérifié sur les 5 copies réelles, `perdues=0`
    # partout — et la branche fichier-entier ci-dessous était morte, `traiter()`
    # sortant avant quand le chapitre manque. Il protégeait la seule chose qui ne
    # risquait rien.
    #
    # Le `- util(socle)` de la (2) garde ce que la version fichier-entier avait de
    # juste : une phrase du socle réécrite au hub n'est pas une perte locale. Mesuré
    # le 2026-09-01 avant d'écrire : 0 ligne signalée sur les 5 dépôts — la correction
    # ne re-bloque pas la propagation qu'elle protège.
    # `socle_origine` ferme la régression que la première version de cette correction a
    # introduite (trouvée par la re-cotation d'audit du 2026-09-01, quelques heures
    # après) : la copie cible vaut `ancien_socle + provenance + chapitre`, donc
    # « présent avant, absent après » contenait TOUTE phrase que le hub avait
    # reformulée entre-temps. Reproduit : réécrire UNE ligne du socle faisait passer
    # les 5 cibles en PERTE-LOCALE, la ligne « perdue » étant une phrase du hub.
    # Un garde-fou muet et un garde-fou qui crie à tort sont le même défaut vu des deux
    # côtés — et c'est ce fichier qui l'a appris deux fois dans la même journée.
    # Retirer AUSSI l'ancien socle : ce qu'il contenait appartient au hub, jamais au
    # local. Ce qui survit aux deux soustractions n'est dans aucun socle, donc local.
    chap_avant, chap_apres = extraire_chapitre_local(avant), extraire_chapitre_local(apres)
    if chap_avant is not None and chap_apres is not None:
        perdues = util(chap_avant) - util(chap_apres)
        hors = util(hors_chapitre(avant)) - util(hors_chapitre(apres)) - util(socle)
        if socle_origine is not None:
            hors -= util(socle_origine)
        perdues |= hors
        return sorted(perdues)
    return sorted(util(avant) - util(apres) - util(socle))


def _cible_sale(racine: str) -> str | None:
    """La copie de la cible porte-t-elle du travail non commite ?

    R2 dit de ne jamais ecraser du travail non commite qui n est pas le notre. Ce
    chemin est le SEUL de ce depot qui ecrive dans le dossier d autrui, et rien ne
    l en empechait : une session pair editant sa propre copie de la skill la voyait
    remplacee sans avertissement (finding du 2026-09-01, trouve par
    bmad-review-edge-case-hunter).

    Rend la raison si sale, None si propre OU si le dossier n est pas un depot git
    (rien a preserver de git alors). Le `returncode` est lu EXPLICITEMENT : lire le
    seul `stdout` confond « propre » et « la commande a echoue » — c est le defaut
    releve le meme jour dans `_socle_non_commite`.
    """
    try:
        # `encoding` explicite : `text=True` seul decode avec l encodage LOCAL
        # (cp1252 ici), et un nom de fichier accente rendrait la sortie fausse.
        out = subprocess.run(["git", "status", "--porcelain", "--", REL_CIBLE],
                             cwd=racine, capture_output=True, text=True,
                             encoding="utf-8", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    sale = [l for l in out.stdout.splitlines() if l.strip()]
    if not sale:
        return None
    return f"copie modifiee et non commitee chez la cible ({sale[0].strip()})"


def traiter(nom: str, racine: str, socle: str, provenance: str, appliquer: bool,
            tolerer_pertes: bool = False) -> dict:
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
    origine = socle_d_origine(actuel)
    perdues = lignes_perdues(actuel, nouveau, socle, socle_origine=origine)
    if perdues and not tolerer_pertes:
        return {"projet": nom, "etat": "PERTE-LOCALE", "perdues": perdues,
                "detail": (f"{len(perdues)} ligne(s) disparaîtraient sans être dans le "
                           f"socle — refus d'écrire (--accepter-pertes pour forcer)")}
    if nouveau == actuel:
        return {"projet": nom, "etat": "a-jour", "detail": f"{len(local.splitlines())} l. locales"}
    # R2 : la copie de la cible peut porter le travail non commite d une autre session.
    sale = _cible_sale(racine)
    if sale:
        return {"projet": nom, "etat": "CIBLE-SALE", "detail":
                sale + " - refus d ecraser (committer chez la cible d abord)"}
    if appliquer:
        io.open(cible, "w", encoding="utf-8", newline="\n").write(nouveau)
    # `perdues` ne vivait que dans le retour de REFUS : avec --accepter-pertes,
    # main() imprimait une liste vide pendant que des lignes disparaissaient, et le
    # detail annoncait « chapitre local preserve » juste apres l avoir ampute. Un
    # drapeau qui existe pour ASSUMER une perte doit d abord la MONTRER.
    etat_local = (f"chapitre local de {len(local.splitlines())} l. préservé"
                  if not perdues else
                  f"{len(perdues)} ligne(s) locales PERDUES, tolérées par "
                  "--accepter-pertes")
    return {"projet": nom, "etat": "applique" if appliquer else "a-propager",
            "perdues": perdues,
            # Le docstring de socle_d_origine promet qu il « le dit » quand il
            # ne resout pas ; il degradait en silence, et l appelant ne pouvait
            # pas savoir que la distinction hub/local s etait faite a l aveugle.
            "provenance": "resolue" if origine is not None else "irresolvable",
            "detail": (f"{len(actuel.splitlines())} l. -> {len(nouveau.splitlines())} l., "
                       + etat_local)}


SOCLE_VIVANT = os.path.join(HUB, ".claude", "skills", "agent-orchestrator", "SKILL.md")


def _socle_perime() -> str | None:
    """Le socle publie dans export/ est-il en retard sur la source vivante du hub ?

    Rend la raison (une phrase) si oui, None si le socle est frais. Fail-open sur une
    source illisible : on ne bloque pas une propagation pour un fichier qu'on n'a pas
    su lire, on la bloque quand on a la PREUVE que le socle est perime.
    """
    try:
        publie = io.open(SOCLE_SRC, encoding="utf-8").read()
        vivant = io.open(SOCLE_VIVANT, encoding="utf-8").read()
    except OSError:
        return None
    if publie == vivant:
        return None
    return (f"{os.path.relpath(SOCLE_SRC, HUB)} differe de la source vivante "
            f"{os.path.relpath(SOCLE_VIVANT, HUB)} "
            f"({len(publie.splitlines())} l. publiees / {len(vivant.splitlines())} l. au hub)")


def _socle_non_commite() -> str | None:
    """Le socle qu on s apprete a copier est-il bien celui que la provenance dira ?

    Rend la raison si non, None si oui. `hash_hub()` estampille HEAD, mais le socle
    reellement copie est lu dans l ARBRE DE TRAVAIL : propager sur un socle non
    commite inscrit chez les 5 cibles une provenance qui designe une revision ou ce
    socle n a jamais existe (mesure le 2026-09-01 : les 5 depots portaient 604fc7c en
    contenant un paragraphe entre dans l histoire en 0f4e632 seulement).

    LA PREMIERE VERSION LISAIT `git status --porcelain` ET SEULEMENT SON `stdout`.
    Trois trous, tous de la meme famille — la sonde ne mesurait pas ce qu elle disait
    (finding du diagnostic etage 2 du meme soir) :

    1. hors depot git, `rc=128` et stdout vide : elle repondait « propre », alors que
       `hash_hub()` rend « inconnu », qui n est pas une revision ;
    2. sous `git update-index --assume-unchanged`, `status` reste vide alors que le
       fichier differe du blob : elle laissait passer le cas meme qu elle vise ;
    3. sous `core.autocrlf=true` — la config REELLE de ce depot — un fichier de
       travail en CRLF pouvait la faire crier alors que son texte EST le blob, et le
       remede qu elle imprime sort « nothing to commit ». Un refus non levable est
       pire qu un trou : on ne peut pas en sortir.

    On ne raffine donc pas la lecture de `status`, on CHANGE D ORACLE : comparer le
    CONTENU au blob HEAD. C est la seule question qui compte — « ce que je vais copier
    est-il ce que la provenance dira qu il est ? » — et elle est insensible aux trois.
    Le `returncode` est lu explicitement ; les fins de ligne sont normalisees des deux
    cotes, parce qu un CRLF ne change pas le TEXTE dont la provenance repond.

    Git INJOIGNABLE bloque, lui : `hash_hub()` rend alors « inconnu » et la ligne
    de provenance designerait litteralement rien, chez cinq tiers, pour toute la
    duree de vie des copies. Ne pas propager coute une commande. C est la
    difference avec `_socle_perime`, qui compare deux fichiers du disque et peut
    s abstenir sans consequence : celle-ci decide s il est licite d ECRIRE une
    affirmation ailleurs. Seul un fichier illisible reste fail-open.
    """
    h = hash_hub()
    if not re.fullmatch("[0-9a-f]{7,40}", h or ""):
        return (f"hash_hub() rend {h!r}, qui n est pas une revision git : la ligne "
                "de provenance ne designerait rien")
    try:
        # `encoding="utf-8"` OBLIGATOIRE, et son absence a produit la 6e occurrence
        # de la famille : `text=True` seul decode avec l encodage LOCAL (cp1252 sur
        # ce poste), donc le blob revenait mutile des sa 87e position et la
        # comparaison ne pouvait JAMAIS aboutir. La porte refusait toute
        # propagation, definitivement, avec « differe du blob HEAD » alors que
        # git status disait propre et que les deux textes faisaient 49 262
        # caracteres identiques. Mesure : 400 lignes accentuees dans le socle,
        # 0 survit au decodage cp1252.
        out = subprocess.run(["git", "show", "HEAD:" + REL_SOCLE_GIT],
                             cwd=HUB, capture_output=True, text=True,
                             encoding="utf-8", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return (f"git ne rend pas {REL_SOCLE_GIT} a HEAD (code {out.returncode}) : "
                "impossible d etablir ce que la provenance designerait")
    try:
        vivant = io.open(SOCLE_SRC, encoding="utf-8").read()
    except OSError:
        return None

    def _lf(t: str) -> str:
        return t.replace("\r\n", "\n").replace("\r", "\n")

    if _lf(vivant) == _lf(out.stdout):
        return None
    return (f"{REL_SOCLE_GIT} differe du blob HEAD ({h}) : le socle qui serait copie "
            "n est pas celui que la provenance designerait")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Propage le socle agent-orchestrator vers la flotte.")
    p.add_argument("--appliquer", action="store_true", help="écrit vraiment (défaut : dry-run)")
    p.add_argument("--dry-run", action="store_true", help="montre sans écrire (défaut)")
    p.add_argument("--projet", help="limiter à un projet")
    p.add_argument("--accepter-pertes", action="store_true",
                   help="écrire malgré des lignes locales qui disparaîtraient (à n'utiliser "
                        "qu'après avoir LU la liste : c'est du travail humain qui part)")
    args = p.parse_args(argv)
    appliquer = args.appliquer and not args.dry_run

    if not os.path.isfile(SOCLE_SRC):
        print("socle introuvable : regenerer export/ d'abord")
        return 1
    # Le socle est lu dans export/, un ARTEFACT GENERE : seule son existence etait
    # testee. Mesure le 2026-09-01 a 15:20 — `export_agentic.py --check` rendait
    # « 47/48, 1 derive », exit 1, pendant que `propager_socle.py --dry-run` annoncait
    # 5 x « a-propager », exit 0, sans un mot : on s'appretait a propager aux 5 cibles
    # une version PERIMEE de la skill. Un artefact genere ne se fait pas confiance sur
    # sa seule presence.
    # BLOQUANT SANS EXCEPTION, et surtout PAS derriere `--accepter-pertes` : ce drapeau
    # parle des lignes LOCALES qui disparaissent (un arbitrage humain sur le contenu de
    # la cible), pas de la fraicheur du socle. Les avoir confondus faisait qu'un
    # utilisateur forcant une perte locale assumee desactivait au passage, sans en etre
    # averti, un controle qu'il n'avait pas eu l'intention de lever (re-cotation d'audit
    # du 2026-09-01). Lever la fraicheur coute 5 depots faux ; la reparer coute une
    # commande — il n'y a donc pas d'arbitrage a offrir.
    perime = _socle_perime()
    if perime:
        print(f"socle PERIME : {perime}\n"
              "  regenerer d'abord : py .claude/dispositif/export_agentic.py\n"
              "  (aucune option ne leve ce refus : propager un socle non regenere\n"
              "   ecrirait une version perimee de la skill dans les 5 depots)")
        return 1
    # Sans exception, et AVANT `ligne_provenance` : une provenance calculee puis
    # jetee laisserait la porte ouverte a un appelant qui la lirait plus tot.
    non_commite = _socle_non_commite()
    if non_commite:
        print(
            f"socle NON COMMITE : {non_commite}" + "\n"
            "  committer d abord au hub : git commit -- " + REL_SOCLE_GIT + "\n"
            "  (aucune option ne leve ce refus : la ligne de provenance affirme\n"
            "   << cette copie = le hub a la revision X >>, affirmation fausse par\n"
            "   construction sur un arbre sale -- et c est elle qui permettra a la\n"
            "   propagation SUIVANTE de distinguer une perte locale d une phrase\n"
            "   que le hub a simplement reformulee)")
        return 1
    socle = io.open(SOCLE_SRC, encoding="utf-8").read()
    prov = ligne_provenance(hash_hub(), dt.date.today().isoformat())

    cibles = [(n, c) for n, c in projets() if not args.projet or n == args.projet]
    if not cibles:
        print("aucune cible")
        return 1

    # Une seule cible illisible (encodage cp1252) faisait remonter l exception hors
    # de main() APRES avoir deja reecrit les depots precedents et sans jamais
    # atteindre les suivants : une propagation a moitie faite dont personne n avait
    # la liste.
    resultats = []
    for n, c in cibles:
        try:
            resultats.append(traiter(n, c, socle, prov, appliquer, args.accepter_pertes))
        except Exception as exc:  # noqa: BLE001 - on veut TOUTES les cibles
            resultats.append({"projet": n, "etat": "ILLISIBLE",
                              "detail": f"{type(exc).__name__}: {exc}"})
    for r in resultats:
        print(f"  {r['etat']:<20} {r['projet']:<9} {r['detail']}")
        for ligne in r.get("perdues", [])[:40]:
            print(f"      PERDUE  {ligne[:120]}")
    # "absent" manquait a cette liste (audit du 2026-09-01) : une cible declaree sans
    # AUCUNE copie installee rendait 0, alors que le commentaire juste en dessous pose
    # que le code non nul dit « la propagation n'est pas complete » -- ce qui est
    # exactement le cas d'une cible jamais installee.
    bloques = [r for r in resultats
               if r["etat"] in ("sans-chapitre-local", "PERTE-LOCALE",
                                "CIBLE-SALE", "ILLISIBLE", "absent")]
    print(f"\n{len(resultats)} cible(s) — mode {'ECRITURE' if appliquer else 'dry-run'}")
    sans_chapitre = [r["projet"] for r in resultats if r["etat"] == "sans-chapitre-local"]
    pertes = [r["projet"] for r in resultats if r["etat"] == "PERTE-LOCALE"]
    # Un seul message pour deux causes envoyait le lecteur creer un chapitre qui
    # existe deja (constate le 2026-09-01 sur les 5 cibles en PERTE-LOCALE).
    if sans_chapitre:
        print("REFUS d'ecraser " + ", ".join(sans_chapitre) +
              " : creer leur chapitre « Portee sur ce projet » a la main d'abord.")
    for etat, phrase in (("CIBLE-SALE", "leur copie porte du travail non commite"),
                         ("ILLISIBLE", "leur copie n a pas pu etre lue")):
        noms = [r["projet"] for r in resultats if r["etat"] == etat]
        if noms:
            print("REFUS d ecraser " + ", ".join(noms) + " : " + phrase + ".")
    if pertes:
        print("REFUS d'ecraser " + ", ".join(pertes) +
              " : des lignes de leur chapitre disparaitraient sans etre dans le socle"
              " — les relire ci-dessus, puis --accepter-pertes si la perte est arbitree.")
    # Un script qui REFUSE d'ecrire et sort 0 ment a son appelant : « rien fait » et
    # « tout applique » etaient indistinguables, y compris quand les cinq cibles
    # etaient bloquees (audit du 2026-09-01). Le code non nul ne dit pas « erreur »,
    # il dit « la propagation n'est PAS complete » — ce qui est exactement le cas.
    return 1 if bloques else 0


if __name__ == "__main__":
    raise SystemExit(main())
