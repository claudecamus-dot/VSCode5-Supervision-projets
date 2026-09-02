"""Une convocation de salle qui ne nomme pas ses skills est REFUSÉE.

Arbitré le 2026-09-02, après que `bmad-advanced-elicitation` (pré-mortem + red team) a
démoli le premier état du raccord.

CE QUE LA CRITIQUE DISAIT, et elle avait raison. Le raccord consistait en un champ
`skills_bmad` dans un TOML et un paragraphe dans un document de 700 lignes. Or c'est
exactement la nature de la table de routage BMAD, qui n'a rien déclenché pendant 33 jours :
un rappel n'est pas un garde-fou. Trois « penser à » s'intercalaient entre la donnée et
l'acte — penser à ouvrir le TOML, penser à en extraire le champ, penser à le recopier dans
le brief — dans une chaîne dont l'échec précédent était précisément un « penser à » manqué.
Et les tests de ce raccord ne lisaient que du texte : ils mesuraient ma propre saisie, pas
un mécanisme.

CE QUI CHANGE ICI. Le seul mécanisme opposable de ce dépôt est un hook bloquant — c'est
ainsi que `guard_destructive_git.py` refuse un `git push --force`. Le point de contrôle
juste est la CONVOCATION : c'est le moment où le nom de la salle est connu et où le brief
s'écrit. Une convocation `bmad-party-mode --party <salle>` dont le texte ne nomme aucune
des skills que la salle déclare est donc refusée, avec la liste attendue dans le message.

CE QUE CE GARDE-FOU NE PRÉTEND PAS FAIRE. Il vérifie que la convocation PORTE les noms,
pas qu'une voix a réellement chargé la skill. Cette seconde vérification ne peut être
qu'a posteriori, contre le compteur de l'étage 1 — elle est traitée ailleurs. Un garde-fou
qui annoncerait plus que ce qu'il mesure serait le défaut que ce dépôt paie en boucle.

FAIL-OPEN INTÉGRAL : ce hook tourne en `PreToolUse`. Une exception y bloquerait un appel
d'outil légitime. TOML illisible, salle inconnue, entrée malformée, `tomllib` absent →
on laisse passer sans un mot. Il ne refuse que sur un cas positivement établi.
"""

import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(HUB, ".claude", "hooks", "guard_salle_skills.py")


def _appel(tool_name="Skill", tool_input=None, cwd=None):
    """Exécute le hook comme le harnais le fait : JSON sur stdin, JSON sur stdout.

    SANS `-X utf8` ni `PYTHONIOENCODING` : le gabarit du kit lance `py "<script>"`, en
    cp1252 sur ce poste. La revue du 2026-09-02 a montré qu'avec ces deux béquilles les
    tests exécutaient un hook que la production n'exécute pas — et ne pouvaient pas voir
    un `deny` sorti en octets illisibles. Décodage strict, pour la même raison.
    """
    charge = {"tool_name": tool_name, "tool_input": tool_input or {}, "cwd": cwd or HUB}
    r = subprocess.run([sys.executable, HOOK],
                       input=json.dumps(charge), capture_output=True, text=True,
                       encoding="utf-8", errors="strict", timeout=30)
    return r


def _decision(r):
    if not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout).get("hookSpecificOutput", {}).get("permissionDecision")
    except ValueError:
        return None


class TestUneConvocationSansSesSkillsEstRefusee:
    def test_refus_quand_aucune_skill_de_la_salle_n_est_nommee(self):
        r = _appel(tool_input={
            "skill": "bmad-party-mode",
            "args": "--party code-review-crew --mode subagent\n\nSUJET : relire ce diff."})
        assert _decision(r) == "deny", (
            "une convocation qui ne nomme aucune skill de la salle a été laissée passer ; "
            f"stdout={r.stdout!r} stderr={r.stderr[:300]!r}")

    def test_le_refus_NOMME_les_skills_attendues(self):
        """Un refus qui ne dit pas quoi écrire fait deviner — et on redevine mal."""
        r = _appel(tool_input={
            "skill": "bmad-party-mode",
            "args": "--party code-review-crew --mode subagent\n\nSUJET : relire ce diff."})
        raison = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "bmad-code-review" in raison, raison

    def test_passe_des_qu_une_skill_de_la_salle_est_nommee(self):
        r = _appel(tool_input={
            "skill": "bmad-party-mode",
            "args": ("--party code-review-crew --mode subagent\n\nSUJET : relire ce diff. "
                     "La voix edge-hunter charge `bmad-review-edge-case-hunter`.")})
        assert _decision(r) != "deny", r.stdout

    def test_la_porte_de_sortie_du_message_existe_dans_le_code(self):
        """Le refus prescrit « aucune skill BMAD sur ce tour, parce que… » ; la revue du
        2026-09-02 a reproduit que cette phrase était refusée à son tour — la seule issue
        était de recopier un nom, exactement ce que le message condamne."""
        r = _appel(tool_input={
            "skill": "bmad-party-mode",
            "args": ("--party code-review-crew --mode subagent\n\nAucune skill BMAD sur ce "
                     "tour, parce que le diff tient en trois lignes.")})
        assert _decision(r) != "deny", r.stdout

    @pytest.mark.parametrize("args", [
        '--party "code-review-crew" --mode subagent\n\nsujet : ce diff',
        "--party\tcode-review-crew --mode subagent",
        "--PARTY Code-Review-Crew --mode subagent",
        "--party=code-review-crew",
    ])
    def test_la_forme_de_la_convocation_n_eteint_pas_le_garde_fou(self, args):
        """Guillemets, tabulation, casse, `=` : autant de contournements d'un caractère
        que la revue du 2026-09-02 a reproduits sur la première regex."""
        r = _appel(tool_input={"skill": "bmad-party-mode", "args": args})
        assert _decision(r) == "deny", f"laissé passer : {args!r} -> {r.stdout!r}"

    def test_la_casse_du_nom_de_skill_ne_fait_pas_un_faux_refus(self):
        r = _appel(tool_input={
            "skill": "bmad-party-mode",
            "args": "--party code-review-crew\n\nLa voix charge BMAD-CODE-REVIEW."})
        assert _decision(r) != "deny", r.stdout


class TestLeBoutonDuWikiPasseLeGardeFou:
    """BLOQUANT de la revue du 2026-09-02 : `action_party` (bouton « Déclencher ») composait
    « --party <salle> --mode subagent --non-interactive » sans nommer une skill — la seule
    convocation que le hub émet lui-même était la seule qu'il refusait, en `claude -p`
    headless où personne ne lève un refus."""

    @staticmethod
    def _serve():
        spec = importlib.util.spec_from_file_location(
            "serve_wiki_guard", os.path.join(HUB, "scripts", "serve_wiki.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _args_exacts(self, prompt):
        """La chaîne que le run passera à l'outil Skill : ce qui suit « EXACTS : » jusqu'au
        sujet — c'est elle, et rien d'autre, que le hook lit."""
        debut = prompt.index("EXACTS : ") + len("EXACTS : ")
        fin = prompt.index("SUJET SOUMIS")
        return prompt[debut:fin]

    def test_chaque_salle_convoquee_par_le_bouton_passe(self, monkeypatch):
        serve = self._serve()
        monkeypatch.setattr(serve, "CLAUDE_BIN", "claude")
        salles = sorted(serve._salles_valides())
        assert salles, "aucune salle lue : rien à vérifier"
        for salle in salles:
            cmd = serve.action_party(salle, "sujet de test")
            assert cmd, salle
            args = self._args_exacts(cmd[-1])
            r = _appel(tool_input={"skill": "bmad-party-mode", "args": args})
            assert _decision(r) != "deny", (
                f"le bouton « Déclencher » de {salle} compose une convocation que le hook "
                f"refuse : {args!r}")

    def test_les_skills_de_la_salle_sont_dans_les_arguments(self, monkeypatch):
        serve = self._serve()
        monkeypatch.setattr(serve, "CLAUDE_BIN", "claude")
        cmd = serve.action_party("code-review-crew", "sujet")
        args = self._args_exacts(cmd[-1])
        for nom in serve._skills_salle("code-review-crew"):
            assert nom in args, (nom, args)


class TestIlNeRefuseQueCeQuIlConnait:
    """Un garde-fou qui refuse ce qu'il ne comprend pas devient un obstacle, et on le
    contourne — ce qui coûte plus cher que de ne pas l'avoir."""

    def test_une_skill_qui_n_est_pas_party_mode_passe(self):
        r = _appel(tool_input={"skill": "revue-increment", "args": "--party n'importe quoi"})
        assert _decision(r) != "deny", r.stdout

    def test_une_salle_inconnue_passe(self):
        r = _appel(tool_input={"skill": "bmad-party-mode",
                               "args": "--party salle-qui-nexiste-pas --mode subagent"})
        assert _decision(r) != "deny", r.stdout

    def test_une_convocation_sans_party_passe(self):
        r = _appel(tool_input={"skill": "bmad-party-mode", "args": "aide-moi à choisir"})
        assert _decision(r) != "deny", r.stdout

    def test_un_autre_outil_passe(self):
        r = _appel(tool_name="Bash", tool_input={"command": "--party code-review-crew"})
        assert _decision(r) != "deny", r.stdout


class TestFailOpen:
    """`PreToolUse` : une exception ici bloquerait un appel d'outil légitime."""

    @pytest.mark.parametrize("charge", [
        "", "pas du json", "{}", '{"tool_name": "Skill"}',
        '{"tool_name": "Skill", "tool_input": null}',
        '{"tool_name": "Skill", "tool_input": {"args": 42}}',
    ])
    def test_une_entree_malformee_ne_fait_ni_lever_ni_refuser(self, charge):
        r = subprocess.run([sys.executable, HOOK], input=charge,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="strict", timeout=30)
        assert r.returncode == 0, f"exit {r.returncode} : {r.stderr[:400]}"
        assert "Traceback" not in (r.stderr or ""), r.stderr[:400]
        assert _decision(r) != "deny"

    def test_un_toml_introuvable_laisse_passer(self, tmp_path):
        """Cas RÉEL du kit publié (le hook y est depuis le 2026-09-02) : une cible sans
        salles. Il ne doit pas y refuser des convocations faute de savoir quoi nommer.

        La redirection passe par `AGENT_SUPERVISION_PARTY_TOML` et non par le `cwd` :
        le hook dérive sa racine de `__file__`, précisément pour qu'un `Skill` lancé depuis
        un sous-répertoire ne lui fasse pas manquer sa configuration — c'est la leçon de
        `warn_verif_before_commit.py`, généralisé le matin même.
        """
        env = dict(os.environ,
                   AGENT_SUPERVISION_PARTY_TOML=str(tmp_path / "absent.toml"))
        charge = json.dumps({"tool_name": "Skill", "tool_input": {
            "skill": "bmad-party-mode", "args": "--party code-review-crew"}})
        r = subprocess.run([sys.executable, HOOK], input=charge,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="strict", timeout=30, env=env)
        assert r.returncode == 0, r.stderr[:300]
        assert _decision(r) != "deny", r.stdout


class TestLeHookEstCable:
    def test_il_est_declare_en_PreToolUse_sur_Skill(self):
        """Un hook non câblé est un fichier, pas un garde-fou — et c'est précisément la
        famille de défaut que ce hook existe pour corriger."""
        with io.open(os.path.join(HUB, ".claude", "settings.json"), encoding="utf-8-sig") as fh:
            s = json.load(fh)
        commandes = [
            h.get("command", "")
            for g in (s.get("hooks") or {}).get("PreToolUse", [])
            for h in g.get("hooks", [])
            if "Skill" in (g.get("matcher") or "")
        ]
        assert any("guard_salle_skills" in c for c in commandes), (
            f"hook absent des PreToolUse matchant Skill : {commandes}")
