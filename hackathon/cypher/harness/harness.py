"""Text-to-Cypher harness: composable pieces around a small model.

validate(query, schema)            -> list of problem strings ([] = looks fine)
generate_and_repair(ex, cfg)       -> one attempt record (generate, validate, execute, repair once)
vote3(ex, cfg)                     -> three attempts at temperature 0.7, majority by result set
route(ex, cfg)                     -> vote3; if no two agree, ask the big model (generate_and_repair)
schema_prune(question, schema)     -> smaller schema text with only the parts the question mentions
retrieve_examples(ex, train, k)    -> k solved training rows from the same graph by word overlap

Every model call goes through call_model(), which charges a shared Budget (ledger + $ cap).
"""
import json, os, re, sys, threading, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CYPHER_DIR = os.path.dirname(HERE)
sys.path.insert(0, CYPHER_DIR)
from executor import execute, normalize_cypher  # noqa: E402
from score import score, clean_pred  # noqa: E402

SMALL = "accounts/fireworks/models/glm-5p3-flash"
BIG = "accounts/fireworks/models/glm-5p3"
KIMI = "accounts/fireworks/models/kimi-k3"
PRICING = {SMALL: (0.15, 0.50), BIG: (1.40, 4.40), KIMI: (3.00, 15.00)}
SYSTEM = open(os.path.join(CYPHER_DIR, "prompts", "v1_plain.txt")).read()


# ---------------------------------------------------------------- budget / API
class BudgetExceeded(Exception):
    pass


class Budget:
    """Thread-safe running spend. Refuses new calls once prior ledger + this run reaches the cap."""

    def __init__(self, start_total, cap):
        self.start, self.cap, self.lock = start_total, cap, threading.Lock()
        self.by_model = {}  # model -> [in, out, cost]

    def spent(self):
        return sum(v[2] for v in self.by_model.values())

    def check(self):
        with self.lock:
            if self.start + self.spent() >= self.cap:
                raise BudgetExceeded(f"cap ${self.cap} reached")

    def charge(self, model, tin, tout):
        pin, pout = PRICING[model]
        c = (tin * pin + tout * pout) / 1e6
        with self.lock:
            v = self.by_model.setdefault(model, [0, 0, 0.0])
            v[0] += tin; v[1] += tout; v[2] += c
        return c


def call_model(model, messages, budget, temperature=0.0, max_tokens=4096, reasoning="low"):
    budget.check()
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
    if reasoning:
        body["reasoning_effort"] = reasoning
    data = json.dumps(body).encode()
    t0 = time.time()
    for attempt in range(6):
        req = urllib.request.Request("https://api.fireworks.ai/inference/v1/chat/completions", data=data,
                                     headers={"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.load(resp)
            u = out.get("usage", {})
            tin, tout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            budget.charge(model, tin, tout)
            return {"raw": out["choices"][0]["message"].get("content") or "", "in": tin, "out": tout,
                    "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
                    "finish": out["choices"][0].get("finish_reason"), "api_error": None,
                    "latency": time.time() - t0}
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt); continue
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:200]
            if attempt < 5:
                time.sleep(2 ** attempt); continue
        return {"raw": "", "in": 0, "out": 0, "reasoning": 0, "finish": None, "api_error": err,
                "latency": time.time() - t0}


# ---------------------------------------------------------------- schema parsing
def parse_schema(schema):
    """Parse the text2cypher schema text into labels{name:set(props)}, rels{type:set(props)}, edges[(a,t,b)]."""
    labels, rels, edges = {}, {}, []
    section, cur = None, None
    for line in schema.splitlines():
        s = line.strip()
        if s.startswith("Node properties"):
            section = "node"; continue
        if s.startswith("Relationship properties"):
            section = "rel"; continue
        if s.startswith("The relationships"):
            section = "edges"; continue
        if section in ("node", "rel"):
            m = re.match(r"^(\w+)\s*\{(.*)\}$", s)  # compact format: Label {prop: TYPE, ...}
            if m:
                (labels if section == "node" else rels).setdefault(m.group(1), set()).update(
                    x.split(":")[0].strip() for x in m.group(2).split(",") if ":" in x)
                cur = None
                continue
            m = re.match(r"-\s*\*\*(.+?)\*\*", s)
            if m:
                cur = m.group(1)
                (labels if section == "node" else rels).setdefault(cur, set())
                continue
            m = re.match(r"-\s*`([^`:]+)", s)
            if m and cur:
                (labels if section == "node" else rels)[cur].add(m.group(1).strip())
        elif section == "edges":
            m = re.match(r"\(:(.+?)\)-\[:(.+?)\]->\(:(.+?)\)", s)
            if m:
                a, t, b = m.groups()
                edges.append((a, t, b))
                labels.setdefault(a, set()); labels.setdefault(b, set()); rels.setdefault(t, set())
    return {"labels": labels, "rels": rels, "edges": edges}


# ---------------------------------------------------------------- 1. validate
WRITE_RE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH)\b", re.I)
CALL_ADMIN_RE = re.compile(r"\bCALL\s+(dbms|db\.(create|drop|index)|apoc\.(create|merge|refactor|periodic|load|export|cypher\.run(?!$)))", re.I)


def _strip_strings(q):
    q = re.sub(r"//[^\n]*", " ", q)
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "''", q)


def _names(s):
    return [x.strip().strip("`") for x in re.split(r"[|:&!]", s) if x.strip().strip("`")]


def validate(query, schema):
    """Return a list of human-readable problems. Empty list = single read-only statement using only
    labels / relationship types / properties that exist in the schema."""
    if not query or not query.strip():
        return ["No Cypher query was returned."]
    q = _strip_strings(normalize_cypher(query))
    problems = []
    if ";" in q.strip().rstrip(";"):
        problems.append("More than one statement; return a single Cypher statement.")
    w = WRITE_RE.search(q)
    if w:
        problems.append(f"Write clause `{w.group(1).upper()}` is not allowed; the query must be read-only.")
    if CALL_ADMIN_RE.search(q):
        problems.append("Administrative or writing procedure calls are not allowed.")
    sch = parse_schema(schema)
    labels, rels = sch["labels"], sch["rels"]
    if not labels:
        return problems
    var_labels, var_rels = {}, {}
    # node patterns: (v:Label:Other {props})
    for m in re.finditer(r"\(\s*(`?\w+`?)?\s*:\s*((?:`[^`]+`|\w+)(?:\s*[:|&]\s*!?(?:`[^`]+`|\w+))*)\s*(\{[^}]*\})?", q):
        var, ls, inline = m.group(1), _names(m.group(2)), m.group(3)
        for l in ls:
            if l not in labels:
                problems.append(f"Node label `{l}` does not exist in the schema. Labels: {', '.join(sorted(labels))}.")
        if var:
            var_labels.setdefault(var.strip("`"), set()).update(l for l in ls if l in labels)
        if inline:
            for p in re.findall(r"(\w+)\s*:", inline):
                ok = [l for l in ls if l in labels]
                if ok and not any(p in labels[l] for l in ok):
                    problems.append(f"Property `{p}` does not exist on {'/'.join(ok)}. It has: {', '.join(sorted(set().union(*[labels[l] for l in ok])))}.")
    # label predicates in WHERE: v:Label
    for m in re.finditer(r"\bWHERE\b[^\n]*?\b(\w+):(\w+)\b", q, re.I):
        pass  # rare; skipped to avoid false positives with map literals
    # relationship patterns: [r:TYPE|OTHER*1..3 {props}]
    for m in re.finditer(r"\[\s*(`?\w+`?)?\s*:\s*((?:`[^`]+`|\w+)(?:\s*[|:]\s*:?\s*(?:`[^`]+`|\w+))*)\s*(\*[\d.\s]*)?\s*(\{[^}]*\})?", q):
        var, ts, inline = m.group(1), _names(m.group(2)), m.group(4)
        for t in ts:
            if t not in rels:
                problems.append(f"Relationship type `{t}` does not exist in the schema. Types: {', '.join(sorted(rels))}.")
        if var:
            var_rels.setdefault(var.strip("`"), set()).update(t for t in ts if t in rels)
        if inline:
            for p in re.findall(r"(\w+)\s*:", inline):
                ok = [t for t in ts if t in rels]
                if ok and not any(p in rels[t] for t in ok):
                    problems.append(f"Property `{p}` does not exist on relationship {'/'.join(ok)}.")
    # property access v.prop for variables bound to a known label / type
    for m in re.finditer(r"(?<![\w.])(`?\w+`?)\.(`?\w+`?)(?!\s*\()", q):
        var, p = m.group(1).strip("`"), m.group(2).strip("`")
        if var in var_labels and var_labels[var]:
            ls = var_labels[var]
            if not any(p in labels[l] for l in ls):
                have = sorted(set().union(*[labels[l] for l in ls]))
                problems.append(f"Property `{p}` does not exist on node `{var}` ({'/'.join(sorted(ls))}). It has: {', '.join(have)}.")
        elif var in var_rels and var_rels[var]:
            ts = var_rels[var]
            if not any(p in rels[t] for t in ts):
                have = sorted(set().union(*[rels[t] for t in ts]))
                problems.append(f"Property `{p}` does not exist on relationship `{var}` ({'/'.join(sorted(ts))}). It has: {', '.join(have) or 'no properties'}.")
    # direction check for simple (a:A)-[:T]->(b:B) patterns
    edge_set = set(sch["edges"])
    if edge_set:
        pat = r"\(\s*\w*\s*:\s*(\w+)[^()]*\)\s*(<?)-\s*\[\s*\w*\s*:\s*(\w+)\s*\]\s*-(>?)\s*\(\s*\w*\s*:\s*(\w+)"
        for m in re.finditer(pat, q):
            a, left, t, right, b = m.groups()
            if a in labels and b in labels and t in rels:
                src, dst = (b, a) if left else (a, b)
                if (left or right) and (src, t, dst) not in edge_set and (dst, t, src) in edge_set:
                    problems.append(f"Direction: the schema has (:{dst})-[:{t}]->(:{src}), not (:{src})-[:{t}]->(:{dst}).")
    return list(dict.fromkeys(problems))


def is_unsafe(problems):
    return any(("not allowed" in p) or ("More than one statement" in p) for p in problems)


# ---------------------------------------------------------------- 5. schema pruning
STOP = set("a an the of in on to for by with and or is are was were be been what which who whom whose how many much "
           "list show find give return get all any each every that this these those from their its it as at do does "
           "did have has had top most more less than not no there per me my i you your".split())


def _stem(w):
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    for suf in ("ing", "ed", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w[:-1] if len(w) > 3 and w.endswith("e") else w


def _split_ident(name):
    parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").split()
    return {_stem(p) for p in parts if len(p) > 1}


def schema_prune(question, schema):
    """Keep labels / rel types / properties whose name stems appear in the question, plus every label
    at either end of a kept relationship. Fall back to the full schema when fewer than 2 labels survive."""
    sch = parse_schema(schema)
    qstems = {_stem(w) for w in re.findall(r"[A-Za-z]+", question) if w.lower() not in STOP}
    qstems |= {s[:5] for s in qstems if len(s) >= 6}

    def hit(name):
        ps = _split_ident(name)
        return bool(ps & qstems) or any(len(p) >= 6 and p[:5] in qstems for p in ps)

    keep_l = {l for l in sch["labels"] if hit(l)}
    keep_r = {t for t in sch["rels"] if hit(t)}
    for l, ps in sch["labels"].items():
        if any(hit(p) for p in ps if p.lower() not in ("name", "id")):
            keep_l.add(l)
    for a, t, b in sch["edges"]:
        if t in keep_r:
            keep_l |= {a, b}
    # relationships connecting two kept labels are kept too
    for a, t, b in sch["edges"]:
        if a in keep_l and b in keep_l:
            keep_r.add(t)
    if len(keep_l) < 2:
        return schema, False
    out, section, cur_keep = [], None, True
    for line in schema.splitlines():
        s = line.strip()
        if s.startswith(("Node properties", "Relationship properties", "The relationships")):
            section = s; cur_keep = True; out.append(line); continue
        m = re.match(r"^(\w+)\s*\{.*\}$", s) if section and not section.startswith("The") else None
        if m:
            if m.group(1) in (keep_l if section.startswith("Node") else keep_r):
                out.append(line)
            continue
        m = re.match(r"-\s*\*\*(.+?)\*\*", s)
        if m:
            name = m.group(1)
            cur_keep = name in (keep_l if section.startswith("Node") else keep_r)
            if cur_keep:
                out.append(line)
            continue
        if section and section.startswith("The relationships"):
            m = re.match(r"\(:(.+?)\)-\[:(.+?)\]->\(:(.+?)\)", s)
            if m and (m.group(2) in keep_r):
                out.append(line)
            continue
        if cur_keep:
            out.append(line)
    return "\n".join(out), True


# ---------------------------------------------------------------- few-shot retrieval
def _words(t):
    return {_stem(w) for w in re.findall(r"[A-Za-z]+", t) if w.lower() not in STOP}


def retrieve_examples(ex, train, k=2):
    qw = _words(ex["question"])
    cands = [t for t in train if t["graph"] == ex["graph"]]
    cands.sort(key=lambda t: -len(qw & _words(t["question"])) / (len(qw | _words(t["question"])) or 1))
    return cands[:k]


# ---------------------------------------------------------------- 2. generate + repair
def _exec(graph, cypher, problems):
    if not cypher:
        return {"ok": False, "rows": [], "columns": [], "error": "no query", "secs": 0}
    if is_unsafe(problems):
        return {"ok": False, "rows": [], "columns": [], "error": "rejected by validator: " + problems[0], "secs": 0}
    return execute(graph, cypher)


def _status(res):
    if not res["ok"]:
        return "error"
    return "empty" if not res["rows"] else "rows"


def generate_and_repair(ex, cfg, budget, temperature=0.0, model=None, train=None):
    """One attempt: generate, validate, execute; if error / empty / validation problems, send the problem
    text back once (optionally with 2 retrieved solved examples), then re-execute.
    cfg keys: repair (bool), fewshot (bool), prune (bool), reasoning (str|None)."""
    model = model or cfg.get("model", SMALL)
    reasoning = cfg.get("reasoning", "low") if model == SMALL else cfg.get("big_reasoning", None)
    schema = ex["schema"]
    pruned = False
    if cfg.get("prune"):
        schema, pruned = schema_prune(ex["question"], ex["schema"])
    msgs = [{"role": "system", "content": SYSTEM.replace("{schema}", schema)},
            {"role": "user", "content": ex["question"]}]
    calls = []
    r = call_model(model, msgs, budget, temperature, reasoning=reasoning)
    calls.append(r)
    q1 = clean_pred(r["raw"])
    p1 = validate(q1, ex["schema"])
    res1 = _exec(ex["graph"], q1, p1)
    rec = {"model": model, "cypher": q1, "problems": p1, "result": res1, "statuses": [_status(res1)],
           "repaired": False, "pruned": pruned, "first_in_tokens": r["in"]}
    need = cfg.get("repair") and (bool(p1) or _status(res1) != "rows")
    if need:
        issue = []
        if not res1["ok"]:
            issue.append(f"Running it failed with: {res1['error']}")
        elif not res1["rows"]:
            issue.append("It ran but returned no rows. The answer is expected to be non-empty; check labels, "
                         "relationship directions, property names and literal values against the schema.")
        issue += [f"Schema check: {p}" for p in p1]
        text = "Your query:\n" + q1 + "\n\nProblems:\n- " + "\n- ".join(issue)
        if cfg.get("fewshot") and train is not None:
            shots = retrieve_examples(ex, train, 2)
            text += "\n\nSolved examples on this graph:\n" + "\n\n".join(
                f"Question: {s['question']}\nCypher: {normalize_cypher(s['cypher'])}" for s in shots)
        text += "\n\nWrite a corrected query for the original question. Return only the Cypher query."
        # repair always sees the full schema so it can recover anything pruning dropped
        msgs2 = [{"role": "system", "content": SYSTEM.replace("{schema}", ex["schema"])},
                 {"role": "user", "content": ex["question"]},
                 {"role": "assistant", "content": q1 or "(no query)"},
                 {"role": "user", "content": text}]
        r2 = call_model(model, msgs2, budget, temperature, reasoning=reasoning)
        calls.append(r2)
        q2 = clean_pred(r2["raw"])
        p2 = validate(q2, ex["schema"])
        res2 = _exec(ex["graph"], q2, p2)
        rec["statuses"].append(_status(res2))
        # take the repair unless it made things worse (rows > empty > error)
        rank = {"rows": 2, "empty": 1, "error": 0}
        if rank[_status(res2)] >= rank[_status(res1)]:
            rec.update(cypher=q2, problems=p2, result=res2)
        rec["repaired"] = True
    rec["calls"] = len(calls)
    rec["in"] = sum(c["in"] for c in calls); rec["out"] = sum(c["out"] for c in calls)
    rec["latency"] = sum(c["latency"] for c in calls)
    rec["exec_secs"] = res1.get("secs", 0) + (rec["result"].get("secs", 0) if rec["repaired"] else 0)
    rec["api_error"] = next((c["api_error"] for c in calls if c["api_error"]), None)
    rec["truncated"] = any(c["finish"] == "length" for c in calls)
    return rec


# ---------------------------------------------------------------- 3. vote
def same_result(a, b):
    """Two executed results agree when both ran, both have rows, and the row multisets match
    (score.py logic, column names and order ignored)."""
    if not (a["ok"] and b["ok"] and a["rows"] and b["rows"]):
        return False
    return score(a, b, "") == "correct"


def vote3(ex, cfg, budget, train=None):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as pool:  # the three attempts run in parallel, so latency ~ one attempt
        atts = list(pool.map(lambda _: generate_and_repair(ex, cfg, budget, temperature=0.7, train=train), range(3)))
    best, agree = None, 1
    for i in range(3):
        group = [j for j in range(3) if same_result(atts[i]["result"], atts[j]["result"])]
        if len(group) > agree or (best is None and len(group) >= 2):
            best, agree = i, len(group)
    if best is None or agree < 2:
        agree = 1
        best = next((i for i, a in enumerate(atts) if a["result"]["ok"] and a["result"]["rows"]),
                    next((i for i, a in enumerate(atts) if a["result"]["ok"]), 0))
    return {"attempts": atts, "chosen": best, "agreement": agree}


# ---------------------------------------------------------------- 4. route
def route(ex, cfg, budget, train=None):
    v = vote3(ex, cfg, budget, train)
    v["escalated"] = False
    if v["agreement"] < cfg.get("escalate_below", 2):  # 2 = only when no two agree; 3 = unless unanimous
        big = generate_and_repair(ex, cfg, budget, temperature=0.0, model=cfg.get("big_model", BIG), train=train)
        v["attempts"].append(big)
        v["chosen"] = len(v["attempts"]) - 1
        v["escalated"] = True
    return v
