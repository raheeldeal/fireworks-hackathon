"""Langfuse tracing for harness runs. One Langfuse trace per question; one observation per model call or query.

Local result files stay the source of truth; Langfuse is a browsable mirror. If the LANGFUSE_* keys are missing
(or --no-trace is passed) every method is a no-op, so runs never depend on Langfuse being up.
Checked against the installed SDK, langfuse 5.1.0.
"""
import contextlib, os


class _NoSpan:
    trace_id = None

    def update(self, **kw):
        pass

    def score_trace(self, **kw):
        pass


class Tracer:
    def __init__(self, enabled=True):
        self.lf = None
        if enabled and os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
            from langfuse import Langfuse
            self.lf = Langfuse(public_key=os.environ["LANGFUSE_PUBLIC_KEY"], secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                               base_url=os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST"))

    @contextlib.contextmanager
    def question(self, row, tag, split, config):
        """Root span for one question. Tags let Langfuse filter by run and keep test and train traces apart."""
        if not self.lf:
            yield _NoSpan()
            return
        from langfuse import propagate_attributes
        with propagate_attributes(trace_name=f"{tag}:{row['id']}", session_id=tag,
                                  tags=[tag, f"split={split}", f"graph={row['graph']}"],
                                  metadata={"tier": row.get("complexity", {}).get("tier", "")}):
            with self.lf.start_as_current_observation(name="question", as_type="chain",
                                                       input={"question": row["question"], "graph": row["graph"]},
                                                       metadata={"config": config}) as root:
                yield root

    @contextlib.contextmanager
    def step(self, name, as_type="span", **kw):
        """Child observation: as_type='generation' for model calls, 'tool' for database queries."""
        if not self.lf:
            yield _NoSpan()
            return
        with self.lf.start_as_current_observation(name=name, as_type=as_type, **kw) as obs:
            yield obs

    def url(self, trace_id):
        return self.lf.get_trace_url(trace_id=trace_id) if self.lf and trace_id else None

    def flush(self):
        if self.lf:
            self.lf.flush()
