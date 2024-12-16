import feedparser
from pymongo import MongoClient
from datetime import datetime

# MongoDB Setup
client = MongoClient('mongodb://localhost:27017/')  # Update with your MongoDB connection URI
db = client['news_database']
collection = db['news_articles']

# List of RSS feed URLs
rss_feeds = {
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "CNN": "http://rss.cnn.com/rss/edition.rss",
    "Reuters": "http://feeds.reuters.com/reuters/topNews",
    "The New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "The Guardian": "https://www.theguardian.com/uk/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml"
}

def parse_rss_feed(feed_url):
    """Fetch and parse RSS feed"""
    feed = feedparser.parse(feed_url)
    articles = []
    
    for entry in feed.entries:
        # Extract the fields you need
        article = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.published if 'published' in entry else None,
            'summary': entry.summary if 'summary' in entry else None,
            'source': feed.feed.title,
            'fetched_at': datetime.now()
        }
        articles.append(article)
    
    return articles

def save_articles_to_mongo(articles):
    """Save articles to MongoDB, avoiding duplicates based on the article link"""
    for article in articles:
        if not collection.find_one({'link': article['link']}):
            collection.insert_one(article)
            print(f"Saved article: {article['title']}")
        else:
            print(f"Duplicate article skipped: {article['title']}")

def crawl_news():
    """Crawl all news outlets and save to MongoDB"""
    for source, url in rss_feeds.items():
        print(f"Crawling articles from: {source}")
        articles = parse_rss_feed(url)
        save_articles_to_mongo(articles)

if __name__ == "__main__":
    crawl_news()
