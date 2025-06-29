def generate_image(prompt):
    import requests
    import os

    api_key = os.getenv("RUNWARE_API_KEY")
    url = "https://api.runware.ai/v1/generate"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "width": 512,
        "height": 512,
        "steps": 25,
        "guidance_scale": 7
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("image_url")
    except Exception as e:
        print("❌ Runware error:", e)
        print(response.text)
        return None
