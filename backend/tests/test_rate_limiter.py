"""Unit tests for the in-process rate limiter."""

from datetime import datetime, timedelta

import pytest

from app.middleware.rate_limiter import RateLimiter


@pytest.mark.security
class TestRateLimiterUnit:
    """Direct unit tests for rate limiter behavior without API dependencies."""

    def test_allows_request_when_no_failures(self):
        limiter = RateLimiter(max_attempts=5, window_seconds=300, block_duration=300)

        allowed, message = limiter.check_rate_limit("127.0.0.1")

        assert allowed is True
        assert message == ""

    def test_blocks_after_max_failed_attempts(self):
        limiter = RateLimiter(max_attempts=5, window_seconds=300, block_duration=300)
        ip = "127.0.0.1"

        # First 5 checks are allowed; each failed attempt is recorded.
        for _ in range(5):
            allowed, _ = limiter.check_rate_limit(ip)
            assert allowed is True
            limiter.record_attempt(ip, success=False)

        # 6th check should be blocked.
        allowed, message = limiter.check_rate_limit(ip)
        assert allowed is False
        assert "Try again" in message

    def test_successful_login_clears_failures_and_block(self):
        limiter = RateLimiter(max_attempts=2, window_seconds=300, block_duration=300)
        ip = "10.0.0.2"

        for _ in range(2):
            allowed, _ = limiter.check_rate_limit(ip)
            assert allowed is True
            limiter.record_attempt(ip, success=False)

        blocked, _ = limiter.check_rate_limit(ip)
        assert blocked is False

        limiter.record_attempt(ip, success=True)

        allowed, message = limiter.check_rate_limit(ip)
        assert allowed is True
        assert message == ""

    def test_expired_block_unblocks_ip(self):
        limiter = RateLimiter()
        ip = "10.0.0.3"

        limiter.blocked[ip] = datetime.utcnow() - timedelta(seconds=1)

        allowed, message = limiter.check_rate_limit(ip)

        assert allowed is True
        assert message == ""
        assert ip not in limiter.blocked

    def test_window_cleanup_removes_old_failures(self):
        limiter = RateLimiter(max_attempts=3, window_seconds=60, block_duration=300)
        ip = "10.0.0.4"

        # Old failures outside window should be dropped.
        old_ts = datetime.utcnow() - timedelta(seconds=120)
        limiter.attempts[ip] = [(old_ts, False), (old_ts, False)]

        allowed, _ = limiter.check_rate_limit(ip)

        assert allowed is True
        assert ip not in limiter.attempts or len(limiter.attempts[ip]) == 0

    def test_status_and_reset(self):
        limiter = RateLimiter(max_attempts=1, window_seconds=300, block_duration=300)
        ip = "10.0.0.5"

        limiter.record_attempt(ip, success=False)
        limiter.check_rate_limit(ip)  # triggers block at max_attempts

        status_before = limiter.get_status()
        assert status_before["blocked_ips"] >= 1
        assert any(entry["ip"] == ip for entry in status_before["blocked_list"])

        limiter.reset(ip)

        status_after = limiter.get_status()
        assert all(entry["ip"] != ip for entry in status_after["blocked_list"])
