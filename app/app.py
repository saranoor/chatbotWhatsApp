import json
import boto3
import httpx
import asyncio
import google.generativeai as genai
import os
from .memory import get_conversation_context, save_message, maybe_summarize

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

from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "documents")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION,
    "es",
    session_token=credentials.token,
)
opensearch = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)
# --- 2. Logic Functions ---

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


def search_relevant_chunks(query_text, top_k=5):
    """Embed query and search OpenSearch for relevant chunks"""
    # Embed the user query
    result = genai.embed_content(
        model="models/gemini-embedding-2",
        content=query_text,
        task_type="retrieval_query",  # note: query not document
    )
    query_vector = result["embedding"]

    # k-NN search
    response = opensearch.search(
        index=OPENSEARCH_INDEX,
        body={
            "size": top_k,
            "query": {
                "knn": {
                    "embedding_vector": {
                        "vector": query_vector,
                        "k": top_k,
                    }
                }
            },
            "_source": ["content", "metadata"],
        },
    )

    hits = response["hits"]["hits"]
    return [hit["_source"]["content"] for hit in hits]


# async def get_ai_answer(user_input):
#     try:
#         # 1. Retrieve relevant chunks
#         chunks = search_relevant_chunks(user_input)
#         context = "\n\n---\n\n".join(chunks)

#         # 2. Build prompt with context
#         grounded_prompt = f"""Use the following documents to answer the user's question.
#             If the answer isn't in the documents, say you don't have that information.

#             DOCUMENTS:
#             {context}

#             USER QUESTION:
#             {user_input}"""

#         model = genai.GenerativeModel(
#             "gemini-2.5-flash", system_instruction=f"TRAVEL_BOT_INSTRUCTIONS"
#         )
#         response = model.generate_content(grounded_prompt)
#         return response.text

#     except Exception as e:
#         print(f"Gemini API error: {e}")
#         return "Sorry, I couldn't process your request at the moment."


async def get_ai_answer(user_input: str, whatsapp_number: str):
    try:
        # 1. Retrieve relevant chunks
        chunks = search_relevant_chunks(user_input)
        context = "\n\n---\n\n".join(chunks)

        # 2. Load memory
        summary, raw_messages = get_conversation_context(whatsapp_number)

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in raw_messages[-20:]
        )

        # 3. Build prompt with context + memory
        grounded_prompt = f"""Use the following documents to answer the user's question.
            If the answer isn't in the documents, say you don't have that information.

            DOCUMENTS:
            {context}

            CONVERSATION SUMMARY (older history):
            {summary or 'None'}

            RECENT MESSAGES:
            {history_text}

            USER QUESTION:
            {user_input}"""

        model = genai.GenerativeModel(
            "gemini-2.5-flash", system_instruction=TRAVEL_BOT_INSTRUCTIONS
        )
        response = model.generate_content(grounded_prompt)
        answer = response.text

        # 4. Save new messages + maybe compress
        save_message(whatsapp_number, "user", user_input)
        save_message(whatsapp_number, "assistant", answer)
        await maybe_summarize(whatsapp_number, raw_messages, summary, model)

        return answer
    except Exception as e:
        print(f"Error in get_ai_answer: {e}")
        return "Sorry, I couldn't process your request at the moment."


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

            # this aysnc only beneficial for multiple messages in the batch, not for a single message, but we keep it for future scalability
            ai_response = await get_ai_answer(text, sender_id)
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
        # remember async/concurent processing of multiple messages in the batch
        tasks = [process_sqs_record(r) for r in event["Records"]]
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks))
        return {"statusCode": 200}

    # Default fallback
    return {"statusCode": 400, "body": "Unknown trigger"}
