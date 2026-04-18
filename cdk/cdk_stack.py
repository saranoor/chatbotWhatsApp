from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_sqs as sqs,
    aws_lambda_event_sources as events,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    aws_ecr as ecr,
    Duration,
)
from constructs import Construct
import os


class WhatsappBotStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Reference existing ECR Repository created by your workflow
        repo = ecr.Repository.from_repository_name(
            self, "WhatsappBotRepo", repository_name="whatsapp-ai-bot"
        )

        # Use the github.sha if passed via context, otherwise fallback to latest
        image_tag = self.node.try_get_context("image_tag") or "latest"

        # 2. SQS & SNS Setup
        queue = sqs.Queue(
            self, "WhatsappQueue", visibility_timeout=Duration.seconds(30)
        )
        topic = sns.Topic(self, "WhatsappTopic")
        topic.add_subscription(subs.SqsSubscription(queue))

        # 3. Lambda Function from ECR
        handler = _lambda.DockerImageFunction(
            self,
            "WhatsappHandler",
            function_name="whatsapp-bot-handler",  # Matches your deploy.yml
            code=_lambda.DockerImageCode.from_ecr(
                repository=repo, tag_or_digest=image_tag
            ),
            timeout=Duration.seconds(30),
            memory_size=512,
        )

        # 4. Permissions for Secrets Manager
        # Note: Use the secret name you created in the console
        # List of your secret names from the console
        secret_names = [
            "llm_api_key",
            "phone_number_id",
            "whatsapp_token",
            "verify_token",
        ]

        for name in secret_names:
            sec = secretsmanager.Secret.from_secret_name_v2(
                self, f"Secret-{name}", name
            )
            sec.grant_read(handler)

        # 5. SQS Event Source
        handler.add_event_source(events.SqsEventSource(queue))

        # 6. API Gateway Setup
        api = apigw.RestApi(
            self,
            "WhatsappApi",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
        )

        webhook_res = api.root.add_resource("webhook")

        # --- GET Method: Direct to Lambda (For Meta Verification) ---
        webhook_res.add_method("GET", apigw.LambdaIntegration(handler))

        # --- POST Method: SNS -> SQS (For Processing Messages) ---
        api_gw_role = iam.Role(
            self,
            "ApiGwRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        topic.grant_publish(api_gw_role)

        api_gateway_cloudwatch_role = iam.Role(
            self,
            "ApiGatewayCloudWatchRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonAPIGatewayPushToCloudWatchLogs"
                )
            ],
        )
        apigw.CfnAccount(
            self,
            "ApiGatewayAccount",
            cloud_watch_role_arn=api_gateway_cloudwatch_role.role_arn,
        )
        sns_integration = apigw.AwsIntegration(
            service="sns",
            action="Publish",
            options=apigw.IntegrationOptions(
                credentials_role=api_gw_role,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-www-form-urlencoded'"
                },
                request_templates={
                    "application/json": (
                        "Action=Publish&"
                        f"TopicArn=$util.urlEncode('{topic.topic_arn}')&"
                        "Message=$util.urlEncode($input.body)"
                    )
                },
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200", response_templates={"application/json": ""}
                    )
                ],
            ),
        )

        webhook_res.add_method(
            "POST",
            sns_integration,
            method_responses=[apigw.MethodResponse(status_code="200")],
        )
