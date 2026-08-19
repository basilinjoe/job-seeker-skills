#!/usr/bin/env python3
"""Check a generated resume .docx against the rules in references/ats-rules.md

Usage: python3 check_ats.py resume.docx [--strict]
       --strict  also enforce ATS-maximal rules (ASCII only, employer per role)

On Windows use `python` or `py -3` in place of `python3`.

Exit 0 = pass. Exit 1 = do not send this file. Exit 2 = usage error.
No third-party dependencies.
"""
import sys, os, re, zipfile, html, unicodedata

STD_FONTS = {"calibri","arial","helvetica","georgia","times new roman","verdana","tahoma","garamond"}

# Heuristic used only to warn that a role line may not name an employer. Software
# titles by default - edit this list for other fields.
ROLE_WORDS = ("Architect","Engineer","Lead","Developer","Manager","Consultant")

# A heading is short and unpunctuated. Longer than this is prose, whatever it says.
HEADING_MAX = 40

def plain_text(xml):
    t = re.sub(r"<w:tab\b[^>]*/?>", "\t", xml)
    t = re.sub(r"<w:(?:br|cr)\b[^>]*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)

def paragraphs_of(doc):
    """[(style, text)] one entry per <w:p>, in document order."""
    out = []
    for m in re.finditer(r"<w:p(?:\s[^>]*)?>(.*?)</w:p>", doc, re.S):
        chunk = m.group(1)
        style = re.search(r'<w:pStyle\s+w:val="([^"]+)"', chunk)
        out.append((style.group(1) if style else "", plain_text(chunk)))
    return out

def is_heading(style, text):
    """Styled as a heading, or short enough that it cannot be a sentence.

    The rule exists because a parser matching on 'Skills' cannot see a heading
    called 'Core Competencies' - and equally cannot see the word 'skills'
    buried in a summary sentence.
    """
    if style.lower().startswith("heading"):
        return True
    t = text.strip()
    return 0 < len(t) <= HEADING_MAX and not t.endswith((".", "!", "?", ",", ";"))

def codepoint(c):
    try:
        return f"U+{ord(c):04X} ({unicodedata.name(c)})"
    except ValueError:
        return f"U+{ord(c):04X}"

def main():
    # The non-ASCII findings would otherwise be unprintable on a cp1252 console.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("usage: check_ats.py resume.docx [--strict]"); return 2
    path = sys.argv[1]
    strict = "--strict" in sys.argv
    if not os.path.exists(path):
        print(f"file not found: {path}"); return 2
    if not path.lower().endswith(".docx"):
        print(f"FAIL  format: {os.path.splitext(path)[1]} - ATS requires .docx"); return 1

    def unreadable(reason):
        print(f"checking: {os.path.basename(path)}")
        print("\nFAIL 1   WARN 0")
        print(f"  FAIL  not a readable .docx: {reason}")
        print("\nDO NOT SEND - fix the failures above")
        return 1

    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
        doc = z.read("word/document.xml").decode("utf8", "replace")
    except zipfile.BadZipFile:
        return unreadable("not a zip archive - a .docx is a zip of XML")
    except KeyError:
        return unreadable("no word/document.xml inside")
    except OSError as e:
        return unreadable(str(e))

    paras = paragraphs_of(doc)
    txt = "\n".join(t for _, t in paras)
    lines = [l.strip() for t in (p[1] for p in paras) for l in t.split("\n") if l.strip()]
    headings = [t.strip() for style, t in paras if is_heading(style, t)]

    fails, warns = [], []

    # --- structural killers ---
    if "<w:tbl>" in doc: fails.append("contains a TABLE - remove; use tab stops or plain paragraphs")
    if "w:txbxContent" in doc or "<v:shape" in doc: fails.append("contains a TEXT BOX - content may be skipped entirely")
    if any("word/media/" in n for n in names): fails.append("contains IMAGES - remove")
    if "<w:drawing" in doc: fails.append("contains DRAWING objects - remove")
    if any(("diagrams" in n) or ("charts" in n) for n in names): fails.append("contains SmartArt or a chart - remove")
    for n in names:
        if re.match(r"word/(header|footer)\d*\.xml$", n):
            body = plain_text(z.read(n).decode("utf8", "replace")).strip()
            if body: fails.append(f"content in {n} - parsers discard headers/footers; move to body")
    m = re.search(r'<w:cols[^>]*w:num="(\d+)"', doc)
    if m and int(m.group(1)) > 1: fails.append(f"multi-column layout ({m.group(1)} cols) - breaks reading order")

    # --- literal bullet glyphs typed as text ---
    for l in lines:
        if re.match(r"^[•●▪*]\s", l) or re.match(r"^-\s", l):
            fails.append(f"literal bullet glyph typed as text: {l[:45]!r}"); break

    # --- required sections, in HEADINGS not prose ---
    heading_text = " \n ".join(headings).lower()
    for word, why in [("summary","summary/profile section"),("skills","skills section"),
                      ("experience","experience section"),("education","education section")]:
        if word not in heading_text:
            hint = "" if word in txt.lower() else " (the word appears nowhere in the document)"
            fails.append(f"no heading containing '{word}' - add a recognisable {why}{hint}")

    # --- contact detectability ---
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", txt): fails.append("no parseable email address found")
    if not has_phone(txt): fails.append("no parseable phone number found")

    # --- placeholders: ats-rules.md says search the finished text for '[' ---
    brackets = re.findall(r"\[[^\[\]]{0,60}\]", txt)
    if brackets:
        shown = ", ".join(repr(b) for b in brackets[:4])
        more = f" (+{len(brackets) - 4} more)" if len(brackets) > 4 else ""
        fails.append(f"unresolved placeholder(s) in text: {shown}{more}")
    if re.search(r"\[(?![^\[\]]{0,60}\])", txt):
        fails.append("unmatched open bracket '[' in text - a bracket in a resume is almost always a leftover placeholder")

    # --- dates ---
    dates = re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", txt)
    if len(dates) < 4: warns.append(f"only {len(dates)} 'Mon YYYY' dates found - check date formatting")
    if re.search(r"\d{4}\s*[–—]\s*(?:\d{4}|Present)", txt):
        (fails if strict else warns).append("en/em dash used in a date range - use a plain hyphen")

    # --- arrow trap: risky in BOTH variants, fatal in strict ---
    if "→" in txt or "➡" in txt:
        msg = "arrow glyph in text - if stripped, adjacent job titles run together; spell the progression out"
        (fails if strict else warns).append(msg)

    # --- fonts: document.xml alone misses anything set in the style definitions ---
    font_xml = doc
    if "word/styles.xml" in names:
        font_xml += z.read("word/styles.xml").decode("utf8", "replace")
    fonts = set(f.lower() for f in re.findall(r'w:ascii="([^"]+)"', font_xml))
    odd = [f for f in fonts if f not in STD_FONTS]
    if odd: warns.append(f"non-standard font(s): {odd}")

    # --- strict / ATS-maximal ---
    if strict:
        na = sorted(set(c for c in txt if ord(c) > 127))
        if na:
            fails.append("non-ASCII characters present: " + ", ".join(codepoint(c) for c in na[:8]))
        # every role-looking line should name an employer
        bad = [l for l in lines
               if any(w in l for w in ROLE_WORDS) and re.search(r"\b(19|20)\d{2}\b", l)
               and "," not in l.split("|")[0]]
        if bad: warns.append(f"{len(bad)} role line(s) may not name an employer, e.g. {bad[0][:60]!r}")

    # --- report ---
    print(f"checking: {os.path.basename(path)}   mode: {'ATS-maximal (strict)' if strict else 'presentation'}")
    print(f"lines of extracted text: {len(lines)}   fonts: {', '.join(sorted(fonts)) or 'default'}")
    print(f"\nFAIL {len(fails)}   WARN {len(warns)}")
    for f in fails: print("  FAIL  " + f)
    for w in warns: print("  warn  " + w)
    print("\nPASS - safe to send" if not fails else "\nDO NOT SEND - fix the failures above")
    return 1 if fails else 0

def has_phone(txt):
    """A date range is not a phone number. Require real digits, not four-digit years."""
    for cand in re.findall(r"\+?\d[\d\s().-]{6,}\d", txt):
        c = cand.strip()
        if re.fullmatch(r"(19|20)\d{2}\s*[-–—]\s*(19|20)\d{2}", c):
            continue
        if len(re.sub(r"\D", "", c)) >= 8:
            return True
    return False

if __name__ == "__main__":
    sys.exit(main())
