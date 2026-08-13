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

startworking = False


@app.route("/")
def Home():
    global startworking

    startworking = True

    return "Server running successfully. Automatic job started."


def job():

    global startworking

    if not startworking:
        return

    try:

        print("\n==============================")
        print("Job running:", datetime.now())
        print("==============================")

        ans = graph.invoke(
            {
                "messages": "generate and upload"
            },
            config=config
        )

        print(ans["messages"][-1].content)

    except Exception as e:

        print("Job error:", e)


def scheduler():

    while True:

        if startworking:
            job()

        print("Waiting 1 minute...\n")
        time.sleep(60 * 60)


if __name__ == "__main__":

    # Start scheduler in background
    thread = threading.Thread(
        target=scheduler,
        daemon=True
    )

    thread.start()

    # Start Flask
    app.run(
        debug=True,
        use_reloader=False
    )