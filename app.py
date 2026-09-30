"""Lambda backend: issues S3 upload URLs and summarizes uploaded documents with Amazon Bedrock."""

import json
import os
import re
import uuid

import boto3
from botocore.config import Config


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

BUCKET = os.environ["BUCKET"]

AWS_REGION = os.environ.get(
    "AWS_REGION",
    "ap-southeast-1"
)

MODEL_ID = os.environ.get(
    "MODEL_ID",
    "apac.amazon.nova-lite-v1:0"
)


MAX_BYTES = 4_500_000

FORMATS = {
    "pdf",
    "txt",
    "md",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "html",
}

LENGTHS = {
    "short": "in 2-3 sentences",
    "medium": "in one paragraph followed by 4-6 key-point bullets",
    "detailed": (
        "in a structured summary with a short overview, "
        "key points, and any decisions, numbers or action items"
    ),
}


# ---------------------------------------------------------
# AWS Clients
# ---------------------------------------------------------

s3_config = Config(
    region_name=AWS_REGION,
    signature_version="s3v4",
    s3={
        "addressing_style": "virtual"
    }
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=s3_config
)

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION
)


# ---------------------------------------------------------
# API Response
# ---------------------------------------------------------

def reply(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


# ---------------------------------------------------------
# File Extension
# ---------------------------------------------------------

def ext_of(name):
    return (
        name.rsplit(".", 1)[-1].lower()
        if "." in name
        else ""
    )


# ---------------------------------------------------------
# Generate S3 Upload URL
# ---------------------------------------------------------

def upload_url(body):

    filename = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        body.get("filename", "")
    )

    if ext_of(filename) not in FORMATS:
        return reply(
            400,
            {
                "error": (
                    "Unsupported file type. Use: "
                    + ", ".join(sorted(FORMATS))
                )
            },
        )

    key = f"uploads/{uuid.uuid4().hex}/{filename}"

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
        },
        ExpiresIn=300,
        HttpMethod="PUT",
    )

    return reply(
        200,
        {
            "uploadUrl": url,
            "key": key,
        },
    )


# ---------------------------------------------------------
# Summarize Document
# ---------------------------------------------------------

def summarize(body):

    key = body.get("key", "")
    length = body.get("length", "medium")

    if not key.startswith("uploads/") or ".." in key:
        return reply(
            400,
            {
                "error": "Invalid file key."
            },
        )

    # Check file size
    head = s3.head_object(
        Bucket=BUCKET,
        Key=key
    )

    if head["ContentLength"] > MAX_BYTES:
        return reply(
            413,
            {
                "error": "File is larger than 4.5 MB."
            },
        )

    # Download document from S3
    data = s3.get_object(
        Bucket=BUCKET,
        Key=key
    )["Body"].read()

    filename = key.rsplit("/", 1)[-1]

    # Bedrock document name restrictions
    name = re.sub(
        r"\s+",
        " ",
        re.sub(
            r"[^A-Za-z0-9\-\(\)\[\] ]",
            " ",
            filename.rsplit(".", 1)[0],
        ),
    ).strip() or "document"

    # Prompt
    prompt = (
        f"Summarize the attached document "
        f"{LENGTHS.get(length, LENGTHS['medium'])}. "
        "Use only information from the document. "
        "Write plain text; use '- ' for bullets."
    )

    # Amazon Bedrock
    out = bedrock.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    },
                    {
                        "document": {
                            "format": ext_of(filename),
                            "name": name,
                            "source": {
                                "bytes": data
                            },
                        }
                    },
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 1000,
            "temperature": 0.3,
        },
    )

    summary = (
        out["output"]["message"]["content"][0]["text"]
    )

    # Delete document after processing
    s3.delete_object(
        Bucket=BUCKET,
        Key=key
    )

    return reply(
        200,
        {
            "summary": summary,
            "filename": filename,
        },
    )


# ---------------------------------------------------------
# Lambda Handler
# ---------------------------------------------------------

def handler(event, context):

    try:

        body = json.loads(
            event.get("body") or "{}"
        )

        route = event.get(
            "routeKey",
            ""
        )

        if route == "POST /upload-url":
            return upload_url(body)

        if route == "POST /summarize":
            return summarize(body)

        return reply(
            404,
            {
                "error": "Not found"
            },
        )

    except Exception as exc:

        print(
            "ERROR",
            repr(exc)
        )

        return reply(
            500,
            {
                "error": (
                    "Summarization failed: "
                    + str(exc)[:200]
                ),
            },
        )
    