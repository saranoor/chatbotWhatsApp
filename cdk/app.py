import aws_cdk as cdk
from cdk_stack import WhatsappBotStack
from storage_stack import StorageStack
from ingestion_stack import IngestionStack

app = cdk.App()

inference = WhatsappBotStack(app, "WhatsappBotStack")

ingestion = IngestionStack(app, "RAGIngestion")

app.synth()
