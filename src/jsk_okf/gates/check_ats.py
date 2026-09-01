#!/usr/bin/env python3
"""Check a generated resume against the rules in references/ats-rules.md

Usage: python3 check_ats.py resume.pdf [--strict]
       python3 check_ats.py resume.txt [--strict]
       --strict  also enforce ATS-maximal rules (ASCII only, employer per role)

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
Reading a PDF needs pymupdf; the .txt path is standard library only.

This used to read a .docx and check seven structural hazards inside its XML - a
table, a text box, an image, a drawing, SmartArt, header content, a second
column. Those checks are gone because the thing they guarded against is gone:
the document is produced by one LaTeX template with no way to emit any of them.
A hazard the generator cannot express does not need re-checking on every render;
it needs a test on the generator, which is what the golden-file test over
emit_latex.py is for.

What remains is everything that was never structural in the first place - what
the extracted text says, and whether a parser can extract it at all.
"""
import sys, os, re, html, unicodedata

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


def codepoint(c):
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
    """
    t = text.strip()
    return 0 < len(t) <= HEADING_MAX and not t.endswith((".", "!", "?", ",", ";"))


def read_pdf(path):
    """(text, embedded font names). Raises ImportError without pymupdf."""
    import pymupdf                                 # noqa: PLC0415 - optional dependency

    pages, fonts = [], set()
    with pymupdf.open(path) as doc:
        for page in doc:
            pages.append(page.get_text())
            for font in page.get_fonts(full=False):
                fonts.add(font[3])
    return "\n".join(pages), sorted(fonts)


def read_txt(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), []


def has_phone(txt):
    """A date range is not a phone number. Require real digits, not four-digit years."""
    for cand in re.findall(r"\+?\d[\d\s().-]{6,}\d", txt):
        c = cand.strip()
        if re.fullmatch(r"(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}", c):
            continue
        if len(re.sub(r"\D", "", c)) >= 8:
            return True
    return False


def main(argv=None):
    """The gate, as an exit code. `argv` is the arguments alone, as check_prose.py takes them.

    It read `sys.argv` directly until `okf gates` needed to call it in-process
    rather than pay a fresh interpreter to do the same work. The CLI is the
    documented API and has not moved: the default reproduces it exactly.
    """
    argv = sys.argv[1:] if argv is None else list(argv)
    # The non-ASCII findings would otherwise be unprintable on a cp1252 console.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not argv:
        print("usage: check_ats.py resume.pdf | resume.txt [--strict]")
        return 2
    path = argv[0]
    strict = "--strict" in argv
    if not os.path.exists(path):
        print(f"file not found: {path}")
        return 2

    ext = os.path.splitext(path)[1].lower()

    def unreadable(reason):
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  unreadable: {reason}")
        print("\nDO NOT SEND - fix the failures above")
        return 1

    if ext == ".pdf":
        try:
            txt, fonts = read_pdf(path)
        except ImportError:
            print("NO PDF LIBRARY - cannot read the deliverable.")
            print("  check_ats.py needs pymupdf to extract text from a PDF:")
            print("      pip install pymupdf")
            print("  Without it the parse gate is unverifiable; treat the resume as unchecked.")
            return 2
        except Exception as e:
            return unreadable(f"{type(e).__name__}: {e}")
    elif ext == ".txt":
        try:
            txt, fonts = read_txt(path)
        except OSError as e:
            return unreadable(str(e))
    else:
        print(f"FAIL  format: {ext or '(none)'} - pass the .pdf or the .txt")
        return 1

    txt = html.unescape(txt)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    headings = [l for l in lines if is_heading(l)]

    fails, warns = [], []

    # --- can a parser read it at all? ---
    # This replaces the old font-name allowlist. A LaTeX PDF embeds Latin Modern,
    # which no such list would have contained, and the name was never the point:
    # what matters is whether text comes back out.
    if ext == ".pdf":
        if len("".join(txt.split())) < MIN_EXTRACTED_CHARS:
            fails.append("almost no extractable text - the PDF is a scan or an image, "
                         "or its fonts are not embedded; no parser can read a word of it")
        if not fonts:
            warns.append("no embedded fonts - text extraction may vary between parsers")

    # --- bullet glyphs a parser may not map to a list item ---
    for l in lines:
        if l[0] in RISKY_BULLETS and not l.startswith(SAFE_BULLETS):
            fails.append(f"bullet glyph {codepoint(l[0])} may not parse as a list item "
                         f"- use a plain hyphen or U+2022: {l[:45]!r}")
            break

    # --- required sections, in HEADINGS not prose ---
    heading_text = " \n ".join(headings).lower()
    for word, why in [("summary", "summary/profile section"), ("skills", "skills section"),
                      ("experience", "experience section"), ("education", "education section")]:
        if word not in heading_text:
            hint = "" if word in txt.lower() else " (the word appears nowhere in the document)"
            fails.append(f"no heading containing '{word}' - add a recognisable {why}{hint}")

    # --- contact detectability ---
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", txt):
        fails.append("no parseable email address found")
    if not has_phone(txt):
        fails.append("no parseable phone number found")

    # --- placeholders: ats-rules.md says search the finished text for '[' ---
    brackets = re.findall(r"\[[^\[\]]{0,60}\]", txt)
    if brackets:
        shown = ", ".join(repr(b) for b in brackets[:4])
        more = f" (+{len(brackets) - 4} more)" if len(brackets) > 4 else ""
        fails.append(f"unresolved placeholder(s) in text: {shown}{more}")
    if re.search(r"\[(?![^\[\]]{0,60}\])", txt):
        fails.append("unmatched open bracket '[' in text - a bracket in a resume is "
                     "almost always a leftover placeholder")

    # --- dates ---
    dates = re.findall(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", txt)
    if len(dates) < 4:
        warns.append(f"only {len(dates)} 'Mon YYYY' dates found - check date formatting")
    if re.search(r"\d{4}\s*[–—]\s*(?:\d{4}|Present)", txt):
        (fails if strict else warns).append(
            "en/em dash used in a date range - use a plain hyphen")

    # --- arrow trap: risky in BOTH variants, fatal in strict ---
    if "→" in txt or "➡" in txt:
        (fails if strict else warns).append(
            "arrow glyph in text - if stripped, adjacent job titles run together; "
            "spell the progression out")

    # --- typographic ligatures: one codepoint where a parser expects two ---
    # ats-rules.md has carried this rule since the T1 Computer Modern era and
    # nothing checked it, so the default render shipped `figures` as f-i-g-u-r-e-s
    # with a U+FB01 in the middle - a word no keyword search will ever match.
    # emit_latex.py breaks the pairs for the ATS-maximal variant, which is why this
    # is fatal there and a warning on the presentation one: the rule is that the
    # variant a parser reads must not contain them.
    found = sorted(set(c for c in txt if c in LIGATURES))
    if found:
        hidden = sorted({w for w in re.findall(r"\S+", txt) if any(c in w for c in found)})
        shown = ", ".join(repr(unicodedata.normalize("NFKC", w)) for w in hidden[:3])
        more = f" and {len(hidden) - 3} more" if len(hidden) > 3 else ""
        (fails if strict else warns).append(
            f"ligature{'s' if len(found) > 1 else ''} in text: "
            + ", ".join(codepoint(c) for c in found)
            + f" - a search for {shown}{more} will not match this document"
        )

    # --- fonts: informational on the presentation variant ---
    # The old allowlist warned on anything outside a set of Office fonts. One
    # template now decides the typeface, so a name check would warn on every
    # correct render and say nothing about any incorrect one.

    # --- strict / ATS-maximal ---
    if strict:
        # Ligatures are non-ASCII too, but the check above already named them and
        # said which words they hide; repeating them here is the same defect twice.
        na = sorted(set(c for c in txt if ord(c) > 127 and c not in LIGATURES))
        if na:
            fails.append("non-ASCII characters present: "
                         + ", ".join(codepoint(c) for c in na[:8]))
        # every role-looking line should name an employer
        bad = [l for l in lines
               if any(w in l for w in ROLE_WORDS) and re.search(r"\b(19|20)\d{2}\b", l)
               and "," not in l.split("|")[0]]
        if bad:
            warns.append(f"{len(bad)} role line(s) may not name an employer, "
                         f"e.g. {bad[0][:60]!r}")

    # --- report ---
    mode = "ATS-maximal (strict)" if strict else "presentation"
    print(f"checking: {os.path.basename(path)}   mode: {mode}")
    print(f"lines of extracted text: {len(lines)}   fonts: {', '.join(fonts) or 'n/a'}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails:
        print("  FAIL  " + f)
    for w in warns:
        print("  warn  " + w)
    print("\nPASS - safe to send" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
