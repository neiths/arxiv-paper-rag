# Understanding the `QueryBuilder` Class

The `QueryBuilder` class is a wrapper around the OpenSearch Query DSL. Its purpose is to generate a complete search request without manually writing JSON every time.

Instead of writing queries like:

```json
{
  "query": {
    "bool": {
      ...
    }
  }
}
```

you simply create a `QueryBuilder` object and call `build()`.

For example:

```python
builder = QueryBuilder(
    query="transformer attention",
    size=10,
    search_chunks=True
)

query = builder.build()
```

The generated query can then be sent directly to OpenSearch.

---

# Overall Architecture

The class follows a builder pattern.

```
                QueryBuilder
                     │
                     ▼
                 build()
                     │
     ┌───────────────┼────────────────┐
     │               │                │
     ▼               ▼                ▼
_build_query()   _source()    _highlight()
     │
     ▼
_build_text_query()
     │
     ▼
_build_filters()
```

Each private method is responsible for building one section of the final OpenSearch request.

---

# Constructor

```python
def __init__(
    self,
    query: str,
    size: int = 10,
    from_: int = 0,
    fields=None,
    categories=None,
    latest_papers=False,
    search_chunks=False,
)
```

The constructor stores all search options that will later be used to construct the query.

Example:

```python
builder = QueryBuilder(
    query="large language model",
    size=20,
    categories=["cs.AI"],
    search_chunks=True
)
```

---

# Automatic Search Fields

One of the nicest features is automatic field selection.

```python
if search_chunks:
    self.fields = [
        "chunk_text^3",
        "title^2",
        "abstract^1"
    ]
else:
    self.fields = [
        "title^3",
        "abstract^2",
        "authors^1"
    ]
```

Notice the `^` notation.

```
chunk_text^3
```

means

> Give matches in `chunk_text` three times the importance of the default weight.

Similarly,

```
title^2
```

means a match in the title is twice as important.

Suppose the query is

```
transformer
```

Two documents are returned.

Document A

```
Title:
Transformer

Abstract:
...
```

Document B

```
Title:
Deep Learning

Chunk:
Transformer architecture...
```

Because `chunk_text` has a weight of **3**, Document B may receive a higher score than Document A.

Field boosting is one of the simplest and most effective ranking techniques in OpenSearch.

---

# build()

```python
query_body = {
    "query": ...,
    "size": ...,
    "from": ...,
    "_source": ...,
    "highlight": ...
}
```

This assembles the complete request.

A generated query looks like

```json
{
  "query": {...},
  "size":10,
  "from":0,
  "_source": {...},
  "highlight": {...}
}
```

This dictionary is exactly what `client.search()` expects.

---

# _build_query()

The main search logic is placed inside a Boolean query.

```python
{
    "bool": {
        ...
    }
}
```

Boolean queries combine multiple conditions.

```
               bool
          ┌─────┴─────┐
          │           │
        must       filter
```

There are four common Boolean clauses:

* must
* should
* filter
* must_not

This implementation currently uses only **must** and **filter**.

---

## must

```python
must_clauses.append(
    self._build_text_query()
)
```

A document **must** satisfy this condition.

If the query is

```
graph neural network
```

OpenSearch performs a full-text search.

---

## match_all

If the user enters an empty query

```python
query=""
```

the class generates

```json
{
  "match_all": {}
}
```

instead of

```json
{
}
```

which tells OpenSearch to return every document.

---

# _build_text_query()

This is the core of keyword searching.

```python
{
    "multi_match": {
        ...
    }
}
```

Unlike `match`, `multi_match` searches several fields simultaneously.

For example

```
Query

transformer attention
```

Searches

* title
* abstract
* chunk_text

at the same time.

---

## Fields

```python
fields=[
    "chunk_text^3",
    "title^2",
    "abstract^1"
]
```

The query is executed against every field.

Higher weights contribute more to the final BM25 score.

---

## type="best_fields"

```python
"type":"best_fields"
```

Suppose

```
Query

attention mechanism
```

Document A

```
Title:
Attention Mechanism
```

Document B

```
Abstract:
Attention
Mechanism
```

`best_fields` prefers the document with the strongest single-field match.

Alternative modes include

```
cross_fields
phrase
phrase_prefix
bool_prefix
```

Each is useful for different search scenarios.

---

## operator="or"

```
deep learning transformer
```

With

```python
operator="or"
```

documents matching **any** word can be returned.

```
deep

OR

learning

OR

transformer
```

If changed to

```python
operator="and"
```

then every term must appear.

```
deep

AND

learning

AND

transformer
```

`or` usually provides higher recall, while `and` is stricter.

---

## fuzziness

```python
"fuzziness":"AUTO"
```

This enables typo tolerance.

Example

User types

```
trasnformer
```

instead of

```
transformer
```

OpenSearch can still find the correct documents.

---

## prefix_length

```python
prefix_length=2
```

The first two characters must match exactly.

Example

```
trnasformer
```

The first two characters

```
tr
```

match, so fuzzy matching is attempted.

However,

```
xransformer
```

starts with

```
xr
```

so it is unlikely to match.

Requiring a matching prefix improves performance and reduces false positives.

---

# _build_filters()

Filters do not affect the relevance score.

Example

```python
categories=["cs.AI"]
```

produces

```json
{
    "terms":{
        "categories":[
            "cs.AI"
        ]
    }
}
```

Only AI papers are searched.

A filter acts like an SQL `WHERE` clause.

```sql
WHERE category='cs.AI'
```

Unlike `must`, filters are cached and therefore faster for repeated queries.

---

# _build_source_fields()

OpenSearch normally returns the entire document.

```
{
    ...
    embedding:[1024 floats],
    title:...
}
```

Returning large embedding vectors wastes bandwidth.

For chunk search

```python
{
    "excludes":[
        "embedding"
    ]
}
```

the embedding is omitted.

This makes responses significantly smaller.

For paper search

```python
[
"title",
"authors",
"abstract"
]
```

only the listed metadata is returned.

---

# _build_highlight()

Highlighting tells OpenSearch to wrap matched text with HTML tags.

Example

Original

```
Transformer models use attention mechanisms.
```

Result

```html
<mark>Transformer</mark> models use attention mechanisms.
```

The frontend can directly render this.

---

## fragment_size

```python
fragment_size=150
```

Return approximately 150 characters around the match.

---

## number_of_fragments

```python
number_of_fragments=2
```

Return up to two highlighted snippets.

---

## require_field_match=False

Normally

```
query matches title
```

only highlights the title.

Setting

```python
require_field_match=False
```

allows OpenSearch to highlight all configured fields that contain matching content, improving the user experience.

---

# _build_sort()

Sorting depends on the search mode.

### Relevance search

If a query exists

```python
query="transformer"
```

the method returns

```python
None
```

OpenSearch then sorts automatically by `_score` (highest relevance first).

---

### Latest papers

If

```python
latest_papers=True
```

the generated sort is

```json
[
  {
    "published_date":{
      "order":"desc"
    }
  },
  "_score"
]
```

Newest papers appear first, while `_score` is used as a tie-breaker when publication dates are equal.

---

### Empty query

If the query is empty, the builder also sorts by publication date.

This effectively turns the search into a "browse the latest papers" feature.

---

# Example Generated Query

Suppose the user searches

```python
builder = QueryBuilder(
    query="transformer attention",
    categories=["cs.AI"],
    search_chunks=True,
    size=5
)
```

The resulting query is conceptually similar to:

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "transformer attention",
            "fields": [
              "chunk_text^3",
              "title^2",
              "abstract^1"
            ],
            "type": "best_fields",
            "operator": "or",
            "fuzziness": "AUTO"
          }
        }
      ],
      "filter": [
        {
          "terms": {
            "categories": ["cs.AI"]
          }
        }
      ]
    }
  },
  "size": 5,
  "from": 0,
  "_source": {
    "excludes": ["embedding"]
  },
  "highlight": {
    ...
  }
}
```

---

# Summary

`QueryBuilder` encapsulates the construction of an OpenSearch Query DSL request in a clean, reusable way. It automatically selects search fields based on whether the search targets papers or chunks, builds a `bool` query with `multi_match` for BM25 full-text retrieval, applies optional category filters, controls pagination and sorting, limits the returned fields to reduce payload size, and configures highlighted snippets for matched text. By separating each concern into dedicated helper methods, the class is easy to extend—for example, by adding date filters, author filters, or additional ranking logic—without modifying the overall query-building workflow.
