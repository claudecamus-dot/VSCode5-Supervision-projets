"""Un scan qui plante le DIT, et laisse une trace qui lui survit.

Demande utilisateur du 2026-09-01 (« traite le pb du scan avale une exception en
silence »), née d'un incident vécu le soir même : une correction de ma main avait
introduit un `NameError: name 'state' is not defined` dans `build_todos`, et le hook
SessionStart l'a absorbé. Seule trace : une ligne

    Supervision agents : scan ignore (NameError: name 'state' is not defined)

et un code de sortie **0**. Le scan n'avait rien produit — ni TODO, ni routing-hints, ni
page — et rien ne le disait. La régression est restée invisible pendant deux commandes.

CE QU'ON NE TOUCHE PAS. Le `except Exception` est délibéré : un hook SessionStart qui
lève bloque l'ouverture de session, ce qui est pire que de ne pas scanner. Le code de
sortie reste donc 0 par défaut. Ce n'est pas le rattrapage qui est fautif, c'est ce
qu'il laisse — ou plutôt ce qu'il ne laisse pas.

CE QU'ON CORRIGE, et ce sont trois manques distincts :

1. **« ignore » ment sur la nature de l'événement.** Le mot dit un saut délibéré ; le
   fait est un plantage. Un lecteur pressé lit « ignore » et passe.
2. **Aucune localisation.** Une classe et un message, sans fichier ni ligne : pour
   retrouver `build_todos`, il a fallu relancer à la main.
3. **Aucune trace qui survive.** La ligne défile dans un démarrage de session et
   disparaît. Un incident qu'aucun fichier ne garde n'a jamais eu lieu.

Le quatrième point est le plus important : le scan SUIVANT doit REMONTER l'incident
précédent. Sans ça, on répare la visibilité de l'instant et pas celle de la durée.
"""

import importlib.util
import io
import json
import os

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "scan_transcripts_incident",
    os.path.join(HUB, ".claude", "supervision", "scan_transcripts.py"))
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _boum():
    """Une exception avec une vraie pile, comme celle qui a echappe au scan."""
    def interne():
        state = None
        return state.get("skills")   # AttributeError, pile a deux niveaux
    return interne()


class TestUnScanQuiPlanteLeDit:

    def _incident(self, tmp_path, monkeypatch, capsys, strict=False):
        journal = str(tmp_path / "incidents.jsonl")
        monkeypatch.setenv("AGENT_SUPERVISION_SCAN_INCIDENTS", journal)
        if strict:
            monkeypatch.setenv("AGENT_SUPERVISION_SCAN_STRICT", "1")
        else:
            monkeypatch.delenv("AGENT_SUPERVISION_SCAN_STRICT", raising=False)
        try:
            _boum()
        except Exception as exc:
            code = st.signaler_incident(exc)
        return code, capsys.readouterr().out, journal

    def test_le_mot_ignore_ne_dit_pas_qu_il_s_agit_d_un_plantage(self, tmp_path,
                                                                monkeypatch, capsys):
        _, sortie, _ = self._incident(tmp_path, monkeypatch, capsys)
        assert "ECHEC" in sortie or "PLANTE" in sortie, (
            "« scan ignore » se lit comme un saut delibere, pas comme un plantage")

    def test_la_localisation_est_donnee(self, tmp_path, monkeypatch, capsys):
        _, sortie, _ = self._incident(tmp_path, monkeypatch, capsys)
        assert "test_scan_incident_visible.py" in sortie, (
            "ni fichier ni ligne : il a fallu relancer a la main pour trouver "
            "build_todos")
        assert "interne" in sortie, "la pile ne remonte pas jusqu'au vrai coupable"

    def test_l_incident_survit_au_demarrage_de_session(self, tmp_path, monkeypatch,
                                                       capsys):
        _, _, journal = self._incident(tmp_path, monkeypatch, capsys)
        assert os.path.isfile(journal), "un incident qu'aucun fichier ne garde n'a pas eu lieu"
        e = json.loads(io.open(journal, encoding="utf-8").read().splitlines()[-1])
        assert e["exception"] == "AttributeError"
        assert e.get("trace"), "l'entree ne porte pas la pile"
        assert e.get("date"), "l'entree n'est pas horodatee"

    def test_le_demarrage_de_session_n_est_JAMAIS_bloque(self, tmp_path, monkeypatch,
                                                         capsys):
        """L'intention d'origine ne se perd pas : un hook qui leve bloque la session."""
        code, _, _ = self._incident(tmp_path, monkeypatch, capsys)
        assert code == 0

    def test_le_mode_strict_rend_le_plantage_fatal(self, tmp_path, monkeypatch, capsys):
        """Pour les tests, la CI et l'appel manuel : la ou rien n'est bloque, un
        plantage doit se voir dans le code de sortie."""
        code, _, _ = self._incident(tmp_path, monkeypatch, capsys, strict=True)
        assert code == 1

    def test_le_scan_SUIVANT_remonte_l_incident_precedent(self, tmp_path, monkeypatch,
                                                          capsys):
        """Le point qui compte : reparer la visibilite de la DUREE, pas de l'instant.

        Sans ca, l'incident defile dans un demarrage de session et disparait — et la
        regression reste invisible, ce qui est exactement ce qui s'est produit.
        """
        _, _, journal = self._incident(tmp_path, monkeypatch, capsys)
        lignes = st.incidents_a_signaler()
        assert lignes, "le scan suivant ne dit rien de l'incident precedent"
        assert any("AttributeError" in l for l in lignes)

    def test_pas_d_incident_pas_de_bruit(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_SUPERVISION_SCAN_INCIDENTS",
                           str(tmp_path / "vide.jsonl"))
        assert st.incidents_a_signaler() == []
