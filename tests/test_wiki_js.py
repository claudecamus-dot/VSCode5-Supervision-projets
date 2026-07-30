"""Garde à la génération du JS du wiki — finding risque_technique de l'audit
2026-07-24 : le <script> de wiki.html est une grosse chaîne générée depuis Python,
et DEUX bugs d'échappement Python->JS ont été vécus le même jour (un \\' consommé
par Python cassant la syntaxe JS du fichier ENTIER — silencieusement —, puis des
SyntaxWarning \\* / \\s). Ce test verrouille la classe de bugs : le JS réellement
livré doit être syntaxiquement valide, vérifié par un vrai parseur (node --check),
pas par une relecture.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = os.path.join(HUB, "docs", "wiki.html")

NODE = shutil.which("node")


SRC_JS = os.path.join(HUB, "docs", "wiki_app.js")

# Harnais DOM minimal : fait TOURNER wiki_app.js dans node avec des stubs, et rejoue une
# séquence de polls de /api/jobs. `node --check` ne prouve que la syntaxe ; ici on prouve
# le COMPORTEMENT — la page se recharge quand un scan l'a régénérée, et pas autrement.
# Écrit en JS plutôt qu'en assertions sur le texte du fichier : une assertion sur une
# chaîne serait verte même si la logique était fausse (leçon du 2026-07-30, mémoire
# feedback-test-garde-fou-assertion-vide).
HARNAIS = r"""
const fs = require('fs');
const SRC = process.argv[2];
const SCENARIO = JSON.parse(process.argv[3]);   // liste de réponses successives d'/api/jobs

let reloads = 0, pollsRestants = [];
const noop = () => {};
const elem = () => ({
  textContent: '', className: '', innerHTML: '', dataset: {}, classList:
    { toggle: noop, add: noop, remove: noop }, setAttribute: noop, addEventListener: noop,
  querySelectorAll: () => [], scrollIntoView: noop, disabled: false, appendChild: noop,
});
// createElement doit être FIDÈLE : echapper() s'en sert pour échapper le HTML en
// écrivant dans textContent puis en relisant innerHTML. Un stub qui rend un objet nu
// fait échouer tout le rendu des cartes — et le .catch() silencieux du poll masque
// l'erreur, ce qui accuse à tort la logique testée (diagnostiqué le 2026-07-30).
const echappable = () => {
  const o = { _t: '' };
  Object.defineProperty(o, 'textContent', { set(v) { o._t = String(v); }, get() { return o._t; } });
  Object.defineProperty(o, 'innerHTML', {
    get() { return o._t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
    set(v) { o._t = String(v); },
  });
  return o;
};
global.document = {
  createElement: echappable,
  getElementById: (id) => (id === 'wiki-config' ? { textContent: '{}' } : elem()),
  querySelectorAll: () => [], addEventListener: noop, body: elem(),
};
global.location = { hash: '', reload: () => { reloads++; } };
global.history = { replaceState: noop };
global.alert = noop;
global.setTimeout = (fn) => { pollsRestants.push(fn); };   // temps contrôlé, pas d'attente réelle
let appel = 0;
global.fetch = (url) => {
  if (url.endsWith('/api/ping')) return Promise.resolve({ json: () => Promise.resolve({ ok: true }) });
  const rep = SCENARIO[Math.min(appel, SCENARIO.length - 1)];
  appel++;
  return Promise.resolve({ ok: true, json: () => Promise.resolve({ jobs: rep }) });
};

eval(fs.readFileSync(SRC, 'utf8'));   // le fichier est une IIFE : il démarre son 1er poll

// setImmediate (macrotâche) et non process.nextTick : nextTick s'exécute AVANT les
// microtâches de promesse, donc la file des polls était vidée avant même que le .then
// du premier fetch n'ait tourné (harnais faux au premier jet, corrigé le 2026-07-30).
const laisserTourner = () => new Promise((r) => setImmediate(r));

(async () => {
  await laisserTourner();
  for (let i = 0; i < 12; i++) {
    const suite = pollsRestants.shift();
    if (suite) suite();
    await laisserTourner();
  }
  console.log(JSON.stringify({ reloads, polls: appel }));
})();
"""


def _jouer(tmp_path, scenario):
    """Rejoue une séquence de réponses d'/api/jobs et rend {reloads, polls}.

    Les jobs des scénarios sont complétés avec les champs que le rendu des cartes
    attend : le JS enveloppe son poll dans un `.catch()` silencieux, donc un job
    incomplet ferait échouer le rendu SANS erreur visible — et le test échouerait en
    accusant la logique de rechargement, qui n'y serait pour rien (vécu au premier jet)."""
    defauts = {"libelle": "job de test", "cible": None, "started": "10:00:00",
               "ended": None, "tail": [], "t0": 0}
    complet = [[dict(defauts, **j) for j in rep] for rep in scenario]
    h = tmp_path / "harnais.js"
    h.write_text(HARNAIS, encoding="utf-8")
    r = subprocess.run([NODE, str(h), SRC_JS, json.dumps(complet)],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(NODE is None, reason="node absent du PATH")
class TestRechargementApresScan:
    """Demande utilisateur 2026-07-30 : « une action corrective terminée doit mettre à
    jour les infos affichées ». Le JS ne rafraîchissait que la liste des jobs ; pastilles,
    bandeau et findings restaient ceux d'avant l'action jusqu'à un F5 manuel."""

    def test_un_scan_qui_se_termine_recharge_la_page(self, tmp_path):
        scenario = [
            [{"id": "1", "action": "scan-rapide", "status": "en cours"}],
            [{"id": "1", "action": "scan-rapide", "status": "ok"}],
        ]
        assert _jouer(tmp_path, scenario)["reloads"] == 1

    def test_les_jobs_deja_finis_a_l_ouverture_ne_rechargent_pas(self, tmp_path):
        """LE piège : au chargement, /api/jobs rend l'historique complet (jusqu'à 200
        jobs terminés). Sans garde, la page se rechargerait en boucle à l'infini."""
        scenario = [[{"id": "1", "action": "scan", "status": "ok"},
                     {"id": "2", "action": "scan-rapide", "status": "ok"}]]
        assert _jouer(tmp_path, scenario)["reloads"] == 0

    def test_une_action_qui_ne_regenere_pas_la_page_ne_recharge_pas(self, tmp_path):
        scenario = [
            [{"id": "1", "action": "remediation", "status": "en cours"}],
            [{"id": "1", "action": "remediation", "status": "ok"}],
        ]
        assert _jouer(tmp_path, scenario)["reloads"] == 0

    def test_un_scan_en_echec_ne_recharge_pas(self, tmp_path):
        scenario = [
            [{"id": "1", "action": "scan", "status": "en cours"}],
            [{"id": "1", "action": "scan", "status": "echec (1)"}],
        ]
        assert _jouer(tmp_path, scenario)["reloads"] == 0

    def test_une_seule_recharge_meme_si_le_scan_reste_visible(self, tmp_path):
        """Le job terminé reste dans /api/jobs pendant 200 entrées : sans mémoire de ce
        qui a déjà été traité, chaque poll relancerait un rechargement."""
        scenario = [
            [{"id": "1", "action": "scan", "status": "en cours"}],
            [{"id": "1", "action": "scan", "status": "ok"}],
            [{"id": "1", "action": "scan", "status": "ok"}],
            [{"id": "1", "action": "scan", "status": "ok"}],
        ]
        assert _jouer(tmp_path, scenario)["reloads"] == 1

    def test_le_suivi_continue_un_tour_apres_la_fin_d_un_job(self, tmp_path):
        """Course étroite fermée le 2026-07-30 : le serveur enchaîne le scan JUSTE APRÈS
        avoir marqué terminé le job qui l'a déclenché. Un poll tombant dans cet intervalle
        ne voit plus rien « en cours » ; si le suivi s'arrêtait là, la fin du scan chaîné
        ne serait jamais observée et la page resterait périmée."""
        scenario = [
            [{"id": "1", "action": "valider", "status": "en cours"}],
            [{"id": "1", "action": "valider", "status": "ok"}],          # rien en cours ici
            [{"id": "1", "action": "valider", "status": "ok"},
             {"id": "2", "action": "scan-rapide", "status": "en cours"}],
            [{"id": "1", "action": "valider", "status": "ok"},
             {"id": "2", "action": "scan-rapide", "status": "ok"}],
        ]
        r = _jouer(tmp_path, scenario)
        assert r["polls"] >= 4, r          # le suivi ne s'est pas arrêté au 2e poll
        assert r["reloads"] == 1, r


@pytest.mark.skipif(NODE is None, reason="node absent du PATH")
class TestJsGenere:
    def _script_livre(self):
        html = open(WIKI, encoding="utf-8").read()
        blocs = re.findall(r"<script>(.*?)</script>", html, re.S)
        assert blocs, "aucun <script> dans docs/wiki.html"
        return blocs

    def test_wiki_html_existe(self):
        assert os.path.isfile(WIKI), "docs/wiki.html absent — lancer scripts/scan_projets.py"

    def test_js_livre_syntaxiquement_valide(self, tmp_path):
        # node --check parse sans exécuter : exactement la garde qui aurait attrapé
        # le bug du \' (SyntaxError: Unexpected identifier 'elle') avant livraison.
        for i, bloc in enumerate(self._script_livre()):
            f = tmp_path / f"bloc{i}.js"
            f.write_text(bloc, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)],
                               capture_output=True, text=True, timeout=30)
            assert r.returncode == 0, f"JS invalide (bloc {i}) : {r.stderr[:400]}"

    # --- F4 (VScode5:js-inline-wiki, arbitré 2026-07-29) : le JS vit dans
    # docs/wiki_app.js et est inliné tel quel à la génération — ces tests sont
    # le filet de la migration, les tests historiques ci-dessus restent verts.

    def test_wiki_app_js_source_syntaxiquement_valide(self):
        src = os.path.join(HUB, "docs", "wiki_app.js")
        assert os.path.isfile(src), "docs/wiki_app.js absent — le JS du wiki est un fichier source"
        r = subprocess.run([NODE, "--check", src], capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, f"wiki_app.js invalide : {r.stderr[:400]}"

    def test_js_livre_est_wiki_app_js_inline(self):
        src = open(os.path.join(HUB, "docs", "wiki_app.js"), encoding="utf-8").read().rstrip("\n")
        html = open(WIKI, encoding="utf-8").read()
        assert src in html, ("le <script> livré doit être exactement docs/wiki_app.js inliné "
                             "— régénérer via scripts/scan_projets.py")

    def test_bloc_config_json_valide(self):
        import json
        html = open(WIKI, encoding="utf-8").read()
        m = re.search(r'<script id="wiki-config" type="application/json">(.*?)</script>',
                      html, re.S)
        assert m, "bloc wiki-config absent de la page livrée"
        config = json.loads(m.group(1))
        assert config.get("api", "").startswith("http"), config

    def test_echappement_pieges_connus(self):
        # Les deux pièges déjà payés : un \' nu consommé par Python (il ne doit
        # rester AUCUNE séquence backslash-apostrophe cassée hors chaîne), et les
        # regex JS dont l'échappement doit survivre au transit par Python.
        script = "\n".join(self._script_livre())
        assert "qu\\'elle" in script or "qu'elle" not in script, \
            "l'apostrophe de « qu'elle » doit être échappée dans la chaîne JS"
        # la regex des options doit garder ses backslashes (\*, \s)
        if "choixProposes" in script:
            assert re.search(r"/\^\\\*\\\*\(Option\\s", script), \
                "la regex de choixProposes a perdu son échappement au transit Python->JS"
