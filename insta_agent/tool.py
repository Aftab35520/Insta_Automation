import os
import requests
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()


@tool
def Generate_image(prompt: str):
    """Generate an image with Pixazo and return its public image URL."""

   

    try:
        api_key = os.getenv("PIXAZO_API_KEY")

        if not api_key:
            return {
                "success": False,
                "image_url": None,
                "message": "PIXAZO_API_KEY is missing"
            }

        url = "https://gateway.pixazo.ai/getImage/v1/getSDXLImage"

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": prompt,
            "negative_prompt": (
                "blurry, low quality, distorted, deformed, "
                "text, letters, numbers, watermark, logo"
            ),
            "width": 1024,
            "height": 1024,
            "num_steps": 20,
            "guidance_scale": 5,
            "seed": -1
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=180
        )

        print("Pixazo status:", response.status_code)
        print("Pixazo response:", response.text[:2000])

        response.raise_for_status()

        data = response.json()

        image_url = data.get("imageUrl")

        if not image_url:
            return {
                "success": False,
                "image_url": None,
                "message": f"No imageUrl returned: {data}"
            }

        print("IMAGE URL:", image_url)

        return {
            "success": True,
            "image_url": image_url,
            "message": "Image generated successfully"
        }

    except Exception as e:
        print("ERROR:", e)

        return {
            "success": False,
            "image_url": None,
            "message": str(e)
        }



import time
@tool
def Upload_to_instagram(image_url: str, caption: str):
    """
    Generate an Instagram media container, wait until Instagram finishes
    processing it, then publish it.
    """

    print("Uploading image to Instagram...")
    print("Image URL:", image_url)

    try:
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        ig_id = os.getenv("INSTAGRAM_USER_ID")

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

        # ==========================================
        # 1. CREATE MEDIA CONTAINER
        # ==========================================

        create_url = f"https://graph.instagram.com/v23.0/{ig_id}/media"

        create_data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": token
        }

        response = requests.post(
            create_url,
            data=create_data,
            timeout=60
        )

        print("CREATE STATUS:", response.status_code)
        print("CREATE RESPONSE:", response.text)

        response.raise_for_status()

        creation_id = response.json()["id"]

        print("Creation ID:", creation_id)

        # ==========================================
        # 2. WAIT FOR INSTAGRAM TO PROCESS IMAGE
        # ==========================================

        status_url = f"https://graph.instagram.com/v23.0/{creation_id}"

        max_attempts = 12

        for attempt in range(max_attempts):

            time.sleep(5)

            status_data = {
                "fields": "status_code,status",
                "access_token": token
            }

            status_response = requests.get(
                status_url,
                params=status_data,
                timeout=60
            )

            print(
                f"STATUS CHECK {attempt + 1}:",
                status_response.status_code,
                status_response.text
            )

            status_response.raise_for_status()

            status = status_response.json()

            status_code = status.get("status_code")
            status_text = status.get("status")

            print("Instagram status:", status_code, status_text)

            # Ready
            if status_code == "FINISHED":
                print("Media is ready for publishing.")
                break

            # Failed
            if status_code in ["ERROR", "EXPIRED"]:
                return {
                    "success": False,
                    "message": f"Instagram media processing failed: {status}"
                }

        else:
            return {
                "success": False,
                "message": "Instagram media was not ready after waiting."
            }

        # ==========================================
        # 3. PUBLISH
        # ==========================================

        publish_url = (
            f"https://graph.instagram.com/v23.0/"
            f"{ig_id}/media_publish"
        )

        publish_data = {
            "creation_id": creation_id,
            "access_token": token
        }

        response = requests.post(
            publish_url,
            data=publish_data,
            timeout=60
        )

        print("PUBLISH STATUS:", response.status_code)
        print("PUBLISH RESPONSE:", response.text)

        response.raise_for_status()

        result = response.json()

        return {
            "success": True,
            "instagram_media_id": result.get("id"),
            "message": "Image successfully published to Instagram"
        }

    except Exception as e:

        print("INSTAGRAM ERROR:", e)

        return {
            "success": False,
            "message": str(e)
        }
