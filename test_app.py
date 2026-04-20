import json
import pytest
from unittest.mock import AsyncMock, patch
from unittest.mock import patch, MagicMock
import os

# 1. Set dummy environment variables BEFORE importing app
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from app import app as app_module  # Assuming your file is named app.py

# ... rest of your tests
# --- Mock Data ---


@pytest.fixture
def api_gateway_get_event():
    """Simulates Meta's Verification Request"""
    return {
        "httpMethod": "GET",
        "queryStringParameters": {
            "hub.mode": "subscribe",
            "hub.verify_token": "whatsapp_webhook_123",
            "hub.challenge": "1158201444",
        },
    }


@pytest.fixture
def sqs_sns_event():
    """Simulates an SQS event containing an SNS-wrapped WhatsApp message"""
    meta_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "123456789", "text": {"body": "Hello AI!"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    sns_wrapper = {"Message": json.dumps(meta_payload)}
    return {"Records": [{"body": json.dumps(sns_wrapper)}]}


# --- Tests ---


@patch("app.app.get_secret")
def test_verify_webhook_success(mock_secret, api_gateway_get_event):
    """Test successful Meta verification"""
    mock_secret.return_value = "whatsapp_webhook_123"
    app_module.VERIFY_TOKEN = "whatsapp_webhook_123"  # Update global

    response = app_module.lambda_handler(api_gateway_get_event, None)

    assert response["statusCode"] == 200
    assert response["body"] == "1158201444"
    assert response["headers"]["Content-Type"] == "text/plain"


def test_verify_webhook_forbidden(api_gateway_get_event):
    """Test verification with wrong token"""
    app_module.VERIFY_TOKEN = "wrong_token"

    response = app_module.lambda_handler(api_gateway_get_event, None)

    assert response["statusCode"] == 403
    assert response["body"] == "Forbidden"


@pytest.mark.asyncio
@patch("app.app.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.app.get_ai_answer", new_callable=AsyncMock)
async def test_process_whatsapp_message(mock_ai, mock_send, sqs_sns_event):
    """Test the async processing of an SQS message"""
    # Setup mocks
    mock_ai.return_value = "AI Response"
    mock_send.return_value = {"status": "sent"}

    # Run the lambda_handler
    response = app_module.lambda_handler(sqs_sns_event, None)

    assert response["statusCode"] == 200
    mock_ai.assert_called_once_with("Hello AI!")
    mock_send.assert_called_once_with("123456789", "AI Response")


@patch("httpx.AsyncClient.post")
@pytest.mark.asyncio
async def test_send_whatsapp_api_call(mock_post):
    """Test the actual HTTP call to Meta Graph API"""
    # Mock the HTTP response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "messaging_product": "whatsapp",
        "contacts": [{"input": "to_num", "wa_id": "wa_id"}],
    }
    mock_post.return_value = mock_response

    app_module.PHONE_NUMBER_ID = "12345"
    app_module.WHATSAPP_TOKEN = "token"

    result = await app_module.send_whatsapp_message("123456789", "Test Message")

    assert "messaging_product" in result
    mock_post.assert_called_once()
