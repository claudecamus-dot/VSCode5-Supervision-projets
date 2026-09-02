"""Le dénominateur du seuil de qualification — `orchestrator_gate.py` + `ratio_qualification`.

Finding `VScode5:seuil-qualification-non-mesurable` (2026-09-02), option A appliquée.
La décision n°2 de `docs/reflexions/conception-agent-orchestrator.md` promettait depuis
juillet une calibration « sur quelques cas réels » du seuil « orchestrer ou exécuter
directement ». Elle n'a jamais eu lieu, et pas par négligence : sur les 106 runs de
`runs.jsonl`, **106 portaient `orchestre` et 0 `direct-signale`**, parce que la méthode
dit qu'une exécution directe ne se journalise pas. Le ratio était non mesurable par
construction — le numérateur existait, le dénominateur nulle part.

Le hook `UserPromptSubmit` est le seul endroit du dispositif qui voit CHAQUE demande.
Il en écrit désormais une ligne, sans le texte du prompt.

Ce que ces tests verrouillent, et qui sont les deux moitiés d'une même promesse :
le hook ne bloque jamais une demande (c'est un hook de prompt, il est sur le chemin
critique de l'utilisateur), et le journal a un LECTEUR — la leçon de `usage.jsonl`,
écrit pendant 40 jours sans que personne l'ouvre.

Le hook est lancé exactement comme la production le lance (`py <script>`, un JSON sur
stdin, aucun `-X utf8`, aucun `PYTHONIOENCODING`) : mémoire
`feedback-tester-un-hook-comme-la-production` — 23 tests verts sur un deny illisible,
le 2026-09-02, parce qu'ils forçaient un encodage que la production n'a pas.

Lancer : py -m pytest tests/test_seuil_qualification.py -q --basetemp=C:/tmp/pt/sq
"""

import importlib.util
import json
import os
import subprocess
import sys

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(HUB, ".claude", "hooks", "orchestrator_gate.py")
CANON = os.path.join(HUB, ".claude", "dispositif", "canon", "scan_transcripts.py")


def _lancer(prompt, journal, env_supp=None):
    """Comme Claude Code le lance : `py <script>`, un JSON sur stdin, rien de plus."""
    env = dict(os.environ, AGENT_ORCHESTRATION_PROMPTS=str(journal))
    env.pop("PYTHONIOENCODING", None)
    env.update(env_supp or {})
    p = subprocess.run([sys.executable, GATE],
                       input=json.dumps({"prompt": prompt}).encode("utf-8"),
                       capture_output=True, timeout=60, env=env, cwd=HUB)
    assert p.returncode == 0, (
        f"un hook UserPromptSubmit qui sort {p.returncode} bloque la demande : {p.stderr!r}")
    return p


def _lignes(journal):
    if not os.path.isfile(journal):
        return []
    with open(journal, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


class TestLeHookCompteSansJamaisGener:
    def test_une_demande_ordinaire_est_comptee_et_recoit_la_grille(self, tmp_path):
        j = tmp_path / "prompts.jsonl"
        demande = "corrige le bug de la page projets"
        p = _lancer(demande, j)
        assert b"[orchestrateur]" in p.stdout
        (ligne,) = _lignes(j)
        # La longueur se DÉRIVE de la demande envoyée. Écrite en dur, elle valait 34
        # pour un prompt de 33 caractères : le test tombait rouge en accusant le hook
        # d'un défaut qui était le sien.
        assert ligne["slash"] is False and ligne["n_car"] == len(demande)

    def test_une_commande_slash_est_comptee_mais_reste_silencieuse(self, tmp_path):
        """Elle compte : c'est une demande vue. Elle ne reçoit pas la grille :
        l'utilisateur a déjà invoqué une skill explicitement."""
        j = tmp_path / "prompts.jsonl"
        p = _lancer("/orchestre relance les travaux", j)
        assert p.stdout.strip() == b""
        (ligne,) = _lignes(j)
        assert ligne["slash"] is True

    def test_le_texte_du_prompt_n_est_JAMAIS_ecrit(self, tmp_path):
        """Un prompt est du contenu client. Le journal en garde la longueur, pas le mot."""
        j = tmp_path / "prompts.jsonl"
        secret = "le mot de passe de production est correcthorsebatterystaple"
        _lancer(secret, j)
        brut = (tmp_path / "prompts.jsonl").read_text(encoding="utf-8")
        assert "correcthorse" not in brut and "production" not in brut
        assert set(_lignes(j)[0]) == {"ts", "slash", "n_car"}

    def test_un_journal_impossible_a_ecrire_ne_bloque_pas_la_demande(self, tmp_path):
        """Le hook est sur le chemin critique : perdre une ligne de mesure est
        acceptable, perdre la demande de l'utilisateur ne l'est pas."""
        cible = tmp_path / "fichier"
        cible.write_text("je ne suis pas un dossier", encoding="utf-8")
        p = _lancer("une demande", cible / "sous" / "prompts.jsonl")
        assert b"[orchestrateur]" in p.stdout

    def test_un_payload_casse_ne_bloque_pas(self, tmp_path):
        env = dict(os.environ, AGENT_ORCHESTRATION_PROMPTS=str(tmp_path / "p.jsonl"))
        p = subprocess.run([sys.executable, GATE], input=b"{ pas du json",
                           capture_output=True, timeout=60, env=env, cwd=HUB)
        assert p.returncode == 0

    def test_le_journal_s_ajoute_et_n_ecrase_pas(self, tmp_path):
        j = tmp_path / "prompts.jsonl"
        for i in range(3):
            _lancer(f"demande {i}", j)
        assert len(_lignes(j)) == 3

    def test_la_sortie_reste_pur_ascii(self):
        """Le déni illisible du 2026-09-02 : une sortie de hook non-ASCII lancée par
        `py <script>` sort en cp1252 sur ce poste. La grille doit rester lisible."""
        source = open(GATE, encoding="utf-8").read()
        grille = source[source.index("GRID = ("):source.index("_HOOKS_DIR")]
        grille.encode("ascii")


class TestLeJournalEstLu:
    """Sans lecteur, capter plus dépense sans rien acheter (leçon `usage.jsonl`)."""

    @pytest.fixture
    def canon(self, tmp_path, monkeypatch):
        spec = importlib.util.spec_from_file_location("canon_ratio", CANON)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        monkeypatch.setattr(mod, "PROMPTS_PATH", str(tmp_path / "prompts.jsonl"))
        return mod

    def _journal(self, canon, lignes):
        with open(canon.PROMPTS_PATH, "w", encoding="utf-8") as fh:
            for l in lignes:
                fh.write(json.dumps(l) + "\n")

    def test_journal_vide_ne_rend_pas_un_faux_zero(self, canon):
        """« 0 % des demandes orchestrées » sur une mesure qui n'a pas commencé se
        lirait comme un résultat."""
        assert canon.ratio_qualification([]) is None

    def test_le_ratio_se_calcule_sur_la_fenetre_du_journal(self, canon):
        """Comparer 106 runs de six semaines à trois jours de prompts donnerait un
        ratio supérieur à 1 : les runs antérieurs à la première ligne sont hors champ."""
        self._journal(canon, [
            {"ts": "2026-09-02T10:00:00+02:00", "slash": False, "n_car": 30},
            {"ts": "2026-09-02T11:00:00+02:00", "slash": False, "n_car": 12},
            {"ts": "2026-09-02T11:30:00+02:00", "slash": True, "n_car": 8},
            {"ts": "2026-09-02T12:00:00+02:00", "slash": False, "n_car": 90},
        ])
        runs = [{"ts": "2026-07-30T09:00:00+02:00"},          # avant le journal
                {"ts": "2026-09-02T10:30:00+02:00"},
                {"ts": "2026-09-02T12:10:00+02:00"}]
        r = canon.ratio_qualification(runs)
        assert r["prompts"] == 3 and r["slash"] == 1
        assert r["runs"] == 2
        assert round(r["part"], 4) == round(2 / 3, 4)
        assert r["depuis"] == "2026-09-02T10:00:00+02:00"

    def test_un_journal_de_slash_seulement_ne_divise_pas_par_zero(self, canon):
        self._journal(canon, [{"ts": "2026-09-02T10:00:00+02:00", "slash": True, "n_car": 5}])
        r = canon.ratio_qualification([{"ts": "2026-09-02T11:00:00+02:00"}])
        assert r["prompts"] == 0 and r["part"] is None

    def test_le_ratio_est_rendu_dans_la_page(self):
        src = open(CANON, encoding="utf-8").read()
        corps = src[src.index("def build_page("):src.index("def _esc(")]
        assert "ratio_qualification(" in corps, (
            "le ratio est calculable mais n'apparait nulle part : journal sans lecteur")
