import pytest
from datetime import datetime, timedelta
from message_parsers import CommonParser
from utils import get_business_day

class DummyState:
    msg_id = "12345"

parser = CommonParser()

def make_msg(content, embeds=None, ts=None):
    return {
        "id": DummyState.msg_id,
        "content": content,
        "embeds": embeds or [],
        "timestamp": ts or datetime.utcnow().isoformat()
    }

@pytest.mark.parametrize("text, expected", [
    # Basic
    ("BTO AAPL 150C 06/20", {
        "underlying": "AAPL", "exp_month": 6, "exp_day": 20,
        "strike": 150.0, "p_or_c": "c", "instr": "BUY", "id": "12345"
    }),
    # Lowercase, “BUY” omitted (FORMAT_12_BUY=False)
    ("AAPL 150p 07/15 BOT", {
        "underlying": "AAPL", "exp_month": 7, "exp_day": 15,
        "strike": 150.0, "p_or_c": "p", "instr": "BUY", "id": "12345"
    }),
    # Reject word
    ("BTO SPY 400C 06/20 RISK", None),
])
def test_parse_simple(text, expected):
    msg = make_msg(text)
    result = parser.parse_message(parser, msg, state={"msg_id": msg["id"]})
    if expected is None:
        assert result is None or result == {}
    else:
        # only check the keys we care about
        for k, v in expected.items():
            assert result[k] == v

def test_parse_dte():
    # e.g. 1DTE → tomorrow (skipping weekends)
    today = datetime.today()
    tomorrow = get_business_day(1)
    msg = make_msg("BTO SPX 450C 1DTE")
    out = parser.parse_message(parser, msg, state={"msg_id": msg["id"]})
    assert out["exp_month"] == tomorrow.month
    assert out["exp_day"] == tomorrow.day
