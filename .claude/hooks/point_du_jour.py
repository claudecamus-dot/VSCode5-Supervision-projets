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
import re
import sys
import unicodedata

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


def findings_ouverts():
    """Findings du diagnostic non fermes par un arbitrage, au sens CANONIQUE.

    Un finding arbitre reste ecrit dans diagnostic.json (reecrit en entier a chaque
    diagnostic) : c'est un arbitrage a sa cible ET couvrant sa categorie qui le clot
    — et `re_challenge: true` prime sur les arbitrages anterieurs au diagnostic.
    Toute cette semantique vit dans `finding_arbitre()` du scan ; on l'appelle, on ne
    la recopie pas.

    Rend cible + titre + categorie : le judas du wiki
    (`scan_projets.render_decisions_html`) et la ligne de ce hook consomment la
    MEME collecte — une seule semantique d'ouverture, deux canaux d'affichage
    (arbitrage « Judas compte » + « Vous prevenir ailleurs », 2026-08-31).
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
    # write_diagnostic.py ecrit la cle "generated" (ancien nom "genere" tolere pour
    # les fichiers/tests anterieurs) -- une mauvaise cle ici laisse `genere` a "" en
    # permanence et court-circuite `finding_arbitre()` (cf. sa docstring, jour="").
    genere = str(diag.get("generated") or diag.get("genere") or diag.get("date") or "")
    ouverts = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        cible = (f.get("cible") or "").strip()
        if not cible:
            continue
        if not canon.finding_arbitre(f, arbitrages, posterieur_a=genere):
            ouverts.append({"cible": cible,
                            "titre": (f.get("titre") or "").strip(),
                            "categorie": (f.get("categorie") or "").strip()})
    return ouverts


def findings_non_arbitres():
    """Compat : les seules cibles, dans le meme ordre (consommee par les tests et
    les appels anterieurs a la collecte enrichie)."""
    return [f["cible"] for f in findings_ouverts()]


def _normalise(texte):
    """Ne garde que alphanumerique en minuscules -- pour comparer un slug d'arbitrage
    a l'URL/titre d'une trouvaille sans se faire avoir par la ponctuation (tirets,
    accents echappes en mojibake, etc.)."""
    return re.sub(r"[^a-z0-9]+", "", (texte or "").lower())


def _veille_arbitree(entree, arbitrages):
    """Vrai si une trouvaille de veille est deja couverte par un arbitrage.

    `veille.json` ne porte pas de champ `cible` (contrairement aux findings du
    diagnostic, que `finding_arbitre()` du canon ferme dessus en comparant deux
    cibles egales) : on reconstitue le rapprochement par le slug de la cible
    `veille:<slug>` contre l'URL/titre de la trouvaille -- la seule information
    stable qu'elle porte. Le slug choisi par l'humain qui arbitre n'est pas toujours
    le nom exact du depot (ex. `veille:multi-agent-observability` pour un depot
    `claude-code-hooks-multi-agent-observability`) : la comparaison se fait donc en
    "slug contenu dans le texte de la trouvaille", pas en egalite stricte.

    Meme principe structurel que `finding_arbitre()` : la presence d'un arbitrage
    concernant la cible ferme le constat -- avec UNE exception, mesuree le 2026-08-31
    sur le fichier reel. `veille:dev-browser` porte « INSTRUIT, ADOPTION CIBLEE EN
    ATTENTE » : l'arbitrage existe, mais il dit lui-meme que la decision n'est pas
    prise. Le fermer dessus enterrait la seule attente reelle du lot, c'est-a-dire
    reproduisait par l'autre bout le defaut que le finding
    `veille:decision-non-reinjectee` reprochait a ce hook.

    On ne lit donc du champ `decision` qu'UN marqueur de convention, « EN ATTENTE »,
    au meme titre que ACCEPTE / ECARTE / INSTRUIT -- pas une analyse de prose. Tout
    le reste (savoir si un ECARTE merite d'etre rouvert) reste un rearbitrage humain,
    pas une detection."""
    texte = _normalise((entree.get("url") or "") + " " + (entree.get("titre") or ""))
    if not texte:
        return False
    for arb in arbitrages or []:
        cible = arb.get("cible") or ""
        if not cible.startswith("veille:"):
            continue
        # Le verdict se lit dans la TETE de la decision, avant le premier « : » -- la
        # ou la convention du fichier le place (« INSTRUIT, ADOPTION CIBLEE EN ATTENTE
        # (statut etudie) : <prose> »). Chercher le marqueur dans toute la prose
        # rouvrait des verdicts conclusifs dont le corps mentionne « en attente » a
        # propos d'autre chose : mesure le 2026-08-31, 2 cas sur 3.
        # _normalise() retire les espaces : « EN ATTENTE » y devient « enattente ».
        verdict = (arb.get("decision") or "").split(":", 1)[0]
        if "enattente" in _normalise(verdict):
            continue  # l'arbitrage se declare lui-meme non conclusif
        slug = _normalise(cible[len("veille:"):])
        if slug and slug in texte:
            return True
    return False


def trouvailles_ouvertes():
    """Les trouvailles ni adoptees ni ecartees, et pas deja couvertes par un
    arbitrage (cf. `_veille_arbitree`) — les entrees COMPLETES, pour que le judas
    du wiki et la ligne du hook consomment la meme collecte.

    Sans le second filtre, une trouvaille reste annoncee "en attente de VOTRE
    decision" indefiniment des lors que personne ne reporte a la main le statut
    d'arbitrages.json dans veille.json -- panne mecanique mesuree le 2026-08-31 :
    3 des 4 trouvailles annoncees portaient deja une decision tracee depuis le
    2026-07-31."""
    v = _charge(VEILLE) or {}
    entrees = [e for e in (v.get("entrees") or [])
               if isinstance(e, dict) and e.get("statut") in ("nouveau", "etudie")]
    if not entrees:
        return []
    arb = _charge(ARBITRAGES) or {}
    arbitrages = arb.get("arbitrages")
    if not isinstance(arbitrages, list):
        arbitrages = []
    return [e for e in entrees if not _veille_arbitree(e, arbitrages)]


def trouvailles_en_attente():
    """(nombre, age de la doyenne) — la forme compacte pour la ligne du hook."""
    entrees = trouvailles_ouvertes()
    if not entrees:
        return 0, None
    v = _charge(VEILLE) or {}
    ages = [a for a in (_age_jours(e.get("date") or v.get("derniere_veille"))
                        for e in entrees) if a is not None]
    return len(entrees), (max(ages) if ages else None)


def _ascii(texte):
    """Plie un texte en ASCII strict (accents decomposes puis ignores) — la
    console cp1252 leve UnicodeDecodeError sur tout caractere hors table, et un
    titre de veille porte accents et tirets cadratins."""
    return unicodedata.normalize("NFKD", texte or "").encode(
        "ascii", "ignore").decode("ascii")


def main():
    # « Vous prevenir ailleurs » (salle atelier-idees, arbitre le 2026-08-31) : la
    # ligne ne DENOMBRE plus, elle donne la commande prete a taper — l'information
    # arrive dans le canal reellement utilise, avec le verbe qui la traite.
    lignes = []

    ouverts = findings_ouverts()
    if ouverts:
        apercu = ", ".join(f["cible"] for f in ouverts[:3]) + (
            "..." if len(ouverts) > 3 else "")
        premier = ouverts[0]["cible"]
        lignes.append(
            "%d finding(s) du diagnostic sans arbitrage : %s -- taper : "
            "applique %s | refuse %s"
            % (len(ouverts), apercu, premier, premier))

    entrees = trouvailles_ouvertes()
    n, age = trouvailles_en_attente()
    if n:
        suffixe = ""
        if age is not None:
            suffixe = " (la plus ancienne depuis %d j%s)" % (
                age, " -- a trancher" if age >= SEUIL_ALERTE_JOURS else "")
        def _age_ou_moins_un(e):
            a = _age_jours(e.get("date"))
            return -1 if a is None else a
        doyenne = _ascii((max(entrees, key=_age_ou_moins_un).get("titre")
                          or "").strip())[:60]
        verbes = (' -- taper : adopte "%s" | ecarte "%s"' % (doyenne, doyenne)
                  if doyenne else "")
        lignes.append("%d trouvaille(s) de veille attendent votre decision%s%s"
                      % (n, suffixe, verbes))

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
