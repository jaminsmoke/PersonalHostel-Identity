# Tools (PersonalHostel)

Kanban CLI y skills para agentes. Copiados desde el patrón de Personal Comander (`jaminsmoke/jarvis-skills`).

```bash
cd tools/kanban-cli
bun install
cd ../..

copy .kanbanrc.json.template .kanbanrc.json   # Windows
# cp .kanbanrc.json.template .kanbanrc.json

bun run tools/kanban-cli/cli.ts config validate
bun run tools/kanban-cli/cli.ts list
```

Skills: `tools/agent-skills/jarvis-github-kanban/SKILL.md` y `jarvis-github-agentuse/SKILL.md`.
