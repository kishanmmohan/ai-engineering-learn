# P1 · Production RAG

> **Production AI Learning Plan · Unit P1**

Retrieval quality caps answer quality — most "model problems" are retrieval problems. This unit takes you from raw PDF to grounded, cited answers, and teaches the debugging discipline that attributes every bad answer to its pipeline stage.

**~1.5 weeks · Core · 3 lessons · Capstone Stage 1 · Exit check gates P2**

**On this page:** [1.1 Ingestion](#11-ingestion-from-documents-to-chunks) · [1.2 Retrieval](#12-retrieval-finding-the-right-evidence) · [1.3 Grounding & graphs](#13-grounding--graphs) · [Capstone Stage 1](#capstone--stage-1--build-document-qa-from-scratch) · [Practice](#practice--hands-on-probes) · [Exit check](#exit-check)

---

## 1.1 Ingestion: from documents to chunks

*Everything downstream is capped by what happens here — garbage in compounds.*

### Parsing reality

- A PDF is a **layout format, not a text format**: text arrives as positioned fragments with no guaranteed reading order. Extraction options escalate in cost: native text layer → OCR for scans → VLM for tables, figures, and complex layouts.
- Watch for the classic corruptions: headers/footers repeated into every page's text, multi-column reading order scrambled, tables flattened into word soup, hyphen-ated line breaks.
- Tables are structure, not prose. Flattening a table destroys the row/column relationships the answer lives in — extract them as structured data or markdown, or route them through a VLM.

### Chunking

- **Fixed-size chunking** is the baseline; **structure-aware chunking** (split on headings/sections, respect paragraph boundaries) is usually worth it — the document's own structure encodes topic boundaries.
- The size trade-off: too small → fragments with no context ("it shall be 30 MPa" — what shall?); too big → mushy embeddings (P0 §0.2) and wasted context budget. Typical starting point: 300–800 tokens with modest overlap; tune empirically.
- **Small-to-big / parent-child:** embed small chunks (sharp vectors), but return the surrounding parent section to the model (rich context). Decouples what you *search* from what you *read*.

### Metadata and tenancy

- Attach metadata at ingestion: document id, section path, page number, revision, dates. Metadata is what makes filters, citations, and re-ingestion possible — you cannot bolt it on later.
- **Multi-tenancy:** every record carries its tenant scope, and every query filters by it — enforced in code, not by convention. One missing filter is a data breach.
- **Idempotency:** key chunks by content hash + document id so re-ingesting a document updates rather than duplicates. (P5 makes this durable.)

> **Systems analogy** — Ingestion is ETL where the schema is implicit in the layout. And like ETL, its failures are silent and compounding: a scrambled table at ingestion becomes a confident wrong answer three stages later, with nothing in between throwing an error.

> **Failure modes to internalize**
>
> - Silent OCR garbage — the pipeline "succeeds", the text is noise. Sample and read your own chunks.
> - Chunk boundaries splitting the answer across two chunks, neither of which retrieves well alone.
> - Header/footer noise dominating small chunks' embeddings.
> - Re-ingesting a revised document and doubling the corpus.

---

## 1.2 Retrieval: finding the right evidence

*Design it as a funnel: cheap-and-wide first, expensive-and-precise second.*

### The three search modes

- **Dense (vectors):** embed the query, nearest-neighbor search (typically HNSW). Wins on paraphrase and synonyms — "thermal insulation requirements" finds "R-value specifications".
- **Sparse (BM25 / keyword):** exact term matching with frequency weighting. Wins on identifiers, rare tokens, exact phrases — "Section 4.2.1", part codes, error strings.
- **Hybrid:** run both, fuse the rankings (reciprocal rank fusion is the simple, robust default). Production systems default to hybrid because P0 §0.2's blind spots are real: dense search *cannot* do exact identifiers reliably.

### Precision tools

- **Metadata filters:** scope before you search — tenant, document type, revision, date range. A filter is worth more than a better embedding when you know the constraint.
- **Reranking:** a cross-encoder reads each (query, chunk) pair together and re-scores. The funnel: retrieve top-50 cheaply, rerank to top-8 expensively. This is routinely the single biggest quality win per unit of effort.
- **Query transforms:** expansion (add synonyms), HyDE (embed a hypothetical answer instead of the question), decomposition (split multi-hop questions into sub-queries). Apply when failure analysis shows vocabulary mismatch — not by default.
- **Context budgeting:** top-k is a cost/quality dial, not a constant. Every chunk you pass costs money, latency, and mid-context attention (P0 §0.1). Fewer, better chunks beat more, worse ones.

> **Systems analogy** — The retrieve-then-rerank funnel is a query planner: a cheap index scan to get candidates, then an expensive verification pass on the shortlist. You already know why you don't run the expensive check on the whole table.

> **Failure modes to internalize**
>
> - Right document, wrong chunk — retrieval "worked", the answer was two paragraphs away.
> - Vocabulary mismatch — the user says "cost", the document says "consideration".
> - Score thresholds that cliff: 0.78 returns evidence, 0.80 returns nothing, and nobody calibrated either.
> - Stale index — the document changed, the vectors didn't.

---

## 1.3 Grounding & graphs

*A grounded answer is a claim you can check. Everything else is vibes with citations.*

### The citation contract

- Every factual claim in the answer maps to a specific retrieved chunk, and the citation is **verifiable** — page or section a human can open and check.
- The dangerous failure is the *plausible* citation: right document, wrong page, claim not actually on it. It looks grounded; it isn't. Only spot-checking (and later, P3's citation-precision metric) catches it.
- **Abstention is a first-class answer.** "The documents don't cover this" must be a designed path (P0 §0.3's failure-path rule), not an accident. A system that never abstains is hallucinating on schedule.

### The failure taxonomy — your debugging discipline

Every bad answer is attributable. Walk the five questions in order:

```
bad answer?
├─ was the fact in the corpus at all?      → ingestion gap (or correct abstention!)
├─ in the corpus, but in no chunk cleanly? → chunking fault
├─ in a chunk, but not retrieved?          → retrieval fault (mode, filters, embedding)
├─ retrieved, but cut by the budget?       → budgeting fault (top-k, reranker order)
└─ in context, but answered wrongly?       → generation fault (prompt, grounding contract)
```

This taxonomy is the unit's core skill. "The model got it wrong" is not a diagnosis.

### Knowledge graphs — when geometry isn't enough

- Vector similarity answers "what text is *about* this?" It cannot answer relational questions: "what references Section 5?", "which components depend on X?", "how many clauses mention the contractor's obligations?" — multi-hop and aggregation need **entities and relations**.
- GraphRAG sketch: extract entities/relations at ingestion → store as a graph → answer by traversal (possibly combined with vector search for entry points).
- The honest trade-off: graphs add an extraction pipeline to build and maintain, and extraction itself is an LLM task with its own error rate. Reach for a graph when failure analysis shows *relational* misses — not because it's interesting.

---

## Capstone · Stage 1 — Build: document QA from scratch

Pick one dense technical PDF (~100+ pages, with structure: numbered sections, tables, cross-references — a standards document, hardware manual, or contract).

1. **Ingest:** parse, structure-aware chunking, metadata on every chunk (section path, page).
2. **Index:** embed into a vector store; add BM25/sparse alongside; hybrid fusion.
3. **Answer:** grounded generation with page-level citations and an explicit abstention path.
4. **Failure log:** five hard queries — a negation, an exact clause number, a cross-reference, a table lookup, an out-of-corpus question — each attributed to its pipeline stage using the taxonomy, with evidence.
5. **Stretch:** add a cross-encoder reranker; measure before/after on 20 self-written queries.

> **Solid when:** 15 of 20 queries answered with correct citations, and every failure is attributed to a stage with evidence.

**Tooling →** Qdrant / pgvector / FAISS · rank-bm25 or built-in sparse vectors · a PDF parser (PyMuPDF, unstructured) · optional: Neo4j for the graph lesson

---

## Practice — hands-on probes

*Do these against your own capstone corpus as you build it.*

1. Parse your PDF and print 5 randomly chosen chunks, raw. Read them like a stranger would.
   *Exit: you've seen your own chunking artifacts — split sentences, header noise, flattened tables — before retrieval hides them.*
2. Run the same natural-language query through dense-only, BM25-only, and hybrid. Compare the top-5 lists.
   *Exit: you can name a query class each mode wins.*
3. Query an exact clause/section number. Watch dense search miss and BM25 hit.
   *Exit: hybrid's existence, demonstrated on your own data.*
4. Retrieve top-50, rerank to top-8 with a cross-encoder. Diff the two lists.
   *Exit: you can articulate what the reranker fixed — and what it cost in latency.*
5. Ask 3 questions you know are **not** in the document.
   *Exit: the abstention path fires all three times — or you've found your first grounding bug.*
6. Take 5 bad answers and run the five-question drill on each.
   *Exit: every failure attributed to a stage, with the evidence written down.*

---

## Exit check

*Answer each from memory, out loud. Tick a box only when you could defend the answer to a colleague. All six → start P2.*

- [ ] Your system answers wrongly. Walk the five-question drill — what evidence do you look at for each stage?
- [ ] Why does hybrid search exist? Name two query classes where pure dense retrieval structurally fails.
- [ ] Chunk size: what breaks when chunks are too small? Too big? What does small-to-big/parent-child decouple?
- [ ] What makes a citation *verifiable*, and why is a plausible-but-wrong citation more dangerous than no citation?
- [ ] When would you add a knowledge graph instead of tuning vector search harder — and what's the maintenance cost you're accepting?
- [ ] A new revision of your PDF arrives. What has to happen to the index, and what silently breaks if you skip it?

---

*Unit P1 of the [Production AI learning plan](./learning-plan.md) · previous: [P0 — LLM Mechanics](./p0-llm-mechanics.md) · next: [P2 — Agents & Orchestration](./p2-agents-orchestration.md)*
