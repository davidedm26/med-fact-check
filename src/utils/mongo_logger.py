"""
MongoDB node-level logger for the LangGraph pipeline.
=====================================================

Provides a ``@log_node`` decorator that transparently persists every
node execution to a single ``node_logs`` MongoDB collection.

Design goals
------------
* **Decoupled** – the pipeline works identically with or without Mongo.
* **Non-structured** – each node dumps whatever it returns; the
  downstream reconstruction task is responsible for interpreting the
  data.
* **Graceful** – if Mongo is unreachable or ``MONGO_LOGGING_ENABLED``
  is ``false``, the decorator becomes a silent no-op.
"""

from __future__ import annotations

import functools
import os
from datetime import datetime, timezone
from typing import Any, Callable

from utils.logger import get_logger

log = get_logger("MongoLogger")

# ---------------------------------------------------------------------------
# Connection singleton
# ---------------------------------------------------------------------------

_mongo_client = None
_mongo_db = None
_mongo_failed = False


def _get_mongo_db():
    """Return the MongoDB database handle (lazy singleton).

    Returns ``None`` when the connection cannot be established so that
    callers can degrade gracefully.
    """
    global _mongo_client, _mongo_db, _mongo_failed

    if _mongo_failed:
        return None

    if _mongo_db is not None:
        return _mongo_db

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "med_fact_check")

    try:
        from pymongo import MongoClient  # import here to avoid hard dep

        _mongo_client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        # Force a quick connection check
        _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[db_name]
        log.info(f"Connected to MongoDB: {uri} / {db_name}")
        return _mongo_db
    except Exception as exc:
        _mongo_failed = True
        log.warning(f"MongoDB connection failed ({exc}). Logging disabled.")
        return None


def _is_logging_enabled() -> bool:
    """Check the ``MONGO_LOGGING_ENABLED`` env var (default ``false``)."""
    return os.getenv("MONGO_LOGGING_ENABLED", "false").strip().lower() in (
        "true",
        "1",
        "yes",
    )


# ---------------------------------------------------------------------------
# Recursive BSON serialiser
# ---------------------------------------------------------------------------


def _serialize_for_mongo(obj: Any) -> Any:
    """Recursively convert *obj* into a BSON-safe structure.

    Handles LangChain message objects, numpy arrays, sets, and falls
    back to ``str()`` for anything else that is not natively
    JSON/BSON-serialisable.
    """
    # --- LangChain messages ---------------------------------------------------
    # Import lazily so the module can be loaded even without langchain installed.
    try:
        from langchain_core.messages import BaseMessage
    except ImportError:
        BaseMessage = None  # type: ignore[misc,assignment]

    if BaseMessage is not None and isinstance(obj, BaseMessage):
        return {
            "type": getattr(obj, "type", obj.__class__.__name__),
            "content": _serialize_for_mongo(obj.content),
            "name": getattr(obj, "name", None),
        }

    # --- LangGraph Command objects --------------------------------------------
    try:
        from langgraph.types import Command
    except ImportError:
        Command = None  # type: ignore[misc,assignment]

    if Command is not None and isinstance(obj, Command):
        return {
            "_kind": "Command",
            "goto": _serialize_for_mongo(getattr(obj, "goto", None)),
            "update": _serialize_for_mongo(getattr(obj, "update", None)),
        }

    # --- numpy arrays ---------------------------------------------------------
    try:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except ImportError:
        pass

    # --- standard containers --------------------------------------------------
    if isinstance(obj, dict):
        serialized = {}
        for k, v in obj.items():
            key = str(k)
            # Truncate text only for the massive 'downloaded_chunks' array to save Mongo space.
            # 'retrieved_chunks' will still be logged in full.
            if key == "downloaded_chunks" and isinstance(v, list):
                serialized[key] = [
                    {
                        **{chunk_k: _serialize_for_mongo(chunk_v) for chunk_k, chunk_v in chunk.items() if chunk_k != "text"},
                        "text": str(chunk.get("text", ""))[:50] + "..."
                    } if isinstance(chunk, dict) else _serialize_for_mongo(chunk)
                    for chunk in v
                ]
            else:
                serialized[key] = _serialize_for_mongo(v)
        return serialized

    if isinstance(obj, (list, tuple)):
        return [_serialize_for_mongo(item) for item in obj]

    if isinstance(obj, set):
        return [_serialize_for_mongo(item) for item in obj]

    # --- primitives that BSON handles natively --------------------------------
    if isinstance(obj, (str, int, float, bool, type(None), datetime)):
        return obj

    # --- fallback -------------------------------------------------------------
    return str(obj)


# ---------------------------------------------------------------------------
# Extract loggable output from a node return value
# ---------------------------------------------------------------------------


def _extract_output(result: Any) -> dict:
    """Return the dict payload to persist, handling both plain dicts and
    LangGraph ``Command`` objects.
    """
    try:
        from langgraph.types import Command
    except ImportError:
        Command = None  # type: ignore[misc,assignment]

    if Command is not None and isinstance(result, Command):
        update = getattr(result, "update", {}) or {}
        goto = getattr(result, "goto", None)
        return {
            "_command_goto": _serialize_for_mongo(goto),
            **_serialize_for_mongo(update),
        }

    if isinstance(result, dict):
        return _serialize_for_mongo(result)

    # Unknown return type – store as string
    return {"_raw": str(result)}


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def log_node(stage: str) -> Callable:
    """Decorator factory that logs a LangGraph node's output to MongoDB.

    Parameters
    ----------
    stage : str
        Logical stage name (e.g. ``"decompose"``, ``"retrieval"``,
        ``"evaluation"``, ``"aggregation"``).

    Usage::

        @log_node("retrieval")
        def source_selector_node(state: State):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state, *args, **kwargs):
            # Execute the original node
            result = func(state, *args, **kwargs)

            # --- persist to Mongo (best-effort) ---------------------------
            if not _is_logging_enabled():
                return result

            try:
                db = _get_mongo_db()
                if db is None:
                    return result

                document = {
                    "run_id": state.get("run_id") if isinstance(state, dict) else getattr(state, "run_id", None),
                    "node_name": func.__name__,
                    "stage": stage,
                    "subclaim_id": state.get("subclaim_id") if isinstance(state, dict) else getattr(state, "subclaim_id", None),
                    "subclaim": state.get("subclaim") if isinstance(state, dict) else getattr(state, "subclaim", None),
                    "timestamp": datetime.now(timezone.utc),
                    "output": _extract_output(result),
                }

                db["node_logs"].insert_one(document)
            except Exception as exc:
                log.warning(
                    f"Failed to log node '{func.__name__}' to MongoDB: {exc}"
                )

            return result

        return wrapper

    return decorator
