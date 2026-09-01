"""Synchronise le dispositif de supervision partagé de la flotte depuis un canon unique.

Problème résolu (dette « risque_technique : critique » de VScode5, audit 2026-07-23) :
`scan_transcripts.py` et `log_run.py` existaient en 6 copies maintenues à la main, qui
avaient DIVERGÉ — chaque projet portait une amélioration que les autres n'avaient pas
(VSCode1 : détection des skills consommées par lecture ; VSCode3 : arbitrage par
catégorie). Un correctif devait être propagé 6 fois à la main (vécu 2 fois le 2026-07-23).

Mécanisme : une source de vérité unique dans `.claude/dispositif/canon/` (ce hub), et ce
script la propage à chaque projet de `projets.json`. Chaque copie déployée porte un en-tête
« généré — ne pas éditer localement ». Toute correction se fait DANS le canon, puis
`py .claude/dispositif/sync_dispositif.py` re-synchronise la flotte.

Usage :
  py .claude/dispositif/sync_dispositif.py            # applique le canon à toute la flotte
  py .claude/dispositif/sync_dispositif.py --check     # n'écrit rien : signale les dérives (exit 1 si dérive)
  py .claude/dispositif/sync_dispositif.py --projet VSCode2   # limite à un projet
"""

from __future__ import annotations

import json
import os
import sys

DISPOSITIF_DIR = os.path.dirname(os.path.abspath(__file__))
CANON_DIR = os.path.join(DISPOSITIF_DIR, "canon")
ROOT = os.path.dirname(os.path.dirname(DISPOSITIF_DIR))  # .../dispositif -> .claude -> hub
CONFIG_PATH = os.path.join(ROOT, "projets.json")

# canon (nom de fichier) -> chemin relatif de destination dans chaque projet cible
MAPPING = {
    "scan_transcripts.py": os.path.join(".claude", "supervision", "scan_transcripts.py"),
    "log_run.py": os.path.join(".claude", "orchestration", "log_run.py"),
}

# Le bandeau est lu DEPUIS LA CIBLE, où `sync_dispositif.py` n'existe pas : il n'est
# pas propagé (outil du hub). Une consigne qui nomme un script absent est
# inapplicable là où on la lit — signalé par la session VSCode3 le 2026-09-01, et
# vérifié : `.claude/dispositif/sync_dispositif.py` est bien absent des 5 dépôts.
# Le bandeau dit donc au lecteur de la CIBLE ce qu'il peut faire (remonter au hub),
# et garde la commande exacte pour celui qui lit depuis le hub.
HEADER_LINES = [
    "# +-- GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT ---------------------------------------",
    "# | Source de vérité : hub de supervision VScode5, .claude/dispositif/canon/{nom}",
    "# | Une correction faite ICI sera ÉCRASÉE à la prochaine propagation. Pour la",
    "# | garder : la signaler au hub, qui corrige le canon et re-synchronise.",
    "# | (Depuis le hub : « py .claude/dispositif/sync_dispositif.py » — ce script",
    "# |  n'est pas déployé, il n'existe pas dans ce dépôt.)",
    "# +---------------------------------------------------------------------------",
    "",
]


def read_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)["projets"]


def read_lf(path):
    """Lit un fichier en normalisant les fins de ligne en \\n (comparaison stable)."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def strip_header(text):
    """Retire un en-tête « généré » déjà présent, pour comparer le corps réel."""
    marker = "# +-- GÉNÉRÉ — NE PAS ÉDITER LOCALEMENT"
    if text.startswith(marker):
        end = text.find("# +---------------------------------------------------------------------------")
        if end != -1:
            nl = text.find("\n", end)
            rest = text[nl + 1:]
            # sauter la ligne vide qui suit l'en-tête
            return rest[1:] if rest.startswith("\n") else rest
    return text


def build_content(nom_canon):
    """Corps attendu (en-tête + canon), en \\n."""
    body = read_lf(os.path.join(CANON_DIR, nom_canon))
    header = "\n".join(line.format(nom=nom_canon) for line in HEADER_LINES)
    return header + "\n" + body


def write_crlf(path, text_lf):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text_lf.replace("\n", "\r\n").encode("utf-8"))


def suites_cibles(chemin):
    """Fichiers de test de la cible qui exercent un script du canon.

    Le canon synchronise les SCRIPTS, jamais les tests : chaque projet garde ses
    copies locales, qui peuvent asserter sur un comportement que le canon vient
    de changer. Un sync « 12/12 à jour » ne dit donc rien de leur santé — d'où
    ce rappel (incident sync-canon 2026-07-29 : le commit 5eb121b a cassé
    tests/test_agent_orchestration.py de VSCode2, découvert par le diagnostic
    local et non par le sync)."""
    tests_dir = os.path.join(chemin, "tests")
    if not os.path.isdir(tests_dir):
        return []
    noms = [os.path.splitext(n)[0] for n in MAPPING]  # scan_transcripts, log_run…
    trouves = []
    for fichier in sorted(os.listdir(tests_dir)):
        if not (fichier.startswith("test_") and fichier.endswith(".py")):
            continue
        try:
            with open(os.path.join(tests_dir, fichier), encoding="utf-8",
                      errors="ignore") as fh:
                contenu = fh.read()
        except OSError:
            continue
        if any(n in contenu for n in noms):
            trouves.append(f"tests/{fichier}")
    return trouves


def rappel_suites_cibles(projets, projet_filtre=None):
    """Affiche, après un sync qui a écrit, les suites à rejouer par cible."""
    lignes = []
    for p in projets:
        if projet_filtre and p["nom"] != projet_filtre:
            continue
        suites = suites_cibles(p["chemin"])
        if suites:
            lignes.append(f"  {p['nom']:10} : py -m pytest {' '.join(suites)} -q")
    if not lignes:
        return
    print("\nSuites à REJOUER sur les cibles (les tests locaux ne sont pas "
          "synchronisés par le canon — un sync vert ne les couvre pas) :")
    for ligne in lignes:
        print(ligne)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check_only = "--check" in argv or "--dry-run" in argv
    # Le script distinguait déjà « dérive (en-tête) » de « DÉRIVE (corps) »… pour les
    # AFFICHER, puis écrasait les deux pareil. Or une dérive de corps, c'est le script
    # canonique MODIFIÉ chez la cible : du travail humain, qui partait sans
    # confirmation, sans diff et sans sauvegarde (audit du 2026-09-01).
    # Le mode par défaut reste l'écriture — le bandeau propagé dans les 6 copies
    # documente `py .claude/dispositif/sync_dispositif.py` sans option, en faire un
    # no-op casserait la consigne que lisent les cibles. C'est la seule écriture
    # destructrice qui est refusée, franchissable explicitement, comme le
    # `--accepter-pertes` de `propager_socle.py`.
    accepter_derive = "--accepter-derive" in argv
    projet_filtre = None
    if "--projet" in argv:
        i = argv.index("--projet")
        if i + 1 < len(argv):
            projet_filtre = argv[i + 1]

    manquants = [n for n in MAPPING if not os.path.isfile(os.path.join(CANON_DIR, n))]
    if manquants:
        print(f"canon introuvable : {manquants}", file=sys.stderr)
        return 2

    projets = read_config()
    attendu = {n: build_content(n) for n in MAPPING}
    n_ecrits = n_ajour = n_derive = n_absents = n_refus = 0

    for p in projets:
        nom, chemin = p["nom"], p["chemin"]
        if projet_filtre and nom != projet_filtre:
            continue
        if not os.path.isdir(chemin):
            print(f"  {nom:10} : projet introuvable ({chemin}) — ignoré")
            continue
        for nom_canon, rel in MAPPING.items():
            dest = os.path.join(chemin, rel)
            exp = attendu[nom_canon]
            if os.path.isfile(dest):
                actuel = read_lf(dest)
                if actuel == exp:
                    n_ajour += 1
                    etat = "à jour"
                else:
                    corps_actuel = strip_header(actuel)
                    corps_exp = strip_header(exp)
                    etat = "DÉRIVE (corps)" if corps_actuel != corps_exp else "dérive (en-tête)"
                    n_derive += 1
            else:
                etat = "ABSENT"
                n_absents += 1
                actuel = None

            if not check_only and etat != "à jour":
                if etat.startswith("DÉRIVE (corps)") and not accepter_derive:
                    etat += (" -> REFUS : le script a été modifié ici. Relire le diff, "
                             "remonter le correctif au canon du hub, ou forcer avec "
                             "--accepter-derive")
                    n_refus += 1
                else:
                    write_crlf(dest, exp)
                    n_ecrits += 1
                    etat += " -> écrit"
            if etat != "à jour":
                print(f"  {nom:10} {nom_canon:22} : {etat}")

    action = "vérification" if check_only else "synchronisation"
    print(f"{action} : {n_ajour} à jour, {n_derive} dérive(s), {n_absents} absent(s)"
          + (f", {n_ecrits} écrit(s)" if not check_only else "")
          + (f", {n_refus} REFUS (dérive de corps préservée)" if n_refus else ""))
    if n_ecrits:
        rappel_suites_cibles(projets, projet_filtre)
    if check_only and (n_derive or n_absents):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
