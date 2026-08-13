# Tools (PersonalHostel)

Kanban CLI y skills para agentes. El **flujo completo** (Detectado → Changelog, Debate con 4 opciones, labels, verificación) está en [`AGENTS.md`](../AGENTS.md) — léelo antes de crear o mover ítems.

Skills: `tools/agent-skills/jarvis-github-kanban/SKILL.md` y `jarvis-github-agentuse/SKILL.md`.

```bash
cd tools/kanban-cli
bun install
cd ../..

copy .kanbanrc.json.template .kanbanrc.json   # Windows
# cp .kanbanrc.json.template .kanbanrc.json

bun run tools/kanban-cli/cli.ts config validate
bun run tools/kanban-cli/cli.ts list
```

Tras crear o cambiar opciones de un SingleSelect, regenerar IDs (ver AGENTS.md: `config generate`, restaurar `repoId`/`repo`, `config validate`, actualizar `.kanbanrc.json.template`). Nunca `convert-draft` con `repoId` = `REPLACE_ME`.
