"""`jsk posting fetch`: a public job board's posting, as an application's posting.md.

The ElevenLabs run (2026-09-25) fetched its Ashby posting through hand-written curl and
inline Python, then assembled posting.md by hand. posting.md is the one input every
requirement quotes, so these tests pin what the command must never do - paraphrase,
trim, overwrite - and none of them touches the network: fetch_json() is the one call
that does, and each test hands in its own.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fixtures  # noqa: F401 - puts the worktree's src first on sys.path

from jsk import posting

ASHBY_URL = "https://jobs.ashbyhq.com/elevenlabs/a571b8e4-8176-4e31-aab6-2287ee810236"
GREENHOUSE_URL = "https://job-boards.greenhouse.io/anthropic/jobs/4461450008"
LEVER_URL = "https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd"

ASHBY = {"jobs": [
    {"id": "00000000-0000-0000-0000-000000000000", "title": "Someone else"},
    {"id": "a571b8e4-8176-4e31-aab6-2287ee810236",
     "title": "Forward Deployed Engineer ",
     "department": "Engineering", "team": "Agents", "location": "London",
     "secondaryLocations": [{"location": "Warsaw"}, {"location": "London"}],
     "employmentType": "FullTime", "isRemote": True, "workplaceType": "Hybrid",
     "publishedAt": "2026-07-21T16:03:51.100+00:00",
     "shouldDisplayCompensationOnJobPostings": False,
     "compensation": {"compensationTierSummary": "£1 – £2"},
     "descriptionPlain": "ABOUT US\n\nWe build voices.\n\n - Ship agents\n - Talk to customers\n",
     "descriptionHtml": "<p>not this one</p>"},
]}

GREENHOUSE = {
    "title": "Account Executive, AI Native",
    "company_name": "Anthropic",
    "departments": [{"name": "Sales"}],
    "location": {"name": "San Francisco, CA"},
    "first_published": "2024-12-20T10:00:00-05:00",
    "updated_at": "2026-09-01T10:00:00-04:00",
    # Greenhouse escapes its HTML once more: this is &lt;p&gt; on the wire.
    "content": "&lt;h2&gt;About the role&lt;/h2&gt;&lt;p&gt;You&amp;rsquo;ll drive "
               "adoption &amp;amp; growth.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;&lt;p&gt;Win new "
               "business&lt;/p&gt;&lt;/li&gt;&lt;li&gt;Design strategies&lt;/li&gt;"
               "&lt;/ul&gt;",
}

LEVER = {
    "text": "Administrative Business Partner",
    "categories": {"location": "Singapore", "team": "Administrative",
                   "commitment": "Full-time"},
    "workplaceType": "hybrid",
    "createdAt": 1786406400000,             # 2026-08-11T00:00:00Z
    "descriptionPlain": "A World-Changing Company\n\nPalantir builds software.\n",
    "lists": [{"text": "What We Value",
               "content": "<li>Ability to adjust quickly</li><li>Tact &amp; care</li>"}],
    "additionalPlain": "Life at Palantir\n\nWe want every Palantirian to thrive.\n",
}


class Recognise(unittest.TestCase):
    def test_each_board_maps_to_its_public_api(self):
        cases = [
            (ASHBY_URL, ("ashby", "elevenlabs", "a571b8e4-8176-4e31-aab6-2287ee810236",
                         "https://api.ashbyhq.com/posting-api/job-board/elevenlabs"
                         "?includeCompensation=true")),
            (ASHBY_URL + "/application?utm=x", ("ashby", "elevenlabs",
                                                "a571b8e4-8176-4e31-aab6-2287ee810236",
                                                "https://api.ashbyhq.com/posting-api/"
                                                "job-board/elevenlabs?includeCompensation=true")),
            ("https://boards.greenhouse.io/anthropic/jobs/4461450008",
             ("greenhouse", "anthropic", "4461450008",
              "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs/4461450008")),
            (GREENHOUSE_URL, ("greenhouse", "anthropic", "4461450008",
                              "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs/"
                              "4461450008")),
            (LEVER_URL + "/apply", ("lever", "palantir",
                                    "6ed76ce8-4156-4b60-b120-403538bd66cd",
                                    "https://api.lever.co/v0/postings/palantir/"
                                    "6ed76ce8-4156-4b60-b120-403538bd66cd")),
            ("https://jobs.eu.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd",
             ("lever", "acme", "6ed76ce8-4156-4b60-b120-403538bd66cd",
              "https://api.eu.lever.co/v0/postings/acme/"
              "6ed76ce8-4156-4b60-b120-403538bd66cd")),
        ]
        for url, want in cases:
            with self.subTest(url=url):
                self.assertEqual(posting.recognise(url), want)

    def test_anything_else_is_not_recognised(self):
        for url in ("https://careers.example.com/jobs/123",
                    "https://jobs.ashbyhq.com/elevenlabs",              # the board, no job
                    "https://boards.greenhouse.io/anthropic",
                    "https://jobs.lever.co/palantir",
                    "https://wd5.myworkdayjobs.com/en-US/acme/job/Engineer_R123",
                    "ftp://jobs.ashbyhq.com/elevenlabs/a571b8e4-8176-4e31-aab6-2287ee810236",
                    "not a url"):
            with self.subTest(url=url):
                self.assertIsNone(posting.recognise(url))


class HtmlToText(unittest.TestCase):
    def test_paragraphs_become_blank_line_separated(self):
        self.assertEqual(posting.html_to_text("<p>One\n  two.</p><p>Three.</p>"),
                         "One two.\n\nThree.")

    def test_list_items_become_dash_lines(self):
        self.assertEqual(
            posting.html_to_text("<p>Do:</p><ul><li>First</li><li><p>Second</p></li></ul>"
                                 "<p>After.</p>"),
            "Do:\n\n- First\n- Second\n\nAfter.")

    def test_a_nested_list_is_indented_under_its_item(self):
        self.assertEqual(
            posting.html_to_text("<ul><li>Outer<ul><li>Inner</li></ul></li><li>Next</li></ul>"),
            "- Outer\n  - Inner\n- Next")

    def test_entities_are_unescaped(self):
        self.assertEqual(posting.html_to_text("<p>R&amp;D &mdash; you&rsquo;ll &lt;3</p>"),
                         "R&D — you’ll <3")

    def test_inline_markup_and_line_breaks(self):
        self.assertEqual(
            posting.html_to_text("<div><strong>Pay:</strong> <em>£1</em><br>per year</div>"),
            "Pay: £1\nper year")

    def test_headings_keep_their_words_and_scripts_are_dropped(self):
        self.assertEqual(
            posting.html_to_text("<h2>About</h2><script>x()</script><p>Text</p>"),
            "About\n\nText")


class Conversion(unittest.TestCase):
    """The JSON each board returns, to posting.md - through fetch(), with the network
    replaced."""

    def fetch(self, url, data):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "applications" / "acme"          # created if missing
            target, title, count = posting.fetch(url, str(app), get=lambda api: data)
            text = Path(target).read_text(encoding="utf-8")
        self.assertEqual(count, len(text))
        return title, text

    def test_ashby(self):
        title, text = self.fetch(ASHBY_URL, ASHBY)
        self.assertEqual(title, "Forward Deployed Engineer")
        self.assertEqual(text, (
            f"{ASHBY_URL}\n\n# Forward Deployed Engineer\n\n"
            "elevenlabs · Engineering · Agents · London / Warsaw · Hybrid · Full time · "
            "Published 2026-07-21\n\n"
            # descriptionPlain verbatim - its odd " - " bullets included.
            "ABOUT US\n\nWe build voices.\n\n - Ship agents\n - Talk to customers\n"))

    def test_ashby_shows_pay_only_where_the_posting_does(self):
        board = {"jobs": [dict(ASHBY["jobs"][1], shouldDisplayCompensationOnJobPostings=True)]}
        _, text = self.fetch(ASHBY_URL, board)
        self.assertIn(" · £1 – £2 · ", text.splitlines()[4])
        _, text = self.fetch(ASHBY_URL, ASHBY)
        self.assertNotIn("£1", text)

    def test_ashby_without_plain_text_converts_its_html(self):
        job = dict(ASHBY["jobs"][1], descriptionPlain="",
                   descriptionHtml="<p>Hello &amp; welcome</p><ul><li>One</li></ul>")
        _, text = self.fetch(ASHBY_URL, {"jobs": [job]})
        self.assertTrue(text.endswith("\n\nHello & welcome\n\n- One\n"), text)

    def test_greenhouse(self):
        title, text = self.fetch(GREENHOUSE_URL, GREENHOUSE)
        self.assertEqual(title, "Account Executive, AI Native")
        self.assertEqual(text, (
            f"{GREENHOUSE_URL}\n\n# Account Executive, AI Native\n\n"
            "Anthropic · Sales · San Francisco, CA · Published 2024-12-20\n\n"
            "About the role\n\nYou’ll drive adoption & growth.\n\n"
            "- Win new business\n- Design strategies\n"))

    def test_lever(self):
        title, text = self.fetch(LEVER_URL, LEVER)
        self.assertEqual(title, "Administrative Business Partner")
        self.assertEqual(text, (
            f"{LEVER_URL}\n\n# Administrative Business Partner\n\n"
            "palantir · Administrative · Singapore · Hybrid · Full-time · "
            "Published 2026-08-11\n\n"
            "A World-Changing Company\n\nPalantir builds software.\n\n"
            "What We Value\n\n- Ability to adjust quickly\n- Tact & care\n\n"
            "Life at Palantir\n\nWe want every Palantirian to thrive.\n"))


class Refusals(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = Path(self._tmp.name) / "acme"

    def main(self, url, data=None, error=None):
        """jsk.posting.main(), its fetch_json replaced by the board's answer."""
        def get(api):
            if error:
                raise error
            return data
        buf = io.StringIO()
        with mock.patch.object(posting, "fetch_json", get), contextlib.redirect_stdout(buf):
            code = posting.main(["fetch", url, str(self.app)])
        return code, buf.getvalue()

    def test_an_unknown_board_is_sent_to_the_browser(self):
        code, out = self.main("https://careers.example.com/jobs/1", error=AssertionError())
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED - ", out)
        self.assertIn("fix:  fetch it with a browser tool and write posting.md with the "
                      "Write tool", out)
        self.assertFalse(self.app.exists())

    def test_a_job_not_on_the_board_may_be_closed(self):
        code, out = self.main(ASHBY_URL, {"jobs": [ASHBY["jobs"][0]]})
        self.assertEqual(code, 1, out)
        self.assertIn("is not on the ashby board", out)
        self.assertIn("fix:  the posting may be closed - check the URL in a browser", out)
        self.assertFalse((self.app / "posting.md").exists())

    def test_a_404_is_a_posting_not_on_the_board(self):
        code, out = self.main(GREENHOUSE_URL, error=posting.NotOnBoard("404"))
        self.assertEqual(code, 1, out)
        self.assertIn("the posting may be closed", out)

    def test_a_network_failure_is_refused_with_its_reason(self):
        code, out = self.main(LEVER_URL, error=posting.Refused(
            "could not read https://api.lever.co/...: timed out", "fix:  try again"))
        self.assertEqual(code, 1, out)
        self.assertIn("timed out", out)
        self.assertIn("fix:", out)

    def test_the_real_fetch_turns_a_network_error_into_a_refusal(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.URLError("no route to host")):
            with self.assertRaises(posting.Refused) as caught:
                posting.fetch_json("https://api.lever.co/v0/postings/x/y")
        self.assertIn("no route to host", str(caught.exception))
        self.assertTrue(caught.exception.fix.startswith("fix:  "))

    def test_the_real_fetch_reads_a_404_as_not_on_the_board(self):
        import urllib.error
        err = urllib.error.HTTPError("https://x", 404, "Not Found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(posting.NotOnBoard):
                posting.fetch_json("https://boards-api.greenhouse.io/v1/boards/x/jobs/1")

    def test_an_existing_posting_md_is_never_overwritten_or_fetched_for(self):
        self.app.mkdir()
        (self.app / "posting.md").write_text("what was answered\n", encoding="utf-8")
        code, out = self.main(ASHBY_URL, error=AssertionError("fetched"))
        self.assertEqual(code, 1, out)
        self.assertIn("already exists", out)
        self.assertIn("fix:", out)
        self.assertEqual((self.app / "posting.md").read_text(encoding="utf-8"),
                         "what was answered\n")

    def test_success_is_one_line(self):
        code, out = self.main(ASHBY_URL, ASHBY)
        self.assertEqual(code, 0, out)
        [line] = out.splitlines()
        self.assertIn("posting.md", line)
        self.assertIn("Forward Deployed Engineer", line)
        self.assertRegex(line, r"\d+ chars$")

    def test_called_wrong_is_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(posting.main(["fetch", ASHBY_URL]), 2)
            self.assertEqual(posting.main(["get", ASHBY_URL, str(self.app)]), 2)
        self.assertIn("usage: jsk posting fetch", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
