"""Verrou de l'intégration BMAD au workflow de l'orchestrateur (2026-07-30).

Le TODO `agent-mort` du wiki disait : 46 skills BMAD installées, **0 invocation sur
113 sessions**. Cause mesurée : la règle « uniquement sur demande explicite, via
bmad-help » — une skill que personne ne nomme n'est jamais invoquée. L'arbitrage
utilisateur a remplacé cette règle par une table de routage besoin → skill →
sous-agent porteur → régime de déclenchement.

Ces tests protègent l'invariant qui fait vivre la table : **toute skill bmad-*
installée y figure** (sinon elle retombe silencieusement dans l'oubli qu'on vient de
corriger), et **tout sous-agent cité existe** (une table qui route vers un agent
absent est une panne à l'exécution). Ils testent des FICHIERS de configuration, ce
qui est le seul moyen de tester du dispositif déclaratif.
"""

import os
import re

import pytest

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(HUB, ".claude", "skills")
AGENTS_DIR = os.path.join(HUB, ".claude", "agents")
ORCHESTRATEUR = os.path.join(SKILLS_DIR, "agent-orchestrator", "SKILL.md")
MARQUEUR_DEBUT = "<!-- BMAD-ROUTAGE:START"
MARQUEUR_FIN = "<!-- BMAD-ROUTAGE:END -->"

MODELES_VALIDES = {"haiku", "sonnet", "opus", "fable", "inherit"}


def lire(chemin):
    with open(chemin, encoding="utf-8") as fh:
        return fh.read()


def bmad_installees():
    """Les skills bmad-* réellement présentes sur le disque."""
    return sorted(
        d for d in os.listdir(SKILLS_DIR)
        if d.startswith("bmad-")
        and os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md")))


def bloc_routage():
    txt = lire(ORCHESTRATEUR)
    debut = txt.index(MARQUEUR_DEBUT)
    fin = txt.index(MARQUEUR_FIN)
    return txt[debut:fin]


def lignes_routage():
    """(besoin, skill, sous-agent porteur, déclenchement) par ligne de la table."""
    out = []
    for ligne in bloc_routage().splitlines():
        cols = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cols) != 4 or cols[0].startswith("---") or cols[0] == "Besoin détecté dans la demande":
            continue
        skill = re.fullmatch(r"`([a-z0-9-]+)`", cols[1])
        porteur = re.fullmatch(r"`([a-z0-9-]+)`", cols[2])
        if not (skill and porteur):
            continue
        out.append((cols[0], skill.group(1), porteur.group(1), cols[3]))
    return out


def non_routees():
    """Les skills installées que la table décide de NE PAS router : dépréciées par
    BMAD, ou gelées par un arbitrage utilisateur encore en vigueur.

    La zone se lit « `a`, `b` → utiliser `c` » : `c` est la skill CANONIQUE de
    remplacement, qui est routée. La compter comme non routée rendait le garde-fou
    de couverture faussement satisfaisable — une skill ni routée ni déclarée pouvait
    passer pour couverte du simple fait d'être citée comme cible de redirection.
    """
    txt = bloc_routage()
    zone = txt.split("**Jamais routées**")[-1]
    zone = re.sub(r"→[^;.\n]*", "", zone)
    return set(re.findall(r"`(bmad-[a-z0-9-]+)`", zone))


def agents_installes():
    return sorted(f[:-3] for f in os.listdir(AGENTS_DIR) if f.endswith(".md"))


def frontmatter(chemin):
    txt = lire(chemin)
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", txt, re.DOTALL)
    assert m, f"{chemin} : pas de frontmatter YAML"
    out = {}
    for ligne in m.group(1).splitlines():
        cle, sep, val = ligne.partition(":")
        if not sep or cle != cle.strip():
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[cle.strip()] = val
    return out


class TestTableDeRoutage:
    def test_toute_skill_bmad_installee_est_routee_ou_declaree_non_routee(self):
        """LE test de l'incrément : une skill installée hors table est une skill
        qui redevient invisible — exactement le trou de 46/46 qu'on vient de fermer.
        Ne pas router est un choix légitime, mais il doit être ÉCRIT."""
        routees = {skill for _, skill, _, _ in lignes_routage()}
        couvertes = routees | non_routees()
        oubliees = sorted(set(bmad_installees()) - couvertes)
        assert not oubliees, (
            "skills BMAD installées mais absentes de la table de routage de "
            f"agent-orchestrator/SKILL.md : {oubliees}")

    def test_aucune_skill_fantome_dans_la_table(self):
        """Router vers une skill non installée casse à l'invocation."""
        installees = set(bmad_installees())
        fantomes = sorted(
            {s for _, s, _, _ in lignes_routage()} - installees) + sorted(
            non_routees() - installees)
        assert not fantomes, f"skills routées mais absentes du disque : {fantomes}"

    def test_aucune_skill_a_la_fois_routee_et_non_routee(self):
        """Une skill ne peut pas être dans la table ET déclarée jamais routée : le
        plan qui la lit ne saurait pas quoi en faire. Ce test a une histoire — la
        levée du gel de `bmad-customize` (2026-07-31) a d'abord été rédigée SOUS le
        titre « Jamais routées », qui aspire tous les backticks jusqu'à la fin du
        bloc : la skill se retrouvait routée et non routée à la fois."""
        routees = {skill for _, skill, _, _ in lignes_routage()}
        double = sorted(routees & non_routees())
        assert not double, (
            "skills à la fois dans la table de routage et déclarées jamais "
            f"routées : {double}")

    def test_la_levee_du_gel_bmad_customize_est_tracee(self):
        """Le gel « aucune customisation jusqu'à la v7 » (arbitrage
        skills-jamais-utilisees du 2026-07-27) a été levé le 2026-07-31 : décision de
        rester en v6 et de customiser, plutôt que d'attendre une version qui ne sort
        pas. Ce qui est verrouillé ici n'est pas la décision — c'est sa TRAÇABILITÉ :
        une skill dégelée sans arbitrage écrit serait une auto-levée, soit R4 à
        l'envers. Si un jour le gel est reposé, ce test doit être réécrit avec lui."""
        routees = {skill for _, skill, _, _ in lignes_routage()}
        assert "bmad-customize" in routees, (
            "gel levé le 2026-07-31 : bmad-customize doit être routée")
        assert "bmad-customize" not in non_routees()

        regime = {s: d for _, s, _, d in lignes_routage()}["bmad-customize"]
        assert regime == "proposé", (
            f"bmad-customize écrit un fichier réel : régime attendu 'proposé', lu '{regime}'")

        # Assertion sur l'OBJET CHARGÉ, jamais sur une sous-chaîne du fichier.
        # Première version vacante (prouvée par mutation, diagnostic du 2026-07-31) :
        # elle cherchait « bmad-customize » et « 2026-07-31 » n'importe où dans le
        # fichier, deux conditions que d'autres entrées sans rapport satisfont — le
        # test restait VERT après suppression de l'arbitrage qu'il est censé exiger.
        import json
        with open(os.path.join(HUB, ".claude", "supervision", "arbitrages.json"),
                  encoding="utf-8") as fh:
            arbitrages = json.load(fh)["arbitrages"]
        levee = [a for a in arbitrages
                 if a.get("cible") == "bmad-customize" and a.get("date") == "2026-07-31"]
        assert levee, (
            "aucun arbitrage de cible « bmad-customize » au 2026-07-31 : une skill "
            "dégelée sans arbitrage écrit est une auto-levée, soit R4 à l'envers.")
        decision = levee[0].get("decision", "")
        assert "LEVEE" in decision.upper() or "LEVÉE" in decision.upper(), (
            f"l'arbitrage existe mais ne dit pas qu'il lève le gel : {decision[:120]}")

    def test_chaque_porteur_existe_dans_claude_agents(self):
        """`inline` est un porteur LÉGITIME et volontairement sans fichier.

        Quatre porteurs jamais invoqués ont été mis en sommeil le 2026-09-01, et les
        29 rangées qui les nommaient portent maintenant `inline` — la skill reste
        routée, elle part dans la conversation courante (§ 2 quinquies le documente
        déjà comme le régime normal des skills bornées). Écrire `—` à la place aurait
        rendu ces rangées INILLISIBLES par `lignes_routage()`, donc leurs 29 skills
        « non routées » : exactement le trou de 46/46 que ce fichier existe pour
        fermer. Le premier essai est passé par là, et ce test l'a attrapé.
        """
        presents = set(agents_installes()) | {"inline"}
        manquants = sorted({p for _, _, p, _ in lignes_routage()} - presents)
        assert not manquants, f"sous-agents porteurs cités mais absents : {manquants}"

    def test_inline_ne_masque_pas_un_porteur_reellement_absent(self):
        """Le garde-fou de l'exemption : `inline` ne doit pas devenir la case où l'on
        range un porteur cassé. Tout porteur cité qui N'EST PAS `inline` doit exister."""
        cites = {p for _, _, p, _ in lignes_routage()} - {"inline"}
        assert cites, "plus aucun porteur nommé : la table ne route plus que de l'inline"
        assert cites <= set(agents_installes())

    def test_les_deux_regimes_seulement(self):
        regimes = {d for _, _, _, d in lignes_routage()}
        assert regimes == {"d'office", "proposé"}, regimes

    def test_les_46_sont_bien_46(self):
        """Si BMAD est mis à jour, ce compte bouge — et la table doit bouger avec
        (le test précédent le dira). Le nombre est ici pour rendre l'écart visible."""
        assert len(bmad_installees()) == 46

    def test_les_structurantes_ne_sont_jamais_en_declenchement_d_office(self):
        """Garde-fou de COÛT : PRD, architecture, stories, code et party-mode
        engagent des minutes et une facture — ils s'annoncent avant de partir."""
        structurantes = {
            "bmad-prd", "bmad-architecture", "bmad-dev-story", "bmad-dev-auto",
            "bmad-quick-dev", "bmad-create-epics-and-stories", "bmad-party-mode",
        }
        fautives = [s for _, s, _, d in lignes_routage()
                    if s in structurantes and d != "proposé"]
        assert not fautives, fautives

    def test_aucune_skill_qui_ecrit_un_fichier_n_est_en_declenchement_d_office(self):
        """Garde-fou d'ÉCRITURE, ajouté par l'arbitrage du finding
        `orchestrateur:regime-office-ecriture` (2026-07-30).

        Le premier jeu de régimes ne pesait que le coût : quatre skills de
        documentation partaient donc « d'office » alors qu'elles écrivent, déplacent
        ou restructurent des fichiers réels — et R4 n'interdit pas la dépense, il
        interdit l'auto-application. Le test précédent passait vert sur exactement ce
        trou, parce qu'il ne connaissait que la liste des skills chères."""
        ecrivent = {
            "bmad-document-project", "bmad-index-docs", "bmad-shard-doc",
            "bmad-agent-tech-writer",
        }
        fautives = [s for _, s, _, d in lignes_routage()
                    if s in ecrivent and d != "proposé"]
        assert not fautives, (
            f"skills qui écrivent un fichier réel laissées en « d'office » : {fautives}")

    def test_l_ancienne_regle_de_blocage_a_disparu(self):
        """Non-régression du changement demandé : la mention qui produisait
        0 invocation ne doit pas revenir par un copier-coller."""
        txt = lire(ORCHESTRATEUR)
        assert "Uniquement sur demande explicite" not in txt


class TestFrontmatterDesSousAgents:
    def test_il_y_a_des_sous_agents(self):
        assert agents_installes(), ".claude/agents/ est vide"

    def test_nom_du_frontmatter_egale_nom_du_fichier(self):
        """Claude Code résout un subagent_type par son `name` : un décalage avec le
        nom de fichier rend l'agent introuvable alors qu'il est là."""
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            assert fm.get("name") == nom, (nom, fm.get("name"))

    def test_description_non_vide(self):
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            assert len(fm.get("description", "")) > 40, nom

    def test_modele_dans_le_vocabulaire_connu_ou_absent(self):
        for nom in agents_installes():
            fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
            if "model" in fm:
                assert fm["model"] in MODELES_VALIDES, (nom, fm["model"])

    @pytest.mark.parametrize("nom", agents_installes())
    def test_les_porteurs_ont_bien_l_outil_skill(self, nom):
        """Sans l'outil `Skill`, un sous-agent ne peut pas invoquer la skill qu'il
        porte — et l'étage 1 ne compterait rien (c'est le cas connu de ppt-designer).

        La liste était ÉCRITE EN DUR (8 noms) : mettre un porteur en sommeil faisait
        donc échouer le test sur un fichier volontairement retiré, et ajouter un
        porteur ne le couvrait pas. Elle vient de `.claude/agents/` depuis le
        2026-09-01 — la même source que le reste du fichier.
        """
        fm = frontmatter(os.path.join(AGENTS_DIR, nom + ".md"))
        outils = [o.strip() for o in fm.get("tools", "").split(",")]
        assert "Skill" in outils, (nom, outils)

    def test_le_porteur_de_revue_a_l_outil_agent(self):
        """`bmad-code-review` est bâtie sur des couches ADVERSARIALES INDÉPENDANTES —
        Blind Hunter, Edge Case Hunter, Acceptance Auditor — dont tout l'intérêt est
        qu'aucune ne voit ce que les autres ont trouvé. Sans l'outil `Agent`, le porteur
        ne peut pas les dispatcher : elles s'exécutent en séquence dans un seul contexte,
        et la troisième lit ce que la première a écrit. Le garde-fou anti-complaisance du
        dispositif devient alors un relecteur unique qui se relit.

        Finding `bmad-revue` (priorité 5, diagnostic VSCode2 du 2026-09-01), arbitré le
        2026-09-02. La dégradation ne se déduit pas, elle est ENREGISTRÉE DEUX FOIS dans
        `runs.jsonl` par les runs eux-mêmes : 2026-08-31T22:07 (« couche aveugle de la
        revue affaiblie, porteur sans outil Agent, layers en séquence, resolution:
        porteur-degrade bmad-code-review ») et 2026-09-01T18:32 (« limite : indépendance
        des couches non tenue chez le 2e relecteur, pas d'outil Agent dans son contexte »).

        Test nommément sur `bmad-revue` et non sur tous les porteurs : `bmad-recherche`
        et `veille-agentic` n'ont aucune couche parallèle à dispatcher, leur donner
        `Agent` serait élargir une surface sans besoin mesuré.
        """
        fm = frontmatter(os.path.join(AGENTS_DIR, "bmad-revue.md"))
        outils = [o.strip() for o in fm.get("tools", "").split(",")]
        assert "Agent" in outils, (
            "le porteur de revue ne peut pas dispatcher ses couches adversariales : "
            f"outils déclarés = {outils}")

    def test_le_superviseur_n_a_ni_write_ni_edit(self):
        """Garde-fou STRUCTUREL de R4 : le superviseur propose, il n'applique pas.
        Sans outil d'écriture, il ne peut ni éditer diagnostic.json à la main, ni
        toucher au wiki généré, ni « corriger » au passage. Retirer cette contrainte
        rend la gouvernance déclarative au lieu d'effective."""
        fm = frontmatter(os.path.join(AGENTS_DIR, "agent-supervisor.md"))
        outils = {o.strip() for o in fm.get("tools", "").split(",")}
        assert "Write" not in outils and "Edit" not in outils, outils

    def test_tout_sous_agent_a_shell_interdit_explicitement_les_commandes_git(self):
        """L'irréversible reste à la session principale.

        PREMIÈRE VERSION FAUSSE, gardée en mémoire ici parce qu'elle a été prise en
        flagrant délit par le diagnostic étage 2 du 2026-07-30 : elle assertait
        `not (outils & {"Commit", "Git"})`. Aucun outil de Claude Code ne porte ces
        noms — l'assertion était VIDE, verte par construction, pendant que 6 des 8
        sous-agents portaient `Bash`/`PowerShell` et pouvaient donc committer sur les
        6 dépôts de la flotte. Un test qui ne peut pas échouer est pire qu'aucun test :
        il fait croire le garde-fou en place.

        Le garde-fou réel est TEXTUEL (l'agent lit son mandat), donc c'est sur le texte
        que le test doit porter — et sur les seuls agents qui ont réellement la
        capacité de le violer."""
        shells = {"Bash", "PowerShell"}
        verifies = 0
        for nom in agents_installes():
            chemin = os.path.join(AGENTS_DIR, nom + ".md")
            fm = frontmatter(chemin)
            outils = {o.strip() for o in fm.get("tools", "").split(",")}
            if not (outils & shells):
                continue          # sans shell, pas de git possible : rien à interdire
            corps = lire(chemin)
            for interdit in ("git add", "git commit", "git push", "git reset"):
                assert f"`{interdit}`" in corps, (
                    f"{nom} porte {sorted(outils & shells)} mais son mandat "
                    f"n'interdit pas explicitement `{interdit}`")
            verifies += 1
        # Le plancher était ÉCRIT EN DUR (`>= 6`), calé sur les 8 porteurs de l'époque.
        # Mettre 4 porteurs en sommeil le 2026-09-01 l'a rendu impossible à satisfaire :
        # le test échouait sur la TAILLE de la population, pas sur ce qu'il garde.
        # Il compte désormais la population réelle — la propriété anti-vidage tient
        # toujours (si les outils changeaient de nom, `attendus` tomberait à 0 et le
        # `>= 1` crierait), mais elle ne dépend plus d'un effectif figé.
        attendus = sum(
            1 for nom in agents_installes()
            if {o.strip() for o in frontmatter(
                os.path.join(AGENTS_DIR, nom + ".md")).get("tools", "").split(",")} & shells)
        assert verifies == attendus, (verifies, attendus)
        assert verifies >= 1, (
            "aucun sous-agent à shell vérifié — le test se serait vidé en silence si "
            "les outils avaient changé de nom")


class TestCommandeOrchestre:
    def test_la_commande_existe_et_charge_la_skill(self):
        chemin = os.path.join(HUB, ".claude", "commands", "orchestre.md")
        assert os.path.isfile(chemin)
        txt = lire(chemin)
        assert "agent-orchestrator" in txt
        assert "$ARGUMENTS" in txt
