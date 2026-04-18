import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# 1. Mock Boto3 Secrets Manager BEFORE importing the app
with patch("boto3.client") as mock_boto:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "test_secret_value"}
    mock_boto.return_value = mock_client

    # Now import your app
    from app.app import app, VERIFY_TOKEN

client = TestClient(app)


## Test 1: Webhook Verification (GET)
def test_webhook_verification_success():
    """Tests the WhatsApp handshake logic."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "test_secret_value",  # Matches the mocked secret
        "hub.challenge": "12345",
    }
    response = client.get("/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_verification_forbidden():
    """Tests failure when token is incorrect."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "12345",
    }
    response = client.get("/webhook", params=params)
    assert response.status_code == 403


## Test 2: Message Handling (POST)
@patch("app.app.send_whatsapp_message")
@patch("app.app.get_ai_answer")
def test_handle_message_flow(mock_ai, mock_whatsapp):
    """Tests the full flow: Receive -> AI -> WhatsApp Reply."""
    # Setup mocks
    mock_ai.return_value = "AI says: Hello"
    mock_whatsapp.return_value = {"status": "success"}

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "123456789", "text": {"body": "Hi there"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify the AI was called with the right text
    mock_ai.assert_called_once_with("Hi there")
    # Verify WhatsApp reply was sent to the right person
    mock_whatsapp.assert_called_once_with("123456789", "AI says: Hello")
