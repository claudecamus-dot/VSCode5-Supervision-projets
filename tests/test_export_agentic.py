"""Tests du kit d'export agentic — `export_agentic.py` (génération) et
`install_agentic.py` (installation dans un projet cible).

Ce que ces tests protègent, et pourquoi. Le défaut trouvé le 2026-08-31 n'était pas
un bug de code mais une **source périmée** : le déploiement servait aux nouveaux
projets une skill orchestrateur de 120 lignes quand le hub en avait 467, parce que la
source vivait dans un autre dépôt figé depuis un mois. Un kit qui se génère sans
détecter sa propre dérive reproduirait exactement ce silence — d'où le test de dérive,
qui vérifie que `--check` **échoue** quand une copie diverge de sa source.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(RACINE, "export")


def _nb_tests_collectes(args: list[str]) -> int:
    """Lance `pytest --collect-only -q` avec les `args` donnés et rend le compte
    annoncé sur la dernière ligne (« N tests collected » / « no tests ran »)."""
    resultat = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        cwd=RACINE, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", resultat.stdout)
    assert m, f"sortie de collecte inattendue :\n{resultat.stdout}\n{resultat.stderr}"
    return int(m.group(1))


def _charger(chemin: str, nom: str):
    """Charge un module par chemin, sans laisser de bytecode derrière.

    `install_agentic.py` vit dans `export/`, qui est un livrable copié tel quel sur
    d'autres machines : l'importer y écrirait un `__pycache__` que le kit emporterait.
    La suite ne doit pas salir l'artefact qu'elle vérifie — sans cette précaution, le
    test de propreté échoue sur un déchet qu'il a lui-même produit.
    """
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    ancien = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = ancien
    return module


@pytest.fixture(scope="module")
def generateur():
    return _charger(os.path.join(RACINE, ".claude", "dispositif", "export_agentic.py"), "export_agentic")


@pytest.fixture(scope="module")
def installateur():
    return _charger(os.path.join(EXPORT, "install_agentic.py"), "install_agentic")


class TestManifeste:
    def test_toutes_les_sources_du_manifeste_existent(self, generateur):
        """Une source absente publierait un kit incomplet sans le dire."""
        absentes = [rel for src, rel, _ in generateur.MANIFESTE if not os.path.isfile(src)]
        assert absentes == [], f"sources introuvables : {absentes}"

    def test_le_manifeste_couvre_tous_les_sous_agents_actifs(self, generateur):
        """Leur absence rendait irréalisable tout plan qui les dispatche.

        Le compte était ÉCRIT EN DUR (`== 8`). Mettre quatre porteurs en sommeil le
        2026-09-01 faisait donc échouer le test sur la TAILLE de la population, pas
        sur ce qu'il garde : que le kit publié emporte exactement les porteurs
        adressables, ni plus (un agent endormi qui partirait quand même) ni moins
        (un porteur actif absent du kit). Il compare maintenant au répertoire.
        """
        actifs = {f[:-3] for f in os.listdir(os.path.join(RACINE, ".claude", "agents"))
                  if f.endswith(".md")}
        assert actifs, ".claude/agents/ est vide"
        publies = {rel.split("/")[-1][:-3] for _s, rel, _d in generateur.MANIFESTE
                   if rel.startswith("agents/")}
        assert publies == actifs, f"kit={sorted(publies)} vs depot={sorted(actifs)}"

    def test_l_installateur_n_a_pas_de_destination_projet(self, generateur):
        """install_agentic.py outille l'export, il ne s'installe pas dans la cible."""
        entrees = {rel: dst for _s, rel, dst in generateur.MANIFESTE}
        assert entrees["install_agentic.py"] is None

    def test_les_destinations_sont_relatives_et_sans_remontee(self, generateur):
        for _src, _rel, dst in generateur.MANIFESTE:
            if dst is None:
                continue
            assert not os.path.isabs(dst) and ".." not in dst.split("/"), dst

    def test_toute_skill_a_cadence_part_avec_son_hook_de_cadence(self, generateur):
        """Une skill sans sa cadence n'est jamais lancée.

        Mesuré au hub le 2026-08-31 : la veille avait 32 jours de retard pour une
        cadence de 3. Exporter `veille-agentic` sans `remind_veille_agentic.py`
        installerait ce silence chez chaque projet équipé.
        """
        exportes = {rel for _s, rel, _d in generateur.MANIFESTE}
        paires = {"skills/veille-agentic/SKILL.md": "hooks/remind_veille_agentic.py",
                  "skills/revue-increment/SKILL.md": "hooks/remind_revue_increment.py"}
        for skill, hook in paires.items():
            if skill in exportes:
                assert hook in exportes, f"{skill} est exportee sans sa cadence {hook}"

    def test_les_hooks_exportes_sont_tous_cables_dans_le_gabarit(self, generateur):
        """Un hook installé mais non câblé ne se déclenche jamais."""
        commandes = " ".join(
            h["command"]
            for groupes in generateur.SETTINGS_TEMPLATE["hooks"].values()
            for groupe in groupes for h in groupe["hooks"])
        for _src, rel, _dst in generateur.MANIFESTE:
            if rel.startswith("hooks/"):
                assert os.path.basename(rel) in commandes, f"hook non cable : {rel}"


class TestConfigPytest:
    """Sans `[tool.pytest.ini_options]` dans pyproject.toml, `pytest` lancé à la
    racine déborde dans `export/` (skills pdf-quality, pptx-framed-image,
    slide-text-polish : 46 tests) et y importe du code, ce qui y crée des
    `__pycache__` — la suite se pollue elle-même et fait échouer
    `TestProprete.test_le_kit_publie_ne_contient_pas_de_bytecode`, avec un verdict
    qui dépend alors de la commande employée (`pytest` vs `pytest tests/`)."""

    def test_la_collecte_racine_egale_celle_de_tests(self):
        racine = _nb_tests_collectes([])
        cible = _nb_tests_collectes(["tests/"])
        assert racine == cible, (
            f"collecte racine ({racine}) != collecte tests/ ({cible}) : "
            "pytest deborde hors de tests/ (export/, _bmad/, .claude/skills/...)")

    def test_la_collecte_racine_n_importe_pas_export(self):
        resultat = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=RACINE, capture_output=True, text=True)
        assert "export" + os.sep not in resultat.stdout and "export/" not in resultat.stdout, (
            f"la collecte racine remonte des tests sous export/ :\n{resultat.stdout}")


class TestProprete:
    def test_le_kit_publie_ne_contient_pas_de_bytecode(self):
        """Le kit se copie tel quel sur une autre machine : il publie du code, pas des .pyc."""
        intrus = [os.path.join(r, f) for r, _d, fs in os.walk(EXPORT)
                  for f in fs if f.endswith(".pyc")]
        caches = [r for r, _d, _f in os.walk(EXPORT) if os.path.basename(r) == "__pycache__"]
        assert intrus == [] and caches == [], f"bytecode publie : {caches or intrus}"


class TestDerive:
    def test_export_genere_est_a_jour(self, generateur):
        """Le dépôt ne doit pas contenir un export/ divergent de ses sources."""
        assert generateur.verifier() == 0, "export/ a derive : py .claude/dispositif/export_agentic.py"

    def test_une_copie_modifiee_est_signalee(self, generateur, tmp_path, monkeypatch):
        """Le garde-fou central : sans lui, le kit repart en silence.

        L'altération conserve **la taille et la date** du fichier — c'est le cas qui
        discrimine : une comparaison superficielle (`filecmp.cmp(shallow=True)`, qui
        ne regarde que la signature `os.stat`) laisse passer cette dérive-là, et le
        test a bien été vu rouge avec elle avant d'être cru. Une simple ligne ajoutée
        ne prouverait rien, la taille suffisant alors à la détecter.
        """
        faux_export = tmp_path / "export"
        for src, rel, _dst in generateur.MANIFESTE:
            cible = faux_export / rel
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(open(src, "rb").read())
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        assert generateur.verifier() == 0

        victime = faux_export / "skills" / "agent-orchestrator" / "SKILL.md"
        avant = victime.stat()
        contenu = victime.read_bytes()
        assert b"orchestrateur" in contenu
        victime.write_bytes(contenu.replace(b"orchestrateur", b"0rchestrateur", 1))
        os.utime(victime, (avant.st_atime, avant.st_mtime))
        assert victime.stat().st_size == avant.st_size, "l'alteration doit conserver la taille"
        assert generateur.verifier() == 1, "une copie divergente doit faire echouer --check"

    def test_une_copie_absente_est_signalee(self, generateur, tmp_path, monkeypatch):
        monkeypatch.setattr(generateur, "EXPORT", str(tmp_path / "vide"))
        assert generateur.verifier() == 1

    def _export_a_jour(self, generateur, tmp_path):
        """Reconstruit un export/ complet et à jour, comme les tests de dérive
        ci-dessus — base saine pour y ajouter un orphelin."""
        faux_export = tmp_path / "export"
        for src, rel, _dst in generateur.MANIFESTE:
            cible = faux_export / rel
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(open(src, "rb").read())
        return faux_export

    def test_un_fichier_orphelin_non_bytecode_est_signale(self, generateur, tmp_path, monkeypatch):
        """Trou trouvé le 2026-08-31 : `verifier()` ne compare que le manifeste vers
        export/, jamais l'inverse. `--check` restait vert (47/47 à jour) alors que
        export/ contenait réellement 57 fichiers — 10 de trop. Même angle mort pour
        un fichier RETIRÉ du manifeste : sa copie périmée resterait éternellement
        dans le kit publié sans que `--check` le voie."""
        faux_export = self._export_a_jour(generateur, tmp_path)
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        assert generateur.verifier() == 0

        orphelin = faux_export / "skills" / "un-fichier-retire-du-manifeste.md"
        orphelin.write_text("copie perimee, plus dans le manifeste", encoding="utf-8")
        assert generateur.verifier() == 1, "un fichier orphelin (hors manifeste) doit faire echouer --check"

    def test_un_orphelin_bytecode_n_est_pas_signale(self, generateur, tmp_path, monkeypatch):
        """Choix assumé : __pycache__/*.pyc ne comptent pas comme orphelins ici — ce
        sont des artefacts d'exécution locale, pas des fichiers du kit publié, et
        TestProprete.test_le_kit_publie_ne_contient_pas_de_bytecode les couvre déjà
        (avec un message dédié « bytecode publié », plus lisible qu'un ORPHELIN
        générique). `--check` resterait donc vert sur du bytecode seul."""
        faux_export = self._export_a_jour(generateur, tmp_path)
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))

        cache = faux_export / "skills" / "agent-orchestrator" / "__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "SKILL.cpython-314.pyc").write_bytes(b"\x00\x01")
        assert generateur.verifier() == 0, "un orphelin purement bytecode ne doit pas faire echouer --check"

    def test_manifeste_json_et_readme_ne_sont_pas_de_faux_orphelins(self, generateur, tmp_path, monkeypatch):
        """MANIFESTE.json et README.md sont écrits par generer() mais n'apparaissent
        pas dans MANIFESTE : sans exception explicite, --check se signalerait
        orphelin lui-même sur son propre export a jour, en boucle sur chaque run."""
        faux_export = self._export_a_jour(generateur, tmp_path)
        (faux_export / "MANIFESTE.json").write_text("{}", encoding="utf-8")
        (faux_export / "README.md").write_text("# export", encoding="utf-8")
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        assert generateur.verifier() == 0


class TestInstallation:
    def test_installe_les_fichiers_du_manifeste(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        assert installateur.installer(str(cible), "Demo", force=False, dry_run=False) == 0
        assert (cible / ".claude" / "skills" / "agent-orchestrator" / "SKILL.md").is_file()
        actifs = [f for f in os.listdir(os.path.join(RACINE, ".claude", "agents"))
                  if f.endswith(".md")]
        assert len(list((cible / ".claude" / "agents").glob("*.md"))) == len(actifs)
        assert (cible / "CLAUDE.md").is_file()

    def test_dry_run_n_ecrit_rien(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        installateur.installer(str(cible), "Demo", force=False, dry_run=True)
        assert list(cible.iterdir()) == []

    def test_le_squelette_claude_md_porte_le_nom_du_projet(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        installateur.installer(str(cible), "MonProjet", force=False, dry_run=False)
        assert "# MonProjet" in (cible / "CLAUDE.md").read_text(encoding="utf-8")

    def test_sans_force_un_fichier_existant_est_conserve(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        (cible / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        garde = cible / ".claude" / "skills" / "agent-orchestrator" / "SKILL.md"
        garde.write_text("version locale a ne pas ecraser", encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        assert garde.read_text(encoding="utf-8") == "version locale a ne pas ecraser"

    def test_avec_force_le_fichier_est_remplace(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        (cible / ".claude" / "skills" / "agent-orchestrator").mkdir(parents=True)
        garde = cible / ".claude" / "skills" / "agent-orchestrator" / "SKILL.md"
        garde.write_text("version locale", encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        assert garde.read_text(encoding="utf-8") != "version locale"


class TestFusionSettings:
    def _settings(self, cible) -> dict:
        return json.loads((cible / ".claude" / "settings.json").read_text(encoding="utf-8"))

    def _commandes(self, settings: dict) -> list[str]:
        return [h["command"] for groupes in settings["hooks"].values()
                for groupe in groupes for h in groupe["hooks"]]

    def test_les_hooks_du_projet_cible_survivent(self, installateur, tmp_path):
        """Un settings.json appartient au projet : on ajoute, on ne retire jamais."""
        cible = tmp_path / "projet"
        (cible / ".claude").mkdir(parents=True)
        (cible / ".claude" / "settings.json").write_text(json.dumps({
            "permissions": {"deny": ["Read(./maison/**)"]},
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "py hook-maison.py"}]}]},
        }), encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        settings = self._settings(cible)
        assert "py hook-maison.py" in self._commandes(settings)
        assert "Read(./maison/**)" in settings["permissions"]["deny"]

    def test_reinstaller_ne_duplique_pas_les_hooks(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        premier = self._commandes(self._settings(cible))
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        second = self._commandes(self._settings(cible))
        assert premier == second
        assert len(second) == len(set(second))

    def test_les_hooks_du_dispositif_sont_tous_cables(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        commandes = " ".join(self._commandes(self._settings(cible)))
        for attendu in ("guard_destructive_git.py", "warn_verif_before_commit.py",
                        "orchestrator_gate.py", "scan_transcripts.py",
                        "remind_revue_increment.py", "log_usage.py"):
            assert attendu in commandes, f"hook non cable : {attendu}"

    def test_un_hook_deja_present_ecrit_autrement_n_est_pas_duplique(self, installateur, tmp_path):
        """L'identite d'un hook est le script qu'il lance, pas sa ligne de commande.

        Mesure du 2026-08-31 : VSCode2 et VSCode3 ecrivaient `${CLAUDE_PROJECT_DIR}` avec
        accolades la ou le gabarit ecrit `$CLAUDE_PROJECT_DIR` sans. Comparer les chaines
        completes a fait installer 6 a 7 hooks en double, chacun execute deux fois par
        session. Ce test rejoue exactement cette orthographe.
        """
        cible = tmp_path / "projet"
        (cible / ".claude").mkdir(parents=True)
        (cible / ".claude" / "settings.json").write_text(json.dumps({
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{
                "type": "command",
                "command": 'py "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_destructive_git.py"',
            }]}]},
        }), encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        commandes = self._commandes(self._settings(cible))
        gardes = [c for c in commandes if "guard_destructive_git.py" in c]
        assert len(gardes) == 1, f"hook duplique par difference d'ecriture : {gardes}"

    def test_identite_de_hook_insensible_a_l_ecriture(self, installateur):
        variantes = [
            'py "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard_destructive_git.py"',
            'py "$CLAUDE_PROJECT_DIR/.claude/hooks/guard_destructive_git.py"',
            "python C:/un/chemin/absolu/.claude/hooks/guard_destructive_git.py",
            r'py "C:\projet\.claude\hooks\guard_destructive_git.py"',
        ]
        rendus = {installateur._script_du_hook(v) for v in variantes}
        assert rendus == {"guard_destructive_git.py"}, rendus

    def test_un_settings_illisible_n_est_pas_ecrase_sans_force(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        (cible / ".claude").mkdir(parents=True)
        casse = cible / ".claude" / "settings.json"
        casse.write_text("{ pas du json", encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        assert casse.read_text(encoding="utf-8") == "{ pas du json"


class TestDeploiementHistorique:
    def test_le_deploiement_lit_desormais_l_export_du_hub(self):
        """Le wiki lit ce MANIFEST : il doit pointer sur export/, pas sur un autre dépôt."""
        module = _charger(
            os.path.join(RACINE, ".claude", "dispositif", "package", "deploy_nouveau_projet.py"),
            "deploy_nouveau_projet")
        sources = [src for src, _dst in module.MANIFEST]
        assert not any(os.path.join("VSCode2", "export") in s for s in sources), \
            "le deploiement pointe encore sur le kit fige de VSCode2"
        assert any(os.path.join(RACINE, "export") in s for s in sources)
        absentes = [s for s in sources if not os.path.exists(s)]
        assert absentes == [], f"sources de deploiement introuvables : {absentes}"


class TestLInstallateurNEcritJamaisHorsDeLaCible:
    """Défaut `install_agentic.py:124-126`, audit technique du 2026-09-01, gravité critique.

    `dst = os.path.join(cible, entree["destination"])` sans validation, alors que
    `MANIFESTE.json` **voyage avec le kit auto-portant** : il n'est pas forcément celui
    que le hub a écrit. Une destination `../DEPOT_VOISIN/...` ou absolue écrivait hors
    de la cible, en rapportant une ligne « ecrit » ordinaire et en sortant avec 0.
    Reproduit par l'audit : `ecrit HORS du repertoire cible ? True`.

    Le test existant garde la liste du manifeste TEL QUE LE HUB LE GÉNÈRE — pas
    l'entrée d'exécution. Mesurer ce qu'on écrit soi-même ne dit rien de ce qu'on
    accepte de l'extérieur.
    """

    @staticmethod
    def _faux_kit(tmp_path, destination):
        """Un export/ minimal portant UNE entrée de manifeste, choisie par le test."""
        kit = tmp_path / "kit"
        (kit / "skills").mkdir(parents=True)
        (kit / "skills" / "charge.md").write_text("charge utile", encoding="utf-8")
        (kit / "MANIFESTE.json").write_text(json.dumps({
            "genere_le": "2026-09-01",
            "fichiers": [{"export": "skills/charge.md", "destination": destination}],
        }), encoding="utf-8")
        return kit

    def _installer_avec(self, installateur, monkeypatch, tmp_path, destination):
        kit = self._faux_kit(tmp_path, destination)
        monkeypatch.setattr(installateur, "EXPORT_DIR", str(kit))
        monkeypatch.setattr(installateur, "MANIFESTE", str(kit / "MANIFESTE.json"))
        cible = tmp_path / "cible"
        cible.mkdir()
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        return tmp_path, cible

    def test_une_destination_relative_qui_remonte_est_refusee(
            self, installateur, monkeypatch, tmp_path):
        racine, _cible = self._installer_avec(
            installateur, monkeypatch, tmp_path,
            "../DEPOT_VOISIN/.claude/hooks/porte_derobee.py")
        intrus = racine / "DEPOT_VOISIN"
        assert not intrus.exists(), (
            f"l'installateur a ecrit hors de la cible : {intrus}")

    def test_une_destination_absolue_est_refusee(
            self, installateur, monkeypatch, tmp_path):
        hors = tmp_path / "AILLEURS" / "vole.py"
        self._installer_avec(installateur, monkeypatch, tmp_path, str(hors))
        assert not hors.exists(), "une destination absolue a ete honoree"

    def test_une_destination_normale_passe_toujours(
            self, installateur, monkeypatch, tmp_path):
        """Le garde-fou ne doit pas devenir un mur : le cas nominal reste écrit,
        sinon on aurait remplacé une faille par une panne."""
        _racine, cible = self._installer_avec(
            installateur, monkeypatch, tmp_path, ".claude/skills/charge.md")
        assert (cible / ".claude" / "skills" / "charge.md").is_file()


class TestLInstallateurNeDetruitPasLeTravailDeLaCible:
    """Défaut `install_agentic.py:157-164`, audit du 2026-09-01, gravité critique.

    `--force` écrasait le `CLAUDE.md` **rédigé** de la cible par le squelette vide,
    sans sauvegarde, et le rapportait comme « ecrit CLAUDE.md (squelette a completer) ».
    Reproduit par l'audit : 3 lignes de règles métier remplacées par 30 lignes de
    gabarit, exit 0. `--force` sert à rafraîchir les fichiers DU KIT ; les règles
    projet de la cible ne lui appartiennent pas.
    """

    def test_avec_force_un_claude_md_redige_survit(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        regles = "# Mon projet\n\nRegle metier 1.\nRegle metier 2.\n"
        (cible / "CLAUDE.md").write_text(regles, encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        assert (cible / "CLAUDE.md").read_text(encoding="utf-8") == regles, (
            "le CLAUDE.md redige de la cible a ete ecrase par le squelette")

    def test_le_squelette_propose_reste_accessible(self, installateur, tmp_path):
        """Refuser n'est pas perdre : le squelette est posé à côté pour que la cible
        puisse le reprendre à la main."""
        cible = tmp_path / "projet"
        cible.mkdir()
        (cible / "CLAUDE.md").write_text("# Mon projet\nRegle.\n", encoding="utf-8")
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        assert (cible / "CLAUDE.md.propose").is_file(), (
            "le squelette n'est ni ecrit ni propose : il est perdu")

    def test_sans_claude_md_le_squelette_est_bien_ecrit(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        installateur.installer(str(cible), "Demo", force=True, dry_run=False)
        assert (cible / "CLAUDE.md").is_file()
        assert not (cible / "CLAUDE.md.propose").exists()


class TestUneInstallationNeSInterrompJamaisAMiParcours:
    """Défaut `install_agentic.py:83-104`, audit du 2026-09-01.

    `_fusionner_settings` plantait en `AttributeError` sur un `settings.json`
    JSON-valide mais de forme inattendue (une liste) : le try/except ne couvrait que
    `json.load`. Le crash survenait **après** la copie des 47 fichiers, sans rollback,
    et la checklist finale n'était jamais affichée — l'installateur laissait la cible
    à moitié équipée en ayant l'air d'avoir echoué au debut.
    """

    def test_un_settings_json_de_forme_inattendue_ne_plante_pas(
            self, installateur, tmp_path):
        cible = tmp_path / "projet"
        (cible / ".claude").mkdir(parents=True)
        (cible / ".claude" / "settings.json").write_text("[]", encoding="utf-8")
        code = installateur.installer(str(cible), "Demo", force=False, dry_run=False)
        assert code == 0
        assert (cible / ".claude" / "skills" / "agent-orchestrator" / "SKILL.md").is_file(), (
            "l'installation s'est interrompue avant la fin")

    def test_le_verdict_de_fusion_dit_ce_qui_s_est_passe(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        (cible / ".claude").mkdir(parents=True)
        (cible / ".claude" / "settings.json").write_text("[]", encoding="utf-8")
        verdict = installateur._fusionner_settings(
            str(cible), {"permissions": {"deny": ["Read(./secrets/**)"]}}, force=False)
        assert verdict.startswith("ECHEC"), (
            f"une forme inattendue passe pour une fusion reussie : {verdict}")


class TestLeRemedePrescritCorrigeVraimentLOrphelin:
    """Défaut `export_agentic.py:364-366 + 558-599`, audit technique du 2026-09-01.

    `verifier()` détecte un ORPHELIN — un fichier sous `export/` sorti du manifeste —
    et prescrit « regenerer avec : py .claude/dispositif/export_agentic.py ». Mais
    `generer()` ne supprimait jamais rien : le remède ne corrigeait pas le défaut qu'il
    nommait, et `--check` restait rouge indéfiniment. Reproduit par l'audit :
    `--check exit 1` → `generer()` → `orphelin existe encore ? True` → `--check exit 1`.

    Un garde-fou dont le remède prescrit ne remédie pas finit ignoré — même mécanique
    que le hook pré-commit qui criait à tort, et que le `lignes_perdues` qui ne pouvait
    pas crier du tout. `export/` étant ENTIÈREMENT généré, y retirer un fichier sorti du
    manifeste est le geste juste, et git le rend réversible.
    """

    def test_un_orphelin_est_retire_par_la_regeneration(self, generateur, tmp_path,
                                                        monkeypatch):
        faux_export = tmp_path / "export"
        faux_export.mkdir()
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        orphelin = faux_export / "sorti_du_manifeste.md"
        orphelin.write_text("copie perimee d'un fichier retire du manifeste",
                            encoding="utf-8")
        assert "sorti_du_manifeste.md" in generateur._orphelins(), (
            "ce test perd son objet si l'orphelin n'est pas detecte")
        generateur.generer()
        assert not orphelin.exists(), (
            "le remede prescrit par --check ne retire pas l'orphelin qu'il signale")

    def test_apres_regeneration_le_check_repasse_au_vert(self, generateur, tmp_path,
                                                         monkeypatch):
        """La boucle complète : c'est elle qui restait ouverte."""
        faux_export = tmp_path / "export2"
        faux_export.mkdir()
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        (faux_export / "intrus.md").write_text("intrus", encoding="utf-8")
        generateur.generer()
        assert generateur._orphelins() == []
        assert generateur.verifier() == 0, "--check reste rouge apres regeneration"

    def test_le_bytecode_n_est_pas_SIGNALE_comme_un_orphelin(self, generateur, tmp_path,
                                                             monkeypatch):
        """`__pycache__` est un artefact d'exécution locale, pas un fichier du kit.

        `generer()` le nettoie depuis toujours, par un chemin distinct et documenté
        (« le kit se copie tel quel sur une autre machine : il ne doit pas emporter de
        bytecode »). Ce qu'on vérifie ici, c'est qu'il ne remonte pas AUSSI comme
        ORPHELIN : `TestProprete` le couvre déjà avec un message dédié, plus lisible
        qu'un « ORPHELIN » générique, et le doublonner masquerait ce message.
        """
        faux_export = tmp_path / "export3"
        (faux_export / "__pycache__").mkdir(parents=True)
        (faux_export / "__pycache__" / "x.cpython-314.pyc").write_bytes(b"\x00")
        monkeypatch.setattr(generateur, "EXPORT", str(faux_export))
        assert generateur._orphelins() == [], (
            "le bytecode remonte comme ORPHELIN et masque le message dedie")
