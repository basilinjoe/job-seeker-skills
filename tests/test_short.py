"""The short resume.json: what one application chose, and nothing the career holds.

Reading it, finding the workspace it belongs to, and the two ways it can be wrong -
its own shape, and ids the career does not hold."""
import json
import tempfile
import unittest
from pathlib import Path

import careerkit
from jsk.domain.resume import short
from jsk.adapters.cli.compose import resume
from jsk.adapters.cli.gates import short as own_check

OK = {"resume": 2, "bullets": ["ach_events_latency", "ach_identity_sso"]}


class Read(unittest.TestCase):
    def test_a_short_file_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(tmp, short=OK)
            self.assertEqual(resume.read(path)["bullets"], OK["bullets"])
            self.assertEqual(Path(resume.workspace(path)), Path(root))

    def test_a_legacy_record_points_at_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"urs": "1.0.0"}), encoding="utf-8")
            with self.assertRaises(short.ShortError) as err:
                resume.read(p)
            # The file named: the short one is written over it.
            self.assertIn(f"jsk kb export --select <id>... --out {p}", err.exception.fix)

    def test_not_json_and_missing_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text("{not json", encoding="utf-8")
            with self.assertRaises(short.ShortError):
                resume.read(p)
            with self.assertRaises(short.ShortError):
                resume.read(Path(tmp, "absent.json"))

    def test_a_cp1252_file_is_refused_as_not_utf8(self):
        """A person edits resume.json - a summary with a Windows editor's curly quote.
        The fix is to save it as UTF-8, not to fix JSON that is fine."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_bytes(b'{"resume": 2, "summary": {"text": "\x93Led\x94 it"}}')
            with self.assertRaises(short.ShortError) as err:
                resume.read(p)
            self.assertIn("not UTF-8", str(err.exception))
            self.assertIn("UTF-8", err.exception.fix)

    def test_a_bom_and_crlf_still_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_bytes(b'\xef\xbb\xbf' + json.dumps(OK, indent=2).encode().replace(b"\n", b"\r\n"))
            self.assertEqual(resume.read(p)["bullets"], OK["bullets"])

    def test_another_version_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"resume": 3, "bullets": []}), encoding="utf-8")
            with self.assertRaises(short.ShortError):
                resume.read(p)

    def test_outside_a_workspace_is_refused_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps(OK), encoding="utf-8")
            with self.assertRaises(short.ShortError) as err:
                resume.workspace(p)
            self.assertIn("career/store/", err.exception.fix)

    def test_a_workspace_named_career_is_found(self):
        # The real one holds career/career/store/: the parent of the file's folder's
        # parent is the wrong answer, so the walk up is the only right one.
        with tempfile.TemporaryDirectory() as tmp:
            root, path = careerkit.workspace(Path(tmp, "career"), short=OK)
            self.assertEqual(Path(resume.workspace(path)), Path(root))


class Shape(unittest.TestCase):
    def check(self, **change):
        return short.shape({**OK, **change})

    def test_clean(self):
        self.assertEqual(short.shape(OK), [])
        self.assertEqual(self.check(format="ats-maximal", region="au", pages=2, ats_pages=3,
                                    floor="inferred", roles=["pos_meridian_lead"],
                                    skills=["skill_kubernetes"],
                                    summary={"text": "Platform engineer.", "status": "inferred"}),
                         [])

    def test_unknown_key(self):
        self.assertTrue(any("views" in f for f in self.check(views=[])))

    def test_no_bullets(self):
        self.assertTrue(self.check(bullets=[]))
        self.assertTrue(short.shape({"resume": 2}))

    def test_bad_format_status_and_floor(self):
        self.assertTrue(self.check(format="web"))
        self.assertTrue(self.check(summary={"text": "x", "status": "disputed"}))
        self.assertTrue(self.check(summary={"status": "inferred"}))
        self.assertTrue(self.check(floor="sure"))

    def test_a_confirmed_summary_carries_its_answer_and_hash(self):
        """Flipping "status" to confirmed by hand confirmed a summary with no answer and
        no audit, and an edit afterwards kept it confirmed."""
        summary = short.confirmed({"text": "Platform engineer.", "status": "inferred"},
                                  "Yes, that is me in one line.")
        self.assertEqual(list(summary), ["text", "status", "answer", "text_sha256"])
        self.assertEqual(summary["text_sha256"], short.digest("Platform engineer."))
        self.assertEqual(len(summary["text_sha256"]), 12)
        self.assertEqual(self.check(summary=summary), [])
        flipped = self.check(summary={"text": "Platform engineer.", "status": "confirmed"})
        self.assertTrue(any("records no answer" in f and "jsk kb confirm --summary" in f
                            for f in flipped), flipped)
        for said in ("yes", "ok", "No."):
            with self.subTest(said=said):
                self.assertTrue(self.check(summary={**summary, "answer": said}))
        edited = self.check(summary={**summary, "text": "Platform engineer and leader."})
        self.assertTrue(any("changed since it was confirmed" in f
                            and "jsk kb confirm --summary" in f for f in edited), edited)
        self.assertTrue(any("text_sha256" in f for f in self.check(
            summary={k: v for k, v in summary.items() if k != "text_sha256"})))
        # An inferred summary needs neither.
        self.assertEqual(self.check(summary={"text": "Platform engineer.", "status": "inferred"}), [])

    def test_a_region_is_a_two_letter_code(self):
        """Final review: "aus" validated and rendered the default profile - two pages and
        no work-rights line - over the person's AU country that would have been right."""
        self.assertTrue(any("region" in f for f in self.check(region="aus")))
        self.assertTrue(self.check(region="Australia"))
        for good in ("au", "in", "us", "xx"):
            self.assertEqual(self.check(region=good), [], good)

    def test_wrong_types(self):
        self.assertTrue(self.check(pages="2"))
        self.assertTrue(self.check(bullets="ach_events_latency"))
        self.assertTrue(self.check(pages=0))

    def test_a_headline_is_held_to_the_summary_s_rules(self):
        """The posting's title under the name is prose the person must stand behind, so a
        hand-set confirmed headline fails as a hand-set confirmed summary does."""
        headline = {"text": "Senior Platform Engineer", "status": "inferred"}
        self.assertEqual(self.check(headline=headline), [])
        flipped = self.check(headline={**headline, "status": "confirmed"})
        self.assertTrue(any("headline is confirmed but records no answer" in f
                            and "jsk kb confirm --headline" in f for f in flipped), flipped)
        earned = short.confirmed(headline, "Yes, that is the title I hold.")
        self.assertEqual(self.check(headline=earned), [])
        self.assertTrue(self.check(headline={"text": "Two\nlines", "status": "inferred"}))
        self.assertTrue(self.check(headline={"text": "x", "status": "inferred", "why": "?"}))

    def test_names_maps_skill_ids_to_strings(self):
        self.assertEqual(self.check(names={"skill_kubernetes": "K8s"}), [])
        self.assertTrue(self.check(names={"ach_events_latency": "K8s"}))
        self.assertTrue(self.check(names={"skill_kubernetes": ""}))
        self.assertTrue(self.check(names=["skill_kubernetes"]))

    def test_wrong_prefix_and_duplicate(self):
        self.assertTrue(self.check(bullets=["prj_events"]))
        self.assertTrue(self.check(roles=["ach_events_latency"]))
        self.assertTrue(self.check(skills=["c:kafka"]))
        self.assertTrue(self.check(bullets=["ach_events_latency", "ach_events_latency"]))


class Example(unittest.TestCase):
    """The workspace jsk doctor renders: a small career and a short file over it. It
    ships as files, and doctor imports it into a store of its own before rendering, as
    `jsk kb load` imports a person's (preflight.verify)."""

    def stored(self):
        import shutil

        from storekit import seed

        from jsk import paths
        from jsk.adapters.cli.compose import record

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(paths.EXAMPLE_WORKSPACE, tmp, dirs_exist_ok=True)
        seed(tmp)
        return record.load(tmp)

    def test_the_example_reads_and_every_id_is_held(self):
        from jsk import paths

        doc = resume.read(paths.EXAMPLE_SHORT)
        self.assertEqual(short.shape(doc), [])
        self.assertEqual(Path(resume.workspace(paths.EXAMPLE_SHORT)),
                         Path(paths.EXAMPLE_WORKSPACE))
        self.assertEqual(short.ids(doc, self.stored()), [])

    def test_the_example_career_imports_clean(self):
        from jsk import paths
        from jsk.infra import legacy_import as legacy
        from jsk.infra.oxigraph import record as R

        imported, _, rewrites = legacy.read_workspace(paths.EXAMPLE_WORKSPACE)
        self.assertEqual(imported.fails(), [])
        self.assertEqual(R.state(imported).kind, "clean")
        self.assertEqual(rewrites, [])          # doctor's import changes no number
        store = self.stored()
        self.assertEqual(store.fails(), [])
        self.assertEqual(R.state(store).kind, "clean")


class Ids(unittest.TestCase):
    def ids(self, doc, edits=()):
        with tempfile.TemporaryDirectory() as tmp:
            root, _ = careerkit.workspace(tmp, edits=edits, short=doc)
            return short.ids(doc, careerkit.store(root))

    def test_ids_the_career_holds(self):
        self.assertEqual(self.ids(OK), [])

    def test_an_unknown_id_names_the_near_one(self):
        found = self.ids({**OK, "bullets": ["ach_events_latencyy"]})
        self.assertTrue(any("ach_events_latencyy" in f and "did you mean ach_events_latency"
                            in f for f in found), found)

    def test_a_name_must_be_the_skill_s_own_or_an_alias(self):
        """`names` picks the posting's spelling of a skill from the ones the career holds;
        a word the career lacks would be a claim nothing confirmed."""
        self.assertEqual(self.ids({**OK, "names": {"skill_kubernetes": "K8s"}}), [])
        self.assertEqual(self.ids({**OK, "names": {"skill_kubernetes": "Kubernetes"}}), [])
        found = self.ids({**OK, "names": {"skill_kubernetes": "OpenShift"}})
        self.assertTrue(any("'OpenShift', which is neither its name nor an alias" in f
                            for f in found), found)
        self.assertTrue(self.ids({**OK, "names": {"skill_nothing_here": "K8s"}}))

    def test_an_id_of_another_kind_is_refused(self):
        # Right prefix, wrong thing: a pos_ in the career's text as a skill id would not
        # be caught by the prefix check.
        self.assertTrue(self.ids({**OK, "skills": ["skill_nothing_here"]}))

    def test_a_retired_bullet_is_named_with_its_reason(self):
        # Review Focus 2: retired after the file was written.
        found = self.ids({**OK, "bullets": ["ach_events_terraform"]}, edits=[careerkit.RETIRE])
        self.assertTrue(any("ach_events_terraform" in f and "not true any more" in f
                            for f in found), found)

    def test_a_bullet_whose_role_or_project_is_retired(self):
        """Final review: a retired role passed the gate, and its live bullet then vanished
        from the render without a warning - and from what freeze carried."""
        role = ('    j:seniority j:hands-on-senior ;\n    j:provenance j:confirmed .\n',
                '    j:seniority j:hands-on-senior ;\n'
                '    j:retired "2026-09-01"^^xsd:date ; j:reason "merged into lead" ;\n'
                '    j:provenance j:confirmed .\n')
        found = self.ids({**OK, "bullets": ["ach_identity_sso"]}, edits=[role])
        self.assertTrue(any("ach_identity_sso" in f and "pos_meridian_engineer" in f
                            and "retired" in f for f in found), found)

    def test_a_bullet_whose_project_has_no_role(self):
        edit = ("k:prj_data j:name \"Data\" ;\n    j:position k:pos_lakeside_contractor ;\n",
                "k:prj_data j:name \"Data\" ;\n")
        found = self.ids({**OK, "bullets": ["ach_data_ingestion"]}, edits=[edit])
        self.assertTrue(any("ach_data_ingestion" in f and "role" in f for f in found), found)


class Main(unittest.TestCase):
    """The short file's own check of one resume.json (adapters/cli/gates/short.py): its
    shape and ids, with no gate behind it."""

    def main(self, *args):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = own_check.main(["short.py", *map(str, args)])
        return code, out.getvalue()

    def test_the_example_passes(self):
        from fixtures import example_short

        code, out = self.main(example_short())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)

    def test_a_retired_bullet_fails_naming_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, path = careerkit.workspace(
                tmp, edits=[careerkit.RETIRE],
                short={**OK, "bullets": ["ach_events_terraform"]})
            code, out = self.main(path)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("ach_events_terraform", out)
        self.assertNotIn("PASS", out)

    def test_a_legacy_record_fails_with_the_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "resume.json")
            p.write_text(json.dumps({"urs": "1.0.0"}), encoding="utf-8")
            code, out = self.main(p)
        self.assertEqual(code, 1, out)
        self.assertIn("jsk kb export", out)

    def test_called_wrong_exits_two(self):
        self.assertEqual(self.main()[0], 2)

    def test_it_runs_as_a_module(self):
        # Doctor spawns it: an entry point that only works imported proves nothing there.
        from fixtures import RECORD_GATE, example_short, run

        code, out = run(RECORD_GATE, example_short())
        self.assertEqual(code, 0, out)
        self.assertIn("PASS - safe to render", out)
