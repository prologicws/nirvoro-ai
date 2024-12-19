#!/usr/bin/env python
# coding: utf-8

# In[27]:


get_ipython().system('pip install requests beautifulsoup4 feedparser pymongo rapidfuzz selenium transformers torch')
import os
import re
import requests
import json
from bs4 import BeautifulSoup
import feedparser
from pymongo import MongoClient
from datetime import datetime
import pytz
from rapidfuzz import fuzz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
from selenium.webdriver.common.action_chains import ActionChains


# In[29]:


# MongoDB Setup
#client = MongoClient('mongodb://localhost:27017/')  # Update with your MongoDB connection URI
mongo_uri = os.getenv('MONGO_URI')  # Load from environment variables
client = MongoClient(mongo_uri)
db = client['news_database']
collection = db['news_articles']


# In[6]:


def setup_driver():
    options = Options()
    options.add_argument('--headless')  # Runs Chrome in headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service('/opt/homebrew/bin/chromedriver')  # Update this path if necessary
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# In[8]:


def convert_relative_time_to_iso(relative_time):
    """
    Convert a relative time string like '21 hours ago' to an ISO timestamp.
    """
    # Get the current time
    current_time = datetime.utcnow()

    # Use regular expressions to extract time units and values
    match = re.match(r"(\d+)\s*(\w+)\s*ago", relative_time)
    if not match:
        return None  # Return None if the format is not recognized

    amount, unit = int(match.group(1)), match.group(2)

    # Convert the time unit into a timedelta object
    if "hour" in unit:
        time_delta = timedelta(hours=amount)
    elif "minute" in unit:
        time_delta = timedelta(minutes=amount)
    elif "second" in unit:
        time_delta = timedelta(seconds=amount)
    elif "day" in unit:
        time_delta = timedelta(days=amount)
    else:
        return None  # If it's a unit we don't handle, return None

    # Subtract the timedelta from the current time
    calculated_time = current_time - time_delta

    # Convert to ISO format
    return calculated_time.isoformat() + "Z"  # Adding 'Z' to denote UTC time


# In[10]:


# Fetch full news content and additional details from the news article page
def fetch_full_article_bbc(url, driver):
    try:
        driver.get(url)
        #time.sleep(3)  # Wait for the page to load

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Initialize fields
        full_text = ""
        published_time = ""
        published_time_raw = ""
        author_name = ""
        author_designation = ""
        reporting_location = ""
        images = []

        # Extract the article content
        article = soup.find('article')
        if article:
            # Extract paragraphs
            paragraphs = article.find_all('p')
            full_text = ' '.join([p.get_text() for p in paragraphs])
            #print(f"Full text: {full_text}")

            # Extract published time
            time_tag = article.find('time')
            if time_tag:
                published_time_raw = time_tag.get_text()                
                print(f"Time: {published_time_raw}")
                published_time = convert_relative_time_to_iso(published_time_raw)


            # Extract author name and designation
            byline_block = article.find('div', {'data-component': 'byline-block'})
            if byline_block:
                author_name_tag = byline_block.find('span', class_='bZCrck')
                if author_name_tag:
                    author_name = author_name_tag.get_text()

                author_designation_tag = byline_block.find('div', class_='hEbjLr')
                if author_designation_tag:
                    author_designation = author_designation_tag.get_text()

                # Extract reporting location
                reporting_location_tag = byline_block.find('span', string=lambda x: x and "Reporting from" in x)
                if reporting_location_tag:
                    reporting_location = reporting_location_tag.get_text().replace("Reporting from", "").strip()
        
        # Extract images within <figure> tags
        figures = soup.find_all('figure')
        for fig in figures:
            img = fig.find('img')
            if img and img.get('src'):
                # Some images might have relative URLs
                img_url = img['src']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    img_url = 'https://www.bbc.com' + img_url
                images.append(img_url)
        
        return {
            "description": full_text if full_text else "Full content not available",
            "published_time": published_time,
            "author_name": author_name,
            "author_designation": author_designation,
            "reporting_location": reporting_location,
            "images": images
        }
    
    except Exception as e:
        print(f"Failed to fetch full content from {url}: {e}")
        return {
            "description": "Failed to fetch full content",
            "published_time": "",
            "author_name": "",
            "author_designation": "",
            "reporting_location": "",
            "images": []
        }


# In[12]:


def is_duplicate_article(new_article, existing_articles):
    """
    Check if the new article is a duplicate based on title similarity and source.
    If the title matches exactly and the source is the same, it's considered a duplicate.
    """
    for article_item in existing_articles:
        # Ensure the existing article has a title and source
        if 'title' in article_item and 'source' in article_item:
            if article_item['title_or'] == new_article['title_or'] and article_item['source'] == new_article['source']:
                print(f"Duplicate title found in the same source: {article_item['title_or']} (Source: {article_item['source']})")
                return True
        else:
            # If either title or source is missing, we can't reliably check for duplicates
            continue
            
    return False


# In[14]:


def determine_category(article_content):
    """
    Determines the category of the article based on its content.
    """
    # Define keywords for each category
    categories = {
        #"Breaking": ["breaking", "urgent", "just in"],
        "World": ["government", "policy", "election", "political", "politics", "weather", "storm", "temperature", "forecast", "climate", "environment", "sustainability", "nature"],
        "Business": ["business", "market", "stocks", "finance", "economy"],
        "Technology": ["research", "scientists", "study", "laboratory", "experiment", "science"],
        "Sports": ["game", "match", "tournament", "league", "athlete"],
        #"Art & Culture": ["art", "museum", "culture", "festival", "heritage"],
        "Entertainment": ["celebrity", "movie", "music", "show", "award", "art", "museum", "culture", "festival", "heritage", "travel", "tourism", "destination", "flight", "hotel"],
        #"Travel": ["travel", "tourism", "destination", "flight", "hotel"],
        #"Weather": ["weather", "storm", "temperature", "forecast"],
        #"Earth": ["climate", "environment", "sustainability", "nature"],
        #"Local": ["local", "community", "neighborhood", "town"]
    }

    # Default category
    assigned_category = "World"

    # Check for category keywords
    for category, keywords in categories.items():
        if any(keyword in article_content.lower() for keyword in keywords):
            assigned_category = category
            break
    print(f"Assigned category: {assigned_category}")
    return assigned_category

# Example usage with an article
#article_content = """The government has announced a new policy that will affect the election process."""
#category = determine_category(article_content)
#print(f"Assigned category: {category}")  # Should print "Politics"


# In[16]:


def save_articles_to_mongo(articles):
    """Save articles to MongoDB, avoiding duplicates based on title similarity across sources."""
    # Fetch all existing articles from the database for comparison
    existing_articles = list(collection.find({}, {'title_or': 1}))  # Only fetch titles for comparison

    for article in articles:
        # Check for duplicate articles based on title similarity
        if not is_duplicate_article(article, existing_articles):
            collection.insert_one(article)
            print(f"Saved article: {article['title_or']}")
        else:
            print(f"Duplicate article skipped: {article['title_or']}")


# In[18]:


def parse_rss_feed(rss_url, driver, portal):
    feed = feedparser.parse(rss_url)
    title = ""
    description = ""
    news_data = []
    images = []
    
    # Fetch existing titles from MongoDB for duplicate checking
    existing_titles = list(collection.find({}, {'title_or': 1}))
    #print(f"Skipping duplicate titles: {existing_titles}")
    existing_titles = [item['title_or'] for item in existing_titles]

    for entry in feed.entries:
        title = entry.title
        
        url = entry.link
        article_details = ''

        # Check for duplicates
        if is_duplicate_article({"title_or": title}, existing_titles):
            print(f"Duplicate article skipped: {title}")
            continue
            
        
        print(f"Portal: {portal}")

        # Fetch additional details from the article page
        article_details = fetch_full_article_bbc(url, driver)
        
        if article_details.get("description", "") != "":
            description = article_details.get("description", "")            
            category = determine_category(description)
            print(f"Title: {title}")  # Should print the Title
            images = article_details.get("images", [])
        
            # Use .get() to avoid KeyError for missing fields
            news_item = {            
                "title_or": title,
                "description_or": description,
                "url": url,
                "published_time": article_details.get("published_time", ""),
                "author_name": article_details.get("author_name", ""),
                "author_designation": article_details.get("author_designation", ""),  # Optional field
                "reporting_location": article_details.get("reporting_location", ""),  # Optional field
                "images": images,  # Optional field, default to empty list
                "source": portal,
                "category": category, 
                "like": 0,
                "comment": 0,
                "share": 0,
                "follow": 0,
                "processed": 0,
                "fetched_at": datetime.now()
            }
            #print(news_item)  # Print news details to the console
            news_data.append(news_item)
    
    return news_data


# In[20]:


def crawl_news():
    """Crawl all news outlets and save to MongoDB"""    
    driver = setup_driver()
    rss_url = "http://feeds.bbci.co.uk/news/rss.xml"
    print(rss_url);
    try:
        # Handle other portals with single URL feeds
        news_data = parse_rss_feed(rss_url, driver, 'bbc')
        save_articles_to_mongo(news_data)
    finally:
        driver.quit()


# In[34]:


if __name__ == "__main__":
    crawl_news()

