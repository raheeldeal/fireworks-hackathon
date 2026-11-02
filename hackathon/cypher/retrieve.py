"""Find the K solved train questions most similar to a new question, from the same graph.

Retriever           similarity = sum of IDF weights of the words both questions share. Deterministic and free.
EmbeddingRetriever  similarity = cosine of qwen3-embedding-8b vectors (matches meaning: "films" ~ "movies").
Both expose top(question, graph, k, exclude_ids).
"""
import hashlib, json, math, os, re, threading
from collections import Counter, defaultdict

STOP = set("""a an the of in on at to for from by with and or is are was were be been what which who whom whose
how many much list show find give return all each any that this these those their there it its as do does
did have has had me i we you please can could would""".split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


class Retriever:
    def __init__(self, rows):
        """rows: dicts with at least id, graph, question, cypher (the solved examples)."""
        self.by_graph = defaultdict(list)
        for r in rows:
            self.by_graph[r["graph"]].append((r, words(r["question"])))
        df = Counter(w for pool in self.by_graph.values() for _, ws in pool for w in ws)
        n = sum(len(pool) for pool in self.by_graph.values())
        self.idf = {w: math.log((n + 1) / (c + 1)) + 1 for w, c in df.items()}

    def top(self, question, graph, k, exclude_ids=()):
        """The k most similar examples. Rows in exclude_ids, or with the identical question, are skipped,
        so a train question never retrieves itself (which would leak its answer into the prompt)."""
        q = words(question)
        scored = []
        for r, ws in self.by_graph.get(graph, []):
            if r["id"] in exclude_ids or r["question"].strip().lower() == question.strip().lower():
                continue
            scored.append((-sum(self.idf.get(w, 0) for w in q & ws), r["id"], r))
        scored.sort(key=lambda t: (t[0], t[1]))  # best score first; id breaks ties deterministically
        return [r for _, _, r in scored[:k]]


class EmbeddingRetriever:
    """Same interface as Retriever, ranked by embedding cosine similarity.

    Vectors are cached in results/emb_cache.json (keyed by a hash of the text), so each text is embedded once.
    Pass `queries` (the questions you will ask about) to embed them all up front in a few batched calls.
    """
    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "emb_cache.json")

    def __init__(self, rows, queries=()):
        import fw
        self.fw, self.lock = fw, threading.Lock()
        self.cache = json.load(open(self.CACHE)) if os.path.exists(self.CACHE) else {}
        self.by_graph = defaultdict(list)
        for r in rows:
            self.by_graph[r["graph"]].append((r, None))  # (row, unused): same shape as Retriever.by_graph
        self._ensure([r["question"] for r in rows] + list(queries))

    @staticmethod
    def _key(text):
        return hashlib.sha1(text.strip().lower().encode()).hexdigest()

    def _ensure(self, texts):
        with self.lock:
            missing = sorted({t for t in texts if self._key(t) not in self.cache})
            if missing:
                for t, v in zip(missing, self.fw.embed(missing, note="embeddings")):
                    norm = math.sqrt(sum(x * x for x in v)) or 1.0
                    self.cache[self._key(t)] = [x / norm for x in v]  # unit length: dot product = cosine
                os.makedirs(os.path.dirname(self.CACHE), exist_ok=True)
                json.dump(self.cache, open(self.CACHE, "w"))

    def top(self, question, graph, k, exclude_ids=()):
        self._ensure([question])
        q = self.cache[self._key(question)]
        scored = []
        for r, _ in self.by_graph.get(graph, []):
            if r["id"] in exclude_ids or r["question"].strip().lower() == question.strip().lower():
                continue
            v = self.cache[self._key(r["question"])]
            scored.append((-sum(a * b for a, b in zip(q, v)), r["id"], r))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [r for _, _, r in scored[:k]]
