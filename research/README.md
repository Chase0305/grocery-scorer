# Food health research (the research agent's workspace)

A scheduled Claude task ("Grocery health research", once a day) works through `QUEUE.md`
one topic per run: what the best evidence says about an additive, sweetener, sugar,
flavouring or oil, and whether the scorer treats it right. It writes:

- `topics/<topic>.md` - the findings, with sources and an evidence grade
- a line in `LOG.md` - what it looked at and what it recommends

**It never changes the scores.** It only reads the scorer (`scripts/scorer.py`,
`scripts/flagged_ingredients.json`) and the catalog, and proposes changes. The user decides;
a proposal is applied by hand and checked with `scripts/whatif_scoring.py` first.

Evidence grades used in every topic:
- **Strong** - consistent systematic reviews / meta-analyses of human studies, or a firm
  regulatory finding (ban, ADI exceeded at normal intake)
- **Moderate** - several human cohort studies pointing the same way, plausible mechanism
- **Weak** - single studies, animal-only, or high-dose-only evidence
- **Contested** - good studies disagree; say who disagrees and why

The agent runs in the cloud (a claude.ai routine), so it works with the Mac off. Its full
instructions are in `AGENT_PROMPT.md`; it commits to the `claude/research` branch, which
gets merged into the main branch by hand.

To add a topic, add a line to `QUEUE.md`. To stop the agent, switch the routine off in the
Claude app (Code tab > Routines) or at claude.ai/code/routines.
