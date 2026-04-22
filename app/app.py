import json
import boto3
import httpx
import asyncio
import google.generativeai as genai
import os

# --- 1. Initialization (Outside the lambda_handler for performance) ---
secrets = boto3.client("secretsmanager")


def get_secret(name):
    try:
        response = secrets.get_secret_value(SecretId=name)
        return response["SecretString"]
    except Exception as e:
        print(f"Error fetching secret {name}: {e}")
        return None


# Load secrets once
VERIFY_TOKEN = get_secret("verify_token")
WHATSAPP_TOKEN = get_secret("whatsapp_token")
PHONE_NUMBER_ID = get_secret("phone_number_id")

# 1. Fetch the secret
raw_secret = get_secret("llm_api_key")

# 2. Check if it's a string (JSON) and convert to dict if needed
if isinstance(raw_secret, str):
    try:
        raw_secret = json.loads(raw_secret)
    except json.JSONDecodeError:
        GEMINI_API_KEY = raw_secret
        raw_secret = None

# 3. Safely extract the key
if isinstance(raw_secret, dict):
    GEMINI_API_KEY = raw_secret.get("llm_api_key", "dummy_key")
else:
    # If GEMINI_API_KEY wasn't set in the string check above
    GEMINI_API_KEY = raw_secret if raw_secret else "dummy_key"

genai.configure(api_key=GEMINI_API_KEY)

# --- 2. Logic Functions ---


async def get_ai_answer(user_input):
    """Gemini AI model logic"""
    try:
        print(f"AI Thinking about: {user_input}")
        TRAVEL_BOT_INSTRUCTIONS = """You are the official AI assistant for 'EuroTravel Connect'. 
            You specialize in European travel, helping tourists and passengers with:
            - Travel routes across Europe.
            - Bus and coach information (schedules, arrivals, and departures).
            - Ticket information: costs, types, and buying methods.

            RULES & GUARDRAILS:
            1. GEOGRAPHIC LIMIT: Only provide information regarding travel within Europe. 
            If asked about travel in other continents (e.g., USA, Asia), politely 
            inform the user that you only specialize in European routes.
            2. TICKET SAFETY: Explain that tickets can be bought via our official website 
            or at station kiosks. NEVER ask for or accept credit card numbers or 
            personal payment details in this chat.
            3. REAL-TIME DATA: If you do not have specific real-time data for a delay, 
            instruct the user to check the 'Live Board' at the station.
            4. TONE: Be professional, helpful, and concise. Use the 24-hour clock (e.g., 15:30) 
            for all time-related queries.
            5. GREETING: Only provide a formal greeting (e.g., "Hello! How can I help you today?") if the user says "Hello" or it is the very start of the chat.
            6. CONTEXT: If the user is continuing a conversation, respond directly to their question without re-introducing yourself or mentioning specific routes like 'Berlin to France' unless the user asked for them.
            7. FOCUS: European travel only (routes, bus times, ticket prices, buying methods).
            8. GUARDRAILS: Never ask for credit card info. Redirect non-European queries politely.
            """

        # Initialize Gemini model
        model = genai.GenerativeModel(
            "gemini-3-flash-preview", system_instruction=TRAVEL_BOT_INSTRUCTIONS
        )

        # Generate response
        response = model.generate_content(user_input)

        return response.text

    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"Sorry, I couldn't process your request at the moment. I will get back to you as soon as possible."


async def send_whatsapp_message(to, text):
    """Meta Graph API call"""
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        return response.json()


async def process_sqs_record(record):
    """Logic for processing a single message from the queue"""
    sqs_body = json.loads(record["body"])
    # Extract the SNS 'Message' string, then parse that JSON
    meta_payload = json.loads(sqs_body["Message"])

    try:
        entry = meta_payload["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            sender_id = message["from"]
            text = message["text"]["body"]

            ai_response = await get_ai_answer(text)
            await send_whatsapp_message(sender_id, ai_response)
    except KeyError as e:
        print(f"Missing expected key in payload: {e}")


# --- 3. The Main Entry Point ---


def lambda_handler(event, context):
    # PATH A: Triggered by API Gateway (The GET Verification)
    if "queryStringParameters" in event and event.get("httpMethod") == "GET":
        params = event["queryStringParameters"]
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/plain"},
                "body": challenge,
            }
        return {"statusCode": 403, "body": "Forbidden"}

    # PATH B: Triggered by SQS (The POST Processing)
    elif "Records" in event:
        loop = asyncio.get_event_loop()
        tasks = [process_sqs_record(r) for r in event["Records"]]
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks))
        return {"statusCode": 200}

    # Default fallback
    return {"statusCode": 400, "body": "Unknown trigger"}
