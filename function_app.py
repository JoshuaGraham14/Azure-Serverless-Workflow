import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import json, os, time

BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")

app = func.FunctionApp()

'''
Function 1: Timer Trigger
Triggers periodically to fetch articles from the BBC news homepage, 
scraping the article's title and contents to a Blob container.
'''
# cron schedule for every hour (and when first run):
@app.timer_trigger(schedule="0 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    start_time = time.time()

    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info(f"Timer Trigger started at: {start_time:.3f}")

    fetch_live_articles()

    end_time = time.time()
    logging.info(f"Timer Trigger completed at: {end_time:.3f}")
    logging.info(f"Execution time for Timer Trigger: {end_time - start_time:.3f} seconds")

def fetch_live_articles():
    url = 'https://www.bbc.com/news'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching BBC News homepage: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    #Find all links on the page that start with '/news/live'
    articles = soup.find_all('a', href=lambda href: href and href.startswith('/news/articles'))

    article_links = set()
    for article in articles[:10]: #retrieve the first 10 articles
        href = article['href']
        full_url = f"https://www.bbc.com{href}" 
        article_links.add(full_url)

    #Process each article
    for link in article_links:
        process_article(link)

def process_article(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching article {url}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract title
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else 'No Title Found'

    # Extract article body
    article_body = soup.find('article')
    paragraphs = article_body.find_all('p') if article_body else []
    content = ' '.join(p.get_text(strip=True) for p in paragraphs)

    #rare case of empty article
    if not content:
        logging.warning(f"No content found for article {url}")
        return

    #place data into structued format
    article_data = {
        'title': title,
        'content': content,
        'url': url
    }

    # logging.info(f"Processed article: {article_data}")

    # Save to Blob
    blob_name = f"article-{title.replace(' ', '_')}.json"
    save_to_blob(article_data, blob_name)

def save_to_blob(data, blob_name):
    try:
        #Initialise BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

        #Get the articles-data container
        container_client = blob_service_client.get_container_client("articles-data")
        if not container_client.exists(): 
            #create container if doesn't exist
            container_client.create_container()

        #Upload the JSON data as a blob
        blob_client = container_client.get_blob_client(blob_name)
        blob_content = json.dumps(data, ensure_ascii=False, indent=4)
        blob_client.upload_blob(blob_content, overwrite=True)

        logging.info(f"Uploaded {blob_name} to Blob Storage in container articles-data.")

    except Exception as e:
        logging.error(f"Error uploading to Blob Storage: {e}")


'''
Function 2: Blob Trigger
Triggers when a new blob is detected in the articles-data container. 
It performs sentiment analysis on the article, appending the results and 
saving it to the articles-sentiment container. 
'''
@app.blob_trigger(arg_name="myblob", path="articles-data/{name}",
                  connection="BLOB_CONNECTION_STRING") 
def BlobTrigger(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob\n"
                 f"Name: {myblob.name}\n"
                 f"Blob Size: {myblob.length} bytes")
    
    start_time = time.time()

    try:
        # Read the blob content
        blob_content = myblob.read()
        article_data = json.loads(blob_content)

        # Extract content from JSON for sentiment analysis
        content = article_data.get('content', '')
        if not content:
            logging.warning("No content found in the blob data.")
            return

        #Do sentiment analysis
        blob = TextBlob(content)
        polarity = blob.sentiment.polarity
        subjectivity = blob.sentiment.subjectivity
        sentiment = "positive" if polarity > 0 else "negative"

        #Append sentiment analysis results to the article data
        article_data['sentiment'] = {
            'polarity': polarity,
            'subjectivity': subjectivity,
            'overall': sentiment
        }

        #Also log the results
        # logging.info(f"Processed article: {article_data['title']}")
        # logging.info(f"Sentiment Analysis: Polarity={polarity}, "
                    #  f"Subjectivity={subjectivity}, Overall Sentiment={sentiment}")

        #Call function to save updated article to the articles-sentiment container
        save_to_blob_with_sentiment(article_data, f"sentiment-{myblob.name}")

        end_time = time.time()
        logging.info(f"Total processing time for blob {myblob.name}: {end_time - start_time:.3f} seconds")

    except Exception as e:
        logging.error(f"Error processing blob {myblob.name}: {e}")


def save_to_blob_with_sentiment(data, blob_name):
    try:
        #Initialise BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

        #Get the articles-sentiment container
        container_client = blob_service_client.get_container_client("articles-sentiment")
        if not container_client.exists():
            container_client.create_container()

        # Upload the JSON data as a blob
        blob_client = container_client.get_blob_client(blob_name)
        blob_content = json.dumps(data, ensure_ascii=False, indent=4)
        blob_client.upload_blob(blob_content, overwrite=True)

        logging.info(f"Uploaded {blob_name} to Blob Storage in container articles-sentiment.")

    except Exception as e:
        logging.error(f"Error uploading sentiment data to Blob Storage: {e}")


'''
Function 3: Generate Fake Articles
An HTTP trigger function to generate fake article data and upload it to
Blob storage.
'''
@app.route(route="GenerateFakeArticles", auth_level=func.AuthLevel.ANONYMOUS)
def GenerateFakeArticles(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    count = 10

    try:
        #Initialise BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
        container_name = "articles-data"

         #Get the articles-sentiment container
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()

        # Generate mock data/article
        for i in range(count):
            fake_article = {
                "title": f"Fake Article {i+1}",
                "content": "This is a generated fake article for scalability testing purposes.",
                "url": f"https://fakeurl.com/article-{i+1}"
            }
            #Upload the JSON data as a blob
            blob_name = f"fake-article-{i+1}.json"
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(json.dumps(fake_article), overwrite=True)

        logging.info(f"Generated and uploaded {count} fake articles.")
        return func.HttpResponse(f"Successfully generated and uploaded {count} fake articles.", status_code=200)

    except Exception as e:
        logging.error(f"Error generating fake articles: {e}")
        return func.HttpResponse(f"An error occurred: {str(e)}", status_code=500)

