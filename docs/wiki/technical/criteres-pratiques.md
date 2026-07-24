# Référentiel de critères — pratiques de la flotte

Établi le 2026-07-23 sur investigation des référentiels faisant autorité (sources en fin
de section). C'est la **cible d'amélioration** du dispositif : chaque domaine liste ses
critères de référence, ce que la flotte **mesure déjà** (scan déterministe ou audit), et
les **écarts à outiller** — qui alimenteront les prochains findings du superviseur.

Légende : ✅ mesuré par le scan déterministe · 🔍 couvert par l'audit qualitatif ·
⬜ non mesuré aujourd'hui (cible d'amélioration).

---

## 1. Pratiques de développement — référentiel : DORA capabilities

Les capacités techniques du programme DORA (Google Cloud), corrélées empiriquement à la
performance de livraison (déploiement fréquent, lead time court, faible taux d'échec).

| Critère | Mesure flotte |
| --- | --- |
| Gestion de version pour tout (code, config, scripts) | ✅ (repo git + dernier commit + dette non commitée) |
| Linter/analyse statique configuré et exécuté | ✅ (dimension pratiques+rules : ruff/ESLint) |
| Intégration continue (build+tests à chaque push) | ✅ (CI présente — seule VSCode1 l'a) |
| Automatisation du déploiement | ⬜ (aucun projet n'a de déploiement outillé — pertinence à évaluer, projets locaux) |
| Trunk-based development (branches courtes, < 3 actives) | ⬜ (mesurable via `git branch` — à ajouter au scan) |
| Revue de code systématique avant merge/commit | ✅ (dimension revue : agent reviewer/hook pré-commit) |
| Dépendances épinglées / build reproductible | 🔍 (audit risque technique — constat : VSCode2 tout en `>=`, lockfile OK sur VSCode1) |
| Documentation du code à jour (voir § 3) | ✅ partiel |
| Rules/conventions explicites (CLAUDE.md, conventions.md) | ✅ |

**Écarts à outiller** : détection trunk-based (branches), fraîcheur des dépendances
(épinglage + versions vulnérables connues), temps de lead (commit→livrable).

## 2. Pratiques de test — référentiels : pyramide de tests + ISO/IEC 25010

Pyramide (beaucoup d'unitaires rapides, moins d'intégration, peu d'e2e — mais des e2e
RÉELS sur le livrable) + les caractéristiques qualité ISO 25010 comme axes de test.

| Critère | Mesure flotte |
| --- | --- |
| Tests unitaires présents sur la logique métier | ✅ (compte de fichiers de test) |
| Couverture mesurée (pas forcément gatée) | ✅ (coverage configuré — fait sur VSCode1 84,7 % / VSCode2 ~38 %) |
| Tests fonctionnels sur l'artefact RÉEL (rendu, PDF re-parsé, navigateur) | ✅ (marqueurs puppeteer/pymupdf/Presentation/TestClient) |
| Chemin critique couvert (le cœur qui fait la valeur) | 🔍 (audit — constat : calcul de scores VSCode1 non testé, export PPT hors `npm test`) |
| Tests d'erreur/cas limites (pas seulement le chemin heureux) | 🔍 (audit robustesse) |
| Tests en CI (pas seulement en local) | ✅ (CI VSCode1) |
| Seuil de couverture gaté (une fois la mesure stabilisée) | ⬜ (décision différée volontairement : mesurer d'abord) |
| Tests de non-régression sur bug corrigé | ⬜ (non détectable automatiquement — discipline à documenter dans conventions) |

**Écarts à outiller** : part unitaire/intégration/e2e (forme de la pyramide), couverture
du chemin critique identifié par projet, tendance de couverture (snapshots).

## 3. Pratiques de documentation — référentiel : Diátaxis

Quatre besoins distincts → quatre formes : **tutorial** (apprentissage), **how-to**
(objectif), **référence** (information), **explication** (compréhension). Qualité
fonctionnelle (exactitude, complétude) ET qualité profonde (répond au besoin réel).

| Critère | Mesure flotte |
| --- | --- |
| Porte d'entrée : README avec install/usage (= how-to minimal) | ✅ (dimension documentation) |
| Référence technique à jour (stack, architecture, conventions) | ✅ partiel (wiki technical présent sur 3 projets) |
| Rules d'agent (CLAUDE.md) présentes et opérantes | ✅ |
| Explication (docs de conception, pourquoi des choix) | ✅ partiel (docs/reflexions ici ; non mesuré ailleurs) |
| Doc générée jamais éditée à la main (marquée comme telle) | ✅ (pratique en place ici — wiki généré) |
| Exactitude : la doc correspond au code réel (pas de doc morte) | ⬜ (non mesuré — un audit doc pourrait comparer commandes documentées vs réelles) |
| Les 4 formes Diátaxis distinguées (pas un fourre-tout) | ⬜ (analyse qualitative à la demande) |

**Écarts à outiller** : détection de doc périmée (commandes/chemins documentés qui
n'existent plus — greppable), datation des sections (fraîcheur).

## 4. Cadrage produit — référentiels : 4 risques de Cagan + Opportunity Solution Tree (Torres)

Cagan (*Inspired*) : toute discovery doit adresser 4 risques — **valeur** (en veulent-ils ?),
**utilisabilité** (savent-ils s'en servir ?), **faisabilité** (peut-on le construire ?),
**viabilité** (est-ce soutenable ?). Torres : arbre outcome → opportunités (besoins) →
solutions, pour relier chaque solution à un besoin réel.

| Critère | Mesure flotte |
| --- | --- |
| Persona / utilisateur cible nommé | ✅ (marqueur persona) |
| Why / problème à résoudre explicite | ✅ (marqueur why/pourquoi) |
| Besoins / pain points formalisés | ✅ (marqueur besoins) |
| Proposition de valeur écrite | ✅ (marqueur valeur) |
| Product brief ou PRD structuré (BMAD ou autre) | ✅ (artefact product-brief détecté) |
| Les 4 risques de Cagan adressés explicitement | ⬜ (analyse qualitative — remédiation `bmad-prfaq`/`bmad-forge-idea`) |
| Lien outcome → solution (chaque feature rattachée à un besoin) | ⬜ (non mesuré — pertinent surtout sur VSCode1/VSCode2) |
| Mesure de succès définie (comment on saura que ça marche) | ⬜ (ajoutable au détecteur : marqueur « mesure de succès / KPI ») |
| Non-objectifs explicites (ce que le produit ne fait pas) | ⬜ (ajoutable au détecteur) |

**Écarts à outiller** : marqueurs « mesure de succès » et « non-objectifs » dans le scan ;
audit produit qualitatif (les 4 risques) via `bmad-agent-pm`/`bmad-prfaq` sur demande.

## 5. Sécurité — référentiels : OWASP ASVS 5.0 (~350 exigences, 17 chapitres) + SAMM (3 niveaux de maturité)

ASVS pour le **quoi vérifier** dans l'application ; SAMM pour la **maturité du
processus**. Adapté à l'échelle de la flotte (projets locaux mono-utilisateur, mais
manipulant des données réelles — PII d'interviews et de répondants).

| Critère (sous-ensemble ASVS pertinent flotte) | Mesure flotte |
| --- | --- |
| Secrets jamais commités (.env gitigné, placeholders) | ✅ proxy + 🔍 audit (constat : .env.dev/prod commités sur VSCode1 — sans secret) |
| Pas d'injection de commande (subprocess en liste, jamais shell=True) | 🔍 audit (6/6 sains) |
| Pas d'eval/pickle/désérialisation non sûre | 🔍 audit (6/6 sains) |
| Entrées utilisateur validées (taille, type, chemin assaini) | 🔍 audit (constats : upload audio sans cap VSCode2, JSON→500 VSCode) |
| SQL paramétré (jamais de concaténation d'entrée) | 🔍 audit (VSCode1/VSCode2 sains) |
| **Authentification là où des données personnelles sont exposées** | 🔍 audit — **constat majeur : API VSCode1 sans aucune auth avec PII** |
| Exposition réseau minimale (bind localhost par défaut) | 🔍 audit — **constat : VSCode écoute 0.0.0.0 en exécutant PowerShell** |
| Garde-fous d'agent (deny rules, guard git destructif) | ✅ proxy |
| Dépendances sans vulnérabilité connue (audit npm/pip) | ⬜ (`npm audit` signalé une fois — à outiller dans le scan) |
| Modélisation de menace même légère (SAMM L1) | ⬜ (à faire une fois par projet à données réelles) |

**Écarts à outiller** : `pip-audit`/`npm audit` dans le scan (déterministe), suivi des
2 constats majeurs (auth VSCode1, bind VSCode) comme findings.

## 6. Pratiques data — référentiel : DAMA-DMBOK (dimensions qualité) + cycle de vie

Nouveau domaine (aucune mesure aujourd'hui). Dimensions qualité DAMA : complétude,
validité, exactitude, cohérence, unicité, fraîcheur. Pertinent surtout pour VSCode1
(répondants/PII, SQLite) et VSCode2 (interviews/verbatims clients, SQLite).

| Critère | Mesure flotte |
| --- | --- |
| Inventaire des données sensibles (où sont les PII ?) | ⬜ — VSCode1 : répondants nominatifs ; VSCode2 : verbatims d'interviews clients |
| Sauvegarde outillée et testée (backup + restore) | ⬜ (VSCode1 a backup-db.js/restore — non vérifié régulièrement) |
| Isolation dev/réel (la base réelle jamais écrasée par les tests) | ✅ partiel (conventions VSCode2 : APP_DB_PATH isolé par conftest) |
| Rétention/purge définies (combien de temps garde-t-on les verbatims ?) | ⬜ |
| Migrations de schéma outillées (pas de DDL artisanal) | 🔍 audit (constat : migrations f-string VSCode2) |
| Qualité des données mesurée (complétude/validité sur les tables clés) | ⬜ |
| Anonymisation/pseudonymisation quand possible (exports, demos) | ⬜ (seed-demo existe sur VSCode1/VSCode2 — à vérifier) |

**Écarts à outiller** : détecteur data au scan (présence backup/restore, seed-demo,
isolation de test), puis audit data qualitatif sur VSCode1/VSCode2 (les 2 projets à PII).

---

## 7. Pratiques agentic — référentiels : docs providers (Anthropic/Claude Code, OpenAI, Mistral, GitHub)

Le domaine propre à cette flotte : des projets **développés avec des agents**. La cible
vient des documentations officielles des providers (pas d'un standard figé — elles
bougent vite, d'où l'alimentation continue par le volet 2 de `veille-agentic`).

| Critère | Mesure flotte |
| --- | --- |
| Contexte projet versionné (CLAUDE.md / règles d'agent par projet) | ✅ (dimension « Pratiques + rules » du scan) |
| Skills packagées pour les workflows récurrents (au lieu de prompts répétés) | ✅ (inventaire skills du scan + catalogue orchestrateur) |
| Garde-fous outillés : hooks destructifs, deny rules, permissions explicites | ✅ (dimension « Sécurité (proxy) » : guard git, deny rules) |
| Supervision de l'usage réel des agents (transcripts → métriques → diagnostic) | ✅ (dispositif étage 1+2 de ce hub — canon partagé) |
| Vérification réelle des livrables d'agent (rendu regardé, pas confiance aveugle) | ✅ (dimension « Test fonctionnel / rendu réel » + pptx-verify) |
| Boucle humaine sur les actions irréversibles (propose → arbitre → applique) | ✅ (arbitrages.json + checkpoints des playbooks) |
| Mémoire projet persistante entretenue (faits durables hors contexte de session) | ⬜ (mémoires présentes côté hub — non mesuré par projet) |
| Sous-agents scopés pour l'exploration volumineuse (contexte principal préservé) | ⬜ (règle du catalogue orchestrateur — usage non mesuré à froid) |

**Alimentation** : le volet 2 de `veille-agentic` (docs providers) propose des entrées
`pratique` avec `regle_proposee` (candidate à devenir un critère ci-dessus) et
`action_corrective` (correctif flotte arbitrable). Une pratique passée `adopte` par
l'utilisateur est intégrée ici, et au scan si mesurable à froid.

---

## Sources

- DORA capabilities : [dora.dev/capabilities](https://dora.dev/capabilities/) (continuous delivery, test automation, trunk-based…)
- OWASP ASVS 5.0 : [owasp.org/www-project-application-security-verification-standard](https://owasp.org/www-project-application-security-verification-standard/) · SAMM : [devguide.owasp.org…/samm](https://devguide.owasp.org/en/11-security-gap-analysis/01-guides/01-samm/)
- Diátaxis : [diataxis.fr](https://diataxis.fr/) (tutorials / how-to / reference / explanation + qualité fonctionnelle vs profonde)
- Cagan, 4 risques de discovery (*Inspired*) · Torres, Opportunity Solution Tree : [productcompass.pm](https://www.productcompass.pm/p/what-exactly-is-product-discovery)
- DAMA-DMBOK dimensions qualité : [dama.org](https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/) · [DDQ research paper (DAMA-NL)](https://dama-nl.org/wp-content/uploads/2020/09/DDQ-Dimensions-of-Data-Quality-Research-Paper-version-1.2-d.d.-3-Sept-2020.pdf)
- Pratiques agentic : [docs Claude Code](https://code.claude.com/docs) · [Anthropic — building effective agents](https://www.anthropic.com/research/building-effective-agents) · [OpenAI platform — agents](https://platform.openai.com/docs/guides/agents) · [docs Mistral](https://docs.mistral.ai/) — surveillées par le volet 2 de `veille-agentic`

## Gouvernance de ce référentiel

Ce document est la **cible** ; le scan et les audits sont la **mesure** ; l'écart entre
les deux alimente les findings du superviseur (`pratique-*`), arbitrés puis appliqués via
`evolution-flotte`. Réviser ce référentiel quand la veille (`veille-agentic`) détecte une
évolution des sources (ex. ASVS 5.x, révision DMBOK).
