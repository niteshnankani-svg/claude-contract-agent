# web — incident mission control

Interactive, animated frontend for **claude-contract-agent**. It replays the
Python LangGraph agent's exact incident run: the 9-node graph lights up as the
agent progresses, the hypothesis ledger updates confidence live, you approve or
reject at the human-review gate, and recovery is verified on the telemetry
panel.

**Live:** https://claude-contract-agent.vercel.app

## Stack

- **Vite** + **React 18** + **TypeScript**
- **Tailwind CSS** (custom dark "mission-control" theme)
- **Framer Motion** (node/edge animation, panel transitions, the approval modal)
- Fonts: Space Grotesk (display), Inter (body), JetBrains Mono (console)

## Develop

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc + vite build -> dist/
npm run preview
```

## Deploy (Vercel)

The project is linked to Vercel; `vercel.json` sets the Vite build. Deploy with:

```bash
cd web
vercel --prod
```

Or connect the GitHub repo in the Vercel dashboard with **Root Directory =
`web`**.

## How it maps to the agent

`src/run.ts` encodes the same node sequence, hypotheses, metrics and outcomes
the Python CLI prints — the UI visualises the agent, it does not re-implement
it. Swap that data for a live API (e.g. streaming the LangGraph run) to drive
the same UI from a real backend.
