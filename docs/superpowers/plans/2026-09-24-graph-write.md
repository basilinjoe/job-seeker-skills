# Graph Write Path (P3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `jsk kb` - the one way an agent changes `career/kb.ttl` (`apply` a TriG changeset, `confirm` with the person's answer, `adopt` a hand edit, `fmt`), and the ways it reads the record by id (`show`, `view`, `query`, `check`) - with `career/log.ttl` kept in step by revision and hash, so a torn write or a hand edit is detected on the next load.

**Architecture:** Four new modules under `src/jsk/graph/`: `record.py` (kb.ttl and log.ttl in step: state, staged writes, the Windows-lock retry, the shadow copy), `changeset.py` (reads TriG, refuses what can be refused without the career), `edit.py` (merges a changeset into kb.ttl: the refusals that need the record, provenance, questions, bullet ids, metric versions) and `kbcli.py` (the `jsk kb` verbs), with `named.py` (the named queries) and `view.py` (the Markdown view) for the read verbs. The loader gains a hash per file and an in-memory override, so a write validates the record it is about to write before writing it. Three tier-2 rules report the record's state: `log-sync` (FAIL), `hand-edited` (WARN) and `answer-placeholder` (WARN).

**Tech Stack:** Python >= 3.10, pyoxigraph 0.5 (parse and query only; the canonical writer is P1's `writer.py`), unittest run by pytest.

**Spec:** `docs/superpowers/plans/2026-09-24-graph-rewrite-roadmap.md` - the P3 paragraph and the "Write path" section. There is no separate P3 spec: the roadmap is detailed enough, per the user ("i have created a claude plan for entire migration and reviewed it"). Where the roadmap leaves a decision open, it is settled in **Rulings** below; read those as the spec's missing lines. Also read `docs/superpowers/specs/2026-09-24-graph-core-design.md` (P1: the ontology, the writer, the rules) - Task 7 amends four of its lines.

## Rulings (decisions the roadmap leaves open)

Each is `what - why - what it costs if wrong`.

1. **Changeset header** is `op:changeset op:base 7 ; op:summary "…" .`, in the default graph; P1's spec had `op:base op:revision "rN"`. - An integer matches `j:revision`, and the summary needs somewhere to live. - A spec line changes (Task 7 amends it); nothing else reads a changeset.
2. **`op:delete`** removes exact triples, each of which must exist; `k:x a op:Entry` removes the whole entry, refused while anything points at it (retire instead). - A delete that matches nothing is a typo, and silence would hide it. - None found.
3. **`op:base` conflicts are per entry**, not per (entry, predicate): the log records ids. - Two edits of one entry's different fields conflict and need a re-read. Cheap next to a silent overwrite.
4. **Blank nodes** are allowed only as the subject of a new bullet in `op:add` (it must name `j:project`); every other new entry names its own id. The roadmap both refuses blank nodes and has apply mint bullet ids "if absent", and in Turtle an absent id is a blank node. - An agent chooses ids for projects and metrics; `id-form` validates them.
5. **A minted bullet id** is `ach_<project stem>_<first three content words>`, then four; stop words and digits are dropped; an id the record or its log ever used is never reused; the changeset's own ids count as taken. **A new bullet with a live bullet's exact text, under the same project, is that bullet**, so re-running an apply mints nothing twice. - Two bullets with identical text under one project cannot both be added as blank nodes; name one.
6. **Metric versions.** The roadmap says "setting a value creates a version and closes the old; versions linked from any application are immutable". Ruling: `op:set` of `j:value`, `j:baseline` or `j:kind` on a version an application *sent* (`j:carriedVersion`) mints the next version (`validFrom` today) and closes the sent one (`validUntil` today: closing is the one change a sent version takes). On a version never sent, it corrects in place. Adding a new version closes the current one, at the new one's `validFrom` or today. Any other change to a sent version is refused. - An unsent value that really changed over time is recorded as a correction unless the changeset adds `v2` itself; the old value then survives only in git.
7. **Provenance.** Changing a predicate the ontology marks `claim=True` drops the entry to `j:inferred`, unless the changeset states a provenance (anything but confirmed). A new claims-bearing entry without one is `j:inferred`. Every entry the change leaves inferred or needs-verification gets a `k:q_<id>` question, unless one is open about it - so `inferred-unasked` stays quiet. - Extra questions on a large braindump, one per new entry; each names what to confirm.
8. **`kb.ttl`'s header gains `j:revision`** (optional, so a hand-written file with no log still loads). Same revision and hash as the log's last entry: clean. Same revision, another hash: `hand-edited` (WARN - it does not block `jsk match`; it blocks writes). kb.ttl one ahead: torn. Anything else: out of sync. Both are `log-sync` (FAIL). **No `.bak`:** the shadow `.jsk/kb.last.ttl` - written last, git-ignored by its own folder - is the previous revision, which is what `adopt` diffs against. - With the shadow deleted, `adopt` lists every confirmed entry instead of what changed.
9. **Writes need a clean record.** An unlogged `kb.ttl` (no log) is adopted first; a hand edit is adopted first; a torn write is adopted. - `jsk new` and `jsk migrate` (P4, P7) must write r1; recorded there.
10. **`apply` writes `career/kb.ttl` only.** Postings are the analyst's (P6), events and freezes P5's. - A changeset naming a posting is refused with the file it belongs in.
11. **What blocks a write:** any FAIL in the career or the vocabulary, a syntax error anywhere, or a FAIL the change would add. An old application's existing FAIL does not. - Same gating as P2's `jsk match`.
12. **`kb query` ships `open`, `unconfirmed`, `holds <concept>` and `stale`.** The roadmap's `experience`, `inconsistent`, `demand` and `pipeline` arrive with the phases whose data they read (P5). - An agent needing one before P5 reads `kb view`.
13. **`confirm` refuses a placeholder answer** ("yes", "ok", "confirmed", "<…>") as well as `kb check` flagging one (`answer-placeholder`), which catches those that reach the log by hand. - A terse real answer ("No.") is refused; say more.
14. **Hand comments:** `adopt` and `fmt` refuse a file holding any, listing them, unless `--drop-comments`. `fmt` of kb.ttl is logged (`by fmt`, day unchanged); of a posting or application, unlogged; `log.ttl` never. - None found.
15. **The log may name concepts** (`j:touched`/`j:minted` accept `c:` as well as `k:`): a changeset that adds `c:payments` is a change to the career. Found by the braindump test (Task 5), whose own log entry failed its shape.
16. **No `--today` on writes.** Dates are the machine's: a backdated write would falsify the log. `jsk match --today` stays, for reproducible scoring. - Tests compare against `datetime.date.today()`.
17. **SKILL.md gains one row, `jsk kb <verb>`, paid for by trimming** the intro sentence and the `jsk index` row. Resident total 5,999 of 6,000 (was 5,997); no ceiling moves. - One token of headroom until P6 rewrites SKILL.md.

## Global Constraints

- Python >= 3.10 (`requires-python`), pyoxigraph `>=0.5.11,<0.6` - the only runtime dependency the graph adds. Import pyoxigraph inside functions, never at module top (P1: a command that never reads the graph never pays for it).
- Record files are LF, UTF-8, no BOM on write; `io.normalise` on read. Staged writes use `newline="\n"`.
- `career/kb.ttl` is only ever written through `record.commit`, after `record.prepare`, after the would-be workspace validated.
- Nothing is sent over the network. The user's email address never goes into a fixture, a test or a log.
- `python -m pytest tests -q -n auto` and `python -m ruff check src tests` green at the end of every task. `tests/test_budget.py`: SKILL.md < 2,400 tokens; SKILL.md + mode-tailor.md + mode-ship.md < 6,000. `tests/test_graph_budget.py` (run alone: `python -m pytest tests/test_graph_budget.py -q -s`) under 1,200 ms; it measured 298 ms after these changes, 288 before.
- Write any file holding a backslash with the Edit or Write tool, never a Bash heredoc: heredocs silently turn `\n` into a newline and eat line-continuation backslashes (it happened four times building this plan).
- Findings print through `validate_urs.show`; every refusal says what is wrong and a `fix:`.

## Review Focus

The input classes the roadmap implies but no line of it tests, most likely first. Each has its test in the task named.

1. **An agent re-runs an apply it thinks failed** → nothing is minted twice: a new bullet with a live bullet's text under the same project is that bullet. Test `test_applying_the_same_changeset_twice_changes_nothing_the_second_time` (Task 5), code `same_bullet` (Task 4).
2. **A changeset saved by a Windows editor** (BOM, CRLF) → reads exactly as the LF one. `test_a_changeset_saved_by_a_windows_editor_reads_the_same` (Task 3).
3. **An old application's posting stops quoting cleanly** → career writes still work; only a FAIL the change adds, or one in the career, blocks. `test_an_old_application_s_fault_does_not_block_the_career` (Task 5).
4. **A changeset adds a label another concept has** → a `label-clash` WARN, and the apply proceeds (matching will ask). `test_a_label_that_clashes_is_a_warning_not_a_refusal` (Task 5).
5. **git restores kb.ttl and log.ttl together to an older commit** → clean, not a hand edit. `test_both_files_restored_together_are_clean` (Task 5).

---

### Task 1: The record's state - a revision and a hash, and the rules that read them

**Files:**
- Create: `src/jsk/graph/record.py` (the state half; Task 2 adds the writing half)
- Modify: `src/jsk/graph/ontology.py` (KB header), `src/jsk/graph/io.py` (hash and text per file), `src/jsk/graph/store.py` (`texts=` override), `src/jsk/graph/rules.py` (three rules)
- Modify: `tests/graph_fixtures/career/kb.ttl`, `tests/graph_fixtures/career/log.ttl` (a real revision and hash)
- Test: `tests/test_graph_rules.py`, `tests/test_graph_shapes.py`

**Interfaces:**
- Consumes: P1's `store.load`, `Store.parsed[file]` (`io.Parsed`), `rules.Rule(id, severity, sparql, detail, fix, post)`.
- Produces: `io.Parsed.sha256: str` and `io.Parsed.text: str` (normalised); `io.sha256(text) -> str`; `store.load(root, vocabulary=..., files=None, texts=None)` where `texts` is `{workspace file name: text}` used instead of disk (files not on disk are added); `record.KB = "career/kb.ttl"`, `record.LOG = "career/log.ttl"`, `record.SHADOW`; `record.State(kind, kb_revision, log_revision, logged_sha, detail)` with kind one of `clean | unlogged | hand-edited | torn | out-of-sync | unreadable | missing`; `record.state(store) -> State`; `record.header_revision(quads) -> int|None`; `record.last_entry(quads) -> (int|None, str|None)`; `rules.PLACEHOLDER` (compiled regex, `fullmatch` = says nothing).

- [ ] **Step 1: Write the failing tests**

In `tests/test_graph_shapes.py`, the duplicate-line test now meets a legitimate `hand-edited` WARN - the copied line is a hand edit - so it filters that rule out:

```diff
--- a/tests/test_graph_shapes.py
+++ b/tests/test_graph_shapes.py
@@ -143,7 +143,8 @@ class Findings(unittest.TestCase):
     def test_a_line_copied_twice_is_one_fact_not_two(self):
         line = 'k:met_team j:subject "engineers led" ; j:unit "engineers" .'
         s, _ = mutated((KB, line, line + "\n" + line, "", ""))
-        self.assertEqual([f.text() for f in s.findings], [])
+        # The copy is a hand edit, and reported as one; it is not a second fact.
+        self.assertEqual([f.text() for f in s.findings if f.rule != "hand-edited"], [])
 
     def test_an_impossible_date_is_refused(self):
         s, _ = mutated((KB, 'j:answered "2026-08-14"', 'j:answered "2026-02-30"', "", ""))
```

In `tests/test_graph_rules.py`, register a mutation for each new rule, mark the two WARNs, and add the state tests:

```diff
--- a/tests/test_graph_rules.py
+++ b/tests/test_graph_rules.py
@@ -9,6 +9,8 @@ from test_graph_shapes import APPLICATION, KB, POSTING, assert_fires, mutated
 
 from jsk.graph import rules
 
+LOG = "career/log.ttl"
+
 # rule: (file, old text, new text, focus id, the fix contains). old=None appends new.
 MUTATIONS = {
     "dangling": (KB, "j:cites k:met_team ;", "j:cites k:met_teem ;",
@@ -73,10 +75,15 @@ MUTATIONS = {
     "necessity-wording": (POSTING, 'j:asked "event-driven" ; j:necessity j:preferred ;',
                           'j:asked "event-driven" ; j:necessity j:required ;',
                           "k:req_acme_platform_engineer_eda", "check the necessity"),
+    "log-sync": (KB, "j:revision 2 .", "j:revision 5 .", "k:kb", "restore the file"),
+    "hand-edited": (KB, 'j:size "1001-5000"', 'j:size "1001-10000"', "k:kb", "jsk kb adopt"),
+    "answer-placeholder": (LOG, 'j:answer "Six throughout; two joined in the second month '
+                                'and two left."', 'j:answer "yes"', "k:rev_2", "in their words"),
 }
 
 WARNS = {"version-gap", "headline-cited", "label-clash", "inferred-unasked",
-         "retired-referenced", "event-before-submit", "necessity-wording"}
+         "retired-referenced", "event-before-submit", "necessity-wording", "hand-edited",
+         "answer-placeholder"}
 
 
 class EveryRuleFires(unittest.TestCase):
@@ -150,6 +157,27 @@ class Findings(unittest.TestCase):
         self.assertTrue([f for f in s.findings if f.rule == "quote-verbatim"
                          and f.focus == "k:req_acme_platform_engineer_eda"])
 
+    def test_a_write_that_reached_only_kb_ttl_is_named_torn(self):
+        s, _ = mutated((KB, "j:revision 2 .", "j:revision 3 .", "", ""))
+        [f] = [f for f in s.findings if f.rule == "log-sync"]
+        self.assertIn("reached kb.ttl and not log.ttl", f.detail)
+        self.assertIn("jsk kb adopt", f.fix)
+        self.assertEqual([f for f in s.findings if f.rule == "hand-edited"], [])
+
+    def test_a_revision_with_no_log_entry_is_out_of_step(self):
+        s, _ = mutated((LOG, "k:rev_2 ", "k:rev_9 ", "", ""))
+        s2, _ = mutated((LOG, "j:revision 2 ;", "j:revision 4 ;", "", ""))
+        # rev_9 still says revision 2: the entry is found by its revision, not its id.
+        self.assertEqual([f.rule for f in s.findings if f.rule == "log-sync"], [])
+        self.assertIn("one of them was restored",
+                      [f for f in s2.findings if f.rule == "log-sync"][0].detail)
+
+    def test_a_confirm_with_no_answer_is_flagged(self):
+        s, _ = mutated((LOG, '    j:answer "Six throughout; two joined in the second month and '
+                             'two left." ;\n', "", "", ""))
+        [f] = [f for f in s.findings if f.rule == "answer-placeholder"]
+        self.assertEqual((f.focus, f.detail), ("k:rev_2", "a confirm with no answer"))
+
     def test_the_log_may_name_ids_that_no_longer_exist(self):
         s, _ = mutated(("career/log.ttl", "j:touched k:met_team.v1,", "j:touched k:met_gone.v1,",
                         "", ""))
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_rules.py tests/test_graph_shapes.py -q`
Expected: FAIL - `test_every_rule_has_a_mutation` (three mutations name no rule), `assert old in text` for the `j:revision 2 .` mutations (the fixture has no revision yet), and the torn/out-of-step/no-answer tests.

- [ ] **Step 3: The KB header's revision (ontology.py)**

In `src/jsk/graph/ontology.py`, the `KB` class's one line gains `revision`:

```python
    Class("KB", "=kb", ("kb",), None, (
        (Pred("format", Lit(("integer",), lo=FORMAT, hi=FORMAT), "1", "the format revision"),
         Pred("name", STR, "1", "whose career this is"),
         Pred("updated", DATE, "1", "the day the last change landed"),
         Pred("revision", Lit(("integer",), lo=1), "?", "the log revision it was written at")),
    ), "the file's header"),
```

- [ ] **Step 4: A hash and the text per parsed file (io.py), and the in-memory override (store.py)**

```diff
--- a/src/jsk/graph/io.py
+++ b/src/jsk/graph/io.py
@@ -3,6 +3,7 @@
 pyoxigraph is imported inside the functions that need it, never at module top, so a
 command that never reads the graph never pays for it (11-12 ms, measured in P0).
 """
+import hashlib
 import re
 from dataclasses import dataclass
 
@@ -31,6 +32,8 @@ class Parsed:
     quads: list        # pyoxigraph Quads, all in the default graph
     lines: dict        # subject iri -> the first line it starts, 1-based
     comments: list     # (line, text): hand comments a rewrite would drop
+    sha256: str = ""   # of the normalised text: what log.ttl records for kb.ttl
+    text: str = ""     # the normalised text, for the canonical check and the diff
 
 
 def normalise(text):
@@ -55,7 +58,11 @@ def parse_text(text, file, kind=None):
         raise GraphError(f"{file}:{e.lineno}:{e.offset}: {e.msg}",
                          "fix the syntax there; the rest of the file was not read",
                          file, e.lineno, e.offset) from None
-    return Parsed(file, kind, quads, subject_lines(text), comments(text))
+    return Parsed(file, kind, quads, subject_lines(text), comments(text), sha256(text), text)
+
+
+def sha256(text):
+    return hashlib.sha256(text.encode("utf-8")).hexdigest()
 
 
 def parse(path, root=None):
```

```diff
--- a/src/jsk/graph/store.py
+++ b/src/jsk/graph/store.py
@@ -10,7 +10,7 @@ from dataclasses import dataclass, field
 from urllib.parse import quote
 
 from . import ontology as O
-from .io import GraphError, parse
+from .io import GraphError, parse, parse_text
 
 SHIPPED_VOCABULARY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "data", "vocabulary.ttl")
@@ -95,8 +95,10 @@ def graph_iri(name):
     return "file:" + quote(name, safe="/-._~")
 
 
-def load(root, vocabulary=SHIPPED_VOCABULARY, files=None):
-    """Load, derive, validate and close over a workspace. `files` overrides discovery."""
+def load(root, vocabulary=SHIPPED_VOCABULARY, files=None, texts=None):
+    """Load, derive, validate and close over a workspace. `files` overrides discovery;
+    `texts` ({file name: text}) stands in for what is on disk - how `jsk kb apply`
+    validates the record it is about to write before writing it."""
     import pyoxigraph as ox
 
     from .rules import tier2
@@ -104,11 +106,14 @@ def load(root, vocabulary=SHIPPED_VOCABULARY, files=None):
 
     store = Store(os.path.abspath(root), ox=ox.Store())
     paths = files if files is not None else workspace_files(root, vocabulary)
+    texts = texts or {}
+    names = {file_name(p, store.root) for p in paths}
+    paths = list(paths) + [os.path.join(store.root, n) for n in sorted(texts) if n not in names]
     derived = ox.NamedNode(O.DERIVED)
     for path in paths:
         name = file_name(path, store.root)
         try:
-            parsed = parse(path)
+            parsed = parse_text(texts[name], name) if name in texts else parse(path)
         except GraphError as e:
             store.findings.append(Finding("syntax", "FAIL", name, e.line or 0, "",
                                           str(e).split(": ", 1)[-1], e.fix))
```

- [ ] **Step 5: record.py, the state half**

```python
"""career/kb.ttl and career/log.ttl kept in step: the revision and hash they share.

Every command that writes the career - apply, confirm, adopt, fmt - writes kb.ttl, then
log.ttl, then a copy of what it wrote in .jsk/. kb.ttl's header carries the revision it
was written at; log.ttl's last entry carries that revision and kb.ttl's hash. So on any
later load:

- same revision, same hash: clean;
- same revision, another hash: somebody edited kb.ttl by hand - legal, and reported, so
  `jsk kb adopt` can log it and list what it raised;
- kb.ttl one revision ahead: the write was torn - kb.ttl landed and log.ttl did not;
- anything else: one of the two files was restored on its own.

Two files cannot be replaced atomically together. This does not prevent a torn write; it
makes one impossible to miss. Detection, not prevention - the same is true of a hand
edit, and both are said plainly where they are reported.
"""
import os
from dataclasses import dataclass

from . import ontology as O

KB = "career/kb.ttl"
LOG = "career/log.ttl"
SHADOW = os.path.join(".jsk", "kb.last.ttl")     # what the last logged write wrote


@dataclass(frozen=True)
class State:
    kind: str              # clean | unlogged | hand-edited | torn | out-of-sync | unreadable | missing
    kb_revision: int = None
    log_revision: int = None
    logged_sha: str = None
    detail: str = ""


def header_revision(quads):
    for q in quads:
        if q.subject.value == O.K + "kb" and q.predicate.value == O.J + "revision":
            return int(q.object.value)
    return None


def last_entry(quads):
    """(revision, kbSha256) of the log's newest entry, or (None, None)."""
    entries = {}
    for q in quads:
        if O.class_of(q.subject.value) == "LogEntry":
            entries.setdefault(q.subject.value, {})[q.predicate.value[len(O.J):]] = q.object.value
    best = max((e for e in entries.values() if "revision" in e),
               key=lambda e: int(e["revision"]), default=None)
    return (int(best["revision"]), best.get("kbSha256")) if best else (None, None)


def state(store):
    """Where kb.ttl and log.ttl stand with each other."""
    on_disk = {f: os.path.isfile(os.path.join(store.root, f)) for f in (KB, LOG)}
    if KB not in store.parsed:
        return State("unreadable" if on_disk[KB] else "missing")
    if LOG not in store.parsed and on_disk[LOG]:
        return State("unreadable")
    kb_rev = header_revision(store.parsed[KB].quads)
    log_rev, sha = last_entry(store.parsed[LOG].quads) if LOG in store.parsed else (None, None)
    if log_rev is None:
        if kb_rev is None:
            return State("unlogged")
        return State("out-of-sync", kb_rev, None, None,
                     f"kb.ttl says r{kb_rev}, and log.ttl has no entries")
    if kb_rev is None:
        return State("out-of-sync", None, log_rev, sha,
                     f"kb.ttl carries no j:revision, and log.ttl ends at r{log_rev}")
    if kb_rev == log_rev:
        kind = "clean" if sha == store.parsed[KB].sha256 else "hand-edited"
        return State(kind, kb_rev, log_rev, sha,
                     "" if kind == "clean" else f"kb.ttl changed outside `jsk kb` since r{log_rev}")
    if kb_rev == log_rev + 1:
        return State("torn", kb_rev, log_rev, sha,
                     f"kb.ttl is at r{kb_rev} and log.ttl ends at r{log_rev}: the last write "
                     f"reached kb.ttl and not log.ttl")
    return State("out-of-sync", kb_rev, log_rev, sha,
                 f"kb.ttl is at r{kb_rev} and log.ttl ends at r{log_rev}: one of them was "
                 f"restored without the other")
```

- [ ] **Step 6: The three rules (rules.py)**

The helpers go above `concept_class_rules()` (a rule row names them, so they must exist when `RULES` is built); the rows go at the end of `RULES`, before `] + concept_class_rules()`. Write this with the Edit tool: the regex has backslashes.

```diff
--- a/src/jsk/graph/rules.py
+++ b/src/jsk/graph/rules.py
@@ -167,6 +167,35 @@ def worded_otherwise(rows, store):
     return out
 
 
+def out_of_step(kinds):
+    """Rows for the record state kinds a rule reports, at k:kb in kb.ttl."""
+    def post(rows, store):
+        from .record import state
+        st = state(store)
+        return [{"focus": node(O.K + "kb"), "state": st}] if st.kind in kinds else []
+    return post
+
+
+def log_sync_fix(row, store):
+    if row["state"].kind == "torn":
+        return "run `jsk kb adopt`: it logs the write and lists what the write raised"
+    return "restore the file that went back on its own, or run `jsk kb adopt` to log kb.ttl as it is"
+
+
+# What an answer is not: a word that agrees without saying what was agreed to.
+PLACEHOLDER = re.compile(r"\s*(|y|yes|ok|okay|sure|fine|right|correct|true|done|confirm(ed)?|"
+                         r"n/?a|none|tbd|todo|\?+|\.+|-+|<[^>]*>)\s*[.!]?\s*", re.I)
+
+
+def placeholder_answers(rows, store):
+    out = []
+    for r in rows:
+        answer = v(r, "a")
+        if answer is None or PLACEHOLDER.fullmatch(answer):
+            out.append({**r, "said": answer})
+    return out
+
+
 def concept_class_rules():
     """One rule per predicate that restricts the class of the concept it points at."""
     rules, seen = [], set()
@@ -314,6 +343,18 @@ RULES = [
          """SELECT ?focus ?q ?n WHERE { ?focus a j:Requirement ; j:quote ?q ; j:necessity ?n }""",
          lambda r: f"the advert says {r['said']!r} but it is j:{r['need']}",
          "check the necessity against the advert's wording", worded_otherwise),
+    Rule("log-sync", FAIL, None,
+         lambda r: r["state"].detail, log_sync_fix, out_of_step(("torn", "out-of-sync"))),
+    Rule("hand-edited", WARN, None,
+         lambda r: r["state"].detail + " - legal, and not yet logged",
+         "run `jsk kb adopt`: it logs the edit and lists every provenance it raised",
+         out_of_step(("hand-edited",))),
+    Rule("answer-placeholder", WARN,
+         """SELECT ?focus ?a WHERE { ?focus j:by j:confirm OPTIONAL { ?focus j:answer ?a } }""",
+         lambda r: ("a confirm with no answer" if r["said"] is None
+                    else f"a confirm whose answer is {r['said']!r}"),
+         "the answer is the audit trail: record what the person said, in their words",
+         placeholder_answers),
 ] + concept_class_rules()
 
 
```

- [ ] **Step 7: The fixture gets a real revision and hash**

`tests/graph_fixtures/career/kb.ttl`, the header line:

```diff
--- a/tests/graph_fixtures/career/kb.ttl
+++ b/tests/graph_fixtures/career/kb.ttl
@@ -3,7 +3,7 @@
 @prefix c: <tag:jsk,2026:concept/> .
 @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
 
-k:kb j:format 3 ; j:name "Priya Raman" ; j:updated "2026-09-20"^^xsd:date .
+k:kb j:format 3 ; j:name "Priya Raman" ; j:updated "2026-09-20"^^xsd:date ; j:revision 2 .
 
 # == Identity
 
```

Then compute kb.ttl's hash as the loader does (LF-normalised):

Run: `python -c "import hashlib,pathlib;print(hashlib.sha256(pathlib.Path('tests/graph_fixtures/career/kb.ttl').read_bytes().replace(b'\r\n',b'\n')).hexdigest())"`
Expected: `4ae3636cbec680050cd4cfbc7478e1a256fa53e6e66d5a953ef3fdaba1bccc56`

and put it in `rev_2` of `tests/graph_fixtures/career/log.ttl` (rev_1 keeps its placeholder - only the last entry is compared):

```diff
--- a/tests/graph_fixtures/career/log.ttl
+++ b/tests/graph_fixtures/career/log.ttl
@@ -13,4 +13,4 @@ k:rev_2 j:revision 2 ; j:date "2026-09-21"^^xsd:date ; j:by j:confirm ;
     j:summary "Confirmed the team size." ;
     j:touched k:met_team.v1, k:q_team_size ;
     j:answer "Six throughout; two joined in the second month and two left." ;
-    j:kbSha256 "1111111111111111111111111111111111111111111111111111111111111111" .
+    j:kbSha256 "4ae3636cbec680050cd4cfbc7478e1a256fa53e6e66d5a953ef3fdaba1bccc56" .
```

If the hash printed differs, the header edit differs from the one above: fix the edit, not the hash.

- [ ] **Step 8: Run the tests to see them pass**

Run: `python -m pytest tests/test_graph_rules.py tests/test_graph_shapes.py tests/test_graph_store.py tests/test_graph_writer.py tests/test_graph_io.py -q`
Expected: PASS. `TheFixtureIsClean` passes too: the fixture's hash now matches its log.

- [ ] **Step 9: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/record.py src/jsk/graph/ontology.py src/jsk/graph/io.py src/jsk/graph/store.py src/jsk/graph/rules.py tests/graph_fixtures/career/kb.ttl tests/graph_fixtures/career/log.ttl tests/test_graph_rules.py tests/test_graph_shapes.py
git commit -m "feat(graph): kb.ttl and log.ttl share a revision and a hash - a torn write or a hand edit is named on load"
```

---

### Task 2: Writing the record - staged, retried, logged, shadowed

**Files:**
- Modify: `src/jsk/graph/record.py` (the writing half)
- Test: `tests/test_graph_record.py`

**Interfaces:**
- Consumes: Task 1's `record.state`, `record.KB/LOG/SHADOW`, `io.sha256`, `io.normalise`; P1's `writer.write(quads, kind) -> str`; `Store.graph(file) -> list[Quad]`.
- Produces: `record.RecordError(message, fix)`; `record.next_revision(state) -> int`; `record.literal(value, xsd_local) -> Literal`; `record.stamp(quads, revision, today, content=True) -> list[Quad]` (the header at `revision`; `updated` = today only when `content`); `record.entry(revision, today, by, summary, sha, touched=(), minted=(), answer=None) -> list[Quad]`; `record.prepare(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None, content=True) -> (revision, kb_text, log_text)`; `record.replace(src, dst, tries=REPLACE_TRIES, wait=0.05)`; `record.staged(path, text) -> tmp_path`; `record.commit(root, kb_text, log_text)` (raises `RecordError`); `record.write_shadow(root, text)`; `record.shadow(root, sha) -> str|None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_record.py`:

```python
"""kb.ttl and log.ttl kept in step: staged writes, the lock retry, torn writes, the shadow."""
import datetime
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_graph_shapes import FIXTURES, load

from jsk.graph import record
from jsk.graph.io import sha256

TODAY = datetime.date(2026, 9, 24)
REAL_REPLACE = os.replace


def workspace():
    tmp = tempfile.mkdtemp()
    shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
    return tmp


def logged_write(root, **kw):
    """Rewrite the fixture's kb.ttl through the record, as every writing command does."""
    s = load(root)
    rev, kb_text, log_text = record.prepare(s, s.graph(record.KB), TODAY, "fmt", "Reformatted.",
                                            **kw)
    record.commit(root, kb_text, log_text)
    return rev, kb_text


def failing(names, times):
    """An os.replace that raises PermissionError `times` times for files named in `names`."""
    left = {"n": times}

    def fake(src, dst):
        if os.path.basename(dst) in names and left["n"]:
            left["n"] -= 1
            raise PermissionError(13, "locked")
        return REAL_REPLACE(src, dst)
    return fake


class State(unittest.TestCase):
    def test_the_fixture_is_clean(self):
        st = record.state(load(FIXTURES))
        self.assertEqual((st.kind, st.kb_revision, st.log_revision), ("clean", 2, 2))

    def test_a_missing_kb_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(record.state(load(tmp)).kind, "missing")


class Commit(unittest.TestCase):
    def setUp(self):
        self.root = workspace()
        self.addCleanup(shutil.rmtree, self.root)

    def test_a_logged_write_leaves_the_record_clean_at_the_next_revision(self):
        rev, kb_text = logged_write(self.root)
        s = load(self.root)
        self.assertEqual(rev, 3)
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(s.findings, [])
        self.assertEqual(record.shadow(self.root, sha256(kb_text)), kb_text)
        self.assertEqual(sorted(os.listdir(Path(self.root) / "career")), ["kb.ttl", "log.ttl"])

    def test_a_reformat_moves_the_revision_and_not_the_day(self):
        _, kb_text = logged_write(self.root, content=False)
        self.assertIn('j:updated "2026-09-20"^^xsd:date ; j:revision 3 .', kb_text)

    def test_a_lock_that_clears_is_waited_out(self):
        with mock.patch("jsk.graph.record.os.replace", failing({"kb.ttl"}, 2)):
            rev, _ = logged_write(self.root)
        self.assertEqual(record.state(load(self.root)).kind, "clean")

    def test_a_lock_that_holds_on_kb_changes_nothing(self):
        before = {f: (Path(self.root) / f).read_bytes() for f in (record.KB, record.LOG)}
        with mock.patch("jsk.graph.record.os.replace", failing({"kb.ttl"}, 99)), \
                mock.patch("jsk.graph.record.time.sleep"):
            with self.assertRaises(record.RecordError) as e:
                logged_write(self.root)
        self.assertIn("kb.ttl is locked", str(e.exception))
        self.assertIn("nothing was changed", str(e.exception))
        self.assertEqual({f: (Path(self.root) / f).read_bytes() for f in before}, before)
        self.assertEqual(sorted(os.listdir(Path(self.root) / "career")), ["kb.ttl", "log.ttl"])

    def test_a_lock_that_holds_on_log_is_a_torn_write_the_next_load_names(self):
        with mock.patch("jsk.graph.record.os.replace", failing({"log.ttl"}, 99)), \
                mock.patch("jsk.graph.record.time.sleep"):
            with self.assertRaises(record.RecordError) as e:
                logged_write(self.root)
        self.assertIn("jsk kb adopt", e.exception.fix)
        s = load(self.root)
        self.assertEqual(record.state(s).kind, "torn")
        self.assertEqual([f.rule for f in s.fails()], ["log-sync"])

    def test_a_shadow_that_is_not_the_logged_revision_is_ignored(self):
        _, kb_text = logged_write(self.root)
        (Path(self.root) / record.SHADOW).write_text(kb_text + "\n", encoding="utf-8")
        self.assertIsNone(record.shadow(self.root, sha256(kb_text)))

    def test_the_shadow_folder_ignores_itself(self):
        logged_write(self.root)
        self.assertEqual((Path(self.root) / ".jsk" / ".gitignore").read_text(), "*\n")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_record.py -q`
Expected: FAIL - `AttributeError: module 'jsk.graph.record' has no attribute 'prepare'` (the two `State` tests pass: Task 1 built them).

- [ ] **Step 3: The writing half of record.py**

```diff
--- a/src/jsk/graph/record.py
+++ b/src/jsk/graph/record.py
@@ -16,6 +16,7 @@ makes one impossible to miss. Detection, not prevention - the same is true of a
 edit, and both are said plainly where they are reported.
 """
 import os
+import time
 from dataclasses import dataclass
 
 from . import ontology as O
@@ -23,6 +24,15 @@ from . import ontology as O
 KB = "career/kb.ttl"
 LOG = "career/log.ttl"
 SHADOW = os.path.join(".jsk", "kb.last.ttl")     # what the last logged write wrote
+REPLACE_TRIES = 6                                # a Windows lock usually clears in ms
+
+
+class RecordError(Exception):
+    """A write that could not happen. Says what was and was not changed, and the fix."""
+
+    def __init__(self, message, fix):
+        super().__init__(message)
+        self.fix = fix
 
 
 @dataclass(frozen=True)
@@ -80,3 +90,134 @@ def state(store):
     return State("out-of-sync", kb_rev, log_rev, sha,
                  f"kb.ttl is at r{kb_rev} and log.ttl ends at r{log_rev}: one of them was "
                  f"restored without the other")
+
+
+def next_revision(st):
+    return max(st.kb_revision or 0, st.log_revision or 0) + 1
+
+
+def literal(value, dtype):
+    import pyoxigraph as ox
+    return ox.Literal(str(value), datatype=ox.NamedNode(O.XSD + dtype))
+
+
+def stamp(quads, revision, today, content=True):
+    """kb.ttl's triples with its header at `revision`. `updated` is the day the last
+    change landed, so a reformat moves the revision and leaves the day alone."""
+    import pyoxigraph as ox
+
+    kb = ox.NamedNode(O.K + "kb")
+    drop = {O.J + "revision"} | ({O.J + "updated"} if content else set())
+    out = [q for q in quads if not (q.subject == kb and q.predicate.value in drop)]
+    out.append(ox.Quad(kb, ox.NamedNode(O.J + "revision"), literal(revision, "integer")))
+    if content:
+        out.append(ox.Quad(kb, ox.NamedNode(O.J + "updated"), literal(today.isoformat(), "date")))
+    return out
+
+
+def entry(revision, today, by, summary, sha, touched=(), minted=(), answer=None):
+    """One log entry, k:rev_<revision>, as quads."""
+    import pyoxigraph as ox
+
+    s = ox.NamedNode(f"{O.K}rev_{revision}")
+
+    def q(p, o):
+        return ox.Quad(s, ox.NamedNode(O.J + p), o)
+    out = [q("revision", literal(revision, "integer")), q("date", literal(today.isoformat(), "date")),
+           q("by", ox.NamedNode(O.J + by)), q("summary", ox.Literal(summary)),
+           q("kbSha256", ox.Literal(sha))]
+    out += [q("touched", ox.NamedNode(i)) for i in sorted(set(touched))]
+    out += [q("minted", ox.NamedNode(i)) for i in sorted(set(minted))]
+    if answer is not None:
+        out.append(q("answer", ox.Literal(answer)))
+    return out
+
+
+def prepare(store, kb_quads, today, by, summary, touched=(), minted=(), answer=None,
+            content=True):
+    """(revision, kb_text, log_text): what a logged write of `kb_quads` would write -
+    kb.ttl stamped with the next revision, log.ttl with an entry holding its hash."""
+    from .io import sha256
+    from .writer import write
+
+    rev = next_revision(state(store))
+    kb_text = write(stamp(kb_quads, rev, today, content), "kb")
+    log_quads = list(store.graph(LOG)) if LOG in store.parsed else []
+    log_quads += entry(rev, today, by, summary, sha256(kb_text), touched, minted, answer)
+    return rev, kb_text, write(log_quads, "log")
+
+
+def replace(src, dst, tries=REPLACE_TRIES, wait=0.05):
+    """os.replace, retried: on Windows an editor, a sync client or a virus scanner holding
+    the file makes it fail for a moment, and a moment later it succeeds."""
+    for n in range(tries):
+        try:
+            os.replace(src, dst)
+            return
+        except PermissionError:
+            if n == tries - 1:
+                raise RecordError(f"{os.path.basename(dst)} is locked by another program - an "
+                                  f"editor, a sync client or a virus scanner",
+                                  "close it and run the command again") from None
+            time.sleep(wait * (n + 1))
+
+
+def staged(path, text):
+    """`text` written beside `path` as path.tmp, flushed to disk: replacing is then the
+    only step left, and it is the one step the filesystem makes atomic."""
+    tmp = path + ".tmp"
+    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
+        fh.write(text)
+        fh.flush()
+        os.fsync(fh.fileno())
+    return tmp
+
+
+def commit(root, kb_text, log_text):
+    """Write kb.ttl, then log.ttl, then the shadow copy. Both files are staged before
+    either is replaced, so the window a crash can tear is two renames wide."""
+    kb, log = os.path.join(root, KB), os.path.join(root, LOG)
+    tmps = [staged(kb, kb_text), staged(log, log_text)]
+    try:
+        try:
+            replace(tmps[0], kb)
+        except RecordError as e:
+            raise RecordError(f"{e} - nothing was changed", e.fix) from None
+        try:
+            replace(tmps[1], log)
+        except RecordError as e:
+            raise RecordError(f"{e} - kb.ttl was written and log.ttl was not",
+                              "close it, then run `jsk kb adopt`: it logs the write") from None
+    finally:
+        for tmp in tmps:
+            if os.path.exists(tmp):
+                os.remove(tmp)
+    write_shadow(root, kb_text)
+
+
+def write_shadow(root, text):
+    """A copy of what was logged, so `jsk kb adopt` can say what a later hand edit
+    changed. Kept in .jsk/, which ignores itself: it is a cache, never a second record.
+    Best effort - without it adopt still works, and says it had nothing to compare."""
+    folder = os.path.join(root, ".jsk")
+    try:
+        os.makedirs(folder, exist_ok=True)
+        with open(os.path.join(folder, ".gitignore"), "w", encoding="utf-8", newline="\n") as fh:
+            fh.write("*\n")
+        with open(os.path.join(root, SHADOW), "w", encoding="utf-8", newline="\n") as fh:
+            fh.write(text)
+    except OSError:
+        pass
+
+
+def shadow(root, sha):
+    """The text the last logged write wrote, or None when the copy is missing or is not
+    the revision the log says it is."""
+    from .io import normalise, sha256
+
+    try:
+        with open(os.path.join(root, SHADOW), encoding="utf-8") as fh:
+            text = normalise(fh.read())
+    except (OSError, UnicodeDecodeError):
+        return None
+    return text if sha and sha256(text) == sha else None
```

The `staged`, `commit` and `write_shadow` bodies hold `"\n"` and `"*\n"`: use the Edit tool.

- [ ] **Step 4: Run them to see them pass**

Run: `python -m pytest tests/test_graph_record.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/record.py tests/test_graph_record.py
git commit -m "feat(graph): the record's write - staged, retried through a Windows lock, logged, shadowed"
```

---

### Task 3: Reading a changeset

**Files:**
- Create: `src/jsk/graph/changeset.py`
- Test: `tests/test_graph_changeset.py`

**Interfaces:**
- Consumes: P1's `io.parse_text(text, file, kind="changeset")` (TriG; raises `io.GraphError`), `ontology.OP`, `ontology.OPS`, `ontology.class_of`, `ontology.BY_NAME`, `writer.curie`.
- Produces: `changeset.OP`, `changeset.GRAPHS`; `changeset.Refusal(focus, detail, fix)` with `.text()`; `changeset.Refused(refusals)` (every reason, not the first); `changeset.Changeset(add, set, retire, delete, base, summary)` - four lists of `(s, p, o)` pyoxigraph terms, `base: int|None`, `summary: str|None`; `changeset.read(text, file="changeset.trig") -> Changeset`; `changeset.curie(iri)` (knows `op:`); `changeset.name(term) -> str`. Test helper `test_graph_changeset.PFX` (the five prefixes) is imported by Tasks 4-7.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_changeset.py`:

```python
"""Reading a changeset: its four graphs and header, and one test per refusal it can make
without the career in front of it."""
import unittest

from jsk.graph import changeset as C
from jsk.graph.io import GraphError

PFX = """@prefix j: <tag:jsk,2026:ns#> .
@prefix k: <tag:jsk,2026:id/> .
@prefix c: <tag:jsk,2026:concept/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix op: <tag:jsk,2026:op#> .
"""


def read(body):
    return C.read(PFX + body)


def refusals(body):
    try:
        read(body)
    except C.Refused as e:
        return [x.text() for x in e.refusals]
    raise AssertionError("not refused")


class Reading(unittest.TestCase):
    def test_the_four_graphs_and_the_header(self):
        cs = read('op:changeset op:base 7 ; op:summary "From the braindump." .\n'
                  'op:add { k:prj_payments j:name "Payments" . }\n'
                  'op:set { k:prj_legacy j:strength 2 . }\n'
                  'op:retire { k:prj_intranet j:reason "Too old." . }\n'
                  'op:delete { k:q_dup a op:Entry . k:ach_x_did_thing j:shows c:java . }\n')
        self.assertEqual((cs.base, cs.summary), (7, "From the braindump."))
        self.assertEqual([len(cs.add), len(cs.set), len(cs.retire), len(cs.delete)], [1, 1, 1, 2])

    def test_a_new_bullet_may_leave_its_id_to_jsk(self):
        cs = read('op:add { [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut it." . }\n')
        self.assertEqual(len(cs.add), 3)

    def test_a_changeset_saved_by_a_windows_editor_reads_the_same(self):
        body = 'op:add { k:prj_payments j:name "Payments" . }\n'
        cs = C.read("﻿" + (PFX + body).replace("\n", "\r\n"))
        self.assertEqual(len(cs.add), 1)
        self.assertEqual(cs.add[0][2].value, "Payments")

    def test_a_syntax_error_is_a_graph_error(self):
        with self.assertRaises(GraphError):
            read("op:add { k:prj_x j:name . }\n")


class Refusals(unittest.TestCase):
    def assertRefused(self, body, *says):
        found = "\n".join(refusals(body))
        for s in says:
            self.assertIn(s, found)

    def test_a_triple_outside_any_graph(self):
        self.assertRefused('k:prj_x j:name "X" .\n', "outside any graph", "op:add")

    def test_an_unknown_graph(self):
        self.assertRefused('op:insert { k:prj_x j:name "X" . }\n', "a graph named op:insert")

    def test_the_derived_graph(self):
        self.assertRefused('j:derived { k:prj_x j:name "X" . }\n', "a graph named j:derived")

    def test_confirmed_provenance(self):
        self.assertRefused('op:set { k:prj_x j:provenance j:confirmed . }\n',
                           "a changeset cannot confirm", "jsk kb confirm")

    def test_a_blank_node_object(self):
        self.assertRefused('op:add { k:prj_x j:headlineMetric [ j:subject "x" ] . }\n',
                           "points at a blank node")

    def test_a_blank_node_outside_add(self):
        self.assertRefused('op:set { [] j:project k:prj_x . }\n', "a blank node in op:set")

    def test_a_blank_node_that_is_not_a_bullet(self):
        self.assertRefused('op:add { [] j:name "Payments" . }\n', "a blank node with no j:project")

    def test_an_unknown_predicate_names_the_nearest(self):
        self.assertRefused('op:add { k:prj_x j:strenght 3 . }\n',
                           "j:strenght is not a Project predicate", "did you mean j:strength?")

    def test_a_foreign_predicate(self):
        self.assertRefused('op:add { k:prj_x <http://schema.org/name> "X" . }\n',
                           "is not a Project predicate")

    def test_a_derived_type(self):
        self.assertRefused('op:add { k:prj_x a j:Project . }\n', "rdf:type is derived")

    def test_not_a_jsk_id(self):
        self.assertRefused('op:add { k:project_x j:name "X" . }\n', "not a jsk id")

    def test_an_entry_of_another_file(self):
        self.assertRefused('op:add { k:evt_x j:kind j:note . }\n', "an Event lives in application.ttl",
                           "writes career/kb.ttl only")

    def test_the_log(self):
        self.assertRefused('op:add { k:rev_9 j:summary "x" . }\n', "lives in log.ttl")

    def test_the_header_jsk_writes(self):
        self.assertRefused('op:set { k:kb j:updated "2026-01-01"^^xsd:date . }\n',
                           "j:updated is written by jsk")

    def test_retire_takes_a_reason_only(self):
        self.assertRefused('op:retire { k:prj_x j:retired "2026-01-01"^^xsd:date . }\n',
                           "op:retire takes j:reason only")

    def test_op_terms_inside_a_graph(self):
        self.assertRefused('op:add { k:prj_x j:uses op:Entry . }\n', "op: terms name graphs")

    def test_every_refusal_is_reported_not_the_first(self):
        self.assertEqual(len(refusals('op:add { k:prj_x j:strenght 3 ; a j:Project . }\n')), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_changeset.py -q`
Expected: FAIL - `ImportError: cannot import name 'changeset' from 'jsk.graph'`.

- [ ] **Step 3: changeset.py**

```python
"""A changeset: the one way an agent changes career/kb.ttl, as TriG.

    @prefix op: <tag:jsk,2026:op#> .
    op:changeset op:base 7 ; op:summary "The payments project, from the braindump" .
    op:add    { k:prj_payments j:name "Payments platform" ; ... }
    op:set    { k:prj_legacy j:strength 2 . }
    op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
    op:delete { k:q_duplicate a op:Entry . k:ach_x j:shows c:java . }

`op:add` adds triples, `op:set` replaces every value of each (subject, predicate) it names,
`op:retire` retires an entry with its reason, `op:delete` removes exact triples - or, for
`a op:Entry`, the whole entry. `op:base` is the log revision the changeset was drafted
against; `op:summary` is what the log says it did.

This module reads a changeset and refuses what can be refused without the career in
front of it. What needs the career - does the entry exist, is it referenced, was it
sent - is edit.py's.
"""
import difflib
from dataclasses import dataclass, field

from . import ontology as O

OP = O.OP
GRAPHS = O.OPS
# Written by jsk, never by a changeset: the header's revision and day, and the format.
WRITTEN_BY_JSK = {"format", "updated", "revision"}


@dataclass(frozen=True)
class Refusal:
    focus: str         # a CURIE, or "" for the whole changeset
    detail: str
    fix: str

    def text(self):
        return f"{self.focus + ' - ' if self.focus else ''}{self.detail}\n        fix: {self.fix}"


class Refused(Exception):
    """Every reason a changeset was not applied - all of them, not the first."""

    def __init__(self, refusals):
        super().__init__(f"{len(refusals)} refusal(s)")
        self.refusals = refusals


@dataclass
class Changeset:
    add: list = field(default_factory=list)       # (s, p, o) pyoxigraph terms
    set: list = field(default_factory=list)
    retire: list = field(default_factory=list)
    delete: list = field(default_factory=list)
    base: int = None
    summary: str = None


def curie(iri):
    if iri.startswith(OP):
        return "op:" + iri[len(OP):]
    from .writer import curie as c
    return c(iri)


def article(cls):
    return ("an " if cls[0] in "AEIOU" else "a ") + cls


def name(t):
    import pyoxigraph as ox
    if isinstance(t, ox.BlankNode):
        return "a blank node"
    return curie(t.value) if isinstance(t, ox.NamedNode) else repr(t.value)


def read(text, file="changeset.trig"):
    """The changeset in `text`. Raises GraphError on a syntax error and Refused on
    anything else wrong with it."""
    import pyoxigraph as ox

    from .io import parse_text

    parsed = parse_text(text, file, kind="changeset")
    cs, refusals = Changeset(), []

    def refuse(focus, detail, fix):
        refusals.append(Refusal(focus, detail, fix))

    for q in parsed.quads:
        s, p, o, g = q.subject, q.predicate, q.object, q.graph_name
        if isinstance(g, ox.DefaultGraph):
            header(cs, s, p, o, refuse)
            continue
        where = g.value[len(OP):] if isinstance(g, ox.NamedNode) and g.value.startswith(OP) else None
        if where not in GRAPHS:
            refuse("", f"a graph named {name(g)}",
                   "changes go in op:add, op:set, op:retire or op:delete")
            continue
        if check(where, s, p, o, refuse):
            getattr(cs, where).append((s, p, o))
    bullets_named(parsed.quads, refuse)
    if refusals:
        raise Refused(refusals)
    return cs


def header(cs, s, p, o, refuse):
    import pyoxigraph as ox

    if s == ox.NamedNode(OP + "changeset") and p.value == OP + "base" and \
            isinstance(o, ox.Literal) and o.value.isdigit():
        cs.base = int(o.value)
    elif s == ox.NamedNode(OP + "changeset") and p.value == OP + "summary" and \
            isinstance(o, ox.Literal) and o.value.strip():
        cs.summary = o.value.strip()
    else:
        refuse(name(s), f"{name(p)} {name(o)} is outside any graph",
               "the default graph holds only op:changeset op:base N ; op:summary \"…\"; "
               "put changes in op:add, op:set, op:retire or op:delete")


def check(where, s, p, o, refuse):
    """True when (s, p, o) may stand in graph `where`; otherwise refuses and says why."""
    import pyoxigraph as ox

    if isinstance(o, ox.BlankNode):
        refuse(name(s), f"{name(p)} points at a blank node",
               "give the entry an id of its own and point at that")
        return False
    if isinstance(s, ox.BlankNode):
        if where != "add":
            refuse("", f"a blank node in op:{where}", "name the entry by its id")
            return False
        return predicate(where, "Achievement", s, p, o, refuse)
    cls = O.class_of(s.value)
    if cls is None:
        refuse(name(s), "not a jsk id", "ids are k:<prefix>_<words>; concepts c:<words-with-dashes>")
        return False
    if "kb" not in O.BY_NAME[cls].kinds:
        home = " or ".join(k + ".ttl" for k in O.BY_NAME[cls].kinds)
        refuse(name(s), f"{article(cls)} lives in {home}", "`jsk kb apply` writes career/kb.ttl only")
        return False
    if where == "delete" and p.value == O.RDF_TYPE and o == ox.NamedNode(OP + "Entry"):
        return True
    return predicate(where, cls, s, p, o, refuse)


def predicate(where, cls, s, p, o, refuse):
    import pyoxigraph as ox

    focus = name(s) if isinstance(s, ox.NamedNode) else "a new bullet"
    if any(isinstance(t, ox.NamedNode) and t.value.startswith(OP) for t in (p, o)):
        refuse(focus, f"{name(p)} {name(o)}: op: terms name graphs and whole entries only",
               "use j: predicates inside a graph; `a op:Entry` only in op:delete")
        return False
    if p.value == O.RDF_TYPE:
        if cls == "Concept" and where in ("add", "set"):
            return True
        refuse(focus, "rdf:type is derived from the id prefix",
               "drop the `a …`; only a c: concept states its class")
        return False
    pname = p.value[len(O.J):] if p.value.startswith(O.J) else None
    preds = O.BY_NAME[cls].preds
    if pname not in preds:
        near = difflib.get_close_matches(pname or p.value, list(preds), n=1)
        refuse(focus, f"{name(p)} is not {article(cls)} predicate",
               f"did you mean j:{near[0]}?" if near else
               f"{article(cls)} takes {', '.join('j:' + x for x in preds)}")
        return False
    if cls == "KB" and pname in WRITTEN_BY_JSK:
        refuse(focus, f"j:{pname} is written by jsk", "leave the header's j:format, j:updated "
               "and j:revision out; every write sets them")
        return False
    if pname == "provenance" and where in ("add", "set") and o == ox.NamedNode(O.J + "confirmed"):
        refuse(focus, "a changeset cannot confirm", "confirm with the person, then "
               "`jsk kb confirm <id> --answer \"what they said\"`; leave provenance out or "
               "state j:inferred")
        return False
    if where == "retire" and pname != "reason":
        refuse(focus, f"op:retire takes j:reason only, not {name(p)}",
               "state why it is retired; jsk dates it")
        return False
    return True


def bullets_named(quads, refuse):
    """A blank node is a new bullet waiting for its id, so it has to say which project it
    belongs to - that is where the id's stem comes from."""
    import pyoxigraph as ox

    blanks = {q.subject for q in quads if isinstance(q.subject, ox.BlankNode)}
    for b in blanks:
        if not any(q.subject == b and q.predicate.value == O.J + "project" for q in quads):
            refuse("a new bullet", "a blank node with no j:project",
                   "only a new bullet may leave its id to jsk, and it names its j:project; "
                   "any other new entry names its own id")
```

- [ ] **Step 4: Run them to see them pass**

Run: `python -m pytest tests/test_graph_changeset.py -q`
Expected: PASS (21 tests).

- [ ] **Step 5: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/changeset.py tests/test_graph_changeset.py
git commit -m "feat(graph): changesets in TriG - four graphs, and every reason one is refused"
```

---

### Task 4: Merging a changeset into the career

**Files:**
- Create: `src/jsk/graph/edit.py`
- Test: `tests/test_graph_edit.py`

**Interfaces:**
- Consumes: Task 3's `Changeset`, `Refusal`, `Refused`, `changeset.OP`, `changeset.curie`; Task 1's `record.KB`, `record.LOG`; P1's `Store.graph`, `Store.select`, `Store.homes`, `Store.definitions`, `store.graph_iri`.
- Produces: `edit.Edit(quads, touched: set[str], minted: set[str], notes: list[str])`; `edit.apply(store, cs, today) -> Edit` (raises `Refused` with every reason); helpers `carried_versions(store) -> {version iri: [app iris]}`, `log_entries(store) -> [(revision, {ids})]`, `taken_ids(store)`, `words(text)`, `mint_bullet(project, text, taken) -> iri|None`, `same_bullet(triples, project, text)`, `mint_question(about, taken)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_edit.py`:

```python
"""A changeset merged into the fixture career: the four graphs, the refusals that need the
record, and what apply does unasked - provenance, questions, bullet ids, versions."""
import datetime
import unittest

from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES, load

from jsk.graph import changeset, edit
from jsk.graph import ontology as O
from jsk.graph.changeset import Refused

TODAY = datetime.date(2026, 9, 24)
STORE = None


def store():
    global STORE
    if STORE is None:
        STORE = load(FIXTURES)
    return STORE


def run(body):
    return edit.apply(store(), changeset.read(PFX + body), TODAY)


def refused(body):
    try:
        run(body)
    except Refused as e:
        return "\n".join(r.text() for r in e.refusals)
    raise AssertionError("not refused")


def props(e, local):
    """{predicate: sorted values} of k:<local> after the edit."""
    out = {}
    for q in e.quads:
        if q.subject.value == O.K + local:
            out.setdefault(q.predicate.value[len(O.J):], []).append(q.object.value)
    return {p: sorted(v) for p, v in out.items()}


NEW_PROJECT = ('op:add { k:prj_payments j:name "Payments platform" ; '
               'j:position k:pos_meridian_principal ; j:strength 4 ; j:recency 2025 . }\n')


class Adding(unittest.TestCase):
    def test_a_new_entry_is_inferred_and_asked_about(self):
        e = run(NEW_PROJECT)
        self.assertEqual(props(e, "prj_payments")["provenance"], [O.J + "inferred"])
        self.assertEqual(props(e, "q_prj_payments")["about"], [O.K + "prj_payments"])
        self.assertEqual(e.minted, {O.K + "prj_payments", O.K + "q_prj_payments"})
        self.assertEqual(e.touched, set())

    def test_a_new_bullet_is_named_by_its_project_and_words(self):
        e = run(NEW_PROJECT[:-3] + ' [] j:project k:prj_payments ; j:rank 1 ; '
                'j:text "Cut settlement latency from 800 ms to 200 ms." . }\n')
        self.assertIn(O.K + "ach_payments_cut_settlement_latency", e.minted)
        self.assertIn("minted k:ach_payments_cut_settlement_latency", e.notes)

    def test_a_minted_id_is_never_one_already_used(self):
        e = run('op:add { [] j:project k:prj_clinical_events ; j:rank 3 ; '
                'j:text "Clinical event latency, halved again." . }\n')
        # ach_clinical_events_clinical_event_latency is free; the fixture's ids are not reused
        self.assertIn(O.K + "ach_clinical_events_clinical_event_latency", e.minted)
        e2 = run('op:add { [] j:project k:prj_clinical_events ; j:rank 3 ; '
                 'j:text "Event latency cut, again." . }\n'
                 'op:add { k:ach_clinical_events_event_latency_cut j:project k:prj_clinical_events ;'
                 ' j:rank 4 ; j:text "x" . }\n')
        # the three-word id is named by the changeset itself, so the bullet takes four
        self.assertIn(O.K + "ach_clinical_events_event_latency_cut", e2.minted)
        self.assertIn(O.K + "ach_clinical_events_event_latency_cut_again", e2.minted)

    def test_adding_a_second_value_where_one_is_allowed_says_use_set(self):
        self.assertIn("op:set replaces it", refused('op:add { k:prj_clinical_events j:strength 4 . }\n'))

    def test_a_shipped_concept_can_be_extended(self):
        e = run('op:add { c:docker j:label "Docker Engine" . }\n')
        self.assertEqual(props_c(e, "docker")["label"], ["Docker Engine"])


def props_c(e, slug):
    out = {}
    for q in e.quads:
        if q.subject.value == O.C + slug:
            out.setdefault(q.predicate.value[len(O.J):], []).append(q.object.value)
    return out


class Setting(unittest.TestCase):
    def test_a_changed_claim_is_an_unconfirmed_claim(self):
        e = run('op:set { k:ach_clinical_events_led_migration j:text "Led 6 engineers." . }\n')
        p = props(e, "ach_clinical_events_led_migration")
        self.assertEqual((p["text"], p["provenance"]), (["Led 6 engineers."], [O.J + "inferred"]))
        self.assertIn(O.K + "q_ach_clinical_events_led_migration", e.minted)
        self.assertIn("k:ach_clinical_events_led_migration is now inferred: j:text changed", e.notes)

    def test_a_change_that_is_not_a_claim_keeps_its_provenance(self):
        e = run('op:set { k:prj_clinical_events j:strength 4 . }\n')
        self.assertEqual(props(e, "prj_clinical_events")["provenance"], [O.J + "confirmed"])
        self.assertEqual(e.touched, {O.K + "prj_clinical_events"})

    def test_a_stated_provenance_stands(self):
        e = run('op:set { k:ach_clinical_events_led_migration j:text "Led 6." ; '
                'j:provenance j:needs-verification . }\n')
        self.assertEqual(props(e, "ach_clinical_events_led_migration")["provenance"],
                         [O.J + "needs-verification"])

    def test_an_open_question_is_not_asked_twice(self):
        e = run('op:set { k:ach_site_onboarding_sites_one_platform j:text "Brought 42 sites on." . }\n')
        self.assertFalse([m for m in e.minted if "q_" in m])

    def test_setting_what_is_already_there_changes_nothing(self):
        e = run('op:set { k:prj_clinical_events j:strength 5 . }\n')
        self.assertEqual((e.touched, e.minted), (set(), set()))

    def test_setting_an_entry_that_does_not_exist(self):
        self.assertIn("op:add it instead", refused('op:set { k:prj_nothing j:strength 2 . }\n'))


class Versions(unittest.TestCase):
    def test_a_sent_version_is_never_changed_its_new_number_is_the_next_version(self):
        e = run('op:set { k:met_team.v1 j:value 7 . }\n')
        self.assertEqual(props(e, "met_team.v1")["value"], ["6"])
        self.assertEqual(props(e, "met_team.v1")["validUntil"], ["2026-09-24"])
        v2 = props(e, "met_team.v2")
        self.assertEqual((v2["value"], v2["validFrom"], v2["provenance"], v2["source"]),
                         (["7"], ["2026-09-24"], [O.J + "inferred"], ["org chart"]))
        self.assertTrue(any("sent in k:app_acme_platform_engineer" in n for n in e.notes))
        self.assertIn(O.K + "q_met_team_v2", e.minted)

    def test_a_version_never_sent_is_corrected_in_place(self):
        e = run('op:set { k:met_sites.v1 j:value 43 . }\n')
        self.assertEqual(props(e, "met_sites.v1")["value"], ["43"])
        self.assertNotIn(O.K + "met_sites.v2", e.minted)

    def test_anything_else_on_a_sent_version_is_refused(self):
        self.assertIn("sent in k:app_acme_platform_engineer",
                      refused('op:set { k:met_team.v1 j:source "HR system" . }\n'))

    def test_a_new_version_closes_the_current_one(self):
        e = run('op:add { k:met_sites.v2 j:of k:met_sites ; j:value 50 ; j:confidence j:measured ; '
                'j:validFrom "2026-09-01"^^xsd:date . }\n')
        self.assertEqual(props(e, "met_sites.v1")["validUntil"], ["2026-09-01"])
        self.assertIn("closed k:met_sites.v1: k:met_sites.v2 is current", e.notes)


class Retiring(unittest.TestCase):
    def test_retiring_dates_it_and_keeps_the_reason(self):
        e = run('op:retire { k:prj_site_onboarding j:reason "Superseded." . }\n')
        p = props(e, "prj_site_onboarding")
        self.assertEqual((p["retired"], p["reason"]), (["2026-09-24"], ["Superseded."]))

    def test_retiring_what_is_retired(self):
        self.assertIn("already retired",
                      refused('op:retire { k:prj_intranet_refresh j:reason "Old." . }\n'))


class Deleting(unittest.TestCase):
    def test_an_entry_nothing_points_at(self):
        e = run('op:delete { k:q_team_size a op:Entry . }\n')
        self.assertEqual(props(e, "q_team_size"), {})
        self.assertEqual(e.touched, {O.K + "q_team_size"})

    def test_an_entry_something_points_at_is_retired_instead(self):
        text = refused('op:delete { k:met_sites a op:Entry . }\n')
        self.assertIn("referenced by k:ach_site_onboarding_sites_one_platform", text)
        self.assertIn("retire it", text)

    def test_a_reference_from_an_application_counts(self):
        self.assertIn("k:app_acme_platform_engineer",
                      refused('op:delete { k:ach_clinical_events_led_migration a op:Entry . }\n'))

    def test_a_triple_that_is_not_there(self):
        self.assertIn("has no j:shows c:java to delete",
                      refused('op:delete { k:ach_clinical_events_led_migration j:shows c:java . }\n'))


class Base(unittest.TestCase):
    def test_an_entry_changed_since_the_base_is_a_conflict(self):
        text = refused('op:changeset op:base 1 .\nop:set { k:met_team.v1 j:source "x" . }\n')
        self.assertIn("changed at r2, after this changeset's op:base r1", text)

    def test_the_base_the_record_is_at_is_no_conflict(self):
        run('op:changeset op:base 2 .\nop:set { k:prj_clinical_events j:strength 4 . }\n')

    def test_a_base_ahead_of_the_log(self):
        self.assertIn("ahead of log.ttl", refused('op:changeset op:base 9 .\n'
                                                  'op:set { k:prj_clinical_events j:strength 4 . }\n'))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_edit.py -q`
Expected: FAIL - `ImportError: cannot import name 'edit' from 'jsk.graph'`.

- [ ] **Step 3: edit.py**

The `same_bullet` continuation line ends in a backslash: write the file with the Write tool.

```python
"""A changeset merged into career/kb.ttl, and the refusals only the career can answer.

changeset.py has already refused what a changeset may never say. What is left needs the
record: does the entry exist, is anything pointing at it, was this metric version sent,
did somebody change the same entry since the changeset was drafted.

Four things happen that the changeset did not ask for, because a record that let them
be skipped would be wrong without anyone noticing:

- a claim changed is a claim unconfirmed: the entry drops to j:inferred;
- an entry left inferred gets a question, so confirming it is on somebody's list;
- a new bullet gets its id from its project and its words;
- a sent metric version never changes: a new value becomes the next version.
"""
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from . import ontology as O
from .changeset import OP, Refusal, Refused, curie

PROVENANCE = O.J + "provenance"
# A version's number: changing these on a sent version makes a new version instead.
VERSIONED = {"value", "baseline", "kind"}
# What a new version does not inherit from the one it replaces.
NOT_INHERITED = {"validFrom", "validUntil", "provenance", "note", "retired", "reason"}
# Words that say nothing about what a bullet is; left out of the id minted for it.
STOP = frozenset("""a an the and or but of to in on for with by at from as into onto over under
via per its their our my his her was were is are be been being that this these those which who
whom than then so across up down out off it we i they them us me all any each more most""".split())


@dataclass
class Edit:
    quads: list                      # kb.ttl after the change, as quads
    touched: set = field(default_factory=set)
    minted: set = field(default_factory=set)
    notes: list = field(default_factory=list)


def node(iri):
    import pyoxigraph as ox
    return ox.NamedNode(iri)


def date(day):
    import pyoxigraph as ox
    return ox.Literal(day.isoformat(), datatype=ox.NamedNode(O.XSD + "date"))


def local(p):
    return p.value[len(O.J):] if p.value.startswith(O.J) else None


def values(triples, s, p):
    return {o for t_s, t_p, o in triples if t_s == s and t_p == p}


def carried_versions(store):
    """{metric version iri: [application iris]} - versions an application sent."""
    out = defaultdict(list)
    for r in store.select(f"PREFIX j: <{O.J}> SELECT ?v ?a WHERE {{ ?a j:carriedVersion ?v }}"):
        out[r["v"].value].append(r["a"].value)
    return out


def log_entries(store):
    """[(revision, {ids touched or minted})] from log.ttl, oldest first."""
    from .record import LOG

    if LOG not in store.parsed:
        return []
    by = defaultdict(lambda: {"ids": set()})
    for q in store.graph(LOG):
        e = by[q.subject.value]
        if local(q.predicate) == "revision":
            e["revision"] = int(q.object.value)
        elif local(q.predicate) in ("touched", "minted"):
            e["ids"].add(q.object.value)
    return sorted((e["revision"], e["ids"]) for e in by.values() if "revision" in e)


def taken_ids(store):
    """Every id the record has ever used: what exists, and what the log says existed."""
    ids = set(store.homes)
    for _, named in log_entries(store):
        ids |= named
    return ids


def words(text):
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [w for w in re.findall(r"[a-z]+", folded) if w not in STOP and len(w) > 1]


def mint_bullet(project, text, taken):
    """ach_<project stem>_<three content words>, then four; None when both are taken or
    the text has no words - the changeset then names the bullet itself."""
    stem = project[len(O.K) + len("prj_"):]
    found = words(text)
    for n in (3, 4):
        iri = f"{O.K}ach_{stem}_{'_'.join(found[:n])}"
        if found and iri not in taken:
            return iri
    return None


def same_bullet(triples, project, text):
    """The live bullet of `project` whose text is `text`, or None."""
    of, says, retired = node(O.J + "project"), node(O.J + "text"), node(O.J + "retired")
    for s, p, o in triples:
        if p == says and o.value == text and (s, of, project) in triples \
                and not values(triples, s, retired):
            return s
    return None


def mint_question(about, taken):
    base = f"{O.K}q_{about[len(O.K):].replace('.', '_')}"
    iri, n = base, 2
    while iri in taken:
        iri, n = f"{base}_{n}", n + 1
    return iri


def apply(store, cs, today):
    """The kb.ttl `cs` makes, as an Edit. Raises Refused with every reason it cannot."""
    import pyoxigraph as ox

    from .record import KB

    refusals = []

    def refuse(s, detail, fix):
        refusals.append(Refusal(curie(s.value) if isinstance(s, ox.NamedNode) else "", detail, fix))

    before = {(q.subject, q.predicate, q.object) for q in store.graph(KB)}
    in_kb = {s for s, _, _ in before}
    carried = carried_versions(store)
    # Ids the changeset names are taken too: a bullet minted onto one would merge with it.
    taken = taken_ids(store) | {s.value for s, _, _ in cs.add + cs.set + cs.retire + cs.delete
                                if isinstance(s, ox.NamedNode)}
    after = set(before)
    redirects = defaultdict(dict)          # sent version -> {predicate: objects}

    def exists(s):
        # A concept the shipped vocabulary defines exists: kb.ttl may extend or narrow it.
        return s in in_kb or (s.value.startswith(O.C) and s.value in store.homes)

    def sent(s, what):
        apps = ", ".join(curie(a) for a in sorted(carried[s.value]))
        refuse(s, f"{what}, but it was sent in {apps}", "a sent version never changes: add "
               "the new number as the next version (k:met_x.vN), and jsk closes this one")

    base_conflicts(store, cs, refuse)

    entries = {s for s, p, o in cs.delete if o == ox.NamedNode(OP + "Entry")}
    for s, p, o in cs.delete:
        if s.value in carried:
            sent(s, "op:delete")
        elif s in entries:
            if s not in in_kb:
                refuse(s, "op:delete of an entry kb.ttl does not hold", "check the id")
            after -= {t for t in after if t[0] == s}
        elif (s, p, o) not in before:
            refuse(s, f"has no {curie(p.value)} {name_of(o)} to delete", "check it against "
                   f"`jsk kb show {curie(s.value)}`")
        else:
            after.discard((s, p, o))

    grouped = defaultdict(set)
    for s, p, o in cs.set:
        grouped[(s, p)].add(o)
    for (s, p), objs in grouped.items():
        if not exists(s):
            refuse(s, "op:set on an entry that does not exist", "op:add it instead")
        elif s.value in carried and local(p) in VERSIONED:
            redirects[s][p] = objs
        elif s.value in carried:
            sent(s, f"op:set {curie(p.value)}")
        else:
            after -= {t for t in after if t[0] == s and t[1] == p}
            after |= {(s, p, o) for o in objs}

    def add(s, p, o):
        if s.value in carried:
            sent(s, f"op:add {curie(p.value)}")
            return
        pred = O.BY_NAME[O.class_of(s.value)].preds.get(local(p)) if local(p) else None
        others = values(after, s, p) - {o}
        if pred and pred.card in "1?" and others and (s, p) not in grouped:
            refuse(s, f"already has {curie(p.value)} {name_of(sorted(others, key=str)[0])}",
                   "op:set replaces it; op:add only adds")
            return
        after.add((s, p, o))

    blanks = defaultdict(list)
    for s, p, o in cs.add:
        if isinstance(s, ox.BlankNode):
            blanks[s].append((p, o))
        else:
            add(s, p, o)

    minted_bullets = []
    for b, props in blanks.items():
        project = next(o for p, o in props if local(p) == "project")
        text = next((o.value for p, o in props if local(p) == "text"), "")
        if O.class_of(project.value) != "Project":
            refuse(project, "a new bullet's j:project is not a k:prj_ id", "point it at its project")
            continue
        same = same_bullet(after, project, text)
        if same is not None:
            # Re-running an apply must not mint the bullet twice: the same words under
            # the same project are the same bullet, and what the changeset says is added
            # to it like any op:add.
            for p, o in props:
                add(same, p, o)
            continue
        iri = mint_bullet(project.value, text, taken | {x.value for x in minted_bullets})
        if iri is None:
            refuse(project, f"no id could be minted for the bullet {text[:40]!r}",
                   "name it yourself: ach_<project>_<two to four words>")
            continue
        minted_bullets.append(node(iri))
        after |= {(node(iri), p, o) for p, o in props}

    for s, p, o in cs.retire:
        if s.value in carried:
            sent(s, "op:retire")
        elif s not in in_kb:
            refuse(s, "op:retire of an entry kb.ttl does not hold", "check the id")
        elif values(after, s, node(O.J + "retired")):
            refuse(s, "is already retired", "leave it, or op:set its j:reason")
        else:
            after |= {(s, node(O.J + "retired"), date(today)), (s, p, o)}

    for e in entries:
        referenced(store, after, e, refuse)
    if refusals:
        raise Refused(refusals)

    edit = Edit([])
    for v, changes in redirects.items():
        new_version(after, v, changes, today, carried, edit)
    close_versions(after, before, today, edit)
    provenance(after, before, cs, minted_bullets, edit)
    questions(after, before, today, taken, edit)

    subjects = {s for s, _, _ in after}
    old = {s for s, _, _ in before}
    edit.minted |= {s.value for s in subjects - old}
    edit.touched = {s.value for s, _, _ in before ^ after} - edit.minted
    for b in minted_bullets:
        edit.notes.append(f"minted {curie(b.value)}")
    edit.quads = [ox.Quad(s, p, o) for s, p, o in after]
    return edit


def name_of(o):
    import pyoxigraph as ox
    return curie(o.value) if isinstance(o, ox.NamedNode) else repr(o.value)


def base_conflicts(store, cs, refuse):
    """op:base rN: refused when an entry this changeset names changed after rN. The log
    records ids, not predicates, so two edits of one entry conflict even when they
    touch different fields - re-reading it is cheap, a silent overwrite is not."""
    import pyoxigraph as ox

    if cs.base is None:
        return
    entries = log_entries(store)
    last = entries[-1][0] if entries else 0
    if cs.base > last:
        refuse(None, f"op:base r{cs.base} is ahead of log.ttl, which ends at r{last}",
               "draft against the record as it is: `jsk kb show` the entries again")
        return
    named = {s.value for s, _, _ in cs.add + cs.set + cs.retire + cs.delete
             if isinstance(s, ox.NamedNode)}
    for rev, ids in entries:
        if rev > cs.base:
            for iri in sorted(named & ids):
                refuse(node(iri), f"changed at r{rev}, after this changeset's op:base r{cs.base}",
                       f"re-read it with `jsk kb show {curie(iri)}` and redraft against r{last}")


def referenced(store, after, e, refuse):
    """An entry is deleted only when nothing points at it; otherwise it is retired."""
    from .record import KB
    from .store import graph_iri

    if [f for f in store.definitions.get(e.value, []) if f != KB]:
        return      # the shipped vocabulary still defines it: removing kb.ttl's part is safe
    refs = sorted({curie(s.value) for s, _, o in after if o == e})
    rows = store.select(f"""PREFIX j: <{O.J}> SELECT DISTINCT ?s WHERE {{ GRAPH ?g {{ ?s ?p <{e.value}> }}
        FILTER(?g != j:derived && ?g != <{graph_iri(KB)}>) FILTER(?p NOT IN (j:touched, j:minted)) }}""")
    refs += sorted(curie(r["s"].value) for r in rows)
    if refs:
        refuse(e, f"is referenced by {', '.join(refs)}",
               "retire it (op:retire with a j:reason) - or remove those references first")


def version_number(iri):
    return int(iri.rsplit(".v", 1)[1])


def versions_of(triples, metric):
    of = node(O.J + "of")
    return sorted({s for s, p, o in triples if p == of and o == metric},
                  key=lambda s: version_number(s.value))


def new_version(after, v, changes, today, carried, edit):
    """A sent version's new number, as the next version of its metric."""
    of = node(O.J + "of")
    metric = next(o for s, p, o in after if s == v and p == of)
    n = max(version_number(x.value) for x in versions_of(after, metric)) + 1
    new = node(f"{metric.value}.v{n}")
    copy = {(new, p, o) for s, p, o in after if s == v and local(p) not in NOT_INHERITED
            and p not in changes}
    copy |= {(new, p, o) for p, objs in changes.items() for o in objs}
    copy.add((new, node(O.J + "validFrom"), date(today)))
    after |= copy
    apps = ", ".join(curie(a) for a in sorted(carried[v.value]))
    edit.notes.append(f"{curie(v.value)} was sent in {apps}, so it stays as it was: the new "
                      f"number is {curie(new.value)}")


def close_versions(after, before, today, edit):
    """Exactly one version of a metric is current. When this change adds one, the one it
    replaces is closed - the day the new one starts, or today. Closing is the one change
    a sent version takes: its number is what was sent, and that does not change."""
    until, start = node(O.J + "validUntil"), node(O.J + "validFrom")
    new = {s for s, _, _ in after} - {s for s, _, _ in before}
    metrics = {o for s, p, o in after if s in new and p == node(O.J + "of")}
    for m in metrics:
        vs = versions_of(after, m)
        open_ = [x for x in vs if not values(after, x, until)]
        for x in open_[:-1]:
            later = [y for y in vs if version_number(y.value) > version_number(x.value)]
            day = next(iter(values(after, later[0], start)), None) if later else None
            after.add((x, until, day if day is not None else date(today)))
            edit.notes.append(f"closed {curie(x.value)}: {curie(open_[-1].value)} is current")


def provenance(after, before, cs, minted_bullets, edit):
    """A new entry is inferred until confirmed; an entry whose claims changed is too,
    unless the changeset said what it is (it may say anything but confirmed)."""
    stated = {s for s, p, _ in cs.add + cs.set if p.value == PROVENANCE}
    stated |= {b for b in minted_bullets if values(after, b, node(PROVENANCE))}
    inferred = node(O.J + "inferred")
    old = {s for s, _, _ in before}
    for s in sorted({s for s, _, _ in after}, key=lambda s: s.value):
        cls = O.BY_NAME[O.class_of(s.value)]
        if not cls.claims or s in stated:
            continue
        if s not in old:
            if not values(after, s, node(PROVENANCE)):
                after.add((s, node(PROVENANCE), inferred))
            continue
        claims = {p for p in cls.preds.values() if p.claim}

        def claimed(triples):
            return {(p, o) for t, p, o in triples if t == s and local(p) in {c.name for c in claims}}
        if claimed(before) != claimed(after):
            was = values(after, s, node(PROVENANCE))
            if was != {inferred}:
                after.difference_update({(s, node(PROVENANCE), o) for o in was})
                after.add((s, node(PROVENANCE), inferred))
                changed = sorted({curie(p.value) for p, _ in claimed(before) ^ claimed(after)})
                edit.notes.append(f"{curie(s.value)} is now inferred: {', '.join(changed)} changed")


def questions(after, before, today, taken, edit):
    """Every entry this change left inferred or unverified gets a question about it,
    unless one is already open - otherwise nothing asks for it to be confirmed."""
    import pyoxigraph as ox

    about, answered = node(O.J + "about"), node(O.J + "answered")
    unsure = {node(O.J + "inferred"), node(O.J + "needs-verification")}
    open_about = {o for q, p, o in after if p == about and not values(after, q, answered)}
    changed = {s for s, _, _ in before ^ after}
    minted = set()
    for s in sorted(changed, key=lambda s: s.value):
        if values(after, s, node(PROVENANCE)) & unsure and s not in open_about:
            q = node(mint_question(s.value, taken | minted))
            minted.add(q.value)
            after |= {(q, about, s), (q, node(O.J + "question"), ox.Literal(ask(after, s))),
                      (q, node(O.J + "asked"), date(today))}
            edit.notes.append(f"asked {curie(q.value)} about {curie(s.value)}")


def ask(after, s):
    """The question, ready to ask aloud."""
    def get(pred):
        found = values(after, s, node(O.J + pred))
        return next(iter(found)).value if found else None
    cls = O.class_of(s.value)
    if cls == "Achievement":
        return f"Is this bullet true as written: \"{get('text')}\"?"
    if cls == "MetricVersion":
        metric = next(iter(values(after, s, node(O.J + "of"))))
        subject = next((o.value for t, p, o in after if t == metric and local(p) == "subject"), "it")
        unit = next((o.value for t, p, o in after if t == metric and local(p) == "unit"), "")
        span = f"from {get('baseline')} to {get('value')}" if get("baseline") else get("value")
        return f"Is {span}{' ' + unit if unit else ''} right for {subject}?"
    return f"Is {curie(s.value)} right as now recorded?"
```

- [ ] **Step 4: Run them to see them pass**

Run: `python -m pytest tests/test_graph_edit.py -q`
Expected: PASS (24 tests). If `test_a_minted_id_is_never_one_already_used` fails on `..._event_latency_cut_again`, `taken` is missing the changeset's own ids - the bullet merged into the entry the changeset names.

- [ ] **Step 5: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/edit.py tests/test_graph_edit.py
git commit -m "feat(graph): a changeset merged - a changed claim is unconfirmed, a sent version never changes"
```

---

### Task 5: `jsk kb apply`

**Files:**
- Create: `src/jsk/graph/kbcli.py`
- Modify: `src/jsk/graph/ontology.py` and `src/jsk/graph/shapes.py` (the log may name concepts), `src/jsk/cli.py` (dispatch), `src/jsk/preflight.py` (modules), `plugins/jsk/skills/jsk/SKILL.md`, `docs/SCRIPTS.md`
- Test: `tests/test_graph_kbcli.py`

**Interfaces:**
- Consumes: Tasks 1-4 (`record.state/prepare/stamp/commit/RecordError`, `changeset.read/Refused`, `edit.apply`), `store.load(root, texts=...)`, `validate_urs.show`, `cliutil.wants_help/docstring_usage`, `writer.write`.
- Produces: `kbcli.main(argv=None) -> int`; `kbcli.VERBS` and the `@verb` decorator (`cmd_<name>(args, root) -> int`); `kbcli.find_root(start)`, `take(args, flag, value=False)`, `usage(message) -> 2`, `refuse(lines, fix=None) -> 1`, `show_findings(findings, title)`, `GUIDE`, `writable(store, allow=("clean",)) -> None|int`, `new_failures(before, after)`, `diff(old, new, name)`, `curies(iris)`, `write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None, content=True, dry_run=False, notes=()) -> int`. `jsk kb` dispatches through `cli.SIMPLE["kb"]`. Test base class `test_graph_kbcli.Workspace` (`self.kb(*args)`, `self.changeset(text)`, `self.edit_kb(old, new, logged=False)`, `self.old_layout()`, `self.loaded()`, `self.path(name)`) is extended by Tasks 6 and 7.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_kbcli.py`:

```python
"""`jsk kb`, end to end, on a copy of the fixture workspace."""
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES

from jsk import cli
from jsk.graph import record
from jsk.graph import store as S
from jsk.graph.io import sha256

BRAINDUMP = PFX + """
op:changeset op:base 2 ; op:summary "The payments project, from the 24 Sep braindump." .

op:add {
    k:prj_payments j:name "Payments platform" ; j:position k:pos_meridian_principal ;
        j:strength 4 ; j:recency 2025 ; j:uses c:kafka, c:payments ;
        j:headlineMetric k:met_settlement .
    [] j:project k:prj_payments ; j:rank 1 ;
        j:text "Cut settlement latency from 800 ms to 200 ms." ;
        j:cites k:met_settlement ; j:shows c:kafka .
    [] j:project k:prj_payments ; j:rank 2 ;
        j:text "Moved card payments onto the event backbone." ; j:shows c:payments .
    k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
    k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ;
        j:confidence j:reported .
    c:payments a j:Domain ; j:label "payments" .
}
"""


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root)

    def path(self, name):
        return Path(self.root) / name

    def changeset(self, text, name="changes.trig"):
        self.path(name).write_text(text, encoding="utf-8")
        return str(self.path(name))

    def kb(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue()

    def loaded(self):
        return S.load(self.root)

    def edit_kb(self, old, new, logged=False):
        """Change kb.ttl by hand. `logged`: and make log.ttl agree, as though jsk had
        written it - how a kb.ttl in an older jsk's layout looks."""
        kb = self.path("career/kb.ttl")
        text = kb.read_text(encoding="utf-8")
        self.assertIn(old, text)
        text = text.replace(old, new)
        kb.write_text(text, encoding="utf-8", newline="\n")
        if logged:
            log = self.path("career/log.ttl")
            log.write_text(log.read_text(encoding="utf-8").replace(
                record.last_entry(self.loaded().graph(record.LOG))[1], sha256(text)),
                encoding="utf-8", newline="\n")
        return text

    def old_layout(self):
        return self.edit_kb("# == Metrics\n\n", "# == Metrics\n\n\n", logged=True)


class Apply(Workspace):
    def test_a_braindump_becomes_a_valid_logged_record(self):
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.fails()], [])
        self.assertEqual(record.state(s).kind, "clean")
        self.assertEqual(record.state(s).log_revision, 3)
        for line in ("+k:prj_payments j:name \"Payments platform\" ;",
                     "+k:ach_payments_cut_settlement_latency j:project k:prj_payments ; j:rank 1 ;",
                     "+k:ach_payments_moved_card_payments j:project k:prj_payments ; j:rank 2 ;",
                     "+c:payments a j:Domain ; j:label \"payments\" .",
                     "minted   c:payments, k:ach_payments_cut_settlement_latency",
                     "r3 written: career/kb.ttl and career/log.ttl"):
            self.assertIn(line, out)
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn('j:summary "The payments project, from the 24 Sep braindump."', log)

    def test_applying_the_same_changeset_twice_changes_nothing_the_second_time(self):
        path = self.changeset(BRAINDUMP.replace("op:base 2 ; ", ""))
        self.assertEqual(self.kb("apply", path)[0], 0)
        # An agent that re-runs an apply it thought failed must not mint every bullet twice:
        # a new bullet with a live bullet's text, under the same project, is that bullet.
        code, out = self.kb("apply", path)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to change", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 3)

    def test_an_old_application_s_fault_does_not_block_the_career(self):
        posting = self.path("applications/acme-platform-engineer/posting.ttl")
        posting.write_text(posting.read_text(encoding="utf-8").replace(
            "Deep, hands-on K8s experience in production", "Ten years of K8s"), encoding="utf-8")
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 0, out)

    def test_a_label_that_clashes_is_a_warning_not_a_refusal(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { c:payments a j:Domain ; j:label "Kafka" . }\n'))
        self.assertEqual(code, 0, out)

    def test_both_files_restored_together_are_clean(self):
        kb, log = self.path("career/kb.ttl"), self.path("career/log.ttl")
        old = (kb.read_bytes(), log.read_bytes())
        self.kb("apply", self.changeset(BRAINDUMP))
        kb.write_bytes(old[0])
        log.write_bytes(old[1])
        self.assertEqual(record.state(self.loaded()).kind, "clean")

    def test_a_dry_run_writes_nothing(self):
        kb = self.path("career/kb.ttl")
        before = (kb.read_bytes(), os.stat(kb).st_mtime_ns)
        code, out = self.kb("apply", self.changeset(BRAINDUMP), "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("+k:prj_payments", out)
        self.assertIn("dry run: r3 not written", out)
        self.assertEqual((kb.read_bytes(), os.stat(kb).st_mtime_ns), before)
        self.assertFalse(self.path(".jsk").exists())

    def test_stdin_is_refused(self):
        code, out = self.kb("apply", "-")
        self.assertEqual(code, 2)
        self.assertIn("stdin is refused", out)

    def test_a_hand_edit_is_adopted_before_anything_is_applied(self):
        kb = self.path("career/kb.ttl")
        kb.write_text(kb.read_text(encoding="utf-8").replace('"1001-5000"', '"5001-10000"'),
                      encoding="utf-8", newline="\n")
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 1)
        self.assertIn("jsk kb adopt", out)

    def test_a_change_that_breaks_the_record_is_refused_whole(self):
        before = self.path("career/kb.ttl").read_bytes()
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:add { k:prj_half j:name "Half a project" . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("j:strength is required", out)
        self.assertEqual(self.path("career/kb.ttl").read_bytes(), before)

    def test_a_refusal_names_every_reason(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:provenance j:confirmed ; j:strenght 4 . }\n'))
        self.assertEqual(code, 1)
        self.assertIn("a changeset cannot confirm", out)
        self.assertIn("did you mean j:strength?", out)

    def test_nothing_to_change_writes_nothing(self):
        code, out = self.kb("apply", self.changeset(
            PFX + 'op:set { k:prj_clinical_events j:strength 5 . }\n'))
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))
        self.assertIn("nothing to change", out)

    def test_a_non_canonical_kb_is_formatted_first(self):
        self.old_layout()
        code, out = self.kb("apply", self.changeset(BRAINDUMP))
        self.assertEqual(code, 1)
        self.assertIn("jsk kb fmt", out)

    def test_a_changeset_that_is_not_trig(self):
        code, out = self.kb("apply", self.changeset("x", "changes.ttl"))
        self.assertEqual(code, 2)


class Dispatch(Workspace):
    def test_help_lists_the_verbs_and_exits_0(self):
        code, out = self.kb("--help")
        self.assertEqual(code, 0)
        self.assertIn("apply <changeset.trig>", out)

    def test_a_verb_s_help(self):
        code, out = self.kb("apply", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--dry-run prints the diff", out)

    def test_an_unknown_verb(self):
        code, out = self.kb("aply")
        self.assertEqual(code, 2)
        self.assertIn("unknown verb: aply", out)

    def test_the_workspace_is_found_from_inside_it(self):
        here = os.getcwd()
        os.chdir(self.path("applications"))
        self.addCleanup(os.chdir, here)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["jsk", "kb", "apply", self.changeset(BRAINDUMP), "--dry-run"])
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: FAIL - every test: `unknown command: kb` (exit 2 where 0 or 1 was expected).

- [ ] **Step 3: kbcli.py with `apply`**

The `write_logged` fix line holds `\n`: write the file with the Write tool.

```python
"""jsk kb - the career record: changed through changesets, read by id.

Usage: jsk kb <verb> [arguments] [--root DIR]

  apply <changeset.trig> [--dry-run]   merge a changeset into career/kb.ttl; prints the diff

--root is the workspace, the folder holding career/; by default the nearest one above
the current directory. `jsk kb <verb> --help` says more about one verb.

Every write goes through the same gate: the workspace validates, kb.ttl is exactly what
the log last recorded (a hand edit is adopted first, so it is logged as one), and the
record it would write validates too. Then kb.ttl, then log.ttl, and the diff.

Exit 0 done (or nothing to do), 1 refused, 2 called wrong.
"""
import datetime
import difflib
import inspect
import os
import sys

from ..cliutil import docstring_usage, wants_help

VERBS = {}


def verb(fn):
    VERBS[fn.__name__.removeprefix("cmd_")] = fn
    return fn


def find_root(start):
    """The nearest folder at or above `start` holding career/kb.ttl, or None."""
    here = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(here, "career", "kb.ttl")):
            return here
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def take(args, flag, value=False):
    """Remove `flag` (and its value) from args; the value, True, or None."""
    if flag not in args:
        return None
    at = args.index(flag)
    if not value:
        del args[at]
        return True
    if at + 1 >= len(args):
        raise SystemExit(usage(f"{flag} needs a value"))
    found = args[at + 1]
    del args[at:at + 2]
    return found


def usage(message):
    print(message)
    print("usage: jsk kb <verb> [arguments] [--root DIR] - `jsk kb --help` lists the verbs")
    return 2


def refuse(lines, fix=None):
    """Print why nothing was written. Returns the exit code."""
    for line in lines:
        print(f"REFUSED  {line}")
    if fix:
        print(f"        fix: {fix}")
    print("nothing was written")
    return 1


def show_findings(findings, title):
    from ..gates.validate_urs import show
    from . import store as S

    rep = S.Store("", findings=findings).report()
    print(title)
    show(rep.fails, "FAIL", 25)


GUIDE = {
    "unlogged": ("career/kb.ttl has no log yet", "run `jsk kb adopt` to start log.ttl from it"),
    "hand-edited": (None, "run `jsk kb adopt` first, so the hand edit is logged as one"),
    "torn": (None, "run `jsk kb adopt`: it logs the write that did not reach log.ttl"),
    "out-of-sync": (None, "restore the file that went back on its own, or `jsk kb adopt`"),
    "missing": ("there is no career/kb.ttl", "run `jsk migrate` or `jsk new`"),
    "unreadable": ("career/kb.ttl or career/log.ttl does not parse", "`jsk kb check` shows where"),
}


def writable(store, allow=("clean",)):
    """None when the record may be written; otherwise the exit code of a refusal."""
    from . import record as R
    from .writer import write

    blocking = [f for f in store.fails() if f.rule not in ("log-sync",)
                and (not f.file.startswith("applications/") or f.rule == "syntax")]
    if blocking:
        show_findings(blocking, f"REFUSED  the career has {len(blocking)} failures - fix them first:")
        print("nothing was written")
        return 1
    st = R.state(store)
    if st.kind not in allow:
        message, fix = GUIDE[st.kind]
        return refuse([message or st.detail], fix)
    if st.kind == "clean" and write(store.graph(R.KB), "kb") != store.parsed[R.KB].text:
        return refuse(["career/kb.ttl is not in the canonical layout this jsk writes"],
                      "run `jsk kb fmt` - a reformat is logged on its own, so no change hides in it")
    return None


def key(f):
    return (f.rule, f.file, f.focus, f.detail)


def new_failures(before, after):
    """What a write would break: any FAIL in the career or the vocabulary, and a FAIL
    anywhere that was not already there - an old application's fault is not this one's."""
    had = {key(f) for f in before.fails()}
    return [f for f in after.fails() if not f.file.startswith("applications/") or key(f) not in had]


def diff(old, new, name="career/kb.ttl"):
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        f"a/{name}", f"b/{name}"))


def curies(iris):
    from .writer import curie
    return ", ".join(curie(i) for i in sorted(iris))


def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
                 content=True, dry_run=False, notes=()):
    """Stamp, validate, print and - unless a dry run - write. Returns the exit code."""
    from . import record as R
    from . import store as S
    from .io import parse_text

    today = datetime.date.today()
    rev, kb_text, log_text = R.prepare(store, quads, today, by, summary, touched, minted,
                                       answer, content)
    # gofmt's promise, checked every time: what was written parses back to what was meant.
    if set(parse_text(kb_text, R.KB).quads) != set(R.stamp(quads, rev, today, content)):
        return refuse(["the writer did not reproduce the record it was given - a jsk bug"],
                      "report it; kb.ttl is untouched")
    after = S.load(root, texts={R.KB: kb_text, R.LOG: log_text})
    broken = new_failures(store, after)
    if broken:
        show_findings(broken, f"REFUSED  the change would leave {len(broken)} failures:")
        print("nothing was written")
        return 1
    print(diff(store.parsed[R.KB].text, kb_text), end="")
    for label, ids in (("minted", minted), ("touched", touched)):
        if ids:
            print(f"{label:8} {curies(ids)}")
    for note in notes:
        print(f"note     {note}")
    if dry_run:
        print(f"dry run: r{rev} not written")
        return 0
    try:
        R.commit(root, kb_text, log_text)
    except R.RecordError as e:
        print(f"FAIL  {e}\n        fix: {e.fix}")
        return 1
    print(f"r{rev} written: career/kb.ttl and career/log.ttl")
    return 0


@verb
def cmd_apply(args, root):
    """jsk kb apply <changeset.trig> [--dry-run]

    Merges a changeset (op:add, op:set, op:retire, op:delete; see docs/SCRIPTS.md) into
    career/kb.ttl, then logs it. A changed claim drops to j:inferred and is asked about; a
    new bullet gets its id; a sent metric version gets a successor instead of a change.
    --dry-run prints the diff and writes nothing.
    """
    from . import changeset, edit
    from . import store as S
    from .io import GraphError

    dry = bool(take(args, "--dry-run"))
    if len(args) != 1:
        return usage("jsk kb apply takes one changeset")
    path = args[0]
    if path == "-":
        return usage("a changeset is a file: write it to changes.trig and pass that path - "
                     "stdin is refused, because a pipe that never closes hangs the command")
    if not path.endswith(".trig") or not os.path.isfile(path):
        return usage(f"{path}: not a .trig file")
    store = S.load(root)
    code = writable(store)
    if code is not None:
        return code
    try:
        with open(path, encoding="utf-8") as fh:
            cs = changeset.read(fh.read(), os.path.basename(path))
        e = edit.apply(store, cs, datetime.date.today())
    except GraphError as err:
        return refuse([str(err)], err.fix)
    except changeset.Refused as err:
        return refuse([r.text() for r in err.refusals])
    if not e.touched and not e.minted:
        print("nothing to change: the record already says all of that")
        return 0
    summary = cs.summary or (f"Applied {os.path.basename(path)}: {len(e.minted)} added, "
                             f"{len(e.touched)} changed.")
    return write_logged(store, root, e.quads, "apply", summary, e.touched, e.minted,
                        dry_run=dry, notes=e.notes)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (wants_help(args) and args[0] not in VERBS):
        print(docstring_usage(__doc__))
        return 0 if args else 2
    name, rest = args[0], args[1:]
    if name not in VERBS:
        return usage(f"unknown verb: {name} - one of {', '.join(VERBS)}")
    if wants_help(rest):
        print(inspect.cleandoc(VERBS[name].__doc__))
        return 0
    try:
        root = take(rest, "--root", value=True) or find_root(os.getcwd())
    except SystemExit as e:
        return e.code
    if root is None or not os.path.isdir(root):
        return usage("no workspace here: run it inside one, or pass --root DIR "
                     "(the folder holding career/)")
    try:
        import pyoxigraph  # noqa: F401
    except ImportError:
        print("FAIL  jsk kb needs pyoxigraph, and this Python has not got it - "
              "`jsk doctor` says how to install it")
        return 1
    try:
        return VERBS[name](rest, os.path.abspath(root))
    except SystemExit as e:
        return e.code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Dispatch it (cli.py) and list the modules (preflight.py)**

```diff
--- a/src/jsk/cli.py
+++ b/src/jsk/cli.py
@@ -15,6 +15,7 @@ will be. This exists so that nobody has to remember every name to get started.
     jsk new PATH --name NAME    scaffold user-knowledgebase.md and applications/
     jsk index KB [--rank POST]  a line-pointing overview of the knowledge base, ranked
     jsk match POSTING.ttl       a posting against the graph record, through the vocabulary
+    jsk kb VERB [...]           the graph record: apply a changeset, confirm, show, check
     jsk validate RECORD.json    the record gate, before anything renders
     jsk render RECORD [...]     one record to a PDF and plain text
     jsk preview RECORD --out D  the same record in every template, to pick a look
@@ -52,6 +53,7 @@ SIMPLE = {
     "new": ("kb.py", "scaffold an empty knowledge base"),
     "index": ("kbindex.py", "overview the knowledge base; rank it against a posting"),
     "match": ("match.py", "a posting matched against the graph record, through the vocabulary"),
+    "kb": ("kbcli.py", "the graph record: changed through changesets, read by id"),
     "render": ("render_resume.py", "one record to .tex/PDF plus .txt"),
     "preview": ("preview_templates.py", "one record in every template, side by side"),
     "fit": ("fit_pages.py", "fit a render to a page budget"),
@@ -104,6 +106,7 @@ SUBPACKAGE = {
     "check_prose.py": "gates",
     "validate_urs.py": "gates",
     "match.py": "graph",
+    "kbcli.py": "graph",
 }
 
 
```

```diff
--- a/src/jsk/preflight.py
+++ b/src/jsk/preflight.py
@@ -47,7 +47,8 @@ MODULES = ["cli", "cliutil", "kb", "kbindex", "paths"]
 # these imports pyoxigraph at module top, so find_spec answers "is the code here" even on
 # a machine without the engine - the engine is its own check below.
 GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer", "graph.shapes",
-                 "graph.rules", "graph.store", "graph.queries", "graph.match"]
+                 "graph.rules", "graph.store", "graph.queries", "graph.match", "graph.record",
+                 "graph.changeset", "graph.edit", "graph.kbcli"]
 GATE_MODULES = ["gates", "gates.check_ats", "gates.check_prose", "gates.validate_urs"]
 # Rendering, the preview and the page fitter moved in here: they drive the
 # record->document pipeline and import nothing else, so a broken urs package takes all
```

- [ ] **Step 5: Run the tests - one still fails, on the log's own shape**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: FAIL in the six tests whose changeset adds a concept (`c:payments`), each with

```
REFUSED  the change would leave 1 failures:
  FAIL  career/log.ttl:18 k:rev_3 - j:minted c:payments is not a k: id
```

The changeset adds a concept, and `j:minted` accepted only `k:` ids. That is Ruling 15.

- [ ] **Step 6: The log may name concepts (ontology.py, shapes.py)**

```diff
--- a/src/jsk/graph/ontology.py
+++ b/src/jsk/graph/ontology.py
@@ -52,7 +52,8 @@ class Enum:
 @dataclass(frozen=True)
 class Ref:
     """A k: id of one of these classes; "*" is any class. `may_dangle` for the log,
-    whose entries name ids that may since have been deleted."""
+    whose entries name ids that may since have been deleted - and concepts, since a
+    change to the person's vocabulary is a change to the career like any other."""
     classes: tuple
     may_dangle: bool = False
 
```

```diff
--- a/src/jsk/graph/shapes.py
+++ b/src/jsk/graph/shapes.py
@@ -205,7 +205,7 @@ def check_object(pred, o):
         return None if o.value.startswith(O.C) else f"{curie(o.value)} is not a c: concept"
     if isinstance(kind, O.Ref):
         target = O.class_of(o.value)
-        if target is None or target == "Concept":
+        if target is None or (target == "Concept" and not kind.may_dangle):
             return f"{curie(o.value)} is not a k: id"
         if kind.classes != O.ANY and target not in kind.classes:
             return f"{curie(o.value)} is a {target}; expected {' or '.join(kind.classes)}"
```

- [ ] **Step 7: Run them to see them pass**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: PASS (17 tests).

- [ ] **Step 8: The surface tests want `jsk kb` documented**

Run: `python -m pytest tests/test_plugin_surface.py -q`
Expected: FAIL - `test_SKILL_md_names_every_subcommand` (`SKILL.md does not name: ['kb']`) and `test_the_scripts_page_lists_every_subcommand`.

SKILL.md gains its row by trimming two lines (Ruling 17). Use the Edit tool; do not `sed` a table row (`\|` is alternation to sed):

````diff
--- a/plugins/jsk/skills/jsk/SKILL.md
+++ b/plugins/jsk/skills/jsk/SKILL.md
@@ -1,163 +1,164 @@
----
-name: jsk
-description: >-
-  Use when the user wants to write, rebuild, update or tailor a resume or CV; capture work history,
-  projects or accomplishments; record something they shipped; prepare a job application or paste a
-  job description; check whether a resume will survive applicant tracking systems (ATS); resolve
-  gaps or missing metrics in their career records; says their resume is outdated or vague; describes
-  their work in long unstructured messages; wants a periodic career review; or asks about a career
-  knowledge base, brag document or resume framework.
-license: MIT
----
-
-# Job Seeker Skill
-
-A career knowledge base in **one Markdown file**, `user-knowledgebase.md`, plus a toolchain that
-renders verified, ATS-safe resumes from it. Interview someone once; regenerate resumes, tailored
-variants and interview briefs from the file forever after.
-
-**The knowledge base is the source of truth. A resume is one rendering of it.**
-
-```
-user-knowledgebase.md  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
-   you read and edit it     you write it        \-> .txt          (paste-in boxes)
-```
-
-**Never hand-author a `.tex`.** Write the URS record, validate it, render every format from it —
-two hand-built documents stop agreeing the moment one is edited.
-
-| Thing | Is | Written by |
-|---|---|---|
-| `user-knowledgebase.md` | the source of truth | the person, and you |
-| `applications/<stem>/posting.md` | the advertisement verbatim, plus its requirements | `jsk-tailor-analyst` |
-| `applications/<stem>/gaps.md` | verdicts, shortfalls and the question queue | `jsk-tailor-analyst` |
-| `applications/<stem>/resume.json` | the URS record for this posting | `jsk-resume-author` |
-| `applications/<stem>/application.md` | what was sent, and its timeline | `jsk freeze` |
-
-`applications/` is the directory beside `user-knowledgebase.md` — resolve it to an absolute path,
-never the working directory.
-
-## Modes
-
-Route on the argument if one was passed, otherwise on the message. Ambiguous? Ask — the modes do
-different things.
-
-| Mode | Trigger | Read |
-|---|---|---|
-| **setup** | no knowledge base, an older bundle, or "set this up" | `references/mode-setup.md` |
-| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
-| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
-| **tailor** | a job description or URL; "customise for this role" | `references/mode-tailor.md` |
-| **ship** | a finished record needs rendering, gating, freezing and logging | `references/mode-ship.md` |
-| **refresh** | "update my knowledge base", quarterly review, got promoted | `references/mode-refresh.md` |
-| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
-| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |
-
-## Every session, first
-
-1. **Find the knowledge base** — search the working directory and connected folders for
-   `user-knowledgebase.md`, or run `jsk doctor`. Sessions share no state; never assume one exists.
-   Read it **whole**: skimming is how a project gets recorded twice.
-2. **None?** Switch to setup — unless they asked for something deliverable anyway. Deliver it first,
-   then offer to capture it. Setup never blocks the actual ask.
-3. **A `projects/` + `resume-generation/` directory** is the old bundle format. Offer the migration in
-   `references/mode-setup.md`; never run it unasked.
-4. **`rules/*.md` beside the knowledge base** override `references/` here.
-5. **Run `jsk --version`** before the first call. Not found → `python3 -m jsk` (`python` or `py -3`
-   on Windows). Neither → say so and stop.
-
-## Editing the knowledge base
-
-There is no write layer: use `Read`, `Edit` and `Write` on the file. Three habits carry what a write
-command would have enforced:
-
-- **Read the section before writing into it.**
-- **Grep a distinctive phrase before adding anything.** People re-tell the same work months apart in
-  different words; two entries for one project split its evidence so neither reads as strong.
-- **Stamp what you inferred** (see Provenance).
-
-`references/kb-spec.md` has the headings, block shapes and ids — for cases the mode file does not
-already cover.
-
-## The `jsk` command
-
-It reads records and rendered files, never `user-knowledgebase.md`. `jsk --help` is the full surface.
-
-| Command | Does |
-|---|---|
-| `jsk doctor [--quick]` | what this machine can do and what each gap disables |
-| `jsk new <path> --name "Name"` | an empty `user-knowledgebase.md` and `applications/` |
-| `jsk index <kb> [--rank <posting.md>]` | every section and entry with its lines; the ranking, computed |
-| `jsk match <posting.ttl>` | a posting matched through the vocabulary |
-| `jsk validate <resume.json>` | the record gate |
-| `jsk render <resume.json> --out DIR --view ID --pdf [--ats-max] [--template N]` | record to `.tex`/PDF and `.txt` |
-| `jsk preview <resume.json> --out DIR` | every template, with page counts |
-| `jsk check <file> [--strict] [--only parse\|prose]` | the parse and prose gates on one file |
-| `jsk gates <out-dir> [--record R] [--pages N]` | record, parse and prose gates together |
-| `jsk ship <resume.json> --out DIR --view ID [--pages N]` | validate, render and gates; stops at the first failure |
-| `jsk fit <resume.tex> --target-pages 2` | fits the render to a page budget |
-| `jsk freeze <app-dir> --submitted DATE\|false --channel TEXT` | refuses unless the gates pass, then writes `application.md` |
-
-Exit codes: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are required — the
-PDF is the only deliverable. A missing input is `SKIPPED` **and** a failure.
-
-## Agents
-
-| Agent | Hand it | Get back |
-|---|---|---|
-| `jsk-tailor-analyst` | posting, knowledge base path | requirements, ranking, `gaps.md` and its question queue |
-| `jsk-resume-author` | posting, gaps, knowledge base path | `resume.json`, every authored clause quoted |
-| `jsk-kb-auditor` | knowledge base path | what is missing, as a prioritised question queue |
-| `jsk-verifier` | a **failed** gate, or the render gate to read | each verdict verbatim, and where the defect is repaired |
-
-**They never interview**: confirming claims, choosing between close projects and telling someone
-where they fall short stay with you and the person. Their output does not reach the person, so
-**relay the evidence verbatim** rather than summarising it. No agents available? Run the mode file's
-procedure inline.
-
-## The four gates
-
-**Never hand over a resume you have not checked.** Passing one gate says nothing about the others.
-
-| Gate | Question | How |
-|---|---|---|
-| **Record** | coherent, shaped right, every number traced to a metric? | `jsk validate` — the only thing that sees a key the renderer ignores |
-| **Parse** | will an ATS read it? | `jsk check` on the PDF; `--strict` on the `.txt` |
-| **Prose** | does it obey the writing rules? | `jsk check --only prose` on the `.tex` |
-| **Render** | does it look right, and is it true? | open every page of the PDF |
-
-The first three are `jsk gates` (or `jsk ship`). **Show the output**; fix and re-run, never explain a
-failure away. The render gate is half yours: you can check the layout, only the person can confirm
-it is true — until they have, the resume is unverified. No PDF renderer → say so and mark it
-unverified. Repair a defect in the knowledge base or record and re-render; never patch the PDF.
-
-## Provenance
-
-Every claim carries `status`: `confirmed` (they said it, or a source document does), `inferred`
-(you wrote it), or `needs-verification` (a known gap).
-
-- **Never let `inferred` content reach a resume unconfirmed.** It reads well and is indefensible in
-  interview.
-- **Write `confirmed` only for what they actually said.** When you change a claim's substance, drop
-  it back to `inferred` and add a row to `## Open questions`.
-- **Never invent a credential**, or call one "in progress", unless they said so.
-- **Never hide text or add a term they cannot defend.** `references/ats-rules.md` has the boundary.
-
-## Working with people
-
-- **Let them ramble**, then structure it. Adapt the vocabulary to what they know.
-- **Push for a number twice, then let go** — write the bullet true without it and log the gap. Never
-  leave a placeholder in a document they might send.
-- **Say why**, flag every inference, and offer options with a recommendation.
-- **Tell them where they fall short.** Being flattered costs interviews.
-- **Append a dated row to `log.md`**, beside the knowledge base, at the end of every session. Record your own earlier mistakes as
-  corrections, never as edits.
-
-Save deliverables beside the knowledge base (Claude Code) or in the outputs folder (Cowork), and
-tell them the path.
-
-## References, on demand
-
-Formats: `kb-spec.md` (the knowledge base), `urs-spec.md` and `view-format.md` (the record, in two
-halves). Rules: `writing-rules.md`, `ats-rules.md`, `templates.md`. `rationale.md` explains why any
-rule exists, for when someone asks.
+---
+name: jsk
+description: >-
+  Use when the user wants to write, rebuild, update or tailor a resume or CV; capture work history,
+  projects or accomplishments; record something they shipped; prepare a job application or paste a
+  job description; check whether a resume will survive applicant tracking systems (ATS); resolve
+  gaps or missing metrics in their career records; says their resume is outdated or vague; describes
+  their work in long unstructured messages; wants a periodic career review; or asks about a career
+  knowledge base, brag document or resume framework.
+license: MIT
+---
+
+# Job Seeker Skill
+
+A career knowledge base in **one Markdown file**, `user-knowledgebase.md`, plus a toolchain that
+renders verified, ATS-safe resumes from it. Interview someone once; regenerate resumes, tailored
+variants and interview briefs from the file forever after.
+
+**The knowledge base is the source of truth. A resume is one rendering of it.**
+
+```
+user-knowledgebase.md  ->  resume.json (URS)  ->  .tex -> .pdf   (the deliverable)
+   you read and edit it     you write it        \-> .txt          (paste-in boxes)
+```
+
+**Never hand-author a `.tex`.** Write the URS record, validate it, render every format from it —
+two hand-built documents stop agreeing the moment one is edited.
+
+| Thing | Is | Written by |
+|---|---|---|
+| `user-knowledgebase.md` | the source of truth | the person, and you |
+| `applications/<stem>/posting.md` | the advertisement verbatim, plus its requirements | `jsk-tailor-analyst` |
+| `applications/<stem>/gaps.md` | verdicts, shortfalls and the question queue | `jsk-tailor-analyst` |
+| `applications/<stem>/resume.json` | the URS record for this posting | `jsk-resume-author` |
+| `applications/<stem>/application.md` | what was sent, and its timeline | `jsk freeze` |
+
+`applications/` is the directory beside `user-knowledgebase.md` — resolve it to an absolute path,
+never the working directory.
+
+## Modes
+
+Route on the argument if one was passed, otherwise on the message. Ambiguous? Ask — the modes do
+different things.
+
+| Mode | Trigger | Read |
+|---|---|---|
+| **setup** | no knowledge base, an older bundle, or "set this up" | `references/mode-setup.md` |
+| **braindump** | telling you about their work; long unstructured messages | `references/mode-braindump.md` |
+| **resume** | "build my resume", "is this ATS-safe" | `references/mode-resume.md` |
+| **tailor** | a job description or URL; "customise for this role" | `references/mode-tailor.md` |
+| **ship** | a finished record needs rendering, gating, freezing and logging | `references/mode-ship.md` |
+| **refresh** | "update my knowledge base", quarterly review, got promoted | `references/mode-refresh.md` |
+| **gaps** | "what's missing", "resume feels vague", verify before applying | `references/mode-gaps.md` |
+| **pipeline** | "what do I chase", "where are my applications", weekly review | `references/mode-pipeline.md` |
+
+## Every session, first
+
+1. **Find the knowledge base** — search the working directory and connected folders for
+   `user-knowledgebase.md`, or run `jsk doctor`. Sessions share no state; never assume one exists.
+   Read it **whole**: skimming is how a project gets recorded twice.
+2. **None?** Switch to setup — unless they asked for something deliverable anyway. Deliver it first,
+   then offer to capture it. Setup never blocks the actual ask.
+3. **A `projects/` + `resume-generation/` directory** is the old bundle format. Offer the migration in
+   `references/mode-setup.md`; never run it unasked.
+4. **`rules/*.md` beside the knowledge base** override `references/` here.
+5. **Run `jsk --version`** before the first call. Not found → `python3 -m jsk` (`python` or `py -3`
+   on Windows). Neither → say so and stop.
+
+## Editing the knowledge base
+
+There is no write layer: use `Read`, `Edit` and `Write` on the file. Three habits carry what a write
+command would have enforced:
+
+- **Read the section before writing into it.**
+- **Grep a distinctive phrase before adding anything.** People re-tell the same work months apart in
+  different words; two entries for one project split its evidence so neither reads as strong.
+- **Stamp what you inferred** (see Provenance).
+
+`references/kb-spec.md` has the headings, block shapes and ids — for cases the mode file does not
+already cover.
+
+## The `jsk` command
+
+It never edits `user-knowledgebase.md`; `jsk --help` is the full surface.
+
+| Command | Does |
+|---|---|
+| `jsk doctor [--quick]` | what this machine can do and what each gap disables |
+| `jsk new <path> --name "Name"` | an empty `user-knowledgebase.md` and `applications/` |
+| `jsk index <kb> [--rank <posting.md>]` | every entry with its lines, and the ranking |
+| `jsk match <posting.ttl>` | a posting matched through the vocabulary |
+| `jsk kb <verb>` | the graph record, changed and read |
+| `jsk validate <resume.json>` | the record gate |
+| `jsk render <resume.json> --out DIR --view ID --pdf [--ats-max] [--template N]` | record to `.tex`/PDF and `.txt` |
+| `jsk preview <resume.json> --out DIR` | every template, with page counts |
+| `jsk check <file> [--strict] [--only parse\|prose]` | the parse and prose gates on one file |
+| `jsk gates <out-dir> [--record R] [--pages N]` | record, parse and prose gates together |
+| `jsk ship <resume.json> --out DIR --view ID [--pages N]` | validate, render and gates; stops at the first failure |
+| `jsk fit <resume.tex> --target-pages 2` | fits the render to a page budget |
+| `jsk freeze <app-dir> --submitted DATE\|false --channel TEXT` | refuses unless the gates pass, then writes `application.md` |
+
+Exit codes: `0` passed, `1` failed, `2` called wrong. A TeX engine and `pymupdf` are required — the
+PDF is the only deliverable. A missing input is `SKIPPED` **and** a failure.
+
+## Agents
+
+| Agent | Hand it | Get back |
+|---|---|---|
+| `jsk-tailor-analyst` | posting, knowledge base path | requirements, ranking, `gaps.md` and its question queue |
+| `jsk-resume-author` | posting, gaps, knowledge base path | `resume.json`, every authored clause quoted |
+| `jsk-kb-auditor` | knowledge base path | what is missing, as a prioritised question queue |
+| `jsk-verifier` | a **failed** gate, or the render gate to read | each verdict verbatim, and where the defect is repaired |
+
+**They never interview**: confirming claims, choosing between close projects and telling someone
+where they fall short stay with you and the person. Their output does not reach the person, so
+**relay the evidence verbatim** rather than summarising it. No agents available? Run the mode file's
+procedure inline.
+
+## The four gates
+
+**Never hand over a resume you have not checked.** Passing one gate says nothing about the others.
+
+| Gate | Question | How |
+|---|---|---|
+| **Record** | coherent, shaped right, every number traced to a metric? | `jsk validate` — the only thing that sees a key the renderer ignores |
+| **Parse** | will an ATS read it? | `jsk check` on the PDF; `--strict` on the `.txt` |
+| **Prose** | does it obey the writing rules? | `jsk check --only prose` on the `.tex` |
+| **Render** | does it look right, and is it true? | open every page of the PDF |
+
+The first three are `jsk gates` (or `jsk ship`). **Show the output**; fix and re-run, never explain a
+failure away. The render gate is half yours: you can check the layout, only the person can confirm
+it is true — until they have, the resume is unverified. No PDF renderer → say so and mark it
+unverified. Repair a defect in the knowledge base or record and re-render; never patch the PDF.
+
+## Provenance
+
+Every claim carries `status`: `confirmed` (they said it, or a source document does), `inferred`
+(you wrote it), or `needs-verification` (a known gap).
+
+- **Never let `inferred` content reach a resume unconfirmed.** It reads well and is indefensible in
+  interview.
+- **Write `confirmed` only for what they actually said.** When you change a claim's substance, drop
+  it back to `inferred` and add a row to `## Open questions`.
+- **Never invent a credential**, or call one "in progress", unless they said so.
+- **Never hide text or add a term they cannot defend.** `references/ats-rules.md` has the boundary.
+
+## Working with people
+
+- **Let them ramble**, then structure it. Adapt the vocabulary to what they know.
+- **Push for a number twice, then let go** — write the bullet true without it and log the gap. Never
+  leave a placeholder in a document they might send.
+- **Say why**, flag every inference, and offer options with a recommendation.
+- **Tell them where they fall short.** Being flattered costs interviews.
+- **Append a dated row to `log.md`**, beside the knowledge base, at the end of every session. Record your own earlier mistakes as
+  corrections, never as edits.
+
+Save deliverables beside the knowledge base (Claude Code) or in the outputs folder (Cowork), and
+tell them the path.
+
+## References, on demand
+
+Formats: `kb-spec.md` (the knowledge base), `urs-spec.md` and `view-format.md` (the record, in two
+halves). Rules: `writing-rules.md`, `ats-rules.md`, `templates.md`. `rationale.md` explains why any
+rule exists, for when someone asks.
````

docs/SCRIPTS.md - the surface line, and a `jsk kb` section after `jsk match`'s:

````diff
--- a/docs/SCRIPTS.md
+++ b/docs/SCRIPTS.md
@@ -1,481 +1,531 @@
-# Commands
-
-The skill runs these for you. This page is for running them yourself.
-
-It is all one command. `pip install 'jsk-resume[all]'` puts `jsk` on your PATH; `python3 -m jsk` is
-the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
-in place of `python3`.
-
-Every subcommand below also exists as a module you can run or import directly —
-`python3 -m jsk.gates.check_ats resume.pdf`, `from jsk.urs import plan`. The headings name both.
-
-**Nothing here reads `user-knowledgebase.md`.** That file is Markdown a person and the skill edit
-with ordinary tools; this toolchain starts at the URS record written out of it, and carries it to a
-document somebody can send.
-
-## The whole surface
-
-```bash
-jsk doctor                       # what works on this machine
-jsk new ./my-career --name "Your Name"
-jsk index user-knowledgebase.md --rank applications/<dir>/posting.md
-jsk match applications/<dir>/posting.ttl   # the same question, over the graph record
-jsk validate resume.json         # the record gate
-jsk render resume.json --out . --view view_default --pdf
-jsk check resume.pdf             # both document gates, one pass
-jsk gates .                      # all three mechanical gates
-jsk fit resume.tex --target-pages 2
-jsk preview resume.json --out ./looks
-jsk ship resume.json --out . --view view_default   # validate, render, gate
-jsk freeze applications/<dir> --submitted 2026-09-08 --channel "Workday portal"
-```
-
-Each subcommand calls the module documented below it, in the same interpreter, with the same
-arguments and the same exit code, so everything on this page is true through `jsk`. None of them
-spawns a Python child: that cost a start-up and a fresh import per call, which was most of the wall
-time of `jsk check`. The one exception is `jsk doctor`'s end-to-end run, which runs each module as
-`python -m` on purpose — proving that entry point works from cold is what it is for.
-
-## Exit codes
-
-Uniform across every subcommand:
-
-| Code | Means |
-|---|---|
-| `0` | passed |
-| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
-| `2` | you called it wrong — bad usage, or a file that is not there |
-
-Nothing here passes quietly when it could not do its job. A page count nobody measured is a page
-count nobody knows.
-
-## Start here
-
-### `jsk doctor`
-
-The `jsk.preflight` module.
-
-```bash
-jsk doctor                 # verifies end to end
-jsk doctor --quick         # skip the render
-jsk doctor --json          # machine-readable
-jsk doctor --kb PATH       # check a specific user-knowledgebase.md
-```
-
-Bare `jsk doctor` renders the shipped example document and runs the parse and prose gates on the
-result, so a pass means the pipeline genuinely works here rather than looking like it should.
-
-Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
-is present but failed its own gates — that is a bug in the skill, not in your setup).
-
-Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
-that needs installing first is not a preflight.
-
-Without `--kb` it searches for `user-knowledgebase.md` three directories down. Searching by filename
-rather than by a directory shape is deliberate — a bundle used to be recognised by the folders inside
-it, so a half-created one was invisible here and reported as absent while the person was looking
-straight at it.
-
-### `jsk new`
-
-The `jsk.kb` module.
-
-```bash
-jsk new ./my-career --name "Your Name"
-jsk new ./my-career --name "Your Name" --force   # overwrite an existing file
-```
-
-Writes `user-knowledgebase.md` with every heading present and empty, plus `log.md` and an
-`applications/` directory beside it. No dependencies. It refuses rather than overwriting, because the
-file it would replace is somebody's career; `--force` replaces the knowledge base but never an
-existing `log.md`.
-
-What each heading is for is written into the file itself, as HTML comments beneath each one.
-Guidance in a template a person is looking at gets read; guidance in a specification they have to go
-and find does not.
-
-### `jsk index`
-
-The `jsk.kbindex` module.
-
-```bash
-jsk index user-knowledgebase.md                          # the overview
-jsk index user-knowledgebase.md --rank posting.md        # plus the ranking and coverage
-jsk index user-knowledgebase.md --rank posting.md --today 2026-09-23   # replay a past run
-```
-
-Needs markdown-it-py and pyyaml (`pip install markdown-it-py pyyaml`, the `index` extra); without
-them it exits 1 saying so. Prints, never writes. Every section and entry with its line range; each project's strength,
-recency, seniority, status and tags; roles with their dates and the years they cover, overlaps
-counted once; the vocabulary, skills with aliases, metric ids and the unanswered questions. About a
-seventh of the file it describes. It is generated each time because line numbers move on every edit.
-
-`--rank` scores every project against the posting's `requirements` by the table in
-`jsk-tailor-analyst.md`: required ×3, preferred ×1, strength ×2, recency +1 within three years and
-+0.5 at four to six, seniority +1 at or above the posting's (the eight levels, most senior first).
-Matches are exact strings against `capabilities` and `technologies`. A **Coverage** table follows:
-which projects carry each requirement's term, and which terms the vocabulary does not have.
-
-Exit 1 when the file is not in the shape `kb-spec.md` describes — a project with no `yaml` block, a
-nested value in a flat block, a strength outside 1–5 — naming the entry. A project that failed to
-parse quietly would score as absent evidence on every posting.
-
-## The record
-
-### `jsk match`
-
-The `jsk.graph.match` module, over the queries in `jsk.graph.queries`.
-
-```bash
-jsk match applications/<dir>/posting.ttl                 # the four sections, as Markdown
-jsk match applications/<dir>/posting.ttl --cover 2       # a cover of at most two projects
-jsk match applications/<dir>/posting.ttl --json --today 2026-09-24
-```
-
-The graph record's `jsk index --rank`: a posting's requirements joined with the career through the
-vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. Reads the
-whole workspace the posting sits in (`career/kb.ttl`, `applications/*/`) and validates it first;
-any FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.
-
-**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
-one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
-only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
-answers with `j:concept`), `candidate` (it names none), `implicit`. Evidence per project is
-`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
-**Ranking** scores exactly as `jsk index --rank` does. **Cover** is the smallest set of projects,
-at most `--cover` (default 3), carrying every required requirement anything carries. **Questions**
-are derived from the gaps, never invented.
-
-Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
-1 when the workspace has a FAIL; 2 called wrong, or a path that is not
-`applications/<dir>/posting.ttl`.
-
-### `jsk validate`
-
-The `jsk.gates.validate_urs` module.
-
-```bash
-jsk validate resume.json
-jsk validate resume.json --strict            # warnings become failures
-jsk validate resume.json --max-findings 0    # print every one
-```
-
-The **record gate**, and the one that got more important. The record used to be compiled from a
-folder of concepts, so a structural check here would only have been re-checking the compiler. It is
-written by hand now, which puts this command between a slip in that writing and a resume somebody
-sends.
-
-What it checks:
-
-- **Shape** — every top-level key is one the renderer knows, `urs` and `person` are present, and
-  every list key holds a list. This is the check the hand-authoring brought back. `experience:`
-  written where `engagements:` belongs renders a resume with no jobs on it, and the mistake is
-  invisible in the PDF precisely because the section is simply not there.
-- **Ids** resolve, and nothing references something that is not in the document.
-- **Periods** are coherent — no end before its start, no ongoing role with an end date.
-- **Metrics** — every numeral in a bullet appears in some metric. This is the check that stops a
-  rewritten clause quietly inflating a number.
-- **Provenance** — nothing below a view's `provenance_floor` reaches that view.
-- **Views** carry no free text and no key the renderer does not know.
-- **Coverage** — a project rated `strength: 4` or better with no evidence fails; below that it warns.
-- **Renderable at all** — a record with no views, or with neither engagements nor projects, fails.
-  Every other check iterates a list, and an empty list satisfies all of them.
-
-A directory is exit 2 with the file to pass instead, and so is a `.md` — failing on a JSON parse
-error would tell somebody their record is malformed when what happened is that the bundle format
-went away.
-
-### `jsk render`
-
-The `jsk.urs.render_resume` module.
-
-```bash
-jsk render resume.json --out DIR --view view_au_default
-jsk render resume.json --out DIR --view view_acme --pdf
-jsk render resume.json --out DIR --view view_acme --region au
-jsk render resume.json --out DIR --view view_acme --pdf --ats-max
-```
-
-One record to `.tex` (and PDF with `--pdf`) plus `.txt`. The PDF is the only rendered deliverable;
-`--ats-max` chooses which variant it holds rather than adding a second file.
-
-**`--view` is required wherever the record holds more than one**, and leaving it out is exit 2 with
-the ids listed — usage, not failure, because nothing is wrong with the record and the missing thing
-is the one decision only a person can make. A record holding exactly one view still renders without
-it.
-
-| Flag | Does |
-|---|---|
-| `--out DIR` | where to write (default `.`) |
-| `--pdf` | also run the TeX engine |
-| `--view ID` | which view to render — required where the record holds more than one |
-| `--region CODE` | apply a region profile |
-| `--profile PATH` | a profile file directly |
-| `--format` | `all` (default), or one of `latex` / `txt` |
-| `--ats-max` | render the PDF in the ATS-maximal variant (shorthand for `--profile ats-maximal`) |
-| `--template NAME` | the visual template (default `monolith`) |
-| `--list-templates` | print the templates with what each is for, and exit |
-| `--name` | override the output filename stem |
-
-**With `--pdf`, a run that produced no PDF exits 1** and says **UNVERIFIED**. It used to record the
-failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there
-wasn't one, and still see success.
-
-**The page count is measured off the PDF**, with `pymupdf`, and printed only with `--pdf`:
-
-```
-  pages  Priya_Raman_Resume.pdf: 1 page against a budget of 2
-```
-
-It used to print the budget alone, which is the number somebody asked for rather than the number they
-got — the resume that prompted the fix rendered on one page against a budget of two and said so
-nowhere. Over budget is named (`- OVER BUDGET, run jsk fit`) and not failed: `jsk fit` owns that
-verdict, and it is the command that can do something about it. Without `pymupdf` the line says the
-budget and says it was not measured, which is the honest version of the same sentence.
-
-`--template` and `--ats-max` are different axes and compose. The variant decides what the document
-says; the template decides how it looks. All five templates extract to identical text, so the choice
-is about the reader and never about the parse. An unknown name is a usage error rather than a silent
-fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
-looked at — and it would look perfectly fine. See `references/templates.md`.
-
-### `jsk preview`
-
-The `jsk.urs.preview_templates` module.
-
-```bash
-jsk preview resume.json --out DIR
-jsk preview resume.json --out DIR --view view_acme --only meridian,ember
-```
-
-The same record rendered in every template, with the page count for each, so the look is chosen by
-looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
-installed. The `.tex` files are written one after another; the TeX compiles run side by side, each in
-its own scratch directory, and the report still lists the templates in their fixed order.
-
-Density is the one difference between templates that is not a matter of taste: the same record is
-one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
-was available is a decision worth making on purpose.
-
-| Flag | Does |
-|---|---|
-| `--out DIR` | required — previews are scratch, not deliverables |
-| `--view ID` / `--region CC` / `--ats-max` | passed straight through to the renderer |
-| `--only A,B` | just these templates |
-
-Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
-worked around: a template that does not build is not a template, and the others may be about to
-break too. Exit 2 = usage, or no TeX engine.
-
-## The gates on the document
-
-### `jsk check --only parse`
-
-The `jsk.gates.check_ats` module.
-
-```bash
-jsk check --only parse resume.pdf               # the rendered deliverable
-jsk check --only parse resume_ATS.txt --strict  # the ASCII variant
-```
-
-The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
-systems mangle a resume: text that does not extract at all, section words that appear in prose but
-never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
-parser will not map, and arrow glyphs that fuse job titles when stripped.
-
-The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
-template produces every render and cannot express any of them, so the check moved from the output to
-a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
-PDF; the `.txt` path is standard library only.
-
-### `jsk check --only prose`
-
-The `jsk.gates.check_prose` module.
-
-```bash
-jsk check --only prose resume.tex
-jsk check --only prose resume_ATS.txt
-```
-
-The **prose gate** — the writing rules the parse gate cannot see. Third person, unresolved
-placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
-across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
-PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.
-
-### `jsk check`
-
-Both document gates in one pass, on one file. Pass either sibling and the other is found beside it:
-the parse gate reads what is actually sent — the PDF — while the prose gate reads the `.tex` it was
-compiled from.
-
-```bash
-jsk check resume.pdf
-jsk check resume.pdf --strict
-```
-
-A run with `--only` never closes by saying both passed. It names the three gates that did not.
-
-### `jsk gates`
-
-```bash
-jsk gates <out-dir>
-jsk gates <out-dir> --record applications/acme/resume.json --pages 2
-jsk gates <out-dir> --view view_acme --json
-jsk gates <out-dir> --max-findings 0
-```
-
-The record, parse and prose gates over one rendered output directory, in **one process**. It is the
-five invocations a hand-run verification used to make — the record gate on `resume.json`, the parse
-gate on the PDF and again on the `.txt` with `--strict`, the prose gate on the `.tex` and again on
-the `.txt`. It imports the checkers rather than shelling out to them, and gives them the same
-arguments, so the findings and the exit code are the ones the five commands produce. That
-equivalence is what it is tested on.
-
-`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: same CLI, same
-arguments, same output to the character, now callable without a subprocess. That entry point is
-load-bearing rather than incidental, so it is documented here beside their CLIs.
-
-**`--record` defaults to `resume.json` in the output directory**, which is where the skill writes it
-for an application. Named rather than searched: a directory holding two records has no way to say
-which one the documents came from, and guessing would put a passing record gate against a resume it
-never described.
-
-Three properties, each of them an existing rule here rather than a new one:
-
-- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
-  rather than take anyone's word for it. The section headers match `jsk check`.
-- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
-  Same behaviour and same wording as `jsk check`. A path you *gave* that is not there is exit 2
-  instead — omitting `--record` and mistyping it are different mistakes, and reporting them
-  identically hides one. Both are non-zero.
-- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
-  and read it. That gate is the one no command can have, and a command that exited 0 having silently
-  skipped it would be the most dangerous thing in this directory.
-
-`--view ID` is optional and does no work. The record names the view it was written for, so nothing
-in the run reads the flag — it exists because this output is archived beside an application as
-evidence, and passing it stamps which view was gated. It was *required* while a bundle held every
-view and the command had no other way to know.
-
-`--pages N` reports and never fails. It measures the PDF and prints the renderer's own over-budget
-line, reused rather than restated. Over budget is named rather than failed everywhere in this
-pipeline, because `jsk fit` owns that verdict and is the command that can act on it.
-
-`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
-as `jsk validate`, because two gates that truncate differently are two gates people read differently.
-The header counts stay true regardless: truncating a list is a reading aid, truncating a count is a
-lie.
-
-`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
-and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
-so **the machine-readable form cannot report the render gate as passed either.** That is what makes
-`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.
-
-The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.
-
-## Fitting
-
-### `jsk fit`
-
-The `jsk.urs.fit_pages` module.
-
-```bash
-jsk fit resume.tex --target-pages 2
-jsk fit resume.tex --dry-run
-jsk fit resume.tex --in-place
-jsk fit resume.tex -o fitted.tex
-```
-
-Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
-the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
-0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
-non-zero, because the remedy then is to cut evidence, not to shrink type.
-
-It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
-and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
-sending. It now measures the artefact that goes out.
-
-Needs a TeX engine and `pymupdf`.
-
-## Shipping
-
-### `jsk ship`
-
-```bash
-jsk ship <resume.json> --out DIR --view ID [--ats-max] [--template N] [--pages N] [--json]
-```
-
-The three commands a ship used to be, in one process and in order, each step's output printed
-verbatim under its own `---` heading the way `jsk gates` prints it:
-
-1. **the record gate** — what `jsk validate <resume.json>` runs. A failure stops here and **nothing
-   is rendered**: a PDF made from a record that failed its gate looks sendable and is not.
-2. **the render** — what `jsk render <resume.json> --out DIR --view ID --pdf` runs, with `--ats-max`
-   and `--template` passed through. A render that produced no PDF stops here.
-3. **the parse and prose gates** — what `jsk gates DIR --record <resume.json> [--pages N]` runs,
-   less the record gate step 1 has just run on the same file.
-
-It closes with the same render-gate section `jsk gates` does: **nobody has read the PDF**, and the
-command says so rather than exiting 0 over it. When it stopped early that section says nothing was
-rendered, instead of pointing at a PDF an earlier run left in `DIR`. The page count is reported —
-the renderer's own line, and `--pages N`'s — and never failed; `jsk fit` owns that verdict.
-
-Exit `0` only if every step passed, `1` on any failure, `2` called wrong. `--json` carries every
-step in `steps[]` in the `jsk gates` shape, the render gate last and `UNVERIFIED`.
-
-### `jsk freeze`
-
-```bash
-jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--view ID] [--doc FILE ...]
-```
-
-Freezes one `applications/<yyyy-mm-dd>-<company>-<role>/` directory the way `references/mode-ship.md`
-describes: renames it to the day it was sent, if its leading date says otherwise, and writes
-`application.md` beside `posting.md`, `gaps.md` and `resume.json`:
-
-```markdown
----
-company: Acme Health
-title: Platform Engineer
-view: view_acme_platform
-submitted: 2026-09-08
-channel: Workday portal
-documents:
-  - Priya_Raman_Acme_Resume.pdf
-  - Priya_Raman_Acme_Resume_ATS.txt
----
-
-# Timeline
-
-| Date | Event | Channel | Note | Due |
-|---|---|---|---|---|
-| 2026-09-08 | submitted | Workday portal | | |
-```
-
-`company` and `title` come from the top-level lines of `posting.md`'s frontmatter. The view is
-`--view`, or the record's only one; a record with several and no `--view` is exit 2, naming them.
-The documents are the `--doc` files, or every `.pdf` and `.txt` in the directory. The final path is
-printed.
-
-It refuses — exit 1, saying why, with nothing renamed and nothing written — when:
-
-- **`application.md` already exists.** A frozen application is never re-frozen; later events are
-  one appended row each, by hand.
-- **any mechanical gate fails.** It runs what `jsk gates <app-dir> --record <app-dir>/resume.json`
-  runs, in process, and prints it. A failing document is never frozen.
-- `posting.md` has no `company:` or `title:`, there is nothing to list as documents, or the renamed
-  directory would land on one that already exists.
-
-`--submitted false` is for an application worked through and deliberately held back: it writes
-`submitted: false`, leaves the directory's name alone, and the timeline has its header and **no
-`submitted` row** — an accurate blank rather than a false green. It never touches
-`user-knowledgebase.md` or `log.md`; the log row stays the skill's to write.
-
-## What is not here any more
-
-The `okf` commands left with the bundle format; what each one did is now an edit or a `grep` on
-`user-knowledgebase.md`, `jsk validate` over the record written from it, or `jsk freeze`.
-
----
-
-Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
+# Commands
+
+The skill runs these for you. This page is for running them yourself.
+
+It is all one command. `pip install 'jsk-resume[all]'` puts `jsk` on your PATH; `python3 -m jsk` is
+the same entry point where it is importable but not on PATH, and on Windows use `python` or `py -3`
+in place of `python3`.
+
+Every subcommand below also exists as a module you can run or import directly —
+`python3 -m jsk.gates.check_ats resume.pdf`, `from jsk.urs import plan`. The headings name both.
+
+**Nothing here reads `user-knowledgebase.md`.** That file is Markdown a person and the skill edit
+with ordinary tools; this toolchain starts at the URS record written out of it, and carries it to a
+document somebody can send.
+
+## The whole surface
+
+```bash
+jsk doctor                       # what works on this machine
+jsk new ./my-career --name "Your Name"
+jsk index user-knowledgebase.md --rank applications/<dir>/posting.md
+jsk match applications/<dir>/posting.ttl   # the same question, over the graph record
+jsk kb apply changes.trig        # change the graph record; `jsk kb --help` lists the rest
+jsk validate resume.json         # the record gate
+jsk render resume.json --out . --view view_default --pdf
+jsk check resume.pdf             # both document gates, one pass
+jsk gates .                      # all three mechanical gates
+jsk fit resume.tex --target-pages 2
+jsk preview resume.json --out ./looks
+jsk ship resume.json --out . --view view_default   # validate, render, gate
+jsk freeze applications/<dir> --submitted 2026-09-08 --channel "Workday portal"
+```
+
+Each subcommand calls the module documented below it, in the same interpreter, with the same
+arguments and the same exit code, so everything on this page is true through `jsk`. None of them
+spawns a Python child: that cost a start-up and a fresh import per call, which was most of the wall
+time of `jsk check`. The one exception is `jsk doctor`'s end-to-end run, which runs each module as
+`python -m` on purpose — proving that entry point works from cold is what it is for.
+
+## Exit codes
+
+Uniform across every subcommand:
+
+| Code | Means |
+|---|---|
+| `0` | passed |
+| `1` | failed — a real finding, or a dependency missing that makes the answer unknowable |
+| `2` | you called it wrong — bad usage, or a file that is not there |
+
+Nothing here passes quietly when it could not do its job. A page count nobody measured is a page
+count nobody knows.
+
+## Start here
+
+### `jsk doctor`
+
+The `jsk.preflight` module.
+
+```bash
+jsk doctor                 # verifies end to end
+jsk doctor --quick         # skip the render
+jsk doctor --json          # machine-readable
+jsk doctor --kb PATH       # check a specific user-knowledgebase.md
+```
+
+Bare `jsk doctor` renders the shipped example document and runs the parse and prose gates on the
+result, so a pass means the pipeline genuinely works here rather than looking like it should.
+
+Verdicts: `READY` · `READY, with gaps` · `BLOCKED` (the install is broken) · `BROKEN` (the toolchain
+is present but failed its own gates — that is a bug in the skill, not in your setup).
+
+Gaps are reported by what they *disable*, not by package name. Runs on a bare Python: a preflight
+that needs installing first is not a preflight.
+
+Without `--kb` it searches for `user-knowledgebase.md` three directories down. Searching by filename
+rather than by a directory shape is deliberate — a bundle used to be recognised by the folders inside
+it, so a half-created one was invisible here and reported as absent while the person was looking
+straight at it.
+
+### `jsk new`
+
+The `jsk.kb` module.
+
+```bash
+jsk new ./my-career --name "Your Name"
+jsk new ./my-career --name "Your Name" --force   # overwrite an existing file
+```
+
+Writes `user-knowledgebase.md` with every heading present and empty, plus `log.md` and an
+`applications/` directory beside it. No dependencies. It refuses rather than overwriting, because the
+file it would replace is somebody's career; `--force` replaces the knowledge base but never an
+existing `log.md`.
+
+What each heading is for is written into the file itself, as HTML comments beneath each one.
+Guidance in a template a person is looking at gets read; guidance in a specification they have to go
+and find does not.
+
+### `jsk index`
+
+The `jsk.kbindex` module.
+
+```bash
+jsk index user-knowledgebase.md                          # the overview
+jsk index user-knowledgebase.md --rank posting.md        # plus the ranking and coverage
+jsk index user-knowledgebase.md --rank posting.md --today 2026-09-23   # replay a past run
+```
+
+Needs markdown-it-py and pyyaml (`pip install markdown-it-py pyyaml`, the `index` extra); without
+them it exits 1 saying so. Prints, never writes. Every section and entry with its line range; each project's strength,
+recency, seniority, status and tags; roles with their dates and the years they cover, overlaps
+counted once; the vocabulary, skills with aliases, metric ids and the unanswered questions. About a
+seventh of the file it describes. It is generated each time because line numbers move on every edit.
+
+`--rank` scores every project against the posting's `requirements` by the table in
+`jsk-tailor-analyst.md`: required ×3, preferred ×1, strength ×2, recency +1 within three years and
++0.5 at four to six, seniority +1 at or above the posting's (the eight levels, most senior first).
+Matches are exact strings against `capabilities` and `technologies`. A **Coverage** table follows:
+which projects carry each requirement's term, and which terms the vocabulary does not have.
+
+Exit 1 when the file is not in the shape `kb-spec.md` describes — a project with no `yaml` block, a
+nested value in a flat block, a strength outside 1–5 — naming the entry. A project that failed to
+parse quietly would score as absent evidence on every posting.
+
+## The record
+
+### `jsk match`
+
+The `jsk.graph.match` module, over the queries in `jsk.graph.queries`.
+
+```bash
+jsk match applications/<dir>/posting.ttl                 # the four sections, as Markdown
+jsk match applications/<dir>/posting.ttl --cover 2       # a cover of at most two projects
+jsk match applications/<dir>/posting.ttl --json --today 2026-09-24
+```
+
+The graph record's `jsk index --rank`: a posting's requirements joined with the career through the
+vocabulary - the shipped `jsk/data/vocabulary.ttl` and the knowledge base's own additions. Reads the
+whole workspace the posting sits in (`career/kb.ttl`, `applications/*/`) and validates it first;
+any FAIL is printed and nothing is matched. Needs pyoxigraph, a dependency of the package.
+
+**Requirements** puts each one in a bucket: `matched` (a project holds the concept, or a narrower
+one within two hops - `via c:aks, 1 hop`), `near` (only an `implies` path, for a required one, or
+only something broader), `missing`, `ambiguous` (the label names several concepts; the analyst
+answers with `j:concept`), `candidate` (it names none), `implicit`. Evidence per project is
+`confirmed` (a confirmed bullet shows it), `unconfirmed` or `tag` (only the project's tags say so).
+**Ranking** scores exactly as `jsk index --rank` does. **Cover** is the smallest set of projects,
+at most `--cover` (default 3), carrying every required requirement anything carries. **Questions**
+are derived from the gaps, never invented.
+
+Exit 0 with the result - missing requirements included, since this is an assessment, not a gate;
+1 when the workspace has a FAIL; 2 called wrong, or a path that is not
+`applications/<dir>/posting.ttl`.
+
+### `jsk kb`
+
+The `jsk.graph.kbcli` module. One verb per operation on the graph record; `jsk kb --help` lists
+them and `jsk kb <verb> --help` explains one. Every verb finds the workspace - the folder holding
+`career/` - from the current directory, or takes `--root DIR`.
+
+```bash
+jsk kb apply changes.trig --dry-run      # the diff it would make, nothing written
+jsk kb apply changes.trig                # merged, validated, written, logged
+```
+
+**`apply`** is how an agent changes `career/kb.ttl`: a changeset, in TriG, with four graphs.
+
+```turtle
+@prefix op: <tag:jsk,2026:op#> .
+op:changeset op:base 7 ; op:summary "The payments project, from the braindump." .
+op:add    { k:prj_payments j:name "Payments platform" ; j:strength 4 ; j:recency 2025 .
+            [] j:project k:prj_payments ; j:rank 1 ; j:text "Cut settlement latency by 75%." . }
+op:set    { k:prj_legacy j:strength 2 . }                     # replaces every value it names
+op:retire { k:prj_intranet j:reason "Too old to earn a line." . }
+op:delete { k:q_duplicate a op:Entry . k:ach_x j:shows c:java . }
+```
+
+`op:add` adds; a predicate that allows one value and already has one is refused - use `op:set`.
+`op:set` replaces every value of each (entry, predicate) it names. `op:retire` dates the entry
+today and keeps the reason. `op:delete` removes exact triples, or with `a op:Entry` the whole
+entry - refused while anything points at it, since retiring is what keeps the history. `op:base`
+is the log revision the changeset was drafted against: an entry changed after it is a conflict,
+refused, to be re-read. The header's `op:summary` becomes the log entry's.
+
+What apply does unasked: a new bullet (a `[]` with `j:project`) gets its id,
+`ach_<project>_<three words of its text>`, never one the record has used. An entry whose claims
+changed drops to `j:inferred`, and every entry left inferred gets a `q_` question unless one is
+open. A metric version an application sent never changes: a new `j:value` becomes the next
+version, and the one it replaces is closed. A changeset cannot confirm anything, cannot write
+another file, cannot use blank nodes except for a new bullet, and cannot name a predicate the
+ontology does not have (it suggests the nearest).
+
+The record it would write is validated before anything is written, and so is the workspace
+before it starts: a FAIL in the career, a hand edit not yet adopted, or a torn write refuses the
+apply with the command that fixes it. Then `career/kb.ttl` is replaced, then `career/log.ttl`,
+and a copy of what was written goes to `.jsk/kb.last.ttl` (a cache that ignores itself in git).
+Two files cannot be replaced together atomically: a crash between them is detected on the next
+load - `log-sync`, "the last write reached kb.ttl and not log.ttl" - not prevented. On Windows, a
+file locked by an editor or a virus scanner is retried for about a second; if it stays locked
+nothing is changed. Stdin (`-`) is refused: a pipe that never closes hangs the command.
+
+Exit 0 written, or nothing to change; 1 refused, with every reason; 2 called wrong.
+
+### `jsk validate`
+
+The `jsk.gates.validate_urs` module.
+
+```bash
+jsk validate resume.json
+jsk validate resume.json --strict            # warnings become failures
+jsk validate resume.json --max-findings 0    # print every one
+```
+
+The **record gate**, and the one that got more important. The record used to be compiled from a
+folder of concepts, so a structural check here would only have been re-checking the compiler. It is
+written by hand now, which puts this command between a slip in that writing and a resume somebody
+sends.
+
+What it checks:
+
+- **Shape** — every top-level key is one the renderer knows, `urs` and `person` are present, and
+  every list key holds a list. This is the check the hand-authoring brought back. `experience:`
+  written where `engagements:` belongs renders a resume with no jobs on it, and the mistake is
+  invisible in the PDF precisely because the section is simply not there.
+- **Ids** resolve, and nothing references something that is not in the document.
+- **Periods** are coherent — no end before its start, no ongoing role with an end date.
+- **Metrics** — every numeral in a bullet appears in some metric. This is the check that stops a
+  rewritten clause quietly inflating a number.
+- **Provenance** — nothing below a view's `provenance_floor` reaches that view.
+- **Views** carry no free text and no key the renderer does not know.
+- **Coverage** — a project rated `strength: 4` or better with no evidence fails; below that it warns.
+- **Renderable at all** — a record with no views, or with neither engagements nor projects, fails.
+  Every other check iterates a list, and an empty list satisfies all of them.
+
+A directory is exit 2 with the file to pass instead, and so is a `.md` — failing on a JSON parse
+error would tell somebody their record is malformed when what happened is that the bundle format
+went away.
+
+### `jsk render`
+
+The `jsk.urs.render_resume` module.
+
+```bash
+jsk render resume.json --out DIR --view view_au_default
+jsk render resume.json --out DIR --view view_acme --pdf
+jsk render resume.json --out DIR --view view_acme --region au
+jsk render resume.json --out DIR --view view_acme --pdf --ats-max
+```
+
+One record to `.tex` (and PDF with `--pdf`) plus `.txt`. The PDF is the only rendered deliverable;
+`--ats-max` chooses which variant it holds rather than adding a second file.
+
+**`--view` is required wherever the record holds more than one**, and leaving it out is exit 2 with
+the ids listed — usage, not failure, because nothing is wrong with the record and the missing thing
+is the one decision only a person can make. A record holding exactly one view still renders without
+it.
+
+| Flag | Does |
+|---|---|
+| `--out DIR` | where to write (default `.`) |
+| `--pdf` | also run the TeX engine |
+| `--view ID` | which view to render — required where the record holds more than one |
+| `--region CODE` | apply a region profile |
+| `--profile PATH` | a profile file directly |
+| `--format` | `all` (default), or one of `latex` / `txt` |
+| `--ats-max` | render the PDF in the ATS-maximal variant (shorthand for `--profile ats-maximal`) |
+| `--template NAME` | the visual template (default `monolith`) |
+| `--list-templates` | print the templates with what each is for, and exit |
+| `--name` | override the output filename stem |
+
+**With `--pdf`, a run that produced no PDF exits 1** and says **UNVERIFIED**. It used to record the
+failure as a passing note and exit 0, so a caller could ask for a PDF, be told in passing there
+wasn't one, and still see success.
+
+**The page count is measured off the PDF**, with `pymupdf`, and printed only with `--pdf`:
+
+```
+  pages  Priya_Raman_Resume.pdf: 1 page against a budget of 2
+```
+
+It used to print the budget alone, which is the number somebody asked for rather than the number they
+got — the resume that prompted the fix rendered on one page against a budget of two and said so
+nowhere. Over budget is named (`- OVER BUDGET, run jsk fit`) and not failed: `jsk fit` owns that
+verdict, and it is the command that can do something about it. Without `pymupdf` the line says the
+budget and says it was not measured, which is the honest version of the same sentence.
+
+`--template` and `--ats-max` are different axes and compose. The variant decides what the document
+says; the template decides how it looks. All five templates extract to identical text, so the choice
+is about the reader and never about the parse. An unknown name is a usage error rather than a silent
+fall back to the default, because a resume rendered in a template nobody chose is a resume nobody has
+looked at — and it would look perfectly fine. See `references/templates.md`.
+
+### `jsk preview`
+
+The `jsk.urs.preview_templates` module.
+
+```bash
+jsk preview resume.json --out DIR
+jsk preview resume.json --out DIR --view view_acme --only meridian,ember
+```
+
+The same record rendered in every template, with the page count for each, so the look is chosen by
+looking. Writes `DIR/<template>.pdf` and `.tex`, plus a `.png` of the first page where `pymupdf` is
+installed. The `.tex` files are written one after another; the TeX compiles run side by side, each in
+its own scratch directory, and the report still lists the templates in their fixed order.
+
+Density is the one difference between templates that is not a matter of taste: the same record is
+one page in a dense template and two in an airy one, and a two-page resume where a one-page resume
+was available is a decision worth making on purpose.
+
+| Flag | Does |
+|---|---|
+| `--out DIR` | required — previews are scratch, not deliverables |
+| `--view ID` / `--region CC` / `--ats-max` | passed straight through to the renderer |
+| `--only A,B` | just these templates |
+
+Exit 0 = every template rendered. Exit 1 = at least one did not, and that is reported rather than
+worked around: a template that does not build is not a template, and the others may be about to
+break too. Exit 2 = usage, or no TeX engine.
+
+## The gates on the document
+
+### `jsk check --only parse`
+
+The `jsk.gates.check_ats` module.
+
+```bash
+jsk check --only parse resume.pdf               # the rendered deliverable
+jsk check --only parse resume_ATS.txt --strict  # the ASCII variant
+```
+
+The **parse gate**. Reads the PDF's text layer (or the `.txt`) for what makes applicant tracking
+systems mangle a resume: text that does not extract at all, section words that appear in prose but
+never in a heading, leftover bracketed placeholders, unparseable phone numbers, bullet glyphs a
+parser will not map, and arrow glyphs that fuse job titles when stripped.
+
+The structural checks — tables, text boxes, header content, second columns — are gone. One LaTeX
+template produces every render and cannot express any of them, so the check moved from the output to
+a golden-file test on the template, where it is proved rather than sampled. Needs `pymupdf` for a
+PDF; the `.txt` path is standard library only.
+
+### `jsk check --only prose`
+
+The `jsk.gates.check_prose` module.
+
+```bash
+jsk check --only prose resume.tex
+jsk check --only prose resume_ATS.txt
+```
+
+The **prose gate** — the writing rules the parse gate cannot see. Third person, unresolved
+placeholders, sentences that stop before their object, phrases that read as junior, bullets repeated
+across projects, bullets that clear their throat before the verb. It reads the `.tex` rather than the
+PDF, because a bullet is an unambiguous `\item` there and needs no library to find. No dependencies.
+
+### `jsk check`
+
+Both document gates in one pass, on one file. Pass either sibling and the other is found beside it:
+the parse gate reads what is actually sent — the PDF — while the prose gate reads the `.tex` it was
+compiled from.
+
+```bash
+jsk check resume.pdf
+jsk check resume.pdf --strict
+```
+
+A run with `--only` never closes by saying both passed. It names the three gates that did not.
+
+### `jsk gates`
+
+```bash
+jsk gates <out-dir>
+jsk gates <out-dir> --record applications/acme/resume.json --pages 2
+jsk gates <out-dir> --view view_acme --json
+jsk gates <out-dir> --max-findings 0
+```
+
+The record, parse and prose gates over one rendered output directory, in **one process**. It is the
+five invocations a hand-run verification used to make — the record gate on `resume.json`, the parse
+gate on the PDF and again on the `.txt` with `--strict`, the prose gate on the `.tex` and again on
+the `.txt`. It imports the checkers rather than shelling out to them, and gives them the same
+arguments, so the findings and the exit code are the ones the five commands produce. That
+equivalence is what it is tested on.
+
+`check_ats.py` and `check_prose.py` grew a `main(argv)` entry point so it could: same CLI, same
+arguments, same output to the character, now callable without a subprocess. That entry point is
+load-bearing rather than incidental, so it is documented here beside their CLIs.
+
+**`--record` defaults to `resume.json` in the output directory**, which is where the skill writes it
+for an application. Named rather than searched: a directory holding two records has no way to say
+which one the documents came from, and guessing would put a passing record gate against a resume it
+never described.
+
+Three properties, each of them an existing rule here rather than a new one:
+
+- **Every gate's output is printed verbatim, never summarised.** The person should see the evidence
+  rather than take anyone's word for it. The section headers match `jsk check`.
+- **A missing input is `SKIPPED` and a failure.** A gate that did not run is not a gate that passed.
+  Same behaviour and same wording as `jsk check`. A path you *gave* that is not there is exit 2
+  instead — omitting `--record` and mistyping it are different mistakes, and reporting them
+  identically hides one. Both are non-zero.
+- **It never attempts the render gate**, and closes with a line saying somebody has to open the PDF
+  and read it. That gate is the one no command can have, and a command that exited 0 having silently
+  skipped it would be the most dangerous thing in this directory.
+
+`--view ID` is optional and does no work. The record names the view it was written for, so nothing
+in the run reads the flag — it exists because this output is archived beside an application as
+evidence, and passing it stamps which view was gated. It was *required* while a bundle held every
+view and the command had no other way to know.
+
+`--pages N` reports and never fails. It measures the PDF and prints the renderer's own over-budget
+line, reused rather than restated. Over budget is named rather than failed everywhere in this
+pipeline, because `jsk fit` owns that verdict and is the command that can act on it.
+
+`--max-findings N` caps how many findings each gate lists — the same flag name and the same default
+as `jsk validate`, because two gates that truncate differently are two gates people read differently.
+The header counts stay true regardless: truncating a list is a reading aid, truncating a count is a
+lie.
+
+`--json` carries each checker's whole text in `gates[].output`, beside `gate`, `command`, `status`
+and `exit`. It always includes a `render gate` entry with `status: "UNVERIFIED"` and `exit: null`,
+so **the machine-readable form cannot report the render gate as passed either.** That is what makes
+`--json` safe to consume here: it is the same evidence in a different envelope, never a summary.
+
+The exit code is the worst gate's: `0` all passed, `1` any failed, `2` called wrong.
+
+## Fitting
+
+### `jsk fit`
+
+The `jsk.urs.fit_pages` module.
+
+```bash
+jsk fit resume.tex --target-pages 2
+jsk fit resume.tex --dry-run
+jsk fit resume.tex --in-place
+jsk fit resume.tex -o fitted.tex
+```
+
+Rewrites the density knobs in the `.tex`, recompiles, and measures the PDF that comes out. It applies
+the levers in a fixed order — spacing, bullet spacing, margins, font size — stopping at the 10pt and
+0.5" floors instead of crossing them. If the target is unreachable without a breach it exits
+non-zero, because the remedy then is to cut evidence, not to shrink type.
+
+It used to measure a `.docx` through LibreOffice while the PDF was what got sent. The two disagreed,
+and a resume this reported as two pages shipped as three — a gate passing on a document nobody was
+sending. It now measures the artefact that goes out.
+
+Needs a TeX engine and `pymupdf`.
+
+## Shipping
+
+### `jsk ship`
+
+```bash
+jsk ship <resume.json> --out DIR --view ID [--ats-max] [--template N] [--pages N] [--json]
+```
+
+The three commands a ship used to be, in one process and in order, each step's output printed
+verbatim under its own `---` heading the way `jsk gates` prints it:
+
+1. **the record gate** — what `jsk validate <resume.json>` runs. A failure stops here and **nothing
+   is rendered**: a PDF made from a record that failed its gate looks sendable and is not.
+2. **the render** — what `jsk render <resume.json> --out DIR --view ID --pdf` runs, with `--ats-max`
+   and `--template` passed through. A render that produced no PDF stops here.
+3. **the parse and prose gates** — what `jsk gates DIR --record <resume.json> [--pages N]` runs,
+   less the record gate step 1 has just run on the same file.
+
+It closes with the same render-gate section `jsk gates` does: **nobody has read the PDF**, and the
+command says so rather than exiting 0 over it. When it stopped early that section says nothing was
+rendered, instead of pointing at a PDF an earlier run left in `DIR`. The page count is reported —
+the renderer's own line, and `--pages N`'s — and never failed; `jsk fit` owns that verdict.
+
+Exit `0` only if every step passed, `1` on any failure, `2` called wrong. `--json` carries every
+step in `steps[]` in the `jsk gates` shape, the render gate last and `UNVERIFIED`.
+
+### `jsk freeze`
+
+```bash
+jsk freeze <app-dir> --submitted YYYY-MM-DD|false --channel TEXT [--view ID] [--doc FILE ...]
+```
+
+Freezes one `applications/<yyyy-mm-dd>-<company>-<role>/` directory the way `references/mode-ship.md`
+describes: renames it to the day it was sent, if its leading date says otherwise, and writes
+`application.md` beside `posting.md`, `gaps.md` and `resume.json`:
+
+```markdown
+---
+company: Acme Health
+title: Platform Engineer
+view: view_acme_platform
+submitted: 2026-09-08
+channel: Workday portal
+documents:
+  - Priya_Raman_Acme_Resume.pdf
+  - Priya_Raman_Acme_Resume_ATS.txt
+---
+
+# Timeline
+
+| Date | Event | Channel | Note | Due |
+|---|---|---|---|---|
+| 2026-09-08 | submitted | Workday portal | | |
+```
+
+`company` and `title` come from the top-level lines of `posting.md`'s frontmatter. The view is
+`--view`, or the record's only one; a record with several and no `--view` is exit 2, naming them.
+The documents are the `--doc` files, or every `.pdf` and `.txt` in the directory. The final path is
+printed.
+
+It refuses — exit 1, saying why, with nothing renamed and nothing written — when:
+
+- **`application.md` already exists.** A frozen application is never re-frozen; later events are
+  one appended row each, by hand.
+- **any mechanical gate fails.** It runs what `jsk gates <app-dir> --record <app-dir>/resume.json`
+  runs, in process, and prints it. A failing document is never frozen.
+- `posting.md` has no `company:` or `title:`, there is nothing to list as documents, or the renamed
+  directory would land on one that already exists.
+
+`--submitted false` is for an application worked through and deliberately held back: it writes
+`submitted: false`, leaves the directory's name alone, and the timeline has its header and **no
+`submitted` row** — an accurate blank rather than a false green. It never touches
+`user-knowledgebase.md` or `log.md`; the log row stays the skill's to write.
+
+## What is not here any more
+
+The `okf` commands left with the bundle format; what each one did is now an edit or a `grep` on
+`user-knowledgebase.md`, `jsk validate` over the record written from it, or `jsk freeze`.
+
+---
+
+Next: [Architecture](ARCHITECTURE.md) · [Why it works this way](WHY.md)
````

Run: `python -m pytest tests/test_plugin_surface.py tests/test_budget.py -q`
Expected: PASS. The resident total is now 5,999 tokens of 6,000:

Run: `python -c "from pathlib import Path;R=Path('plugins/jsk/skills/jsk');print(sum(len(p.read_bytes().replace(b'\r\n',b'\n')) for p in [R/'SKILL.md',R/'references/mode-tailor.md',R/'references/mode-ship.md'])//4)"`
Expected: `5999`

- [ ] **Step 9: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/kbcli.py src/jsk/graph/ontology.py src/jsk/graph/shapes.py src/jsk/cli.py src/jsk/preflight.py plugins/jsk/skills/jsk/SKILL.md docs/SCRIPTS.md tests/test_graph_kbcli.py
git commit -m "feat: jsk kb apply - a changeset merged, validated, written, then logged"
```

---

### Task 6: `confirm`, `adopt`, `fmt`

**Files:**
- Modify: `src/jsk/graph/kbcli.py`, `docs/SCRIPTS.md`
- Test: `tests/test_graph_kbcli.py`

**Interfaces:**
- Consumes: Task 5's `kbcli` helpers; `rules.PLACEHOLDER`; `record.shadow`, `record.literal`, `record.replace`, `record.staged`; `io.parse_text`; `writer.write`, `writer.WriteError`.
- Produces: verbs `confirm`, `adopt`, `fmt`; `writable(store, allow=("clean",), canonical=True)`; `write_logged(..., old=None)` (diff base); `kbcli.iri_of(text)`, `unknown(iri, store) -> (detail, fix)`, `PROVENANCE_RANK`, `provenances(quads)`, `claims(quads, s)`, `upgrades(before_quads_or_None, after_quads) -> [str]`, `comments_refused(parsed)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_graph_kbcli.py`, add `import datetime` after `import contextlib`, and insert these classes before `class Dispatch(Workspace):`:

```python
ANSWER = "Yes - 42 sites at hand-over, and a quarter each before the platform."


class Confirm(Workspace):
    def test_confirming_answers_the_open_questions_and_logs_the_answer(self):
        code, out = self.kb("confirm", "k:ach_site_onboarding_sites_one_platform",
                            "prj_site_onboarding", "--answer", ANSWER)
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual([f.text() for f in s.findings], [])
        text = self.path("career/kb.ttl").read_text(encoding="utf-8")
        self.assertIn("k:q_sites_bullet j:about k:ach_site_onboarding_sites_one_platform", text)
        self.assertEqual(text.count('j:answered "' + datetime.date.today().isoformat()), 2)
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn(f'j:answer "{ANSWER}"', log)
        self.assertIn("j:by j:confirm", log)

    def test_an_answer_that_says_nothing_is_refused(self):
        for said in ("yes", "OK.", "confirmed", "", "<answer>", "..."):
            with self.subTest(said=said):
                code, out = self.kb("confirm", "prj_site_onboarding", "--answer", said)
                self.assertEqual(code, 1)
                self.assertIn("is not an answer", out)

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("confirm", "prj_site_onbording", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_site_onboarding?", out)

    def test_an_entry_that_is_not_a_claim(self):
        code, out = self.kb("confirm", "met_sites", "--answer", ANSWER)
        self.assertEqual(code, 1)
        self.assertIn("a Metric is not a claim", out)

    def test_confirming_what_is_confirmed_changes_nothing(self):
        code, out = self.kb("confirm", "prj_clinical_events", "--answer", ANSWER)
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))


class Adopt(Workspace):
    def test_a_hand_edit_is_logged_with_what_it_raised(self):
        self.kb("apply", self.changeset(PFX + 'op:set { k:prj_clinical_events j:strength 4 . }\n'))
        self.edit_kb("j:outcome \"Onboarding fell to two weeks; 42 sites now run on it.\" ;\n"
                     "    j:provenance j:inferred .",
                     "j:outcome \"Onboarding fell to two weeks; 42 sites now run on it.\" ;\n"
                     "    j:provenance j:confirmed .")
        self.edit_kb('"Led a team of 6 engineers', '"Led a team of 8 engineers')
        self.assertEqual(record.state(self.loaded()).kind, "hand-edited")
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:prj_site_onboarding: inferred -> confirmed", out)
        self.assertIn("raised   k:ach_clinical_events_led_migration: j:text changed while confirmed", out)
        self.assertIn("-    j:provenance j:inferred .", out)      # the diff is from r3
        s = self.loaded()
        self.assertEqual((record.state(s).kind, record.state(s).log_revision), ("clean", 4))
        log = self.path("career/log.ttl").read_text(encoding="utf-8")
        self.assertIn("Raised: k:ach_clinical_events_led_migration: j:text changed while confirmed", log)

    def test_with_no_copy_to_compare_every_confirmed_entry_is_listed(self):
        self.edit_kb('j:size "1001-5000"', 'j:size "5001-10000"')
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertIn("raised   k:prj_clinical_events is confirmed", out)
        self.assertIn("No copy of r2 to compare against",
                      self.path("career/log.ttl").read_text(encoding="utf-8"))

    def test_a_torn_write_is_adopted(self):
        self.edit_kb("j:revision 2 .", "j:revision 3 .")
        self.assertEqual(record.state(self.loaded()).kind, "torn")
        code, out = self.kb("adopt")
        self.assertEqual(code, 0, out)
        self.assertEqual(record.state(self.loaded()).kind, "clean")

    def test_comments_are_refused_unless_dropped(self):
        self.edit_kb("# == Metrics\n", "# == Metrics\n# ask about the latency\n")
        code, out = self.kb("adopt")
        self.assertEqual(code, 1)
        self.assertIn("career/kb.ttl:", out)
        self.assertIn("# ask about the latency", out)
        code, out = self.kb("adopt", "--drop-comments")
        self.assertEqual(code, 0, out)
        self.assertNotIn("# ask", self.path("career/kb.ttl").read_text(encoding="utf-8"))

    def test_a_clean_record_has_nothing_to_adopt(self):
        code, out = self.kb("adopt")
        self.assertEqual(code, 0)
        self.assertIn("nothing to adopt", out)


class Fmt(Workspace):
    def test_a_reformat_is_logged_on_its_own_and_keeps_the_day(self):
        self.old_layout()
        code, out = self.kb("fmt")
        self.assertEqual(code, 0, out)
        s = self.loaded()
        self.assertEqual((record.state(s).kind, record.state(s).log_revision), ("clean", 3))
        self.assertIn('j:updated "2026-09-20"^^xsd:date ; j:revision 3 .',
                      self.path("career/kb.ttl").read_text(encoding="utf-8"))
        self.assertIn("j:by j:fmt", self.path("career/log.ttl").read_text(encoding="utf-8"))

    def test_a_canonical_file_is_left_alone(self):
        code, out = self.kb("fmt")
        self.assertEqual((code, record.state(self.loaded()).log_revision), (0, 2))
        self.assertIn("already canonical", out)

    def test_a_hand_edit_is_adopted_not_formatted(self):
        self.edit_kb("# == Metrics\n\n", "# == Metrics\n\n\n")
        code, out = self.kb("fmt")
        self.assertEqual(code, 1)
        self.assertIn("jsk kb adopt", out)

    def test_another_record_file_is_rewritten_unlogged(self):
        posting = self.path("applications/acme-platform-engineer/posting.ttl")
        posting.write_text(posting.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
        code, out = self.kb("fmt", str(posting))
        self.assertEqual(code, 0, out)
        self.assertIn("posting.ttl: rewritten", out)
        self.assertEqual(record.state(self.loaded()).log_revision, 2)

    def test_the_log_is_not_a_file_to_format(self):
        code, out = self.kb("fmt", str(self.path("career/log.ttl")))
        self.assertEqual(code, 1)
        self.assertIn("written by jsk only", out)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: FAIL - the new tests: `unknown verb: confirm` / `adopt` / `fmt` (exit 2).

- [ ] **Step 3: The three verbs**

The `writable` continuation line ends in a backslash: use the Edit tool.

```diff
--- a/src/jsk/graph/kbcli.py
+++ b/src/jsk/graph/kbcli.py
@@ -3,6 +3,9 @@
 Usage: jsk kb <verb> [arguments] [--root DIR]
 
   apply <changeset.trig> [--dry-run]   merge a changeset into career/kb.ttl; prints the diff
+  confirm <id>... --answer "..."       confirm entries with the person's answer, logged
+  adopt [--drop-comments]              log a hand edit, listing every provenance it raised
+  fmt [<file>...] [--drop-comments]    rewrite in the canonical layout; kb.ttl's is logged
 
 --root is the workspace, the folder holding career/; by default the nearest one above
 the current directory. `jsk kb <verb> --help` says more about one verb.
@@ -91,7 +94,7 @@ GUIDE = {
 }
 
 
-def writable(store, allow=("clean",)):
+def writable(store, allow=("clean",), canonical=True):
     """None when the record may be written; otherwise the exit code of a refusal."""
     from . import record as R
     from .writer import write
@@ -106,7 +109,8 @@ def writable(store, allow=("clean",)):
     if st.kind not in allow:
         message, fix = GUIDE[st.kind]
         return refuse([message or st.detail], fix)
-    if st.kind == "clean" and write(store.graph(R.KB), "kb") != store.parsed[R.KB].text:
+    if canonical and st.kind == "clean" and \
+            write(store.graph(R.KB), "kb") != store.parsed[R.KB].text:
         return refuse(["career/kb.ttl is not in the canonical layout this jsk writes"],
                       "run `jsk kb fmt` - a reformat is logged on its own, so no change hides in it")
     return None
@@ -134,8 +138,9 @@ def curies(iris):
 
 
 def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=None,
-                 content=True, dry_run=False, notes=()):
-    """Stamp, validate, print and - unless a dry run - write. Returns the exit code."""
+                 content=True, dry_run=False, notes=(), old=None):
+    """Stamp, validate, print and - unless a dry run - write. Returns the exit code.
+    The diff is from `old` when given (adopt: the revision the log last recorded)."""
     from . import record as R
     from . import store as S
     from .io import parse_text
@@ -153,7 +158,7 @@ def write_logged(store, root, quads, by, summary, touched=(), minted=(), answer=
         show_findings(broken, f"REFUSED  the change would leave {len(broken)} failures:")
         print("nothing was written")
         return 1
-    print(diff(store.parsed[R.KB].text, kb_text), end="")
+    print(diff(store.parsed[R.KB].text if old is None else old, kb_text), end="")
     for label, ids in (("minted", minted), ("touched", touched)):
         if ids:
             print(f"{label:8} {curies(ids)}")
@@ -214,6 +219,230 @@ def cmd_apply(args, root):
                         dry_run=dry, notes=e.notes)
 
 
+def iri_of(text):
+    """k:prj_x, prj_x or c:kafka as an iri."""
+    from . import ontology as O
+
+    if text.startswith("k:"):
+        return O.K + text[2:]
+    if text.startswith("c:"):
+        return O.C + text[2:]
+    return O.K + text
+
+
+def unknown(iri, store):
+    from .writer import curie
+
+    near = difflib.get_close_matches(iri, list(store.homes), n=1)
+    return (f"{curie(iri)} is not in the record",
+            f"did you mean {curie(near[0])}?" if near else "check the id: `jsk kb view` lists them")
+
+
+@verb
+def cmd_confirm(args, root):
+    """jsk kb confirm <id>... --answer "what the person said"
+
+    The only way an entry becomes j:confirmed. Ask the person; record their answer in their
+    words. Each entry named is confirmed, every open question about it is answered today,
+    and the log keeps the answer beside the ids - the audit trail of why it is confirmed.
+    An answer that says nothing ("yes", "ok", "confirmed") is refused.
+    """
+    import pyoxigraph as ox
+
+    from . import ontology as O
+    from . import record as R
+    from . import store as S
+    from .rules import PLACEHOLDER
+
+    answer = take(args, "--answer", value=True)
+    if not args or answer is None:
+        return usage('jsk kb confirm takes ids and --answer "what the person said"')
+    if PLACEHOLDER.fullmatch(answer):
+        return refuse([f"{answer!r} is not an answer"],
+                      "record what the person said, in their words: the log keeps it as the "
+                      "reason this is confirmed")
+    store = S.load(root)
+    code = writable(store)
+    if code is not None:
+        return code
+    quads = list(store.graph(R.KB))
+    in_kb = {q.subject.value for q in quads}
+    prov, confirmed = ox.NamedNode(O.J + "provenance"), ox.NamedNode(O.J + "confirmed")
+    ids, problems = [], []
+    for text in args:
+        iri = iri_of(text)
+        cls = O.class_of(iri)
+        if iri not in in_kb:
+            problems.append(unknown(iri, store))
+        elif not O.BY_NAME[cls].claims:
+            problems.append((f"{text} has no provenance to confirm: a {cls} is not a claim",
+                             "confirm the entry that makes the claim"))
+        elif any(q.subject.value == iri and q.predicate.value == O.J + "retired" for q in quads):
+            problems.append((f"{text} is retired", "a retired entry is not confirmed"))
+        else:
+            ids.append(iri)
+    if problems:
+        for detail, fix in problems:
+            print(f"REFUSED  {detail}\n        fix: {fix}")
+        print("nothing was written")
+        return 1
+    todo = [i for i in ids if (ox.NamedNode(i), prov, confirmed) not in
+            {(q.subject, q.predicate, q.object) for q in quads}]
+    about, answered = ox.NamedNode(O.J + "about"), ox.NamedNode(O.J + "answered")
+    done = {q.subject for q in quads if q.predicate == answered}
+    asked = sorted({q.subject.value for q in quads if q.predicate == about
+                    and q.object.value in ids and q.subject not in done})
+    if not todo and not asked:
+        print("nothing to change: every one of them is confirmed already")
+        return 0
+    quads = [q for q in quads if not (q.subject.value in todo and q.predicate == prov)]
+    quads += [ox.Quad(ox.NamedNode(i), prov, confirmed) for i in todo]
+    quads += [ox.Quad(ox.NamedNode(q), answered, R.literal(datetime.date.today().isoformat(), "date"))
+              for q in asked]
+    return write_logged(store, root, quads, "confirm", f"Confirmed {curies(ids)}.",
+                        touched=set(todo) | set(asked), answer=answer)
+
+
+PROVENANCE_RANK = {"confirmed": 3, "inferred": 2, "needs-verification": 1, "disputed": 0}
+
+
+def provenances(quads):
+    from . import ontology as O
+    return {q.subject.value: q.object.value[len(O.J):] for q in quads
+            if q.predicate.value == O.J + "provenance"}
+
+
+def claims(quads, s):
+    from . import ontology as O
+    cls = O.BY_NAME[O.class_of(s)]
+    names = {p.name for p in cls.preds.values() if p.claim}
+    return {(q.predicate.value, q.object.value) for q in quads
+            if q.subject.value == s and q.predicate.value[len(O.J):] in names}
+
+
+def upgrades(before, after):
+    """What a hand edit raised: provenance moved up, an entry added as confirmed, or a
+    claim changed under a confirmation it no longer earns. Without the revision the log
+    last recorded to compare against, every confirmed entry is listed."""
+    from .writer import curie
+
+    now = provenances(after)
+    if before is None:
+        return [f"{curie(s)} is confirmed" for s, p in sorted(now.items()) if p == "confirmed"]
+    was, out = provenances(before), []
+    for s, p in sorted(now.items()):
+        if s not in was:
+            if p == "confirmed":
+                out.append(f"{curie(s)}: added as confirmed")
+        elif PROVENANCE_RANK[p] > PROVENANCE_RANK[was[s]]:
+            out.append(f"{curie(s)}: {was[s]} -> {p}")
+        elif p == "confirmed" and claims(before, s) != claims(after, s):
+            changed = sorted({curie(pred) for pred, _ in claims(before, s) ^ claims(after, s)})
+            out.append(f"{curie(s)}: {', '.join(changed)} changed while confirmed")
+    return out
+
+
+def comments_refused(parsed):
+    lines = [f"{parsed.file}:{n} {text}" for n, text in parsed.comments]
+    return refuse([f"{len(lines)} hand comment(s) the canonical layout would drop:"] + lines,
+                  "move each into a j:note on the entry it is about, or pass --drop-comments")
+
+
+@verb
+def cmd_adopt(args, root):
+    """jsk kb adopt [--drop-comments]
+
+    Logs career/kb.ttl as it now is: after a hand edit, a torn write, a restored file, or
+    for a kb.ttl that has no log yet. It writes the file in the canonical layout and lists
+    every provenance the edit raised - an entry marked confirmed by hand is exactly what
+    `jsk kb confirm` exists to prevent, so each one is named, to be checked with the person.
+    This is detection, not prevention: the edit already happened; adopt makes it visible.
+    """
+    from . import record as R
+    from . import store as S
+    from .io import parse_text
+
+    drop = bool(take(args, "--drop-comments"))
+    if args:
+        return usage("jsk kb adopt takes no arguments")
+    store = S.load(root)
+    st = R.state(store)
+    if st.kind == "clean":
+        print(f"nothing to adopt: career/kb.ttl is what r{st.log_revision} logged")
+        return 0
+    code = writable(store, allow=("unlogged", "hand-edited", "torn", "out-of-sync"))
+    if code is not None:
+        return code
+    if store.parsed[R.KB].comments and not drop:
+        return comments_refused(store.parsed[R.KB])
+    old = R.shadow(root, st.logged_sha)
+    before = parse_text(old, R.KB).quads if old is not None else None
+    after = store.graph(R.KB)
+    raised = upgrades(before, after)
+    touched = ({q.subject.value for q in set(before) ^ set(after)} if before is not None else set())
+    what = {"unlogged": "a kb.ttl with no log yet", "hand-edited": "a hand edit",
+            "torn": "a write that did not reach log.ttl", "out-of-sync": "a restored file"}[st.kind]
+    compared = "" if before is not None or st.kind == "unlogged" else \
+        f" No copy of r{st.log_revision} to compare against, so every confirmed entry is listed."
+    summary = (f"Adopted {what}.{compared} " + ("Raised: " + "; ".join(raised) + "." if raised
+                                               else "Raised no provenance.")).strip()
+    for line in raised:
+        print(f"raised   {line}")
+    if raised:
+        print("         check each with the person; `jsk kb confirm <id> --answer` records it")
+    return write_logged(store, root, after, "adopt", summary, touched, old=old)
+
+
+@verb
+def cmd_fmt(args, root):
+    """jsk kb fmt [<file>...] [--drop-comments]
+
+    Rewrites record files in the canonical layout - career/kb.ttl when none is named. A
+    reformat of kb.ttl is logged on its own (`by fmt`), so no content change can hide in
+    it; a hand-edited kb.ttl is adopted, not formatted. Any other record file (a
+    posting.ttl, an application.ttl) is rewritten in place and not logged. Hand comments
+    would be lost, so a file holding any is refused unless --drop-comments.
+    """
+    from . import ontology as O
+    from . import record as R
+    from . import store as S
+    from .writer import WriteError, write
+
+    drop = bool(take(args, "--drop-comments"))
+    store = S.load(root)
+    names = [S.file_name(os.path.abspath(a), root) for a in args] or [R.KB]
+    for name in names:
+        if name == R.LOG:
+            return refuse(["career/log.ttl is written by jsk only"], "leave it; every write keeps it")
+        if name not in store.parsed or O.kind_of(name) in (None, "vocabulary"):
+            return usage(f"{name}: not a record file of this workspace that parses")
+    code = 0
+    for name in names:
+        parsed = store.parsed[name]
+        if parsed.comments and not drop:
+            code = comments_refused(parsed)
+            continue
+        try:
+            text = write(store.graph(name), parsed.kind)
+        except WriteError as e:
+            code = refuse([f"{name}: {e}"], "`jsk kb check` shows what is wrong with it")
+            continue
+        if text == parsed.text:
+            print(f"{name}: already canonical")
+            continue
+        if name == R.KB:
+            refused = writable(store, canonical=False)
+            code = refused if refused is not None else write_logged(
+                store, root, store.graph(R.KB), "fmt", "Reformatted kb.ttl; no content changed.",
+                content=False)
+            continue
+        path = os.path.join(root, name)
+        R.replace(R.staged(path, text), path)
+        print(diff(parsed.text, text, name), end="")
+        print(f"{name}: rewritten")
+    return code
+
+
 def main(argv=None):
     args = list(sys.argv[1:] if argv is None else argv)
     if not args or (wants_help(args) and args[0] not in VERBS):
```

- [ ] **Step 4: Run them to see them pass**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: PASS (32 tests).

- [ ] **Step 5: Document them**

````diff
--- a/docs/SCRIPTS.md
+++ b/docs/SCRIPTS.md
@@ -198,6 +198,31 @@ load - `log-sync`, "the last write reached kb.ttl and not log.ttl" - not prevent
 file locked by an editor or a virus scanner is retried for about a second; if it stays locked
 nothing is changed. Stdin (`-`) is refused: a pipe that never closes hangs the command.
 
+```bash
+jsk kb confirm k:ach_payments_cut_settlement_latency --answer "Yes: 800 ms before, 200 after, from the Grafana board."
+jsk kb adopt                             # after a hand edit of kb.ttl
+jsk kb fmt                               # after a jsk upgrade changed the layout
+```
+
+**`confirm`** is the only way an entry becomes `j:confirmed`, and it takes the person's answer in
+their words: each id named is confirmed, every open question about it is answered today, and the
+log entry keeps the answer beside the ids. An answer that says nothing - `yes`, `ok`,
+`confirmed`, a placeholder - is refused, and one that reached the log by hand is flagged by
+`answer-placeholder`. This is an instruction with an audit trail, not a proof that anyone asked.
+
+**`adopt`** logs `kb.ttl` as it now is. Hand edits are legal; they are also invisible to the log
+until adopted, so every write refuses until they are (`hand-edited`, a WARN, says so on every
+load). Adopt lists every provenance the edit raised - an entry moved up to confirmed, added as
+confirmed, or a claim changed while confirmed - comparing against `.jsk/kb.last.ttl`, the copy of
+the last logged revision; without that copy it lists every confirmed entry. It also records a
+torn write and a file restored on its own, and starts the log for a `kb.ttl` that has none.
+Detection, not prevention: the edit already happened, and adopt makes it visible.
+
+**`fmt`** rewrites a record file in the canonical layout: `kb.ttl` when none is named, logged on
+its own (`by fmt`, the day unchanged) so no content change hides in a reformat. A `posting.ttl`
+or `application.ttl` is rewritten in place, unlogged. Hand comments would be lost: `adopt` and
+`fmt` refuse a file with any, listing them, unless `--drop-comments`.
+
 Exit 0 written, or nothing to change; 1 refused, with every reason; 2 called wrong.
 
 ### `jsk validate`
````

- [ ] **Step 6: The whole suite, lint, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

```bash
git add src/jsk/graph/kbcli.py docs/SCRIPTS.md tests/test_graph_kbcli.py
git commit -m "feat: jsk kb confirm, adopt and fmt - confirmed only with an answer, a hand edit logged with what it raised"
```

---

### Task 7: `show`, `view`, `query`, `check`

**Files:**
- Create: `src/jsk/graph/named.py`, `src/jsk/graph/view.py`
- Modify: `src/jsk/graph/kbcli.py`, `src/jsk/preflight.py`, `docs/SCRIPTS.md`, `docs/superpowers/specs/2026-09-24-graph-core-design.md`
- Test: `tests/test_graph_kbcli.py`

**Interfaces:**
- Consumes: P2's `queries.PRE`, `queries.paths_to(store, concept)`, `queries.evidence(store, project, concept)`; P1's `writer.Subjects`, `writer.block`, `writer.order`, `writer.curie`; Task 6's `iri_of`, `unknown`.
- Produces: verbs `show`, `view`, `query`, `check`; `named.QUERIES = {name: (args, doc, fn(store, *args) -> (columns, rows))}` with `open`, `unconfirmed`, `holds`, `stale`; `named.table(columns, rows) -> str`; `view.render(triples, only=None) -> str`; `kbcli.entry_text(quads, iri)`, `with_children(quads, iri)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_graph_kbcli.py`, add `import json` after `import io` and `from jsk.graph import ontology as O` before `from jsk.graph import record`, then insert before `class Dispatch(Workspace):`:

```python
class Show(Workspace):
    def test_a_project_is_shown_with_its_bullets_and_the_base_to_draft_against(self):
        code, out = self.kb("show", "prj_clinical_events")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("# r2 - op:base 2\n"))
        first = out.index("k:ach_clinical_events_event_latency j:project")
        second = out.index("k:ach_clinical_events_led_migration j:project")
        self.assertLess(out.index("k:prj_clinical_events j:name"), first)
        self.assertLess(first, second)

    def test_a_metric_is_shown_with_its_versions(self):
        code, out = self.kb("show", "k:met_event_latency")
        self.assertLess(out.index("k:met_event_latency.v1"), out.index("k:met_event_latency.v2"))

    def test_a_shipped_concept_is_shown_from_the_vocabulary(self):
        code, out = self.kb("show", "c:kafka")
        self.assertEqual(code, 0, out)
        self.assertIn("# vocabulary.ttl", out)
        self.assertIn("# career/kb.ttl", out)       # kb.ttl extends it

    def test_an_unknown_id_names_the_nearest(self):
        code, out = self.kb("show", "prj_clinical_event")
        self.assertEqual(code, 1)
        self.assertIn("did you mean k:prj_clinical_events?", out)


class View(Workspace):
    def test_the_whole_career_in_section_order(self):
        code, out = self.kb("view")
        self.assertEqual(code, 0, out)
        at = [out.index(f"## {s}\n") for s in O.SECTIONS["kb"]]
        self.assertEqual(at, sorted(at))
        self.assertIn("- **Care-site onboarding** `k:prj_site_onboarding` _(inferred)_", out)
        self.assertIn("_(retired 2026-01-10: Too old and too small to earn a line.)_", out)
        self.assertIn("  - **Led a team of 6 engineers", out)
        self.assertIn("    problem: The legacy scheduler", out)

    def test_one_section(self):
        code, out = self.kb("view", "--section", "skills")
        self.assertIn("## Skills", out)
        self.assertNotIn("## Projects", out)

    def test_it_writes_nothing(self):
        before = sorted(p.name for p in Path(self.root).rglob("*"))
        self.kb("view")
        self.assertEqual(sorted(p.name for p in Path(self.root).rglob("*")), before)


class Query(Workspace):
    def test_open_questions(self):
        code, out = self.kb("query", "open")
        self.assertIn("| k:q_sites_bullet | k:ach_site_onboarding_sites_one_platform | 2026-09-01 |", out)
        self.assertNotIn("q_team_size", out)          # answered

    def test_unconfirmed_entries(self):
        code, out = self.kb("query", "unconfirmed", "--json")
        rows = json.loads(out)
        self.assertEqual([r["entry"] for r in rows],
                         ["k:ach_site_onboarding_sites_one_platform", "k:prj_site_onboarding"])

    def test_what_holds_a_concept(self):
        code, out = self.kb("query", "holds", "c:azure")
        self.assertIn("| k:prj_clinical_events | c:azure-ai-foundry | 1 | False | tag |", out)

    def test_a_revised_metric_makes_the_application_that_sent_it_stale(self):
        code, _ = self.kb("query", "stale")
        self.kb("apply", self.changeset(PFX + "op:set { k:met_team.v1 j:value 7 . }\n"))
        code, out = self.kb("query", "stale")
        today = datetime.date.today().isoformat()
        self.assertIn(f"| k:app_acme_platform_engineer | k:met_team.v1 | {today} | k:met_team.v2 |",
                      out)

    def test_an_unknown_query(self):
        code, out = self.kb("query", "everything")
        self.assertEqual(code, 2)
        self.assertIn("open, unconfirmed, holds, stale", out)


class Check(Workspace):
    def test_a_clean_workspace(self):
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("record   clean at r2", out)
        self.assertIn("0 FAIL, 0 WARN", out)

    def test_a_fail_exits_1_and_a_hand_edit_is_named(self):
        self.edit_kb("j:cites k:met_team ;", "j:cites k:met_teem ;")
        code, out = self.kb("check")
        self.assertEqual(code, 1)
        self.assertIn("record   hand-edited at r2", out)
        self.assertIn("did you mean k:met_team?", out)

    def test_a_file_out_of_layout_is_named(self):
        self.old_layout()
        code, out = self.kb("check")
        self.assertEqual(code, 0)
        self.assertIn("career/kb.ttl - not in the canonical layout", out)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: FAIL - the new tests: `unknown verb: show` / `view` / `query` / `check`.

- [ ] **Step 3: The named queries and the Markdown view**

Create `src/jsk/graph/named.py` (the `table` cell escape holds `"\\|"`: use the Write tool):

```python
"""The named queries `jsk kb query` runs: questions an agent asks the record by name.

Each returns (columns, rows), rows as dicts, so the same answer prints as a table or as
JSON. A query is here because an agent would otherwise work it out by reading the whole
file - which is the reading the graph exists to save. The roadmap's `experience`,
`inconsistent`, `demand` and `pipeline` arrive with the phases that need them (P5).
"""
from . import ontology as O
from .queries import PRE, evidence, paths_to
from .writer import curie

QUERIES = {}


def query(name, args="", doc=""):
    def register(fn):
        QUERIES[name] = (args, doc, fn)
        return fn
    return register


def local(iri):
    return iri[len(O.J):] if iri.startswith(O.J) else iri


@query("open", doc="open questions, oldest first")
def open_questions(store):
    rows = store.select(PRE + """SELECT ?q ?about ?text ?asked WHERE {
        ?q j:about ?about ; j:question ?text ; j:asked ?asked
        FILTER NOT EXISTS { ?q j:answered ?d } } ORDER BY ?asked ?q""")
    return (("question", "about", "asked", "ask"),
            [{"question": curie(r["q"].value), "about": curie(r["about"].value),
              "asked": r["asked"].value, "ask": r["text"].value} for r in rows])


@query("unconfirmed", doc="live entries not yet confirmed, with the question open about each")
def unconfirmed(store):
    rows = store.select(PRE + """SELECT ?s ?pv (SAMPLE(?q) AS ?open) WHERE {
        ?s j:provenance ?pv FILTER(?pv != j:confirmed) FILTER NOT EXISTS { ?s j:retired ?r }
        OPTIONAL { ?q j:about ?s FILTER NOT EXISTS { ?q j:answered ?d } } }
        GROUP BY ?s ?pv ORDER BY ?s""")
    return (("entry", "provenance", "open question"),
            [{"entry": curie(r["s"].value), "provenance": local(r["pv"].value),
              "open question": curie(r["open"].value) if "open" in r else ""} for r in rows])


@query("holds", "<concept>", "live projects holding a concept, or one that counts as it")
def holds(store, concept):
    iri = O.C + concept[2:] if concept.startswith("c:") else O.C + concept
    rows = sorted(paths_to(store, iri), key=lambda r: (r[2], r[0], r[1]))
    seen, out = set(), []
    for proj, held, hops, implied in rows:
        if proj in seen:
            continue
        seen.add(proj)
        out.append({"project": curie(proj), "holds": curie(held), "hops": hops,
                    "implied": implied, "evidence": evidence(store, proj, iri)})
    return (("project", "holds", "hops", "implied", "evidence"), out)


@query("stale", doc="applications that sent a metric version since replaced")
def stale(store):
    rows = store.select(PRE + """SELECT ?app ?v ?until ?now WHERE {
        ?app j:carriedVersion ?v . ?v j:validUntil ?until ; j:of ?m .
        OPTIONAL { ?now j:of ?m FILTER NOT EXISTS { ?now j:validUntil ?u } } }
        ORDER BY ?app ?v""")
    return (("application", "sent", "replaced", "current"),
            [{"application": curie(r["app"].value), "sent": curie(r["v"].value),
              "replaced": r["until"].value,
              "current": curie(r["now"].value) if "now" in r else ""} for r in rows])


def table(columns, rows):
    """A Markdown table; `|` in a value is escaped so the row keeps its cells."""
    def cell(v):
        return str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    out += ["| " + " | ".join(cell(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join(out)
```

Create `src/jsk/graph/view.py`:

```python
"""career/kb.ttl as Markdown, to be read end to end - stdout only, never a second file.

docs/WHY.md's rule survives the graph: a person must be able to read their record, whole,
and correct it. kb.ttl is laid out to be read; this is the same record without the
syntax, in the same section order. It is never written anywhere, so it can never drift
from the file it shows.
"""
from . import ontology as O
from .writer import Subjects, curie, order

# The predicate an entry is known by, per class, in the order they are tried.
TITLES = ("fullName", "name", "title", "subject", "institution", "question", "language",
          "jurisdiction", "text")
QUIET = {"provenance", "note", "retired", "reason"}
# Written under the entry, not beside it: paragraphs, not facts.
PROSE = {"problem", "decision", "outcome", "positioning"}
# What nesting already says: a bullet sits under its project, a version under its metric.
NESTED = {"Achievement": {"project"}, "MetricVersion": {"of"}}


def value(t):
    import pyoxigraph as ox
    return curie(t.value) if isinstance(t, ox.NamedNode) else t.value


def facts(sub, s, part, skip):
    """`pred: value` for each predicate of this part, in the class's order."""
    out, prose = [], []
    cls = sub.cls[s]
    for line in cls.lines:
        for p in line:
            if p.name in skip or p.name in QUIET or (p.section or "main") != part:
                continue
            vals = sub.props[s].get(p.name)
            if not vals:
                continue
            text = ", ".join(sorted(value(v) for v in vals))
            (prose if p.name in PROSE or "\n" in text else out).append((p.name, text))
    return out, prose


def entry(sub, s, part, indent=""):
    cls = sub.cls[s]
    title = next((t for t in TITLES if t in sub.props[s] and (cls.preds[t].section or "main") == part),
                 None)
    head = sub.get(s, title) if title else curie(s)
    tags = []
    pv = sub.get(s, "provenance")
    if pv and pv != O.J + "confirmed":
        tags.append(pv[len(O.J):])
    if sub.get(s, "retired"):
        tags.append(f"retired {sub.get(s, 'retired')}: {sub.get(s, 'reason', '')}")
    if cls.name == "Concept":
        tags += [value(t) for t in sub.props[s].get("a", [])]
    short, prose = facts(sub, s, part, {title} | NESTED.get(cls.name, set()))
    line = f"{indent}- **{head}** `{curie(s)}`" + (f" _({'; '.join(tags)})_" if tags else "")
    if short:
        line += " - " + "; ".join(f"{p}: {v}" for p, v in short)
    out = [line]
    for p, text in prose:
        body = text.replace("\n", "\n" + indent + "    ")
        out.append(f"{indent}    {p}: {body}")
    return out


def render(triples, only=None):
    """The Markdown for kb.ttl's triples; `only` limits it to one section."""
    sub = Subjects(triples)
    header = next(iter(sub.of("KB")), None)
    out = [f"# {sub.get(header, 'name', 'Career')}", ""] if header else []
    for section in O.SECTIONS["kb"]:
        if only and section.lower() != only.lower():
            continue
        out += [f"## {section}", ""]
        entries = order(sub, section)
        if not entries:
            out += ["_(none)_", ""]
            continue
        for s, part in entries:
            nested = sub.cls[s].name in ("Achievement", "MetricVersion")
            out += entry(sub, s, part, "  " if nested else "")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
```

- [ ] **Step 4: The four verbs**

```diff
--- a/src/jsk/graph/kbcli.py
+++ b/src/jsk/graph/kbcli.py
@@ -6,6 +6,10 @@ Usage: jsk kb <verb> [arguments] [--root DIR]
   confirm <id>... --answer "..."       confirm entries with the person's answer, logged
   adopt [--drop-comments]              log a hand edit, listing every provenance it raised
   fmt [<file>...] [--drop-comments]    rewrite in the canonical layout; kb.ttl's is logged
+  show <id>...                         entries as kb.ttl holds them, and the op:base to use
+  view [--section NAME]                the whole career as Markdown, to read
+  query <name> [args] [--json]         open | unconfirmed | holds <concept> | stale
+  check                                validate the workspace; exit 1 on a FAIL
 
 --root is the workspace, the folder holding career/; by default the nearest one above
 the current directory. `jsk kb <verb> --help` says more about one verb.
@@ -443,6 +447,149 @@ def cmd_fmt(args, root):
     return code
 
 
+def entry_text(quads, iri):
+    """One entry as kb.ttl writes it - every part, for the Person's Positioning too."""
+    from .writer import Subjects, block
+
+    sub = Subjects(quads)
+    parts = ["main"] + sorted({p.section for p in sub.cls[iri].preds.values() if p.section})
+    return "\n\n".join(b[0] for b in (block(sub, iri, part) for part in parts) if b)
+
+
+def with_children(quads, iri):
+    """The entry and what is read with it: a project's bullets, a metric's versions."""
+    from . import ontology as O
+
+    def of(pred):
+        return sorted({q.subject.value for q in quads if q.predicate.value == O.J + pred
+                       and q.object.value == iri})
+    kids = {"Project": sorted(of("project"), key=lambda a: rank(quads, a)),
+            "Metric": sorted(of("of"), key=lambda v: int(v.rsplit(".v", 1)[1]))}
+    return [iri] + kids.get(O.class_of(iri), [])
+
+
+def rank(quads, iri):
+    from . import ontology as O
+    return next((int(q.object.value) for q in quads if q.subject.value == iri
+                 and q.predicate.value == O.J + "rank"), 1 << 30)
+
+
+@verb
+def cmd_show(args, root):
+    """jsk kb show <id>...
+
+    The entries as their files hold them, in the canonical layout: a project with its
+    bullets, a metric with its versions. The first line is the revision to put in a
+    changeset's op:base, so a change drafted from what was shown is checked against it.
+    """
+    from . import record as R
+    from . import store as S
+
+    if not args:
+        return usage("jsk kb show takes one or more ids")
+    store = S.load(root)
+    st = R.state(store)
+    print(f"# r{st.log_revision} - op:base {st.log_revision}" if st.log_revision else
+          "# not logged yet - `jsk kb adopt` starts the log")
+    code = 0
+    for text in args:
+        iri = iri_of(text)
+        files = [f for f in store.definitions.get(iri, []) if f in store.parsed]
+        if not files:
+            detail, fix = unknown(iri, store)
+            print(f"\nREFUSED  {detail}\n        fix: {fix}")
+            code = 1
+            continue
+        for f in files:
+            quads = store.graph(f)
+            print(f"\n# {f}")
+            print("\n\n".join(entry_text(quads, i) for i in with_children(quads, iri)))
+    return code
+
+
+@verb
+def cmd_view(args, root):
+    """jsk kb view [--section NAME]
+
+    The whole career as Markdown, in kb.ttl's section order, to read end to end and
+    correct - stdout only; it is never written to a file, so it cannot drift. Entries not
+    confirmed, and retired ones, say so beside their names.
+    """
+    from . import record as R
+    from . import store as S
+    from .view import render
+
+    only = take(args, "--section", value=True)
+    if args:
+        return usage("jsk kb view takes only --section NAME")
+    store = S.load(root)
+    if R.KB not in store.parsed:
+        return refuse([GUIDE[R.state(store).kind][0]], GUIDE[R.state(store).kind][1])
+    print(render(store.graph(R.KB), only), end="")
+    return 0
+
+
+@verb
+def cmd_query(args, root):
+    """jsk kb query <name> [arguments] [--json]
+
+      open                questions not yet answered, oldest first
+      unconfirmed         live entries not confirmed, with the question open about each
+      holds <concept>     projects holding a concept, or one that counts as it
+      stale               applications that sent a metric version since replaced
+
+    A table by default; --json for the same rows, structured.
+    """
+    import json
+
+    from . import store as S
+    from .named import QUERIES, table
+
+    as_json = bool(take(args, "--json"))
+    if not args or args[0] not in QUERIES:
+        return usage(f"jsk kb query takes one of: {', '.join(QUERIES)}")
+    name, rest = args[0], args[1:]
+    want, _, fn = QUERIES[name]
+    if len(rest) != len(want.split()):
+        return usage(f"jsk kb query {name} {want}".rstrip())
+    columns, rows = fn(S.load(root), *rest)
+    print(json.dumps(rows, indent=2, ensure_ascii=False) if as_json else table(columns, rows))
+    return 0
+
+
+@verb
+def cmd_check(args, root):
+    """jsk kb check
+
+    Validates the whole workspace - every rule, every file - and says where kb.ttl and
+    log.ttl stand, and which record files are not in the canonical layout. Exit 1 on any
+    FAIL; a WARN is printed and passes.
+    """
+    from ..gates.validate_urs import show
+    from . import record as R
+    from . import store as S
+    from .writer import WriteError, write
+
+    if args:
+        return usage("jsk kb check takes no arguments")
+    store = S.load(root)
+    rep = store.report()
+    for name, parsed in sorted(store.parsed.items()):
+        if parsed.kind in ("kb", "log", "posting", "application"):
+            try:
+                if write(parsed.quads, parsed.kind) != parsed.text:
+                    rep.warn(f"{name} - not in the canonical layout\n        fix: `jsk kb fmt {name}`")
+            except WriteError:
+                pass                     # a file the writer cannot lay out has a FAIL already
+    st = R.state(store)
+    print(f"record   {st.kind}" + (f" at r{st.log_revision}" if st.log_revision else "")
+          + (f" - {st.detail}" if st.detail else ""))
+    print(f"{len(rep.fails)} FAIL, {len(rep.warns)} WARN")
+    show(rep.fails, "FAIL", 0)
+    show(rep.warns, "WARN", 0)
+    return 1 if rep.fails else 0
+
+
 def main(argv=None):
     args = list(sys.argv[1:] if argv is None else argv)
     if not args or (wants_help(args) and args[0] not in VERBS):
```

```diff
--- a/src/jsk/preflight.py
+++ b/src/jsk/preflight.py
@@ -48,7 +48,7 @@ MODULES = ["cli", "cliutil", "kb", "kbindex", "paths"]
 # a machine without the engine - the engine is its own check below.
 GRAPH_MODULES = ["graph", "graph.ontology", "graph.io", "graph.writer", "graph.shapes",
                  "graph.rules", "graph.store", "graph.queries", "graph.match", "graph.record",
-                 "graph.changeset", "graph.edit", "graph.kbcli"]
+                 "graph.changeset", "graph.edit", "graph.kbcli", "graph.named", "graph.view"]
 GATE_MODULES = ["gates", "gates.check_ats", "gates.check_prose", "gates.validate_urs"]
 # Rendering, the preview and the page fitter moved in here: they drive the
 # record->document pipeline and import nothing else, so a broken urs package takes all
```

- [ ] **Step 5: Run them to see them pass**

Run: `python -m pytest tests/test_graph_kbcli.py -q`
Expected: PASS (47 tests). `test_a_revised_metric_makes_the_application_that_sent_it_stale` is the roadmap's end-to-end check 7: a metric revised through apply, and `kb query stale` naming the application that sent the old number.

- [ ] **Step 6: Document them, and amend the P1 spec**

````diff
--- a/docs/SCRIPTS.md
+++ b/docs/SCRIPTS.md
@@ -223,6 +223,23 @@ its own (`by fmt`, the day unchanged) so no content change hides in a reformat.
 or `application.ttl` is rewritten in place, unlogged. Hand comments would be lost: `adopt` and
 `fmt` refuse a file with any, listing them, unless `--drop-comments`.
 
+```bash
+jsk kb show prj_payments met_settlement  # the entries, and the op:base to draft against
+jsk kb view --section Projects           # the career as Markdown, to read
+jsk kb query unconfirmed --json          # open | unconfirmed | holds <concept> | stale
+jsk kb check                             # every rule, the record's state, the layout
+```
+
+**`show`** prints entries exactly as their files hold them - a project with its bullets, a
+metric with its versions, a concept from the vocabulary and from `kb.ttl` - under a first line
+naming the revision to put in `op:base`. **`view`** is the whole career as Markdown in `kb.ttl`'s
+section order, entries not confirmed and retired ones marked; it goes to stdout and never to a
+file, so it cannot drift from the record. **`query`** answers a named question as a table or
+`--json`: `open` questions, `unconfirmed` entries with the question open about each, the projects
+that `holds` a concept (or one that counts as it, with the evidence), and `stale` - applications
+that sent a metric version since replaced. **`check`** runs every rule over the workspace, says
+where `kb.ttl` and `log.ttl` stand, and names files out of the canonical layout; exit 1 on a FAIL.
+
 Exit 0 written, or nothing to change; 1 refused, with every reason; 2 called wrong.
 
 ### `jsk validate`
````

```diff
--- a/docs/superpowers/specs/2026-09-24-graph-core-design.md
+++ b/docs/superpowers/specs/2026-09-24-graph-core-design.md
@@ -101,7 +101,7 @@ pattern, since URS keeps its own precision.
 
 | Section | Class (id) | Predicates |
 |---|---|---|
-| (header) | KB `k:kb` | format 1 (= 3), name 1, updated 1 (date) |
+| (header) | KB `k:kb` | format 1 (= 3), name 1, updated 1 (date), revision ? (the log revision it was written at; P3) |
 | Identity | Person `k:person` | **fullName** 1, givenName ?, familyName ?, **headline** ?, city ?, region ?, country ? (ISO 3166-1 alpha-2), workMode ? (onsite·hybrid·remote), email *, phone *, linkedin *, github *, website *, primary ? (a literal equal to one of the contact values) |
 | Positioning | Person `k:person` | positioning ? (prose) - the one predicate whose section differs from its class's |
 | Work authorization and languages | WorkAuthorization `auth_` | jurisdiction 1, **kind** 1 (citizen·permanent·employment-visa·residence·student·working-holiday·none), **authorization** 1 (held·expired·eligible·requires-sponsorship), validUntil ? |
@@ -130,9 +130,9 @@ live on its versions, so a bullet cites `met_x` and the current version is resol
 | | Requirement `req_<stem>_<term>` | posting 1, asked 1 (the term as written), quote 1 (the advert's words), necessity 1 (required·preferred·implicit), concept ? (-> Concept: the analyst's choice when a label is ambiguous) |
 | application.ttl | Application `app_` | posting 1, view ?, submitted 1 (date, or `false` when held back), channel ?, document *, recordSha256 ?, carried * (-> Achievement), carriedVersion * (-> MetricVersion) |
 | | Event `evt_<stem>_<date>_<kind>` | application 1, date 1 (date, or `"unknown"`), kind 1 (the pipeline vocabulary: submitted·acknowledged·screen-scheduled·screen-done·interview-scheduled·interview-done·onsite-scheduled·onsite-done·offer·offer-accepted·rejected·withdrawn·no-response·offer-declined·follow-up-sent·note·referral·recruiter-contact), channel ?, note ?, due ? (date) |
-| log.ttl | LogEntry `rev_<N>` | revision 1, date 1, by 1 (apply·confirm·adopt·migrate·fmt), summary 1, touched *, minted *, answer ? (only with `by confirm`), kbSha256 1 |
+| log.ttl | LogEntry `rev_<N>` | revision 1, date 1, by 1 (apply·confirm·adopt·migrate·fmt), summary 1, touched * (k: ids and concepts), minted *, answer ? (only with `by confirm`), kbSha256 1 |
 | vocabulary.ttl | Concept `c:` | as in kb.ttl, restricted to Technology with no `implies` (a P2 rule) |
-| changeset.trig | reserved graphs | `op:set`, `op:add`, `op:retire`, `op:delete`, and the triple `op:base op:revision "rN"`. P1 names them; P3 gives them meaning |
+| changeset.trig | reserved graphs | `op:set`, `op:add`, `op:retire`, `op:delete`, and the header `op:changeset op:base N ; op:summary "…"`. P1 names them; P3 gives them meaning (docs/superpowers/plans/2026-09-24-graph-write.md) |
 
 **Across files:** a concept in kb.ttl may extend one the shipped vocabulary defines (more labels, more
 edges) - the person's vocabulary layered over the shipped one. A `k:` subject defined in two files
@@ -247,7 +247,7 @@ Named so nothing is forgotten; each phase owns its rule.
 |---|---|---|
 | requirement `quote` appears verbatim in posting.md | reads a Markdown file, not the graph | P2 |
 | shipped vocabulary: Technology only, no `implies` | a property of the shipped data P2 writes | P2 |
-| kb.ttl changed outside `jsk kb apply` (hash in log.ttl) | needs apply to write the hash | P3 |
+| kb.ttl changed outside `jsk kb apply` (hash in log.ttl) | needs apply to write the hash | P3: done, `hand-edited` and `log-sync` |
 | a carried metric version was changed | needs history - the log's hashes | P5 |
 
 **Mutation sweep.** For every rule: the valid fixture plus one edit must produce exactly that rule's
```

- [ ] **Step 7: The whole suite, lint, the load budget, commit**

Run: `python -m pytest tests -q -n auto` then `python -m ruff check src tests`
Expected: PASS; `All checks passed!`

Run: `python -m pytest tests/test_graph_budget.py -q -s`
Expected: PASS, `budget: 16373 quads loaded and validated in` about 300 ms (1,200 is the ceiling).

```bash
git add src/jsk/graph/named.py src/jsk/graph/view.py src/jsk/graph/kbcli.py src/jsk/preflight.py docs/SCRIPTS.md docs/superpowers/specs/2026-09-24-graph-core-design.md tests/test_graph_kbcli.py
git commit -m "feat: jsk kb show, view, query and check - the record read by id, whole, by question, and checked"
```

---

## The roadmap's P3 tests, and where each is

| Roadmap | Test |
|---|---|
| one per refusal | `tests/test_graph_changeset.py::Refusals` (17), `tests/test_graph_edit.py` (the record's refusals), `test_graph_kbcli.py::Apply` (guards) |
| confirm-by-changeset refused | `test_graph_changeset.py::Refusals::test_confirmed_provenance` |
| torn write detected | `test_graph_record.py::test_a_lock_that_holds_on_log_is_a_torn_write_the_next_load_names`, `test_graph_rules.py::test_a_write_that_reached_only_kb_ttl_is_named_torn` |
| hand edit detected / adopted with upgrades listed | `test_graph_rules.py` (`hand-edited` mutation), `test_graph_kbcli.py::Adopt::test_a_hand_edit_is_logged_with_what_it_raised` |
| `--dry-run` touches no mtime | `test_graph_kbcli.py::Apply::test_a_dry_run_writes_nothing` |
| `-` refused | `test_graph_kbcli.py::Apply::test_stdin_is_refused` |
| Windows lock retry | `test_graph_record.py::test_a_lock_that_clears_is_waited_out`, `..._holds_on_kb_changes_nothing` |
| metric versioning | `test_graph_edit.py::Versions` (4) |
| `op:base` conflict | `test_graph_edit.py::Base` (3) |
| **Exit:** scripted braindump → valid kb.ttl with correct diff | `test_graph_kbcli.py::Apply::test_a_braindump_becomes_a_valid_logged_record` |
