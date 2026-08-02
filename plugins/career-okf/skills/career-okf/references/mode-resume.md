# Mode: resume

Render the bundle into verified files. Read `references/ats-rules.md`, `references/writing-rules.md`
and the structure rules in `references/bundle-spec.md` first — or the bundle's own
`resume-generation/*` if present, which wins.

## Output

| File | For |
|---|---|
| `<Name>_Resume.docx` | Humans |
| `<Name>_Resume_ATS.docx` | Portals |
| `<Name>_Resume_ATS.txt` | Paste-in boxes |

## Build order

1. **Read** `profile/positioning.md`, `resume-generation/*`, all of `projects/`, and
   `open-questions.md` — you need to know what is unresolved before you publish it.

2. **Rank evidence** by `strength`, `recency` and fit to their stated target.

3. **Write the summary as a claim**, per `writing-rules.md`.

4. **Generate the presentation variant.**

5. **Generate the ATS variant** from the same content with the ATS-maximal transformations.

6. **Generate plain text** by extracting the ATS variant's paragraphs in order, prefixing list items
   with `- `.

7. **Verify — not optional:**

```bash
python3 scripts/check_ats.py <Name>_Resume.docx
python3 scripts/check_ats.py <Name>_Resume_ATS.docx --strict
```

Both must PASS. **Show the output.** Fix and re-run rather than explaining away a failure.

8. **Confirm two pages** by converting to PDF and counting. If it runs over, compress the oldest
roles. Never shrink below 10pt or 0.5" margins — both read as desperate and hurt parsing.

## Generating the .docx

Any method that produces clean OOXML is fine. Whatever you use, the output must satisfy
`check_ats.py` — that is the contract, not the tool.

If a `docx` library is unavailable, a `.docx` is a zip of XML and can be written with the standard
library alone. Keep the markup minimal: paragraphs, runs, a numbering definition for bullets, tab
stops for right-aligned dates. Minimal markup parses best anyway.

## Deliver

Present the files, say plainly which goes where, show the checker output. Then name what is still
weak — a missing certification, a thin metric, an unconfirmed claim. They can act on a known gap;
they cannot act on a compliment.
