import os
import pymupdf
import pandas as pd
from docx import Document
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
import shutil
import tiktoken
import uvicorn
import json
import random
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Allowed origins (Adjust as needed)
origins = [
    "http://localhost:3000",
    "https://yourfrontend.com",
]

# Define constants
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB upload file size limit
MAX_TOKEN_SIZE = 10000  # 10k input tokens limit
RATE_LIMIT = "10/minute"  # Rate limit: 5 requests per minute

app = FastAPI()
limiter = Limiter(key_func=get_remote_address)


# Add rate limit exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429, content={"error": "Too many requests. Try again later."}
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allow specific origins
    allow_credentials=True,  # Allow cookies & authentication headers
    allow_methods=["GET", "POST"],  # Allowed methods
    allow_headers=["*"],  # Allow all headers
)


# count tokens of dataset
def count_tokens(text, model="gpt-4o-mini"):
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)


# extract text from files
def dataset_create(filename):
    extension = os.path.splitext(filename)[1].lower()
    text = None

    # PDF
    if extension == ".pdf":
        doc = pymupdf.open(filename)
        text = "\n".join([page.get_text() for page in doc])
        text = {"data": text}

    # Word file
    elif extension == ".docx" or extension == ".doc":
        doc = Document(filename)
        text = [para.text for para in doc.paragraphs if para.text.strip()]
        text = {"data": text}

    # CSV or Excel file
    elif extension == ".csv" or extension == ".xls" or extension == ".xlsx":
        if extension == ".csv":
            df = pd.read_csv(filename)
        else:
            df = pd.read_excel(filename)
        text = df.to_json(orient="records")
        text = json.loads(text)

    # Text file
    elif extension == ".txt" or extension == ".md":
        with open(filename, "r", encoding="utf-8") as file:
            text = file.read()
            text = text.replace("\t", "")
        text = {"data": text}

    # JSON file
    elif extension == ".json":
        with open(filename, "r", encoding="utf-8") as file:
            text = json.load(file)

    return text


# generate unique filename
def generate_unique_filename(filename):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_number = random.randint(10000, 99999)
    ext = filename.split(".")[-1]
    return f"{timestamp}_{random_number}.{ext}"


# Upload files for data extraction at http://localhost:8000/upload
@app.post("/upload")
@limiter.limit(RATE_LIMIT)
async def upload_files(request: Request, files: list[UploadFile] = File(...)):
    dataset = []

    for file in files:
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size limit exceeded: > {file.filename}",
            )
        unique_filename = generate_unique_filename(file.filename)
        file_location = os.path.join(UPLOAD_DIR, unique_filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        dataset_file = dataset_create(file_location)
        if dataset_file != None:
            dataset.append(dataset_file)

    token_size = count_tokens(str(dataset))
    if token_size > MAX_TOKEN_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Token size: {token_size} - Max token limit exceeded",
        )
    return {"dataset": dataset, "token_size": token_size}  # Return the extracted data


# Run the app and listen on port 8000
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
