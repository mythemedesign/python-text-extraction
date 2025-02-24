import os
import pymupdf
import pandas as pd
from docx import Document
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Body
import shutil
import tiktoken
import uvicorn
import json
import random
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# from slowapi import Limiter
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded
# from starlette.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware

# Allowed origins (Adjust as needed)
# origins = [
#     "http://localhost:3000",
#     "https://yourfrontend.com",
# ]

# Define constants
UPLOAD_DIR = "uploads"
SAVE_DATASET_DIR = "save_dataset"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB upload file size limit
MAX_TOKEN_SIZE = 10000  # 10k input tokens limit
# RATE_LIMIT = "10/minute"  # Rate limit: 5 requests per minute
MAX_PAGES_TO_FETCH = 20  # Maximum number of pages to fetch
HEADERS_WEB_SCRAPE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}
app = FastAPI()
# limiter = Limiter(key_func=get_remote_address)

# Add rate limit exception handler
# @app.exception_handler(RateLimitExceeded)
# async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
#     return JSONResponse(
#         status_code=429, content={"error": "Too many requests. Try again later."}
#     )


# Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,  # Allow specific origins
#     allow_credentials=True,  # Allow cookies & authentication headers
#     allow_methods=["GET", "POST"],  # Allowed methods
#     allow_headers=["*"],  # Allow all headers
# )


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
    random_number = random.randint(1000000, 9999999)
    ext = filename.split(".")[-1]
    return f"{timestamp}_{random_number}.{ext}"


@app.post("/extract-data")
# @limiter.limit(RATE_LIMIT)
async def upload_files(request: Request, files: list[UploadFile] = File(...)):
    try:
        dataset = []
        if files[0].filename == "":
            raise HTTPException(
                status_code=413,
                detail="No files uploaded.",
            )

        for file in files:
            if file.size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size limit exceeded: > {file.filename}",
                )
            unique_filename = generate_unique_filename(file.filename)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            file_location = os.path.join(UPLOAD_DIR, unique_filename)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            dataset_file = dataset_create(file_location)
            if dataset_file != None:
                dataset.append(dataset_file)

        # count tokens of dataset
        token_size = count_tokens(str(dataset))
        if token_size > MAX_TOKEN_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Max token size limit exceeded! - Token size: {token_size}",
            )

        # save dataset to file
        unique_filename = generate_unique_filename("dataset.json")
        os.makedirs(SAVE_DATASET_DIR, exist_ok=True)
        file_path = os.path.join(SAVE_DATASET_DIR, unique_filename)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(str(dataset))

        return {
            "message": "Data extracted successfully into file.",
            "file_name": unique_filename,
            "token_size": token_size,
        }

    except Exception as e:
        raise HTTPException(
            status_code=413,
            detail=f"Failed to extract data from files: {e}",
        )


@app.post("/web-links")
# @limiter.limit(RATE_LIMIT)
async def web_links(request: Request, body: dict[str, str] = Body(...)):
    # request example
    # { "url" : "https://example.com" }

    try:
        url = body["url"]
        if not url.startswith("http"):
            url = f"http://{url}"
        visited_urls = set()
        response = requests.get(url, headers=HEADERS_WEB_SCRAPE)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        urls_list = set()
        urls_list.add(url)

        # Find all links on the page and fetch them
        for link in soup.find_all("a", href=True):
            next_url = link["href"]
            if next_url.endswith("/"):
                next_url = next_url[:-1]
            if "#" in next_url:
                next_url = next_url.split("#")[0]
            if not next_url.startswith("http"):
                next_url = requests.compat.urljoin(url, next_url)
            if next_url.startswith("http://www.") or next_url.startswith(
                "https://www."
            ):
                next_url = next_url.replace("www.", "")
            if next_url.startswith(url) and next_url not in visited_urls:
                urls_list.add(next_url)
            # Limit the number of pages to fetch
            if len(urls_list) >= MAX_PAGES_TO_FETCH:
                break

        links_data = []
        for url in urls_list:
            data = {}
            response = requests.get(url, headers=HEADERS_WEB_SCRAPE)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            if soup.title:
                data["title"] = soup.title.string.strip()
            else:
                data["title"] = "No title"
            data["link"] = url
            links_data.append(data)

        return links_data

    except Exception as e:
        raise HTTPException(
            status_code=413,
            detail=f"Failed to fetch {url}: {e}",
        )


@app.post("/web-scrape")
# @limiter.limit(RATE_LIMIT)
async def web_scrape(request: Request, body: dict[str, str] = Body(...)):
    # request example
    # { "url" : "https://example.com/page" }

    try:
        url = body["url"]
        if not url.startswith("http"):
            url = f"http://{url}"
        response = requests.get(url, headers=HEADERS_WEB_SCRAPE)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        data = {}

        # Find and remove useless links
        useless_texts = [
            "read more",
            "click here",
            "continue reading",
            "learn more",
            "share",
            "comment",
            "reply",
            "subscribe",
            "previous",
            "next",
            "back",
            "return",
            "continue",
            "more",
            "download",
            "get",
            "buy",
            "purchase",
            "order",
            "shop",
            "add to cart",
            "add to basket",
            "checkout",
            "sign up",
            "log in",
            "login",
            "register",
            "profile",
            "account",
            "settings",
            "edit",
            "delete",
            "remove",
            "قبلی",
            "بعدی",
            "بازگشت",
            "ادامه",
            "نظر بدهید",
            "لغو پاسخ",
            "بیشتر بخوانید",
            "ادامه مطلب",
            "پاسخ",
            "دریافت",
            "دانلود",
            "اشتراک گذاری",
            "خرید",
            "سفارش",
            "افزودن به سبد خرید",
            "ورود",
            "ثبت نام",
            "پروفایل",
            "تنظیمات",
            "ویرایش",
            "حذف",
            "خروج",
        ]
        for a_tag in soup.find_all("a"):
            if any(
                text in a_tag.get_text(strip=True).lower() for text in useless_texts
            ):
                a_tag.decompose()

        # set title
        if soup.title:
            data["title"] = soup.title.string.strip()

        # set headings
        headings = []
        for h in soup.find_all(["h1", "h2", "h3"]):
            headings.append(h.get_text(strip=True))
        data["headings"] = headings

        # remove duplicate title
        tag_title = soup.title
        tag_title.decompose()

        # set tables
        json_output = []
        table_tags = soup.find_all("table")
        if len(table_tags) > 0:
            for index, table in enumerate(table_tags):
                print(f"Table {index+1}:")
                table_full = []

                table_headers = []
                for header in table.find_all("th"):
                    table_headers.append(header.get_text(strip=True))

                for row in table.find_all("tr")[1:]:  # Skip header row
                    cells = row.find_all("td")
                    row_data = {
                        table_headers[i]: cells[i].get_text(strip=True)
                        for i in range(len(cells))
                    }
                    table_full.append(row_data)

                json_output.append(table_full)
            data["tables"] = json_output

        # Remove unwanted tags
        for tag in soup.find_all(
            [
                "nav",
                "aside",
                "footer",
                "script",
                "style",
                "form",
                "button",
                "i",
                "table",
            ]
        ):
            tag.decompose()
        # set content
        data["content"] = soup.get_text(separator="\n", strip=True)

        # count tokens of dataset
        token_size = count_tokens(str(data))
        if token_size > MAX_TOKEN_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Token size: {token_size} - Max token limit exceeded",
            )

        # save dataset to file
        unique_filename = generate_unique_filename("dataset.json")
        os.makedirs(SAVE_DATASET_DIR, exist_ok=True)
        file_path = os.path.join(SAVE_DATASET_DIR, unique_filename)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(str(data))

        return {
            "message": "Data fetched successfully and inserted into file.",
            "file_name": unique_filename,
            "token_size": token_size,
        }

    except Exception as e:
        raise HTTPException(
            status_code=413,
            detail=f"Failed to fetch {url}: {e}",
        )


# Run the app and listen on port 8000
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
