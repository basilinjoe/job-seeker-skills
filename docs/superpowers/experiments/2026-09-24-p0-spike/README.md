# P0 spike: the facts the graph rewrite's P1 spec depends on

**Status:** done 2026-09-24. Throwaway. Roadmap: `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md`.
**Run:** `pip install "pyoxigraph>=0.5.11,<0.6"`, then `python spike.py --wheels` and `python tighten.py`.

## pyoxigraph (spike.py) — Windows 11 / Python 3.13 and Linux / Python 3.10, identical results

| Question | Answer | Consequence for P1 |
|---|---|---|
| Version and wheels | 0.5.11; an `abi3` wheel (cp38+) for Windows x64/ARM64, Linux x64/aarch64 (glibc and musl), macOS x64/arm64, plus per-version wheels 3.10-3.14 | pin `pyoxigraph>=0.5.11,<0.6`; no platform gap (unlike LadybugDB 0.19-0.20.4) |
| Parse errors | `SyntaxError: Parser error at line 4 column 27: …` | hand-edit errors can name file:line:column directly |
| Built-in serializer | output order depends on insertion order; multi-line prose written as one `"…\n…"` line; no prefixes, no comments | **own canonical writer required** (as the roadmap assumed); pyoxigraph only parses and queries |
| Our `"""` escaping (`"""` inside, trailing `"`, `\`) | round-trips through the parser | the writer's escaping rule is settled |
| Named graphs | one graph per file; `use_default_graph_as_union=True` queries across them; `GRAPH ?g` names the file | errors name the file; derived triples go in their own graph |
| Import / load / validate / materialise | 11-12 ms import; ~10,350 quads (a 400-project KB + 100 applications) load in 61-67 ms, two validation queries 3-4 ms, closure insert < 1 ms | every command can load and validate the whole workspace |

## Is Turtle too costly to read? (tighten.py, sample-kb.md vs sample-kb.ttl)

The same career — every section of the kb: 2 format — written both ways. Tokens are bytes/4.

| Layout | Tokens | vs kb.md |
|---|---|---|
| kb.md (today) | 1,131 | 1.00 |
| kb.ttl as first drafted | 1,980 | 1.75 — over the 1.6 exit threshold |
| + short section banners (`# == Projects`) | 1,469 | 1.30 |
| + no file header comment | 1,422 | 1.26 |
| + no `a j:Class` (the id prefix names the class; the loader derives the type) | **1,324** | **1.17** |

Only the 22 derived `rdf:type` triples differ; no content is lost. **P1 layout decision:** short banners, and
the writer never emits `a j:Class` — `prj_` is a Project, `ach_` an Achievement, and so on, derived on load
into `j:derived`. The long box-drawing banners alone cost ~500 tokens.

Two notes on what the ratio means:
- Agents do not read the whole file any more: `jsk kb show <ids>` and `jsk match` return the part that matters,
  so the ratio is mostly the cost of a person reading their career end to end.
- `sample-kb.tight.ttl` is what that reading looks like. **Before P1, look at it and say whether it is a file
  you would read and correct.** The graph simulation cannot answer that; only the person can.

## Not done here

- **A real knowledge base** was not migrated: none exists in this repo (the eval workspace holds only the old
  bundle format). Run `tighten.py` against a real `user-knowledgebase.md` — hand-converted, or via P4's
  migrator — before P1's layout is frozen.
