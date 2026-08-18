import os
import time
import requests

from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

ARK_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
ARK_MODEL = "seedance-1-5-pro-251215"

INSTAGRAM_API_VERSION = "v23.0"


# ============================================================
# GENERATE VIDEO
# ============================================================

@tool
def Generate_video(prompt: str):
    """
    Generate a vertical video with ARK Seedance API.

    The generated video includes AI-generated audio.
    Returns the public video URL.
    """

    try:

        api_key = os.getenv("ARK_API_KEY")

        if not api_key:
            return {
                "success": False,
                "video_url": None,
                "message": "ARK_API_KEY is missing"
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # ----------------------------------------------------
        # VIDEO GENERATION REQUEST
        # ----------------------------------------------------

        payload = {
            "model": ARK_MODEL,

            "content": [
                {
                    "type": "text",
                    "text": prompt
                }
            ],

            # Vertical Instagram Reel
            "resolution": "720p",
            "ratio": "9:16",

            # 5 seconds
            "duration": 10,

            # IMPORTANT:
            # Enable generated audio
            "generate_audio": True,
        }

        print("\n========================================")
        print("CREATING VIDEO")
        print("========================================")

        response = requests.post(
            f"{ARK_BASE_URL}/contents/generations/tasks",
            headers=headers,
            json=payload,
            timeout=60
        )

        print("ARK CREATE STATUS:", response.status_code)
        print("ARK CREATE RESPONSE:", response.text[:2000])

        response.raise_for_status()

        data = response.json()

        task_id = data.get("id")

        if not task_id:
            return {
                "success": False,
                "video_url": None,
                "message": f"No task ID returned: {data}"
            }

        print("Video task ID:", task_id)

        # ----------------------------------------------------
        # POLL VIDEO STATUS
        # ----------------------------------------------------

        max_attempts = 120

        for attempt in range(1, max_attempts + 1):

            time.sleep(5)

            status_response = requests.get(
                f"{ARK_BASE_URL}/contents/generations/tasks/{task_id}",
                headers=headers,
                timeout=60
            )

            print(
                f"Video status check {attempt}:",
                status_response.status_code
            )

            status_response.raise_for_status()

            result = status_response.json()

            status = result.get("status")

            print("Video generation status:", status)

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if status == "succeeded":

                content = result.get("content", {})

                video_url = content.get("video_url")

                if not video_url:
                    return {
                        "success": False,
                        "video_url": None,
                        "message": f"Generation succeeded but no video_url returned: {result}"
                    }

                print("\n========================================")
                print("VIDEO GENERATED SUCCESSFULLY")
                print("========================================")
                print("VIDEO URL:", video_url)

                return {
                    "success": True,
                    "video_url": video_url,
                    "message": "Video generated successfully with audio"
                }

            # ------------------------------------------------
            # FAILED
            # ------------------------------------------------

            if status in [
                "failed",
                "expired",
                "cancelled"
            ]:

                return {
                    "success": False,
                    "video_url": None,
                    "message": f"Video generation failed. Status: {status}"
                }

        # ----------------------------------------------------
        # TIMEOUT
        # ----------------------------------------------------

        return {
            "success": False,
            "video_url": None,
            "message": "Video generation timed out after 10 minutes"
        }

    except requests.exceptions.RequestException as e:

        print("ARK REQUEST ERROR:", e)

        return {
            "success": False,
            "video_url": None,
            "message": str(e)
        }

    except Exception as e:

        print("VIDEO GENERATION ERROR:", e)

        return {
            "success": False,
            "video_url": None,
            "message": str(e)
        }


# ============================================================
# SAVE VIDEO METADATA
# ============================================================

@tool
def Save_video_metadata(video_url: str, metadata: dict):
    """
    Save video metadata for logging and tracking.
    """

    try:

        print("\n========================================")
        print("VIDEO METADATA")
        print("========================================")

        print("Video URL:", video_url)
        print("Metadata:", metadata)

        return {
            "success": True,
            "message": "Video metadata saved successfully"
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# UPLOAD VIDEO TO INSTAGRAM REELS
# ============================================================

@tool
def Upload_to_instagram(video_url: str, caption: str):
    """
    Upload a generated video to Instagram as a Reel.

    Steps:
    1. Create Instagram Reel container
    2. Wait for Instagram video processing
    3. Publish Reel
    """

    print("\n========================================")
    print("UPLOADING VIDEO TO INSTAGRAM")
    print("========================================")

    print("Video URL:", video_url)

    try:

        token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        ig_id = os.getenv("INSTAGRAM_USER_ID")

        # ----------------------------------------------------
        # CHECK ENVIRONMENT VARIABLES
        # ----------------------------------------------------

        if not token:

            return {
                "success": False,
                "message": "INSTAGRAM_ACCESS_TOKEN is missing"
            }

        if not ig_id:

            return {
                "success": False,
                "message": "INSTAGRAM_USER_ID is missing"
            }

        if not video_url:

            return {
                "success": False,
                "message": "video_url is empty"
            }

        # ====================================================
        # 1. CREATE REEL CONTAINER
        # ====================================================

        create_url = (
            f"https://graph.instagram.com/"
            f"{INSTAGRAM_API_VERSION}/"
            f"{ig_id}/media"
        )

        create_data = {

            # IMPORTANT
            # Tell Instagram this is a Reel
            "media_type": "REELS",

            "video_url": video_url,

            "caption": caption,

            "access_token": token
        }

        print("\nCreating Instagram Reel container...")

        response = requests.post(
            create_url,
            data=create_data,
            timeout=60
        )

        print("CREATE STATUS:", response.status_code)
        print("CREATE RESPONSE:", response.text)

        # Don't immediately hide Instagram's useful error
        if response.status_code != 200:

            return {
                "success": False,
                "message": (
                    f"Instagram container creation failed. "
                    f"HTTP {response.status_code}: "
                    f"{response.text}"
                )
            }

        create_result = response.json()

        creation_id = create_result.get("id")

        if not creation_id:

            return {
                "success": False,
                "message": f"Instagram did not return creation ID: {create_result}"
            }

        print("Creation ID:", creation_id)

        # ====================================================
        # 2. WAIT FOR INSTAGRAM PROCESSING
        # ====================================================

        print("\nWaiting for Instagram to process Reel...")

        status_url = (
            f"https://graph.instagram.com/"
            f"{INSTAGRAM_API_VERSION}/"
            f"{creation_id}"
        )

        max_attempts = 36

        for attempt in range(1, max_attempts + 1):

            time.sleep(5)

            status_response = requests.get(
                status_url,
                params={
                    "fields": "status_code,status",
                    "access_token": token
                },
                timeout=60
            )

            print(
                f"Instagram status check {attempt}:",
                status_response.status_code,
                status_response.text
            )

            if status_response.status_code != 200:

                return {
                    "success": False,
                    "message": (
                        f"Instagram status check failed: "
                        f"{status_response.text}"
                    )
                }

            status = status_response.json()

            status_code = status.get("status_code")
            status_text = status.get("status")

            print(
                "Instagram processing:",
                status_code,
                status_text
            )

            # ------------------------------------------------
            # VIDEO READY
            # ------------------------------------------------

            if status_code == "FINISHED":

                print("Instagram Reel is ready!")

                break

            # ------------------------------------------------
            # PROCESSING ERROR
            # ------------------------------------------------

            if status_code in [
                "ERROR",
                "EXPIRED"
            ]:

                return {
                    "success": False,
                    "message": (
                        f"Instagram video processing failed: "
                        f"{status}"
                    )
                }

        else:

            return {
                "success": False,
                "message": (
                    "Instagram Reel was not ready "
                    "after 3 minutes."
                )
            }

        # ====================================================
        # 3. PUBLISH REEL
        # ====================================================

        print("\nPublishing Instagram Reel...")

        publish_url = (
            f"https://graph.instagram.com/"
            f"{INSTAGRAM_API_VERSION}/"
            f"{ig_id}/media_publish"
        )

        publish_data = {
            "creation_id": creation_id,
            "access_token": token
        }

        publish_response = requests.post(
            publish_url,
            data=publish_data,
            timeout=60
        )

        print(
            "PUBLISH STATUS:",
            publish_response.status_code
        )

        print(
            "PUBLISH RESPONSE:",
            publish_response.text
        )

        if publish_response.status_code != 200:

            return {
                "success": False,
                "message": (
                    f"Instagram publishing failed: "
                    f"{publish_response.text}"
                )
            }

        publish_result = publish_response.json()

        instagram_media_id = publish_result.get("id")

        print("\n========================================")
        print("INSTAGRAM REEL PUBLISHED")
        print("========================================")

        print(
            "Instagram Media ID:",
            instagram_media_id
        )

        return {
            "success": True,
            "instagram_media_id": instagram_media_id,
            "creation_id": creation_id,
            "message": "Video successfully published as Instagram Reel"
        }

    except requests.exceptions.RequestException as e:

        print("INSTAGRAM REQUEST ERROR:", e)

        return {
            "success": False,
            "message": str(e)
        }

    except Exception as e:

        print("INSTAGRAM ERROR:", e)

        return {
            "success": False,
            "message": str(e)
        }