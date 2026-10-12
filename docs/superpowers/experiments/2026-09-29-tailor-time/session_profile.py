"""One Claude Code session, turn by turn: each tool call's duration, result size and the
context it ran at, every text the model showed, and the token totals - for the session and
each of its subagents.

Usage: python session_profile.py <session>
  <session> is ~/.claude/projects/<project>/<uuid>, without .jsonl; its subagents are read
  from <session>/subagents/*.jsonl."""
import json, sys, os, glob
from datetime import datetime

def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def short(x, n=160):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    s = s.replace("\n", " ")
    return s[:n]

def analyze(path, label):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    print(f"\n######## {label}  ({os.path.basename(path)})")
    first = last = None
    tot = dict(inp=0, out=0, cr=0, cc=0)
    pending = {}
    events = []
    seen_msg = set()
    for r in rows:
        t = r.get("timestamp")
        if t:
            first = first or ts(t); last = ts(t)
        m = r.get("message")
        if r.get("type") == "assistant" and m:
            mid = m.get("id")
            u = m.get("usage", {})
            if mid not in seen_msg:
                seen_msg.add(mid)
                tot["inp"] += u.get("input_tokens", 0); tot["out"] += u.get("output_tokens", 0)
                tot["cr"] += u.get("cache_read_input_tokens", 0); tot["cc"] += u.get("cache_creation_input_tokens", 0)
            for c in m.get("content", []):
                if c.get("type") == "tool_use":
                    pending[c["id"]] = (ts(t), c["name"], c["input"], u.get("cache_read_input_tokens",0)+u.get("cache_creation_input_tokens",0)+u.get("input_tokens",0))
                elif c.get("type") == "text" and c["text"].strip():
                    events.append((ts(t), "TEXT", short(c["text"], 200), 0, 0))
        elif r.get("type") == "user" and m:
            content = m.get("content")
            if isinstance(content, str):
                events.append((ts(t), "USER", short(content, 300), 0, 0))
            else:
                for c in content or []:
                    if c.get("type") == "tool_result" and c["tool_use_id"] in pending:
                        st, name, inp, ctx = pending.pop(c["tool_use_id"])
                        res = c.get("content")
                        rl = len(json.dumps(res, ensure_ascii=False)) if res else 0
                        dur = (ts(t) - st).total_seconds()
                        desc = inp.get("command") or inp.get("file_path") or inp.get("description") or inp.get("skill") or inp.get("pattern") or inp
                        events.append((st, name, short(desc, 180), dur, rl, ctx))
                    elif c.get("type") == "text":
                        events.append((ts(t), "USER", short(c["text"], 300), 0, 0))
    print(f"wall: {first} -> {last}  = {(last-first).total_seconds()/60:.1f} min")
    print(f"tokens: in={tot['inp']} out={tot['out']} cache_read={tot['cr']} cache_create={tot['cc']}  assistant msgs={len(seen_msg)}")
    for e in events:
        ctx = e[5] if len(e) > 5 else ""
        print(f"{e[0].strftime('%H:%M:%S')} {e[1]:<10} dur={e[3]:6.1f}s res={e[4]:6d}c ctx={ctx} | {e[2]}")

if len(sys.argv) != 2:
    sys.exit(__doc__)
base = sys.argv[1].removesuffix(".jsonl")
analyze(base + ".jsonl", "MAIN")
for f in sorted(glob.glob(base + "/subagents/*.jsonl")):
    meta = f.replace(".jsonl", ".meta.json")
    try: print("META", open(meta).read()[:300])
    except: pass
    analyze(f, "SUB")
