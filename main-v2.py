#!/usr/bin/env python
# coding: utf-8

# In[4]:


import os
import requests
from pymongo import MongoClient
import datetime


# In[6]:


# Event Registry API details
API_URL = "https://eventregistry.org/api/v1/article/getArticles"
API_KEY = "9d8ccead-0c1f-448f-9ceb-b85f4def0063"


# In[8]:


# MongoDB Setup
mongo_uri = os.getenv('MONGO_URI')  # Load from environment variables
client = MongoClient(mongo_uri)
db = client['news_database']
collection = db['news_articles']


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


# In[10]:


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


# In[12]:


# API request payload
payload = {
    "action": "getArticles",
    "keyword": "Tesla Inc",
    "sourceLocationUri": [
        "http://en.wikipedia.org/wiki/United_States",
        "http://en.wikipedia.org/wiki/United_Kingdom",
        "https://en.wikipedia.org/wiki/India"
    ],
    "ignoreSourceGroupUri": "paywall/paywalled_sources",
    "articlesPage": 1,
    "articlesCount": 100,
    "articlesSortBy": "date",
    "articlesSortByAsc": False,
    "dataType": ["news", "pr"],
    "forceMaxDataTimeWindow": 31,
    "resultType": "articles",
    "apiKey": API_KEY
}

# Fetch data from the API
response = requests.get(API_URL, json=payload)
if response.status_code != 200:
    print("Error fetching data:", response.status_code, response.text)
    exit()

# Parse response JSON
data = response.json()
articles = data.get("articles", {}).get("results", [])
print(len(articles))


# In[14]:


# Process and insert into MongoDB
news_data = []
category = "";
skipped_count = 0;
current_time = datetime.datetime.utcnow().isoformat()  # Current timestamp in UTC

for article in articles:
    uri = article.get("uri")
    print(f"My uri: "+uri)
    print(len(article.get("authors")))
    category = determine_category(article.get("body"))


    # Check if the article already exists in MongoDB
    if collection.find_one({"uri": uri}):
        skipped_count += 1
        continue  # Skip duplicate entry
        
    news_item = {
        "uri": article.get("uri"),
        "lang": article.get("lang"),
        "title_or": article.get("title"),
        "description_or": article.get("body"),
        "category": category,
        "url": article.get("url"),
        "published_time": article.get("dateTimePub"),
        "fetched_at": current_time,
        "image": article.get("image"),
        "images": [article.get("image")] if article.get("image") else [],
        "source": article.get("source", {}).get("title"),
        "sentiment": article.get("sentiment"),
        "wgt": article.get("wgt"),
        "relevance": article.get("relevance"),
        "author_name": article["authors"][0]["name"] if "authors" in article and article["authors"] else None,
        "likes": 0,
        "comments": 0,
        "shares": 0
    }
    news_data.append(news_item)
    #inserted_count = len(news_data)


if news_data:
    collection.insert_many(news_data)
    inserted_count = len(news_data)

print(f"Inserted {inserted_count} new articles, skipped {skipped_count} duplicates.")



# In[ ]:


# Close MongoDB connection
client.close()

