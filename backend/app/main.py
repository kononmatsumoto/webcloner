from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any
import os
from dotenv import load_dotenv

from .scraper import WebsiteScraper
from .llm_service import LLMService

# Load environment variables
load_dotenv()

app = FastAPI(title="Website Cloning API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services lazily
llm_service = None

def get_llm_service():
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service

class CloneRequest(BaseModel):
    url: HttpUrl

class CloneResponse(BaseModel):
    success: bool
    html_content: str = ""
    error: str = ""
    scraped_data: Dict[str, Any] = {}

@app.get("/")
def read_root():
    return {"message": "Website Cloning API", "version": "1.0.0"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/clone", response_model=CloneResponse)
async def clone_website(request: CloneRequest):
    """
    Clone a website by scraping it and generating HTML with LLM
    """
    try:
        url = str(request.url)
        
        # Scrape the website
        scraper = WebsiteScraper()
        scraped_data = await scraper.scrape_website(url)
        
        # Generate HTML using LLM
        llm = get_llm_service()
        html_content = await llm.generate_html_clone(scraped_data)
        
        # Clean the HTML response
        cleaned_html = html_content
        
        # Calculate enhanced statistics
        text_hierarchy = scraped_data.get('text_hierarchy', {})
        statistics = scraped_data.get('statistics', {})
        
        # Count text elements more accurately
        total_text_elements = statistics.get('text_elements', 0)
        
        # Count components
        components_count = statistics.get('components', 0)
        
        # Include full data for debugging, plus basic stats for frontend
        full_data = scraped_data.get('data', {})
        articles = full_data.get('articles', [])
        
        return CloneResponse(
            success=True,
            html_content=cleaned_html,
            scraped_data={
                'title': scraped_data.get('title', ''),
                'url': scraped_data.get('url', ''),
                'method': scraped_data.get('method', 'unknown'),  # Track which scraping method was used
                'text_content_count': total_text_elements,
                'images_count': len(scraped_data.get('images', [])),
                'colors_count': len(scraped_data.get('colors', [])),
                'components_count': components_count,
                'navigation_items': statistics.get('navigation_items', 0),
                'buttons_count': statistics.get('buttons', 0),
                # Include article data for debugging
                'articles_found': len(articles),
                'data': full_data  # Include full data structure
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/scrape")
async def scrape_website(request: CloneRequest):
    """
    Scrape a website and return the extracted data (for debugging/testing)
    """
    try:
        url = str(request.url)
        
        scraper = WebsiteScraper()
        scraped_data = await scraper.scrape_website(url)
        
        # Remove the screenshot from response to reduce size
        if 'screenshot' in scraped_data:
            scraped_data['screenshot'] = f"[Screenshot data - {len(scraped_data['screenshot'])} characters]"
        
        return scraped_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
