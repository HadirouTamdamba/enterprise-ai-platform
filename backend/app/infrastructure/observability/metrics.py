"""Prometheus metrics for HTTP, LLM and RAG activity."""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "eap_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "eap_http_request_duration_seconds", "HTTP request latency", ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

LLM_REQUESTS = Counter(
    "eap_llm_requests_total", "LLM gateway calls", ["provider", "model", "outcome"]
)
LLM_TOKENS = Counter(
    "eap_llm_tokens_total", "LLM tokens", ["provider", "model", "direction"]
)
LLM_COST = Counter("eap_llm_cost_usd_total", "LLM cost in USD", ["provider", "model"])
LLM_LATENCY = Histogram(
    "eap_llm_latency_seconds", "LLM call latency", ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
LLM_CACHE_HITS = Counter("eap_llm_cache_hits_total", "Gateway cache hits", ["provider", "model"])

RAG_QUERIES = Counter("eap_rag_queries_total", "RAG queries", ["knowledge_base"])
RAG_RETRIEVED_CHUNKS = Histogram(
    "eap_rag_retrieved_chunks", "Chunks retrieved per query", buckets=(0, 2, 4, 8, 16, 32)
)
DOCUMENTS_INDEXED = Counter("eap_documents_indexed_total", "Documents indexed", ["status"])

AGENT_RUNS = Counter("eap_agent_runs_total", "Agent runs", ["agent", "outcome"])
GUARDRAIL_BLOCKS = Counter("eap_guardrail_blocks_total", "Guardrail blocks", ["guardrail"])

ACTIVE_INGESTIONS = Gauge("eap_active_ingestions", "Documents currently being processed")
