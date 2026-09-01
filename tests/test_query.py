"""The read layer's foundation: the walk, the id index, the output contract.

Four modules answer questions on top of these three, and each of those has its own
test file. What is pinned here is the part they all rest on - because a defect in the
walk or in an id is not visible in any of them. A search that missed a file, or an id
that resolved to the wrong concept, produces an answer that looks exactly like a
correct one.

Two tests in this file are load-bearing beyond their own subject:

`EveryCompiledIdResolves` is the agreement between `query/ids.py` and
`okf_compile.py`. The read layer derives ids rather than compiling, which is the whole
reason it is fast - and the cost of that choice is that two modules now know how an id
is built. This is what stops them drifting.

`NothingHereCompiles` is the design, asserted. The moment a query calls `load()` it
costs what the thing it replaces costs, and the reason for the layer is gone.
"""
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import CLI, query_bundle, query_module, run

walk = query_module("walk")
ids = query_module("ids")
render = query_module("render")
commands = query_module("commands")
okf_compile = query_module("jsk_okf.okf_compile")


class QueryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.bundle = query_bundle(self.tmp / "bundle")

    def rels(self, **kwargs):
        return [c.rel for c in walk.walk(self.bundle, **kwargs)]


# --- the walk -------------------------------------------------------------------

class TheWalk(QueryCase):
    def test_the_frozen_archive_is_not_read_by_default(self):
        """The compile skips it and so must this - but the stronger reason is that a
        frozen copy may not be edited. A hit surfaced from one sends somebody to
        change the record of what was already sent."""
        self.assertEqual([r for r in self.rels() if "applications" in r], [])

    def test_archive_admits_it_and_nothing_outside_it_is_frozen(self):
        found = {c.rel: c.frozen for c in walk.walk(self.bundle, archive=True)}
        self.assertTrue([rel for rel in found if "applications" in rel],
                        "--archive read nothing from the archive")
        self.assertFalse(any(found[rel] for rel in found if "applications" not in rel))

    def test_only_the_frozen_companions_are_frozen_not_the_application_itself(self):
        """`bundle-spec.md` draws this line and it is not a nicety. The copies frozen
        beside a sent application may not be edited - an application linking to a
        mutable posting cannot say what it was answering. **Its own `<stem>.md` is the
        opposite case:** the `# Timeline` is appended to for as long as the process is
        live, which is how a rejection gets recorded at all.

        Marking the whole directory frozen told somebody the one file in there they are
        supposed to write to was off limits. `validate_bundle.py` draws the same line -
        a problem in a frozen copy is a warning, one in the application's own file is
        still an error.
        """
        found = {c.rel: c for c in walk.walk(self.bundle, archive=True)}
        application = found["tailoring/applications/2025/"
                            "2025-11-03-kestrel-staff.md"]
        self.assertEqual(application.type, "Application")
        self.assertFalse(application.frozen, "the application's own log reads as frozen")
        for rel, concept in found.items():
            if "applications" in rel and rel != application.rel:
                self.assertTrue(concept.frozen, rel)

    def test_index_files_are_never_read(self):
        """Their rows are generated from the concepts they point at, so every hit in
        one is a duplicate of a hit the caller already has - attached to a file
        nobody should edit by hand."""
        self.assertEqual([r for r in self.rels(archive=True)
                          if r.endswith("index.md")], [])

    def test_a_file_with_no_frontmatter_is_still_read(self):
        """`okf_compile.concepts()` drops it, correctly - it compiles to nothing. A
        text search that dropped it would make a person's own notes invisible in
        their own bundle."""
        found = {c.rel: c for c in walk.walk(self.bundle)}
        self.assertIn("sources/retro-notes.md", found)
        self.assertIsNone(found["sources/retro-notes.md"].type)
        self.assertEqual(found["sources/retro-notes.md"].offset, 0)

    def test_typed_only_excludes_it(self):
        self.assertNotIn("sources/retro-notes.md", self.rels(typed_only=True))

    def test_types_narrows_to_the_named_types(self):
        found = {c.type for c in walk.walk(self.bundle, types=("Project",),
                                           typed_only=True)}
        self.assertEqual(found, {"Project"})

    def test_scope_narrows_to_one_subtree(self):
        self.assertEqual(sorted(self.rels(scope="projects")),
                         ["projects/billing-reconciliation.md",
                          "projects/care-platform.md"])

    def test_a_scope_outside_the_bundle_is_refused_by_name(self):
        for bad in ("..", "/etc", "."):
            with self.assertRaises(ValueError) as caught:
                list(walk.walk(self.bundle, scope=bad))
            self.assertIn("fix:", str(caught.exception))

    def test_a_scope_that_is_not_there_says_so(self):
        with self.assertRaises(ValueError) as caught:
            list(walk.walk(self.bundle, scope="nowhere"))
        self.assertIn("nowhere", str(caught.exception))

    def test_tailoring_false_skips_the_whole_directory(self):
        self.assertEqual([r for r in self.rels(tailoring=False)
                          if r.startswith("tailoring/")], [])

    def test_must_contain_skips_a_file_that_cannot_match(self):
        """The pre-filter `career.references()` uses. Sound rather than heuristic for
        an exact-case literal: a file not holding the string cannot hold a match."""
        found = self.rels(must_contain=("data-sovereignty",))
        self.assertIn("projects/care-platform.md", found)
        self.assertNotIn("roles/senior-engineer.md", found)

    def test_scope_takes_several_subtrees_in_one_pass(self):
        """A question about `projects/` and `skills/` is one question. Answering it with
        two walks costs two directory traversals to read the same files, and
        `okf list orphans` needs six."""
        found = self.rels(scope=("projects", "skills"))
        self.assertIn("projects/care-platform.md", found)
        self.assertIn("skills/competencies.md", found)
        self.assertNotIn("roles/senior-engineer.md", found)


class WhatTheWalkReadsUnderTailoring(QueryCase):
    """The most expensive knob in the layer, and the one whose wrong value is silent.

    A bundle of a hundred answered postings holds three files per target and only the
    view is career record. Reading all three took this walk from 216 concepts to 419 -
    a posting and a gap assessment each opened, YAML-parsed and wanted by nobody, which
    is the identical waste `okf_compile.concepts()`' docstring records removing from
    the compile. The default is therefore "views", the same as the compile's.

    Every assertion here is a file count or a file name rather than a duration, because
    a timing test on a shared machine is a flaky test and this defect is not about
    timing - it is about which files are opened, which is deterministic.
    """

    def test_a_posting_and_an_assessment_are_not_read_by_default(self):
        found = self.rels()
        self.assertIn("tailoring/targets/meridian-principal.view.md", found)
        self.assertNotIn("tailoring/targets/meridian-principal.posting.md", found)
        self.assertNotIn("tailoring/targets/meridian-principal.gaps.md", found)

    def test_all_reads_them_because_a_job_advertisement_is_searchable_text(self):
        """`okf search` is the one caller that wants them: somebody searching for a
        phrase from an advertisement is asking a real question, and a search that
        could not answer it is one people stop trusting."""
        found = self.rels(tailoring="all")
        self.assertIn("tailoring/targets/meridian-principal.posting.md", found)
        self.assertIn("tailoring/targets/meridian-principal.gaps.md", found)

    def test_none_does_not_enter_the_directory(self):
        self.assertEqual([r for r in self.rels(tailoring="none")
                          if r.startswith("tailoring/")], [])

    def test_the_narrowing_never_hides_a_sent_application(self):
        """The bug this nearly shipped with. An `Application` is `<stem>.md`, not a
        `.view.md`, so applying the views filter under `tailoring/applications/` would
        honour `archive=True` by walking into the directory and then skipping
        everything the flag was asked for. `okf refs` reads the archive by default and
        would have found no application at all."""
        found = {c.rel: c.type for c in walk.walk(self.bundle, archive=True)}
        applications = [rel for rel, kind in found.items() if kind == "Application"]
        self.assertEqual(len(applications), 1, found)
        self.assertTrue(found["tailoring/applications/2025/"
                              "2025-11-03-kestrel-staff.view.md"])

    def test_true_and_false_still_mean_what_they_said(self):
        """The earlier signature was a boolean. A caller written against it should not
        silently start reading a different set of files."""
        self.assertEqual(sorted(self.rels(tailoring=True)),
                         sorted(self.rels(tailoring="all")))
        self.assertEqual(sorted(self.rels(tailoring=False)),
                         sorted(self.rels(tailoring="none")))

    def test_a_value_nobody_recognises_is_refused(self):
        with self.assertRaises(ValueError):
            list(walk.walk(self.bundle, tailoring="veiws"))


class AQueryReadsNoMoreThanTheCompile(QueryCase):
    """The layer's premise, made checkable.

    `query/__init__.py` says nothing here compiles, because a query that cost what a
    compile costs would have no reason to exist. `NothingHereCompiles` below asserts
    the letter of that - `load()` is never called. This asserts the substance, which is
    the part that actually regressed: the walk was reading nearly twice the files the
    compile reads, so every query was slower than the thing it replaces while
    truthfully never calling it.

    Counting files rather than timing them is deliberate. The cost of a query on this
    bundle is dominated by opening and YAML-parsing concepts, the count is exact, and a
    duration on a machine running four other jobs is noise.
    """

    def compiled(self):
        return {f"{stem}.md" for stem, _, _, _ in
                okf_compile.concepts(str(self.bundle), "views")}

    def test_the_default_walk_opens_no_concept_the_compile_skips(self):
        walked = {Path(c.rel).name for c in walk.walk(self.bundle) if c.type}
        extra = sorted(walked - self.compiled())
        self.assertEqual(extra, [],
                         f"the walk reads typed concepts the compile does not: {extra}")

    def test_an_untyped_file_is_the_only_thing_it_reads_extra(self):
        """And it is read on purpose - a person's own notes are searchable. Asserted so
        that the subset test above cannot be satisfied by dropping it."""
        walked = {Path(c.rel).name for c in walk.walk(self.bundle)}
        self.assertEqual(sorted(walked - self.compiled()), ["retro-notes.md"])

    def test_scoping_reads_only_the_subtree_asked_for(self):
        walked = [c.rel for c in walk.walk(self.bundle, scope="projects")]
        self.assertTrue(walked)
        self.assertTrue(all(r.startswith("projects/") for r in walked), walked)


class TheLineArithmetic(QueryCase):
    """`offset` is the whole reason a reported `file:line` can be trusted.

    Every one of these opens the file, counts to the reported line, and asserts what
    is on it. A test that only checked the number against another calculation would
    agree with the same mistake twice.
    """

    def line_at(self, rel, number):
        text = (Path(self.bundle) / rel).read_text(encoding="utf-8")
        return text.splitlines()[number - 1]

    def test_the_first_body_line_is_reported_where_it_is(self):
        for concept in walk.walk(self.bundle, typed_only=True):
            if not concept.body.strip():
                continue
            body_lines = concept.body.splitlines()
            for n, text in enumerate(body_lines, 1):
                if not text.strip():
                    continue
                self.assertEqual(self.line_at(concept.rel, concept.line_of(n)), text,
                                 f"{concept.rel}: body line {n} is not at file line "
                                 f"{concept.line_of(n)}")
                break

    def test_it_holds_for_every_body_line_of_every_concept(self):
        for concept in walk.walk(self.bundle, archive=True):
            for n, text in enumerate(concept.body.splitlines(), 1):
                self.assertEqual(self.line_at(concept.rel, concept.line_of(n)), text,
                                 f"{concept.rel}:{concept.line_of(n)}")

    def test_a_file_on_disk_with_crlf_endings_still_reports_the_right_line(self):
        """End to end over a CRLF file, which is what a Windows checkout has.

        This does *not* reach `read_frontmatter`'s CRLF arm, and it is worth saying so
        rather than implying it: `walk` opens with the default `newline=None`, so
        universal-newline translation has turned every `\\r\\n` into `\\n` before the
        text arrives. `markup.py`'s docstring makes the same point about that arm
        being unreachable from inside this package. What is checked here is the whole
        path a person actually uses; the arm itself is covered below.
        """
        path = Path(self.bundle) / "projects" / "care-platform.md"
        text = path.read_text(encoding="utf-8")
        path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        found = {c.rel: c for c in walk.walk(self.bundle)}["projects/care-platform.md"]
        raw = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(found.body.splitlines(), 1):
            self.assertEqual(raw[found.line_of(n) - 1], line)

    def test_the_offset_is_right_on_text_no_one_translated(self):
        """The arm the test above cannot reach.

        `read_frontmatter` slices at `end + 7` for `\\r\\n---\\r\\n` and `end + 5` for
        `\\n---\\n`, and **neither width is spelt in `body_offset`** - the length of
        what survived the slice is. So this passes for the same reason it passes on
        LF, and an implementation that hardcoded either width would fail exactly one
        of the two.

        Reached by calling the function rather than by writing a file, because a
        caller inside this package cannot get untranslated text out of `open()`.
        """
        crlf = ("---\r\ntype: Project\r\ntitle: \"X\"\r\n---\r\n"
                "\r\n# Head\r\n\r\nBody line.\r\n")
        _, body = walk.okf_compile.read_frontmatter(crlf)
        self.assertEqual(walk.body_offset(crlf, body), 4)
        lf = crlf.replace("\r\n", "\n")
        _, body = walk.okf_compile.read_frontmatter(lf)
        self.assertEqual(walk.body_offset(lf, body), 4)

    def test_a_body_that_is_only_a_frontmatter_block_reports_no_negative_line(self):
        path = Path(self.bundle) / "projects" / "bare.md"
        path.write_text("---\ntype: Project\ntitle: \"Bare\"\n---\n", encoding="utf-8")
        found = {c.rel: c for c in walk.walk(self.bundle)}["projects/bare.md"]
        self.assertGreaterEqual(found.line_of(1), 1)


# --- the id index ---------------------------------------------------------------

def record_ids(doc):
    """Every id the compiled record carries, at any depth."""
    if isinstance(doc, dict):
        found = {doc["id"]} if isinstance(doc.get("id"), str) else set()
        for value in doc.values():
            found |= record_ids(value)
        return found
    if isinstance(doc, list):
        found = set()
        for value in doc:
            found |= record_ids(value)
        return found
    return set()


class EveryCompiledIdResolves(QueryCase):
    """The agreement that stops `query/ids.py` and `okf_compile.py` drifting.

    The read layer derives ids instead of compiling. That is the point - it is why a
    query costs a walk rather than a second - and the price is that two modules now
    know how an id is built. An id derived differently here would send somebody to
    the wrong file with nothing to say so, and worse: `okf list bullets` would print
    an id that `okf view include` then refuses, which reads as a bug in the write
    layer.
    """

    def test_every_id_in_the_record_is_in_the_index(self):
        doc = okf_compile.load(self.bundle)
        found = set(ids.index(self.bundle))
        missing = sorted(i for i in record_ids(doc)
                         if not i.startswith("urn:") and i not in found)
        self.assertEqual(missing, [],
                         f"the record carries ids query/ids.py cannot resolve: {missing}")

    def test_each_one_resolves_to_the_file_the_compile_read_it_from(self):
        index = ids.index(self.bundle)
        for wanted, rel in (("prj_care_platform", "projects/care-platform.md"),
                            ("pos_principal_engineer", "roles/principal-engineer.md"),
                            ("org_meridian_health", "organisations/meridian-health.md"),
                            ("eng_meridian_health", "organisations/meridian-health.md"),
                            ("skill_dotnet", "skills/competencies.md"),
                            ("view_meridian_principal",
                             "tailoring/targets/meridian-principal.view.md")):
            self.assertEqual(index[wanted].rel, rel, wanted)

    def test_a_bullet_id_points_at_the_line_the_bullet_is_on(self):
        index = ids.index(self.bundle)
        located = index["ach_projects_care_platform_md_2"]
        line = (Path(self.bundle) / located.rel).read_text(
            encoding="utf-8").splitlines()[located.line - 1]
        self.assertIn("data-sovereignty", line)

    def test_a_bullets_own_status_wins_over_its_concepts(self):
        """The concept is `confirmed` and its second bullet is not. Reporting the
        concept's status against a claim is how an inferred sentence reads as
        signed-off."""
        index = ids.index(self.bundle)
        self.assertEqual(index["ach_projects_care_platform_md_1"].status, "confirmed")
        self.assertEqual(index["ach_projects_care_platform_md_2"].status, "inferred")

    def test_a_bullet_with_no_status_reads_inferred_not_its_concepts_status(self):
        """`okf_compile.bullets` falls back to `"inferred"`, not to the concept.

        Falling back to the concept made a status-less bullet inside a
        `status: confirmed` project read as confirmed - so `okf show` called a claim
        signed off while the renderer withheld it under `provenance_floor: confirmed`.
        That is the one direction provenance must never be wrong in: it is the
        difference between a sentence somebody agreed to and a sentence drafted for
        them, and the second kind reads well, which is why it is dangerous.
        """
        path = Path(self.bundle) / "projects" / "no-status.md"
        path.write_text(
            '---\ntype: Project\ntitle: "No status"\ndescription: "x"\n'
            "role: principal-engineer\nstatus: confirmed\nstrength: 3\n"
            "recency: 2023\nseniority: hands-on\n---\n\n"
            "# Bullets\n\n- A sentence with no status field under it.\n",
            encoding="utf-8")
        located = ids.index(self.bundle)["ach_projects_no_status_md_1"]
        self.assertEqual(located.status, "inferred")
        compiled = {a["id"]: a["provenance"]["status"]
                    for project in okf_compile.load(self.bundle)["projects"]
                    for a in project.get("achievements", ())}
        self.assertEqual(located.status, compiled["ach_projects_no_status_md_1"])

    def test_a_credentials_currency_is_not_reported_as_its_provenance(self):
        """`build_credentials` carries a comment saying the two "must not be
        conflated": a credential's own `status` is `active`/`expired` - whether the
        certification is current - and its *provenance* comes from the concept's
        frontmatter. Reading the item's field as provenance reported `active` where a
        caller expected one of the three provenance words."""
        located = ids.index(self.bundle)["cred_cloud_certifications_1"]
        self.assertEqual(located.status, "confirmed")
        self.assertEqual(located.detail.get("status"), "active")

    def test_a_concept_evidencing_no_certification_mints_no_id(self):
        """The third phantom of the same family. `build_credentials` mints
        `cred_<stem>` from one shape only - no `# Held` block *and* an
        `- **Issuer:**` line - so a concept recording a certification *gap* compiles
        to nothing and says so in its notes. Guarding on the absent block alone gave
        "none held yet" an id that resolved and existed nowhere in the record."""
        path = Path(self.bundle) / "education" / "none-held.md"
        path.write_text(
            '---\ntype: Certification Status\ntitle: "Nothing held yet"\n'
            'description: "A gap."\nstatus: confirmed\n---\n\n'
            "# Considering\n\n- Azure Solutions Architect, next year.\n",
            encoding="utf-8")
        self.assertNotIn("cred_none_held", ids.index(self.bundle))
        self.assertNotIn("cred_none_held",
                         {c["id"] for c in okf_compile.load(self.bundle)["credentials"]})

    def test_no_id_is_minted_that_the_record_does_not_carry(self):
        """The one mistake this module cannot make. `build_credentials` returns before
        the single-certification branch as soon as a `# Held` block yields anything,
        so `cred_<stem>` is not an id for a concept that has one. Registering it
        would put a phantom into `okf show`, and from there into a view's
        `include[].ref`, where it renders nothing and no gate names it."""
        doc = okf_compile.load(self.bundle)
        carried = record_ids(doc)
        self.assertIn("cred_cloud_certifications_1", carried)
        self.assertNotIn("cred_cloud_certifications", carried)
        self.assertNotIn("cred_cloud_certifications", ids.index(self.bundle))

    def test_no_engagement_is_offered_for_a_company_nobody_worked_for(self):
        """The second phantom, and the one that survived longest.

        An engagement is built from the *roles* that name a company -
        `build_engagements` groups by a role's `organisation:` key - so a company with
        no role compiles to no engagement. Minting `eng_` per Organisation looked
        obviously right and resolved `eng_kestrel_systems` against a record with no
        such entity. Every bundle has these: one per employer ever applied to, each a
        `relationship: prospect`.
        """
        index = ids.index(self.bundle)
        self.assertIn("org_kestrel_systems", index)
        self.assertNotIn("eng_kestrel_systems", index)
        # And the one that *is* worked for still has both.
        self.assertIn("org_meridian_health", index)
        self.assertIn("eng_meridian_health", index)

    def test_every_resolved_location_exists_and_its_line_is_in_range(self):
        """An id that resolves to a line past the end of its file is worse than an id
        that does not resolve: the caller opens the file and reads the wrong thing, or
        nothing, and has no reason to doubt it."""
        for name, located in ids.index(self.bundle, archive=True).items():
            path = Path(self.bundle) / located.rel
            self.assertTrue(path.exists(), f"{name} -> {located.rel}")
            if located.line:
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(located.line, len(lines), f"{name} at {located.at}")

    def test_ids_of_over_a_walk_is_the_same_as_the_index(self):
        """`of()` exists so a module already walking need not walk again, and the only
        thing that makes it safe is that it cannot answer differently."""
        by_of, roles, orgs = {}, [], {}
        for concept in walk.walk(self.bundle, typed_only=True, types=ids.TYPES):
            if concept.type == "Role":
                roles.append(concept)
            elif concept.type == "Organisation":
                orgs[concept.stem] = concept
            for located in ids.of(concept):
                by_of.setdefault(located.id, located)
        for located in ids.engagements_of(roles, orgs) + ids.metrics(self.bundle):
            by_of.setdefault(located.id, located)
        self.assertEqual(set(by_of), set(ids.index(self.bundle)))

    def test_a_narrowed_index_agrees_with_the_broad_one(self):
        """Narrowing is what makes a listing cheap. An index that answered differently
        when narrowed would make `okf list projects` and `okf show` disagree about the
        same project."""
        narrow = ids.index(self.bundle, scope="projects", types=("Project",))
        broad = {i for i, located in ids.index(self.bundle).items()
                 if located.rel.startswith("projects/")}
        self.assertEqual(set(narrow), broad)

    def test_the_claim_ids_are_the_ones_the_write_layer_accepts(self):
        """`okf view include` validates a referenced id against
        `authoring.common.item_ids`. An id printed here that fails there is worse
        than no listing at all."""
        common = query_module("jsk_okf.authoring.common")
        index = ids.index(self.bundle)
        for kind, prefix in (("bullet", "ach_"), ("skill", "skill_"),
                             ("credential", "cred_")):
            expected = set(common.item_ids(self.bundle, kind))
            got = {i for i, located in index.items()
                   if located.kind == ("credential" if kind == "credential" else kind)
                   and i.startswith(prefix)}
            self.assertEqual(got, expected, kind)


class TheResolveFastPath(QueryCase):
    """`resolve()` finds a hit without building the index, and must not differ for it.

    Building the index parses the YAML of every concept, which is five sixths of the
    walk: on a 235-file bundle it was 569ms against the compile's 549ms, so `okf show` -
    the cheap way to ask what an id is - cost what the compile it replaces costs. The
    fast path parses only files that could mint the id and answers in 14ms.

    The only thing that makes that safe is that `candidates()` is a *superset* test and
    whatever it admits goes through `of()`, the real derivation. So the test that matters
    is not that it is fast, it is that it cannot answer differently.
    """

    def test_every_id_resolves_to_exactly_what_the_index_says(self):
        index = ids.index(self.bundle, archive=True, tailoring="all")
        self.assertTrue(index)
        for name, expected in index.items():
            located, _ = ids.resolve(self.bundle, name, archive=True)
            self.assertEqual((located.id, located.rel, located.line),
                             (expected.id, expected.rel, expected.line), name)

    def test_the_candidate_filter_admits_every_id_built_from_a_filename(self):
        """A false positive costs one parse. A false negative would be an id that
        exists and cannot be found - so the filter's reach is asserted here and its
        two blind spots are asserted immediately below, rather than left to the
        docstring.
        """
        unpredictable = ("skill_", "nar_")
        for concept in walk.walk(self.bundle, archive=True, typed_only=True,
                                 types=ids.TYPES, tailoring="all"):
            for located in ids.of(concept):
                if located.id.startswith(unpredictable):
                    continue
                self.assertTrue(
                    ids.candidates(concept, located.id),
                    f"{concept.rel} mints {located.id} and was filtered out")

    def test_the_two_shapes_it_cannot_see_are_the_two_it_says_it_cannot(self):
        """A blind spot that is real and documented is a design. One that has quietly
        grown a third member is a bug, and the only difference is whether anything
        checks. `skill_` is derived from the skill's own text and `nar_` from a
        heading; neither is in a filename, so neither can be predicted from one."""
        blind = set()
        for concept in walk.walk(self.bundle, archive=True, typed_only=True,
                                 types=ids.TYPES, tailoring="all"):
            for located in ids.of(concept):
                if not ids.candidates(concept, located.id):
                    blind.add(located.id.split("_")[0] + "_")
        self.assertEqual(blind, {"skill_", "nar_"})

    def test_a_metric_id_is_answered_without_walking_the_bundle(self):
        """`metrics()` is one file and one parse, so it is tried before the walk - which
        took a `met_` id from 199ms to 54ms. Asserted by behaviour rather than by clock:
        the answer must be right with the walk unable to produce it."""
        located, _ = ids.resolve(self.bundle, "met_tenants_onboarded")
        self.assertEqual(located.kind, "metric")
        self.assertEqual(located.rel, "achievements/metrics.md")

    def test_a_concept_declaring_a_metric_id_still_outranks_the_table(self):
        """The precedence the fast path had to buy back. `index()` registers concepts
        before metrics and `put` uses `setdefault`, so a concept declaring `id: met_x`
        wins there - and a `resolve()` that answered differently would make `okf show`
        disagree with `okf list` about one id, which is the whole failure this module is
        built to avoid.

        It is reachable only by declaration, because every prefix `of()` derives comes
        from CONCEPTS, CLAIMS, `view_`, `nar_` or `eng_` and none of those is `met_`. So
        a literal-only walk is enough to find it, and that is what `declares()` runs.
        """
        colliding = Path(self.bundle) / "projects" / "collides.md"
        colliding.write_text(
            "---\ntype: Project\nid: met_tenants_onboarded\n"
            'title: "Declares a metric id"\nstatus: confirmed\n---\n',
            encoding="utf-8")
        located, _ = ids.resolve(self.bundle, "met_tenants_onboarded")
        from_index = ids.index(self.bundle)["met_tenants_onboarded"]
        self.assertEqual(located.rel, "projects/collides.md")
        self.assertEqual((located.kind, located.rel),
                         (from_index.kind, from_index.rel))

    def test_an_id_whose_shape_no_filename_predicts_still_resolves(self):
        """`skill_` comes from the skill's own text and `nar_` from a heading, so
        neither is in a filename. Those fall through to the index rather than being
        reported missing - which is the case a fast path most easily gets wrong."""
        for wanted in ("skill_azure", "nar_b_keyword_dense"):
            located, _ = ids.resolve(self.bundle, wanted)
            self.assertEqual(located.id, wanted)


class ResolvingOneId(QueryCase):
    def test_a_typo_names_the_near_misses(self):
        with self.assertRaises(ids.Unknown) as caught:
            ids.resolve(self.bundle, "prj_care_platfrom")
        message = str(caught.exception)
        self.assertIn("prj_care_platform", message)
        self.assertIn("fix:", message)

    def test_an_id_nothing_resembles_says_where_to_look(self):
        with self.assertRaises(ids.Unknown) as caught:
            ids.resolve(self.bundle, "zzzzzz")
        self.assertIn("okf list", str(caught.exception))

    def test_it_says_the_archive_was_not_read(self):
        """A view id that only exists in the archive is not missing, it is unread.
        Those are different mistakes and a refusal that conflated them sends
        somebody looking for a file they did write."""
        with self.assertRaises(ids.Unknown) as caught:
            ids.resolve(self.bundle, "view_kestrel_staff")
        self.assertIn("--archive", str(caught.exception))
        located, _ = ids.resolve(self.bundle, "view_kestrel_staff", archive=True)
        self.assertTrue(located.frozen)


# --- the output contract --------------------------------------------------------

class TheOutputContract(unittest.TestCase):
    def result(self, count):
        return render.Result(
            [{"id": f"i{n}", "text": "x" * 80} for n in range(count)],
            columns=(render.Column("Id", "id", 10), render.Column("Text", "text")))

    def test_a_cut_is_always_visible(self):
        """A listing that silently stopped at fifteen is a listing somebody draws a
        conclusion from."""
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            render.emit(self.result(40), "list", "b", top=15)
        self.assertIn("and 25 more", buffer.getvalue())

    def test_json_is_never_truncated(self):
        """--top is a reading aid, and a parser does not read."""
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            render.emit(self.result(40), "list", "b", top=15, as_json=True)
        self.assertEqual(len(json.loads(buffer.getvalue())["rows"]), 40)

    def test_a_value_wider_than_its_column_is_cut_visibly(self):
        self.assertTrue(render.cell("x" * 40, 10).endswith(render.ELLIPSIS))
        self.assertEqual(len(render.cell("x" * 40, 10)), 10)

    def test_a_result_renders_as_columns_or_blocks_and_not_both(self):
        with self.assertRaises(ValueError):
            render.Result([], columns=(), block=lambda row: [])
        with self.assertRaises(ValueError):
            render.Result([])


# --- the command surface --------------------------------------------------------

class TheBundleArgument(QueryCase):
    def test_a_path_that_is_not_a_directory_is_a_call_error(self):
        code, out = run(CLI, "stats", str(self.tmp / "nowhere"))
        self.assertEqual(code, 2, out)
        self.assertIn("fix:", out)

    def test_a_directory_that_is_not_a_bundle_names_what_is_missing(self):
        code, out = run(CLI, "stats", str(self.tmp))
        self.assertEqual(code, 2, out)
        self.assertIn("projects/", out)

    def test_a_subdirectory_of_a_bundle_is_refused_rather_than_walked(self):
        code, out = run(CLI, "stats", str(Path(self.bundle) / "projects"))
        self.assertEqual(code, 2, out)


class TheFiveVerbs(QueryCase):
    def test_every_verb_is_dispatched_by_the_cli(self):
        for args in (("search", str(self.bundle), "latency"),
                     ("list", str(self.bundle), "projects"),
                     ("show", str(self.bundle), "prj_care_platform"),
                     ("refs", str(self.bundle), "care-platform"),
                     ("stats", str(self.bundle))):
            code, out = run(CLI, *args)
            self.assertIn(code, (0, 2), out)
            self.assertNotIn("Traceback", out, f"okf {args[0]} raised:\n{out}")

    def test_no_verb_ever_exits_one(self):
        """0 it ran, 2 you called it wrong, and never 1. A query has no findings -
        whether what it reports is a problem is a gate's judgement, and an
        `okf list unconfirmed` that exited 1 would read as a failed check that
        somebody then starts clearing."""
        for args in (("search", str(self.bundle), "nothing-matches-this-string"),
                     ("search", str(self.bundle)),
                     ("list", str(self.bundle), "projects"),
                     ("list", str(self.bundle), "unconfirmed"),
                     ("list", str(self.bundle), "orphans"),
                     ("show", str(self.bundle), "prj_care_platform"),
                     ("refs", str(self.bundle), "care-platform"),
                     ("stats", str(self.bundle))):
            code, out = run(CLI, *args)
            self.assertNotEqual(code, 1, f"okf {' '.join(args[:1])} exited 1:\n{out}")

    def test_list_with_no_noun_says_which_nouns_there_are(self):
        code, out = run(CLI, "list", str(self.bundle))
        self.assertEqual(code, 2, out)
        self.assertIn("projects", out)

    def test_an_unknown_noun_is_a_call_error(self):
        code, out = run(CLI, "list", str(self.bundle), "frobnicates")
        self.assertEqual(code, 2, out)


class Show(QueryCase):
    def test_it_names_what_the_id_is_and_where_to_read_it(self):
        code, out = run(CLI, "show", str(self.bundle), "prj_care_platform")
        self.assertEqual(code, 0, out)
        self.assertIn("projects/care-platform.md", out)
        self.assertIn("Care coordination platform", out)

    def test_a_bullet_id_reports_the_line_it_is_on(self):
        code, out = run(CLI, "show", str(self.bundle),
                        "ach_projects_care_platform_md_2")
        self.assertEqual(code, 0, out)
        self.assertIn("care-platform.md:", out)
        self.assertIn("inferred", out)

    def test_path_prints_the_path_alone_for_feeding_to_a_reader(self):
        code, out = run(CLI, "show", str(self.bundle), "prj_care_platform", "--path")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.strip(), "projects/care-platform.md")

    def test_an_archived_id_says_it_may_not_be_edited(self):
        code, out = run(CLI, "show", str(self.bundle), "view_kestrel_staff",
                        "--archive")
        self.assertEqual(code, 0, out)
        self.assertIn("FROZEN", out)

    def test_a_typo_exits_two_and_suggests(self):
        code, out = run(CLI, "show", str(self.bundle), "prj_care_platfrom")
        self.assertEqual(code, 2, out)
        self.assertIn("prj_care_platform", out)

    def test_show_with_no_id_says_where_to_find_one(self):
        code, out = run(CLI, "show", str(self.bundle))
        self.assertEqual(code, 2, out)
        self.assertIn("okf list", out)


class NothingHereCompiles(QueryCase):
    """The design, asserted rather than described.

    `okf_compile.load()` walks the tree, parses every concept, resolves every
    relation and raises on a bundle it does not like. A query that paid for it would
    cost what the thing it replaces costs - and would refuse to answer a question
    about a bundle that is mid-edit, which is exactly when the question gets asked.

    Run in-process with `load` replaced by something that raises, so the failure is
    unmissable rather than a slow test nobody times.
    """

    def each_verb(self):
        class Args:
            archive = False
            as_json = False
            top = 0
            path = False
            scope = regex = case_sensitive = frontmatter = body = None
            text = "latency"
            id = "prj_care_platform"
            target = "care-platform"
            noun = None
            type = status = capability = technology = domain = None
            seniority = strength = recency = None

        for verb in commands.VERBS:
            args = Args()
            args.verb = verb
            if verb == "list":
                args.noun = "projects"
            yield verb, args

    def test_no_verb_calls_load(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("a query called okf_compile.load()")

        original = okf_compile.load
        okf_compile.load = refuse
        try:
            for verb, args in self.each_verb():
                args.bundle = str(self.bundle)
                try:
                    commands.dispatch(args)
                except (ImportError, AttributeError) as exc:   # module not built yet
                    self.skipTest(f"okf {verb} is not implemented yet: {exc}")
        finally:
            okf_compile.load = original


if __name__ == "__main__":
    unittest.main()
