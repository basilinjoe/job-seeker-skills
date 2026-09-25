"""A last page under half full is reported beside the page count.

The Everforth render came out on two pages against a budget of two - reported as a
success - with 45% of page 1 given to a padded skills block and page 2 half empty.
The count was right and the page was wasted; only the fill says so.
"""
import unittest

from jsk.urs import render_resume


class TheLastPageIsMeasured(unittest.TestCase):
    def report(self, count, budget, fill):
        return render_resume.page_report("Resume.pdf", count, budget, fill)

    def test_a_half_empty_last_page_is_named(self):
        line = self.report(2, 2, 38.0)
        self.assertIn("page 2 is 38% full", line)
        self.assertIn("or fit it to 1 page", line)

    def test_a_full_last_page_says_nothing_more(self):
        self.assertEqual(self.report(2, 2, 82.0),
                         "  pages  Resume.pdf: 2 pages against a budget of 2")

    def test_a_one_page_resume_is_not_told_to_fill_itself(self):
        """One page with room left is a short resume, not a wasted page."""
        self.assertNotIn("full", self.report(1, 2, 30.0))

    def test_over_budget_still_wins(self):
        self.assertIn("OVER BUDGET", self.report(3, 2, 20.0))

    def test_no_measurement_keeps_the_old_line(self):
        self.assertEqual(self.report(2, 2, None),
                         "  pages  Resume.pdf: 2 pages against a budget of 2")


if __name__ == "__main__":
    unittest.main()
