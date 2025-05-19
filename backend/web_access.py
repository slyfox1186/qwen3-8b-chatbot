import os
import time
import json
import aiohttp
import aiofiles
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import asyncio
from urllib.parse import urlparse
import re
import hashlib
import random
from aiohttp import ClientTimeout
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("web_access_async")

# Constants
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # Cache results for 1 hour by default
MAX_SEARCH_RESULTS = 5
MAX_CONTENT_LENGTH = 10000  # Maximum number of characters to extract from a page
REQUEST_TIMEOUT = 10  # Seconds
RATE_LIMIT_DELAY = 0.5  # Delay between requests in seconds
MAX_RETRIES = 3

# Google Custom Search API config
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY")

# User agent rotation for better scraping resilience
USER_AGENTS = [
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.156",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.3240.76",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 OPR/120.0.0.0"
]

# Create cache directory if it doesn't exist
os.makedirs(CACHE_DIR, exist_ok=True)

# Check if Google Custom Search API keys are available
if GOOGLE_API_KEY and GOOGLE_CSE_KEY:
    logger.info("Google Custom Search API configured")
    SEARCH_AVAILABLE = True

    # Initialize Google Custom Search API client
    try:
        import googleapiclient.discovery

        def get_google_search_service():
            return googleapiclient.discovery.build(
                "customsearch", "v1", developerKey=GOOGLE_API_KEY
            )

        # Test the configuration
        search_service = get_google_search_service()
        logger.info("Google Custom Search API client initialized successfully")
    except ImportError:
        logger.warning("Google API Python Client not available. Install with: pip install google-api-python-client")
        # Continue with direct API calls via aiohttp
    except Exception as e:
        logger.error(f"Error initializing Google Custom Search API client: {e}")
        # Continue with direct API calls via aiohttp
else:
    logger.warning("Google Custom Search API keys not found. Please set GOOGLE_API_KEY and GOOGLE_CSE_KEY in .env file")
    SEARCH_AVAILABLE = False

    # Fallback to DuckDuckGo if available
    try:
        from duckduckgo_search import AsyncDDGS
        search_client = AsyncDDGS()
        logger.info("Falling back to DuckDuckGo search")
        SEARCH_AVAILABLE = True
    except ImportError:
        try:
            from duckduckgo_search import DDGS
            logger.info("Using sync DuckDuckGo client with asyncio wrapper")
            SEARCH_AVAILABLE = True
        except ImportError:
            logger.warning("DuckDuckGo search module not available. Install with: pip install duckduckgo-search")
            SEARCH_AVAILABLE = False

def get_random_user_agent() -> str:
    """Get a random user agent from the list."""
    return random.choice(USER_AGENTS)

async def check_robots_txt(url: str, session: aiohttp.ClientSession) -> bool:
    """
    Check if the URL is allowed according to robots.txt.
    Returns True if allowed or unable to check, False if disallowed.
    """
    try:
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        headers = {'User-Agent': get_random_user_agent()}
        timeout = ClientTimeout(total=5)
        
        async with session.get(robots_url, headers=headers, timeout=timeout) as response:
            if response.status == 200:
                text = await response.text()
                # Basic parsing - check if path is disallowed
                path = parsed_url.path or "/"
                lines = text.lower().split('\n')
                disallow_next = False
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('user-agent:') and ('*' in line or 'bot' in line):
                        disallow_next = True
                    elif disallow_next and line.startswith('disallow:'):
                        disallowed_path = line.replace('disallow:', '').strip()
                        if disallowed_path and path.startswith(disallowed_path):
                            logger.warning(f"Path {path} is disallowed by robots.txt")
                            return False
                    elif line.startswith('user-agent:'):
                        disallow_next = False
    except Exception as e:
        # If we can't check robots.txt, assume it's allowed
        logger.debug(f"Could not check robots.txt for {url}: {e}")
    
    return True

def get_cache_path(url: str) -> str:
    """Generate a unique cache filename for the given URL."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.json")

def is_cache_valid(cache_path: str) -> bool:
    """Check if a cache file exists and is still valid (not expired)."""
    if not os.path.exists(cache_path):
        return False
    
    # Check file age
    file_age = time.time() - os.path.getmtime(cache_path)
    return file_age < CACHE_TTL

async def save_to_cache(url: str, data: Dict[str, Any]) -> None:
    """Save data to the cache."""
    cache_path = get_cache_path(url)
    cache_data = {
        'url': url,
        'timestamp': time.time(),
        'data': data
    }
    async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(cache_data))

async def load_from_cache(url: str) -> Optional[Dict[str, Any]]:
    """Load data from the cache if available and valid."""
    cache_path = get_cache_path(url)
    if is_cache_valid(cache_path):
        try:
            async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                cache_data = json.loads(content)
                return cache_data.get('data')
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading cache file: {e}")
    
    return None

def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    # Replace multiple whitespace chars with a single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text

async def extract_content(html: str, url: str) -> Dict[str, Any]:
    """
    Extract relevant content from HTML using BeautifulSoup.
    Focus on important elements like headers, paragraphs, etc.
    
    Run in executor since BeautifulSoup is CPU-bound.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_content_sync, html, url)

def _extract_content_sync(html: str, url: str) -> Dict[str, Any]:
    """Synchronous version of extract_content for executor"""
    # Specify parser for consistency
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script, style, iframe, noscript, svg, header, nav, footer elements and comments
    # Also remove elements with common non-content roles
    for element in soup([
        'script', 'style', 'iframe', 'noscript', 'svg', 
        'header', 'nav', 'footer',
        lambda tag: tag.has_attr('role') and tag['role'] in ['navigation', 'banner', 'contentinfo', 'search', 'complementary']
    ]):
        element.decompose()
    
    # Extract title
    title = soup.title.string if soup.title else ""
    
    # Extract meta description
    meta_desc = ""
    meta_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if meta_tag and meta_tag.get('content'):
        meta_desc = meta_tag.get('content')
    
    # Extract main content
    content_elements = []
    
    # Try to find main content containers - add more common selectors
    main_content_selectors = [
        'main',
        'article',
        'div[role="main"]',
        'div#main',
        'div.main',
        'div#content',
        'div.content',
        'div#main-content',
        'div.main-content',
        'div.entry-content' 
    ]
    target_container = None
    for selector in main_content_selectors:
        target_container = soup.select_one(selector)
        if target_container:
            break # Found a primary container
    
    # If no specific main content area found, fallback to soup.body, but this is less ideal
    target_scope = target_container if target_container else soup.body
    
    if target_scope:
        # Get all headings, paragraphs, and list items
        # Consider only elements with meaningful text length
        min_text_len = 25 # Minimum characters for a text block to be considered

        for elem in target_scope.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote', 'td', 'th']): # Added td, th
            text = clean_text(elem.get_text(separator=' ', strip=True)) # Use separator and strip
            if text and len(text) > min_text_len: 
                elem_type = elem.name
                # Avoid adding text that is identical to the title or meta description if it's just a short P tag
                if elem_type == 'p' and (text == title or text == meta_desc) and len(text) < 150:
                    continue
                content_elements.append({
                    'type': elem_type,
                    'text': text
                })
    
    # Limit total content length
    total_text_len = 0
    filtered_elements = []
    
    for elem in content_elements:
        if total_text_len + len(elem['text']) > MAX_CONTENT_LENGTH:
            # Add a truncated version if we're close to the limit
            if total_text_len < MAX_CONTENT_LENGTH - 100:
                available_space = MAX_CONTENT_LENGTH - total_text_len
                elem['text'] = elem['text'][:available_space - 3] + "..."
                filtered_elements.append(elem)
            break
        
        filtered_elements.append(elem)
        total_text_len += len(elem['text'])
    
    # Parse domain for citation
    domain = urlparse(url).netloc
    
    return {
        'url': url,
        'domain': domain,
        'title': clean_text(title),
        'description': clean_text(meta_desc),
        'content': filtered_elements
    }

async def fetch_url(url: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """
    Fetch content from a URL with caching and best practices.
    Returns extracted content or None if the request fails.
    """
    # Check cache first
    cached_data = await load_from_cache(url)
    if cached_data:
        logger.info(f"Using cached content for: {url}")
        return cached_data
    
    # Check robots.txt
    if not await check_robots_txt(url, session):
        logger.warning(f"URL {url} is disallowed by robots.txt")
        return None
    
    # Not in cache, fetch from web
    logger.info(f"Fetching content from: {url}")
    
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    timeout = ClientTimeout(total=REQUEST_TIMEOUT)
    
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, headers=headers, timeout=timeout) as response:
                # Check if content is HTML
                content_type = response.headers.get('Content-Type', '').lower()
                if not ('text/html' in content_type or 'application/xhtml+xml' in content_type):
                    logger.warning(f"Skipping non-HTML content: {content_type} for {url}")
                    return None
                
                html = await response.text()
                
                # Extract content
                extracted_data = await extract_content(html, url)
                
                # Save to cache
                await save_to_cache(url, extracted_data)
                
                # Rate limiting
                await asyncio.sleep(RATE_LIMIT_DELAY)
                
                return extracted_data
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout error fetching {url} (attempt {attempt + 1}/{MAX_RETRIES})")
        except aiohttp.ClientError as e:
            logger.error(f"Client error fetching {url}: {e} (attempt {attempt + 1}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None
        
        # Wait before retry
        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(attempt + 1)
    
    return None

async def search_web(query: str, num_results: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    """
    Search the web using Google Custom Search API or fallback to DuckDuckGo.
    """
    if not SEARCH_AVAILABLE:
        logger.error("Search functionality not available. Configure Google Custom Search API or install duckduckgo-search.")
        return []

    try:
        logger.info(f"Searching for: {query}")

        # Use Google Custom Search API if keys are available
        if GOOGLE_API_KEY and GOOGLE_CSE_KEY:
            try:
                # First try using the Google API Python Client
                try:
                    import googleapiclient.discovery
                    import googleapiclient.errors

                    # Run in executor since the Google API client is synchronous
                    loop = asyncio.get_event_loop()
                    search_results = await loop.run_in_executor(
                        None,
                        lambda: _google_search_sync(query, num_results)
                    )

                    if search_results and len(search_results) > 0:
                        return search_results

                except (ImportError, NameError):
                    logger.warning("Google API Python Client not available, falling back to direct API calls")
                    # Fall through to direct API call method

                # Fallback to direct API call using aiohttp
                logger.info("Using direct Google Custom Search API call")
                api_url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": GOOGLE_API_KEY,
                    "cx": GOOGLE_CSE_KEY,
                    "q": query,
                    "num": min(num_results, 10)  # Google API limits to 10 results per call
                }

                # Make async request to Google Custom Search API
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, params=params) as response:
                        if response.status == 200:
                            google_results = await response.json()
                            logger.info(f"Google search returned {len(google_results.get('items', []))} results")

                            # Format results to match expected structure
                            results = []
                            for item in google_results.get("items", []):
                                results.append({
                                    "title": item.get("title", ""),
                                    "href": item.get("link", ""),
                                    "body": item.get("snippet", ""),
                                    "source": "Google"
                                })
                            return results
                        else:
                            error_data = await response.text()
                            logger.error(f"Google Custom Search API error: {response.status} - {error_data}")
                            # Fall through to DuckDuckGo as backup
            except Exception as e:
                logger.error(f"Error using Google Custom Search API: {e}")
                # Fall through to DuckDuckGo as backup

        # Fallback to DuckDuckGo
        logger.info("Falling back to DuckDuckGo search")
        # Try async client first
        try:
            from duckduckgo_search import AsyncDDGS
            async with AsyncDDGS() as ddgs:
                results = []
                async for result in ddgs.text(query, max_results=num_results):
                    results.append(result)
                return results
        except (NameError, ImportError):
            # Fallback to sync client in executor
            try:
                from duckduckgo_search import DDGS
                loop = asyncio.get_event_loop()
                sync_client = DDGS()
                results = await loop.run_in_executor(
                    None,
                    lambda: list(sync_client.text(query, max_results=num_results))
                )
                return results
            except ImportError:
                logger.error("Neither Google Custom Search API nor DuckDuckGo search are available")
                return []
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return []

def _google_search_sync(query: str, num_results: int) -> List[Dict[str, Any]]:
    """Synchronous function to search Google using the official client library."""
    try:
        import googleapiclient.discovery
        import googleapiclient.errors

        # Build a service object
        service = googleapiclient.discovery.build(
            "customsearch", "v1", developerKey=GOOGLE_API_KEY
        )

        # Execute the search
        res = service.cse().list(
            q=query,
            cx=GOOGLE_CSE_KEY,
            num=min(num_results, 10)
        ).execute()

        # Format results to match expected structure
        results = []
        for item in res.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "href": item.get("link", ""),
                "body": item.get("snippet", ""),
                "source": "Google"
            })

        return results
    except Exception as e:
        logger.error(f"Error in Google Search sync: {e}")
        return []

async def fetch_search_results_content(search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fetch the actual content from search results URLs in parallel.
    """
    urls = [result.get('href') for result in search_results if result.get('href')]
    
    detailed_results = []
    
    # Create connector with connection pool
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=2)
    timeout = ClientTimeout(total=REQUEST_TIMEOUT)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Create tasks for all URLs
        tasks = []
        for url in urls:
            task = fetch_url(url, session)
            tasks.append(task)
        
        # Process results as they complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (url, result) in enumerate(zip(urls, results)):
            if isinstance(result, Exception):
                logger.error(f"Error processing {url}: {result}")
                continue
            
            if result:
                # Find the original search result for this URL
                for search_result in search_results:
                    if search_result.get('href') == url:
                        # Combine search result metadata with page content
                        combined_data = {
                            **result,
                            'snippet': search_result.get('body', ''),
                            'title': result.get('title') or search_result.get('title', '')
                        }
                        detailed_results.append(combined_data)
                        break
    
    return detailed_results

def format_search_results(query: str, detailed_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Format the search results into a structured response that can be used by the model.
    """
    formatted_articles = []
    
    for i, result in enumerate(detailed_results):
        article = {
            'title': result.get('title', 'Untitled'),
            'url': result.get('url', ''),
            'domain': result.get('domain', ''),
            'description': result.get('description', result.get('snippet', '')),
            'content': []
        }
        
        # Format the content sections
        for elem in result.get('content', []):
            article['content'].append({
                'type': elem.get('type', 'p'),
                'text': elem.get('text', '')
            })
        
        formatted_articles.append(article)
    
    return {
        'query': query,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'num_results': len(formatted_articles),
        'articles': formatted_articles
    }

def format_citations(articles: List[Dict[str, Any]]) -> str:
    """
    Generate formatted citations for web content.
    """
    if not articles:
        return ""
    
    citations = "\n\nSources:\n"
    
    for i, article in enumerate(articles):
        domain = article.get('domain', 'Unknown source')
        url = article.get('url', '')
        title = article.get('title', 'Untitled')
        
        citations += f"[{i+1}] {title} ({domain}) - {url}\n"
    
    return citations

def generate_search_prompt(user_query: str, search_results: Dict[str, Any]) -> str:
    """
    Generate a comprehensive prompt for the model that includes the search results.
    """
    articles = search_results.get('articles', [])
    
    prompt = f"I need to answer this question: '{user_query}'\n\n"
    prompt += f"Based on the latest search results ({search_results.get('timestamp', 'recent')}), here's what I found:\n\n"
    
    for i, article in enumerate(articles):
        prompt += f"SOURCE {i+1}: {article.get('title', 'Untitled')} ({article.get('domain', '')})\n"
        
        # Add the content from the article
        content_text = ""
        for elem in article.get('content', []):
            elem_type = elem.get('type', 'p')
            text = elem.get('text', '')
            
            if elem_type.startswith('h'):
                content_text += f"\n{text}\n"
            else:
                content_text += f"{text}\n"
        
        # Truncate if content is very long
        if len(content_text) > 1500:
            content_text = content_text[:1500] + "...\n"
            
        prompt += f"{content_text}\n"
    
    prompt += "\nPlease use this information to provide a comprehensive, accurate, and up-to-date answer to the question. Include relevant facts and cite your sources using [1], [2], etc. as needed."
    
    return prompt

async def web_search(query_for_search_engine: str, original_cleaned_user_query: str) -> Dict[str, Any]:
    """
    Main function to handle web search and content retrieval.
    Uses query_for_search_engine for hitting search APIs.
    Uses original_cleaned_user_query for constructing prompts for the main LLM.

    Returns a dictionary with:
    - search_results: The formatted search results
    - model_prompt: Prompt to send to the model
    - citations: Formatted citations
    """
    logger.info(f"Web access: Received query for search engine: '{query_for_search_engine}'")
    logger.info(f"Web access: Received original cleaned user query: '{original_cleaned_user_query}'")

    # Add current date/time to the engine-specific query for time-sensitive questions
    from datetime import datetime
    current_date = datetime.now().strftime("%Y %B %d")
    time_sensitive_engine_query = f"{query_for_search_engine} as of {current_date}"

    # Search the web with the time-enhanced, engine-optimized query
    logger.info(f"Using time-enhanced engine query for search API: '{time_sensitive_engine_query}'")
    # The function previously named search_web (which makes the API calls) should be used here.
    # Let's assume it's now _raw_search_engine_call or similar internal name if we refactored it,
    # or that the existing search_web correctly uses its first param for the API call.
    # For now, assuming the existing search_web function (that calls Google/DDG) will take this engine query.
    search_api_results = await search_web_api_call(time_sensitive_engine_query) # search_web_api_call is the renamed search_web
    
    if not search_api_results:
        return {
            "success": False,
            "error": "No search results found from search engine API",
            "search_results": None,
            # Use original_cleaned_user_query for user-facing messages or LLM prompts about the failure
            "model_prompt": f"I was asked: '{original_cleaned_user_query}' but couldn't find any reliable information online.",
            "citations": ""
        }
    
    # Fetch content from search results
    detailed_results = await fetch_search_results_content(search_api_results)
    
    if not detailed_results:
        return {
            "success": False,
            "error": "Failed to retrieve content from search results",
            "search_results": None,
            "model_prompt": f"I was asked: '{original_cleaned_user_query}' but couldn't retrieve content from the search results.",
            "citations": ""
        }
    
    # Format the results - use original_cleaned_user_query here
    formatted_results = format_search_results(original_cleaned_user_query, detailed_results)
    
    # Generate a prompt for the model - use original_cleaned_user_query here
    model_prompt_for_llm = generate_search_prompt(original_cleaned_user_query, formatted_results)
    
    # Generate citations
    citations = format_citations(formatted_results.get('articles', []))
    
    return {
        "success": True,
        "search_results": formatted_results,
        "model_prompt": model_prompt_for_llm,
        "citations": citations
    }

# Renaming the original search_web to search_web_api_call to make its role clearer
# This function now solely focuses on interacting with the search engine APIs.
async def search_web_api_call(query_for_engine: str, num_results: int = MAX_SEARCH_RESULTS) -> List[Dict[str, Any]]:
    """
    Search the web using Google Custom Search API or fallback to DuckDuckGo.
    This is the raw call to the search engine using the (potentially optimized) query_for_engine.
    """
    if not SEARCH_AVAILABLE:
        logger.error("Search functionality not available. Configure Google Custom Search API or install duckduckgo-search.")
        return []

    try:
        logger.info(f"Searching for: {query_for_engine}")

        # Use Google Custom Search API if keys are available
        if GOOGLE_API_KEY and GOOGLE_CSE_KEY:
            try:
                # First try using the Google API Python Client
                try:
                    import googleapiclient.discovery
                    import googleapiclient.errors

                    # Run in executor since the Google API client is synchronous
                    loop = asyncio.get_event_loop()
                    search_results = await loop.run_in_executor(
                        None,
                        lambda: _google_search_sync(query_for_engine, num_results)
                    )

                    if search_results and len(search_results) > 0:
                        return search_results

                except (ImportError, NameError):
                    logger.warning("Google API Python Client not available, falling back to direct API calls")
                    # Fall through to direct API call method

                # Fallback to direct API call using aiohttp
                logger.info("Using direct Google Custom Search API call")
                api_url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": GOOGLE_API_KEY,
                    "cx": GOOGLE_CSE_KEY,
                    "q": query_for_engine,
                    "num": min(num_results, 10)  # Google API limits to 10 results per call
                }

                # Make async request to Google Custom Search API
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, params=params) as response:
                        if response.status == 200:
                            google_results = await response.json()
                            logger.info(f"Google search returned {len(google_results.get('items', []))} results")

                            # Format results to match expected structure
                            results = []
                            for item in google_results.get("items", []):
                                results.append({
                                    "title": item.get("title", ""),
                                    "href": item.get("link", ""),
                                    "body": item.get("snippet", ""),
                                    "source": "Google"
                                })
                            return results
                        else:
                            error_data = await response.text()
                            logger.error(f"Google Custom Search API error: {response.status} - {error_data}")
                            # Fall through to DuckDuckGo as backup
            except Exception as e:
                logger.error(f"Error using Google Custom Search API: {e}")
                # Fall through to DuckDuckGo as backup

        # Fallback to DuckDuckGo
        logger.info("Falling back to DuckDuckGo search")
        # Try async client first
        try:
            from duckduckgo_search import AsyncDDGS
            async with AsyncDDGS() as ddgs:
                results = []
                async for result in ddgs.text(query_for_engine, max_results=num_results):
                    results.append(result)
                return results
        except (NameError, ImportError):
            # Fallback to sync client in executor
            try:
                from duckduckgo_search import DDGS
                loop = asyncio.get_event_loop()
                sync_client = DDGS()
                results = await loop.run_in_executor(
                    None,
                    lambda: list(sync_client.text(query_for_engine, max_results=num_results))
                )
                return results
            except ImportError:
                logger.error("Neither Google Custom Search API nor DuckDuckGo search are available")
                return []
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return []