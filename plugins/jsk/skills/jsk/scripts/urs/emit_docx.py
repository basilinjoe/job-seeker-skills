"""DOCX emitter: minimal OOXML, standard library only.

Minimal markup is not a shortcut, it is the requirement. Every element this file
declines to emit - tables, text boxes, drawings, headers, footers, columns - is
one that `check_ats.py` fails a document for. The contract is that output passes
that checker plain and under --strict; the tool used to produce it is incidental.

Two details that have burned real resumes, both from mode-resume.md:

  * The bullet glyph lives in numbering.xml as U+2022 in Calibri, never as
    U+F0B7 in Symbol. The Symbol form renders as a tofu box wherever the font
    fails to resolve, and no XML-level checker can see it happen.
  * Fonts are set as w:ascii on every run and in the style definitions, and
    w:asciiTheme is never emitted - the theme attribute wins where both exist,
    which is how a document with Calibri written all over it renders in
    something else entirely.
"""
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FONT = "Calibri"

PAGE = {
    "A4": (11906, 16838),
    "Letter": (12240, 15840),
}
LETTER_REGIONS = {"US", "CA"}
MARGIN = 1080          # 0.75in in twips
TAB_SLACK = 40         # keep the right tab just inside the text column

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>"""

NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="%s">
<w:abstractNum w:abstractNumId="0">
  <w:multiLevelType w:val="singleLevel"/>
  <w:lvl w:ilvl="0">
    <w:start w:val="1"/>
    <w:numFmt w:val="bullet"/>
    <w:lvlText w:val="•"/>
    <w:lvlJc w:val="left"/>
    <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:hint="default"/></w:rPr>
  </w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>""" % (W, FONT, FONT)

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="%(w)s">
<w:docDefaults>
  <w:rPrDefault><w:rPr>
    <w:rFonts w:ascii="%(f)s" w:hAnsi="%(f)s" w:cs="%(f)s"/>
    <w:sz w:val="%(sz)d"/><w:szCs w:val="%(sz)d"/>
  </w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr>
    <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
  </w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
  <w:name w:val="Normal"/>
  <w:rPr><w:rFonts w:ascii="%(f)s" w:hAnsi="%(f)s"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
  <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
  <w:pPr>
    <w:keepNext/><w:spacing w:before="200" w:after="60"/>
    <w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="auto"/></w:pBdr>
    <w:outlineLvl w:val="0"/>
  </w:pPr>
  <w:rPr><w:rFonts w:ascii="%(f)s" w:hAnsi="%(f)s"/><w:b/><w:caps/><w:sz w:val="%(hsz)d"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
  <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:keepNext/><w:spacing w:before="120" w:after="20"/><w:outlineLvl w:val="1"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="%(f)s" w:hAnsi="%(f)s"/><w:b/></w:rPr>
</w:style>
</w:styles>"""


def _run(text, bold=False, italic=False, size=None):
    rpr = ['<w:rFonts w:ascii="%s" w:hAnsi="%s"/>' % (FONT, FONT)]
    if bold:
        rpr.append("<w:b/>")
    if italic:
        rpr.append("<w:i/>")
    if size:
        rpr.append('<w:sz w:val="%d"/>' % size)
    return "<w:r><w:rPr>%s</w:rPr><w:t xml:space=\"preserve\">%s</w:t></w:r>" % (
        "".join(rpr), escape(text or ""))


def _tab():
    return "<w:r><w:tab/></w:r>"


def _para(runs, style=None, tab_at=None, bullet=False, align=None,
          space_before=None, space_after=None, keep_next=False):
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if bullet:
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
        ppr.append('<w:ind w:left="360" w:hanging="180"/>')
    if keep_next:
        ppr.append("<w:keepNext/>")
    if tab_at:
        ppr.append('<w:tabs><w:tab w:val="right" w:pos="%d"/></w:tabs>' % tab_at)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    spacing = []
    if space_before is not None:
        spacing.append('w:before="%d"' % space_before)
    if space_after is not None:
        spacing.append('w:after="%d"' % space_after)
    if spacing:
        ppr.append("<w:spacing %s/>" % " ".join(spacing))
    prefix = "<w:pPr>%s</w:pPr>" % "".join(ppr) if ppr else ""
    return "<w:p>%s%s</w:p>" % (prefix, "".join(runs))


def emit(plan, path):
    paper = "Letter" if plan.get("region") in LETTER_REGIONS else "A4"
    width, height = PAGE[paper]
    tab_at = width - 2 * MARGIN - TAB_SLACK

    body = [
        _para([_run(plan["name"], bold=True, size=34)], align="center", space_after=20),
    ]
    for line in plan["header_lines"]:
        body.append(_para([_run(line)], align="center", space_after=20))

    for section in plan["sections"]:
        if section.get("heading"):
            body.append(_para([_run(section["heading"])], style="Heading1"))
        body.extend(_section(section, tab_at))

    body.append(
        '<w:sectPr><w:pgSz w:w="%d" w:h="%d"/>'
        '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
        'w:header="0" w:footer="0" w:gutter="0"/>'
        '<w:cols w:num="1" w:space="0"/></w:sectPr>'
        % (width, height, MARGIN, MARGIN, MARGIN, MARGIN)
    )

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>'
        % (W, "".join(body))
    )
    styles = STYLES % {"w": W, "f": FONT, "sz": 21, "hsz": 24}

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", NUMBERING)
    return path


def _section(section, tab_at):
    kind = section["kind"]
    out = []
    if kind == "text":
        for para in section["paragraphs"]:
            out.append(_para([_run(para)], space_after=40))
    elif kind == "lines":
        for line in section["lines"]:
            out.append(_para([_run(line)], space_after=20))
    elif kind == "rows":
        for row in section["rows"]:
            out.append(_para(
                [_run(row["label"] + ": ", bold=True), _run(", ".join(row["items"]))],
                space_after=20))
    elif kind == "entries":
        for entry in section["entries"]:
            if entry.get("org_line"):
                out.append(_pair(entry["org_line"], entry.get("org_right"), tab_at,
                                 bold=True, space_before=120))
            for n, role in enumerate(entry["roles"]):
                out.append(_pair(role["left"], role.get("right"), tab_at,
                                 italic=not entry.get("org_line"),
                                 bold=not entry.get("org_line"),
                                 space_before=120 if not entry.get("org_line") and not n else None))
            for line in entry["lines"]:
                out.append(_para([_run(line)], space_after=20))
            for bullet in entry["bullets"]:
                out.append(_para([_run(bullet)], bullet=True, space_after=20))
    return out


def _pair(left, right, tab_at, bold=False, italic=False, space_before=None):
    runs = [_run(left, bold=bold, italic=italic)]
    if right:
        runs.extend([_tab(), _run(right)])
    return _para(runs, tab_at=tab_at if right else None, keep_next=True,
                 space_before=space_before, space_after=20)
