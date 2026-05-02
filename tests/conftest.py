"""
tests/conftest.py — Session-level server check for integration tests.

When test_api.py is in the test session, this fixture verifies the server is
running at localhost:8000. If not, the ENTIRE session is skipped with a clear
message so developers see one line instead of 67 connection errors.

Running only test_unit.py does NOT require a server and will not be skipped.
"""

import pytest
import requests


def pytest_collection_modifyitems(config, items):
    """Check if any integration test (test_api.py) is in the collected items."""
    # Store whether test_api tests are present so the fixture can decide.
    config._alphahunter_has_api_tests = any(
        "test_api.py" in str(node.fspath) for node in items
    )


@pytest.fixture(scope="session", autouse=True)
def require_server(request):
    """Skip entire session if server is needed but not running."""
    config = request.config

    # If only unit tests are running, no server needed.
    if not getattr(config, "_alphahunter_has_api_tests", False):
        return

    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        if r.status_code != 200:
            pytest.skip(
                "Server at localhost:8000 returned non-200 "
                f"(got {r.status_code}) -- start it first: "
                "uvicorn api.main:app --port 8000",
                allow_module_level=True,
            )
    except Exception:
        pytest.skip(
            "Server not running at localhost:8000 -- start it first: "
            "uvicorn api.main:app --port 8000",
            allow_module_level=True,
        )


@pytest.fixture(scope="session", autouse=True)
def ensure_test_user(require_server):
    """Insert QA test user (id=99999) so _auth_headers() JWT resolves correctly."""
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from api.auth.database import _get_connection
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (id, google_id, email, name, created_at, last_login)
                VALUES
                    (99999, 'qa-test-google-id-99999', 'qa-test@alphahunter.test',
                     'QA Test User', ?, ?)
                """,
                (now, now),
            )
            conn.commit()
    except Exception as e:
        pytest.skip(f"Could not create test user in DB: {e}")
