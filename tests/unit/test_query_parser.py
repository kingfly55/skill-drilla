from skill_drilla.search.query import QuerySyntaxError, parse_csv_filters, parse_query


def test_parse_query_supports_single_keyword():
    parsed = parse_query("pipeline")
    assert parsed.operator == "OR"
    assert [term.value for term in parsed.terms] == ["pipeline"]
    assert parsed.matches("pipeline report") is True


def test_parse_query_supports_exact_phrase():
    parsed = parse_query('"pipeline report"')
    assert parsed.terms[0].is_phrase is True
    assert parsed.matches("nightly pipeline report generated") is True
    assert parsed.matches("pipeline generated report") is False


def test_parse_query_supports_boolean_and():
    parsed = parse_query("pipeline AND report")
    assert parsed.operator == "AND"
    assert [term.value for term in parsed.terms] == ["pipeline", "report"]
    assert parsed.matches("pipeline status report") is True
    assert parsed.matches("pipeline only") is False


def test_parse_query_defaults_multiple_terms_to_or():
    parsed = parse_query("pipeline report")
    assert parsed.operator == "OR"
    assert parsed.matches("pipeline only") is True
    assert parsed.matches("report only") is True


def test_parse_query_rejects_mixed_operators():
    try:
        parse_query("pipeline AND report OR alert")
    except QuerySyntaxError as exc:
        assert "mixed boolean operators" in str(exc)
    else:
        raise AssertionError("expected QuerySyntaxError")


def test_parse_query_rejects_unterminated_phrase():
    try:
        parse_query('"pipeline report')
    except QuerySyntaxError as exc:
        assert "unterminated" in str(exc)
    else:
        raise AssertionError("expected QuerySyntaxError")


def test_parse_csv_filters_supports_repeated_and_comma_values():
    assert parse_csv_filters(["alpha,beta", " gamma "]) == ("alpha", "beta", "gamma")
