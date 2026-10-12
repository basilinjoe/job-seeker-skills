# Tailor time - the measurements behind the plan

`docs/superpowers/plans/2026-09-29-tailor-time.md` was planned from these.

## session_profile.py

One session, turn by turn: each tool call's duration, result size (characters) and the context
it ran at, every text the model showed, and the token totals - for the session and each of its
subagents.

```bash
python session_profile.py ~/.claude/projects/C--Projects-basilin-joe-resume/<session-uuid>
```

A turn re-reads the whole context, so cost ≈ turns × context: read `ctx=` down the column, and
count the turns after the person's last answer.

## heading_proto.py

Ruling 1 (bare headings, one item per line under a section) against the parser in `src/`, over
every `applications/*/posting.md` of a workspace: qual/resp/other per advert, today / TC-1's
rule / this plan's. Name part of an application to list its lines.

```bash
python heading_proto.py C:/Projects/basilin-joe-resume arrow schneider
```

Once Task 1 lands, `today` equals `new`: the column is the check that it landed as prototyped.

## The baseline (2026-09-29)

| | Arrow (`.docx`) | Schneider (URL, Playwright) |
|---|---|---|
| Wall time | 11.9 min | 11.7 min |
| of which the person answering | 1.4 min | 3.0 min |
| Main-thread turns | 38 | 39 |
| Main-thread cache reads / output | 3.51 M / 21.4k | 3.17 M / 19.9k |
| Main-thread context, first turn → last | 47k → 126k | 48k → 117k |
| Analyst: minutes, turns, cache reads | 2.0, 15, 0.34 M | 2.1, 14, 0.31 M |
| Author: minutes, turns, cache reads | 2.0, 15, 0.65 M | 1.1, 8, 0.27 M |

Sessions: Arrow `9f68b941-321a-4e36-9a36-cf4c558921a5`, Schneider
`f2c2ea73-54c1-419b-8fd7-566523b61581`.
