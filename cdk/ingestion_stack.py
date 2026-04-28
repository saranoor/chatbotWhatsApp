from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_s3_notifications as s3n,
    aws_iam as iam,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class IngestionStack(Stack):
    def __init__(self, scope, construct_id, opensearch_domain, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket
        bucket = s3.Bucket(self, "DocumentsBucket", removal_policy=RemovalPolicy.RETAIN)

        # Lambda
        processor = lambda_.Function(
            self,
            "Processor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="main.lambda_handler",
            code=lambda_.Code.from_asset("app/ingestion"),
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_domain.domain_endpoint,
                "OPENSEARCH_INDEX": "documents",
                "CHUNK_SIZE": "500",
                "CHUNK_OVERLAP": "50",
            },
        )

        # Permissions
        bucket.grant_read(processor)
        opensearch_domain.grant_index_read_write("documents", processor)
        processor.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=["*"])
        )

        # S3 Trigger
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(processor)
        )

        self.bucket = bucket
