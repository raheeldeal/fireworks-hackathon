#!/usr/bin/env python3
"""Generate 400 more gold-first training rows (4 per tool) with glm-5p3, same recipe as submission/data/train.jsonl
(runs/mcp-tool-pick/gen_data.py), with the confusable pairs seen in the SFT misses added as explicit neighbors.
Labels are the sampled tool, never model-chosen. Writes data/train_extra.jsonl; run check_leak.py on it afterwards.
Cost is logged to train/ledger.csv (glm-5p3: $1.40/M in, $4.40/M out)."""
import json, os, random, re, sys, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.dirname(HERE)
sys.path.insert(0, SUB)
import fw  # noqa: E402
fw.LEDGER = os.path.join(HERE, "ledger.csv")

cat = json.load(open(os.path.join(SUB, "data", "catalog.json")))
by_name = {t["name"]: t for t in cat}
by_server = {}
for t in cat:
    by_server.setdefault(t["server"], []).append(t)

# Pairs the SFT model confused on the locked set (results/sft_nocatalog.json) or could not produce in RFT sampling.
CONFUSABLE = {
    "jira.move_to_sprint": ["jira.update_ticket", "jira.transition_ticket"],
    "github.update_issue": ["github.create_issue", "jira.update_ticket"],
    "drive.upload_file": ["fs.move_file", "drive.move_file"],
    "github.create_pull_request": ["github.merge_pull_request"],
    "db.run_query": ["db.execute_statement", "db.explain_query", "db.describe_table"],
    "pagerduty.acknowledge_incident": ["jira.transition_ticket"],
    "calendar.find_free_time": ["calendar.create_event", "calendar.list_events"],
    "calendar.update_event": ["calendar.respond_to_invite", "calendar.create_event"],
    "zoom.list_meetings": ["calendar.list_events"],
    "github.create_issue": ["jira.create_ticket"],
    "stripe.create_customer": ["notion.add_database_row"],
    "fs.move_file": ["drive.move_file", "drive.upload_file"],
    "browser.type_text": ["browser.fill_form"],
    "gmail.archive_email": ["gmail.trash_email"],
    "calendar.respond_to_invite": ["calendar.update_event"],
    "db.create_backup": ["db.execute_statement"],
    "fs.search_files": ["drive.search_files", "github.search_code"],
    "slack.search_messages": ["gmail.search_emails"],
    "notion.search": ["notion.query_database", "drive.search_files"],
    "notion.query_database": ["notion.search", "db.run_query"],
}
STYLES = [
    "terse, like a chat message to a bot (under 15 words)",
    "conversational and a bit rambling, with context about why",
    "written by a non-native English speaker, with one or two small grammar slips",
    "phrased indirectly so the tool is implied, never naming the product or the action verb from the catalog",
    "a message to a colleague that an assistant intercepted, including a name and a specific detail (date, file, id)",
]
SYS = "You write realistic user requests for testing an AI assistant's tool routing. Output strictly valid JSON."


def prompt(tool, styles):
    sib = [t for t in by_server[tool["server"]] if t["name"] != tool["name"]]
    conf = [by_name[n] for n in CONFUSABLE.get(tool["name"], []) if n in by_name]
    others = random.sample([t for t in cat if t["server"] != tool["server"] and t not in conf], 4)
    seen, neigh = set(), []
    for t in conf + sib + others:
        if t["name"] not in seen:
            seen.add(t["name"]); neigh.append(f"- {t['name']}: {t['description']}")
    st = "\n".join(f"{i+1}. {s}" for i, s in enumerate(styles))
    return f"""TARGET TOOL (the request must need exactly this tool):
- {tool['name']}: {tool['description']}

NEIGHBOR TOOLS (the request must clearly NOT be solvable by any of these; a careful reader should be able to rule each out, especially the first ones, which are easy to confuse with the target):
{chr(10).join(neigh)}

Write {len(styles)} different user requests, one in each style below. Each must be a single message a real person would type to an assistant, must require the TARGET tool and none of the neighbors, and must not mention the tool name or the server name literally (saying "GitHub" is fine, saying "create_issue" is not). Vary the domain details (companies, names, dates, filenames) across them.
Styles:
{st}

Return JSON: {{"requests": [{", ".join(['"..."'] * len(styles))}]}}"""


def gen(args):
    tool, styles, style_ids = args
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": prompt(tool, styles)}]
    for attempt in range(3):
        try:
            r = fw.chat("glm-5p3", msgs, max_tokens=1500, extra={"reasoning_effort": "low", "response_format": {"type": "json_object"}},
                        note="gen_more", temperature=0.9)
        except Exception as e:
            print("call fail", tool["name"], str(e)[:80], file=sys.stderr); continue
        txt = re.sub(r"^```(json)?|```$", "", (r["content"] or "").strip()).strip()
        try:
            reqs = json.loads(txt)["requests"]
            if isinstance(reqs, list) and len(reqs) == len(styles) and all(isinstance(x, str) and len(x) > 8 for x in reqs):
                return [{"text": x.strip(), "label": tool["name"], "style": s} for x, s in zip(reqs, style_ids)]
        except Exception as e:
            print("parse fail", tool["name"], str(e)[:80], file=sys.stderr)
    return []


def main():
    random.seed(23)  # different seed from last night's generation (11)
    jobs = []
    for i, t in enumerate(cat):
        drop = i % 5  # rotate which style is left out so all five styles appear across the set
        ids = [s for s in range(5) if s != drop]
        jobs.append((t, [STYLES[s] for s in ids], ids))
    rows = []
    with cf.ThreadPoolExecutor(6) as ex:
        for out in ex.map(gen, jobs):
            rows.extend(out); print(len(rows), end=" ", flush=True)
    rows.sort(key=lambda r: (r["label"], r["style"]))
    for i, r in enumerate(rows):
        r["id"] = f"x{i:03d}"
    out = os.path.join(HERE, "data", "train_extra.jsonl")
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(rows)} rows to {out}; ledger ${fw.ledger_total():.4f}")


if __name__ == "__main__":
    main()
