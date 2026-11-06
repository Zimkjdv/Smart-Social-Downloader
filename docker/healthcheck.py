"""Bounded direct-loopback readiness probe; no proxy, redirects or private output."""
import http.client
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ssdl.config import configured_port


def main() -> int:
    connection = None
    try:
        connection = http.client.HTTPConnection("127.0.0.1", configured_port(), timeout=3)
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        content = response.read(2049)
        if response.status != 200 or len(content) > 2048:
            return 1
        result = json.loads(content)
        if not isinstance(result, dict):
            return 1
        checks = result.get("checks")
        return 0 if (result.get("service") == "ssdl" and result.get("status") == "healthy"
                     and isinstance(checks, dict)
                     and set(checks) == {"application", "worker", "persistence", "dependencies"}
                     and all(value is True for value in checks.values())) else 1
    except (OSError, ValueError, RuntimeError, http.client.HTTPException):
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
