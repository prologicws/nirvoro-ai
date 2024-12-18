#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import time
import random
from pymongo import MongoClient
from transformers import pipeline
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB


# In[2]:


# MongoDB Setup
#client = MongoClient('mongodb://localhost:27017/')  # Update with your MongoDB connection URI
mongo_uri = os.getenv('MONGO_URI')  # Load from environment variables
client = MongoClient(mongo_uri)
db = client['news_database']
collection = db['news_articles']


# In[5]:


# Use explicit model names and enable GPU if available
summarizer = pipeline(
    'summarization', 
    model='sshleifer/distilbart-cnn-12-6', 
    revision='a4f8f3e',
    device=0  # Set to 0 for GPU, -1 for CPU
)

sentiment_analyzer = pipeline(
    'sentiment-analysis', 
    model='distilbert-base-uncased-finetuned-sst-2-english', 
    revision='714eb0f',
    device=0  # Set to 0 for GPU, -1 for CPU
)

vectorizer = CountVectorizer()


# In[6]:


def setup_driver():
    options = Options()
    options.add_argument('--headless')  # Runs Chrome in headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service('/opt/homebrew/bin/chromedriver')  # Update this path if necessary
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# In[9]:


def randomize_bias_scores():
    """
    Generate random scores for left, center, and right ensuring their sum is 100.
    """
    left = random.randint(0, 100)
    center = random.randint(0, 100 - left)
    right = 100 - (left + center)
    return {"left": left, "center": center, "right": right}


# In[11]:


def clean_and_summarize_text(text, max_len=50, min_len=20):
    """
    Clean sensationalism and summarize the input text (title or description).
    """
    # Summarize the input text (if needed)
    summary = summarizer(text, max_length=max_len, min_length=min_len, do_sample=False)[0]['summary_text']
    
    # Bolden important points in the summary
    cleaned_summary = bolden_important_points(summary)
    
    return cleaned_summary


# In[13]:


# Retrieve all articles from the collection
#articles = []
#articles = list(collection.find())
#mark_and_save_duplicate_articles();

def clean_sensationalism(article_text):
    """
    Cleans sensationalism by detecting overly emotional or sensational language 
    and rephrasing the text to focus on the facts.
    """
    
    # Break the text into sentences
    if not article_text:  # Check if article_text is None or empty
        return "Content not available or cannot be cleaned."
    
    sentences = article_text.split('. ')
    factual_sentences = []
    #print(f"Sentences: {sentences}")

    # Analyze each sentence
    for sentence in sentences:
        sentiment = sentiment_analyzer(sentence)
        if sentiment[0]['label'] in ['NEGATIVE', 'POSITIVE'] and sentiment[0]['score'] > 0.7:
            # Skip overly emotional sentences or rewrite them
            #print(f"Skipping sensational sentence: {sentence}")
            continue
        factual_sentences.append(sentence)

    # Join the factual sentences
    clean_text = '. '.join(factual_sentences)
    
    # Use summarization to condense the cleaned text
    summary = summarizer(clean_text, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
    
    return summary


# In[15]:


def process_articles(batch_size=10):
    driver = setup_driver()  # Initialize the Selenium driver
    try:
        while True:
            # Fetch unprocessed articles in small batches
            articles = list(collection.find({"processed": 0}).limit(batch_size))
            if not articles:
                print("No more articles to process.")
                break

            updates = []
            for article in articles:
                try:
                    # Prepare update data
                    update_data = {"processed": 1}

                    # Extract first image
                    if "images" in article and isinstance(article["images"], list) and article["images"]:
                        update_data["image"] = article["images"][0]

                    # Process text fields
                    if "title_or" in article:
                        update_data["title"] = clean_sensationalism(article["title_or"])
                    else:
                        print(f"Missing 'title_or' field in article ID: {article['_id']}")

                    if "description_or" in article:
                        update_data["description"] = clean_sensationalism(article["description_or"])
                        update_data["subtitle"] = summarizer(
                            article["description_or"], max_length=50, min_length=20, do_sample=False
                        )[0]["summary_text"]
                    else:
                        print(f"Missing 'description_or' field in article ID: {article['_id']}")

                    # Add update operation
                    updates.append(
                        {"filter": {"_id": article["_id"]}, "update": {"$set": update_data}}
                    )
                except Exception as e:
                    print(f"Error processing article ID {article['_id']}: {e}")

            # Perform bulk write for the batch
            if updates:
                try:
                    bulk_operations = [
                        {
                            "updateOne": {
                                "filter": upd["filter"],
                                "update": upd["update"]
                            }
                        }
                        for upd in updates
                    ]
                    result = collection.bulk_write(bulk_operations)
                    print(f"Updated {result.modified_count} articles.")
                except Exception as e:
                    print(f"Error during bulk write: {e}")
            else:
                print("No articles to update.")

            # Pause briefly to avoid overwhelming resources
            time.sleep(2)
    except Exception as e:
        print(f"An error occurred during processing: {e}")
    finally:
        driver.quit()


# In[17]:


def process_single_article():
    driver = setup_driver()  # Initialize the Selenium driver
    try:
        # Fetch one unprocessed article
        article = collection.find_one({"processed": 0})
        if not article:
            print("No more articles to process.")
            return

        try:
            print(f"Processing article ID: {article['_id']}")

            # Prepare update data
            update_data = {"processed": 1}

            # Extract first image
            if "images" in article and isinstance(article["images"], list) and article["images"]:
                update_data["image"] = article["images"][0]

            # Process text fields
            if "title_or" in article:
                update_data["title"] = clean_sensationalism(article["title_or"])
            else:
                print(f"Missing 'title_or' field in article ID: {article['_id']}")

            if "description_or" in article:
                update_data["description"] = clean_sensationalism(article["description_or"])
                update_data["subtitle"] = summarizer(
                    article["description_or"], max_length=50, min_length=20, do_sample=False
                )[0]["summary_text"]
            else:
                print(f"Missing 'description_or' field in article ID: {article['_id']}")

            # Generate randomized bias scores
            bias_scores = randomize_bias_scores()
            update_data.update(bias_scores)

            # Perform single update
            print(f"Prepared update data: {update_data}")
            result = collection.update_one({"_id": article["_id"]}, {"$set": update_data})

            # Log result
            if result.modified_count == 1:
                print(f"Successfully updated article ID: {article['_id']}")
            else:
                print(f"Article ID: {article['_id']} was not updated.")
        except Exception as e:
            print(f"Error processing article ID {article['_id']}: {e}")
            raise  # Re-raise the error for visibility
    finally:
        driver.quit()  # Ensure the Selenium driver is closed

# Run the function


# In[ ]:





# In[23]:


if __name__ == "__main__":
    #process_articles(batch_size=10)
    process_single_article()

