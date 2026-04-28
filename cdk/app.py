import aws_cdk as cdk
from cdk_stack import WhatsappBotStack
from storage_stack import StorageStack
from ingestion_stack import IngestionStack

app = cdk.App()

# Storage layer (OpenSearch)
storage = StorageStack(app, "WhatsAppRAGStorage")

# Existing inference stack
inference = WhatsappBotStack(app, "WhatsappBotStack")

# New ingestion stack
ingestion = IngestionStack(
    app,
    "RAGIngestion",
    opensearch_domain=storage.opensearch_domain,  # Pass OpenSearch
)

# Set dependencies
ingestion.add_dependency(storage)

app.synth()
