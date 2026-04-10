https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started

uvicorn chatbotEuroInc.app:app --reload

ngrok http 8000

# test GET /webhook
https://YOUR_NEW_URL.ngrok-free.app/webhook?hub.mode=subscribe&hub.verify_token=your_chosen_verify_token&hub.challenge=test1234

update the forwarding url to callback url 

## simulate Phone -> Meta -> ngrok -> Laptop | direct -> laptop
$body = @{
     entry = @(
         @{
             changes = @(
                 @{
                     value = @{
                         messages = @(
                             @{
                                 from = "14372309256"
                                 text = @{ body = "Hello AI!" }
                             }
                         )
                     }
                 }
             )
         }
     )
 } | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://127.0.0.1:8000/webhook" -Method Post -Body $body -ContentType "application/json"

# to generate token
# go to system user and click on Generate Token
https://business.facebook.com/latest/settings/system_users?business_id=4321133904829898&selected_user_id=61576695158815


# setup

## local without docker

## Local with docker

docker build -f Dockerfile.local -t app:local .
docker compose up # to run all services

# now go to ngrok contianer, open the port it is running and copy the forwarding url for eg and copy to META
https://developers.facebook.com/apps/
Got to your (Meta Developer console) -> app chatbotEuroInc -> app -> usecase -> cusotmize -> configuration
<!-- https://eurychoric-mitsuko-pseudomonoclinic.ngrok-free.dev --> +/webhook

# test the whatsApp messages

case 1: 42372309256 -> test id
case 2: other number -> test id ->> cant verify in test mode

# aws docker
docker build -f Dockerfile.aws -t myapp:aws .
docker compose up 

test this on github to test lambda-test by running test_lambda.py

curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
-d '{
    "resource": "/",
    "path": "/",
    "httpMethod": "GET",
    "requestContext": {},
    "multiValueQueryStringParameters": null,
    "queryStringParameters": null,
    "pathParameters": null,
    "stageVariables": null,
    "headers": {
        "Accept": "application/json"
    },
    "body": null,
    "isBase64Encoded": false
}'

# setup cloud infra

goto aws console
got AWS ECR -> create registry with default -> view commands
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 357457231130.dkr.ecr.us-east-1.amazonaws.com
aws configure * if not
# push image to aws
docker buildx build --provenance=false --platform linux/arm64 -t 357457231130.dkr.ecr.us-east-1.amazonaws.com/whatsapp-ai-bot:latest -f Dockerfile.aws --push .
...

# create lambda function

# create API Gateway
make sure logs are being logged in cloud watch

# update lambda permission
create lambda permission for API Gateway

# Goto Meta Developer Console
Got to your (Meta Developer console) -> app chatbotEuroInc -> app -> usecase -> cusotmize -> configuration

# troubleshoot
- check logs
- check route 
- manually trigger the webhook and see if it validates

# set env variable through AWS Secret manager

# allows lambda to access those env variable
lambda secrets policy -> attach policy to lambda role

# Grant Lambda Permission to Access Secrets
aws iam put-role-policy --role-name whatsapp-webhook-handler-role-m9poi2dt --policy-name SecretsAccess --policy-document file://secrets-policy.json

# if making changes to local how to manually push it to aws 
-build the image again

-docker buildx build \
  --provenance=false \
  --platform linux/arm64 \
  -t 357457231130.dkr.ecr.us-east-1.amazonaws.com/whatsapp-ai-bot:latest \
  -f Dockerfile.aws \
  --push .

-aws lambda update-function-code \
  --function-name whatsapp-webhook \
  --image-uri 357457231130.dkr.ecr.us-east-1.amazonaws.com/whatsapp-ai-bot:latest

- update lambda
aws lambda update-function-code \
  --function-name whatsapp-webhook \
  --image-uri 357457231130.dkr.ecr.us-east-1.amazonaws.com/whatsapp-ai-bot:latest

# Automate deployment to aws -> local to aws with CI/CD Github Action

# after CI/CD it is not replying back? debug the issue
- logs
    - 2026-04-10T11:50:10.408Z
INIT_REPORT Init Duration: 2.88 ms	Phase: invoke	Status: error	Error Type: Runtime.InvalidEntrypoint