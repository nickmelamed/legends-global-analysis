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
    assert grade(CASE, 200, body(reply, fallback="model unreachable")) == [
        "fell back: model unreachable"
    ]
    allowed = {"expect": dict(CASE["expect"], allow_fallback=True)}
    assert grade(allowed, 200, body(reply, fallback="model unreachable")) == []


def test_status_mismatch_stops_grading():
    assert grade(CASE, 403, {}) == ["status 403, expected 200"]
    assert grade({"expect": {"status": 403}}, 403, {}) == []


def test_cost_uses_the_model_price():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000}
    assert cost({"model": "claude-opus-5-5", "usage": usage}) == 6.0
    assert cost({"model": "recorded", "usage": usage}) is None
