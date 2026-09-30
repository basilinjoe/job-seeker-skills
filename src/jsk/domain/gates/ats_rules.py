"""The parse gate's rules: what extracted resume text says, and whether a parser can read it.

These were the body of check_ats.main, which read the file, judged it and printed in one
function. Judging needs only the text and the fonts a reader returned, so it is here and
testable without a file; check_ats.py keeps the reading and the printing. Every rule
records into one Report, in the order the gate has always printed.
"""
import html
import re
import unicodedata

from .report import Report

# A heading is short and unpunctuated. Longer than this is prose, whatever it says.
HEADING_MAX = 40

# The Latin typographic ligatures a TeX engine emits by default. Each is one
# codepoint standing in for the two or three ASCII letters a parser is matching on.
LIGATURES = "ﬀﬁﬂﬃﬄﬅﬆ"

# Heuristic used only to warn that a role line may not name an employer. Software
# titles by default - edit this list for other fields.
ROLE_WORDS = ("Architect", "Engineer", "Lead", "Developer", "Manager", "Consultant")

# Bullets every parser maps to a list item. A PDF has no list *structure* to
# inspect - the marker is a glyph in the text either way - so the question is no
# longer "was this typed by hand?" but "is it a glyph a parser recognises?". The
# presentation template emits U+2022; the ATS-maximal one emits a hyphen.
SAFE_BULLETS = ("•", "-")
RISKY_BULLETS = "●▪◆▶‣⁃*·∙"

# Below this much extracted text the file is a scan, or its fonts are not
# embedded. Either way no ATS can read a word of it.
MIN_EXTRACTED_CHARS = 200

# A word broken across a line end: a letter, a hyphen, the line break, and a
# lowercase letter carrying on. The default template hyphenated, and the
# Everforth render's text layer held "Mi-\ncroservices" - a search for
# "Microservices" does not match it, and most parsers keep the hyphen because in
# extracted text a soft break looks exactly like a real one. A lowercase
# continuation is the tell: "Offline-\nTolerant" is a compound that happened to
# break at its own hyphen, and the templates forbid that break too.
SPLIT_WORD = re.compile(r"([A-Za-z]+)-\n([a-z]+)")


def codepoint(c):
    """Name one character for a finding.

    Args:
        c: a single character.

    Returns:
        "U+XXXX (NAME)", or "U+XXXX" alone for a codepoint Unicode gives no name.
    """
    try:
        return f"U+{ord(c):04X} ({unicodedata.name(c)})"
    except ValueError:
        return f"U+{ord(c):04X}"


def is_heading(text):
    """Short enough that it cannot be a sentence.

    The rule exists because a parser matching on 'Skills' cannot see a heading
    called 'Core Competencies' - and equally cannot see the word 'skills' buried
    in a summary sentence. The .docx path could also trust w:pStyle; extracted
    text has no styles, so only the shape of the line is left.

    Args:
        text: one line of extracted text.

    Returns:
        True for a non-empty line of at most HEADING_MAX characters that does not end
        on sentence punctuation.
    """
    t = text.strip()
    return 0 < len(t) <= HEADING_MAX and not t.endswith((".", "!", "?", ",", ";"))


def has_phone(txt):
    """A date range is not a phone number. Require real digits, not four-digit years.

    Args:
        txt: the document's text.

    Returns:
        True when some run of digits and separators holds at least eight digits and is
        not a year range.
    """
    for cand in re.findall(r"\+?\d[\d\s().-]{6,}\d", txt):
        c = cand.strip()
        if re.fullmatch(r"(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}", c):
            continue
        if len(re.sub(r"\D", "", c)) >= 8:
            return True
    return False


def extractable(txt, fonts, report):
    """Can a parser read the PDF at all, and did the typesetter split a word?

    This replaces the old font-name allowlist. A LaTeX PDF embeds Latin Modern,
    which no such list would have contained, and the name was never the point:
    what matters is whether text comes back out.

    Args:
        txt: the PDF's extracted text.
        fonts: the embedded font names the reader found.
        report: the Report the findings are added to.
    """
    if len("".join(txt.split())) < MIN_EXTRACTED_CHARS:
        report.fail("almost no extractable text - the PDF is a scan or an image, "
                    "or its fonts are not embedded; no parser can read a word of it")
    if not fonts:
        report.warn("no embedded fonts - text extraction may vary between parsers")
    # Fatal in both modes, unlike ligatures: people upload the presentation
    # PDF to portals, and a broken keyword is missing from either variant.
    # Only for a PDF - the .txt has no line breaks a typesetter chose.
    splits = SPLIT_WORD.findall(txt)
    if splits:
        shown = ", ".join(repr(f"{a}-{b}") for a, b in splits[:3])
        more = f" and {len(splits) - 3} more" if len(splits) > 3 else ""
        report.fail(
            f"word{'s' if len(splits) > 1 else ''} split across a line end by a "
            f"hyphen: {shown}{more} - a keyword search for "
            f"{splits[0][0] + splits[0][1]!r} will not match this document\n"
            f"        fix: re-render - the current templates turn hyphenation off; "
            f"a PDF made elsewhere needs hyphenation disabled at its source")


def bullet_glyphs(lines, report):
    """Fail the first line opening on a bullet glyph a parser may not map to a list item.

    Args:
        lines: the document's non-empty lines, stripped.
        report: the Report the finding is added to.
    """
    for l in lines:
        if l[0] in RISKY_BULLETS and not l.startswith(SAFE_BULLETS):
            report.fail(f"bullet glyph {codepoint(l[0])} may not parse as a list item "
                        f"- use a plain hyphen or U+2022: {l[:45]!r}")
            break


def sections(lines, txt, report):
    """Fail each required section with no heading naming it: in a heading, not in prose.

    Args:
        lines: the document's non-empty lines, stripped.
        txt: the document's text, to say when the word is missing altogether.
        report: the Report the findings are added to.
    """
    heading_text = " \n ".join(l for l in lines if is_heading(l)).lower()
    for word, why in [("summary", "summary/profile section"), ("skills", "skills section"),
                      ("experience", "experience section"), ("education", "education section")]:
        if word not in heading_text:
            hint = "" if word in txt.lower() else " (the word appears nowhere in the document)"
            report.fail(f"no heading containing '{word}' - add a recognisable {why}{hint}")


def contact(txt, report):
    """Fail a document with no parseable email address or phone number.

    Args:
        txt: the document's text.
        report: the Report the findings are added to.
    """
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", txt):
        report.fail("no parseable email address found")
    if not has_phone(txt):
        report.fail("no parseable phone number found")


def brackets(txt, report):
    """Fail a placeholder left in the text: ats-rules.md says search it for '['.

    Args:
        txt: the document's text.
        report: the Report the findings are added to.
    """
    found = re.findall(r"\[[^\[\]]{0,60}\]", txt)
    if found:
        shown = ", ".join(repr(b) for b in found[:4])
        more = f" (+{len(found) - 4} more)" if len(found) > 4 else ""
        report.fail(f"unresolved placeholder(s) in text: {shown}{more}")
    if re.search(r"\[(?![^\[\]]{0,60}\])", txt):
        report.fail("unmatched open bracket '[' in text - a bracket in a resume is "
                    "almost always a leftover placeholder")


def dates(txt, strict, report):
    """Warn on too few 'Mon YYYY' dates; flag an en or em dash in a date range.

    Args:
        txt: the document's text.
        strict: the ATS-maximal variant, where the dash is a failure, not a warning.
        report: the Report the findings are added to.
    """
    found = re.findall(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", txt)
    if len(found) < 4:
        report.warn(f"only {len(found)} 'Mon YYYY' dates found - check date formatting")
    if re.search(r"\d{4}\s*[–—]\s*(?:\d{4}|Present)", txt):
        (report.fail if strict else report.warn)(
            "en/em dash used in a date range - use a plain hyphen")


def arrows(txt, strict, report):
    """Flag an arrow glyph: risky in both variants, fatal in the strict one.

    Args:
        txt: the document's text.
        strict: the ATS-maximal variant.
        report: the Report the finding is added to.
    """
    if "→" in txt or "➡" in txt:
        (report.fail if strict else report.warn)(
            "arrow glyph in text - if stripped, adjacent job titles run together; "
            "spell the progression out")


def ligatures(txt, strict, report):
    """Flag typographic ligatures: one codepoint where a parser expects two.

    ats-rules.md has carried this rule since the T1 Computer Modern era and
    nothing checked it, so the default render shipped `figures` as f-i-g-u-r-e-s
    with a U+FB01 in the middle - a word no keyword search will ever match.
    emit_latex.py breaks the pairs for the ATS-maximal variant, which is why this
    is fatal there and a warning on the presentation one: the rule is that the
    variant a parser reads must not contain them.

    Args:
        txt: the document's text.
        strict: the ATS-maximal variant.
        report: the Report the finding is added to.
    """
    found = sorted(set(c for c in txt if c in LIGATURES))
    if found:
        hidden = sorted({w for w in re.findall(r"\S+", txt) if any(c in w for c in found)})
        shown = ", ".join(repr(unicodedata.normalize("NFKC", w)) for w in hidden[:3])
        more = f" and {len(hidden) - 3} more" if len(hidden) > 3 else ""
        (report.fail if strict else report.warn)(
            f"ligature{'s' if len(found) > 1 else ''} in text: "
            + ", ".join(codepoint(c) for c in found)
            + f" - a search for {shown}{more} will not match this document"
        )


def ats_maximal(txt, lines, report):
    """The strict variant's own rules: ASCII only, and an employer on every role line.

    Args:
        txt: the document's text.
        lines: the document's non-empty lines, stripped.
        report: the Report the findings are added to.
    """
    # Ligatures are non-ASCII too, but the check above already named them and
    # said which words they hide; repeating them here is the same defect twice.
    na = sorted(set(c for c in txt if ord(c) > 127 and c not in LIGATURES))
    if na:
        report.fail("non-ASCII characters present: "
                    + ", ".join(codepoint(c) for c in na[:8]))
    bad = [l for l in lines
           if any(w in l for w in ROLE_WORDS) and re.search(r"\b(19|20)\d{2}\b", l)
           and "," not in l.split("|")[0]]
    if bad:
        report.warn(f"{len(bad)} role line(s) may not name an employer, "
                    f"e.g. {bad[0][:60]!r}")


def judge(txt, fonts, *, pdf, strict):
    """Every parse-gate rule over one document's extracted text, in the gate's order.

    The fonts are informational: the old allowlist warned on anything outside a set of
    Office fonts, and one template now decides the typeface, so a name check would warn
    on every correct render and say nothing about any incorrect one.

    Args:
        txt: the text a reader extracted, HTML entities not yet decoded.
        fonts: the embedded font names, empty for a .txt.
        pdf: the text came from a PDF, so the extraction rules apply.
        strict: the ATS-maximal variant's rules apply, and some warnings become failures.

    Returns:
        (lines, report): the document's non-empty lines, stripped, and the Report of
        its findings.
    """
    txt = html.unescape(txt)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    report = Report()
    if pdf:
        extractable(txt, fonts, report)
    bullet_glyphs(lines, report)
    sections(lines, txt, report)
    contact(txt, report)
    brackets(txt, report)
    dates(txt, strict, report)
    arrows(txt, strict, report)
    ligatures(txt, strict, report)
    if strict:
        ats_maximal(txt, lines, report)
    return lines, report
