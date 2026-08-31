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
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT = os.path.join(RACINE, "export")


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

    def test_le_manifeste_couvre_les_huit_sous_agents(self, generateur):
        """Leur absence rendait irréalisable tout plan qui les dispatche."""
        agents = {rel for _s, rel, _d in generateur.MANIFESTE if rel.startswith("agents/")}
        assert len(agents) == 8, f"attendu 8 sous-agents, trouve {sorted(agents)}"

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


class TestInstallation:
    def test_installe_les_fichiers_du_manifeste(self, installateur, tmp_path):
        cible = tmp_path / "projet"
        cible.mkdir()
        assert installateur.installer(str(cible), "Demo", force=False, dry_run=False) == 0
        assert (cible / ".claude" / "skills" / "agent-orchestrator" / "SKILL.md").is_file()
        assert len(list((cible / ".claude" / "agents").glob("*.md"))) == 8
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
