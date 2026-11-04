"""Isolate tests from the developer's persisted store: each test session gets a throwaway
AIRLOCK_DB_PATH so runs/keys from local dev never leak into assertions (and vice versa)."""
import os
import tempfile

os.environ.setdefault("AIRLOCK_DB_PATH", os.path.join(tempfile.mkdtemp(), "test-store.db"))
