"""The cost of loading a realistic workspace - the price every graph command pays."""
import tempfile
import time
import unittest
from pathlib import Path

from jsk.graph import ontology as O
from jsk.graph import store


def big_workspace(root, projects=300, applications=100):
    """A valid career of `projects` projects, 3 bullets each, and `applications`
    applications - about 10,000 quads, P0's measured size."""
    pfx = "".join(f"@prefix {n}: <{ns}> .\n" for n, ns in O.PREFIXES) + "\n"
    kb = [pfx, 'k:kb j:format 3 ; j:name "Big" ; j:updated "2026-09-20"^^xsd:date .\n',
          'k:person j:fullName "Big" ; j:provenance j:confirmed .\n',
          'k:org_o j:name "O" ; j:relationship j:employer ; j:provenance j:confirmed .\n',
          'k:pos_p j:organisation k:org_o ; j:title "T" ; j:start "2020-01" ; '
          'j:state j:ongoing ; j:seniority j:hands-on ; j:provenance j:confirmed .\n']
    for n in range(projects):
        kb.append(f'k:prj_p{n} j:name "Project {n}" ; j:position k:pos_p ; j:strength 3 ; '
                  f'j:recency 2024 ; j:domain c:healthcare ; j:uses c:kafka, c:python ; '
                  f'j:headlineMetric k:met_m{n} ; j:problem """Line one.\nLine two.""" ; '
                  f'j:provenance j:confirmed .\n'
                  f'k:met_m{n} j:subject "m{n}" .\n'
                  f'k:met_m{n}.v1 j:of k:met_m{n} ; j:value {n} ; j:confidence j:measured ; '
                  f'j:provenance j:confirmed .\n')
        for b in range(3):
            kb.append(f'k:ach_p{n}_bullet_{"abc"[b]} j:project k:prj_p{n} ; j:rank {b + 1} ; '
                      f'j:text "Did thing {b}." ; j:cites k:met_m{n} ; j:shows c:kafka ; '
                      f'j:provenance j:confirmed .\n')
    kb.append("c:healthcare a j:Domain .\n")
    (root / "career").mkdir()
    (root / "career" / "kb.ttl").write_text("".join(kb), encoding="utf-8")
    for a in range(applications):
        d = root / "applications" / f"a{a}"
        d.mkdir(parents=True)
        (d / "posting.md").write_text("We use Kafka.", encoding="utf-8")
        (d / "posting.ttl").write_text(
            pfx + f'k:post_a{a} j:company "C" ; j:title "T" ; j:captured "2026-09-01"^^xsd:date ;'
            f' j:advert "posting.md" .\n'
            + "".join(f'k:req_a{a}_r{r} j:posting k:post_a{a} ; j:asked "Kafka" ; '
                      f'j:necessity j:required ; j:quote "Kafka" .\n' for r in range(5)),
            encoding="utf-8")
        (d / "application.ttl").write_text(
            pfx + f'k:app_a{a} j:posting k:post_a{a} ; j:submitted "2026-09-02"^^xsd:date ; '
            f'j:carried k:ach_p{a}_bullet_a ; j:carriedVersion k:met_m{a}.v1 .\n'
            f'k:evt_a{a}_submitted j:application k:app_a{a} ; j:date "2026-09-02"^^xsd:date ; '
            f'j:kind j:submitted .\n', encoding="utf-8")


class Budget(unittest.TestCase):
    """Every command loads and validates the whole workspace, so it has to stay cheap.

    Target: under 400 ms for this workspace (P1 measured 250-390 ms on a Windows laptop,
    Python 3.13). Asserted at 3x, so a slow CI runner does not make it flaky; the figure
    is printed so a creeping cost shows in the log before it fails.
    """

    def test_ten_thousand_quads(self):
        with tempfile.TemporaryDirectory() as tmp:
            big_workspace(Path(tmp))
            store.load(tmp)                      # warm: the first query compiles caches
            start = time.perf_counter()
            s = store.load(tmp)
            ms = (time.perf_counter() - start) * 1000
            quads = len(s.ox)
            print(f"\n  budget: {quads} quads loaded and validated in {ms:.0f} ms")
            self.assertGreater(quads, 9000)
            self.assertEqual([f.text() for f in s.fails()], [])
            self.assertLess(ms, 1200)


if __name__ == "__main__":
    unittest.main()
