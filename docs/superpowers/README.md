# Design history

Not documentation of how to use jsk - that is `README.md` and `docs/`. These are the records the
graph record was designed from, kept because the code and `docs/WHY.md` cite them:

- `plans/2026-09-24-graph-rewrite-roadmap.md` - the migration to `career/kb.ttl`, phase by phase
  (P0-P8), with the rulings each phase made where the plan was silent.
- `specs/2026-09-24-graph-core-design.md` - the record format; `src/jsk/graph/ontology.py` is its
  single definition in code.
- `specs/2026-09-24-graph-match-design.md` - how a posting is matched through the vocabulary.
- `experiments/2026-09-24-graph-simulation/` - the twelve scenarios that made the case for a graph.
- `experiments/2026-09-24-p0-spike/` - pyoxigraph measured before it became a dependency.

Earlier specs and the per-phase plans were removed once built; `git log -- docs/superpowers` has
them.
