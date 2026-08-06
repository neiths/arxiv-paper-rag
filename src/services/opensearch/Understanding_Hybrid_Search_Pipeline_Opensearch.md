# Understanding the Hybrid Search Pipeline in OpenSearch

When performing **hybrid search**, OpenSearch executes two independent searches:

1. **BM25 search** (keyword-based retrieval)
2. **Vector (KNN) search** (semantic retrieval)

The challenge is that these two searches produce completely different score ranges.

For example:

**BM25**

| Document | Score |
| -------- | ----: |
| A        |  18.5 |
| B        |  12.1 |
| C        |   4.3 |

**Vector Search (Cosine Similarity)**

| Document | Score |
| -------- | ----: |
| B        |  0.95 |
| C        |  0.92 |
| D        |  0.90 |

These scores cannot simply be added together because they are measured on different scales.

The search pipeline defines **how OpenSearch combines the two result sets into one final ranking.**

---

# 1. RRF Pipeline

```python
HYBRID_RRF_PIPELINE = {
    "id": "hybrid-rrf-pipeline",
    "description": "Post processor for hybrid RRF search",
    "phase_results_processors": [
        {
            "score-ranker-processor": {
                "combination": {
                    "technique": "rrf",
                    "rank_constant": 60,
                }
            }
        }
    ],
}
```

This pipeline uses **Reciprocal Rank Fusion (RRF)**.

Instead of combining **scores**, it combines **rank positions**.

---

# 2. Why Use RRF?

Suppose the query is:

> "transformer attention"

The BM25 search returns:

| Rank | Document |
| ---- | -------- |
| 1    | A        |
| 2    | B        |
| 3    | C        |

The vector search returns:

| Rank | Document |
| ---- | -------- |
| 1    | B        |
| 2    | D        |
| 3    | A        |

Notice that:

- BM25 prefers **Document A** because it contains the exact keywords.
- Vector search prefers **Document B** because it is semantically similar.

Which document should be ranked first?

This is exactly what RRF solves.

---

# 3. RRF Formula

RRF assigns each document a score using:

$\text{Score} = \frac{1}{k + \text{rank}}$

where:

- **rank** = document position (1, 2, 3, ...)
- **k** = `rank_constant`

In your configuration:

```python
"rank_constant": 60
```

so the formula becomes: $\frac{1}{60+\text{rank}}$

---

# 4. Example Calculation

### BM25 Ranking

| Rank | Score |
| ---- | ----- |
| A    | 1     |
| B    | 2     |
| C    | 3     |

RRF contribution:

| Document |     Contribution |
| -------- | ---------------: |
| A        | 1 / 61 = 0.01639 |
| B        | 1 / 62 = 0.01613 |
| C        | 1 / 63 = 0.01587 |

---

### Vector Ranking

| Rank | Score |
| ---- | ----- |
| B    | 1     |
| D    | 2     |
| A    | 3     |

Contribution:

| Document |     Contribution |
| -------- | ---------------: |
| B        | 1 / 61 = 0.01639 |
| D        | 1 / 62 = 0.01613 |
| A        | 1 / 63 = 0.01587 |

---

### Final RRF Score

Add the contributions from both rankings.

| Document | BM25    | Vector  |       Total |
| -------- | ------- | ------- | ----------: |
| A        | 0.01639 | 0.01587 | **0.03226** |
| B        | 0.01613 | 0.01639 | **0.03252** |
| C        | 0.01587 | 0       |     0.01587 |
| D        | 0       | 0.01613 |     0.01613 |

Final ranking:

1. B
2. A
3. D
4. C

Notice that **Document B** wins because it appears near the top of both searches, even though it is not ranked first by BM25.

---

# 5. Why `rank_constant = 60`?

If `k` is small:

```
k = 1

Rank 1 → 0.50
Rank 2 → 0.33
Rank 3 → 0.25
```

The difference between ranks is very large.

If `k = 60`:

```
Rank 1 → 0.01639
Rank 2 → 0.01613
Rank 3 → 0.01587
```

The differences become much smaller.

This means:

- Multiple rankings contribute more fairly.
- A document that ranks well in both searches is rewarded.
- One search cannot dominate simply because it ranked a document first.

A value around **60** has been shown in research to work well across many retrieval tasks and is the commonly recommended default.

---

# 6. Why Is RRF Popular?

RRF has several advantages:

- It ignores incompatible score scales between BM25 and vector search.
- It requires no manual weight tuning.
- It is robust across different datasets.
- It is simple to understand and compute.
- It often performs competitively with more complex ranking methods.

Because of these properties, RRF is widely used in Retrieval-Augmented Generation (RAG) systems and search engines.

---

# 7. The Alternative Pipeline

The commented-out pipeline uses a different strategy:

```python
"normalization-processor"
```

Instead of using document ranks, it combines the **actual scores**.

---

## Step 1: Normalize Scores

```python
"normalization": {
    "technique": "l2"
}
```

BM25 and vector scores have different ranges.

Example:

BM25:

```
18
15
10
5
```

Vector:

```
0.92
0.88
0.81
```

L2 normalization rescales each list so that their magnitudes become comparable before combining them.

Without normalization, BM25's larger numeric values would overwhelm vector similarity scores.

---

## Step 2: Combine Scores

```python
"technique": "harmonic_mean"
```

The harmonic mean emphasizes documents that perform well in **both** searches.

For example:

| BM25 | Vector | Harmonic Mean |
| ---: | -----: | ------------: |
|  0.9 |    0.9 |          High |
|  0.9 |    0.2 |           Low |
|  0.5 |    0.5 |        Medium |

Unlike an arithmetic average, the harmonic mean penalizes a document that scores well in only one retrieval method.

---

## Step 3: Weights

```python
"weights": [0.3, 0.7]
```

This specifies the relative importance of each search method:

- **30%** BM25
- **70%** Vector Search

If semantic similarity is more important than exact keyword matching, assigning a higher weight to vector search can improve results.

However, finding the best weights usually requires experimentation on your own dataset.

---

# 8. Why the Code Chooses RRF

The comments indicate that RRF is the default because it generally provides strong performance without requiring manual tuning.

| RRF                     | Weighted Average             |
| ----------------------- | ---------------------------- |
| Uses document ranks     | Uses numeric scores          |
| No normalization needed | Requires score normalization |
| No weight tuning        | Requires choosing weights    |
| Robust across datasets  | Dataset-specific tuning      |
| Easy to maintain        | More configuration           |

For many production RAG systems, RRF is a sensible default because it avoids the complexity of calibrating different scoring systems while still producing high-quality rankings.

---

# Summary

This configuration defines a **hybrid ranking pipeline** that merges BM25 keyword search and vector similarity search. The active pipeline uses **Reciprocal Rank Fusion (RRF)**, which combines the rank positions of documents rather than their raw scores, making it robust to different scoring scales and eliminating the need for manual weight tuning. The commented-out alternative demonstrates a score-based approach that normalizes BM25 and vector scores and combines them using a weighted harmonic mean, offering greater control but requiring careful parameter tuning. For most applications, especially Retrieval-Augmented Generation (RAG), RRF is preferred because it is simple, reliable, and consistently produces strong retrieval quality.
