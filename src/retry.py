import time
import random
import logging
from functools import wraps
from openai import APIStatusError

log = logging.getLogger(__name__)

def retry_on_service_unavailable(max_attempts: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    A decorator that retries a function that raises a 503 Service Unavailable error.
    
    It implements exponential backoff with jitter to avoid overwhelming the API.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except APIStatusError as e:
                    # Check for a 503 status code specifically
                    if e.status_code != 503:
                        raise  # Re-raise other errors (like 401, 404) immediately
                    
                    if attempt == max_attempts - 1:
                        log.error("Max retry attempts reached for 503 error.")
                        raise  # Final attempt failed, raise the exception
                    
                    # Calculate exponential backoff with jitter
                    delay = min(max_delay, (base_delay * (2 ** attempt))) + random.uniform(0, 1)
                    log.warning(
                        f"Received 503 (Service Unavailable). "
                        f"Retrying in {delay:.2f} seconds... (Attempt {attempt + 1}/{max_attempts})"
                    )
                    time.sleep(delay)
            return None  # Should not be reachable
        return wrapper
    return decorator