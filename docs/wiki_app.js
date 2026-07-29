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
  // Onglets (hash persistant : #pane-veille rouvre l'onglet Veille)
  var boutons = document.querySelectorAll("nav.tabs button");
  function activer(nom) {
    boutons.forEach(function (b) { b.classList.toggle("actif", b.dataset.pane === nom); });
    document.querySelectorAll("section.pane").forEach(function (s) {
      s.classList.toggle("actif", s.id === "pane-" + nom);
    });
  }
  boutons.forEach(function (b) {
    b.addEventListener("click", function () {
      activer(b.dataset.pane);
      history.replaceState(null, "", "#pane-" + b.dataset.pane);
    });
  });
  var h = (location.hash || "").replace("#pane-", "");
  if (h && document.getElementById("pane-" + h)) activer(h);

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
    return "echec";   // echec (N) / erreur (...)
  }
  function libelleStatut(statut) {
    if (statut === "en cours") return "⏳ en cours";
    if (statut === "ok") return "✅ terminé";
    return "❌ " + statut;
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
    return '<div class="rapport-carte ' + classe + '">' +
      '<div class="rapport-entete">' +
        '<span class="rapport-titre">' + echapper(j.libelle) + '</span>' +
        '<span class="rapport-statut ' + classe + '">' + libelleStatut(j.status) + '</span>' +
      '</div>' +
      '<div class="rapport-heure">' + echapper(j.started) + (j.ended ? ' → ' + echapper(j.ended) : '') + '</div>' +
      decisionArbitrage(j, tousJobs) +
      '<details class="rapport-details" data-job="' + j.id + '"' + ouvert + '>' +
        '<summary>Détail du rapport</summary>' +
        '<pre class="rapport-sortie" data-job="' + j.id + '">' + tailHtml + '</pre>' +
      '</details>' +
    '</div>';
  }
  function zoneRapportPour(action) {
    if (action === "deploy") return "rapports-deploiement";
    if (action === "remediation" || action === "valider" || action === "refuser") return "rapports-correctifs";
    if (action === "pdf") return "rapports-exports";
    if (action === "veille" || action === "reflexion" || action === "deployer-veille") return "rapports-veille";
    return "rapports-agentic";
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

  function rafraichirJobs() {
    fetch(API + "/api/jobs").then(function (r) { return r.json(); }).then(function (d) {
      var jobs = d.jobs || [];
      // Un job qui se termine (n'est plus "en cours") restaure son bouton une seule fois.
      jobs.forEach(function (j) {
        if (j.status !== "en cours" && boutonParJob[j.id] && !jobsTermines[j.id]) {
          arreterChargement(boutonParJob[j.id]);
          jobsTermines[j.id] = true;
        }
      });
      var AGENTIC = ["scan", "scan-rapide", "sync-check", "package-check", "diagnostic", "audit"];
      remplirZone("rapports-agentic",
                  jobs.filter(function (j) { return AGENTIC.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action lancée dans cette session.");
      var CORRECTIFS = ["remediation", "valider", "refuser"];
      remplirZone("rapports-correctifs",
                  jobs.filter(function (j) { return CORRECTIFS.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action corrective lancée dans cette session.");
      remplirZone("rapports-deploiement",
                  jobs.filter(function (j) { return j.action === "deploy"; }), jobs,
                  "Aucun déploiement lancé dans cette session.");
      remplirZone("rapports-exports",
                  jobs.filter(function (j) { return j.action === "pdf"; }), jobs,
                  "Aucun export relancé dans cette session.");
      var VEILLE_ACTIONS = ["veille", "reflexion", "deployer-veille"];
      remplirZone("rapports-veille",
                  jobs.filter(function (j) { return VEILLE_ACTIONS.indexOf(j.action) !== -1; }), jobs,
                  "Aucune action de veille lancée dans cette session.");
      if (jobs.some(function (j) { return j.status === "en cours"; }))
        setTimeout(rafraichirJobs, 1500);
    }).catch(function () {});
  }

  // Délégation sur document (pas un forEach au chargement) : les boutons Valider/Invalider
  // sont injectés APRÈS coup par remplirZone (innerHTML) — un câblage one-shot au chargement
  // ne les verrait jamais. La délégation couvre statique et dynamique uniformément.
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-action]");
    if (!b) return;
    var corps = {};
    if (b.dataset.action === "audit")
      corps.projet = document.getElementById("audit-projet").value;
    if (b.dataset.action === "deployer-veille")
      corps.projet = document.getElementById("veille-deploy-projet").value;
    if (b.dataset.action === "remediation") corps.cible = b.dataset.cible;
    if (b.dataset.action === "deploy") {
      var champChemin = document.getElementById(b.dataset.cibleInput);
      var champNom = document.getElementById(b.dataset.nomInput);
      var champForce = document.getElementById(b.dataset.forceInput);
      corps.cible = champChemin ? champChemin.value.trim() : "";
      corps.nom = champNom ? champNom.value.trim() : "";
      corps.force = champForce ? champForce.checked : false;
      if (!corps.cible) { alert("Indiquer le dossier du nouveau projet avant de déployer."); return; }
    }
    var encart = null;
    if (b.dataset.action === "valider" || b.dataset.action === "refuser") {
      corps.cible = b.dataset.cible;
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
