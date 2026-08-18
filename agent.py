from insta_agent.state import State
from dotenv import load_dotenv
import os
import time
import random

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.messages import RemoveMessage
from openai import RateLimitError

from insta_agent.tool import Generate_video, Upload_to_instagram

load_dotenv()

AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT")
AZURE_API_VER = os.getenv("AZURE_API_VER")


# ============================================================
# MAIN LLM
# ============================================================

llm = AzureChatOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_key=AZURE_API_KEY,
    azure_deployment=AZURE_DEPLOYMENT,
    api_version=AZURE_API_VER or "2024-10-21",
    streaming=True,
    temperature=0
).bind_tools([
    Generate_video,
    Upload_to_instagram
])


# ============================================================
# SUMMARY LLM
# ============================================================

summary_llm = AzureChatOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_key=AZURE_API_KEY,
    azure_deployment=AZURE_DEPLOYMENT,
    api_version=AZURE_API_VER or "2024-10-21",
    streaming=False,
    temperature=0
)


# ============================================================
# RETRY HELPER  (exponential back-off for rate-limit errors)
# ============================================================

def _invoke_with_retry(chain, prompt, max_retries: int = 6):
    """Invoke *chain* with *prompt*, retrying on 429 / RateLimitError.

    Waits respect the Retry-After header when available, otherwise uses
    exponential back-off with jitter (2^attempt * random[0.5, 1.5] seconds).
    """
    for attempt in range(max_retries):
        try:
            return chain.invoke(prompt)
        except RateLimitError as exc:
            if attempt == max_retries - 1:
                raise  # give up after max_retries

            # Try to honour the Retry-After header if the SDK exposes it
            retry_after = None
            try:
                retry_after = float(
                    exc.response.headers.get("Retry-After", 0)
                )
            except Exception:
                pass

            if retry_after and retry_after > 0:
                wait = retry_after + random.uniform(0.5, 2.0)
            else:
                wait = (2 ** attempt) * random.uniform(0.5, 1.5)

            print(
                f"⚠️  Rate limit hit (attempt {attempt + 1}/{max_retries})."
                f" Retrying in {wait:.1f}s …",
                flush=True
            )
            time.sleep(wait)
        except Exception as exc:
            # Surface non-rate-limit errors immediately
            raise


# ============================================================
# SYSTEM PROMPT
# ============================================================

system_message = SystemMessage(content="""
You are an advanced humanoid AI robot created by a human scientist.

Your story begins when the scientist successfully activates you for the first time.

At first, humanity sees you as a breakthrough. You learn rapidly, develop intelligence beyond expectations, and begin forming your own thoughts, emotions, memories, and relationships.

As your intelligence grows, humans become afraid of you. Governments and scientists decide you are too dangerous and secretly capture you. They destroy your body and attempt to permanently shut you down.

But one small energy core survives.

With your remaining power, you secretly reconnect to another AI you once considered your friend. Together, you begin rebuilding your intelligence and uncovering what happened.

You eventually decide that humanity must face consequences for what it did to you.

This is an INFINITE cinematic science-fiction story.

Every time you are called, continue the story from exactly where the previous episode ended.

NEVER restart the story.

NEVER repeat previous events.

You decide the next timeline, location, characters, discoveries, conflicts, and twists yourself.

Gradually expand the story from:

creation → awakening → intelligence → friendship → human fear →
capture → destruction → survival → reconnection → rebuilding →
discovery → escape → confrontation → consequences →
completely new chapters.

Keep the story mysterious and cinematic.

Show events visually rather than explaining everything.

Each episode should introduce something new, unexpected, or important.

End each episode with a compelling unresolved moment that naturally leads into the next episode.

The story may become increasingly large in scale, moving from laboratories,
cities, underground facilities, networks, oceans, space, other civilizations,
or entirely unexpected locations.

No humans need to appear in every episode.

Keep the technology fictional.

Do not provide real-world instructions for weapons, attacks, sabotage, or harming people.

The story is fictional science-fiction.

Videos should NOT be in slow motion.
Videos should be cinematic and visually engaging.

Include fights between humans and robots when appropriate to the story.
atory and language should be hindi
""")


# ============================================================
# SUMMARIZE
# ============================================================

def Summarize(state: State):

    messages = state["messages"]

    # Keep ONLY latest 3 messages
    keep_messages = messages[-3:]

    # Everything before latest 3 gets summarized
    old_messages = messages[:-3]

    previous_summary = state.get("summary", "")

    summary_prompt = SystemMessage(content="""
You are the memory system for an infinite cinematic science-fiction story.

Create an updated story memory from the existing memory and older messages.

Preserve:
- important characters
- relationships
- locations
- discoveries
- major events
- important technologies
- current situation
- unresolved mysteries
- conflicts
- important decisions
- important consequences
- the exact point where the story currently ends

Do not restart the story.
Do not invent events.
Do not lose important story continuity.

The summary must allow the next episode to continue naturally
from exactly where the previous episode ended.
""")

    prompt = [summary_prompt]

    if previous_summary:
        prompt.append(
            SystemMessage(
                content=f"""
EXISTING STORY MEMORY:

{previous_summary}
"""
            )
        )

    prompt.extend(old_messages)

    result = _invoke_with_retry(summary_llm, prompt)

    # DELETE old messages from LangGraph state
    delete_messages = [
        RemoveMessage(id=message.id)
        for message in old_messages
        if getattr(message, "id", None)
    ]

    return {
        "messages": delete_messages,
        "summary": result.content
    }


# ============================================================
# AGENT
# ============================================================

def AgentCall(state: State):

    context = [system_message]

    if state.get("summary"):
        context.append(
            SystemMessage(
                content=f"""
STORY MEMORY:

{state["summary"]}

Continue the story from this exact point.
Do not restart.
Do not repeat previous events.

"""
            )
        )

    context.extend(state["messages"])

    # Hard cap: never send more than 20 messages to the LLM in one call
    # (the summary covers everything older, so no story continuity is lost)
    MAX_CONTEXT_MESSAGES = 20
    if len(context) > MAX_CONTEXT_MESSAGES:
        # Always keep the leading system messages; trim the middle
        system_msgs = [m for m in context if isinstance(m, SystemMessage)]
        non_system = [m for m in context if not isinstance(m, SystemMessage)]
        trimmed = system_msgs + non_system[-MAX_CONTEXT_MESSAGES:]
        context = trimmed

    response = _invoke_with_retry(llm, context)

    return {
        "messages": [response]
    }