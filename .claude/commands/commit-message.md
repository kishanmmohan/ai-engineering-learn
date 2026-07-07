---
description: Analyze the current diff and produce a structured commit message
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*)
---

## Context

- Staged diff: !`git diff --staged`
- Unstaged diff: !`git diff`
- Status: !`git status --short`
- Recent commits (for style): !`git log --oneline -10`

## Task

Analyze the diff above and produce a **structured commit message** following the Conventional Commits spec.

If there is a staged diff, base the message on the staged changes only. Otherwise use the unstaged changes.

Output the message in a fenced code block, using this structure:

```
<type>(<optional scope>): <short imperative summary, ≤50 chars>

<body: what changed and why, wrapped at 72 chars. One blank line
between paragraphs. Use bullet points for multiple distinct changes.>

<optional footer: BREAKING CHANGE:, refs, etc.>
```

Rules:
- `type` is one of: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Summary line: imperative mood ("add", not "added"), no trailing period.
- Match the style of the recent commits shown above where reasonable.
- Omit the body if the change is trivial and the summary is self-explanatory.
- Do NOT commit — only output the proposed message. If `$ARGUMENTS` contains `commit`, then also run `git commit` with the generated message.
