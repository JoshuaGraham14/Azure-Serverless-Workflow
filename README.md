# Azure Serverless Workflow: BBC News Scraping and Sentiment Analysis

## Overview
This project demonstrates a serverless architecture using Azure Functions to scrape BBC News articles, perform sentiment analysis, and store results in Azure Blob Storage. Additionally, it includes a scalability testing function for generating mock articles.

---

## Architecture

### 1. Timer Trigger Function
- Scrapes live articles from the BBC News homepage every hour.
- Saves each article (title, content, URL) as a JSON file in the `articles-data` Blob Storage container.

### 2. Blob Trigger Function
- Detects new articles in the `articles-data` container.
- Performs sentiment analysis on the article content using `TextBlob`.
- Appends the results to the article data and saves it in the `articles-sentiment` container.

### 3. HTTP Trigger Function
- Generates mock articles for scalability testing.
- Uploads these fake articles to the `articles-data` container.

---

## Prerequisites

1. **Azure Function App**:
   - Deploy and configure for Python.
2. **Azure Blob Storage**:
   - Create containers `articles-data` and `articles-sentiment`.
   - Add the `BLOB_CONNECTION_STRING` environment variable in `local.settings.json`.
3. **Python Dependencies**:
   - Install required libraries from the requirements.txt.

---