---
name: desearch
version: 1.0.0
description: Launch parallel deep web research on any topic with multiple angles and synthesized report
user-invocable: true
---

# Deep Research Protocol

Research the topic: "$ARGUMENTS"

## Step 0 — Ensure Agents Are Available

Check that `desearch-researcher` and `desearch-synthesizer` agents are installed:
1. Check `~/.config/opencode/agents/desearch-researcher.md` exists
2. Check `~/.config/opencode/agents/desearch-synthesizer.md` exists

If either is missing, check if `~/claude-config/` exists:
- **If yes**: Run `cp ~/claude-config/agents/desearch-*.md ~/.config/opencode/agents/`
- **If no**: Clone it: `git clone git@github.com:rus-lan/claude-config.git ~/claude-config` (fallback to HTTPS if SSH fails), then copy agents.

## Step 1 — Create Output Directory

Create a topic-specific subdirectory inside `.research/` in the project root. Derive the directory name from the research topic using kebab-case (e.g., `.research/react-hooks/`, `.research/telegram-mini-apps/`). If the directory already exists, reuse it — this allows re-running research on the same topic to update results.

## Step 2 — Decompose the Research

Analyze the topic and decompose it into 3-5 distinct research angles. Choose from these standard angles, adapting to the topic:

1. **Overview & Official Sources** — What is this? Official documentation, announcements, primary sources.
2. **Community & Practical Experience** — Tutorials, blog posts, real-world usage reports, Stack Overflow discussions.
3. **Limitations, Criticism & Known Issues** — What doesn't work? What are people complaining about? Edge cases, bugs, footguns.
4. **Alternatives & Comparison** — What else exists? How do alternatives compare? Migration paths.
5. **Latest Developments & Roadmap** — Recent releases, upcoming features, trends, deprecations.

For narrower topics, use 3 angles. For broad topics, use 5.

## Step 3 — Launch Parallel Researchers

Spawn one `desearch-researcher` agent per research angle, ALL IN PARALLEL (in a single message with multiple Agent tool calls). Each agent receives:

- The specific research angle and what to focus on
- The output file path: `.research/<topic>/01-overview.md`, `.research/<topic>/02-community.md`, etc.
- Context from the original topic to keep them focused

Run all agents with `run_in_background: true` to maximize parallelism.

Wait for ALL agents to complete before proceeding.

## Step 4 — Synthesize

After all researchers complete, spawn the `desearch-synthesizer` agent with:

- The path to the `.research/<topic>/` directory
- The original research topic/question
- Instruction to write the final report to `.research/<topic>/REPORT.md`

## Step 5 — Present Results

After the synthesizer completes:

1. Read `.research/<topic>/REPORT.md`
2. Present the Executive Summary and Recommendations to the user directly
3. Note the full report path for detailed reading

## Rules

- NEVER skip the parallel research step. Always spawn at least 3 researchers.
- NEVER let researchers make up information. They must cite real URLs.
- If a researcher fails or returns low-quality results, note this in the synthesis — do NOT retry silently.
- The final report must answer the user's original question directly in the Executive Summary.
- All files stay in `.research/` for the user to review, share, or archive.
