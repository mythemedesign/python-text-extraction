# Python Text Extraction & Web Scraping

This script sets up a FastAPI application to handle file uploads and extract text data from various file formats and also scrape web pages and grab links of related pages.

Supported file types: `pdf`, `txt`, `md`, `xls`, `xlsx`, `csv`, `json`, `doc`, `docx`

It includes rate limiting, CORS middleware, and token counting for the uploaded data.

## Constants:

`UPLOAD_DIR (str)`: Directory to store uploaded files.

`MAX_FILE_SIZE (int)`: Maximum allowed file size for uploads (10MB).

`MAX_TOKEN_SIZE (int)`: Maximum allowed token size for input data (10,000 tokens).

`RATE_LIMIT (str)`: Rate limit for requests (10 requests per minute).

`MAX_PAGES_TO_FETCH (int)`: Maximum number of pages to fetch (20 pages)

## Setup:

To set up and run the FastAPI application for file extraction, follow these steps:
---
### 1. Clone the Repository

First, clone the repository to your local machine:

```
git clone <repository_url>
cd <repository_directory>
```
---
### 2. Create a Virtual Environment

Create a virtual environment to manage dependencies:

```
python3 -m venv .venv
source .venv/bin/activate
# On Windows, use `.venv\Scripts\activate`
```
---
### 3. Install Dependencies

Install the required dependencies using pip:

```
pip install -r requirements.txt
```
---
### 4. Run the Application

Run the FastAPI application using uvicorn:

```
uvicorn main:app --reload
```

> This will start the server on http://127.0.0.1:8000.

---
### 5. Test the Application

#### - Text Extraction

Send POST request to

`http://127.0.0.1:8000/extract-data`

(multiple files could be uploaded at once)

> return extracted data and token size

---

#### - Related Links

Send POST request to

`http://127.0.0.1:8000/web-links`

```
{ "url" : "https://example.com" }
```

> return all links from the url

---

#### - Web Scraping

Send POST request to

`http://127.0.0.1:8000/web-scrape`

```
{ "url" : "https://example.com/page" }
```

> return extracted data from the scraped url
