# Project Name

## Problem

To create a RAG based chatbot to answer customer questions on whatsapp. 
## Proposed Solution
The proposed solution is to use whatsapp META Developer API to interact with user. 
Utilized an AI model with guardrails to answer customer/user questions.

## Architectural Diagram

## DEMO 

## Setup

### Cloud Setup

Follow these steps to deploy and run the project in a cloud environment:

1. **Prerequisites**
   - WhatsAPP META API setup https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started
    - create a new META APP in whatsapp
    - Start using the whatsapp META API
    - Send and receieve message on your business number
   - AWS access (must have access to aws account)

2. **Configuration**
   - Set up environment variables in local or configure them in cloud using AWS secret manager

   - AWS Resource creation and configure in cloud services will be done using cdk_stack.py
   
3. **Deployment**
   - make sure aws access key and secret are set in github
   - push code to github
   - deploy.yml will automatically do the following
        - install dependencies
        - run unit test cases
        - log in to aws
        - deploy.yml will create an image and push it to AWS ECR
        - deploy infrastructure
        - update lambda function with the new image
    - may need to enable logs manually if aws xray are not active
   
4. **Verification**
   - How to verify the deployment was successful
        - send a message to your business number and see if you recieve response back
   - Where to find logs or monitoring
        - checks log groups and xray

### Local Setup

Follow these steps to run the project on your local machine:
    ## TODO: update later

## Challenges:
    # TOD0: add technical challenges
## Design Document
    # TODO: add link to design documents