"""Verite du taux de reussite par playbook (correctif majeur 1, campagne 2026-08-31).

Mesure sur le journal reel (`runs.jsonl`, 80 runs) : `evolution-flotte` = 36 runs =
30 succes + 4 en-attente-validation + 2 partiel, et **0 echec**. Avant ce correctif,
`build_runs_stats` (canon `scan_transcripts.py`) ne retirait du denominateur `n` que le
statut `en-cours` -- `en-attente-validation` et `partiel` y entraient sans jamais
incrementer `succes` ni `echecs`, ce qui produit un taux de 30/36 = 83 % alors qu'aucun
des 36 runs n'a echoue. Le wiki affiche ce pourcentage comme s'il mesurait des echecs
reels.

Correctif retenu : traiter `en-attente-validation` et `partiel` comme `en-cours` deja
l'etait -- des runs NON SOLDES, exclus de `n` (donc du taux), mais comptes a part pour
rester visibles (sinon leur disparition du denominateur serait aussi silencieuse que le
bug qu'elle corrige). C'est une generalisation du principe deja ecrit pour `en-cours`
dans la docstring de `build_runs_stats` : un statut qui ne dit encore ni reussite ni
echec ne doit pas fausser le taux, dans un sens comme dans l'autre.

Lancer cible : py -m pytest tests/test_stats_runs.py -q --basetemp=C:/tmp/gC
"""

import importlib.util
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(HUB, ".claude", "dispositif", "canon")


def _load(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = _load("canon_scan_transcripts_stats", os.path.join(CANON, "scan_transcripts.py"))


def _run(resultat, playbook="evolution-flotte", reprises=0):
    return {"resultat": resultat, "playbook": playbook, "reprises": reprises, "plan": []}


class TestBuildRunsStatsDenominateur:
    """Cas reel mesure sur runs.jsonl : 36 runs = 30 succes + 4 en-attente-validation +
    2 partiel, 0 echec -- le taux doit refleter zero echec, pas 83 %."""

    def _runs_evolution_flotte(self):
        runs = [_run("succes") for _ in range(30)]
        runs += [_run("en-attente-validation") for _ in range(4)]
        runs += [_run("partiel") for _ in range(2)]
        return runs

    def test_en_attente_validation_exclu_du_denominateur(self):
        par_playbook, _ = scan.build_runs_stats(self._runs_evolution_flotte())
        e = par_playbook["evolution-flotte"]
        assert e["n"] == 30, "les 4 en-attente-validation ne doivent plus gonfler n"
        assert e["succes"] == 30
        assert e["echecs"] == 0, "aucun des 36 runs n'est un echec reel"

    def test_partiel_exclu_du_denominateur(self):
        par_playbook, _ = scan.build_runs_stats(self._runs_evolution_flotte())
        e = par_playbook["evolution-flotte"]
        # Un taux succes/n ne doit plus jamais retomber a 30/36 = 83% : avec le
        # correctif, succes/n = 30/30 = 100%, ce qui dit la verite (0 echec).
        assert e["succes"] / e["n"] == 1.0

    def test_non_soldes_restent_visibles_et_comptes(self):
        """Exclure du denominateur ne doit pas les faire disparaitre silencieusement --
        meme piege que celui documente pour `en_cours`."""
        par_playbook, _ = scan.build_runs_stats(self._runs_evolution_flotte())
        e = par_playbook["evolution-flotte"]
        assert e["en_attente_validation"] == 4
        assert e["partiels"] == 2

    def test_echec_reel_compte_toujours(self):
        """Non-regression : un vrai echec doit toujours entrer dans n ET echecs."""
        runs = [_run("succes"), _run("echec"), _run("echec")]
        par_playbook, _ = scan.build_runs_stats(runs)
        e = par_playbook["evolution-flotte"]
        assert e["n"] == 3 and e["succes"] == 1 and e["echecs"] == 2

    def test_en_cours_toujours_exclu(self):
        """Non-regression du comportement deja correct avant ce correctif."""
        runs = [_run("succes"), _run("en-cours"), _run("en-cours")]
        par_playbook, _ = scan.build_runs_stats(runs)
        e = par_playbook["evolution-flotte"]
        assert e["n"] == 1 and e["en_cours"] == 2

    def test_par_agent_meme_traitement(self):
        """Le meme correctif s'applique a l'agregat par agent (meme sous-fonction
        `cumuler`), pas seulement par playbook."""
        runs = [{"resultat": "en-attente-validation", "playbook": None, "reprises": 0,
                 "plan": [{"agent": "bmad-revue"}]}]
        _, par_agent = scan.build_runs_stats(runs)
        e = par_agent["bmad-revue"]
        assert e["n"] == 0 and e["en_attente_validation"] == 1

    def test_repartition_reelle_mesuree(self):
        """Chiffres de controle donnes par l'orchestrateur (mesures sur les 80 runs
        reels de runs.jsonl) : verifie les 5 playbooks/absence-de-playbook d'un coup."""
        runs = (
            [_run("succes", "evolution-flotte") for _ in range(30)]
            + [_run("en-attente-validation", "evolution-flotte") for _ in range(4)]
            + [_run("partiel", "evolution-flotte") for _ in range(2)]
            + [_run("succes", "dev-verifie") for _ in range(4)]
            + [_run("succes", "revue-design-parallele") for _ in range(1)]
            + [_run("succes", None) for _ in range(37)]
            + [_run("partiel", None) for _ in range(1)]
            + [_run("en-attente-validation", None) for _ in range(1)]
        )
        par_playbook, _ = scan.build_runs_stats(runs)
        assert par_playbook["evolution-flotte"]["n"] == 30
        assert par_playbook["evolution-flotte"]["succes"] == 30
        assert par_playbook["evolution-flotte"]["echecs"] == 0
        assert par_playbook["dev-verifie"] == {
            "n": 4, "succes": 4, "echecs": 0, "reprises": 0, "en_cours": 0,
            "en_attente_validation": 0, "partiels": 0,
        }
        assert par_playbook["revue-design-parallele"]["n"] == 1
        assert "export-ppt-verifie" not in par_playbook  # 0 run reel
        assert None not in par_playbook  # les runs "sans playbook" ne cumulent pas sous None


class TestDocLiensMorts:
    """Correctif mineur 4 : docs/reflexions/agent-superviseur.md et
    agent-orchestrateur.md n'ont jamais existe (verifie : ni sur disque, ni dans
    `git log --all`). Le canon ne doit plus y referer."""

    def _source(self):
        with open(os.path.join(CANON, "scan_transcripts.py"), encoding="utf-8") as fh:
            return fh.read()

    def test_pas_de_reference_a_agent_superviseur_md(self):
        assert "docs/reflexions/agent-superviseur.md" not in self._source()

    def test_pas_de_reference_a_agent_orchestrateur_md(self):
        assert "docs/reflexions/agent-orchestrateur.md" not in self._source()


class TestInventaireSkillsBmadComplet:
    """Correctif mineur 3 : invoquees + jamais-invoquees (+ bibliotheque/reference)
    doit toujours retomber sur le total reel de dossiers .claude/skills/bmad-*, sans
    qu'aucune skill installee ne disparaisse du decompte."""

    def _repartition_bmad(self, fam, skills):
        """Reproduit exactement la partition faite par build_page/build_html_section
        (canon `scan_transcripts.py`, ~l. 851-861 et 996-1005) : chaque skill de `fam`
        doit atterrir dans exactement un des trois seaux."""
        libref = scan.non_invocation_skills(fam)
        unused_by_family = {}
        libref_unused = []
        for name, family in fam.items():
            if name in skills:
                continue
            if name in libref:
                libref_unused.append(name)
            else:
                unused_by_family.setdefault(family, []).append(name)
        return unused_by_family.get("BMAD", []), libref_unused

    def test_toutes_les_skills_bmad_sont_comptees_quelque_part(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scan, "REPO", str(tmp_path))
        monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path / "faux-home"))
        skills_dir = tmp_path / ".claude" / "skills"
        noms = [f"bmad-outil-{i}" for i in range(45)] + ["bmad-qa-generate-e2e-tests"]
        for n in noms:
            (skills_dir / n).mkdir(parents=True)
        fam = scan.installed_skills()
        assert len(fam) == 46
        invoques = {"bmad-outil-0": {"n": 1}, "bmad-outil-1": {"n": 3}}
        jamais, libref_unused = self._repartition_bmad(fam, invoques)
        total_family = sum(1 for v in fam.values() if v == "BMAD")
        assert total_family == 46
        # Invariant du correctif : invoquees + jamais-invoquees (+ bibliotheque) = total.
        assert len(invoques) + len(jamais) + len(libref_unused) == total_family
        assert "bmad-qa-generate-e2e-tests" in jamais, (
            "une skill BMAD installee et jamais invoquee doit apparaitre dans la "
            "liste des jamais-invoquees -- elle ne peut disparaitre du decompte")
