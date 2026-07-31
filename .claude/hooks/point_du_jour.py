"""Hook SessionStart — le point du jour : ce qui attend VOTRE decision.

Rupture B de docs/reflexions/approche-disruptive-wiki-2026-07-31.md, arbitree le
2026-07-31. La mesure qui la fonde : sur 242 jobs enregistres depuis les boutons du
wiki, 241 etaient des artefacts de tests et UN SEUL une action humaine. Personne ne
vient sur la page. En revanche, la conversation sert tous les jours -- 67 runs
orchestres. Donc l'information ne s'affiche plus la ou personne ne regarde : elle
arrive dans le canal reellement utilise.

CE QUE CE HOOK NE FAIT PAS. Il ne redit rien de ce que `scan_transcripts.py` annonce
deja au meme demarrage (runs a solder, reliquat non commite, diagnostic perime,
constats ecartes) : deux hooks qui se repetent forment le mur qu'on cesse de lire --
exactement la maladie dont souffrait le site. Il ne dit qu'une chose, celle que
personne ne disait : **ce qui attend un arbitrage humain**.

Il reste volontairement COURT (3 lignes au plus). Un point du jour qui deborde
redevient un tableau de bord, et on aura deplace le probleme au lieu de le regler.

Hook LOCAL au hub : `scan_transcripts.py` appartient au canon propage aux six projets
(en-tete « GENERE -- NE PAS EDITER LOCALEMENT »), le modifier pour un besoin
d'affichage du hub casserait les cibles. Lecon payee le 2026-07-31.

stdout en ASCII STRICT : les tests capturent ce flux en subprocess, et une console
cp1252 leve UnicodeDecodeError sur tout caractere hors table (incident 2026-07-29).
"""

import datetime as dt
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIAGNOSTIC = os.path.join(RACINE, ".claude", "supervision", "diagnostic.json")
VEILLE = os.path.join(RACINE, ".claude", "veille", "veille.json")
ARBITRAGES = os.path.join(RACINE, ".claude", "supervision", "arbitrages.json")

# Au-dela, une decision qui attend n'est plus une file : c'est un oubli.
SEUIL_ALERTE_JOURS = 7


def _charge(chemin):
    try:
        with open(chemin, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _age_jours(iso):
    """Jours ecoules depuis une date ISO, ou None si illisible."""
    if not iso:
        return None
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo:
            d = d.astimezone().replace(tzinfo=None)
        return (dt.datetime.now() - d).days
    except (ValueError, TypeError):
        return None


def _canon():
    """Charge scan_transcripts.py (meme dossier de supervision) pour REUTILISER sa
    logique de fermeture des findings au lieu de la reimplémenter.

    Lecon payee le jour meme de l'ecriture de ce hook (revue fraiche, 2026-07-31) :
    la premiere version croisait cible-contre-cible, sans categorie ni re_challenge.
    Deux faux negatifs reproduits par le relecteur — un arbitrage de routage fermait
    un finding de qualite sur la meme cible (friction cible-suppression, 2026-07-21),
    et un finding re-challenge restait masque par un arbitrage anterieur (constat
    prio 5 du 2026-07-28 : 3 constats sur 4 masques). Ces deux bugs avaient DEJA ete
    payes et corriges dans `finding_arbitre()` ; les reintroduire ici en les
    recodant de tete est exactement ce que la reutilisation evite.
    """
    import importlib.util
    chemin = os.path.join(RACINE, ".claude", "supervision", "scan_transcripts.py")
    spec = importlib.util.spec_from_file_location("scan_transcripts_pdj", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def findings_non_arbitres():
    """Findings du diagnostic non fermes par un arbitrage, au sens CANONIQUE.

    Un finding arbitre reste ecrit dans diagnostic.json (reecrit en entier a chaque
    diagnostic) : c'est un arbitrage a sa cible ET couvrant sa categorie qui le clot
    — et `re_challenge: true` prime sur les arbitrages anterieurs au diagnostic.
    Toute cette semantique vit dans `finding_arbitre()` du scan ; on l'appelle, on ne
    la recopie pas.
    """
    diag = _charge(DIAGNOSTIC) or {}
    findings = diag.get("findings")
    if not isinstance(findings, list) or not findings:
        return []
    arb = _charge(ARBITRAGES) or {}
    arbitrages = arb.get("arbitrages")
    if not isinstance(arbitrages, list):
        arbitrages = []
    canon = _canon()
    genere = str(diag.get("genere") or diag.get("date") or "")
    ouverts = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        cible = (f.get("cible") or "").strip()
        if not cible:
            continue
        if not canon.finding_arbitre(f, arbitrages, posterieur_a=genere):
            ouverts.append(cible)
    return ouverts


def trouvailles_en_attente():
    """(nombre, age de la doyenne) des trouvailles ni adoptees ni ecartees."""
    v = _charge(VEILLE) or {}
    entrees = [e for e in (v.get("entrees") or [])
               if e.get("statut") in ("nouveau", "etudie")]
    if not entrees:
        return 0, None
    ages = [a for a in (_age_jours(e.get("date") or v.get("derniere_veille"))
                        for e in entrees) if a is not None]
    return len(entrees), (max(ages) if ages else None)


def main():
    lignes = []

    ouverts = findings_non_arbitres()
    if ouverts:
        apercu = ", ".join(ouverts[:3]) + ("..." if len(ouverts) > 3 else "")
        lignes.append(
            "%d finding(s) du diagnostic sans arbitrage : %s"
            % (len(ouverts), apercu))

    n, age = trouvailles_en_attente()
    if n:
        suffixe = ""
        if age is not None:
            suffixe = " (la plus ancienne depuis %d j%s)" % (
                age, " -- a trancher" if age >= SEUIL_ALERTE_JOURS else "")
        lignes.append("%d trouvaille(s) de veille attendent votre decision%s"
                      % (n, suffixe))

    if not lignes:
        # Le silence est une information : rien ne vous attend. On le dit une fois,
        # brievement, plutot que de ne rien afficher -- l'absence de message se lit
        # comme un hook casse.
        print("Point du jour : rien n'attend votre arbitrage.")
        return 0

    print("Point du jour -- ce qui attend VOTRE decision :")
    for ligne in lignes[:3]:
        print("  " + ligne)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - un hook ne doit jamais bloquer la session
        print("Point du jour : ignore (%s: %s)" % (exc.__class__.__name__, exc))
        sys.exit(0)
