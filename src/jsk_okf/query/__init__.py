"""Asking a bundle a question.

The third cluster in this package, beside `authoring/` which changes a bundle and
`urs/` which renders one. Everything here reads and nothing writes.

`okf` could compile a bundle, validate it, render it and write to it, and could not
answer a question about it. So every question a session actually asks - "have I
already recorded this project?", "what bullet ids can this view include?", "which
projects carry event-driven-architecture?", "what is still inferred?" - was answered
by a full compile, by reading every concept, or by raw grep. The first two cost about
a second and thirty kilobytes each; the third cannot see that a hit landed in an
`inferred` bullet, or in a *frozen* archived posting nobody is permitted to edit.

Two rules hold across every command here, and both are load-bearing.

**Nothing here compiles.** `okf_compile.load()` walks the tree, parses every concept,
resolves relations and raises on a bundle it does not like. Ids are derived instead, by
`ids.py`, out of the same helpers the compile derives them with.

Be exact about what that buys, because the obvious answer is only half right and the
wrong half is the one people quote. **A compile is one walk** - `load()` is `concepts()`
plus dict-building, and the building is nearly free - so a question that has to read
every concept cannot get materially under a compile, and one that claimed to would be
reading fewer files than the compile reads. `okf list unconfirmed` is a walk, which is
the floor, and that is fine.

What the layer actually buys is two other things:

* **A targeted question is dramatically cheaper.** `okf show <id>` is ~11ms against a
  549ms compile on a 235-file bundle, because `ids.candidates()` and `must_contain` skip
  the YAML parse - five sixths of a walk - for every file that cannot hold the answer.
* **An answer at all, on a bundle that will not compile.** A dangling `role:` or a date
  that does not parse makes `load()` refuse the whole bundle. That is the state a bundle
  is in while somebody is working on it, which is when the question gets asked. And a
  record cannot answer some of these at any price: it holds no claim-level provenance to
  audit, no notion of a metric nothing cites.

**Nothing here exits 1.** The exit codes are uniform across this CLI - 0 passed, 1 a
real finding, 2 called wrong - and a query has no findings. It reports what is there;
whether that is a *problem* is a gate's judgement, and this layer deliberately makes
none. An `inferred` claim is a legitimate state, not an error, and a search that
matched nothing has still answered the question it was asked. `okf pipeline` exits 1
and is not a counter-example: it derives urgency against a date, which is a judgement
it was built to make. The temptation is grep's convention, where 1 means no match -
resist it, because then `okf list unconfirmed` finding an inferred bullet reads as a
failed check and someone starts clearing it.
"""
