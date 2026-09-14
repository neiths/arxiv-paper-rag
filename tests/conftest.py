"""Shared pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_arxiv_response():
    """Mock response from arXiv API with realistic XML structure."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <title>ArXiv Query Results</title>
      <id>http://arxiv.org/api/query</id>
      <updated>2024-01-01T12:00:00Z</updated>
      <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1</opensearch:totalResults>
      <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
      <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">1</opensearch:itemsPerPage>
      <link href="http://arxiv.org/api/query?search_query=cat%3Acs.AI&amp;id_list=&amp;start=0&amp;max_results=1&amp;sortBy=submittedDate&amp;sortOrder=descending" rel="alternate" type="text/html"/>
      <link href="http://arxiv.org/api/query?search_query=cat%3Acs.AI&amp;id_list=&amp;start=0&amp;max_results=1&amp;sortBy=submittedDate&amp;sortOrder=descending" rel="self" type="application/atom+xml"/>
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <published>2024-01-01T18:42:23Z</published>
        <updated>2024-01-01T18:42:23Z</updated>
        <title>Attention Is All You Need: A Transformer Architecture</title>
        <summary>This paper introduces the Transformer architecture, which relies entirely on attention mechanisms, dispensing with recurrence and convolutions entirely. The model achieves new state of the art on machine translation tasks.</summary>
        <author><name>John Doe</name></author>
        <author><name>Jane Smith</name></author>
        <arxiv:primary_category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
        <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
        <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
        <link title="pdf" href="http://arxiv.org/pdf/2401.00001v1" rel="alternate" type="application/pdf"/>
        <link title="Abstract" href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
        <link rel="related" href="http://arxiv.org/cits/2401.00001v1" title="Citations"/>
        <arxiv:doi>10.48550/arXiv.2401.00001</arxiv:doi>
      </entry>
    </feed>"""


@pytest.fixture
def mock_empty_arxiv_response():
    """Mock empty response from arXiv API."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <title>ArXiv Query Results</title>
      <id>http://arxiv.org/api/query</id>
      <updated>2024-01-01T12:00:00Z</updated>
      <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>
      <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
      <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:itemsPerPage>
    </feed>"""
