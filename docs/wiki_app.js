(function () {
  // Valeurs dynamiques : injectées par scan_projets.py dans le bloc JSON
  // <script id="wiki-config" type="application/json"> — jamais par
  // interpolation de chaîne Python dans ce fichier (classe de bugs 2026-07-24).
  var CFG = {};
  try {
    var cfgEl = document.getElementById("wiki-config");
    if (cfgEl) CFG = JSON.parse(cfgEl.textContent);
  } catch (e) { /* config illisible : les défauts ci-dessous s'appliquent */ }
  var API = CFG.api || "http://localhost:8765";
  // Onglets (hash persistant : #pane-pilotage rouvre l'onglet Pilotage)
  var boutons = document.querySelectorAll("nav.tabs button");
  // Fusion du 2026-09-03 (11 -> 5 onglets primaires) : ces noms ne sont plus des
  // panes de premier niveau, seulement des sous-panneaux (class="sous-pane") d'un
  // pane fusionné. Un signet ou un lien externe vers l'un d'eux (#pane-veille,
  // #pane-correctifs…) doit rouvrir son PARENT — sinon activer() ne trouve aucun
  // "section.pane" dont l'id corresponde, ne rend rien actif, et affiche une page
  // blanche (finding de restructuration, corrigé avant publication).
  var PARENT_DE = {
    actions: "arbitrer", correctifs: "arbitrer",
    veille: "archive", deploiement: "archive", exports: "archive",
    tokens: "archive", tutoriel: "archive", dispositif: "archive"
  };
  function activerEtCibler(nom) {
    var parent = PARENT_DE[nom];
    activer(parent || nom);
    if (parent) {
      var cible = document.getElementById("pane-" + nom);
      if (cible) cible.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  function activer(nom) {
    // Journaliser depuis ICI, pas depuis le seul listener des boutons : un onglet
    // s'atteint par trois chemins (clic, hash au chargement, lien [data-goto]), et
    // n'instrumenter que le premier biaisait la mesure dans le sens de « jamais
    // atteint » (revue du 2026-09-02). Un re-clic sur l'onglet déjà actif ne compte
    // pas : rien n'est atteint de nouveau.
    var courant = document.querySelector("section.pane.actif");
    var dejaActif = courant && courant.id === "pane-" + nom;
    boutons.forEach(function (b) {
      var actif = b.dataset.pane === nom;
      b.classList.toggle("actif", actif);
      // aria-selected est la seule chose qu'un lecteur d'écran perçoit ici — la
      // classe CSS actif ne lui dit rien (finding wiki:accessibilite-onglets).
      b.setAttribute("aria-selected", actif ? "true" : "false");
    });
    document.querySelectorAll("section.pane").forEach(function (s) {
      s.classList.toggle("actif", s.id === "pane-" + nom);
    });
    if (!dejaActif) journaliserOnglet(nom);
  }
  // L'INSTRUMENT QUI SÉPARE « introuvable » DE « inutile » (arbitrage du 2026-09-02,
  // demandé par la salle inspection-critique). `vues.jsonl` comptait 24 ouvertures de
  // page pour zéro job en 32 jours : le compteur avait éliminé « la page ne s'ouvre
  // jamais » sans départager les deux lectures restantes — l'onglet qui porte les
  // boutons n'est jamais ATTEINT, ou il est atteint et rien n'y est cliqué. Ces deux-là
  // commandent deux refontes contraires, et la Rupture C se déciderait sinon sur une
  // conviction.
  //
  // Tirer-et-oublier : pas de `await`, pas de `.then`, le `.catch` est muet. Mesurer
  // l'usage ne doit jamais gêner l'usage — si le serveur est absent (page ouverte en
  // file://), le clic doit changer d'onglet exactement pareil. C'est aussi pourquoi
  // l'appel vient en FIN d'`activer()`, une fois les classes basculées.
  //
  // Déclarée après `activer()` mais appelée depuis elle : `function` est hissée dans
  // l'IIFE, l'ordre du fichier ne change rien.
  function journaliserOnglet(nom) {
    try {
      fetch(API + "/api/onglet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ onglet: nom })
      }).catch(function () {});
    } catch (e) { /* aucun recours utile : on ne gêne pas la navigation */ }
  }

  boutons.forEach(function (b) {
    b.addEventListener("click", function () {
      activer(b.dataset.pane);
      history.replaceState(null, "", "#pane-" + b.dataset.pane);
    });
  });
  var h = (location.hash || "").replace("#pane-", "");
  if (h && document.getElementById("pane-" + h)) activerEtCibler(h);

  // « La réponse du jour » renvoie vers l'onglet qui traite le sujet : un constat
  // qu'on ne peut pas suivre d'un clic n'est qu'une notification de plus. Délégué
  // sur le document, parce que le bloc est régénéré à chaque scan.
  document.addEventListener("click", function (ev) {
    var lien = ev.target.closest ? ev.target.closest("[data-goto]") : null;
    if (!lien) return;
    var cible = lien.dataset.goto;
    if (!document.getElementById("pane-" + cible)) return;   // onglet disparu : ne rien casser
    ev.preventDefault();
    activerEtCibler(cible);
    history.replaceState(null, "", "#pane-" + cible);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // Serveur d'actions : état + déclencheurs
  var etat = document.getElementById("serveur-etat");
  function ping() {
    fetch(API + "/api/ping").then(function (r) { return r.json(); }).then(function () {
      etat.textContent = "Serveur d'actions actif — les boutons sont opérationnels.";
      etat.className = "on";
    }).catch(function () {
      etat.textContent = "Serveur d'actions non détecté — lancer : py scripts/serve_wiki.py (puis ouvrir http://localhost:8765).";
      etat.className = "off";
    });
  }
  ping();

  // --- Sablier + libellé sur le bouton, du clic jusqu'à la fin du job --------
  var boutonParJob = {};   // id de job -> bouton qui l'a déclenché (pour le restaurer)
  var jobsTermines = {};   // id de job déjà rendu terminé (évite de re-basculer le bouton)
  var pliManuel = {};      // id de job -> true/false : dernier état choisi PAR L'UTILISATEUR
                            // (remplirZone reconstruit tout le HTML à chaque poll ; sans ceci,
                            // un rapport déplié à la main se replierait au rafraîchissement suivant)
  var scrollSortie = {};   // id de job -> scrollTop de sa <pre class="rapport-sortie"> — même
                            // cause que pliManuel : sans ça, un scroll dans la sortie revient en
                            // haut au poll suivant (le <pre> est détruit puis recréé à chaque fois)

  function demarrerChargement(b) {
    if (!b.dataset.label) b.dataset.label = b.innerHTML;   // libellé d'origine, une seule fois
    b.innerHTML = '<span class="spin"></span>En cours…';
    b.classList.add("loading");
    b.disabled = true;
  }
  function arreterChargement(b) {
    if (b.dataset.label) b.innerHTML = b.dataset.label;
    b.classList.remove("loading");
    b.disabled = false;
  }

  function classeStatut(statut) {
    if (statut === "en cours") return "encours";
    if (statut === "ok") return "ok";
    if (statut === "annule") return "annule";
    return "echec";   // echec (N) / erreur (...)
  }
  // Une action LLM démarre à froid en ~25 s (mesuré) puis travaille plusieurs
  // minutes : sans durée qui avance, « en cours » ne se distingue pas d'un job
  // planté — c'est ce qui faisait lire le lancement comme « beaucoup trop lent ».
  function duree(s) {
    if (s == null) return "";
    if (s < 60) return s + " s";
    return Math.floor(s / 60) + " min " + ("0" + (s % 60)).slice(-2) + " s";
  }
  function libelleStatut(statut, d) {
    var suffixe = d ? " — " + duree(d) : "";
    if (statut === "en cours") return "⏳ en cours" + suffixe;
    if (statut === "ok") return "✅ terminé" + suffixe;
    if (statut === "annule") return "🚫 annulé" + suffixe;
    return "❌ " + statut + suffixe;
  }

  function echapper(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML.replace(/"/g, "&quot;");
  }

  // Actions dont le prompt se termine par « demande l'arbitrage explicite avant
  // d'appliquer » — celles-là seules proposent une décision à trancher. « reflexion »
  // en est volontairement exclue (elle n'applique jamais rien, rien à valider/refuser).
  var ACTIONS_AVEC_ARBITRAGE = ["remediation", "deployer-veille"];

  // Cherche, dans la liste COMPLÈTE des jobs (pas la seule liste filtrée de la zone —
  // un job "valider" né d'un rapport de l'onglet Veille vit dans la zone Correctifs),
  // le dernier valider/refuser pour cette cible. Dérivé du serveur, pas d'une mémoire
  // locale : survit à un rechargement de page ET empêche de relancer une action déjà
  // en cours ou déjà tranchée (le vrai bug rapporté — l'état local se perdait au reload).
  function decisionExistante(tousJobs, cible) {
    for (var i = 0; i < tousJobs.length; i++) {
      var j = tousJobs[i];   // déjà trié du plus récent au plus ancien par le serveur
      if ((j.action === "valider" || j.action === "refuser") && j.cible === cible) return j;
    }
    return null;
  }

  // Une proposition n'est pas toujours un simple oui/non — un rapport peut énumérer
  // plusieurs options (« **Option A — …** », « **Option B — …** »). Détecter ≥ 2
  // options dans la sortie et les faire APPARAÎTRE distinctement, plutôt que de les
  // laisser noyées dans le texte replié derrière un Valider/Invalider aveugle.
  function choixProposes(tail) {
    var options = [];
    (tail || []).forEach(function (ligne) {
      var m = /^\*\*(Option\s+[^*]+)\*\*/i.exec((ligne || "").trim());
      if (m) options.push(m[1]);
    });
    return options;
  }

  function decisionArbitrage(j, tousJobs) {
    // Sur un rapport TERMINÉ dont la proposition a été présentée, dans N'IMPORTE QUEL
    // onglet (Actions correctives, Veille…) : Valider (applique, LLM) ou Invalider
    // (note le refus, 0 token).
    if (ACTIONS_AVEC_ARBITRAGE.indexOf(j.action) === -1 || j.status !== "ok" || !j.cible) return "";
    var decision = decisionExistante(tousJobs, j.cible);
    if (decision) {
      if (decision.status === "en cours") {
        var quoi = decision.action === "valider" ? "l'application" : "l'enregistrement du refus";
        return '<div class="decision-arbitrage prise encours">' +
          '<span class="spin spin-sombre"></span>Une action est déjà en cours de traitement pour ' +
          'cette cible (' + quoi + ') — patiente qu\'elle se termine.</div>';
      }
      if (decision.status === "ok") {
        return decision.action === "valider"
          ? '<div class="decision-arbitrage prise">✅ Validé — appliqué (' + decision.started + ')</div>'
          : '<div class="decision-arbitrage prise">🚫 Refusé (' + decision.started + ') — ne sera plus reproposé</div>';
      }
      // echec/erreur : aucune décision solide n'a abouti — on relaisse la main (boutons).
    }
    var cible = echapper(j.cible);
    var options = choixProposes(j.tail);
    var choixHtml = "";
    if (options.length >= 2) {
      choixHtml = '<div class="choix-proposes"><span class="choix-titre">Choix proposés :</span>' +
        options.map(function (o) { return '<span class="choix-item">' + echapper(o) + '</span>'; }).join("") +
        '</div><input type="text" class="choix-input" ' +
        'placeholder="Préciser un choix (ex. ' + echapper(options[0].split(/[—–-]/)[0].trim()) + ')">';
    }
    return '<div class="decision-arbitrage">' +
      choixHtml +
      '<span class="decision-question">Décision en attente :</span> ' +
      '<button class="oui" data-action="valider" data-cible="' + cible + '">Valider</button> ' +
      '<button class="non" data-action="refuser" data-cible="' + cible + '">Invalider</button>' +
      '</div>';
  }

  function carteRapport(j, estLaDerniere, tousJobs) {
    var classe = classeStatut(j.status);
    // Repliée par défaut ; la toute dernière action lancée et tout job en cours démarrent
    // ouverts — SAUF si l'utilisateur a explicitement plié/déplié cette carte lui-même,
    // auquel cas son choix prime sur la règle par défaut à chaque rafraîchissement.
    var parDefaut = estLaDerniere || j.status === "en cours";
    var ouvert = (j.id in pliManuel ? pliManuel[j.id] : parDefaut) ? " open" : "";
    // libelle et tail = sortie brute d'un sous-process / claude -p (texte non contrôlé) :
    // échappés avant injection en innerHTML (finding sécurité XSS stocké, audit 2026-07-24).
    var tailHtml = (j.tail || []).map(echapper).join("\n");
    // Annuler n'a de sens que tant que le job tourne — un job long (audit/diagnostic,
    // plusieurs minutes, facturé) n'avait jusqu'ici aucun moyen de l'interrompre
    // (finding wiki:actions-irreversibles (c), diagnostic 2026-07-30).
    var boutonAnnuler = j.status === "en cours"
      ? '<button class="annuler" data-action="cancel" data-job="' + j.id + '">Annuler</button>'
      : '';
    return '<div class="rapport-carte ' + classe + '">' +
      '<div class="rapport-entete">' +
        '<span class="rapport-titre">' + echapper(j.libelle) + '</span>' +
        '<span class="rapport-statut ' + classe + '">' + libelleStatut(j.status, j.duree_s) + '</span>' +
        boutonAnnuler +
      '</div>' +
      '<div class="rapport-heure">' + echapper(j.started) + (j.ended ? ' → ' + echapper(j.ended) : '') + '</div>' +
      decisionArbitrage(j, tousJobs) +
      '<details class="rapport-details" data-job="' + j.id + '"' + ouvert + '>' +
        '<summary>Détail du rapport</summary>' +
        '<pre class="rapport-sortie" data-job="' + j.id + '">' + tailHtml + '</pre>' +
      '</details>' +
    '</div>';
  }
  function zoneRapportPour() {
    // Zone UNIQUE depuis le judas (2026-08-31) : la page n'a plus qu'un journal
    // de session, dans l'onglet Décisions — éparpiller cinq zones rendait les
    // comptes rendus introuvables (et quatre d'entre elles n'avaient plus de
    // bouton pour les alimenter).
    return "rapports-decisions";
  }
  function remplirZone(id, jobs, tousJobs, videTexte) {
    var zone = document.getElementById(id);
    if (!zone) return;   // le conteneur peut ne pas exister sur cette page
    zone.innerHTML = jobs.length
      ? jobs.map(function (j, i) { return carteRapport(j, i === 0, tousJobs); }).join("")
      : '<p class="vide">' + videTexte + '</p>';
    // Le innerHTML ci-dessus recrée les <details> à chaque poll : ré-attacher l'écoute
    // du pli à chaque fois pour mémoriser le choix de l'utilisateur (cf. pliManuel).
    zone.querySelectorAll(".rapport-details").forEach(function (det) {
      det.addEventListener("toggle", function () {
        pliManuel[det.dataset.job] = det.open;
      });
    });
    // Même cause, même remède pour le scroll À L'INTÉRIEUR d'une sortie longue : le
    // <pre> est recréé à chaque poll, donc on restaure la position connue puis on
    // réécoute pour la garder à jour (pas de scroll = pas d'entrée, rien à restaurer).
    zone.querySelectorAll(".rapport-sortie").forEach(function (pre) {
      var id = pre.dataset.job;
      if (id in scrollSortie) pre.scrollTop = scrollSortie[id];
      pre.addEventListener("scroll", function () {
        scrollSortie[id] = pre.scrollTop;
      }, { passive: true });
    });
  }

  // Un scan RÉGÉNÈRE docs/wiki.html : le DOM affiché devient périmé à la seconde où il
  // se termine (pastilles, bandeau, findings datent d'avant l'action). Recharger est la
  // seule façon sûre de montrer la vérité — la page est reconstruite entièrement côté
  // serveur, et rien n'est perdu : l'onglet actif vit dans le hash de l'URL, les rapports
  // vivent dans JOBS côté serveur. Le serveur enchaîne lui-même un scan après toute
  // action qui écrit (cf. ACTIONS_QUI_PERIMENT_LES_MESURES dans serve_wiki.py) : ici on
  // ne fait que réagir à sa fin.
  var REGENERENT_LA_PAGE = ["scan", "scan-rapide", "pdf"];
  var premierPoll = true;      // à l'ouverture, les jobs DÉJÀ finis ne doivent rien déclencher
  var finVue = {};             // id de job dont la fin a déjà été traitée (une fois par job)
  var rechargeEnCours = false;

  function annoncerPuisRecharger() {
    if (rechargeEnCours) return;
    rechargeEnCours = true;
    if (etat) {
      etat.textContent = "Mesures régénérées par le scan — rechargement de la page…";
      etat.className = "on";
    }
    // Court délai : l'utilisateur voit POURQUOI la page bouge sous ses yeux.
    setTimeout(function () { location.reload(); }, 1500);
  }

  function rafraichirJobs() {
    fetch(API + "/api/jobs").then(function (r) { return r.json(); }).then(function (d) {
      var jobs = d.jobs || [];
      var aRecharger = false;
      var finObservee = false;   // un job s'est terminé DEPUIS le poll précédent
      // Un job qui se termine (n'est plus "en cours") restaure son bouton une seule fois.
      jobs.forEach(function (j) {
        var fini = j.status !== "en cours";
        if (fini && boutonParJob[j.id] && !jobsTermines[j.id]) {
          arreterChargement(boutonParJob[j.id]);
          jobsTermines[j.id] = true;
        }
        if (!fini || finVue[j.id]) return;
        finVue[j.id] = true;
        if (premierPoll) return;            // déjà fini à l'ouverture : ne déclenche rien
        finObservee = true;
        if (j.status === "ok" && REGENERENT_LA_PAGE.indexOf(j.action) !== -1) {
          aRecharger = true;
        }
      });
      premierPoll = false;
      if (aRecharger) annoncerPuisRecharger();
      // Zone unique (judas, 2026-08-31) : TOUS les jobs — décisions, salles, et le
      // scan chaîné par le serveur — dans le journal de session de l'onglet
      // Décisions. Un compte rendu éparpillé est un compte rendu introuvable.
      remplirZone("rapports-decisions", jobs, jobs,
                  "Aucune action lancée dans cette session.");
      // On continue de regarder tant qu'un job tourne — ET un tour de plus après qu'un
      // job vient de finir. Sans ce tour supplémentaire, une course étroite mais réelle :
      // le serveur enchaîne le scan JUSTE APRÈS avoir marqué le job précédent terminé,
      // donc un poll tombant dans cet intervalle ne verrait plus rien « en cours »,
      // arrêterait le suivi, et la fin du scan chaîné ne serait jamais observée — la page
      // resterait périmée alors que tout le dispositif a bien fonctionné.
      if (jobs.some(function (j) { return j.status === "en cours"; }) || finObservee)
        setTimeout(rafraichirJobs, 1500);
    }).catch(function () {});
  }

  // Délégation sur document (pas un forEach au chargement) : les boutons Valider/Invalider
  // sont injectés APRÈS coup par remplirZone (innerHTML) — un câblage one-shot au chargement
  // ne les verrait jamais. La délégation couvre statique et dynamique uniformément.
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    if (!b) return;
    // Annuler un job en cours : route dédiée, ne passe pas par /api/run (finding
    // wiki:actions-irreversibles (c), diagnostic 2026-07-30).
    if (b.dataset.action === "cancel") {
      b.disabled = true;
      fetch(API + "/api/cancel/" + b.dataset.job, { method: "POST" })
        .then(function () { rafraichirJobs(); })
        .catch(function () { alert("Annulation impossible : serveur injoignable."); })
        .then(function () { b.disabled = false; });
      return;
    }
    var corps = {};
    if (b.dataset.action === "remediation") corps.cible = b.dataset.cible;
    // Les trois décisions du judas (2026-08-31) : la cible voyage sur le bouton,
    // posé sur l'objet même (finding, trouvaille, run) — jamais de formulaire.
    if (["solder", "ecarter-veille", "adopter"].indexOf(b.dataset.action) !== -1)
      corps.cible = b.dataset.cible;
    // Adopter lance un agent qui APPLIQUE la trouvaille : confirmation explicite
    // nommant la cible, même règle que Valider (finding wiki:actions-irreversibles).
    if (b.dataset.action === "adopter" && !confirm(
        "Adopter « " + (corps.cible || "") + " » : lance un agent qui APPLIQUE la " +
        "trouvaille (référentiel, scan, projets concernés de la flotte).\n\n" +
        "Le clic vaut arbitrage d'adoption. Confirmer ?"
    )) return;
    // Table ronde : la salle et le sujet voyagent sur le bouton lui-même, parce qu'ils
    // dépendent de l'endroit du wiki d'où l'on clique (une trouvaille de veille et un
    // finding de pratique n'appellent pas les mêmes voix). Pas de confirmation : la
    // salle DÉLIBÈRE et ne modifie aucun fichier — au pire elle coûte, elle ne casse rien.
    if (b.dataset.action === "party") {
      corps.salle = b.dataset.salle;
      corps.sujet = b.dataset.sujet || "";
    }
    var encart = null;
    if (b.dataset.action === "valider" || b.dataset.action === "refuser") {
      corps.cible = b.dataset.cible;
      // Le clic sur Valider lance un agent --dangerously-skip-permissions qui MODIFIE
      // un dépôt réel de la flotte : une confirmation explicite, nommant le dépôt visé,
      // avant tout fetch (finding wiki:actions-irreversibles (a), diagnostic 2026-07-30).
      if (b.dataset.action === "valider" && !confirm(
          "Confirmer l'application de ce correctif sur :\n\n" + corps.cible + "\n\n" +
          "Cette action lance un agent en --dangerously-skip-permissions qui modifie un DÉPÔT RÉEL."
      )) return;
      encart = b.closest(".decision-arbitrage");
      // Choix précisé (quand la proposition énumérait plusieurs options) : transmis
      // tel quel au serveur, qui l'injecte dans le prompt de valider — sans ce champ,
      // un fresh claude -p sans mémoire du run précédent devrait redeviner l'option.
      var champChoix = encart && encart.querySelector(".choix-input");
      if (champChoix && champChoix.value.trim()) corps.choix = champChoix.value.trim();
      // Désactive les 2 boutons AVANT même la réponse réseau (latence) — l'état
      // durable (déjà décidé / déjà en cours) vient ensuite du serveur via
      // decisionExistante(), pas d'une mémoire locale qui se perdrait au rechargement.
      if (encart) encart.querySelectorAll("button").forEach(function (fr) { fr.disabled = true; });
    }
    demarrerChargement(b);
    fetch(API + "/api/run/" + b.dataset.action, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    }).then(function (r) {
      if (!r.ok) return r.json().then(function (err) { throw new Error(err.message || err.erreur || "échec"); });
      return r.json();
    }).then(function (d) {
      boutonParJob[d.job] = b;   // le bouton restera "en cours" jusqu'à la fin de CE job
      rafraichirJobs();
      // Le clic « ouvre » la zone de suivi : on l'amène dans le viewport tout de
      // suite, sans attendre que l'utilisateur pense à descendre la chercher.
      var zone = document.getElementById(zoneRapportPour(b.dataset.action));
      if (zone) zone.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }).catch(function (err) {
      arreterChargement(b);
      // Refusé par le garde-fou serveur (deja_en_cours) ou tout autre échec : on
      // réactive ce qu'on avait désactivé de façon optimiste, rien ne reste bloqué.
      if (encart) encart.querySelectorAll("button").forEach(function (fr) { fr.disabled = false; });
      alert(err && err.message ? err.message : "Action refusée ou serveur injoignable : lancer py scripts/serve_wiki.py");
    });
  });
  rafraichirJobs();
})();
