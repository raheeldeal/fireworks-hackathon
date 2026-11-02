"""Verify the Langfuse code path in tracing.py without a Langfuse account.

Builds a real Langfuse client but hands it a TracerProvider whose exporter is in memory,
so spans never leave the process. Then runs the same span calls the harness wrappers make
and asserts the tree, the usage/cost fields and the trace-level tags all arrive.

Run:  PYTHONPATH=trace/.pylib ../.venv/bin/python verify_langfuse_path.py
"""
import json, os, sys

TRACE_DIR = "/Users/raheelahmed/fireworks-hackathon/hackathon/cypher/trace"
sys.path.insert(0, os.path.join(TRACE_DIR, ".pylib"))
sys.path.insert(0, TRACE_DIR)

os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-offline-verify"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-offline-verify"
os.environ["LANGFUSE_HOST"] = "http://127.0.0.1:1"
os.environ["LANGFUSE_PROJECT_ID"] = "proj-offline"
os.environ["CYPHER_TRACE_LOCAL"] = "1"

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langfuse import Langfuse

import tracing as T

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
T._client = Langfuse(public_key="pk-lf-offline-verify", secret_key="sk-lf-offline-verify",
                     host="http://127.0.0.1:1", tracer_provider=provider)
assert T.ACTIVE and T.LANGFUSE_ON

T.install_thread_propagation()

# --- exercise the exact shapes instrument.py produces, including the thread fan-out
from concurrent.futures import ThreadPoolExecutor


def attempt(i):
    with T.span("attempt", kind="chain", model="m/small", temperature=0.7) as sp:
        with T.span("generate", kind="generation", model="m/small",
                    model_parameters={"temperature": 0.7, "max_tokens": 4096}) as g:
            g.update(input=[{"role": "user", "content": "q"}], output="MATCH (n) RETURN n",
                     model="m/small", usage={"input": 100 + i, "output": 20},
                     cost=0.000123, metadata={"finish_reason": "stop"},
                     model_parameters={"temperature": 0.7, "max_tokens": 4096},
                     prompt_name="cypher-generate", prompt_version="abc123def456")
        with T.span("validate", kind="evaluator") as v:
            v.update(input={"cypher": "MATCH (n) RETURN n"}, output={"problems": [], "n_problems": 0})
        with T.span("execute", kind="retriever", graph="movies") as e:
            e.update(input={"graph": "movies", "cypher": "MATCH (n) RETURN n"},
                     output={"status": "rows", "row_count": 3}, latency_s=1.2)
        sp.update(output={"cypher": "MATCH (n) RETURN n", "status": "rows"},
                  usage={"input": 100 + i, "output": 20}, cost=0.000123)
    return i


with T.trace("text2cypher", tags=["movies", "hard", "route_big"],
             graph="movies", tier="hard", config="route_big", row_id="t000") as root:
    root.update(input={"question": "who?"}, session_id="verify_session")
    with T.span("route", kind="agent") as r:
        with T.span("vote", kind="agent") as v:
            with ThreadPoolExecutor(3) as pool:
                list(pool.map(attempt, range(3)))
            v.update(output={"agreement": 3, "chosen": 0})
        r.update(output={"escalated": False})
    root.update(output={"rows": [{"a": 1}], "correct": True}, cost=0.00037,
                usage={"input": 303, "output": 60})
    root.score("correct", 1)
    root.score("latency_s", 2.1)
    tid = root.trace_id
    url = root.url

spans = exporter.get_finished_spans()
by_id = {s.context.span_id: s for s in spans}
names = sorted(s.name for s in spans)


def parent_name(s):
    p = s.parent
    return by_id[p.span_id].name if (p and p.span_id in by_id) else None


print("trace_id:", tid)
print("url:", url)
print("span count:", len(spans))
print("names:", names)
print()
for s in spans:
    print(f"  {s.name:<12} parent={parent_name(s)}")
print()
gen = next(s for s in spans if s.name == "generate")
attrs = dict(gen.attributes)
print("generate attributes:")
for k, v in sorted(attrs.items()):
    print(f"  {k} = {str(v)[:160]}")
root_span = next(s for s in spans if s.name == "text2cypher")
print("\nroot (trace-level) attributes:")
for k, v in sorted(dict(root_span.attributes).items()):
    print(f"  {k} = {str(v)[:220]}")

# --- assertions
assert len(spans) == 15, len(spans)
assert names.count("attempt") == 3 and names.count("generate") == 3
assert parent_name(next(s for s in spans if s.name == "vote")) == "route"
assert all(parent_name(s) == "vote" for s in spans if s.name == "attempt")
assert all(parent_name(s) == "attempt" for s in spans if s.name == "generate")
assert len({s.context.trace_id for s in spans}) == 1, "fan-out split the trace"
assert any("usage_details" in k for k in attrs), "token usage missing"
assert any("cost_details" in k for k in attrs), "cost missing"
assert attrs.get("langfuse.observation.type") == "generation"
rattrs = dict(root_span.attributes)
assert "movies" in str(rattrs.get("langfuse.trace.tags")), rattrs.get("langfuse.trace.tags")
assert "correct" in str(rattrs.get("langfuse.trace.output"))
assert rattrs.get("session.id") == "verify_session"
assert url and "/traces/" in url, url

# --- observation types: each step typed as what it is, not a generic span
types = {s.name: dict(s.attributes).get("langfuse.observation.type") for s in spans}
assert types["generate"] == "generation", types
assert types["attempt"] == "chain", types
assert types["validate"] == "evaluator", types
assert types["execute"] == "retriever", types
assert types["route"] == "agent" and types["vote"] == "agent", types
print("\nobservation types:", json.dumps(types, sort_keys=True))

# --- model parameters and prompt identity on the generation
assert any("model_parameters" in k for k in attrs), "model_parameters missing"
assert "cypher-generate" in str(attrs), "prompt_name missing"

# --- identity: user, release/version, environment
assert rattrs.get("user.id") == T.USER_ID, rattrs.get("user.id")
assert str(rattrs.get("langfuse.version")) == T.RELEASE, rattrs.get("langfuse.version")
assert T.TEST_SET_SHA, "test set hash did not load from data/TEST_HASH"
print("release:", T.RELEASE, " environment:", T.ENVIRONMENT, " user:", T.USER_ID)

# --- masking: nothing credential-shaped can reach Langfuse even if it reached a span.
# These are synthetic strings of the right SHAPE only. No real credential belongs in
# this repo, which is shared; the live keys are exported inline at run time.
shapes = {
    "fireworks": "fw_" + "0" * 24,
    "langfuse_secret": "sk-lf-" + "0000aaaa-1111-2222-3333-444455556666",
    "langfuse_public": "pk-lf-" + "0000aaaa-1111-2222-3333-444455556666",
    "bearer_header": "Bearer " + "x" * 20,
    "generic_sk": "sk-" + "y" * 24,
}
for label, s in shapes.items():
    masked = T.mask(data={"messages": [{"role": "system", "content": f"key={s}"}]})
    assert s not in json.dumps(masked), f"{label} survived masking: {masked}"
    assert T.REDACTED in json.dumps(masked), f"{label} not redacted: {masked}"
assert T.mask(data={"cypher": "MATCH (n) RETURN n"}) == {"cypher": "MATCH (n) RETURN n"}, \
    "masking altered an ordinary Cypher payload"
print("masking:", len(shapes), "credential shapes redacted; ordinary payloads untouched")

# --- no credential-shaped string appeared in any exported span
blob = json.dumps([{k: str(v) for k, v in dict(s.attributes).items()} for s in spans])
for pat in ("fw_", "sk-lf-", "pk-lf-", "FIREWORKS_API_KEY", "Bearer "):
    assert pat not in blob, f"{pat!r} found in exported spans"
print("span audit: no credential-shaped string in any of the", len(spans), "exported spans")

print("\nALL ASSERTIONS PASSED")
print("local tree steps:", json.dumps(T.last_tree(), default=str)[:120], "...")
