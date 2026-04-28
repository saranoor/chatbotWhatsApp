"""
Triggers Bedrock Knowledge Base sync when file uploaded to S3
"""

import boto3
import os

bedrock_agent = boto3.client("bedrock-agent", region_name="us-east-1")

KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
DATA_SOURCE_ID = os.environ["DATA_SOURCE_ID"]


def lambda_handler(event, context):
    """Trigger Knowledge Base sync when S3 file uploaded"""

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        print(f"New file uploaded: s3://{bucket}/{key}")

        # Trigger immediate sync
        try:
            response = bedrock_agent.start_ingestion_job(
                knowledgeBaseId=KNOWLEDGE_BASE_ID, dataSourceId=DATA_SOURCE_ID
            )

            print(f"Sync started: {response['ingestionJob']['ingestionJobId']}")

        except Exception as e:
            print(f"Error starting sync: {str(e)}")
            raise

    return {"statusCode": 200, "body": "Sync triggered"}
