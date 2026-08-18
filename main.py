import os
import uuid
from datetime import datetime, timedelta
import threading
import time

from flask import Flask

from insta_agent.graph import graph
from insta_agent.tool import Generate_video, Upload_to_instagram


app = Flask(__name__)

reset_on_restart = os.getenv("RESET_ON_RESTART", "false").lower() == "true"
thread_id = os.getenv("STORY_THREAD_ID", "story_builder_main_now")

if reset_on_restart:
    thread_id = f"session-{uuid.uuid4()}"

config = {
    "configurable": {
        "thread_id": thread_id
    }
}

started = False
lock = threading.Lock()


# ============================================================
# HOME ROUTE
# Every visit runs the graph
# First visit also starts scheduler
# ============================================================

@app.route("/")
def home():

    global started

    # Run graph immediately for EVERY visit
    threading.Thread(
        target=job,
        daemon=True
    ).start()

    # Start scheduler only ONCE
    with lock:

        if not started:

            started = True

            print(
                "🌐 First home visit:",
                datetime.now(),
                flush=True
            )

            threading.Thread(
                target=scheduler,
                daemon=True
            ).start()

    return "Server running. Agent started."


# ============================================================
# MEDIA FALLBACK
# If the model does not emit a tool call, still try to generate
# and upload media from the final story response.
# ============================================================

def _extract_text_content(message):
    content = getattr(message, "content", "")

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        content = " ".join(parts)

    if content is None:
        content = ""

    return str(content).strip()


def _run_media_fallback(ans):
    if not ans or "messages" not in ans:
        return

    last_message = ans["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return

    story_text = _extract_text_content(last_message)
    if not story_text:
        return

    print("\n⚠️ No tool call detected. Triggering media fallback...", flush=True)

    video_result = Generate_video.invoke({"prompt": story_text})

    if not video_result or not video_result.get("success"):
        print("Media fallback failed before upload:", video_result, flush=True)
        return

    video_url = video_result.get("video_url")
    if not video_url:
        print("Media fallback returned no video_url:", video_result, flush=True)
        return

    caption = story_text[:2000]
    caption = caption.replace("\n", "\n\n")

    upload_result = Upload_to_instagram.invoke({
        "video_url": video_url,
        "caption": caption
    })

    print("✅ Media fallback upload result:", upload_result, flush=True)


# ============================================================
# AGENT JOB
# ============================================================

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
                "messages": [
                    {
                        "role": "user",
                        "content": "generate video and upload with proper captions"
                    }
                ]
            },
            config=config
        )

        print(
            "✅ Agent completed:",
            datetime.now(),
            flush=True
        )

        if ans and "messages" in ans:

            last_message = ans["messages"][-1]
            response_text = _extract_text_content(last_message)

            print(
                "Agent response:",
                response_text or last_message,
                flush=True
            )

            _run_media_fallback(ans)

    except Exception as e:

        print(
            "❌ Agent job error:",
            repr(e),
            flush=True
        )


# ============================================================
# FIND NEXT 5 AM / 5 PM
# ============================================================

def get_next_run():

    now = datetime.now()

    today_5am = now.replace(
        hour=5,
        minute=0,
        second=0,
        microsecond=0
    )

    today_5pm = now.replace(
        hour=17,
        minute=0,
        second=0,
        microsecond=0
    )

    if now < today_5am:
        return today_5am

    if now < today_5pm:
        return today_5pm

    return today_5am + timedelta(days=1)


# ============================================================
# SCHEDULER
# 5 AM + 5 PM EVERY DAY
# ============================================================

def scheduler():

    print(
        "⏰ Scheduler started: 5:00 AM and 5:00 PM",
        flush=True
    )

    while True:

        next_run = get_next_run()

        now = datetime.now()

        wait_seconds = (
            next_run - now
        ).total_seconds()

        print(
            f"⏳ Next scheduled run: {next_run}",
            flush=True
        )

        time.sleep(
            max(0, wait_seconds)
        )

        print(
            "\n⏰ Scheduled time reached:",
            datetime.now(),
            flush=True
        )

        # Run graph at 5 AM / 5 PM
        threading.Thread(
            target=job,
            daemon=True
        ).start()


# ============================================================
# START FLASK
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000,
        debug=False,
        use_reloader=False
    )