import requests
import json

# The local address of your lambda-test container
URL = "http://localhost:9000/2015-03-31/functions/function/invocations"


def test_webhook():
    # 1. This is the exact JSON structure your FastAPI code expects from WhatsApp
    whatsapp_data = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "text": {"body": "Hello from my test script!"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    # 2. This is the "Envelope" Mangum needs to not crash
    payload = {
        "version": "2.0",
        "rawPath": "/webhook",
        "requestContext": {
            "http": {"method": "POST", "path": "/webhook", "sourceIp": "127.0.0.1"}
        },
        "headers": {"content-type": "application/json"},
        "body": json.dumps(whatsapp_data),  # Must be a string!
        "isBase64Encoded": False,
    }

    # 3. Send it to the container
    print("Sending test request to Lambda container...")
    response = requests.post(URL, json=payload)

    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    test_webhook()
