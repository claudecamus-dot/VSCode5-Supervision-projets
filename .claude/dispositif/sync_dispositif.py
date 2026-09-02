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

import datetime as dt
import json
import os
import re
import subprocess
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
    "# | Provenance canon : {hash} du {date} — permet, au prochain sync, de dire si",
    "# | une différence vient d'une édition locale ou d'une avance du canon (voir",
    "# | `determiner_cause` dans sync_dispositif.py au hub).",
    "# +---------------------------------------------------------------------------",
    "",
]

# Une copie ne porte cette ligne que si `sync_dispositif.py` l'a écrite APRÈS ce
# correctif — les copies antérieures n'ont pas de provenance, `determiner_cause`
# le dégrade en cause indéterminée plutôt que d'inventer une réponse.
_RE_PROVENANCE = re.compile(r"# \| Provenance canon : ([0-9a-f]{7,40}) du")


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


CANON_GIT = ".claude/dispositif/canon"


def hash_hub() -> str:
    """Hash court du DERNIER COMMIT QUI A TOUCHÉ LE CANON — la révision que la ligne
    de provenance embarque.

    Pas `HEAD` : jusqu'au 2026-09-02 c'était HEAD, et la revue de fin de séance a
    reproduit ce que ça produisait. Le sync tourne AVANT le commit qui contient le
    canon (c'est l'ordre normal) : les 6 copies portaient donc `97c2183`, une révision
    dont le canon différait de 73 lignes de ce qu'elles avaient reçu — et
    `determiner_cause`, en comparant à ce canon-là, répondait « cible-divergee » sur la
    copie du hub lui-même, corps byte-à-byte identique au canon. Le mécanisme arbitré
    le matin même pour ne plus accuser la cible à tort l'accusait par construction.
    Second effet : chaque commit du hub faisait dériver les 12 en-têtes, un signal
    constant, donc muet.

    `git log -1 -- <canon>` désigne exactement la révision dont le corps est copié —
    à condition que le canon soit commité, ce que `_canon_non_commite` garantit.
    Une provenance qui ne désigne aucune révision est marquée « inconnu » plutôt que
    de mentir."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%h", "--", CANON_GIT],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=15)
        return out.stdout.strip() or "inconnu"
    except (OSError, subprocess.SubprocessError):
        return "inconnu"


def _canon_non_commite():
    """Les fichiers du canon modifiés ou non suivis, ou [] si le canon est propre.

    Même garde que `propager_socle._socle_non_commite`, pour la même raison : la ligne
    de provenance affirme « cette copie = le canon à la révision X » ; sur un canon
    sale, cette affirmation est fausse par construction et c'est elle qui permettra
    au sync SUIVANT de distinguer une divergence locale d'un canon qui a avancé.
    Fail-open sur git injoignable : on ne bloque pas une propagation sur un doute."""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", CANON_GIT],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    return [l[3:].strip() for l in out.stdout.splitlines() if l.strip()]


def canon_a_revision(nom_canon, hash_court):
    """Le corps du fichier canon `nom_canon` TEL QU'IL ÉTAIT à la révision
    `hash_court` du hub — sur le modèle exact de `propager_socle.socle_d_origine`,
    qui répond à la même question pour le socle agent-orchestrator : retrouver un
    ancien contenu par le hash que la copie porte dans sa propre ligne de
    provenance, via `git show <hash>:<chemin>`.

    Rend None si le hash est invalide, absent de l'histoire, ou git injoignable :
    l'appelant (`determiner_cause`) dégrade alors vers une cause indéterminée
    plutôt que d'accuser à tort l'une des deux parties.
    """
    if not re.fullmatch("[0-9a-f]{7,40}", hash_court or ""):
        return None
    chemin_git = f".claude/dispositif/canon/{nom_canon}"
    try:
        # `encoding="utf-8", errors="replace"` : sans ça `text=True` décode avec
        # l'encodage LOCAL (cp1252 sur ce poste) et le premier caractère accentué
        # du canon rend la comparaison qui suit fausse — l'incident du 2026-09-01
        # sur `propager_socle._socle_non_commite`, une heure de propagation bloquée.
        out = subprocess.run(["git", "show", f"{hash_court}:{chemin_git}"],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.replace("\r\n", "\n").replace("\r", "\n")


def extraire_hash_provenance(texte_complet):
    """Le hash que la ligne `# | Provenance canon : <hash> du <date>` porte, ou
    None si la copie est antérieure à ce mécanisme."""
    m = _RE_PROVENANCE.search(texte_complet)
    return m.group(1) if m else None


def determiner_cause(nom_canon, texte_complet_actuel, corps_actuel):
    """La copie diffère du canon courant : est-ce la CIBLE qui a divergé (édition
    locale du script) ou le CANON qui a avancé au hub depuis que cette copie a été
    synchronisée ? Le message affiché doit accuser la bonne partie — c'est le
    finding du 2026-09-02 : « le script a été modifié ici » désignait la cible à
    tort quand c'était en réalité le canon qui avait bougé.

    Même mécanisme que `propager_socle.socle_d_origine` : comparer non pas au
    canon COURANT, mais au canon à SA RÉVISION DE PROVENANCE — celle que la copie
    elle-même déclare avoir reçue.

    Rend :
    - "canon-avance" si le corps actuel est identique au canon à sa révision de
      provenance (la cible n'a pas bougé, seul le canon a évolué depuis) ;
    - "cible-divergee" si le corps actuel diffère aussi du canon d'origine (une
      édition locale a bien eu lieu) ;
    - None si la provenance est absente (copie antérieure à ce mécanisme) ou
      irrésolvable (hash hors de l'histoire, git injoignable) — l'appelant doit
      alors s'abstenir de trancher plutôt que de deviner.
    """
    h = extraire_hash_provenance(texte_complet_actuel)
    if not h:
        return None
    corps_origine = canon_a_revision(nom_canon, h)
    if corps_origine is None:
        return None
    return "canon-avance" if corps_actuel == corps_origine else "cible-divergee"


def build_content(nom_canon, hash_court=None, jour=None):
    """Corps attendu (en-tête + canon), en \\n.

    `hash_court`/`jour` sont surchargeables (tests, ou pour figer une provenance) ;
    par défaut, la révision courante du hub et la date du jour."""
    body = read_lf(os.path.join(CANON_DIR, nom_canon))
    if hash_court is None:
        hash_court = hash_hub()
    if jour is None:
        jour = dt.date.today().isoformat()
    header = "\n".join(line.format(nom=nom_canon, hash=hash_court, date=jour)
                       for line in HEADER_LINES)
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

    if not check_only:
        sales = _canon_non_commite()
        if sales:
            print("canon NON COMMITÉ : " + ", ".join(sales) + " — la ligne de provenance "
                  "désignerait une révision qui ne contient pas ce qui serait copié.\n"
                  "  committer d'abord au hub : git commit -- " + CANON_GIT + "\n"
                  "  (aucune option ne lève ce refus — c'est cette ligne qui permettra au "
                  "sync suivant de dire si une cible a divergé ou si le canon a avancé)")
            return 3

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
            cause = None
            if os.path.isfile(dest):
                actuel = read_lf(dest)
                if actuel == exp:
                    n_ajour += 1
                    etat = "à jour"
                else:
                    corps_actuel = strip_header(actuel)
                    corps_exp = strip_header(exp)
                    if corps_actuel == corps_exp:
                        etat = "dérive (en-tête)"
                    else:
                        etat = "DÉRIVE (corps)"
                        # La différence de corps a DEUX causes possibles, que le
                        # message doit distinguer plutôt que d'accuser la cible par
                        # défaut (finding du 2026-09-02) : la cible a réellement
                        # divergé, OU le canon a avancé au hub depuis que cette
                        # copie a été synchronisée — auquel cas la cible, elle,
                        # n'a pas bougé. `determiner_cause` tranche en comparant
                        # au canon À SA RÉVISION DE PROVENANCE (mécanisme de
                        # `propager_socle.socle_d_origine`), pas au canon courant.
                        cause = determiner_cause(nom_canon, actuel, corps_actuel)
                    n_derive += 1
            else:
                etat = "ABSENT"
                n_absents += 1
                actuel = None

            if not check_only and etat != "à jour":
                if etat.startswith("DÉRIVE (corps)") and not accepter_derive:
                    if cause == "canon-avance":
                        etat += (" -> REFUS : le canon a avancé depuis que cette copie a "
                                 "été synchronisée (la cible, elle, n'a pas été modifiée) "
                                 "— re-synchroniser avec --accepter-derive pour l'aligner "
                                 "sur le canon actuel")
                    elif cause == "cible-divergee":
                        etat += (" -> REFUS : le script a été modifié ici. Relire le diff, "
                                 "remonter le correctif au canon du hub, ou forcer avec "
                                 "--accepter-derive")
                    else:
                        etat += (" -> REFUS : impossible de déterminer si le script a été "
                                 "modifié ici ou si le canon a avancé (provenance absente "
                                 "ou introuvable) — relire le diff avant de trancher, ou "
                                 "forcer avec --accepter-derive")
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
