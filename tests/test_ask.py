"""Ask the data on the synthetic database, with a scripted model.

Last week is 2026-09-28 to 2026-10-04. SSD has 70 guests and $3,230 of
revenue ($390 a day plus a $500 event). There is nothing a year earlier.
"""

import json

import pytest

from api import ask_tools
from api.llm import LLMError, RecordedClient, recording_key

FORBIDDEN_KEYS = {
    "customer_country",
    "order_id",
    "person_id",
    "comments",
    "notes",
    "voided_reason",
    "lost_reason_name",
}
LAST_WEEK = {"period": "last_week", "start": None, "end": None, "compare": "none"}


def tool_use(name="get_kpis", args=None, id="t1"):
    return {
        "content": [
            {"type": "tool_use", "id": id, "name": name, "input": args or LAST_WEEK}
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def text(reply, stop="end_turn"):
    return {
        "content": [{"type": "text", "text": reply}],
        "stop_reason": stop,
        "usage": {"input_tokens": 200, "output_tokens": 20},
    }


class FakeClient:
    model = "fake"

    def __init__(self, *turns):
        self.turns = list(turns)
        self.calls = []

    def create(self, system, tools, messages):
        self.calls.append(json.loads(json.dumps(messages)))
        turn = self.turns.pop(0) if len(self.turns) > 1 else self.turns[0]
        if isinstance(turn, Exception):
            raise turn
        return turn


def ask(make_client, fake, question="How did last week go?", user="nick@dev", **p):
    client = make_client(user)
    client.app.state.llm = fake
    return client.post("/api/ask", params=p, json={"question": question})


def keys(obj):
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in keys(v)}
    return set()


def test_grounded_reply_is_returned_with_its_numbers(make_client):
    fake = FakeClient(
        tool_use(), text("Attendance was 70 and total revenue was $3,230.")
    )
    body = ask(make_client, fake).json()
    assert body["answer"] == "Attendance was 70 and total revenue was $3,230."
    assert body["grounded"] is True and body["fallback"] is None
    assert body["tool_calls"] == [{"name": "get_kpis", "args": LAST_WEEK}]
    rows = {r["metric"]: r for r in body["table"]}
    assert rows["Attendance"]["current"] == 70
    assert rows["Total revenue"]["current"] == 3230.0
    assert body["usage"] == {"input_tokens": 300, "output_tokens": 30}


def test_tool_results_reach_the_model(make_client):
    fake = FakeClient(tool_use(), text("Attendance was 70."))
    ask(make_client, fake)
    result = fake.calls[1][-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "t1"
    out = json.loads(result["content"])
    assert out["venues"] == ["SSD"]
    assert out["window"]["start"] == "2026-09-28"


def test_invented_figure_falls_back_to_the_table(make_client):
    fake = FakeClient(tool_use(), text("Total revenue was $3,500, up 12%."))
    body = ask(make_client, fake).json()
    assert body["answer"] is None and body["grounded"] is False
    assert body["ungrounded"] == ["$3,500", "12%"]
    assert "not in the data" in body["fallback"]
    assert body["notice"].startswith("The answer had figures that could not be")
    assert {r["metric"] for r in body["table"]} >= {"Total revenue", "Attendance"}


def test_model_outage_falls_back_to_last_week_table(make_client):
    body = ask(make_client, FakeClient(LLMError("model unreachable"))).json()
    assert body["answer"] is None
    assert body["fallback"].startswith("model unreachable")
    assert body["notice"] == (
        "The assistant could not answer, so here are the numbers. "
        "These are for last week against last year."
    )
    rows = {r["metric"]: r for r in body["table"]}
    assert rows["Attendance"]["start"] == "2026-09-28"
    assert rows["Attendance"]["current"] == 70
    assert rows["Attendance"]["compared"] is True
    assert rows["Attendance"]["comparison_start"] == "2025-09-29"


def test_unrecorded_question_falls_back(make_client, tmp_path):
    body = ask(make_client, RecordedClient(tmp_path)).json()
    assert body["fallback"].startswith("no recorded answer")
    assert body["table"]


def test_recorded_turns_replay(make_client, tmp_path):
    first = "Selected venues: Summit Sky Deck (SSD)\n<question>\nHow?\n</question>"
    turns = [tool_use(), text("Attendance was 70.")]
    path = tmp_path / f"{recording_key([{'content': first}])}.json"
    path.write_text(json.dumps({"question": "How?", "model": "m", "turns": turns}))
    body = ask(make_client, RecordedClient(tmp_path), question="How?").json()
    assert body["answer"] == "Attendance was 70."
    assert body["model"] == "m"


def test_turn_limit_stops_the_loop(make_client):
    fake = FakeClient(tool_use())
    body = ask(make_client, fake).json()
    assert len(fake.calls) == 4
    assert "turn limit" in body["fallback"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_early_stop_falls_back(make_client, stop):
    body = ask(make_client, FakeClient(text("Attendance was 70.", stop))).json()
    assert body["answer"] is None
    assert stop in body["fallback"]


def test_bad_tool_arguments_go_back_as_an_error(make_client):
    bad = dict(LAST_WEEK, period="yesterday")
    fake = FakeClient(tool_use(args=bad), text("I don't know."))
    body = ask(make_client, fake).json()
    result = fake.calls[1][-1]["content"][0]
    assert result["is_error"] is True
    assert body["answer"] == "I don't know."


@pytest.mark.parametrize(
    "question", ["How did Riverbend Tower Lookout do?", "Show me RTL revenue"]
)
def test_restricted_user_naming_another_venue_gets_403_without_a_model_call(
    make_client, question
):
    fake = FakeClient(text("unused"))
    r = ask(make_client, fake, question, user="marcus@dev")
    assert r.status_code == 403
    assert fake.calls == []


def test_restricted_user_cannot_select_another_venue(make_client):
    fake = FakeClient(text("unused"))
    r = ask(make_client, fake, user="marcus@dev", venue="RTL")
    assert r.status_code == 403
    assert fake.calls == []


def test_naming_an_unselected_venue_asks_to_switch(make_client):
    fake = FakeClient(text("unused"))
    body = ask(make_client, fake, "How did Riverbend Tower Lookout do?").json()
    assert "Select it in the venue filter" in body["answer"]
    assert body["model_called"] is False and fake.calls == []


def test_tools_take_no_venue_and_are_strict():
    for tool in ask_tools.TOOLS:
        schema = tool["input_schema"]
        assert "venue" not in json.dumps(schema).lower()
        assert tool["strict"] is True
        assert schema["additionalProperties"] is False


@pytest.mark.parametrize("name", [t["name"] for t in ask_tools.TOOLS])
@pytest.mark.parametrize("venue", ["SSD", "RTL"])
def test_tool_outputs_hold_no_guest_or_free_text_fields(make_client, name, venue):
    fake = FakeClient(tool_use(name), text("I don't know."))
    ask(make_client, fake, venue=venue)
    out = json.loads(fake.calls[1][-1]["content"][0]["content"])
    assert not keys(out) & FORBIDDEN_KEYS
    assert out["venues"] == [venue]
    other = {"SSD", "RTL"} - {venue}
    assert not other & set(json.dumps(out).split('"'))


def test_missing_day_is_no_data_not_zero(make_client):
    day = {"period": "custom", "start": "2026-10-01", "end": "2026-10-01"}
    fake = FakeClient(
        tool_use(args=dict(day, compare="none")),
        text("There is no attendance data for 2026-10-01."),
    )
    body = ask(make_client, fake, venue="RTL").json()
    rows = {r["metric"]: r for r in body["table"]}
    assert rows["Attendance"]["current"] is None
    assert rows["Attendance"]["no_data"] is True
    assert body["grounded"] is True
