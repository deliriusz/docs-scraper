import os
import sys
import asyncio
import unittest

# Add parent directory to sys.path to import docs_crawler
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import docs_crawler

class TestDocsCrawler(unittest.TestCase):
    def setUp(self):
        # Setup test environment
        self.config_file = os.path.join(os.path.dirname(__file__), "docs.json")
        self.output_dir = os.path.join(os.path.dirname(__file__), "output")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def tearDown(self):
        # Cleanup not needed for basic test
        # But could be added here to remove test output files
        pass
    
    def test_crawl_docs(self):
        """Test that docs_crawler can process the test config file and generate output."""
        # Run the main function
        asyncio.run(docs_crawler.main(self.config_file, self.output_dir))
        
        # Check if output directory contains files
        files = os.listdir(self.output_dir)
        self.assertTrue(len(files) > 0, "No output files were generated")
        
        # Check if VISITED_URLS contains the URLs from the config
        with open(self.config_file) as json_data:
            import json
            conf = json.load(json_data)
            
            # Check if single page was visited
            for url in conf["single_page"]:
                url = docs_crawler.cleanup_url(url)
                self.assertTrue(url in docs_crawler.VISITED_URLS, f"URL {url} was not visited")
            
            # Check if YouTube page was visited
            for url in conf["youtube"]:
                url = docs_crawler.cleanup_url(url)
                self.assertTrue(url in docs_crawler.VISITED_URLS, f"URL {url} was not visited")
            
            # Check if at least the base URL from scrap was visited
            for scrap_item in conf["scrap"]:
                self.assertTrue(docs_crawler.cleanup_url(scrap_item["url"]) in docs_crawler.VISITED_URLS,
                                f"URL {scrap_item['url']} was not visited")
        
        print(f"Test completed successfully. Generated {len(files)} output files.")
        print(f"Output directory: {self.output_dir}")
        print(f"Visited URLs: {len(docs_crawler.VISITED_URLS)}")

if __name__ == "__main__":
    unittest.main() 