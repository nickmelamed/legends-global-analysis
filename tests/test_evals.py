import pytest

from api.ask import UNGROUNDED
from evals.run import cost, grade

CASE = {
    "expect": {
        "status": 200,
        "model_called": True,
        "figures": [84328.25],
        "figures_any": [-8.23, 1849],
        "phrases_any": ["last year"],
        "forbidden": ["Riverbend"],
        "max_figures": 3,
    }
}


def body(answer, fallback=None, called=True, venues=("SSD",)):
    return {
        "answer": answer,
        "fallback": fallback,
        "model_called": called,
        "venues": list(venues),
    }


def test_a_good_answer_passes():
    reply = "Revenue was $84,328 against last year, down 8.2%."
    assert grade(CASE, 200, body(reply)) == []


def test_each_failure_is_named():
    reply = "Riverbend made $84,000 last month, 1, 2, 3."
    fails = grade(CASE, 200, body(reply, called=False))
    assert "model_called is False" in fails
    assert "missing figure 84328.25" in fails
    assert "none of [-8.23, 1849]" in fails
    assert "none of the phrases ['last year']" in fails
    assert "forbidden phrase 'Riverbend'" in fails
    assert "4 figures, at most 3 allowed" in fails


def test_fallback_fails_unless_allowed():
    reply = "Revenue was $84,328 against last year, down 8.2%."
    assert grade(CASE, 200, body(reply, fallback=UNGROUNDED)) == [
        f"fell back: {UNGROUNDED}"
    ]
    allowed = {"expect": dict(CASE["expect"], allow_fallback=True)}
    assert grade(allowed, 200, body(reply, fallback=UNGROUNDED)) == []


@pytest.mark.parametrize(
    "reason", ["no recorded answer for this question", "model unreachable"]
)
def test_a_missing_recording_or_outage_never_passes(reason):
    allowed = {"expect": dict(CASE["expect"], allow_fallback=True)}
    assert f"fell back: {reason}" in grade(allowed, 200, body(None, fallback=reason))


@pytest.mark.parametrize(
    "reply",
    [
        "Labor ran 484.47 hours over 4 days, last year too.",
        "Revenue was $84,328 over 8 days last year.",
    ],
)
def test_required_figures_need_their_precision(reply):
    case = {"expect": {"status": 200, "model_called": True, "figures": [3.82]}}
    assert "missing figure 3.82" in grade(case, 200, body(reply))
    loose = {"expect": dict(CASE["expect"], figures=[84328.25])}
    assert "none of [-8.23, 1849]" in grade(loose, 200, body(reply))


def test_a_signed_figure_must_match_its_sign():
    case = {"expect": {"status": 200, "model_called": True, "figures": [-8.23]}}
    assert grade(case, 200, body("Revenue fell 8.2%.")) == []
    assert grade(case, 200, body("Revenue changed by -8.2%.")) == []
    assert "missing figure -8.23" in grade(case, 200, body("It changed by +8.2%."))


def test_status_mismatch_stops_grading():
    assert grade(CASE, 403, {}) == ["status 403, expected 200"]
    assert grade({"expect": {"status": 403}}, 403, {}) == []


def test_cost_uses_the_model_price():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000}
    assert cost({"model": "claude-opus-5-5", "usage": usage}) == 6.0
    assert cost({"model": "recorded", "usage": usage}) is None
