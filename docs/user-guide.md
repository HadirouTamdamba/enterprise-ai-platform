# User Guide

## Signing in
Open the platform URL, sign in with the credentials from your administrator. Toggle dark
mode from the sidebar.

## Asking questions about your documents (RAG Studio)
1. **RAG Studio → Create** a knowledge base (or pick an existing one).
2. **Upload documents** — PDF, Word, PowerPoint, Excel, Markdown, CSV, HTML, images.
   The status badge moves `uploaded → processing → indexed` (a few seconds to minutes).
3. Ask a question. Answers cite their sources `[1] filename — p.X` and show a
   **groundedness** badge: green (≥70%) means well-supported by your documents; treat
   amber answers with care and check the citations.
4. Re-uploading a file with the same name creates a new version; old content stops being used.

## Testing prompts (Playground)
Pick a provider/model (or keep the platform default), set temperature, write a system +
user prompt, and run. Every run shows tokens, cost and latency — compare models before
committing a prompt to the registry.

## Using agents
Choose an agent for the job — **planner** (break work down), **research**, **compliance**
(regulatory check), **security** (code review), **reporting** (executive summary),
**critic** (stress-test a plan) and more. Give it a task; expand **Execution trace** to see
its reasoning steps and tool calls. Runs are capped by iteration and cost budgets.

## Reading the dashboards
**Overview** shows 30-day requests, tokens, cost and latency plus the AI inventory.
**Monitoring** breaks cost down by model. If something looks wrong, note the time and
contact your administrator — every request has a traceable ID.

## Good to know
- Malicious-looking prompts (injection attempts) are blocked automatically.
- Personal data (emails, IBANs, phone numbers) is redacted from prompts and answers.
- Your feedback (👍/👎 via API/integrations) feeds the evaluation datasets that improve answers.
