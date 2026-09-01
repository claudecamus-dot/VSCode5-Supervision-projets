"""`export/` est scellé : ni édition manuelle silencieuse, ni intégrité invérifiable.

Demande utilisateur du 2026-09-01 (« sécurise les fichiers de export »), arbitrée sur
trois volets dont deux sont outillés ici. Le troisième — la revue de sécurité du contenu
publié — est une passe de lecture, pas un test.

CE QU'EST `export/`, et pourquoi il méritait mieux que rien. C'est un kit auto-portant
que le hub publie et que CINQ dépôts installent chez eux : des hooks qui s'exécutent au
démarrage de chaque session, un installateur qui écrit dans `.claude/` de la cible et
fusionne son `settings.json`, des scripts de supervision. Jusqu'ici il n'avait aucune
protection : ni règle d'édition, ni empreinte, ni contrôle à l'installation.

VOLET 1 — L'ÉDITION MANUELLE. `export/` est ENTIÈREMENT généré : une correction faite là
est perdue à la régénération suivante, en silence. `export_agentic.py --check` sait le
dire, mais rien ne l'appelait au moment qui compte, celui du commit. C'est ce garde-fou
manquant qui a laissé le déploiement servir, sans le dire, un `agent-orchestrator` de
120 lignes contre 467 au hub (mesuré le 2026-08-31).

VOLET 2 — L'INTÉGRITÉ. `MANIFESTE.json` listait les fichiers sans empreinte. Une cible ne
pouvait donc PAS vérifier que ce qu'elle installe est ce que le hub a publié — et le
manifeste VOYAGE AVEC LE KIT, donc il n'est pas forcément celui que le hub a écrit. Le
contrôle de destination posé le 2026-09-01 a fermé la moitié du trou (OÙ l'on écrit) ;
celui-ci ferme l'autre (QUOI l'on écrit).
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLeManifestePorteUneEmpreinte:

    def _manifeste(self):
        return json.load(io.open(os.path.join(HUB, "export", "MANIFESTE.json"),
                                 encoding="utf-8"))

    def test_chaque_fichier_publie_porte_son_sha256(self):
        sans = [e["export"] for e in self._manifeste()["fichiers"] if not e.get("sha256")]
        assert not sans, f"{len(sans)} fichier(s) publies sans empreinte : {sans[:4]}"

    def test_les_empreintes_correspondent_au_contenu_reel(self):
        """Une empreinte qui ne correspond pas est pire qu'aucune : elle rassure."""
        faux = []
        for e in self._manifeste()["fichiers"]:
            f = os.path.join(HUB, "export", e["export"].replace("/", os.sep))
            if not os.path.isfile(f):
                continue
            if hashlib.sha256(io.open(f, "rb").read()).hexdigest() != e.get("sha256"):
                faux.append(e["export"])
        assert not faux, f"empreinte fausse pour {faux[:4]}"


class TestLInstallateurRefuseUnFichierAltere:

    def _kit(self, tmp_path, contenu, empreinte):
        kit = tmp_path / "kit"
        (kit / "supervision").mkdir(parents=True)
        io.open(kit / "supervision" / "x.py", "w", encoding="utf-8",
                newline="\n").write(contenu)
        entree = {"export": "supervision/x.py",
                  "destination": ".claude/supervision/x.py"}
        if empreinte is not None:
            entree["sha256"] = empreinte
        io.open(kit / "MANIFESTE.json", "w", encoding="utf-8").write(json.dumps({
            "fichiers": [entree],
            "settings_template": {}, "claude_md_template": "", "checklist": [],
        }))
        shutil.copy2(os.path.join(HUB, "export", "install_agentic.py"),
                     str(kit / "install_agentic.py"))
        return kit

    def _installer(self, kit, cible):
        return subprocess.run(
            [sys.executable, str(kit / "install_agentic.py"), str(cible), "--force"],
            capture_output=True, text=True, encoding="utf-8")

    def test_un_fichier_dont_lempreinte_ne_colle_pas_nest_PAS_installe(self, tmp_path):
        bon = hashlib.sha256(b"le vrai contenu\n").hexdigest()
        kit = self._kit(tmp_path, "un contenu ALTERE\n", bon)
        cible = tmp_path / "cible"
        cible.mkdir()
        r = self._installer(kit, cible)
        assert not (cible / ".claude" / "supervision" / "x.py").exists(), (
            "un fichier qui ne correspond pas a son empreinte a ete installe")
        assert "empreinte" in r.stdout.lower(), r.stdout
        assert r.returncode != 0, "l'installateur sort 0 apres avoir refuse un fichier"

    def test_un_fichier_conforme_sinstalle_normalement(self, tmp_path):
        contenu = "le vrai contenu\n"
        kit = self._kit(tmp_path, contenu,
                        hashlib.sha256(contenu.encode("utf-8")).hexdigest())
        cible = tmp_path / "cible"
        cible.mkdir()
        r = self._installer(kit, cible)
        assert (cible / ".claude" / "supervision" / "x.py").exists(), r.stdout

    def test_un_kit_ancien_sans_empreinte_sinstalle_encore(self, tmp_path):
        """Retro-compatibilite : une cible peut porter un kit publie avant ce volet.
        Refuser tout ce qui n'a pas d'empreinte transformerait une amelioration en
        panne de deploiement."""
        kit = self._kit(tmp_path, "contenu\n", None)
        cible = tmp_path / "cible"
        cible.mkdir()
        self._installer(kit, cible)
        assert (cible / ".claude" / "supervision" / "x.py").exists()


class TestLeHookRefuseUnCommitDExportDerive:
    """Le hook est appele comme le harnais l'appelle : JSON sur stdin, JSON en sortie.

    Les deux sondes couteuses (`git diff --cached`, `export_agentic.py --check`) sont
    surchargeables par variable d'environnement : sans cela le test mesurerait l'etat
    du depot au moment ou il tourne, pas le comportement du hook — la faute que les
    tests de `test_check_flotte.py` ont deja values au dispositif.
    """

    def _hook(self, staged, derive, commande="git commit -m x"):
        env = dict(os.environ)
        env["AGENT_SUPERVISION_TEST_STAGED"] = "\n".join(staged)
        env["AGENT_SUPERVISION_TEST_DERIVE"] = "1" if derive else "0"
        r = subprocess.run(
            [sys.executable, os.path.join(HUB, ".claude", "hooks",
                                          "guard_export_genere.py")],
            input=json.dumps({"tool_input": {"command": commande}}),
            capture_output=True, text=True, encoding="utf-8", env=env)
        return r.stdout

    def test_un_export_derive_en_cours_de_commit_est_refuse(self):
        out = self._hook(["export/skills/a/SKILL.md"], derive=True)
        assert "deny" in out, (
            "une edition manuelle d'export/ passe au commit et sera perdue en silence "
            "a la regeneration")
        assert "export_agentic" in out, "le refus ne dit pas la commande qui le repare"

    def test_un_export_a_jour_ne_bloque_rien(self):
        assert self._hook(["export/skills/a/SKILL.md"], derive=False).strip() == ""

    def test_un_commit_sans_export_ne_bloque_rien(self):
        assert self._hook(["scripts/scan_projets.py"], derive=True).strip() == ""

    def test_une_commande_qui_nest_pas_un_commit_ne_bloque_rien(self):
        assert self._hook(["export/x"], derive=True, commande="git status").strip() == ""
