#!/usr/bin/env python3
"""Generate 500 user requests (5 per tool) with glm-5p3. Gold label = the sampled tool (not model-chosen).
Writes data/all.jsonl, then split_data.py makes test/train."""
import json, random, re, sys, concurrent.futures as cf
import fw
cat = json.load(open("data/catalog.json"))
by_server = {}
for t in cat: by_server.setdefault(t["server"], []).append(t)
STYLES = [
 "terse, like a chat message to a bot (under 15 words)",
 "conversational and a bit rambling, with context about why",
 "written by a non-native English speaker, with one or two small grammar slips",
 "phrased indirectly so the tool is implied, never naming the product or the action verb from the catalog",
 "a message to a colleague that an assistant intercepted, including a name and a specific detail (date, file, id)",
]
SYS = "You write realistic user requests for testing an AI assistant's tool routing. Output strictly valid JSON."
def prompt(tool):
    sib = [t for t in by_server[tool["server"]] if t["name"] != tool["name"]]
    others = random.sample([t for t in cat if t["server"] != tool["server"]], 4)
    neigh = "\n".join(f"- {t['name']}: {t['description']}" for t in sib + others)
    styles = "\n".join(f"{i+1}. {s}" for i, s in enumerate(STYLES))
    return f"""TARGET TOOL (the request must need exactly this tool):
- {tool['name']}: {tool['description']}

NEIGHBOR TOOLS (the request must clearly NOT be solvable by any of these; a careful reader should be able to rule each out):
{neigh}

Write 5 different user requests, one in each style below. Each must be a single message a real person would type to an assistant, must require the TARGET tool and none of the neighbors, and must not mention the tool name or the server name literally (saying "GitHub" is fine, saying "create_issue" is not). Vary the domain details (companies, names, dates, filenames) across the 5.
Styles:
{styles}

Return JSON: {{"requests": ["...", "...", "...", "...", "..."]}}"""
def gen(tool):
    msgs = [{"role":"system","content":SYS},{"role":"user","content":prompt(tool)}]
    for attempt in range(3):
        r = fw.chat("glm-5p3", msgs, max_tokens=1500, extra={"reasoning_effort":"low", "response_format":{"type":"json_object"}}, note="gen", temperature=0.8)
        txt = r["content"].strip()
        txt = re.sub(r"^```(json)?|```$", "", txt.strip()).strip()
        try:
            reqs = json.loads(txt)["requests"]
            if isinstance(reqs, list) and len(reqs) == 5 and all(isinstance(x, str) and len(x) > 8 for x in reqs):
                return [{"tool": tool["name"], "style": i, "text": x.strip()} for i, x in enumerate(reqs)]
        except Exception as e:
            print("parse fail", tool["name"], str(e)[:80], file=sys.stderr)
    return []
random.seed(11)
rows = []
with cf.ThreadPoolExecutor(6) as ex:
    for out in ex.map(gen, cat):
        rows.extend(out); print(len(rows), end=" ", flush=True)
rows.sort(key=lambda r: (r["tool"], r["style"]))
for i, r in enumerate(rows): r["id"] = f"q{i:03d}"
with open("data/all.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")
print("\nwrote", len(rows), "ledger $%.4f" % fw.ledger_total())
