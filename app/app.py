import json
import boto3
import httpx
import asyncio

# --- 1. Initialization (Outside the handler for performance) ---
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

# --- 2. Logic Functions ---


async def get_ai_answer(user_input):
    """Your AI model logic"""
    print(f"AI Thinking about: {user_input}")
    return f"AI Response to: {user_input}"


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
