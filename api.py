from flask import Flask, request, jsonify
from pymongo import MongoClient
from dateutil import parser
from bson import json_util
import re

app = Flask(__name__)

# MongoDB Setup
client = MongoClient('mongodb://localhost:27017/')  # Update with your MongoDB connection URI
db = client['news_database']
collection = db['news_articles']

# Function to clean and parse published_time
def normalize_published_time(published_time):
    # Remove unwanted text like "Updated"
    cleaned_time = re.sub(r"Updated|\s+", " ", published_time).strip()
    
    try:
        # Parse date using dateutil.parser
        parsed_date = parser.parse(cleaned_time)
        return parsed_date.isoformat()  # Convert to ISO format for MongoDB
    except (parser.ParserError, ValueError):
        return None

@app.route('/api/news', methods=['GET'])
def get_news():
    # Fetch query parameters for filters and pagination
    category = request.args.get('category')
    source = request.args.get('source')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))

    # Build MongoDB query
    query = {}
    if category:
        query["category"] = category
    if source:
        query["source"] = source

    # Calculate skip for pagination
    skip = (page - 1) * limit

    # Query the database with filters and pagination
    news_cursor = collection.find(query).sort("published_time", -1).skip(skip).limit(limit)
    news_list = []

    for news in news_cursor:
        # Parse and normalize the published_time field
        news['published_time'] = normalize_published_time(news.get('published_time', ''))
        news_list.append(news)

    return json_util.dumps(news_list), 200, {'Content-Type': 'application/json'}
    #return jsonify(news_list)

if __name__ == '__main__':
    app.run(debug=True)
