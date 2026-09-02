"""Mesure réelle de la consommation de tokens du projet — 0 token LLM, à la demande.

POURQUOI CE SCRIPT EXISTE. L'étude de consommation du 2026-07-30 a buté sur un mur :
le dispositif comptait 159 invocations de skills et de sous-agents, mais **aucune
donnée en tokens nulle part**. Ni `log_usage.py` (qui n'enregistre que ts / session /
outil / skill / sous-agent), ni `state.json`, ni `runs.jsonl` ne portent le moindre
compteur. Toute décision d'économie se prenait donc sur des proxys — un nombre
d'invocations, une taille de fichier — jamais sur la dépense réelle.

Les compteurs existent pourtant : chaque message d'assistant d'un transcript porte un
bloc `usage` (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`). Ce script les agrège.

POURQUOI PAS DANS LE HOOK DE SESSION. `scan_transcripts.py` tourne à CHAQUE démarrage
(2,5-3,8 s mesurés) et ne parse que les lignes passant un préfiltre étroit. Ajouter
`usage` à ce préfiltre ferait parser *tous* les messages d'assistant à chaque session,
pour une donnée dont on a besoin de temps en temps. La mesure est donc un script
séparé, lancé à la demande — le hook reste rapide.

CE QUE CE SCRIPT NE FAIT JAMAIS : stocker, afficher ou recopier le moindre CONTENU de
message. Il ne retient que des entiers et des dates. Les transcripts contiennent du
contenu d'interviews clients : l'analyse reste strictement locale et strictement
numérique.

Usage :
    py -X utf8 scripts/mesure_tokens.py            # agrège et écrit tokens.json
    py -X utf8 scripts/mesure_tokens.py --jours 7  # ne garde que les 7 derniers jours
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Destination redirigeable, comme les trois autres journaux du dispositif
# (AGENT_SUPERVISION_JOBS_JOURNAL, _VUES_JOURNAL, _ARBITRAGES). Deux raisons, et la
# seconde a été payée : (1) le scan doit pouvoir dire OÙ il veut la mesure ; (2) sans
# redirection, un test qui exerce ce script écrase la mesure de PRODUCTION — c'est
# exactement le défaut trouvé le 2026-09-02 sur jobs.jsonl, dont les 242 lignes
# venaient toutes de la suite de tests, et qui a rendu inutilisable la seule mesure
# d'usage du site pendant un mois.
SORTIE = os.environ.get("AGENT_SUPERVISION_TOKENS_JSON") or os.path.join(
    ROOT, ".claude", "supervision", "tokens.json")


def dossier_transcripts(racine=None):
    """Le dossier `~/.claude/projects/<slug>` du projet.

    Dérivation reprise TELLE QUELLE de `.claude/dispositif/canon/scan_transcripts.py`
    (fonction faisant autorité) : Claude Code remplace TOUT caractère non alphanumérique
    par un tiret, et la casse du lecteur peut différer (`C:` vs `c:`), d'où le repli
    insensible à la casse. Réinventer cette règle donne un chemin faux — c'est ce qui
    est arrivé au premier jet de ce script."""
    chemin = ROOT if racine is None else racine
    slug = re.sub(r"[^A-Za-z0-9]", "-", chemin)
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    candidat = os.path.join(base, slug)
    if os.path.isdir(candidat):
        return candidat
    if os.path.isdir(base):
        for nom in os.listdir(base):
            if nom.lower() == slug.lower():
                return os.path.join(base, nom)
    return candidat


TRANSCRIPTS = dossier_transcripts()
CHAMPS = ("input_tokens", "output_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")


def _vide():
    return dict.fromkeys(CHAMPS, 0) | {"messages": 0}


def _ajouter(acc, usage):
    for c in CHAMPS:
        v = usage.get(c)
        if isinstance(v, int):
            acc[c] += v
    acc["messages"] += 1


def agreger(dossier=None, jours=None, now=None):
    """Agrège les compteurs `usage` des transcripts, par jour et par modèle.

    Streaming ligne à ligne avec préfiltre octet : un transcript de plusieurs Mo n'est
    jamais chargé en mémoire, et les lignes sans `usage` ne sont même pas décodées.
    `jours` borne la fenêtre (None = tout l'historique)."""
    dossier = TRANSCRIPTS if dossier is None else dossier
    limite = None
    if jours:
        maintenant = now or dt.datetime.now(dt.UTC)
        limite = (maintenant - dt.timedelta(days=jours)).isoformat()[:10]
    total, par_jour, par_modele = _vide(), {}, {}
    fichiers = 0
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.jsonl"))):
        fichiers += 1
        try:
            fh = open(chemin, "rb")
        except OSError:
            continue
        with fh:
            for brut in fh:
                if b'"usage"' not in brut:
                    continue
                try:
                    obj = json.loads(brut.decode("utf-8", "replace"))
                except ValueError:
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                jour = (obj.get("timestamp") or "")[:10]
                if limite and jour and jour < limite:
                    continue
                _ajouter(total, usage)
                if jour:
                    _ajouter(par_jour.setdefault(jour, _vide()), usage)
                modele = msg.get("model") or "(inconnu)"
                _ajouter(par_modele.setdefault(modele, _vide()), usage)
    return {
        "genere": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fenetre_jours": jours,
        "fichiers_parcourus": fichiers,
        "total": total,
        "par_jour": dict(sorted(par_jour.items())),
        "par_modele": dict(sorted(par_modele.items(),
                                  key=lambda kv: -kv[1]["output_tokens"])),
    }


def _fmt(n):
    return f"{n:,}".replace(",", " ")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    jours = None
    if "--jours" in argv:
        try:
            jours = int(argv[argv.index("--jours") + 1])
        except (IndexError, ValueError):
            print("mesure_tokens : --jours attend un entier", file=sys.stderr)
            return 2
    if not os.path.isdir(TRANSCRIPTS):
        print(f"mesure_tokens : dossier de transcripts introuvable ({TRANSCRIPTS})")
        return 1
    data = agreger(jours=jours)
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    t = data["total"]
    factures = t["input_tokens"] + t["output_tokens"] + t["cache_creation_input_tokens"]
    print(
        f"mesure_tokens : {data['fichiers_parcourus']} transcript(s), "
        f"{_fmt(t['messages'])} message(s) -> {os.path.relpath(SORTIE, ROOT)}\n"
        f"  entree {_fmt(t['input_tokens'])} · sortie {_fmt(t['output_tokens'])} · "
        f"cache ecrit {_fmt(t['cache_creation_input_tokens'])} · "
        f"cache relu {_fmt(t['cache_read_input_tokens'])}\n"
        f"  facturable (entree + sortie + ecriture de cache) : {_fmt(factures)} — "
        "le cache RELU ne se facture pas au prix plein, il n'est pas compté ici."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
