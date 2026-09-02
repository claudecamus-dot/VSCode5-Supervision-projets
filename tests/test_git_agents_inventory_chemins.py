"""`git_agents_inventory.py` répond « non » à tort sur un chemin accentué, et PLANTE
sur un chemin qui commence par arobase. Deux défauts arbitrés le 2026-09-02, dans le
même mécanisme (le parsing de `git log --name-only`), vérifiés sur un VRAI dépôt git
jetable — pas de monkeypatch qui fabriquerait la sortie voulue : c'est précisément par
un monkeypatch qu'un défaut de cette famille est passé inaperçu ici le 2026-09-01.

CE QUI ÉTAIT CASSÉ.

1. `core.quotepath` (par défaut activé dans git, aucune config globale sur ce poste
   ne le désactive — vérifié par `git config --get core.quotepath`, qui ne rend
   rien). Git ÉCHAPPE alors tout octet non-ASCII d'un chemin et l'entoure de
   guillemets : `agents/résumé-projet.md` ressort en
   `"agents/r\\303\\251sum\\303\\251-projet.md"`. Cette forme ne termine plus par
   `.md` (elle termine par `.md"`), donc les regex de classification ne la
   reconnaissent plus — un agent ou une skill réellement présent(e), ou réellement
   supprimé(e), devient invisible. L'outil sert à répondre « un agent équivalent a-t-il
   déjà existé ? » avant d'en recréer un : répondre « non » à tort fait dupliquer un
   travail qui existe déjà dans l'historique.

2. Le séparateur d'en-tête `@%H|%ad|%s`. Un CHEMIN DE FICHIER qui commence lui-même
   par `@` (mesuré : `@robot/agents/special.md`) est confondu avec une ligne d'en-tête
   de commit. Le code tente alors `sha, date, sujet = ligne[1:].split("|", 2)` sur un
   texte qui ne contient aucun `|` — `ValueError: not enough values to unpack` — et
   `inventaire()` plante entièrement, y compris pour tous les commits déjà traités
   correctement.

LE CORRECTIF (voir `.claude/orchestration/git_agents_inventory.py`) : `-c
core.quotepath=false` sur l'appel git, et un séparateur d'en-tête `\\x1e` (Record
Separator ASCII) au lieu de `@`. `\\x1e` est un caractère de contrôle : Windows
interdit purement et simplement les caractères de contrôle 0-31 dans un nom de
fichier, et même sur un système qui l'accepterait, git échappe TOUJOURS les
caractères de contrôle d'un chemin (indépendamment de `core.quotepath`, qui ne
gouverne que les octets >= 0x80) — un vrai chemin ne peut donc jamais apparaître en
clair avec ce premier octet, contrairement à `@`, qui est un premier caractère de
nom de fichier parfaitement légal.

Reproduit empiriquement avant d'écrire ce fichier (`git ls-files` /
`git -c core.quotepath=false ls-files` sur un dépôt jetable) : voir la trace de
session — la duplication n'est pas supposée, elle est mesurée.
"""

import importlib.util
import os
import subprocess

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HUB, ".claude", "orchestration", "git_agents_inventory.py")


def _load():
    """Charge le script par chemin (ce n'est pas un package) — même geste que
    `tests/test_propager_socle.py` et `tests/test_canon.py` pour les modules du
    dispositif."""
    spec = importlib.util.spec_from_file_location("git_agents_inventory_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inv = _load()


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _depot_reel(tmp_path):
    r"""Un VRAI dépôt git, avec :
    - une skill PRÉSENTE au nom accentué (`skills/étude-de-marché/SKILL.md`) ;
    - un agent SUPPRIMÉ au nom accentué (`agents/résumé-projet.md`, ajouté puis
      supprimé) ;
    - un agent SUPPRIMÉ dont le CHEMIN COMMENCE PAR AROBASE
      (`@robot/agents/special.md`, ajouté puis supprimé) ;
    - un agent SUPPRIMÉ ordinaire APRÈS celui-ci (`agents/normal-agent.md`), pour
      vérifier que le parsing qui suit la ligne piégée n'est pas corrompu.

    Ordre des commits : c1 ajoute tout, c2 supprime l'agent accentué, c3 supprime
    l'agent en `@`, c4 supprime l'agent normal — `git log` les rend du plus récent
    au plus ancien, donc la ligne `@robot/agents/special.md` est bien rencontrée
    ENTRE deux en-têtes de commit réels, exactement le cas qui fait planter l'ancien
    séparateur.
    """
    repo = tmp_path / "depot"
    repo.mkdir()
    r = str(repo)
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")

    (repo / "skills" / "étude-de-marché").mkdir(parents=True)
    (repo / "skills" / "étude-de-marché" / "SKILL.md").write_text(
        "# Étude de marché\n", encoding="utf-8")
    (repo / "agents").mkdir()
    (repo / "agents" / "résumé-projet.md").write_text("agent résumé\n", encoding="utf-8")
    (repo / "agents" / "normal-agent.md").write_text("agent normal\n", encoding="utf-8")
    (repo / "@robot" / "agents").mkdir(parents=True)
    (repo / "@robot" / "agents" / "special.md").write_text("agent special\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "c1 ajoute tout")

    _git(r, "rm", "-q", "agents/résumé-projet.md")
    _git(r, "commit", "-qm", "c2 supprime l'agent accentue")

    _git(r, "rm", "-q", "@robot/agents/special.md")
    _git(r, "commit", "-qm", "c3 supprime l'agent en arobase")

    _git(r, "rm", "-q", "agents/normal-agent.md")
    _git(r, "commit", "-qm", "c4 supprime l'agent normal")
    return r


class TestLeCheminAccentuePresentEstTrouve:
    """Défaut 1a : `core.quotepath` fait ressortir un chemin accentué échappé — les
    regex de classification ne le reconnaissent plus, et l'outil répond « non » à
    tort à la question « une skill équivalente existe-t-elle déjà ? »."""

    def test_la_skill_accentuee_apparait_dans_les_presents(self, tmp_path, monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        noms = {e["nom"] for e in result["presents"]}
        assert "étude-de-marché" in noms, (
            f"la skill accentuée est invisible des présents (noms trouvés : {noms}) — "
            "un chemin échappé par core.quotepath ne termine plus en .md pour la regex")

    def test_le_chemin_rendu_est_en_clair_pas_echappe(self, tmp_path, monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        chemins = [e["chemin"] for e in result["presents"]]
        assert any("étude-de-marché" in c for c in chemins), (
            f"chemins rendus : {chemins!r} — forme octale echappee au lieu de l'UTF-8 clair")
        assert not any("\\303\\251" in c or c.startswith('"') for c in chemins), (
            "le chemin porte encore l'échappement octal / les guillemets de git : "
            "core.quotepath=false n'est pas appliqué à l'appel")


class TestLAgentAccentueSupprimeEstTrouve:
    """Même défaut, côté `git log --diff-filter=D --name-only` : un agent réellement
    supprimé de l'historique doit rester restaurable — c'est tout l'intérêt de cet
    outil face à un agent qu'on s'apprêterait à recréer de zéro."""

    def test_l_agent_accentue_apparait_dans_les_supprimes(self, tmp_path, monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        noms = {e["nom"] for e in result["supprimes"]}
        assert "résumé-projet" in noms, (
            f"l'agent accentué supprimé est invisible (noms trouvés : {noms}) — "
            "l'outil répondrait NON à tort et ferait recréer un agent qui a existé")

    def test_la_commande_de_restauration_vise_le_vrai_chemin_accentue(self, tmp_path,
                                                                       monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        entree = next((e for e in result["supprimes"] if e["nom"] == "résumé-projet"),
                      None)
        assert entree is not None
        assert "résumé-projet.md" in entree["chemin"]
        assert "résumé-projet.md" in entree["restaurer"]
        assert "\\303\\251" not in entree["restaurer"]


class TestLeCheminEnArobaseNeFaitPasPlanterLinventaire:
    """Défaut 1b : un chemin de fichier qui COMMENCE par `@` est confondu avec une
    ligne d'en-tête de commit (`@%H|%ad|%s`) — le code tente de la découper en
    sha/date/sujet et lève `ValueError`. `inventaire()` doit survivre, ET continuer à
    attribuer correctement les commits qui suivent dans le flux."""

    def test_inventaire_ne_leve_pas(self, tmp_path, monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        try:
            inv.inventaire()
        except ValueError as exc:
            pytest.fail(
                f"inventaire() a plante sur un chemin commencant par '@' : {exc!r}")

    def test_l_agent_en_arobase_est_correctement_classe_supprime(self, tmp_path,
                                                                  monkeypatch):
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        entree = next((e for e in result["supprimes"] if e["nom"] == "special"), None)
        assert entree is not None, (
            "l'agent dont le chemin commence par '@' n'est pas dans les supprimes — "
            "il a ete pris pour une ligne d'en-tete de commit")
        assert entree["sujet"] == "c3 supprime l'agent en arobase", (
            "l'agent en '@' est attribue au mauvais commit — la corruption du "
            f"parsing continue en aval (sujet trouve : {entree['sujet']!r})")

    def test_le_commit_normal_qui_suit_la_ligne_piegee_reste_correct(self, tmp_path,
                                                                      monkeypatch):
        """La ligne `@robot/agents/special.md` est rencontrée ENTRE deux en-têtes de
        commit réels : si elle est mal reconnue, le parsing qui suit peut dérailler
        pour tout le reste de l'historique, pas seulement pour elle."""
        repo = _depot_reel(tmp_path)
        monkeypatch.setattr(inv, "REPO", repo)
        result = inv.inventaire()
        entree = next((e for e in result["supprimes"] if e["nom"] == "normal-agent"),
                      None)
        assert entree is not None, "l'agent normal (commit suivant) a disparu"
        assert entree["sujet"] == "c4 supprime l'agent normal"


class TestAutresAppelsGit:
    """Le fichier n'a qu'un seul point d'entrée git (`_git`), partagé par `ls-files`
    et `log` — un seul correctif de `core.quotepath` suffit donc à couvrir les deux,
    et ce test le vérifie plutôt que de le supposer."""

    def test_un_seul_point_d_entree_git_dans_le_fichier(self):
        texte = open(SCRIPT, encoding="utf-8").read()
        # hors la fonction _git elle-même, aucun autre `subprocess.run(["git"` ne
        # doit apparaitre : sinon il faudrait lui appliquer quotepath separement.
        appels = texte.count('subprocess.run(')
        assert appels == 1, (
            f"{appels} appel(s) subprocess.run trouve(s) — verifier que chacun "
            "porte -c core.quotepath=false s'il liste des chemins")
