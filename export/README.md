# export/ — kit agentic du hub de supervision

Bundle **auto-portant** du dispositif agentic éprouvé sur la flotte : skills de
pilotage, sous-agents porteurs, hooks de garde-fou, playbooks, catalogue et scripts
de supervision. Destiné à être **repris tel quel par un autre projet**, y compris
sur une machine qui n'a pas le hub.

Généré le **2026-09-01** par `py .claude/dispositif/export_agentic.py`.

> **Contenu généré.** Ne rien modifier ici : le correctif serait perdu à la
> régénération suivante. Corriger la source dans le hub, puis régénérer.
> `--check` signale la dérive entre les sources vivantes et ce répertoire.

## Installer dans un projet

```bash
py export/install_agentic.py --liste                      # ce qui serait installé, et où
py export/install_agentic.py --dry-run "C:/chemin/Projet"  # simulation, aucune écriture
py export/install_agentic.py "C:/chemin/Projet" --nom MonProjet
```

Aucun fichier existant n'est écrasé sans `--force`. `settings.json` n'est jamais
écrasé : ses hooks sont **fusionnés** (ceux du projet cible sont préservés, et
réinstaller ne duplique pas les hooks du dispositif).

## Contenu

| Fichier | Installé dans le projet cible |
| --- | --- |
| `supervision/scan_transcripts.py` | `.claude/supervision/scan_transcripts.py` |
| `orchestration/log_run.py` | `.claude/orchestration/log_run.py` |
| `supervision/log_usage.py` | `.claude/supervision/log_usage.py` |
| `supervision/write_diagnostic.py` | `.claude/supervision/write_diagnostic.py` |
| `supervision/refuser_arbitrage.py` | `.claude/supervision/refuser_arbitrage.py` |
| `hooks/guard_destructive_git.py` | `.claude/hooks/guard_destructive_git.py` |
| `hooks/orchestrator_gate.py` | `.claude/hooks/orchestrator_gate.py` |
| `hooks/remind_revue_increment.py` | `.claude/hooks/remind_revue_increment.py` |
| `hooks/warn_verif_before_commit.py` | `.claude/hooks/warn_verif_before_commit.py` |
| `hooks/remind_veille_agentic.py` | `.claude/hooks/remind_veille_agentic.py` |
| `skills/agent-orchestrator/SKILL.md` | `.claude/skills/agent-orchestrator/SKILL.md` |
| `skills/agent-supervisor/SKILL.md` | `.claude/skills/agent-supervisor/SKILL.md` |
| `skills/revue-increment/SKILL.md` | `.claude/skills/revue-increment/SKILL.md` |
| `skills/veille-agentic/SKILL.md` | `.claude/skills/veille-agentic/SKILL.md` |
| `skills/audit-technique/SKILL.md` | `.claude/skills/audit-technique/SKILL.md` |
| `skills/pptx-framed-image/SKILL.md` | `.claude/skills/pptx-framed-image/SKILL.md` |
| `skills/pptx-framed-image/scripts/framed_image.py` | `.claude/skills/pptx-framed-image/scripts/framed_image.py` |
| `skills/pptx-framed-image/scripts/stock_images.py` | `.claude/skills/pptx-framed-image/scripts/stock_images.py` |
| `skills/pptx-framed-image/scripts/nature_images.py` | `.claude/skills/pptx-framed-image/scripts/nature_images.py` |
| `skills/pptx-framed-image/tests/test_framed_image.py` | `.claude/skills/pptx-framed-image/tests/test_framed_image.py` |
| `skills/slide-text-polish/SKILL.md` | `.claude/skills/slide-text-polish/SKILL.md` |
| `skills/slide-text-polish/scripts/slide_lint.py` | `.claude/skills/slide-text-polish/scripts/slide_lint.py` |
| `skills/slide-text-polish/tests/test_slide_lint.py` | `.claude/skills/slide-text-polish/tests/test_slide_lint.py` |
| `skills/deck-design-library/SKILL.md` | `.claude/skills/deck-design-library/SKILL.md` |
| `skills/deck-design-library/references/catalogue-restitution.md` | `.claude/skills/deck-design-library/references/catalogue-restitution.md` |
| `skills/pdf-quality/SKILL.md` | `.claude/skills/pdf-quality/SKILL.md` |
| `skills/pdf-quality/scripts/pdf_report.py` | `.claude/skills/pdf-quality/scripts/pdf_report.py` |
| `skills/pdf-quality/scripts/pdf_verify.py` | `.claude/skills/pdf-quality/scripts/pdf_verify.py` |
| `skills/pdf-quality/tests/test_pdf_quality.py` | `.claude/skills/pdf-quality/tests/test_pdf_quality.py` |
| `agents/agent-orchestrator.md` | `.claude/agents/agent-orchestrator.md` |
| `agents/agent-supervisor.md` | `.claude/agents/agent-supervisor.md` |
| `agents/veille-agentic.md` | `.claude/agents/veille-agentic.md` |
| `agents/bmad-revue.md` | `.claude/agents/bmad-revue.md` |
| `agents/bmad-doc.md` | `.claude/agents/bmad-doc.md` |
| `agents/bmad-recherche.md` | `.claude/agents/bmad-recherche.md` |
| `agents/bmad-cadrage.md` | `.claude/agents/bmad-cadrage.md` |
| `agents/bmad-livraison.md` | `.claude/agents/bmad-livraison.md` |
| `orchestration/catalogue.md` | `.claude/orchestration/catalogue.md` |
| `orchestration/git_agents_inventory.py` | `.claude/orchestration/git_agents_inventory.py` |
| `orchestration/generate_bmad_playbook.py` | `.claude/orchestration/generate_bmad_playbook.py` |
| `orchestration/playbooks/FORMAT.md` | `.claude/orchestration/playbooks/FORMAT.md` |
| `orchestration/playbooks/dev-verifie.md` | `.claude/orchestration/playbooks/dev-verifie.md` |
| `orchestration/playbooks/export-ppt-verifie.md` | `.claude/orchestration/playbooks/export-ppt-verifie.md` |
| `orchestration/playbooks/revue-design-parallele.md` | `.claude/orchestration/playbooks/revue-design-parallele.md` |
| `orchestration/playbooks/evolution-flotte.md` | `.claude/orchestration/playbooks/evolution-flotte.md` |
| `commands/orchestre.md` | `.claude/commands/orchestre.md` |
| `party/bmad-party-mode.toml` | `_bmad/custom/bmad-party-mode.toml` |

Plus `install_agentic.py` (l'installateur), `MANIFESTE.json` (la table ci-dessus,
les gabarits `settings.json`/`CLAUDE.md` et la checklist) et ce README.

## Ce que l'installation ne fait pas

- Elle n'installe **pas BMAD** : les skills `bmad-*` s'installent séparément, et la
  table de routage de l'orchestrateur ne vaut que si elles sont présentes. Cela vaut
  aussi pour les **salles** : `_bmad/custom/bmad-party-mode.toml` est un *override*
  de la skill `bmad-party-mode` — sans cette skill installée, il est inerte, et
  silencieusement. Le vérifier après installation (checklist).
- Les 12 salles arrivent avec les **relais de la flotte du hub** (`relais-vscode1`…) :
  ce sont les contraintes réelles des dépôts supervisés, pas celles du projet cible.
  Sur un projet hors flotte, écrire son propre relais plutôt que d'emprunter un voisin.
- Elle n'adapte **pas** les hooks au canal du projet : `warn_verif_before_commit.py`
  contient des préfixes surveillés à ajuster (checklist, étape 1).
- Elle n'inscrit **pas** le projet au scan de la flotte : c'est `projets.json` du hub.
- Deux hooks (`remind_revue_increment`, `warn_verif_before_commit`) sont pris dans leur
  version **générique** (VSCode3) et non dans celle du hub, spécialisée supervision.
- `revue-increment` exportée est la version du hub, orientée supervision (journal,
  arbitrages, wiki) : dans un projet applicatif, sa passe 2 est à réécrire sur le
  canal réel du projet — tests, rendu, livrable.
