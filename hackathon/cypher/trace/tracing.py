"""Opt-in tracing for the text-to-Cypher harness. No-op unless an env var turns it on.

    from tracing import trace, span

    with trace("text2cypher", tags=["movies", "hard", "route_big"]) as root:
        with span("generate", kind="generation", model=M, input=msgs) as sp:
            sp.update(output=text, usage={"input": 120, "output": 40}, cost=0.0003)
        root.update(output={"rows": rows, "correct": True})

Two independent switches, both off by default:

  LANGFUSE_PUBLIC_KEY (+ LANGFUSE_SECRET_KEY)  send spans to Langfuse
  CYPHER_TRACE_LOCAL=1                         build the same span tree in memory and
                                               dump it to trace/last_trace.json

With neither set, `trace()` and `span()` return a handle whose methods do nothing: no
imports, no network, no allocation beyond one object per span. Scored eval runs that never
set these variables behave exactly as before.

Thread fan-out: call install_thread_propagation() once and the span stack (and the
OpenTelemetry context Langfuse nests on) is carried into ThreadPoolExecutor workers, so
the harness's three parallel vote attempts nest under the vote span instead of
detaching into three orphan trees.
"""
import atexit, json, os, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_DUMP_PATH = os.path.join(HERE, "last_trace.json")
MAX_LOCAL_STR = 4000  # local JSON only; Langfuse gets the untruncated value

LANGFUSE_ON = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
LOCAL_ON = os.environ.get("CYPHER_TRACE_LOCAL", "").lower() in ("1", "true", "yes", "on")
ACTIVE = LANGFUSE_ON or LOCAL_ON

_tls = threading.local()
_client = None
_client_err = None
_client_lock = threading.Lock()
_roots = []  # local trees closed so far, newest last


# ---------------------------------------------------------------- langfuse client
def client():
    """The Langfuse client, or None when keys are absent or the SDK will not load."""
    global _client, _client_err
    if not LANGFUSE_ON:
        return None
    with _client_lock:
        if _client is None and _client_err is None:
            try:
                from langfuse import Langfuse
                _client = Langfuse(
                    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                    secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
                    host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
                    flush_at=20, flush_interval=2.0,
                )
            except Exception as e:  # noqa: BLE001  keys wrong, SDK missing, no network
                _client_err = repr(e)[:300]
                print(f"[tracing] Langfuse disabled: {_client_err}")
        return _client


def flush():
    """Push everything buffered to Langfuse. Safe to call when tracing is off."""
    c = _client
    if c is not None:
        try:
            c.flush()
        except Exception as e:  # noqa: BLE001
            print(f"[tracing] flush failed: {e!r}")


atexit.register(flush)


# ---------------------------------------------------------------- local span tree
def _cap(v, depth=0):
    """Shrink a value for the local JSON dump: long strings clipped, deep structures summarised."""
    if isinstance(v, str):
        return v if len(v) <= MAX_LOCAL_STR else v[:MAX_LOCAL_STR] + f"... [+{len(v) - MAX_LOCAL_STR} chars]"
    if isinstance(v, dict):
        return {k: _cap(x, depth + 1) for k, x in v.items()} if depth < 6 else "..."
    if isinstance(v, (list, tuple)):
        head = [_cap(x, depth + 1) for x in list(v)[:20]]
        return head + [f"... [+{len(v) - 20} more]"] if len(v) > 20 else head
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    return repr(v)[:MAX_LOCAL_STR]


class Node:
    __slots__ = ("name", "kind", "input", "output", "meta", "start", "end", "children", "error")

    def __init__(self, name, kind, meta):
        self.name, self.kind, self.meta = name, kind, dict(meta or {})
        self.input = self.output = self.error = None
        self.start, self.end = time.time(), None
        self.children = []

    def as_dict(self):
        return {
            "step": self.name,
            "kind": self.kind,
            "seconds": round((self.end or time.time()) - self.start, 3),
            "input": _cap(self.input),
            "output": _cap(self.output),
            "meta": _cap(self.meta),
            **({"error": _cap(self.error)} if self.error else {}),
            "children": [c.as_dict() for c in self.children],
        }


# ---------------------------------------------------------------- handles
class _Null:
    """Returned when tracing is off. Every method is a no-op; attribute reads give None."""
    __slots__ = ()
    trace_id = None
    url = None

    def update(self, **_kw):
        return self

    def score(self, *_a, **_kw):
        return self

    def event(self, *_a, **_kw):
        return self


NULL = _Null()


class Handle:
    """One span. `update()` adds input/output/metadata; `score()` attaches a numeric score."""

    def __init__(self, node, lf, is_root):
        self.node, self.lf, self.is_root = node, lf, is_root

    # ---- data
    def update(self, input=None, output=None, metadata=None, usage=None, cost=None,
               model=None, level=None, tags=None, error=None, **extra):
        n = self.node
        if n is not None:
            if input is not None:
                n.input = input
            if output is not None:
                n.output = output
            if metadata:
                n.meta.update(metadata)
            if extra:
                n.meta.update(extra)
            if usage:
                n.meta["usage"] = usage
            if cost is not None:
                n.meta["cost_usd"] = cost
            if model:
                n.meta["model"] = model
            if error:
                n.error = error
        if self.lf is not None:
            kw = {}
            if input is not None:
                kw["input"] = input
            if output is not None:
                kw["output"] = output
            md = dict(metadata or {})
            md.update(extra)
            if md:
                kw["metadata"] = md
            if model:
                kw["model"] = model
            if usage:
                kw["usage_details"] = usage
            if cost is not None:
                kw["cost_details"] = {"total": cost}
            if error:
                kw["level"] = "ERROR"
                kw["status_message"] = str(error)[:500]
            elif level:
                kw["level"] = level
            try:
                if kw:
                    self.lf.update(**kw)
                if tags or (self.is_root and (input is not None or output is not None)):
                    tkw = {}
                    if tags:
                        tkw["tags"] = list(tags)
                    if self.is_root and input is not None:
                        tkw["input"] = input
                    if self.is_root and output is not None:
                        tkw["output"] = output
                    if tkw:
                        self.lf.update_trace(**tkw)
            except Exception as e:  # noqa: BLE001  never let tracing break the run
                print(f"[tracing] update failed on {self.node.name if self.node else '?'}: {e!r}")
        return self

    # ---- scores
    def score(self, name, value, comment=None, data_type="NUMERIC"):
        if self.node is not None:
            self.node.meta.setdefault("scores", {})[name] = value
        c = client()
        if c is not None and self.lf is not None:
            try:
                c.create_score(name=name, value=value, trace_id=self.lf.trace_id,
                               data_type=data_type, comment=comment)
            except Exception as e:  # noqa: BLE001
                print(f"[tracing] score {name} failed: {e!r}")
        return self

    @property
    def trace_id(self):
        return self.lf.trace_id if self.lf is not None else None

    @property
    def url(self):
        """Langfuse URL for this trace, or None when Langfuse is off."""
        c = client()
        if c is None or self.lf is None:
            return None
        try:
            return c.get_trace_url(trace_id=self.lf.trace_id)
        except Exception:  # noqa: BLE001
            return None


# ---------------------------------------------------------------- span / trace
class _Ctx:
    """Context manager produced by span() / trace(). Not reused."""

    def __init__(self, name, kind, is_root, tags, meta):
        self.name, self.kind, self.is_root, self.tags, self.meta = name, kind, is_root, tags, meta
        self.handle = NULL
        self._cm = None

    def __enter__(self):
        if not ACTIVE:
            return NULL
        stack = getattr(_tls, "stack", None)
        if stack is None:
            stack = _tls.stack = []

        node = None
        if LOCAL_ON:
            node = Node(self.name, self.kind, self.meta)
            if stack and stack[-1].node is not None:
                stack[-1].node.children.append(node)

        lf = None
        c = client()
        if c is not None:
            try:
                start = c.start_as_current_generation if self.kind == "generation" else c.start_as_current_span
                kw = {"name": self.name}
                if self.meta:
                    kw["metadata"] = self.meta
                if self.kind == "generation" and self.meta.get("model"):
                    kw["model"] = self.meta["model"]
                self._cm = start(**kw)
                lf = self._cm.__enter__()
                if self.is_root:
                    lf.update_trace(name=self.name, tags=list(self.tags or []),
                                    metadata=self.meta or None)
                elif self.tags:
                    lf.update_trace(tags=list(self.tags))
            except Exception as e:  # noqa: BLE001
                print(f"[tracing] could not open span {self.name}: {e!r}")
                self._cm, lf = None, None

        self.handle = Handle(node, lf, self.is_root)
        stack.append(self.handle)
        return self.handle

    def __exit__(self, exc_type, exc, tb):
        if not ACTIVE:
            return False
        stack = getattr(_tls, "stack", None) or []
        if stack and stack[-1] is self.handle:
            stack.pop()
        node = self.handle.node
        if node is not None:
            node.end = time.time()
            if exc is not None and node.error is None:
                node.error = f"{exc_type.__name__}: {exc}"
        if exc is not None and self.handle.lf is not None:
            try:
                self.handle.lf.update(level="ERROR", status_message=f"{exc_type.__name__}: {exc}"[:500])
            except Exception:  # noqa: BLE001
                pass
        if self._cm is not None:
            try:
                self._cm.__exit__(exc_type, exc, tb)
            except Exception:  # noqa: BLE001
                pass
        if self.is_root:
            if node is not None:
                _roots.append(node)
                dump_local()
            flush()
        return False


def span(name, kind="span", tags=None, **meta):
    """A nested span. kind="generation" marks it as a model call in Langfuse."""
    return _Ctx(name, kind, False, tags, meta)


def trace(name, tags=None, **meta):
    """A root trace. One per question."""
    return _Ctx(name, "span", True, tags, meta)


def current():
    """Innermost open span handle, or NULL."""
    stack = getattr(_tls, "stack", None) or []
    return stack[-1] if stack else NULL


# ---------------------------------------------------------------- local dump
def last_tree():
    return _roots[-1].as_dict() if _roots else None


def all_trees():
    return [r.as_dict() for r in _roots]


def dump_local(path=None):
    """Write the most recent root to trace/last_trace.json. No-op without CYPHER_TRACE_LOCAL."""
    if not LOCAL_ON or not _roots:
        return None
    path = path or LOCAL_DUMP_PATH
    try:
        with open(path, "w") as f:
            json.dump(last_tree(), f, indent=1, default=str)
        return path
    except Exception as e:  # noqa: BLE001
        print(f"[tracing] local dump failed: {e!r}")
        return None


def dump_all(path):
    if not LOCAL_ON:
        return None
    try:
        with open(path, "w") as f:
            json.dump(all_trees(), f, indent=1, default=str)
        return path
    except Exception as e:  # noqa: BLE001
        print(f"[tracing] batch dump failed: {e!r}")
        return None


# ---------------------------------------------------------------- pretty printer
_ORDER_HINT = {"schema_prune": "schema", "generate": "model", "repair": "model",
               "validate": "check", "execute": "query", "vote": "vote", "route": "route"}


def render(tree, indent=0, out=None):
    """Readable step-by-step rendering of a local span tree."""
    out = [] if out is None else out
    if tree is None:
        return "(no local trace; set CYPHER_TRACE_LOCAL=1)"
    pad = "  " * indent
    meta = tree.get("meta") or {}
    bits = [f"{tree['seconds']:.2f}s"]
    u = meta.get("usage") or {}
    if u:
        bits.append(f"tok in={u.get('input', 0)} out={u.get('output', 0)}")
    if meta.get("cost_usd") is not None:
        bits.append(f"${meta['cost_usd']:.5f}")
    if meta.get("model"):
        bits.append(str(meta["model"]).split("/")[-1])
    note = meta.get("note")
    head = f"{pad}{'└─ ' if indent else ''}{tree['step']}  [{'  '.join(bits)}]"
    out.append(head)
    if note:
        out.append(f"{pad}   {note}")
    if tree.get("error"):
        out.append(f"{pad}   ! {tree['error']}")
    for k in ("scores",):
        if meta.get(k):
            out.append(f"{pad}   {k}: {meta[k]}")
    for ch in tree.get("children") or []:
        render(ch, indent + 1, out)
    return "\n".join(out) if indent == 0 else out


# ---------------------------------------------------------------- thread fan-out
_propagation_installed = False


def install_thread_propagation():
    """Carry the span stack and the OTel context into ThreadPoolExecutor workers.

    The harness runs its three vote attempts in a pool. Neither our stack (thread-local)
    nor Langfuse's parent context (a contextvar) crosses that boundary by itself, so
    without this the attempts would appear as separate root traces.
    """
    global _propagation_installed
    if _propagation_installed or not ACTIVE:
        return
    from concurrent.futures import ThreadPoolExecutor
    try:
        from opentelemetry import context as otel_context
    except Exception:  # noqa: BLE001
        otel_context = None

    original = ThreadPoolExecutor.submit

    def submit(self, fn, /, *args, **kwargs):
        stack = list(getattr(_tls, "stack", None) or [])
        ctx = otel_context.get_current() if (otel_context and LANGFUSE_ON) else None

        def runner(*a, **k):
            _tls.stack = list(stack)
            token = otel_context.attach(ctx) if ctx is not None else None
            try:
                return fn(*a, **k)
            finally:
                if token is not None:
                    otel_context.detach(token)
                _tls.stack = []

        return original(self, runner, *args, **kwargs)

    ThreadPoolExecutor.submit = submit
    _propagation_installed = True
