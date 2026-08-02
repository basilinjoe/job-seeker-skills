#!/usr/bin/env python3
"""Check a generated resume .docx against resume-generation/ats-rules.md

Usage: python3 framework/check_ats.py resume.docx [--strict]
       --strict  also enforce ATS-maximal rules (ASCII only, employer per role)

Exit 0 = pass. Exit 1 = do not send this file.
No third-party dependencies.
"""
import sys, os, re, zipfile, html

STD_FONTS = {"calibri","arial","helvetica","georgia","times new roman","verdana","tahoma","garamond"}

def text_of(doc):
    t = re.sub(r"<w:tab[^>]*/>", "\t", doc)
    t = re.sub(r"</w:p>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)

def main():
    if len(sys.argv) < 2:
        print("usage: check_ats.py resume.docx [--strict]"); return 2
    path = sys.argv[1]
    strict = "--strict" in sys.argv
    if not os.path.exists(path):
        print(f"file not found: {path}"); return 2
    if not path.lower().endswith(".docx"):
        print(f"FAIL  format: {os.path.splitext(path)[1]} - ATS requires .docx"); return 1

    z = zipfile.ZipFile(path)
    names = z.namelist()
    doc = z.read("word/document.xml").decode("utf8")
    txt = text_of(doc)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]

    fails, warns = [], []

    # --- structural killers ---
    if "<w:tbl>" in doc: fails.append("contains a TABLE - remove; use tab stops or plain paragraphs")
    if "w:txbxContent" in doc or "<v:shape" in doc: fails.append("contains a TEXT BOX - content may be skipped entirely")
    if any("word/media/" in n for n in names): fails.append("contains IMAGES - remove")
    if "<w:drawing>" in doc: fails.append("contains DRAWING objects - remove")
    if any(("diagrams" in n) or ("charts" in n) for n in names): fails.append("contains SmartArt or a chart - remove")
    for n in names:
        if re.match(r"word/(header|footer)\d*\.xml$", n):
            body = text_of(z.read(n).decode("utf8")).strip()
            if body: fails.append(f"content in {n} - parsers discard headers/footers; move to body")
    m = re.search(r'<w:cols[^>]*w:num="(\d+)"', doc)
    if m and int(m.group(1)) > 1: fails.append(f"multi-column layout ({m.group(1)} cols) - breaks reading order")

    # --- literal bullet glyphs typed as text ---
    for l in lines:
        if re.match(r"^[•●▪*]\s", l) or re.match(r"^-\s", l):
            fails.append(f"literal bullet glyph typed as text: {l[:45]!r}"); break

    # --- required sections ---
    joined = txt.lower()
    for word, why in [("summary","summary/profile section"),("skills","skills section"),
                      ("experience","experience section"),("education","education section")]:
        if word not in joined:
            fails.append(f"no heading containing '{word}' - add a recognisable {why}")

    # --- contact detectability ---
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", txt): fails.append("no parseable email address found")
    if not re.search(r"(\+?\d[\d\s()-]{7,}\d)", txt):  fails.append("no parseable phone number found")

    # --- placeholders ---
    ph = re.findall(r"\[(?:[A-Za-z]{0,3}%?|[^\]]{0,30}(?:need|TBD|recommend|delete)[^\]]{0,30})\]", txt, re.I)
    if ph: fails.append(f"unresolved placeholder(s) in text: {ph[:3]}")

    # --- dates ---
    dates = re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b", txt)
    if len(dates) < 4: warns.append(f"only {len(dates)} 'Mon YYYY' dates found - check date formatting")
    if re.search(r"\d{4}\s*[–—]\s*(?:\d{4}|Present)", txt):
        (fails if strict else warns).append("en/em dash used in a date range - use a plain hyphen")

    # --- arrow trap: risky in BOTH variants, fatal in strict ---
    if "\u2192" in txt or "\u27a1" in txt:
        msg = "arrow glyph in text - if stripped, adjacent job titles run together; spell the progression out"
        (fails if strict else warns).append(msg)

    # --- fonts ---
    fonts = set(f.lower() for f in re.findall(r'w:ascii="([^"]+)"', doc))
    odd = [f for f in fonts if f not in STD_FONTS]
    if odd: warns.append(f"non-standard font(s): {odd}")

    # --- strict / ATS-maximal ---
    if strict:
        na = sorted(set(c for c in txt if ord(c) > 127))
        if na:
            fails.append("non-ASCII characters present: " +
                         ", ".join(f"U+{ord(c):04X} {c!r}" for c in na[:8]))
        # every role-looking line should name an employer
        role_words = ("Architect","Engineer","Lead","Developer","Manager","Consultant")
        bad = [l for l in lines
               if any(w in l for w in role_words) and re.search(r"\b(19|20)\d{2}\b", l)
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

if __name__ == "__main__":
    sys.exit(main())
