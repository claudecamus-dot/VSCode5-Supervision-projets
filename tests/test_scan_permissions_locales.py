"""Le canal LOCAL des permissions n'est plus un angle mort du scan.

Arbitrage `flotte:rtk-settings-local` (2026-09-01, option « purger + outiller »).

Le fait qui l'a ouvert : l'arbitrage `flotte:rtk` du 2026-07-29 annonçait le retrait
de `rtk` « de toute la flotte, permissions comprises ». Le canal versionné était bien
purgé — mais `Bash(rtk *)` survivait dans TROIS `settings.local.json` (11 permissions
sur 3 dépôts), et l'ensemble de permissions EFFECTIF autorisait donc toujours l'outil
là où le titre le déclarait retiré.

La cause est structurelle, pas un oubli : `settings.local.json` est git-ignoré, donc
un commit scopé (R2) ne pouvait par construction pas le voir, et le scan ne lisait que
`settings.json`. Un retrait de flotte s'arrêtait à la frontière du versionné **en
silence** — c'est le silence qui est le défaut, pas les 11 lignes.

Ces tests verrouillent la mesure, pas la purge : ils passent des répertoires fabriqués
et n'assertent rien sur l'état des cinq dépôts réels (les deux tests de
`test_check_flotte.py` qui assertent une propriété du monde ont déjà été qualifiés de
défaut par l'audit du 2026-09-01 — on ne recommence pas).
"""

import importlib.util
import io
import json
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "scan_projets_perms", os.path.join(HUB, "scripts", "scan_projets.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def _projet(tmp_path, versionne=None, local=None):
    d = tmp_path / ".claude"
    d.mkdir(parents=True)
    if versionne is not None:
        io.open(d / "settings.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": {"allow": versionne}}))
    if local is not None:
        io.open(d / "settings.local.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": {"allow": local}}))
    return str(tmp_path)


class TestLeCanalLocalEstMesure:

    def test_une_permission_du_seul_canal_local_est_vue(self, tmp_path):
        chemin = _projet(tmp_path, versionne=["Bash(git *)"],
                         local=["Bash(rtk find *)"])
        c = scan.permissions_par_canal(chemin)
        assert "Bash(rtk find *)" in c["local"]
        assert "Bash(rtk find *)" in c["local_seules"], (
            "une permission qui n'existe QUE dans le canal git-ignore n'est pas "
            "signalee : c'est exactement le silence de flotte:rtk")
        assert "Bash(git *)" not in c["local_seules"]

    def test_le_canal_local_absent_ne_casse_rien(self, tmp_path):
        chemin = _projet(tmp_path, versionne=["Bash(git *)"])
        c = scan.permissions_par_canal(chemin)
        assert c["local"] == [] and c["local_seules"] == []
        assert c["versionne"] == ["Bash(git *)"]

    def test_un_json_local_illisible_ne_fait_pas_tomber_le_scan(self, tmp_path):
        chemin = _projet(tmp_path, versionne=["Bash(git *)"])
        io.open(os.path.join(chemin, ".claude", "settings.local.json"),
                "w", encoding="utf-8").write("{ pas du json")
        c = scan.permissions_par_canal(chemin)
        assert c["local"] == [], "le scan doit degrader, jamais planter"

    def test_les_trois_familles_de_permissions_sont_balayees(self, tmp_path):
        """`deny` et `ask` comptent autant qu'`allow` : un `deny` posé seulement en
        local donne une garantie que le canal versionné ne porte pas."""
        d = tmp_path / ".claude"
        d.mkdir(parents=True)
        io.open(d / "settings.json", "w", encoding="utf-8").write(json.dumps({}))
        io.open(d / "settings.local.json", "w", encoding="utf-8").write(json.dumps(
            {"permissions": {"deny": ["Bash(rm -rf *)"], "ask": ["Bash(curl *)"]}}))
        c = scan.permissions_par_canal(str(tmp_path))
        assert "Bash(rm -rf *)" in c["local"] and "Bash(curl *)" in c["local"]

    def test_la_pratique_securite_voit_un_deny_pose_en_local(self, tmp_path):
        """Avant l'outillage, un projet dont les deny rules vivaient en local était
        noté comme n'en ayant aucune — sous-évaluation, pas seulement silence."""
        d = tmp_path / ".claude"
        d.mkdir(parents=True)
        io.open(d / "settings.json", "w", encoding="utf-8").write(json.dumps({}))
        io.open(d / "settings.local.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": {"deny": ["Bash(rm -rf /)"]}}))
        res = scan.analyse_pratiques(str(tmp_path), [], [])
        assert "deny rules" in res["securite_proxy"]["detail"]

    def test_le_canal_local_est_RENDU_pas_seulement_mesure(self, tmp_path):
        """Un compteur qu'aucune page n'affiche reproduit le silence qu'il ferme.

        Le detail de la dimension « Sécurité (proxy) » est rendu tel quel dans le
        wiki : c'est le seul endroit ou la mesure atteint un lecteur humain.
        """
        d = tmp_path / ".claude"
        d.mkdir(parents=True)
        io.open(d / "settings.json", "w", encoding="utf-8").write(json.dumps({}))
        io.open(d / "settings.local.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": {"allow": ["Bash(rtk find *)"]}}))
        res = scan.analyse_pratiques(str(tmp_path), [], [])
        assert "hors git" in res["securite_proxy"]["detail"], (
            "la mesure existe mais n'apparait nulle part pour un humain")

    def test_aucune_permission_locale_ne_produit_aucun_bruit(self, tmp_path):
        chemin = _projet(tmp_path, versionne=["Bash(git *)"])
        res = scan.analyse_pratiques(chemin, [], [])
        assert "hors git" not in res["securite_proxy"]["detail"]
