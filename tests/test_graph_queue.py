"""Writers queue, and a write that queued behind another rebases onto what it left.

Each test runs `jsk kb` as a person's session would - `python -m jsk.cli kb ...` in its
own process - against one workspace's career/store/. Ruling 7: nobody is refused for
being second; a write drafted at an op:base the record has since moved past lands when
it names no id changed since, and is refused - by the base check, or by the rules run
again over the record as it now is - when it would silently undo or break what landed.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import storekit
from fixtures import CLI, child_env
from test_graph_changeset import PFX
from test_graph_shapes import FIXTURES

from jsk.infra.oxigraph import db
from jsk.domain.record import edit
from jsk.domain import ontology as O
from jsk.infra.oxigraph import record as R
from jsk.graph import store as S


def jsk(root, *args):
    """Start `jsk kb <args> --root root` in a process of its own."""
    return subprocess.Popen([sys.executable, "-m", CLI, "kb", *map(str, args), "--root", root],
                            env=child_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8")


def done(proc):
    out, _ = proc.communicate(timeout=120)
    return proc.returncode, out


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(FIXTURES, self.root, dirs_exist_ok=True)
        storekit.seed(self.root)
        self.n = 0

    def changeset(self, body):
        self.n += 1
        path = os.path.join(self.root, f"change{self.n}.trig")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(PFX + body)
        return path

    def apply(self, body):
        return done(jsk(self.root, "apply", self.changeset(body)))

    def record(self):
        return db.dump_text(db.read(self.root))

    def entries(self):
        """{revision: (by, {touched ∪ minted})} of the log as the store holds it."""
        s = S.load(self.root)
        by = {}
        for q in s.graph(R.LOG):
            e = by.setdefault(q.subject.value, {"ids": set()})
            name = q.predicate.value[len(O.J):]
            if name == "revision":
                e["revision"] = int(q.object.value)
            elif name == "by":
                e["by"] = q.object.value[len(O.J):]
            elif name in ("touched", "minted"):
                e["ids"].add(q.object.value)
        return {e["revision"]: (e["by"], e["ids"]) for e in by.values()}

    def value(self, subject, pred):
        s = S.load(self.root)
        return sorted(q.object.value for q in s.graph(R.KB)
                      if q.subject.value == O.K + subject and q.predicate.value == O.J + pred)


class Queue(Workspace):
    DISJOINT = ("op:changeset op:base 2 .\nop:set { k:prj_clinical_events j:strength 4 . }\n",
                "op:changeset op:base 2 .\nop:set { k:prj_site_onboarding j:strength 4 . }\n",
                "op:changeset op:base 2 .\n"
                'op:add { c:queue-work a j:Capability ; j:label "queue work" . }\n',
                "op:changeset op:base 2 .\nop:set { k:met_sites.v1 j:value 43 . }\n")

    def test_four_writers_drafted_at_one_base_all_land_as_consecutive_revisions(self):
        paths = [self.changeset(body) for body in self.DISJOINT]
        procs = [jsk(self.root, "apply", p) for p in paths]        # started together
        results = [done(p) for p in procs]
        self.assertEqual([code for code, _ in results], [0, 0, 0, 0],
                         "\n\n".join(out for _, out in results))
        landed = sorted(int(re.search(r"^r(\d+) written", out, re.M).group(1))
                        for _, out in results)
        self.assertEqual(landed, [3, 4, 5, 6])
        self.assertEqual(sorted(self.entries()), [1, 2, 3, 4, 5, 6])
        st = R.state(S.load(self.root))
        self.assertEqual((st.kind, st.kb_revision), ("clean", 6))
        self.assertEqual(self.value("prj_clinical_events", "strength"), ["4"])
        self.assertEqual(self.value("prj_site_onboarding", "strength"), ["4"])
        self.assertEqual(self.value("met_sites.v1", "value"), ["43"])
        self.assertIn(O.C + "queue-work", S.load(self.root).homes)

    def test_of_two_overlapping_writers_the_second_is_refused_and_changes_nothing(self):
        paths = [self.changeset("op:changeset op:base 2 .\n"
                                f"op:set {{ k:prj_clinical_events j:strength {n} . }}\n")
                 for n in (4, 3)]
        procs = [jsk(self.root, "apply", p) for p in paths]
        results = [done(p) for p in procs]
        codes = sorted(code for code, _ in results)
        self.assertEqual(codes, [0, 1], "\n\n".join(out for _, out in results))
        [won] = [n for (code, _), n in zip(results, (4, 3), strict=True) if code == 0]
        [lost_out] = [out for code, out in results if code == 1]
        self.assertIn("k:prj_clinical_events - changed at r3, after this changeset's op:base r2",
                      lost_out)
        self.assertIn("nothing was written", lost_out)
        self.assertEqual(sorted(self.entries()), [1, 2, 3])
        self.assertEqual(self.value("prj_clinical_events", "strength"), [str(won)])

    def test_a_rebase_that_breaks_a_rule_is_refused_by_the_rule(self):
        """The two share no id: the base check lets the second through, and the rules, run
        again over the record the first left, refuse it."""
        code, out = self.apply(
            'op:add { k:met_standalone j:subject "standalone things" ; j:unit "things" .\n'
            "    k:met_standalone.v1 j:of k:met_standalone ; j:value 3 ; "
            "j:confidence j:measured . }\n")
        self.assertEqual(code, 0, out)
        drop = self.changeset("op:changeset op:base 3 .\n"
                              "op:delete { k:met_standalone a op:Entry . "
                              "k:met_standalone.v1 a op:Entry . "
                              "k:q_met_standalone_v1 a op:Entry . }\n")
        cite = self.changeset("op:changeset op:base 3 .\n"
                              "op:add { [] j:project k:prj_clinical_events ; j:rank 3 ;\n"
                              '    j:text "Counted 3 standalone things." ; '
                              "j:cites k:met_standalone . }\n")
        self.assertEqual(done(jsk(self.root, "apply", drop))[0], 0)
        before = self.record()
        code, out = done(jsk(self.root, "apply", cite))
        self.assertEqual(code, 1, out)
        self.assertIn("j:cites k:met_standalone: nothing defines it", out)
        self.assertNotIn("after this changeset's op:base", out)
        self.assertEqual(self.record(), before)

    def test_a_number_the_store_would_rewrite_is_refused_with_the_form_it_keeps(self):
        code, out = self.apply("op:set { k:met_sites.v1 j:value 8.4 . }\n")
        self.assertEqual(code, 0, out)
        before = self.record()
        code, out = self.apply("op:set { k:met_sites.v1 j:value 8.40 . }\n")
        self.assertEqual(code, 1, out)
        self.assertIn("j:value 8.40 is kept as 8.4", out)
        self.assertIn("fix: write 8.4", out)
        self.assertEqual(self.record(), before)
        # and what it asks for is already there
        code, out = self.apply("op:set { k:met_sites.v1 j:value 8.4 . }\n")
        self.assertEqual((code, "nothing to change" in out), (0, True), out)


class TouchedIsComplete(Workspace):
    """Rebase trusts the log: a write whose entry leaves out an id it changed would let a
    changeset drafted before it overwrite that id unrefused. So for every kind of change,
    touched ∪ minted is exactly the subjects whose triples differ between the revisions."""

    STEPS = (
        ("apply", "a project, its bullets, a metric and a concept", """
op:add {
    k:prj_payments j:name "Payments platform" ; j:position k:pos_meridian_principal ;
        j:strength 4 ; j:recency 2025 ; j:uses c:kafka, c:payments ;
        j:headlineMetric k:met_settlement .
    [] j:project k:prj_payments ; j:rank 1 ;
        j:text "Cut settlement latency from 800 ms to 200 ms." ; j:cites k:met_settlement .
    [] j:project k:prj_payments ; j:rank 2 ; j:text "Moved card payments onto events." .
    k:met_settlement j:subject "settlement latency" ; j:unit "ms" ; j:direction j:decrease .
    k:met_settlement.v1 j:of k:met_settlement ; j:baseline 800 ; j:value 200 ;
        j:confidence j:reported .
    c:payments a j:Domain ; j:label "payments" .
}
"""),
        ("apply", "a claim reworded: unconfirmed, and asked about",
         'op:set { k:ach_clinical_events_led_migration j:text "Led 6 engineers through it." ;\n'
         "    j:shows c:team-leadership . }\n"),
        ("apply", "a field that is not a claim, and a triple deleted",
         "op:set { k:prj_clinical_events j:strength 4 . }\n"
         "op:delete { k:ach_site_onboarding_sites_one_platform j:cites k:met_sites . }\n"),
        ("apply", "a sent metric's new number: the next version, the old one closed",
         "op:set { k:met_team.v1 j:value 7 . }\n"),
        ("apply", "a retire, and a whole entry deleted",
         'op:retire { k:prj_site_onboarding j:reason "Folded into the platform work." . }\n'
         "op:delete { k:q_team_size a op:Entry . }\n"),
        ("confirm", "confirmed, answering the open questions",
         ("k:ach_clinical_events_led_migration", "k:met_team.v2",
          "--answer", "Yes - six engineers then, seven once the team grew.")),
    )

    def subjects(self, graph):
        stamp = {(O.K + "kb", O.J + "revision"), (O.K + "kb", O.J + "updated")}
        return {(q.subject.value, q.predicate.value, str(q.object)) for q in graph
                if (q.subject.value, q.predicate.value) not in stamp}

    def test_every_write_logs_every_id_it_changed(self):
        for verb, what, body in self.STEPS:
            with self.subTest(what):
                before = S.load(self.root)
                was = self.subjects(before.graph(R.KB))
                rev = R.state(before).log_revision
                args = (self.changeset(body),) if verb == "apply" else body
                code, out = done(jsk(self.root, verb, *args))
                self.assertEqual(code, 0, out)
                after = S.load(self.root)
                self.assertEqual(R.state(after).log_revision, rev + 1, out)
                changed = {s for s, _, _ in was ^ self.subjects(after.graph(R.KB))}
                by, named = self.entries()[rev + 1]
                self.assertEqual(by, verb)
                self.assertTrue(changed)
                self.assertEqual(named, changed)
                # and it is what base_conflicts reads back
                self.assertEqual(edit.log_entries(after)[-1], (rev + 1, changed))

    def test_a_pack_applied_logs_every_concept_it_added_or_enriched(self):
        pack = os.path.join(self.root, "pack.trig")
        code, out = done(jsk(self.root, "pack", "capabilities", "--out", pack))
        self.assertEqual(code, 0, out)
        before = self.subjects(S.load(self.root).graph(R.KB))
        code, out = done(jsk(self.root, "apply", pack))
        self.assertEqual(code, 0, out)
        changed = {s for s, _, _ in before ^ self.subjects(S.load(self.root).graph(R.KB))}
        self.assertEqual(self.entries()[3][1], changed)


if __name__ == "__main__":
    unittest.main()
