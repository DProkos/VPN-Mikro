"""Rate limiter for connection attempts.

Implements a simple rate limiting mechanism to prevent brute-force
attacks and excessive connection attempts.
"""

from datetime import datetime, timedelta
from typing import Optional


class RateLimiter:
    """Rate limiter for connection attempts.
    
    Implements a cooldown mechanism after a specified number of failed attempts.
    After MAX_ATTEMPTS failures, enforces a COOLDOWN_SECONDS wait period.
    
    Attributes:
        MAX_ATTEMPTS: Maximum failed attempts before cooldown (default 5).
        COOLDOWN_SECONDS: Cooldown duration in seconds (default 60).
    """
    
    MAX_ATTEMPTS = 5
    COOLDOWN_SECONDS = 60
    
    def __init__(
        self,
        max_attempts: int = MAX_ATTEMPTS,
        cooldown_seconds: int = COOLDOWN_SECONDS
    ):
        """Initialize the rate limiter.
        
        Args:
            max_attempts: Maximum failed attempts before cooldown.
            cooldown_seconds: Cooldown duration in seconds.
        """
        self._max_attempts = max_attempts
        self._cooldown_seconds = cooldown_seconds
        self._attempts = 0
        self._cooldown_until: Optional[datetime] = None
    
    @property
    def attempts(self) -> int:
        """Get current number of failed attempts."""
        return self._attempts
    
    @property
    def cooldown_until(self) -> Optional[datetime]:
        """Get the datetime when cooldown ends, or None if not in cooldown."""
        return self._cooldown_until
    
    def can_attempt(self) -> bool:
        """Check if a new attempt is allowed.
        
        Returns:
            True if an attempt is allowed, False if in cooldown.
        """
        if self._cooldown_until is None:
            return True
        
        if datetime.now() >= self._cooldown_until:
            # Cooldown expired, reset state
            self._reset()
            return True
        
        return False
    
    def record_failure(self) -> None:
        """Record a failed attempt.
        
        If this failure exceeds MAX_ATTEMPTS, starts the cooldown period.
        """
        self._attempts += 1
        
        if self._attempts >= self._max_attempts:
            self._cooldown_until = datetime.now() + timedelta(seconds=self._cooldown_seconds)
    
    def record_success(self) -> None:
        """Record a successful attempt.
        
        Resets the failure counter and clears any cooldown.
        """
        self._reset()
    
    def get_cooldown_remaining(self) -> int:
        """Get remaining cooldown time in seconds.
        
        Returns:
            Remaining seconds in cooldown, or 0 if not in cooldown.
        """
        if self._cooldown_until is None:
            return 0
        
        remaining = (self._cooldown_until - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def is_in_cooldown(self) -> bool:
        """Check if currently in cooldown period.
        
        Returns:
            True if in cooldown, False otherwise.
        """
        return not self.can_attempt()
    
    def _reset(self) -> None:
        """Reset the rate limiter state."""
        self._attempts = 0
        self._cooldown_until = None
