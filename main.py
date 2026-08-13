from flask import Flask
import threading
import time
from datetime import datetime

from insta_agent.graph import graph


app = Flask(__name__)

config = {
    "configurable": {
        "thread_id": "1"
    }
}

# Prevent multiple scheduler threads/jobs
started = False
lock = threading.Lock()


@app.route("/")
def home():
    global started

    # First home visit only
    with lock:
        if not started:
            started = True

            print(
                "🌐 First home visit detected:",
                datetime.now(),
                flush=True
            )

            # Run first agent call immediately
            threading.Thread(
                target=job,
                daemon=True
            ).start()

            # Start hourly scheduler
            threading.Thread(
                target=scheduler,
                daemon=True
            ).start()

            return "Server running. Agent started."

    # All later Updown calls
    return "Server running successfully."


def job():

    print("\n==============================", flush=True)
    print(
        "🤖 Agent job started:",
        datetime.now(),
        flush=True
    )
    print("==============================", flush=True)

    try:

        ans = graph.invoke(
            {
                "messages": "generate and upload"
            },
            config=config
        )

        print(
            "✅ Agent completed:",
            datetime.now(),
            flush=True
        )

        if ans and "messages" in ans:

            print(
                "Agent response:",
                ans["messages"][-1].content,
                flush=True
            )

    except Exception as e:

        print(
            "❌ Agent job error:",
            repr(e),
            flush=True
        )


def scheduler():

    print(
        "⏰ Hourly scheduler started",
        flush=True
    )

    # Wait exactly 1 hour after the FIRST job was started
    time.sleep(60 * 60)

    while True:

        print(
            "\n⏰ One hour passed. Starting agent:",
            datetime.now(),
            flush=True
        )

        job()

        print(
            "💤 Waiting 1 hour...",
            flush=True
        )

        time.sleep(60 * 60)


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False,
        use_reloader=False
    )
