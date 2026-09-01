"""Le garde-fou pré-commit doit voir la vérification quel que soit le shell.

Finding `verification-manquante` sur `.claude/hooks/warn_verif_before_commit.py`
(diagnostic étage 2 du 2026-09-01), arbitré « applique » le jour même.

CE QUI ÉTAIT CASSÉ. `_verif_ran()` ne reconnaissait une vérification que sous l'outil
`Bash` — alors que **PowerShell est le shell primaire** de cet environnement. Mesuré
par appel direct sur des transcripts synthétiques : Bash `py -m pytest` → True,
PowerShell `py -m pytest` → **False**. Et sur le hub, `_VERIF_SKILL = ()` rendait la
branche Skill structurellement morte : aucune valeur ne pouvait la satisfaire.

POURQUOI C'EST GRAVE, et pas juste agaçant. Ce hook est le critère « fort » de la
pastille « Revue de code » verte sur 6 dépôts sur 6. La pastille reposait donc sur la
PRÉSENCE du garde-fou, jamais sur son FONCTIONNEMENT — le corollaire R6 exact de
CLAUDE.md : « l'étage 1 mesure la présence, jamais le fonctionnement ». Et un garde-fou
qui crie au loup quand la vérif A eu lieu s'ignore ; le jour où il a raison, il
s'ignore aussi. Le faux négatif avait d'ailleurs été constaté en production et
journalisé au run `2026-08-31T21:59` — sans être creusé.

CE QUE LA MESURE A PRÉCISÉ par rapport au finding : le trou PowerShell est UNIVERSEL
(les 6 copies portent `name == "Bash"` seul), mais la branche Skill morte est propre au
HUB — les 5 copies de la flotte portent `("pptx-verify", "revue-increment")` et
fonctionnent. Les deux défauts n'ont donc pas le même périmètre de correction.
"""

import importlib.util
import json
import os
import tempfile

from conftest import tmp_court

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(HUB, ".claude", "hooks", "warn_verif_before_commit.py")

_spec = importlib.util.spec_from_file_location("warn_verif_shell", HOOK)
wv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wv)


def _transcript(nom, **entree):
    """Un transcript de session à un seul tool_use — la forme que lit le hook."""
    ligne = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": nom, "input": entree}]}}
    fd, chemin = tempfile.mkstemp(suffix=".jsonl", dir=tmp_court())
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    return chemin


def _verif(nom, **entree):
    chemin = _transcript(nom, **entree)
    try:
        return wv._verif_ran(chemin)
    finally:
        os.remove(chemin)


def _fire_sous_powershell(chemin_copie):
    """Le garde-fou de CETTE copie se déclenche-t-il vraiment sous PowerShell ?

    Vérification FONCTIONNELLE, et c'est tout l'objet de la correction apportée ici
    le 2026-09-01 après la remarque de la session VSCode1. La première version de ce
    test cherchait la chaîne `name == "Bash"` dans le fichier — c'est-à-dire qu'elle
    mesurait une PRÉSENCE, exactement la faute que le finding dénonce. Un test de
    présence sur un défaut de fonctionnement est un test qui ne garde rien.

    Le témoin est LOCAL : chaque copie adapte `_VERIF_BASH` au canal réel de son
    projet (npm chez VSCode1, pytest ailleurs, `smoke-test` sur VSCode). Sonder tout
    le monde avec `py -m pytest` ne prouverait rien là où pytest n'est pas dans le
    tuple — la démonstration d'origine avait ce défaut, et VSCode1 l'a relevé.
    """
    import importlib.util as _iu
    spec = _iu.spec_from_file_location("wv_copie_" + os.path.basename(
        os.path.dirname(os.path.dirname(os.path.dirname(chemin_copie)))), chemin_copie)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    temoin = next(iter(mod._VERIF_BASH), None)
    if not temoin:
        return True  # pas de signal shell déclaré : rien à prouver ici
    ligne = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "PowerShell",
         "input": {"command": "cmd " + temoin}}]}}
    fd, p = tempfile.mkstemp(suffix=".jsonl", dir=tmp_court())
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    try:
        return bool(mod._verif_ran(p))
    finally:
        os.remove(p)


class TestLesDeuxShellsComptent:
    """L'invariant central : c'est la COMMANDE qui prouve la vérification, pas l'outil
    par lequel elle est passée. Les deux exposent la commande sous `input.command`."""

    def test_pytest_via_bash_est_reconnu(self):
        assert _verif("Bash", command="py -m pytest tests/ -q") is True

    def test_pytest_via_powershell_est_reconnu(self):
        """LE test du finding : PowerShell est le shell primaire de ce poste.
        Rouge avant correction."""
        assert _verif("PowerShell", command="py -m pytest tests/ -q") is True

    def test_le_scan_via_powershell_est_reconnu(self):
        assert _verif("PowerShell", command="py scripts/scan_projets.py") is True

    def test_py_compile_via_powershell_est_reconnu(self):
        assert _verif("PowerShell", command="py -m py_compile scripts/scan_projets.py") is True

    def test_une_commande_sans_verif_reste_fausse(self):
        """Le garde-fou doit rester capable de dire NON : un hook qui rend toujours
        True ne garde plus rien, et c'est la faute symétrique de celle corrigée ici."""
        for outil in ("Bash", "PowerShell"):
            assert _verif(outil, command="git status --porcelain") is False
            assert _verif(outil, command="echo bonjour") is False


class TestLaBrancheSkillNEstPlusMorte:
    """Défaut propre au HUB : `_VERIF_SKILL = ()` rendait la branche inatteignable.
    Les 5 copies de la flotte portaient déjà un tuple non vide."""

    def test_le_tuple_des_skills_de_verif_n_est_pas_vide(self):
        assert wv._VERIF_SKILL, (
            "_VERIF_SKILL vide = branche Skill structurellement morte : aucune valeur "
            "ne peut la satisfaire, le code ne s'exécute jamais")

    def test_la_boucle_de_revue_compte_comme_verification(self):
        """`revue-increment` EST la vérification de fin d'incrément de ce hub :
        l'exclure obligeait à re-lancer pytest pour satisfaire un garde-fou que la
        revue venait déjà de satisfaire."""
        assert _verif("Skill", skill="revue-increment") is True

    def test_une_skill_quelconque_ne_vaut_pas_verification(self):
        assert _verif("Skill", skill="agent-orchestrator") is False


class TestLaFlotteEstCouverteAussi:
    """Le trou PowerShell était UNIVERSEL : le corriger au hub seul laisserait cinq
    dépôts avec un garde-fou aveugle, et la pastille verte resterait fausse chez eux."""

    def _copies(self):
        import json as _json
        chemin = os.path.join(HUB, "projets.json")
        with open(chemin, encoding="utf-8") as fh:
            projets = _json.load(fh)["projets"]
        out = []
        for p in projets:
            f = os.path.join(p["chemin"], ".claude", "hooks",
                             "warn_verif_before_commit.py")
            if os.path.isfile(f):
                out.append((p["nom"], f))
        return out

    def test_aucune_copie_de_la_flotte_ne_teste_bash_seul(self):
        """Toute copie NON exemptée doit être corrigée.

        L'exemption est explicite et datée, pas un silence : le hub n'a pas le droit
        de committer dans un dépôt tiers sans mandat de son propriétaire (R2/R4). Une
        assertion sèche sur les 5 dépôts rendrait donc la suite du hub OTAGE d'une
        décision qui ne lui appartient pas — un test rouge y signalerait la politesse
        du hub, pas une régression. La liste ci-dessous fait l'inverse : elle nomme ce
        qui reste découvert, et le test échoue dès qu'un dépôt NON listé redevient
        aveugle. Vider la liste est le but ; l'allonger sans raison écrite est le
        défaut qu'elle rend visible.
        """
        # dépôt -> pourquoi il n'est pas encore corrigé (avec la date de la demande).
        # VIDE le 2026-09-01 : les 6 copies sont couvertes. VSCode2, seul exempté
        # quelques heures, a été corrigé par sa propre session après que le hub lui a
        # proposé le correctif — et c'est l'assertion `obsoletes` ci-dessous qui l'a
        # signalé, en refusant de laisser l'exemption survivre à sa raison d'être.
        EN_ATTENTE_DU_PROPRIETAIRE = {}
        restants = [nom for nom, f in self._copies() if not _fire_sous_powershell(f)]
        surprises = [n for n in restants if n not in EN_ATTENTE_DU_PROPRIETAIRE]
        assert not surprises, (
            f"garde-fou aveugle a PowerShell sur un depot NON exempte : {surprises}")
        obsoletes = [n for n in EN_ATTENTE_DU_PROPRIETAIRE if n not in restants]
        assert not obsoletes, (
            f"exemption devenue fausse (ces depots sont corriges) : {obsoletes} — "
            "retirer l'entree, sinon la liste ment sur l'etat reel")

    def test_le_kit_publie_porte_la_correction(self):
        """Sinon tout nouveau projet installerait le garde-fou aveugle."""
        publie = os.path.join(HUB, "export", "hooks", "warn_verif_before_commit.py")
        if not os.path.isfile(publie):
            return
        assert 'name == "Bash"' not in open(publie, encoding="utf-8").read()
