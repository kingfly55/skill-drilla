"""Interactive search and inspection over materialized corpus views."""

from skill_drilla.search.index import (
    InspectionResult,
    SearchMatch,
    SearchResult,
    inspect_evidence,
    load_view_artifacts,
    run_search,
    write_search_result,
)
from skill_drilla.search.inspect import inspect_evidence_record
from skill_drilla.search.query import ParsedQuery, QuerySyntaxError, SearchFilters, parse_csv_filters, parse_query

__all__ = [
    "InspectionResult",
    "ParsedQuery",
    "QuerySyntaxError",
    "SearchFilters",
    "SearchMatch",
    "SearchResult",
    "inspect_evidence",
    "inspect_evidence_record",
    "load_view_artifacts",
    "parse_csv_filters",
    "parse_query",
    "run_search",
    "write_search_result",
]
