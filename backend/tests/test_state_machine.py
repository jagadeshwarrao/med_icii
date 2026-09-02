import pytest
from app.main import transition
from fastapi import HTTPException
def test_quote_transition_accepts_allowed_state(): transition('SENT','ACCEPTED',{'SENT':{'ACCEPTED'}})
def test_quote_transition_rejects_invalid_state():
 with pytest.raises(HTTPException): transition('DRAFT','ACCEPTED',{'SENT':{'ACCEPTED'}})
