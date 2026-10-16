import pytest
from hypothesis import given
from hypothesis import strategies as st

from api.grounding import check, figures

TOOL_OUTPUT = [
    {
        "window": {
            "start": "2026-09-28",
            "end": "2026-10-04",
            "comparison_start": "2025-09-29",
            "days_elapsed": 7,
        },
        "kpis": [
            {"key": "total_revenue", "current": 84328.25, "delta_pct": -8.23},
            {"key": "attendance", "current": 1849, "comparison": None},
            {"key": "guests_per_labor_hour", "current": 3.82},
        ],
        "data_gap": False,
    }
]


@pytest.mark.parametrize(
    "reply",
    [
        "Total revenue was $84,328.25.",
        "Total revenue was about $84,328.",
        "Revenue fell 8.2% against last year.",
        "Revenue changed by -8.23%.",
        "Attendance was 1,849 guests over 7 days.",
        "Productivity was 3.82 guests per labor hour, or 3.8 rounded.",
        "Last week ran from 2026-09-28 to 2026-10-04.",
        "Last week ran from Sep 28 to October 4, 2026, against 2025.",
        "I don't know. The data has no competitor prices.",
        "Total revenue declined 8.2% against last year.",
        "Total revenue decreased 8.23% to $84,328.25.",
        "Revenue may rise next week. Last week it was $84,328.25.",
        "Revenue changed by -8.23%, a fall of 8.23%.",
    ],
)
def test_grounded_replies_pass(reply):
    result = check(reply, TOOL_OUTPUT)
    assert result.ok, result.ungrounded


@pytest.mark.parametrize(
    "reply, bad",
    [
        ("Total revenue was $84,500.", "$84,500"),
        ("Attendance was 1,850.", "1,850"),
        ("Revenue was $84.3K.", "$84.3K"),
        ("Revenue was $1.2 million.", "$1.2 million"),
        ("Competitors charge $35 a ticket.", "$35"),
        ("Last week ran from 2026-09-21.", "2026-09-21"),
        ("Last week ran from Sep 21.", "Sep 21"),
        ("Revenue was down 9%.", "9%"),
        ("Revenue fell by .5%.", ".5%"),
        ("Revenue changed by +8.23%.", "+8.23%"),
        ("Separately 28 guests complained.", "28"),
        ("Revenue was twelve thousand dollars higher.", "twelve"),
        ("Revenue was about a third more than plan.", "third"),
    ],
)
def test_ungrounded_figures_are_named(reply, bad):
    result = check(reply, TOOL_OUTPUT)
    assert not result.ok
    assert bad in result.ungrounded


def test_booleans_are_not_numbers():
    assert not check("There were 0 gaps.", [{"data_gap": False}]).ok


def test_figures_finds_every_number():
    assert figures("Up 3.2% to $1,200 from -4 and 7") == ["3.2%", "$1,200", "-4", "7"]


@given(
    value=st.floats(-1e7, 1e7, allow_nan=False).map(lambda v: round(v, 2)),
    places=st.integers(0, 2),
    style=st.sampled_from(["{:,.{p}f}", "${:,.{p}f}", "{:.{p}f}%"]),
)
def test_any_tool_value_formatted_for_display_is_grounded(value, places, style):
    reply = "The figure was " + style.format(value, p=places) + "."
    assert check(reply, [{"current": value}]).ok


@given(value=st.integers(1, 10**6), offset=st.integers(1, 1000))
def test_a_different_whole_number_is_not_grounded(value, offset):
    assert not check(f"It was {value + offset:,}.", [{"current": value}]).ok
