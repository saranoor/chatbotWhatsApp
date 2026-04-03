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
Got to your app chatbotEuroInc -> app -> usecase -> cusotmize -> configuration
<!-- https://eurychoric-mitsuko-pseudomonoclinic.ngrok-free.dev --> +/webhook