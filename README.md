# NewHire.work

> **Hire new employees under 10 seconds.**

Paste a job description into your AI chat. A virtual employee
materializes — name, avatar, role title — with their core skills
branching out as a tree. Click any skill to break it down into
concrete tasks. Click any task to launch an agent that runs it.

Built on [Reboot](https://reboot.dev) — the backend is Python,
state is durable across restarts, and the React skill-tree canvas
is mounted as an MCP UI inside Claude / ChatGPT / any MCP host.

---

## Stack

- **Backend** — Reboot (Python). Two state types (`User`,
  `Employee`) with `Reader` / `Writer` / `Transaction` methods.
- **AI** — Anthropic SDK (`claude-sonnet-4-5`) for skill
  generation, decomposition, and task execution. Hand-tuned mock
  fallbacks if no API key is set, so the demo always runs.
- **Frontend** — React + `@xyflow/react` (React Flow) +
  `dagre` for auto-layout + Framer Motion for entry animations
  + DiceBear for avatars + ReactMarkdown for agent output.
- **Token router** — MCP. Every method is a tool the AI can call.

## Tool surface (what the AI sees)

| Tool                     | Type        | Purpose                                                 |
| ------------------------ | ----------- | ------------------------------------------------------- |
| `User.hire_employee`     | Transaction | Generate name, role, and 3-6 skills from a job desc.    |
| `User.list_my_employees` | Reader      | List the user's existing employees.                     |
| `Employee.get`           | Reader      | Read full profile (name, role, avatar, skills + tasks). |
| `Employee.expand_skill`  | Writer      | Decompose a skill into 2-4 concrete tasks.              |
| `Employee.run_task`      | Writer      | Execute a task with a scope of work; returns markdown.  |
| `Employee.show_profile`  | UI          | Open the skill-tree canvas inline in the AI chat.       |

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python package manager)
- Node 20+ and `npm`
- *(Optional)* `ANTHROPIC_API_KEY` — without it, mocks are used.

## Run it (3 terminals, from this directory)

```bash
# 1) install deps + generate code (first time)
uv sync
uv run rbt generate
cd web && npm install && cd ..
uv run rbt generate    # second pass — needs node_modules

# Terminal 1 — backend
export ANTHROPIC_API_KEY=sk-ant-...   # optional
uv run rbt dev run

# Terminal 2 — frontend HMR
cd web && npm run dev

# Terminal 3 — talk to it via the MCP inspector
npx @mcpjam/inspector@2.4.0 --config mcp_servers.json --server newhire
```

Then in the inspector, try:

> *"Hire a Senior Game Designer who specializes in roguelite
> progression systems and combat feel. Then show me their profile."*

## Project layout

```
api/newhire/v1/employee.py        — API definition (state + tools)
backend/src/main.py               — entrypoint, registers servicers
backend/src/servicers/employee.py — User + Employee servicer impls
web/ui/profile/App.tsx            — skill-tree canvas (React Flow)
web/ui/profile/App.module.css     — dark-theme styling
.rbtrc                            — Reboot run/generate config
mcp_servers.json                  — MCP host config
```

## License

MIT (or whatever you want — this is a hackathon prototype).
