from datetime import datetime, timedelta
from threading import Lock
import logging
import random

logger = logging.getLogger(__name__)

# ── KNOWN LIMITATION ─────────────────────────────────────────────────────────
# This rate limiter stores state in-process memory (Python dict).
# It works correctly with a SINGLE Uvicorn worker.
# When running multiple workers (e.g. Gunicorn + multiple Uvicorn workers)
# each worker has its own separate counter → a blocked IP can bypass the limit
# by hitting a different worker.
#
# PHASE 5 TODO: Replace this dict-based store with Redis so all workers share
# one counter. The public API (check_rate_limit / record_attempt) stays the
# same — only the storage backend changes.
# ─────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """Thread-safe IP-based rate limiter with automatic cleanup"""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, 
                 block_duration: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.block_duration = block_duration
        
        self.attempts = {}  # {ip: [(timestamp, is_success), ...]}
        self.blocked = {}   # {ip: blocked_until_timestamp}
        self._lock = Lock()
    
    def check_rate_limit(self, ip: str) -> tuple[bool, str]:
        """Check if IP is allowed to attempt login"""
        with self._lock:
            # Periodic cleanup (1% chance per request)
            if random.random() < 0.01:
                self._cleanup_inactive_ips()
            
            # Check if currently blocked
            if self._is_blocked(ip):
                remaining_time = self._get_remaining_block_time(ip)
                logger.warning(f"RATE LIMIT: Blocked IP {ip} attempted login")
                return False, remaining_time
            
            # Cleanup old attempts for this IP
            self._cleanup_old_entries(ip)
            
            # Check recent failed attempts
            recent_failures = [
                timestamp for timestamp, success in self.attempts.get(ip, [])
                if not success
            ]
            
            if len(recent_failures) >= self.max_attempts:
                # Block this IP
                block_until = datetime.utcnow() + timedelta(seconds=self.block_duration)
                self.blocked[ip] = block_until
                
                logger.warning(
                    f"RATE LIMIT: IP {ip} exceeded {self.max_attempts} failed attempts "
                    f"- BLOCKING for {self.block_duration}s"
                )
                
                return False, self._get_remaining_block_time(ip)
            
            return True, ""
    
    def record_attempt(self, ip: str, success: bool):
        """Record login attempt"""
        with self._lock:
            if success:
                # Successful login - clear all failed attempts
                if ip in self.attempts:
                    del self.attempts[ip]
                if ip in self.blocked:
                    del self.blocked[ip]
                logger.info(f"AUTH SUCCESS: {ip} - cleared failed attempts")
            else:
                # Record failed attempt
                now = datetime.utcnow()
                if ip not in self.attempts:
                    self.attempts[ip] = []
                self.attempts[ip].append((now, False))
                logger.info(f"AUTH FAIL: {ip} - failed login attempt")
    
    def _is_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked"""
        if ip not in self.blocked:
            return False
        
        blocked_until = self.blocked[ip]
        if datetime.utcnow() >= blocked_until:
            # Block expired
            del self.blocked[ip]
            return False
        
        return True
    
    def _get_remaining_block_time(self, ip: str) -> str:
        """Get human-readable remaining block time"""
        if ip not in self.blocked:
            return ""
        
        remaining = int((self.blocked[ip] - datetime.utcnow()).total_seconds())
        minutes = remaining // 60
        seconds = remaining % 60
        
        return f"Too many failed login attempts. Try again in {minutes}m {seconds}s."
    
    def _cleanup_old_entries(self, ip: str):
        """Remove expired attempts for specific IP"""
        if ip not in self.attempts:
            return
        
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        self.attempts[ip] = [
            (timestamp, success) for timestamp, success in self.attempts[ip]
            if timestamp > cutoff
        ]
        
        # Remove empty entries
        if not self.attempts[ip]:
            del self.attempts[ip]
    
    def _cleanup_inactive_ips(self):
        """Remove IPs not seen in 24 hours (prevent memory leak)"""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)

        # Clean attempts
        self.attempts = {
            ip: entries for ip, entries in self.attempts.items()
            if entries and entries[-1][0] > cutoff
        }

        # Clean expired blocks
        self.blocked = {
            ip: until for ip, until in self.blocked.items()
            if until > now
        }

    def get_status(self) -> dict:
        """Return current rate limiter stats — useful for monitoring and tests."""
        with self._lock:
            return {
                "tracked_ips": len(self.attempts),
                "blocked_ips": len(self.blocked),
                "blocked_list": [
                    {
                        "ip": ip,
                        "blocked_until": until.isoformat(),
                        "remaining_seconds": max(0, int((until - datetime.utcnow()).total_seconds()))
                    }
                    for ip, until in self.blocked.items()
                    if until > datetime.utcnow()
                ],
            }

    def reset(self, ip: str | None = None):
        """Clear rate limit state. Pass an IP to clear one address, or None to clear all.
        Primarily used in tests.
        """
        with self._lock:
            if ip is None:
                self.attempts.clear()
                self.blocked.clear()
                logger.info("RATE LIMIT: Full reset")
            else:
                self.attempts.pop(ip, None)
                self.blocked.pop(ip, None)
                logger.info(f"RATE LIMIT: Reset for IP {ip}")
