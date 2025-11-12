import pytest
from cga.utils.fs import parse_omitted_lines, omit_lines


def make_lines(n):
    """Helper to create lines: [(1,'L1'), (2,'L2'), ...]"""
    return [(i, f"L{i}") for i in range(1, n + 1)]


def extract_line_nums(result):
    """Return list of first elements (line numbers or omitted markers) from omit_lines output."""
    return [r[0] for r in result]


def test_parse_omitted_lines_empty():
    assert parse_omitted_lines("") == set()


def test_parse_omitted_lines_ranges_and_single():
    s = "2-4,6"
    expected = {2, 3, 4, 6}
    assert parse_omitted_lines(s) == expected


def test_omit_lines_no_omission():
    lines = make_lines(5)
    res = omit_lines(lines, set())
    assert res == lines


def test_omit_single_line():
    lines = make_lines(5)
    res = omit_lines(lines, {3})
    # Expect marker at position of line 3
    firsts = extract_line_nums(res)
    assert firsts == [1, 2, "[omitted lines: 3]", 4, 5]


def test_omit_continuous_range():
    lines = make_lines(6)
    res = omit_lines(lines, {2, 3, 4})
    firsts = extract_line_nums(res)
    assert firsts == [1, "[omitted lines: 2-4]", 5, 6]


def test_omit_multiple_ranges_and_singletons():
    # Omit lines 2, 4-5, 8
    lines = make_lines(10)
    omitted = {2, 4, 5, 8}
    res = omit_lines(lines, omitted)
    firsts = extract_line_nums(res)
    # Expected sequence: 1, marker 2, 3, marker 4-5, 6,7, marker 8, 9,10
    assert firsts == [1, "[omitted lines: 2]", 3, "[omitted lines: 4-5]", 6, 7, "[omitted lines: 8]", 9, 10]


def test_omit_at_start_and_end():
    lines = make_lines(5)
    res = omit_lines(lines, {1, 5})
    firsts = extract_line_nums(res)
    assert firsts == ["[omitted lines: 1]", 2, 3, 4, "[omitted lines: 5]"]
