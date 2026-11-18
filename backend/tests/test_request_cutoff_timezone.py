from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

from orion.api.interactive.request_manager.request_manager import RequestManager


def test_cutoff_converts_local_time_and_explicit_offset_to_utc():
    assert RequestManager._cutoff_to_utc(datetime(2030, 1, 15, 12), 'America/Toronto') == datetime(2030, 1, 15, 17)
    assert RequestManager._cutoff_to_utc(datetime(2030, 7, 15, 12), 'America/Toronto') == datetime(2030, 7, 15, 16)
    assert RequestManager._cutoff_to_utc(datetime(2030, 1, 15, 12, tzinfo=timezone(timedelta(hours=5))), 'America/Toronto') == datetime(2030, 1, 15, 7)


@pytest.mark.parametrize('value', [datetime(2030, 3, 10, 2, 30), datetime(2030, 11, 3, 1, 30)])
def test_cutoff_rejects_nonexistent_and_ambiguous_local_times(value):
    with pytest.raises(HTTPException):
        RequestManager._cutoff_to_utc(value, 'America/Toronto')


def test_expiry_validation_compares_start_in_request_timezone():
    RequestManager._validate_request_expiry(datetime(2099, 1, 15, 16), datetime(2099, 1, 15, 12), timezone_name='America/Toronto')
    with pytest.raises(HTTPException):
        RequestManager._validate_request_expiry(datetime(2099, 1, 15, 18), datetime(2099, 1, 15, 12), timezone_name='America/Toronto')
