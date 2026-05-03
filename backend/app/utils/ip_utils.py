from fastapi import Request

def get_client_ip(request: Request) -> str:
    """
    Get real client IP address, handling proxies/load balancers correctly.
    
    Checks X-Forwarded-For header first (set by proxies),
    falls back to direct connection IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For format: "client, proxy1, proxy2"
        # First IP is the real client
        return forwarded.split(",")[0].strip()
    
    # Direct connection (no proxy)
    return request.client.host
