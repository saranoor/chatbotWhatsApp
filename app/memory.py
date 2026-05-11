import boto3
import time
from datetime import datetime

dynamodb = boto3.resource("dynamodb", region_name="your-region")
table = dynamodb.Table("whatsapp-chat-history")

RAW_WINDOW = 20  # max raw messages to keep


# ─── Read ────────────────────────────────────────────────────────────────────


def get_conversation_context(whatsapp_number: str) -> tuple[str, list[dict]]:
    """Returns (summary_text, raw_messages_list)"""

    # Fetch all items for this user, sorted by timestamp
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("whatsapp_number").eq(
            whatsapp_number
        ),
        ScanIndexForward=True,  # oldest first
    )
    items = response.get("Items", [])

    summary_text = ""
    raw_messages = []

    for item in items:
        if item.get("type") == "summary":
            summary_text = item.get("content", "")
        else:
            raw_messages.append(item)

    return summary_text, raw_messages


# ─── Write ───────────────────────────────────────────────────────────────────


def save_message(whatsapp_number: str, role: str, content: str):
    """Save a single user/assistant message."""
    table.put_item(
        Item={
            "whatsapp_number": whatsapp_number,
            "timestamp": str(time.time()),
            "type": "message",
            "role": role,  # 'user' or 'assistant'
            "content": content,
        }
    )


def save_summary(whatsapp_number: str, summary: str):
    """Overwrite the rolling summary (fixed sort key)."""
    table.put_item(
        Item={
            "whatsapp_number": whatsapp_number,
            "timestamp": "0000000000_summary",  # fixed key so it's always overwritten
            "type": "summary",
            "content": summary,
        }
    )


def delete_old_messages(whatsapp_number: str, messages_to_delete: list[dict]):
    """Delete raw messages that were rolled into the summary."""
    with table.batch_writer() as batch:
        for msg in messages_to_delete:
            batch.delete_item(
                Key={
                    "whatsapp_number": msg["whatsapp_number"],
                    "timestamp": msg["timestamp"],
                }
            )


# ─── Summarize ───────────────────────────────────────────────────────────────


async def maybe_summarize(
    whatsapp_number: str, raw_messages: list[dict], existing_summary: str, model
):
    """Re-summarize and prune only when raw window overflows."""

    if len(raw_messages) <= RAW_WINDOW:
        return  # nothing to do

    messages_to_summarize = raw_messages[:-10]  # keep last 10 raw, summarize the rest

    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages_to_summarize
    )

    prompt = f"""You are summarizing a WhatsApp conversation for memory compression.

EXISTING SUMMARY:
{existing_summary or 'None'}

NEW MESSAGES TO ADD TO SUMMARY:
{history_text}

Write a concise updated summary capturing key facts, preferences, and decisions."""

    response = model.generate_content(prompt)
    new_summary = response.text

    save_summary(whatsapp_number, new_summary)
    delete_old_messages(whatsapp_number, messages_to_summarize)
