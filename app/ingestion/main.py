"""
Document Ingestion Lambda - Single File
Triggered by S3 upload events
"""

import json
import os
import boto3
from io import BytesIO
from datetime import datetime

# AWS Clients
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")

# OpenSearch client
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Configuration
OPENSEARCH_ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"]
OPENSEARCH_INDEX = os.environ.get("OPENSEARCH_INDEX", "documents")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize OpenSearch
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION,
    "es",
    session_token=credentials.token,
)

opensearch = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)


def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            print(f"Processing: s3://{bucket}/{key}")

            # Download file
            file_obj = s3.get_object(Bucket=bucket, Key=key)
            file_content = file_obj["Body"].read()

            # Extract text
            text = extract_text(key, file_content)
            if not text:
                print(f"No text extracted from {key}")
                continue

            # Chunk
            chunks = chunk_text(text)
            print(f"Created {len(chunks)} chunks")

            # Generate embeddings and index
            index_chunks(chunks, bucket, key)
            print(f"Successfully indexed {len(chunks)} chunks")

        return {"statusCode": 200, "body": json.dumps("Success")}

    except Exception as e:
        print(f"Error: {str(e)}")
        raise


def extract_text(filename, content):
    """Extract text from different file types"""

    # PDF
    if filename.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader

            pdf_file = BytesIO(content)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return None

    # Word Document
    elif filename.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            print(f"DOCX extraction error: {e}")
            return None

    # Plain text
    elif filename.endswith(".txt"):
        return content.decode("utf-8")

    else:
        print(f"Unsupported file type: {filename}")
        return None


def chunk_text(text):
    """Split text into overlapping chunks"""
    # Simple character-based chunking
    chars_per_chunk = CHUNK_SIZE * 4  # ~4 chars per token
    overlap_chars = CHUNK_OVERLAP * 4

    chunks = []
    start = 0

    while start < len(text):
        end = start + chars_per_chunk
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(".")
            if last_period > chars_per_chunk * 0.7:
                end = start + last_period + 1
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end - overlap_chars

    return chunks


def generate_embedding(text):
    """Generate embedding using Bedrock"""
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1", body=json.dumps({"inputText": text})
    )

    response_body = json.loads(response["body"].read())
    return response_body["embedding"]


def index_chunks(chunks, bucket, key):
    """Generate embeddings and index to OpenSearch"""
    from opensearchpy import helpers

    # Prepare bulk actions
    actions = []

    for i, chunk in enumerate(chunks):
        # Generate embedding
        embedding = generate_embedding(chunk)

        # Prepare document
        doc = {
            "_index": OPENSEARCH_INDEX,
            "_source": {
                "content": chunk,
                "embedding_vector": embedding,
                "metadata": {
                    "source_file": key,
                    "bucket": bucket,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "upload_date": datetime.utcnow().isoformat(),
                    "file_type": key.split(".")[-1],
                },
            },
        }
        actions.append(doc)

    # Bulk index
    helpers.bulk(opensearch, actions)
