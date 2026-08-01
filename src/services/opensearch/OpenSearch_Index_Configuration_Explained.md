# OpenSearch Index Configuration Explained

This configuration defines an OpenSearch index designed for **hybrid search**, which combines:

* **BM25 (keyword search)** for lexical matching.
* **Vector search (KNN)** for semantic similarity using embeddings.

The goal is to retrieve relevant paper chunks even when the query does not contain the exact same words.

---

# 1. Index Name

```python
ARXIV_PAPERS_CHUNKS_INDEX = "arxiv-papers-chunks"
```

This is simply the name of the OpenSearch index where all document chunks are stored.

Instead of storing an entire paper as one document, each paper is split into multiple chunks.

Example:

```
Paper A
├── Chunk 0
├── Chunk 1
├── Chunk 2
└── Chunk 3
```

Each chunk becomes one document inside the index.

---

# 2. Settings

```python
"settings": {
```

The `settings` section controls how the index behaves internally.

---

## number_of_shards

```python
"number_of_shards": 1
```

A shard is a partition of an index.

Example:

```
100 documents

1 shard
+----------------+
| 100 documents  |
+----------------+

4 shards
+----+----+----+----+
|25  |25  |25  |25  |
+----+----+----+----+
```

More shards allow distributed searching across multiple machines but add overhead.

For small datasets, a single shard is usually enough.

---

## number_of_replicas

```python
"number_of_replicas": 0
```

A replica is a copy of a shard.

Example:

```
Primary Shard
      |
      +------ Replica
```

Replicas provide:

* Fault tolerance
* Higher search throughput

Since this configuration is likely intended for development or experimentation, replicas are disabled.

---

## Enable KNN

```python
"index.knn": True
```

This enables vector search functionality.

Without this setting, OpenSearch only supports traditional BM25 keyword search.

---

## Vector Similarity Metric

```python
"index.knn.space_type": "cosinesimil"
```

This tells OpenSearch to compare vectors using **cosine similarity**.

Example:

```
Query embedding
        ↑

Document A  ↗

Document B  →

Document C  ↓
```

The smaller the angle between vectors, the more semantically similar they are.

---

# 3. Text Analysis

```python
"analysis": {
```

Before indexing text, OpenSearch processes it through an analyzer.

---

## Standard Analyzer

```python
"standard_analyzer": {
    "type": "standard",
    "stopwords": "_english_"
}
```

Example input:

```
The cat is sleeping on the sofa.
```

After analysis:

```
cat
sleeping
sofa
```

Common stop words like **the**, **is**, and **on** are removed.

---

## Custom Text Analyzer

```python
"text_analyzer": {
    "type": "custom",
    "tokenizer": "standard",
    "filter": [
        "lowercase",
        "stop",
        "snowball"
    ]
}
```

This analyzer performs three steps:

### Lowercase

```
Machine Learning
↓

machine learning
```

---

### Stop Filter

```
This is a machine learning paper

↓

machine learning paper
```

---

### Snowball Stemmer

Words are reduced to their root form.

```
running
runner
runs

↓

run
```

This improves matching across different grammatical forms.

---

# 4. Mapping

```python
"mappings": {
```

Mappings define the schema of documents stored in the index.

It's similar to a table schema in SQL.

---

## Dynamic Strict

```python
"dynamic": "strict"
```

Only fields explicitly defined in the mapping are allowed.

Example:

Allowed:

```json
{
    "title": "...",
    "authors": "..."
}
```

Rejected:

```json
{
    "title": "...",
    "foo": "bar"
}
```

This helps catch bugs caused by unexpected fields.

---

# 5. Metadata Fields

```python
"chunk_id": {"type": "keyword"}
```

A unique identifier for each chunk.

Example:

```
paper1_chunk3
```

---

```python
"paper_id": {"type": "keyword"}
```

Identifies the original paper.

Example:

```
paper_123
```

---

```python
"arxiv_id": {"type": "keyword"}
```

Stores the official arXiv identifier.

Example:

```
2405.12345
```

---

```python
"chunk_index": {"type": "integer"}
```

Indicates the order of chunks within the paper.

```
Chunk 0

Chunk 1

Chunk 2
```

---

# 6. Chunk Text

```python
"chunk_text": {
    "type": "text",
```

This is the main content that will be searched using BM25.

Example:

```
Transformers have revolutionized NLP...
```

The field also has a keyword subfield:

```python
"fields": {
    "keyword": {
        "type": "keyword"
    }
}
```

This creates two indexed versions:

```
chunk_text
    ↓
Analyzed text
```

and

```
chunk_text.keyword
    ↓
Exact string
```

Use:

* `chunk_text` → full-text search
* `chunk_text.keyword` → exact filtering or aggregations

---

# 7. Character Positions

```python
"start_char"
"end_char"
```

These store the chunk's position in the original document.

Example:

```
Paper

0........................5000

Chunk 1

500-1000
```

Useful for reconstructing or highlighting text.

---

# 8. Embedding Field

```python
"embedding": {
    "type": "knn_vector"
}
```

This is the heart of semantic search.

Instead of storing text, it stores a numerical vector.

Example:

```
"Deep learning"

↓

[0.12,
 -0.44,
 0.98,
 ...
]
```

The vector has 1024 dimensions because it was generated by the **Jina v3 embedding model**.

---

# 9. HNSW Configuration

```python
"method": {
    "name": "hnsw"
}
```

HNSW (Hierarchical Navigable Small World) is an Approximate Nearest Neighbor (ANN) algorithm.

Instead of comparing the query vector with every document (which is slow), it builds a graph that allows OpenSearch to jump quickly to nearby vectors.

```
Traditional

Query

↓

Compare with

1
2
3
4
5
...
1,000,000
```

```
HNSW

Query

↓

Graph

↓

Nearby nodes

↓

Top candidates
```

This dramatically speeds up vector search while maintaining high recall.

---

## Engine

```python
"engine": "nmslib"
```

`nmslib` is the underlying ANN library used to build and search the HNSW graph.

---

## m

```python
"m": 16
```

Controls the number of connections each node has in the graph.

Higher values:

* Better recall
* More memory usage
* Slower indexing

Lower values:

* Less memory
* Faster indexing
* Lower search quality

---

## ef_construction

```python
"ef_construction": 512
```

Controls how thoroughly the graph is built during indexing.

Higher values:

* Better graph quality
* Higher recall
* Slower indexing
* Larger index

Lower values:

* Faster indexing
* Lower recall

This parameter affects indexing only, not search.

---

# 10. Paper Metadata

Additional fields provide context for each chunk:

* `title` – Paper title, analyzed for text search.
* `authors` – Author names, searchable and filterable.
* `abstract` – Full paper abstract.
* `categories` – arXiv categories (stored as `keyword` for exact filtering).
* `published_date` – Publication date.
* `section_title` – Section where the chunk came from (e.g., "Introduction", "Methodology").
* `embedding_model` – Records which embedding model generated the vector, useful when multiple models are used.
* `created_at` / `updated_at` – Timestamps for auditing and data management.

---

# 11. How Hybrid Search Works

When a user submits a query:

```
"What is reinforcement learning?"
```

Two searches happen in parallel:

### BM25 Search

```
Query
      ↓
Keyword Matching
      ↓
Text Score
```

This finds chunks containing words like:

* reinforcement
* learning

---

### Vector Search

```
Query
      ↓
Embedding Model
      ↓
1024-dimensional Vector
      ↓
Nearest Neighbor Search (HNSW)
```

This retrieves chunks that are semantically related, even if they don't contain the exact keywords.

For example, a chunk discussing "RL agents optimizing cumulative rewards" may still be retrieved because its embedding is close to the query's embedding.

---

# Summary

This index is optimized for Retrieval-Augmented Generation (RAG) by combining traditional lexical search with semantic vector search. BM25 provides precise keyword matching, while the `knn_vector` field and HNSW index enable fast semantic retrieval. The additional metadata fields allow efficient filtering, ranking, and reconstruction of the original paper, making this schema well-suited for indexing and searching chunked academic documents.
