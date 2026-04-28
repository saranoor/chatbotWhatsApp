from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_s3_notifications as s3n,
    aws_iam as iam,
    aws_bedrock as bedrock,
    RemovalPolicy,
    CfnOutput,
    Duration,
)
from constructs import Construct
import os


class IngestionStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # S3 Bucket
        bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
        )

        # IAM Role for Bedrock KB
        kb_role = iam.Role(
            self,
            "BedrockKBRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        )
        bucket.grant_read(kb_role)
        kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1"
                ],
            )
        )

        # Bedrock Knowledge Base
        knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name="company-knowledge-base",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn="arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1"
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=f"arn:aws:aoss:us-east-1:{self.account}:collection/bedrock-kb-collection",
                    vector_index_name="bedrock-kb-index",
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="bedrock-kb-vector",
                        text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        metadata_field="AMAZON_BEDROCK_METADATA",
                    ),
                ),
            ),
        )

        # Data Source
        data_source = bedrock.CfnDataSource(
            self,
            "DataSource",
            name="s3-documents",
            knowledge_base_id=knowledge_base.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=bucket.bucket_arn
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=500, overlap_percentage=10
                    ),
                )
            ),
        )

        # Lambda to trigger immediate sync
        dirname = os.path.dirname(__file__)
        sync_lambda = lambda_.Function(
            self,
            "SyncTrigger",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="main.lambda_handler",
            code=lambda_.Code.from_asset(
                os.path.join(dirname, "..", "app", "ingestion")
            ),
            timeout=Duration.minutes(2),
            environment={
                "KNOWLEDGE_BASE_ID": knowledge_base.attr_knowledge_base_id,
                "DATA_SOURCE_ID": data_source.attr_data_source_id,
            },
        )

        # Permissions for Lambda to trigger sync
        sync_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:StartIngestionJob"],
                resources=[knowledge_base.attr_knowledge_base_arn],
            )
        )

        # S3 trigger
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(sync_lambda)
        )

        # Outputs
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "KnowledgeBaseId", value=knowledge_base.attr_knowledge_base_id)
