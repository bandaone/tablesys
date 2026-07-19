from datetime import time

from app.utils.transit import insufficient_transit_time


def test_back_to_back_events_in_different_rooms_require_transit_time():
    assert insufficient_transit_time(
        time(9), time(11), 10,
        time(11), time(13), 11,
    )


def test_back_to_back_events_in_the_same_room_are_allowed():
    assert not insufficient_transit_time(
        time(9), time(11), 10,
        time(11), time(13), 10,
    )


def test_ten_minute_gap_in_different_rooms_is_allowed():
    assert not insufficient_transit_time(
        time(9), time(11), 10,
        time(11, 10), time(13, 10), 11,
    )


def test_unknown_venue_is_not_treated_as_the_same_room():
    assert insufficient_transit_time(
        time(9), time(11), None,
        time(11), time(13), 10,
    )
