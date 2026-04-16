from fastapi import FastAPI, Request, Response, Query
import httpx
import google.generativeai as genai
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Response
from pathlib import Path
import os
from dotenv import load_dotenv
from mangum import Mangum
import boto3

base_path = Path(__file__).resolve().parent
env_path = base_path / ".env"

load_dotenv(env_path)

secrets = boto3.client("secretsmanager")


def get_secret(name):
    response = secrets.get_secret_value(SecretId=name)
    return response["SecretString"]


# VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "whatsapp_webhook_123")
# WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
# PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

VERIFY_TOKEN = get_secret("verify_token")
WHATSAPP_TOKEN = get_secret("whatsapp_token")
PHONE_NUMBER_ID = get_secret("phone_number_id")
LLM_API_KEY = get_secret("llm_api_key")

genai.configure(api_key=LLM_API_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview")

app = FastAPI()


class DisableNgrokWarning(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response


app.add_middleware(DisableNgrokWarning)

handler = Mangum(app)


@app.get("/")
async def root():
    return {"status": "WhatsApp webhook server running"}


@app.get("/webhook")
async def verify(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        # CRITICAL: Must be plain text, NOT a JSON object
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def handle_message(request: Request):
    data = await request.json()

    # Extract the message and sender ID
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            sender_id = message["from"]
            text = message["text"]["body"]
            print(f"Received message from {sender_id}: {text}")
            # 1. SEND TEXT TO YOUR AI (OpenAI/Claude)
            ai_response = await get_ai_answer(text)

            # 2. SEND AI RESPONSE BACK TO WHATSAPP
            await send_whatsapp_message(sender_id, ai_response)

    except Exception as e:
        print(f"Error processing: {e}")

    return {"status": "ok"}


async def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    # why use async and not celery?
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"API Response Body: {response.json()}")

        return response.json()


async def get_ai_answer(user_input):
    # TODO: Replace this with actual API calls to your AI model
    prompt = f" Answer this: {user_input}"
    response = model.generate_content(prompt)
    return response.text
    print(f"Getting AI answer for: {user_input}")
    return f"AI says: You sent '{user_input}'"


# If running locally (optional)
if __name__ == "__main__":
    import uvicorn

    # uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    uvicorn.run(
        "app:app", host="0.0.0.0", port=8000, reload=True, reload_includes=["*.py"]
    )

    # TO DO: Add error handling, logging, and more robust AI integration!
