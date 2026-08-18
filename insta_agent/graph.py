from insta_agent.agent import AgentCall, Summarize

from langgraph.graph import StateGraph, START, END

from insta_agent.state import State

from insta_agent.tool import Generate_video, Upload_to_instagram

from langgraph.prebuilt import ToolNode

from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

import certifi
import threading
import time
import os


# ============================================================
# MONGODB
# ============================================================

DB_NAME = "Insta_memory_video"
MONGO_URI = "mongodb+srv://Aftab355201:Aftab355201@cluster0.cn5rpym.mongodb.net/?appName=Cluster0"

client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)

checkpointer = MongoDBSaver(
    client=client,
    db_name=DB_NAME
)


# ============================================================
# MONGODB CLEANUP
# Keeps only the LATEST checkpoint per thread_id across ALL
# checkpoint databases.  Drops empty databases so Atlas storage
# is continuously reclaimed.
# Runs every CLEANUP_INTERVAL_HOURS hours in the background.
# ============================================================

CLEANUP_INTERVAL_HOURS = int(os.getenv("CHECKPOINT_CLEANUP_HOURS", "24"))

# All databases that may accumulate LangGraph checkpoints
_ALL_CHECKPOINT_DBS = [
    DB_NAME,
    "langgraph",
    "Insta_memory",
    "Insta_memory_real",
]


def _clean_one_db(db_name: str) -> tuple:
    """Clean a single checkpoint database.
    Returns (deleted_checkpoints, deleted_writes).
    """
    db = client[db_name]
    checkpoints_col = db["checkpoints"]
    writes_col      = db["checkpoint_writes"]

    thread_ids = checkpoints_col.distinct("thread_id")
    total_cp = total_wr = 0

    for tid in thread_ids:
        latest = checkpoints_col.find_one(
            {"thread_id": tid},
            sort=[("checkpoint_id", -1)]
        )
        if not latest:
            continue

        latest_id = latest["checkpoint_id"]

        r1 = checkpoints_col.delete_many({
            "thread_id": tid,
            "checkpoint_id": {"$ne": latest_id}
        })
        total_cp += r1.deleted_count

        r2 = writes_col.delete_many({
            "thread_id": tid,
            "checkpoint_id": {"$ne": latest_id}
        })
        total_wr += r2.deleted_count

    # If both collections are now empty, drop the whole database so Atlas
    # actually reclaims the storage (dropping empty collections first).
    if (
        db_name != DB_NAME  # never auto-drop the active database
        and checkpoints_col.count_documents({}) == 0
        and writes_col.count_documents({}) == 0
    ):
        try:
            checkpoints_col.drop()
            writes_col.drop()
            client.drop_database(db_name)
            print(f"  🗑️  Dropped empty database `{db_name}`.", flush=True)
        except Exception:
            pass

    return total_cp, total_wr


def _cleanup_old_checkpoints():
    """Run cleanup across all known checkpoint databases."""
    total_cp = total_wr = 0
    for db_name in _ALL_CHECKPOINT_DBS:
        try:
            cp, wr = _clean_one_db(db_name)
            total_cp += cp
            total_wr += wr
        except Exception as exc:
            print(f"⚠️  MongoDB cleanup error ({db_name}): {exc}", flush=True)

    print(
        f"🧹 MongoDB cleanup done: removed {total_cp} old checkpoint(s)"
        f" and {total_wr} old write(s).",
        flush=True
    )


def _cleanup_loop():
    """Background thread: wait 60 s for startup, then run every N hours."""
    time.sleep(60)
    while True:
        _cleanup_old_checkpoints()
        time.sleep(CLEANUP_INTERVAL_HOURS * 3600)


# Start cleanup thread
_cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
_cleanup_thread.start()


# ============================================================
# ROUTER
# ============================================================

def route_after_agent(state: State):

    last_message = state["messages"][-1]

    # If agent requested a tool
    if getattr(last_message, "tool_calls", None):
        return "tools"

    # No tool call → check message count
    if len(state["messages"]) > 15:
        return "summarize"

    return "end"


# ============================================================
# GRAPH
# ============================================================

graph = StateGraph(State)

graph.add_node("AgentCall", AgentCall)

graph.add_node(
    "tools",
    ToolNode([
        Generate_video,
        Upload_to_instagram
    ])
)

graph.add_node("Summarize", Summarize)


# ============================================================
# START
# ============================================================

graph.add_edge(
    START,
    "AgentCall"
)


# ============================================================
# AGENT ROUTING
# ============================================================

graph.add_conditional_edges(
    "AgentCall",
    route_after_agent,
    {
        "tools": "tools",
        "summarize": "Summarize",
        "end": END
    }
)


# ============================================================
# TOOLS → AGENT
# ============================================================

graph.add_edge(
    "tools",
    "AgentCall"
)


# ============================================================
# SUMMARY → END
# ============================================================

graph.add_edge(
    "Summarize",
    END
)


# ============================================================
# COMPILE
# ============================================================

graph = graph.compile(
    checkpointer=checkpointer
)


# ============================================================
# RUN
# ============================================================
