# AI-Based Document Summarization System

Upload a document, get an AI-generated summary.

**Flow:** Browser → API Gateway (`POST /upload-url`) → Lambda returns a presigned S3 URL → Browser uploads the file straight to **S3** → API Gateway (`POST /summarize`) → **Lambda** reads the file from S3 and sends it to **Amazon Bedrock** (Generative AI / NLP) → summary returned and the file is deleted.

```
frontend/   index.html, style.css, app.js, config.js   (HTML/CSS/JS)
backend/    app.py                                     (Lambda, Python 3.12)
template.yaml                                          (AWS SAM: S3 + API Gateway + Lambda + IAM)
```

## Deploy
1. **Enable a Bedrock model.** AWS Console → Bedrock → Model access → enable *Amazon Nova Lite* (or change `ModelId`, e.g. a Claude model your account has access to). Use a region where it's available (e.g. us-east-1).
2. Install the AWS CLI and SAM CLI, run `aws configure`.
3. From this folder:
   ```
   sam build
   sam deploy --guided      # accept defaults; note the region
   ```
4. Copy the `ApiUrl` output into `frontend/config.js`.
5. Run the frontend: `cd frontend && python -m http.server 8000` → open http://localhost:8000
   (To host it: upload `frontend/` to an S3 static site, CloudFront, or Amplify Hosting.)

## Notes
- Supported: PDF, DOCX, DOC, XLSX, XLS, TXT, MD, CSV, HTML, up to 4.5 MB (Bedrock limit).
- API Gateway HTTP APIs time out at 30 s, so very long documents may fail; use short/medium length for those.
- Security for production: restrict CORS `AllowedOrigins` to your site domain, add Cognito/API keys, and add rate limiting.
- Cleanup: `sam delete`.
