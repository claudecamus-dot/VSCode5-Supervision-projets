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


class TestUneExpositionNeSeLitJamaisCommeUneProtection:
    """Finding `VSCode1:.claude/settings.local.json` (diagnostic du 2026-09-01, arbitre
    le jour meme). Defaut introduit LE MEME JOUR par le correctif qui devait fermer
    l'angle mort du canal local.

    Mesure : `docs/wiki/projets-supervision.md` l.254 rendait
    « 🟢 deny rules, guard git, 89 perm. hors git » sous une legende « Garde-fous
    PRESENTS ». Les 89 permissions git-ignorees, jamais revues — dont
    `Read(//c/Users/claude.camus/**)`, deux `Edit` sur les skills globales de
    l'utilisateur, `Bash(node -e ...)` a joker et `Skill(run:*)` — se lisaient comme un
    TROISIEME garde-fou, dans la meme liste separee par virgules, sous la meme pastille
    verte.

    C'est la famille de defaut que la journee entiere a corrigee, commise dans la
    mesure censee la fermer : une EXPOSITION rendue comme une PROTECTION. Deux regles en
    sortent, et ce sont elles que ces tests verrouillent :

    1. `local_seules` ne compte jamais parmi les garde-fous, ni dans le score ni dans la
       liste — il est marque et separe.
    2. Il entre dans la NOTATION : un ensemble de permissions qu'aucun commit ne peut
       relire n'est pas une posture verte. Le niveau est plafonne a `moyen`.
    """

    def _projet_avec(self, tmp_path, versionne, local):
        d = tmp_path / ".claude"
        d.mkdir(parents=True)
        io.open(d / "settings.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": versionne}))
        io.open(d / "settings.local.json", "w", encoding="utf-8").write(
            json.dumps({"permissions": {"allow": local}}))
        io.open(tmp_path / ".gitignore", "w", encoding="utf-8").write(".env\n")
        return str(tmp_path)

    def test_les_perm_hors_git_ne_sont_pas_dans_la_liste_des_garde_fous(self, tmp_path):
        chemin = self._projet_avec(tmp_path, {"deny": ["Bash(rm *)"]},
                                   ["Bash(node -e *)"])
        detail = scan.analyse_pratiques(chemin, [], [])["securite_proxy"]["detail"]
        avant_marqueur = detail.split("⚠")[0]
        assert "hors git" not in avant_marqueur, (
            "l'exposition est enumeree parmi les garde-fous, comme s'en etait un")

    def test_les_perm_hors_git_restent_VISIBLES_mais_marquees(self, tmp_path):
        chemin = self._projet_avec(tmp_path, {"deny": ["Bash(rm *)"]},
                                   ["Bash(node -e *)"])
        detail = scan.analyse_pratiques(chemin, [], [])["securite_proxy"]["detail"]
        assert "hors git" in detail, "la mesure a disparu, on revient au silence"
        assert "⚠" in detail, "rien ne distingue l'exposition de la protection"

    def test_les_perm_hors_git_ne_gonflent_pas_le_score(self, tmp_path):
        """Sans elles le projet est deja au maximum : elles ne doivent rien ajouter."""
        sans = self._projet_avec(tmp_path / "a", {"deny": ["Bash(rm *)"]}, [])
        avec = self._projet_avec(tmp_path / "b", {"deny": ["Bash(rm *)"]},
                                 ["Bash(node -e *)"])
        n_sans = scan.analyse_pratiques(sans, [], [])["securite_proxy"]["niveau"]
        n_avec = scan.analyse_pratiques(avec, [], [])["securite_proxy"]["niveau"]
        assert n_avec != "ok" or n_sans != "ok", (
            "ajouter des permissions non relisables ne peut pas laisser le vert intact")

    def test_un_ensemble_qu_aucun_commit_ne_relit_n_est_pas_vert(self, tmp_path):
        """La notation, pas seulement l'affichage : c'est la moitie du finding."""
        chemin = self._projet_avec(
            tmp_path, {"deny": ["Bash(rm *)"]}, ["Bash(node -e *)", "Skill(run:*)"])
        res = scan.analyse_pratiques(chemin, [], [])["securite_proxy"]
        assert res["niveau"] != "ok", (
            "2 garde-fous + 2 permissions hors git = pastille verte : "
            "la notation ignore ce que le detail signale")

    def test_sans_permission_hors_git_le_vert_reste_atteignable(self, tmp_path):
        """Le plafond ne doit pas devenir une penalite universelle."""
        chemin = self._projet_avec(tmp_path, {"deny": ["Bash(rm *)"]}, [])
        assert scan.analyse_pratiques(chemin, [], [])["securite_proxy"]["niveau"] == "ok"
