"""`jsk kb pack capabilities`: the starter pack, and the changeset that adopts it.

The pack ships to everyone, like the vocabulary, but it is judgement, so it is never
loaded as vocabulary: it reaches a record only as a changeset the person applies.
"""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import storekit
from test_graph_shapes import FIXTURES

import jsk
from jsk import cli
from jsk.infra.oxigraph import codec
from jsk.infra import files
from jsk.domain import ontology as O
from jsk.infra.oxigraph import record
from jsk.domain.record import writer
from jsk.adapters.cli.compose import record as S
from jsk.infra import legacy_import
from jsk.infra.packs import PACKS

PACK = Path(jsk.__file__).parent / "data" / "capabilities.ttl"
SHIPPED = Path(jsk.__file__).parent / "data" / "vocabulary.ttl"


def quads(path):
    return codec.parse_text(Path(path).read_text(encoding="utf-8"), "capabilities.ttl",
                          kind="vocabulary").quads


def edit_career(case, root, old, new):
    """Change the stored career as a write would leave it - the header, so the revision,
    as it was: the edit stands for one made before the fixture's last revision."""
    text = storekit.kb_text(root)
    case.assertIn(old, text)
    record.write_graphs(str(root), {record.KB: codec.parse_text(text.replace(old, new),
                                                              record.KB).quads})
    storekit.rehash(root)


class Fixture(unittest.TestCase):
    """A copy of the fixture workspace, and `jsk kb` run on it."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.seed()

    def seed(self):
        storekit.seed(self.root)

    def path(self, name):
        return Path(self.root) / name

    def kb(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["jsk", "kb", *args, "--root", self.root])
        return code, out.getvalue(), err.getvalue()

    def apply(self, path, dry_run=False):
        """career_apply (career_preview with `dry_run`) on the changeset file at `path`, as
        `kb` returns a verb's result: (exit code, output, stderr)."""
        import recordkit

        with open(path, encoding="utf-8") as f:
            code, out = recordkit.apply(self.root, f.read(), dry_run=dry_run)
        return code, out, ""

    def edit_kb(self, old, new):
        edit_career(self, self.root, old, new)

    def pack(self, name="pack.trig"):
        code, out, err = self.kb("pack", "capabilities", "--out", str(self.path(name)))
        return code, out + err


class ThePack(unittest.TestCase):
    def test_it_holds_capabilities_and_domains_only_and_no_implies(self):
        q = quads(PACK)
        kinds = {x.object.value for x in q if x.predicate.value == O.RDF_TYPE}
        self.assertEqual(kinds, {O.J + "Capability", O.J + "Domain"})
        preds = {x.predicate.value for x in q}
        for banned in ("implies", "unlabel", "unlink"):
            self.assertNotIn(O.J + banned, preds)
        self.assertTrue(80 <= len({x.subject.value for x in q}) <= 130)

    def test_it_is_canonical(self):
        text = PACK.read_bytes().decode("utf-8")
        self.assertEqual(writer.write(codec.parse_text(text, "x.ttl", kind="vocabulary").quads,
                                      "vocabulary"), text)

    def test_no_label_is_a_shipped_label_or_id_or_another_pack_concept_s(self):
        shipped = {O.norm(x.object.value) for x in files.parse(SHIPPED).quads
                   if x.predicate.value in (O.J + "label", O.J + "former")}
        shipped |= {x.subject.value[len(O.C):] for x in files.parse(SHIPPED).quads}
        owners = {}
        q = quads(PACK)
        for x in q:
            owners.setdefault(x.subject.value[len(O.C):], set()).add(x.subject.value)
            if x.predicate.value == O.J + "label":
                owners.setdefault(O.norm(x.object.value), set()).add(x.subject.value)
        self.assertEqual({n for n in owners if n in shipped}, set())
        self.assertEqual({n: o for n, o in owners.items() if len(o) > 1}, {})

    def test_every_edge_lands_in_the_pack(self):
        q = quads(PACK)
        subjects = {x.subject.value for x in q}
        for x in q:
            if x.predicate.value in (O.J + "isA", O.J + "partOf", O.J + "distinct"):
                self.assertIn(x.object.value, subjects)

    def test_it_is_never_loaded_as_vocabulary(self):
        self.assertEqual(PACKS["capabilities"], str(PACK))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotIn(str(PACK), legacy_import.workspace_files(tmp))
            s = S.load(tmp)
        self.assertNotIn(O.C + "system-design", s.homes)
        self.assertEqual(O.kind_of(PACK), None)

    def test_a_two_line_summary_round_trips(self):
        from jsk.domain.record.pack import trig

        summary = 'Merged c:a into c:b.\nThe "old" wording stays as a label.'
        text = trig(2, summary, {})
        said = [q.object.value for q in codec.parse_text(text, "x.trig", kind="changeset").quads
                if q.predicate.value == O.OP + "summary"]
        self.assertEqual(said, [summary])

    def test_the_shipped_vocabulary_is_still_technologies_only(self):
        kinds = {x.object.value for x in files.parse(SHIPPED).quads
                 if x.predicate.value == O.RDF_TYPE}
        self.assertEqual(kinds, {O.J + "Technology"})


class InARecord(Fixture):
    def test_the_pack_beside_the_shipped_vocabulary_fails_nothing_and_clashes_nothing(self):
        both = list(S.load(self.root).graph(record.KB)) + list(quads(PACK))
        s = S.load(self.root, graphs={record.KB: both})
        self.assertEqual([f.text() for f in s.fails() if f.rule != "log-sync"], [])
        self.assertEqual([f.text() for f in s.findings
                          if f.rule in ("label-clash", "wall-crossed", "counts-as-cycle",
                                        "concept-reclassed", "concepts-bare")], [])

    def test_the_changeset_dry_runs_clean(self):
        code, out = self.pack()
        self.assertEqual(code, 0, out)
        self.assertIn("concepts added", out)
        text = self.path("pack.trig").read_text(encoding="utf-8")
        self.assertIn("op:changeset op:base 2 ;", text)
        self.assertIn("c:system-design a j:Capability", text)
        code, out, _ = self.apply(str(self.path("pack.trig")), dry_run=True)
        self.assertEqual(code, 0, out)
        self.assertIn("dry run: r3 not written", out)

    def test_a_concept_the_record_has_gets_only_what_it_lacks(self):
        from jsk.adapters.cli.compose import record as changeset

        self.pack()
        cs = changeset.read_changeset(self.path("pack.trig").read_text(encoding="utf-8"))
        eda = {(p.value[len(O.J):] if p.value.startswith(O.J) else "a", o.value)
               for s, p, o in cs.add if s.value == O.C + "event-driven-architecture"}
        # Its class and its own "EDA" stay as they are; the pack adds its other wordings
        # and its edges.
        self.assertNotIn("a", {p for p, _ in eda})
        self.assertIn(("label", "event-driven systems"), eda)
        self.assertIn(("isA", O.C + "distributed-systems"), eda)
        self.assertEqual(cs.set + cs.retire + cs.delete, [])

    def test_adopted_once_there_is_nothing_more_to_add(self):
        self.assertEqual(self.pack()[0], 0)
        code, out, _ = self.apply(str(self.path("pack.trig")))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.kb("check")[0], 0)
        code, out = self.pack("again.trig")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to add", out)
        self.assertFalse(self.path("again.trig").exists())

    def test_to_stdout_the_changeset_and_to_stderr_what_was_skipped(self):
        self.edit_kb("c:healthcare a j:Domain .", "c:healthcare a j:Domain .\n"
                     "c:mentoring a j:Domain .")
        code, out, err = self.kb("pack", "capabilities")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(out.startswith("@prefix j:"))
        self.assertNotIn("skipped  ", out)
        self.assertIn("skipped  c:mentoring", err)

    def test_a_concept_of_another_class_is_skipped_and_said(self):
        self.edit_kb("c:healthcare a j:Domain .", "c:healthcare a j:Domain .\n"
                     "c:mentoring a j:Domain .\nc:ai-agents a j:Technology .")
        code, out = self.pack()
        self.assertEqual(code, 0, out)
        self.assertIn("skipped  c:mentoring: the pack has it as a Capability, the record as "
                      "Domain", out)
        # Its edges go with it, and so does an edge pointing at it.
        self.assertIn("skipped  c:agent-orchestration j:isA c:ai-agents: c:ai-agents was "
                      "skipped", out)
        text = self.path("pack.trig").read_text(encoding="utf-8")
        self.assertNotIn("c:mentoring", text)
        self.assertNotIn("c:ai-agents", text)
        self.assertEqual(self.apply(str(self.path("pack.trig")), dry_run=True)[0], 0)

    def test_a_label_that_names_another_concept_is_skipped_and_said(self):
        self.edit_kb("c:healthcare a j:Domain .", "c:healthcare a j:Domain .\n"
                     'c:my-rag a j:Capability ; j:label "retrieval-augmented generation" .\n'
                     "c:tech-lead a j:Capability ; j:isA c:team-leadership .")
        code, out = self.pack()
        self.assertEqual(code, 0, out)
        self.assertIn("skipped  label 'retrieval-augmented generation' on c:rag: it already "
                      "names c:my-rag", out)
        # An id is a name too: matching reads c:tech-lead as "tech lead".
        self.assertIn("skipped  label 'tech lead' on c:technical-leadership: it already names "
                      "c:tech-lead", out)
        code, out, _ = self.apply(str(self.path("pack.trig")))
        self.assertEqual(code, 0, out)
        self.assertEqual([f.text() for f in self.loaded().findings if f.rule == "label-clash"],
                         [])

    def test_an_edge_across_a_distinct_wall_is_skipped_and_said(self):
        self.edit_kb("c:healthcare a j:Domain .", "c:healthcare a j:Domain .\n"
                     "c:distributed-systems a j:Capability ; "
                     "j:distinct c:event-driven-architecture .")
        code, out = self.pack()
        self.assertEqual(code, 0, out)
        self.assertIn("skipped  c:event-driven-architecture j:isA c:distributed-systems:", out)
        self.assertIn("they are distinct", out)
        code, out, _ = self.apply(str(self.path("pack.trig")))
        self.assertEqual(code, 0, out)
        self.assertEqual([f.text() for f in self.loaded().findings if f.rule == "wall-crossed"],
                         [])

    def test_called_wrong(self):
        self.assertEqual(self.kb("pack")[0], 2)
        self.assertEqual(self.kb("pack", "technologies")[0], 2)
        self.assertEqual(self.kb("pack", "capabilities", "--out", "x.ttl")[0], 2)

    def loaded(self):
        return S.load(self.root)


if __name__ == "__main__":
    unittest.main()
