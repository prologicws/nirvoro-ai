# Import functions from the individual script files
from crawl_news_bbc import crawl_news
from process_news_articles import process_single_article

def main():
    print("Starting the main script.")
    
    # Call tasks from individual scripts
    crawl_news()
    process_single_article()

    print("All tasks are completed.")

if __name__ == "__main__":
    main()
