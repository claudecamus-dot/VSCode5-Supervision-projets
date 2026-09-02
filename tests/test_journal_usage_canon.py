"""Le TROISIÈME canal du canon : `usage.jsonl` lu par `scan_transcripts.py`.

Finding mesuré le 2026-09-02 (trouvaille de veille « seuil de dilution des skills »,
adoptée) : `dormants()` annonçait « tous canaux confondus » mais ses deux canaux
(`skills`, `subagents`) dérivaient des MÊMES transcripts — dont 126 sur 137 avaient
disparu du disque. Le tableau de bord publiait « Élaguer les skills BMAD : 43/46 jamais
invoqués » pendant que le journal du hook PostToolUse portait 8 invocations de
`bmad-code-review`, 10 de `bmad-review-edge-case-hunter`, 6 de
`bmad-review-adversarial-general` : cinq skills invoquées le jour même étaient comptées
mortes, et le TODO proposait d'élaguer ce qui venait de servir.

La séance qui a écrit `scan_journal_usage()` a été coupée par la limite de session
AVANT de l'appeler : une fonction définie et jamais lue. Ces tests verrouillent les
trois choses qui manquaient — l'appel, la lecture incrémentale, et l'usage du résultat
par les TODO et les hints.

Lancer : py -m pytest tests/test_journal_usage_canon.py -q --basetemp=C:/tmp/pt/ju
"""

import importlib.util
import json
import os

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(HUB, ".claude", "dispositif", "canon", "scan_transcripts.py")


def _load():
    spec = importlib.util.spec_from_file_location("canon_journal", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def canon(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "SUP_DIR", str(tmp_path))
    return mod


def _ecrire(tmp_path, morceaux, mode="w"):
    """Écrit les morceaux TELS QUELS (le test décide où sont les fins de ligne)."""
    with open(tmp_path / "usage.jsonl", mode, encoding="utf-8", newline="") as fh:
        fh.write("".join(morceaux))


def _l(skill=None, subagent=None, ts="2026-09-02T10:00:00+02:00"):
    d = {"ts": ts, "session_id": "s", "tool": "Skill" if skill else "Agent",
         "skill": skill, "subagent_type": subagent, "description": ""}
    return json.dumps(d) + "\n"


class TestLaLectureEstIncrementaleEtFailOpen:
    def test_journal_absent_rend_zero_sans_exception(self, canon):
        state = {}
        assert canon.scan_journal_usage(state) == 0
        assert state.get("skills_journal", {}) == {}

    def test_les_deux_canaux_du_journal_sont_agreges(self, canon, tmp_path):
        _ecrire(tmp_path, [_l(skill="bmad-code-review"),
                           _l(skill="bmad-code-review", ts="2026-09-02T11:00:00+02:00"),
                           _l(subagent="bmad-revue")])
        state = {}
        assert canon.scan_journal_usage(state) == 3
        assert state["skills_journal"]["bmad-code-review"]["n"] == 2
        assert state["skills_journal"]["bmad-code-review"]["last"] == "2026-09-02T11:00:00+02:00"
        assert state["subagents_journal"]["bmad-revue"]["n"] == 1

    def test_un_second_passage_ne_recompte_pas(self, canon, tmp_path):
        """Un scan qui relirait tout à chaque session doublerait les compteurs."""
        _ecrire(tmp_path, [_l(skill="x")])
        state = {}
        canon.scan_journal_usage(state)
        assert canon.scan_journal_usage(state) == 0
        assert state["skills_journal"]["x"]["n"] == 1
        _ecrire(tmp_path, [_l(skill="x")], mode="a")
        assert canon.scan_journal_usage(state) == 1
        assert state["skills_journal"]["x"]["n"] == 2

    def test_une_ligne_en_cours_d_ecriture_attend_le_passage_suivant(self, canon, tmp_path):
        _ecrire(tmp_path, [_l(skill="a"), '{"ts": "2026-09-02T12:00:00", "skill": "b"'])
        state = {}
        assert canon.scan_journal_usage(state) == 1
        assert "b" not in state["skills_journal"]
        _ecrire(tmp_path, [', "tool": "Skill"}\n'], mode="a")
        assert canon.scan_journal_usage(state) == 1
        assert state["skills_journal"]["b"]["n"] == 1

    def test_ligne_illisible_et_evenements_ignores(self, canon, tmp_path):
        stop = json.dumps({"ts": "2026-09-02T10:00:00", "event": "subagent-stop",
                           "skill": "ne-doit-pas-compter"}) + "\n"
        _ecrire(tmp_path, ["{ pas du json\n", stop, "[1, 2]\n", _l(skill="ok")])
        state = {}
        assert canon.scan_journal_usage(state) == 1
        assert set(state["skills_journal"]) == {"ok"}

    def test_un_journal_tronque_repart_de_zero(self, canon, tmp_path):
        _ecrire(tmp_path, [_l(skill="ancien")] * 5)
        state = {}
        canon.scan_journal_usage(state)
        assert state["usage_offset"] > 0
        _ecrire(tmp_path, [_l(skill="neuf")])           # remplacé par un journal plus court
        assert canon.scan_journal_usage(state) == 1
        assert set(state["skills_journal"]) == {"neuf"}

    def test_le_reset_detecteur_efface_aussi_ce_canal(self, canon):
        state = {"detector_version": -1, "skills_journal": {"x": {"n": 1, "last": "t"}},
                 "usage_offset": 42}
        assert canon.reset_si_detecteur_change(state)
        assert state["skills_journal"] == {} and "usage_offset" not in state


class TestLeCanalEstReellementLu:
    """La moitié qui manquait le 2026-09-02 à 18:17."""

    def test_main_appelle_scan_journal_usage(self):
        src = open(CANON, encoding="utf-8").read()
        corps = src[src.index("def main(argv)"):]
        assert "scan_journal_usage(state)" in corps, (
            "scan_journal_usage est définie mais jamais appelée : le canal reste mort")

    def test_derniers_usages_prend_le_max_sur_les_quatre_canaux(self, canon):
        state = {"skills": {"a": {"n": 1, "last": "2026-07-01"}},
                 "subagents": {"b": {"n": 1, "last": "2026-07-02"}},
                 "skills_journal": {"a": {"n": 3, "last": "2026-09-02"}},
                 "subagents_journal": {"c": {"n": 1, "last": ""}}}
        d = canon.derniers_usages(state)
        # `c` n'a pas de date : un nom sans usage daté n'est pas « utilisé ».
        assert d == {"a": "2026-09-02", "b": "2026-07-02"}

    def test_une_skill_vue_par_le_journal_n_est_pas_dormante(self, canon, monkeypatch):
        monkeypatch.setattr(canon, "days_since",
                            lambda ts: 90 if ts.startswith("2026-06") else 0)
        state = {"skills": {"a": {"n": 1, "last": "2026-06-01"}},
                 "skills_journal": {"a": {"n": 1, "last": "2026-09-02"},
                                    "z": {"n": 1, "last": "2026-06-01"}}}
        assert canon.dormants(state) == ["z"]

    def test_le_todo_elaguer_ne_compte_pas_une_skill_vue_par_le_journal(self, canon):
        fam = {"bmad-code-review": "BMAD", "bmad-prd": "BMAD", "bmad-ux": "BMAD"}
        state = {"skills": {}, "subagents": {},
                 "skills_journal": {"bmad-code-review": {"n": 8, "last": "2026-09-02T10:00:00"}}}
        todos = canon.build_todos({}, fam, {}, [], state=state)
        elaguer = [t for t in todos if "laguer" in t or "Trier" in t]
        assert len(elaguer) == 1 and "2/3" in elaguer[0], todos

    def test_sans_state_le_todo_reste_sur_le_seul_canal_transcripts(self, canon):
        """Compatibilité : les appels historiques sans `state` ne cassent pas."""
        fam = {"bmad-prd": "BMAD"}
        todos = canon.build_todos({}, fam, {}, [])
        assert any("Trier" in t for t in todos)

    def test_les_hints_jamais_utilises_excluent_le_journal(self, canon):
        fam = {"bmad-code-review": "BMAD", "bmad-prd": "BMAD"}
        state = {"skills": {}, "subagents": {},
                 "skills_journal": {"bmad-code-review": {"n": 8, "last": "2026-09-02T10:00:00"}}}
        hints = canon.build_routing_hints(state, fam, {}, {}, None, [], [])
        assert hints["jamais_utilises"] == ["bmad-prd"]


class TestLesTroisConsommateursLisentVraimentLeJournal:
    """Les tests de `TestLeCanalEstReellementLu` étaient des grep sur le source : ils
    seraient restés VERTS sur un appel mort, et aucun ne touchait `build_html_section`
    — c'est-à-dire précisément le seul chemin où le correctif manquait. La revue du
    2026-09-02 y a trouvé trois constats bloquants que ces 24 tests laissaient passer :
    la section HTML (le canal SERVI, celui que CLAUDE.md demande de contrôler)
    republiait « jamais invoqué », `eprouves` et `verifications_oubliees` lisaient
    encore le seul canal transcripts, et une skill connue du seul journal SORTAIT de
    « jamais utilisés » sans ENTRER dans le tableau d'usage — elle disparaissait de la
    page, un faux négatif visible remplacé par une absence.

    Ces tests-ci exercent les trois consommateurs sur un état réel. Motif payé le
    2026-07-30 (mémoire `feedback-test-garde-fou-assertion-vide`) : un test de
    garde-fou qui n'a jamais échoué ne prouve rien.
    """

    ETAT = {
        "files": {"s1": {}},
        "skills": {},                                     # transcripts : PURGÉS
        "subagents": {},
        "skills_journal": {"bmad-code-review": {"n": 8, "first": "2026-09-02T09:00:00",
                                                "last": "2026-09-02T16:24:01"}},
        "subagents_journal": {},
        "last_scan": "2026-09-02T18:00:00",
    }
    FAM = {"bmad-code-review": "BMAD", "bmad-forge-idea": "BMAD"}

    def _sans_disque(self, canon, monkeypatch, tmp_path):
        """`build_page` lit `PROMPTS_PATH`/`RUNS_PATH` : on les neutralise pour que le
        test mesure le rendu, pas l'état du dépôt."""
        monkeypatch.setattr(canon, "PROMPTS_PATH", str(tmp_path / "absent-prompts.jsonl"))
        monkeypatch.setattr(canon, "RUNS_PATH", str(tmp_path / "absent-runs.jsonl"))

    def test_la_section_html_ne_republie_pas_jamais_invoque(self, canon, monkeypatch, tmp_path):
        self._sans_disque(canon, monkeypatch, tmp_path)
        html = canon.build_html_section(dict(self.ETAT), dict(self.FAM), [])
        assert "bmad-forge-idea" in html, "la skill réellement jamais vue doit rester listée"
        assert "jamais invoqués" in html
        bloc = html[html.index("jamais invoqués"):]
        assert "bmad-code-review" not in bloc, (
            "le canal SERVI republie « jamais invoqué » une skill que le journal a vue "
            "tourner le jour même — c'est le constat bloquant de la revue du 2026-09-02")

    def test_la_skill_vue_du_seul_journal_apparait_dans_le_tableau_d_usage(
            self, canon, monkeypatch, tmp_path):
        self._sans_disque(canon, monkeypatch, tmp_path)
        md = canon.build_page(dict(self.ETAT), dict(self.FAM), [])
        html = canon.build_html_section(dict(self.ETAT), dict(self.FAM), [])
        for rendu, canal in ((md, "markdown"), (html, "html")):
            assert "bmad-code-review" in rendu, (
                f"{canal} : la skill sort de « jamais utilisés » sans entrer dans le "
                "tableau d'usage — elle disparaît de la page")
            assert "8" in rendu, f"{canal} : le nombre d'invocations du journal manque"

    def test_le_total_affiche_compte_le_journal(self, canon, monkeypatch, tmp_path):
        self._sans_disque(canon, monkeypatch, tmp_path)
        md = canon.build_page(dict(self.ETAT), dict(self.FAM), [])
        assert "**0** invocations de skills" not in md, (
            "l'en-tête annonce 0 invocation alors que le journal en porte 8")

    def test_les_hints_tiennent_compte_du_journal(self, canon):
        etat = dict(self.ETAT)
        etat["skills_journal"] = dict(etat["skills_journal"])
        etat["skills_journal"]["revue-increment"] = {"n": 7, "last": "2026-09-02T17:45:17"}
        fam = dict(self.FAM, **{"revue-increment": "projet"})
        hints = canon.build_routing_hints(etat, fam, {}, {}, None, runs=[], arbitrages=[])
        assert "bmad-code-review" in hints["eprouves"], (
            "8 invocations au journal, PROVEN_MIN=3 : la skill est éprouvée, "
            "routing-hints.json disait le contraire")
        assert "bmad-code-review" not in hints["jamais_utilises"]
        assert not any("revue-increment" in v for v in hints["verifications_oubliees"]), (
            "le hint reprochait à l'orchestrateur d'oublier une skill invoquée 7 fois")


class TestLesChiffresPubliesNeSontPasInventes:
    def test_une_ligne_mal_formee_n_est_pas_comptee_comme_commande_slash(
            self, canon, monkeypatch, tmp_path):
        j = tmp_path / "prompts.jsonl"
        j.write_text('{"ts": "2026-09-02T10:00:00", "slash": false, "n_car": 40}\n'
                     '[1, 2]\n"x"\n', encoding="utf-8")
        monkeypatch.setattr(canon, "PROMPTS_PATH", str(j))
        r = canon.ratio_qualification([])
        assert (r["prompts"], r["slash"]) == (1, 0), (
            f"slash dérivé d'une soustraction : {r} — deux lignes non-dict publiées "
            "comme commandes slash sur une page d'arbitrage")

    def test_un_journal_sans_aucune_date_rend_none_au_lieu_de_lever(
            self, canon, monkeypatch, tmp_path):
        j = tmp_path / "prompts.jsonl"
        j.write_text('{"slash": false, "n_car": 4}\n{"ts": "", "slash": true}\n',
                     encoding="utf-8")
        monkeypatch.setattr(canon, "PROMPTS_PATH", str(j))
        assert canon.ratio_qualification([]) is None    # min() sur un vide levait

    def test_un_state_abime_ne_coute_pas_le_scan_de_demarrage(self, canon, tmp_path):
        _ecrire(tmp_path, [_l(skill="a")])
        for abime in ({"usage_offset": "42"}, {"skills_journal": []},
                      {"subagents_journal": "x", "usage_offset": -9}):
            state = dict(abime)
            canon.scan_journal_usage(state)      # ne doit RIEN lever
            assert isinstance(state["skills_journal"], dict)


class TestLesCasLimitesDeLaRevueDu20260902:
    """Trois BLOQUANT + six MAJEUR/MOYEN sur `usage.jsonl` remontés par les deux
    couches adversariales (bmad-code-review, bmad-review-edge-case-hunter) du
    2026-09-02. Ceux qui touchent au rendu des trois consommateurs sont verrouillés
    dans `TestLesTroisConsommateursLisentVraimentLeJournal` ; ceux-ci verrouillent
    les cas limites internes à `scan_journal_usage`."""

    def test_un_remplacement_de_meme_taille_ou_plus_long_est_detecte(self, canon, tmp_path):
        """`offset > taille` ne voit pas passer un contenu DIFFÉRENT mais de même
        taille ou plus long (rotation, restauration, `git checkout`)."""
        _ecrire(tmp_path, [_l(skill="ancien")])
        state = {}
        assert canon.scan_journal_usage(state) == 1
        assert state["skills_journal"] == {"ancien": {"n": 1,
            "first": "2026-09-02T10:00:00+02:00", "last": "2026-09-02T10:00:00+02:00"}}
        # Remplacement (pas append) par un contenu différent, plus long.
        _ecrire(tmp_path, [_l(skill="neuf"), _l(skill="neuf")], mode="w")
        assert canon.scan_journal_usage(state) == 2
        assert "ancien" not in state["skills_journal"], (
            "le compteur de l'ancien contenu a survécu à un remplacement non détecté")
        assert state["skills_journal"]["neuf"]["n"] == 2

    def test_un_bom_en_tete_ne_perd_pas_la_premiere_ligne(self, canon, tmp_path):
        with open(tmp_path / "usage.jsonl", "wb") as fh:
            fh.write(b"\xef\xbb\xbf")     # BOM UTF-8
            fh.write(_l(skill="a").encode("utf-8"))
        state = {}
        assert canon.scan_journal_usage(state) == 1
        assert "a" in state["skills_journal"], "la première ligne, sous le BOM, est perdue"

    def test_un_state_json_touche_ne_double_compte_pas(self, canon, tmp_path):
        """Une exception EN COURS de lecture (ligne 2 corrompue au sens du décodage)
        ne doit pas persister un `usage_offset` partiel, sous peine de double compte
        au scan suivant si le state est malgré tout sauvegardé entre les deux."""
        _ecrire(tmp_path, [_l(skill="a")])
        state = {}
        canon.scan_journal_usage(state)
        avant = dict(state["skills_journal"])
        # Deuxième ligne : nom de skill qui n'est PAS une chaîne (list) -- filtré,
        # pas une exception, mais vérifie qu'aucun état intermédiaire ne fuit.
        with open(tmp_path / "usage.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "t", "skill": ["x"], "tool": "Skill"}) + "\n")
        canon.scan_journal_usage(state)
        assert state["skills_journal"] == avant


class TestLeRatioSignaleQuandIlNeVeutRienDire:
    @pytest.fixture
    def canon(self, tmp_path, monkeypatch):
        mod = _load()
        monkeypatch.setattr(mod, "PROMPTS_PATH", str(tmp_path / "prompts.jsonl"))
        return mod

    def test_plus_de_runs_que_de_demandes_hors_slash_est_signale(self, canon, tmp_path):
        """Chasse aux cas limites, 2026-09-02 : 4 commandes slash + 1 demande hors
        slash pour 5 runs publiait 500 % sans avertissement."""
        with open(tmp_path / "prompts.jsonl", "w", encoding="utf-8") as fh:
            for _ in range(4):
                fh.write(json.dumps({"ts": "2026-09-02T09:00:00", "slash": True, "n_car": 9}) + "\n")
            fh.write(json.dumps({"ts": "2026-09-02T09:00:01", "slash": False, "n_car": 20}) + "\n")
        runs = [{"ts": f"2026-09-02T09:00:0{i}"} for i in range(2, 7)]
        r = canon.ratio_qualification(runs)
        assert r["prompts"] == 1 and r["runs"] == 5
        assert r["part"] == 5.0
        assert r["part_fiable"] is False, "un ratio de 500 % doit se signaler non fiable"

    def test_un_ratio_normal_reste_fiable(self, canon, tmp_path):
        with open(tmp_path / "prompts.jsonl", "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-09-02T09:00:00", "slash": False, "n_car": 20}) + "\n")
            fh.write(json.dumps({"ts": "2026-09-02T09:00:01", "slash": False, "n_car": 20}) + "\n")
        r = canon.ratio_qualification([{"ts": "2026-09-02T09:00:02"}])
        assert r["part_fiable"] is True


class TestMesureIncompleteCouvreLeJournal:
    def test_journal_absent_n_est_pas_signale_muet(self, canon):
        """Un dépôt qui n'a jamais encore vu tourner `log_usage.py` (kit fraîchement
        posé) est un état normal, pas une panne : ne pas le confondre avec un
        journal illisible."""
        assert canon.mesure_incomplete({})["journal_usage_muet"] is False

    def test_un_journal_present_sans_offset_pose_est_signale_muet(self, canon, tmp_path):
        chemin = tmp_path / "usage.jsonl"
        chemin.write_text('{"ts": "t", "skill": "a", "tool": "Skill"}\n', encoding="utf-8")
        import os as _os
        old = _os.environ.get("AGENT_SUPERVISION_USAGE")
        _os.environ["AGENT_SUPERVISION_USAGE"] = str(chemin)
        try:
            m = canon.mesure_incomplete({})   # state vierge : usage_offset jamais posé
            assert m["journal_usage_muet"] is True
        finally:
            if old is None:
                _os.environ.pop("AGENT_SUPERVISION_USAGE", None)
            else:
                _os.environ["AGENT_SUPERVISION_USAGE"] = old
