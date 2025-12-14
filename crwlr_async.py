import sys
import argparse
import signal
import json
import time
import re
import asyncio
import aiohttp
import logging
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import tldextract
from tqdm.asyncio import tqdm
import aiosocks
from DataBase import CrawlDatabaseManager, CrawlSessionConfig, CrawlMetrics
from buffer_handler import CrawlBufferHandler
import os
from dotenv import load_dotenv

logging.basicConfig(filename='./results/debug.log', level=logging.DEBUG, format='[%(levelname)s] %(asctime)s: %(message)s')

load_dotenv()

logging.info("Loading .env and attempting to connect to the database")

# Legacy PostgreSQL connection - kept for backwards compatibility
# Now using SQLite through CrawlDatabaseManager for crawl data
def try_connection():
    """Legacy PostgreSQL connection test - deprecated, use --db flag instead"""
    try:
        from DataBase.config import DB_Config
        db_connection = DB_Config(
            db_endpoint=os.getenv("DB_HOST"),
            db_port=os.getenv("DB_PORT")
        )
        db_connection.connect_db()
        
        logging.debug(f"Database connection established")

        db_connection.close()
    except Exception as e:
        logging.error(f"Failed to connect to database: {str(e)}")



# Colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
END = '\033[0m'
BOLD = '\033[1m'

# Global sets to track visited URLs and found items
visited_urls = set()
found_subdomains = set()
found_paths = set()
urls_lock = asyncio.Lock()
subdomains_lock = asyncio.Lock()
paths_lock = asyncio.Lock()

# Crawl data buffer handler
buffer_handler = None
CRAWLED_URLS_QTY = 100  # Flush to DB every N records
buffer_flush_event = None  # Event to stop background flusher

# For graceful shutdown
shutdown_flag = False

# Banner placeholder
ascii_art = f"""{CYAN}{BOLD}

░█████╗░██████╗░░██╗░░░░░░░██╗██████╗░██╗░░░░░
██╔══██╗██╔══██╗░██║░░██╗░░██║██╔══██╗██║░░░░░
██║░░╚═╝██████╔╝░╚██╗████╗██╔╝██████╔╝██║░░░░░
██║░░██╗██╔══██╗░░████╔═████║░██╔══██╗██║░░░░░
╚█████╔╝██║░░██║░░╚██╔╝░╚██╔╝░██║░░██║███████╗
░╚════╝░╚═╝░░╚═╝░░░╚═╝░░░╚═╝░░╚═╝░░╚═╝╚══════╝
{END}"""

def signal_handler(sig, frame):
    global shutdown_flag
    shutdown_flag = True
    print(f"\n[{RED}INTERRUPTED{END}] Finishing current requests and exiting...")

def get_args():
    description = """
Extract subdomains and paths from website source code by crawling internal links.

This tool recursively analyzes a website's HTML to discover:
  • Subdomains belonging to the main domain
  • All internal paths and routes
  • Multi-level subdomain hierarchies

The crawler respects rate limits and uses asyncio for efficient scanning.
"""
    
    epilog = """
Examples:
  # Basic scan
  %(prog)s -u https://example.com
  
  # Fast scan with 10 workers and minimal delay
  %(prog)s -u https://example.com -w 10 -r 0.2
  
  # Deep scan with max depth of 5 levels
  %(prog)s -u https://example.com -d 5
  
  # Save results to files (TXT + JSON)
  %(prog)s -u https://example.com -o results -j
  
  # Verbose mode with custom User-Agent
  %(prog)s -u https://example.com -v -a "MyBot/1.0"
  
  # Scan with authentication cookie
  %(prog)s -u https://example.com -H "Cookie: session=abc123"
  
  # Multiple custom headers
  %(prog)s -u https://example.com -H "Cookie: session=abc" -H "Authorization: Bearer token123"
  
  # Load headers from file
  %(prog)s -u https://example.com --headers-file headers.txt
  
  # Exclude specific paths and subdomains
  %(prog)s -u https://example.com --exclude-paths "/admin/.*" --exclude-subdomains "test\..*"
  
  # Use proxy
  %(prog)s -u https://example.com --proxy http://proxy.example.com:8080
  
  # Use SOCKS proxy
  %(prog)s -u https://example.com --socks socks5://user:pass@proxy.example.com:1080
  
  # Full featured scan
  %(prog)s -u https://example.com -w 10 -d 4 -r 0.3 -o output -j -v

For more information: https://github.com/AUCB21/CRWLR
"""
    
    parser = argparse.ArgumentParser(
        prog="CRWLR",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-u", "--url",
        type=str,
        dest="url",
        help="target URL to scan (must include http:// or https://)",
        required=True,
        metavar="URL"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        dest="verbose",
        help="show detailed output including all visited URLs and errors"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        dest="output",
        help="save results to files with this prefix (creates PREFIX_subdomains.txt and PREFIX_paths.txt)",
        metavar="PREFIX"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        dest="timeout",
        default=5,
        help="HTTP request timeout in seconds (default: 5)",
        metavar="SECONDS"
    )
    parser.add_argument(
        "-d", "--max-depth",
        type=int,
        dest="max_depth",
        default=3,
        help="maximum crawling depth to prevent infinite loops (default: 3)",
        metavar="DEPTH"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        dest="workers",
        default=5,
        help="number of concurrent async tasks for faster crawling (default: 5)",
        metavar="NUM"
    )
    parser.add_argument(
        "-r", "--rate-limit",
        type=float,
        dest="rate_limit",
        default=0.5,
        help="delay between requests in seconds to be respectful to servers (default: 0.5)",
        metavar="SECONDS"
    )
    parser.add_argument(
        "-a", "--user-agent",
        type=str,
        dest="user_agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        help="custom User-Agent string to avoid being blocked (default: Chrome/120)",
        metavar="STRING"
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        dest="json_output",
        help="export results in JSON format for easier automation and parsing"
    )
    parser.add_argument(
        "-H", "--header",
        action="append",
        dest="headers",
        help="custom HTTP header (can be used multiple times). Format: 'Name: Value'",
        metavar="HEADER"
    )
    parser.add_argument(
        "--headers-file",
        type=str,
        dest="headers_file",
        help="file containing custom headers (one per line, format: 'Name: Value')",
        metavar="FILE"
    )
    parser.add_argument(
        "--exclude-paths",
        type=str,
        dest="exclude_paths",
        help="regex pattern to exclude paths (e.g., '/admin/.*')",
        metavar="REGEX"
    )
    parser.add_argument(
        "--exclude-subdomains",
        type=str,
        dest="exclude_subdomains",
        help="regex pattern to exclude subdomains (e.g., 'test\..*')",
        metavar="REGEX"
    )
    parser.add_argument(
        "--proxy",
        type=str,
        dest="proxy",
        help="HTTP/HTTPS proxy URL (e.g., http://proxy.example.com:8080)",
        metavar="URL"
    )
    parser.add_argument(
        "--socks",
        type=str,
        dest="socks",
        help="SOCKS proxy URL (e.g., socks5://user:pass@proxy.example.com:1080)",
        metavar="URL"
    )
    parser.add_argument(
        "--db",
        type=str,
        dest="database",
        help="SQLite database file to store crawl results (e.g., 'crwlr.db')",
        metavar="FILE"
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        dest="buffer_size",
        default=100,
        help="number of records to buffer before flushing to database (default: 100)",
        metavar="NUM"
    )
    
    return parser.parse_args()

def parse_custom_headers(args):
    """Parse custom headers from arguments and file"""
    custom_headers = {}
    
    # Parse headers from -H flag
    if args.headers:
        for header in args.headers:
            if ':' in header:
                name, value = header.split(':', 1)
                custom_headers[name.strip()] = value.strip()
            else:
                print(f"[{YELLOW}WARNING{END}] Invalid header format (ignoring): {header}")
    
    # Parse headers from file
    if args.headers_file:
        try:
            with open(args.headers_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and ':' in line:
                        name, value = line.split(':', 1)
                        custom_headers[name.strip()] = value.strip()
            print(f"[{CYAN}INFO{END}] Loaded {len(custom_headers)} custom headers from file")
        except FileNotFoundError:
            print(f"[{RED}ERROR{END}] Headers file not found: {args.headers_file}")
            sys.exit(1)
        except Exception as e:
            print(f"[{RED}ERROR{END}] Error reading headers file: {str(e)}")
            sys.exit(1)
    
    return custom_headers

def normalize_url(url):
    """Normalize URL by removing fragments and ensuring proper format"""
    parsed = urlparse(url)
    # Remove fragment and normalize
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ''  # Remove fragment
    ))
    return normalized

def is_same_domain(url1, url2):
    """Check if two URLs belong to the same domain"""
    ext1 = tldextract.extract(url1)
    ext2 = tldextract.extract(url2)
    return ext1.domain == ext2.domain and ext1.suffix == ext2.suffix

def get_subdomain(url):
    """Extract subdomain from URL"""
    ext = tldextract.extract(url)
    if ext.subdomain and ext.subdomain != 'www':
        return f"{ext.subdomain}.{ext.domain}.{ext.suffix}"
    return None

def should_exclude(url, exclude_paths, exclude_subdomains):
    """Check if URL should be excluded based on patterns"""
    if exclude_paths:
        path = urlparse(url).path
        if re.search(exclude_paths, path):
            return True
    if exclude_subdomains:
        subdomain = get_subdomain(url)
        if subdomain and re.search(exclude_subdomains, subdomain):
            return True
    return False

def extract_urls_from_json(data, base_url):
    """Recursively extract potential URLs from JSON data"""
    urls = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                # Check if it looks like a URL
                if value.startswith(('http://', 'https://', '/')):
                    absolute_url = urljoin(base_url, value)
                    urls.append(normalize_url(absolute_url))
            elif isinstance(value, (dict, list)):
                urls.extend(extract_urls_from_json(value, base_url))
    elif isinstance(data, list):
        for item in data:
            urls.extend(extract_urls_from_json(item, base_url))
    return urls

async def buffer_monitor_task(handler):
    """Background task to monitor buffer size and flush when limit reached"""
    global buffer_flush_event
    
    while not buffer_flush_event.is_set():
        try:
            # Check if flush needed
            flushed = handler.flush_if_needed()
            
            if flushed > 0:
                stats = handler.get_stats()
                print(f"[{CYAN}BUFFER FLUSH{END}] #{stats['flush_count']}: {flushed} records → DB")
            
            # Check every 1 second
            await asyncio.sleep(1)
            
        except Exception as e:
            logging.error(f"Buffer monitor error: {e}")
            await asyncio.sleep(1)


async def crawl_url(session, url, base_domain, depth, args, custom_headers, semaphore, pbar, handler=None):
    """Crawl a single URL and extract links"""
    global shutdown_flag
    
    if shutdown_flag:
        return []
    
    async with urls_lock:
        if url in visited_urls:
            return []
        visited_urls.add(url)
    
    if args.verbose:
        print(f"[{BLUE}VISITING{END}] {url} (depth: {depth})")
    
    new_urls = []
    
    try:
        # Rate limiting
        await asyncio.sleep(args.rate_limit)
        
        # Build headers - start with defaults, then apply custom
        headers = {
            'User-Agent': args.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Override/add custom headers
        headers.update(custom_headers)
        
        request_start = time.time()
        async with semaphore:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=args.timeout), headers=headers, allow_redirects=True) as response:
                request_time = time.time() - request_start
                # logging.debug(f"Visited {url}, status {response.status}, final URL {response.url}, redirects: {len(response.history)}")
                # if len(response.history) > 0:
                #     for i, resp in enumerate(response.history):
                #         logging.debug(f"Redirect {i+1}: {resp.url} -> {resp.status}")
                if response.status == 200:
                    # Add the original and final URLs to found_paths if same domain
                    final_url = str(response.url)
                    
                    # Log successful response via handler
                    if handler:
                        try:
                            parsed = urlparse(url)
                            handler.add_url_record(
                                url=url,
                                normalized_url=normalize_url(url),
                                domain=parsed.netloc,
                                path=parsed.path,
                                depth=depth,
                                status_code=response.status,
                                content_type=response.headers.get('Content-Type'),
                                response_time_ms=request_time * 1000
                            )
                        except Exception as e:
                            logging.debug(f"Failed to buffer URL data: {e}")
                    async with paths_lock:
                        if is_same_domain(url, base_domain):
                            if url not in found_paths:
                                found_paths.add(url)
                                # logging.debug(f"Added original URL to paths: {url}")
                        if final_url != url and is_same_domain(final_url, base_domain):
                            if final_url not in found_paths:
                                found_paths.add(final_url)
                                # logging.debug(f"Added final URL to paths: {final_url}")
                    
                    # Extract subdomain from final URL
                    subdomain = get_subdomain(final_url)
                    if subdomain:
                        async with subdomains_lock:
                            if subdomain not in found_subdomains:
                                found_subdomains.add(subdomain)
                                print(f"[{GREEN}SUBDOMAIN{END}] {subdomain}")
                    
                    content_type = response.headers.get('Content-Type', '').lower()
                    # logging.debug(f"Content-Type: {content_type}")
                    potential_urls = []
                    
                    if 'application/json' in content_type:
                        # Parse JSON response
                        try:
                            data = await response.json()
                            potential_urls = extract_urls_from_json(data, url)
                        except json.JSONDecodeError:
                            if args.verbose:
                                print(f"[{YELLOW}WARNING{END}] Failed to parse JSON from {url}")
                    
                    elif 'text/html' in content_type:
                        # Parse HTML response
                        text = await response.text()
                        soup = BeautifulSoup(text, 'html.parser')
                        
                        for link in soup.find_all('a', href=True):
                            if shutdown_flag:
                                break
                                
                            href = link.get('href')
                            
                            # Resolve relative URLs
                            absolute_url = urljoin(url, href)
                            normalized = normalize_url(absolute_url)
                            potential_urls.append(normalized)
                    
                    else:
                        # Skip other content types
                        if args.verbose:
                            print(f"[{YELLOW}WARNING{END}] Unsupported content type {content_type} for {url}")
                    
                    # logging.debug(f"Found {len(potential_urls)} potential URLs from content")
                    
                    # Process potential URLs
                    for normalized in potential_urls:
                        if shutdown_flag:
                            break
                            
                        parsed = urlparse(normalized)
                        
                        # Skip invalid schemes
                        if parsed.scheme not in ['http', 'https']:
                            continue
                        
                        # Check exclusions
                        if should_exclude(normalized, args.exclude_paths, args.exclude_subdomains):
                            continue
                        
                        # Check if it belongs to the same domain
                        if is_same_domain(normalized, base_domain):
                            # Check for subdomain
                            subdomain = get_subdomain(normalized)
                            if subdomain:
                                async with subdomains_lock:
                                    if subdomain not in found_subdomains:
                                        found_subdomains.add(subdomain)
                                        print(f"[{GREEN}SUBDOMAIN{END}] {subdomain}")
                            
                            # Add URL to crawl queue if within depth limit
                            if depth < args.max_depth:
                                new_urls.append((normalized, depth + 1))
                else:
                    # logging.debug(f"Non-200 status for {url}: {response.status}")
                    
                    # Log non-200 response via handler
                    if handler:
                        try:
                            parsed = urlparse(url)
                            handler.add_url_record(
                                url=url,
                                normalized_url=normalize_url(url),
                                domain=parsed.netloc,
                                path=parsed.path,
                                depth=depth,
                                status_code=response.status,
                                content_type=response.headers.get('Content-Type'),
                                response_time_ms=request_time * 1000
                            )
                        except Exception as e:
                            logging.debug(f"Failed to buffer URL data: {e}")
    
    except asyncio.TimeoutError:
        if args.verbose:
            print(f"[{RED}TIMEOUT{END}] {url}")
        
        # Log timeout via handler
        if handler:
            try:
                parsed = urlparse(url)
                handler.add_url_record(
                    url=url,
                    normalized_url=normalize_url(url),
                    domain=parsed.netloc,
                    path=parsed.path,
                    depth=depth,
                    error_message='Request timeout'
                )
            except Exception as e:
                logging.debug(f"Failed to buffer timeout data: {e}")
    except aiohttp.ClientError as e:
        if args.verbose:
            print(f"[{RED}ERROR{END}] {url} - {str(e)[:50]}")
        
        # Log client error via handler
        if handler:
            try:
                parsed = urlparse(url)
                handler.add_url_record(
                    url=url,
                    normalized_url=normalize_url(url),
                    domain=parsed.netloc,
                    path=parsed.path,
                    depth=depth,
                    error_message=f'Client error: {str(e)[:200]}'
                )
            except Exception as log_error:
                logging.debug(f"Failed to buffer error data: {log_error}")
    except Exception as e:
        if args.verbose:
            print(f"[{RED}ERROR{END}] {url} - {str(e)[:50]}")
        
        # Log general error via handler
        if handler:
            try:
                parsed = urlparse(url)
                handler.add_url_record(
                    url=url,
                    normalized_url=normalize_url(url),
                    domain=parsed.netloc,
                    path=parsed.path,
                    depth=depth,
                    error_message=f'Error: {str(e)[:200]}'
                )
            except Exception as log_error:
                logging.debug(f"Failed to buffer error data: {log_error}")
    finally:
        # Update progress bar after visiting
        pbar.update(1)
    
    return new_urls

def save_results(prefix, json_output=False, metrics_data=None):
    """Save results to files"""
    if json_output:
        # Save JSON
        json_file = f"{prefix}_results.json"
        results = {
            "subdomains": sorted(list(found_subdomains)),
            "paths": sorted(list(found_paths)),
            "visited_urls": sorted(list(visited_urls)),
            "stats": {
                "total_subdomains": len(found_subdomains),
                "total_paths": len(found_paths),
                "total_visited": len(visited_urls)
            }
        }
        if metrics_data:
            results["stats"]["metrics"] = metrics_data
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"[{GREEN}SAVED{END}] JSON results saved to {json_file}")
    else:
        # Save subdomains
        subdomain_file = f"{prefix}_subdomains.txt"
        with open(subdomain_file, 'w') as f:
            for subdomain in sorted(found_subdomains):
                f.write(f"{subdomain}\n")
        print(f"[{GREEN}SAVED{END}] Subdomains saved to {subdomain_file}")
        
        # Save paths
        paths_file = f"{prefix}_paths.txt"
        with open(paths_file, 'w') as f:
            for path in sorted(found_paths):
                f.write(f"{path}\n")
        print(f"[{GREEN}SAVED{END}] Paths saved to {paths_file}")

async def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    args = get_args()
    url = args.url
    
    # Parse custom headers
    custom_headers = parse_custom_headers(args)
    
    # Validate URL has scheme
    parsed = urlparse(url)
    if not parsed.scheme:
        print(f"[{RED}ERROR{END}] No scheme provided. Please include 'http://' or 'https://' in the URL.")
        sys.exit(1)
    
    if parsed.scheme not in ['http', 'https']:
        print(f"[{RED}ERROR{END}] Invalid scheme. Only 'http' and 'https' are supported.")
        sys.exit(1)
    
    # Normalize base URL
    base_url = normalize_url(url)
    
    print(ascii_art)
    print(f"[{CYAN}TARGET{END}] {base_url}")
    print(f"[{CYAN}MAX DEPTH{END}] {args.max_depth}")
    print(f"[{CYAN}WORKERS{END}] {args.workers}")
    print(f"[{CYAN}RATE LIMIT{END}] {args.rate_limit}s between requests")
    if custom_headers:
        print(f"[{CYAN}CUSTOM HEADERS{END}] {len(custom_headers)} header(s) loaded")
    if args.exclude_paths:
        print(f"[{CYAN}EXCLUDE PATHS{END}] {args.exclude_paths}")
    if args.exclude_subdomains:
        print(f"[{CYAN}EXCLUDE SUBDOMAINS{END}] {args.exclude_subdomains}")
    if args.proxy:
        print(f"[{CYAN}PROXY{END}] {args.proxy}")
    if args.socks:
        print(f"[{CYAN}SOCKS{END}] {args.socks}")
    
    # Initialize database if requested
    db_manager = None
    session_id = None
    monitor_task = None
    global buffer_handler, buffer_flush_event
    
    if args.database:
        print(f"[{CYAN}DATABASE{END}] {args.database}")
        try:
            db_manager = CrawlDatabaseManager(args.database)
            db_manager.initialize()
            session_id = db_manager.start_session(CrawlSessionConfig(
                target_url=base_url,
                max_depth=args.max_depth,
                workers=args.workers,
                rate_limit=args.rate_limit,
                timeout=args.timeout,
                user_agent=args.user_agent,
                proxy=args.proxy or args.socks
            ))
            print(f"[{GREEN}DB SESSION{END}] Started session #{session_id}")
            
            # Initialize buffer handler
            buffer_handler = CrawlBufferHandler(
                session_id=session_id,
                db_manager=db_manager,
                buffer_limit=args.buffer_size,
                output_dir="results"
            )
            
            # Start background buffer monitor
            buffer_flush_event = asyncio.Event()
            monitor_task = asyncio.create_task(buffer_monitor_task(buffer_handler))
            print(f"[{CYAN}BUFFER MONITOR{END}] Auto-flush enabled (every {args.buffer_size} records)")
        except Exception as e:
            print(f"[{YELLOW}DB WARNING{END}] Failed to initialize database: {e}")
            db_manager = None
    print()
    
    # Setup proxy
    connector = None
    if args.socks:
        from aiosocks.connector import ProxyConnector
        connector = ProxyConnector.from_url(args.socks)
    elif args.proxy:
        connector = aiohttp.TCPConnector()
        # For HTTP proxy, aiohttp handles it via proxy param in session
    
    # Queue of URLs to visit (url, depth)
    urls_to_visit = [(base_url, 0)]
    
    # Execution metrics
    start_time = time.time()
    crawl_start_time = time.time()
    total_request_time = 0
    total_parse_time = 0
    
    semaphore = asyncio.Semaphore(args.workers)
    
    # Progress bar - start with estimated total
    proxy_url = args.proxy if args.proxy else None
    
    # Track completion status
    quitted = False
    
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            with tqdm(desc="Crawling", unit="url", colour="cyan") as pbar:
                while urls_to_visit and not shutdown_flag:
                    # Get batch of URLs to process
                    batch_size = min(args.workers * 2, len(urls_to_visit))
                    batch = []
                    for _ in range(batch_size):
                        if urls_to_visit and not shutdown_flag:
                            batch.append(urls_to_visit.pop(0))
                    
                    # Create tasks
                    tasks = [crawl_url(session, url, base_url, depth, args, custom_headers, semaphore, pbar, buffer_handler) for url, depth in batch]
                    
                    # Run tasks concurrently
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Collect new URLs
                    for result in results:
                        if isinstance(result, Exception):
                            if args.verbose:
                                print(f"[{RED}TASK ERROR{END}] {str(result)[:50]}")
                            continue
                        if result:
                            # Only add URLs that haven't been visited yet
                            async with urls_lock:
                                new_unique_urls = [u for u in result if u[0] not in visited_urls]
                            urls_to_visit.extend(new_unique_urls)
        
        # If we get here without interruption, mark as completed normally
        if not shutdown_flag:
            quitted = False
    
    finally:
        # Always calculate and log execution metrics
        elapsed_time = time.time() - start_time
        crawl_time = time.time() - crawl_start_time
        
        # Print results
        print(f"\n{BOLD}{'='*60}{END}")
        
        # Show completion status
        if shutdown_flag:
            print(f"{BOLD}[{YELLOW}INTERRUPTED{END}{BOLD}]{END} - Crawl was stopped early\n")
        else:
            print(f"{BOLD}[{GREEN}COMPLETED{END}{BOLD}]{END} - Crawl finished successfully\n")
        
        print(f"{BOLD}[{PURPLE}RESULTS{END}{BOLD}]{END}\n")
    
        print(f"[{CYAN}TOTAL URLS VISITED{END}] {len(visited_urls)}")
        print(f"[{GREEN}SUBDOMAINS FOUND{END}] {len(found_subdomains)}")
        print(f"[{YELLOW}PATHS FOUND{END}] {len(found_paths)}")
        
        # Detailed execution metrics
        print(f"\n{BOLD}[{BLUE}EXECUTION METRICS{END}{BOLD}]{END}")
        print(f"[{BLUE}TOTAL TIME{END}] {elapsed_time:.2f} seconds")
        print(f"[{BLUE}CRAWL TIME{END}] {crawl_time:.2f} seconds")
        
        if elapsed_time > 0:
            print(f"[{BLUE}CRAWL SPEED{END}] {len(visited_urls)/elapsed_time:.2f} URLs/second")
            print(f"[{BLUE}AVG TIME/URL{END}] {elapsed_time/len(visited_urls) if visited_urls else 0:.3f} seconds")
        
        # Calculate efficiency metrics
        if elapsed_time > 0:
            efficiency = (len(found_subdomains) + len(found_paths)) / elapsed_time
            print(f"[{BLUE}DISCOVERY RATE{END}] {efficiency:.2f} items/second")
        
        # Log to file as well
        logging.info(f"Crawl finished - Status: {'Interrupted' if shutdown_flag else 'Completed'}, Total Time: {elapsed_time:.2f}s, URLs Visited: {len(visited_urls)}, Subdomains: {len(found_subdomains)}, Paths: {len(found_paths)}")
        
        if found_subdomains:
            print(f"\n{BOLD}[{GREEN}SUBDOMAINS{END}{BOLD}]{END}")
            for subdomain in sorted(found_subdomains):
                print(f"  • {subdomain}")
        
        # Save to files if requested
        if args.output:
            print()
            metrics_data = {
                "total_time_seconds": round(elapsed_time, 2),
                "crawl_time_seconds": round(crawl_time, 2),
                "avg_time_per_url_seconds": round(elapsed_time/len(visited_urls) if visited_urls else 0, 3),
                "crawl_speed_urls_per_second": round(len(visited_urls)/elapsed_time if elapsed_time > 0 else 0, 2),
                "discovery_rate_items_per_second": round((len(found_subdomains) + len(found_paths))/elapsed_time if elapsed_time > 0 else 0, 2),
                "termination": "canceled" if shutdown_flag else "completed"
            }
            save_results(args.output, args.json_output, metrics_data)
        
        # Save to database if enabled
        if db_manager and session_id and buffer_handler:
            try:
                # Stop background monitor
                if buffer_flush_event:
                    buffer_flush_event.set()
                if monitor_task:
                    await monitor_task
                    print(f"[{CYAN}BUFFER MONITOR{END}] Stopped")
                
                # Add subdomains to buffer
                ext = tldextract.extract(base_url)
                base_domain = f"{ext.domain}.{ext.suffix}"
                for subdomain in found_subdomains:
                    buffer_handler.add_subdomain_record(subdomain, base_domain)
                
                # Final flush of remaining buffer
                remaining = buffer_handler.final_flush()
                if remaining > 0:
                    print(f"[{CYAN}FINAL FLUSH{END}] {remaining} remaining records → DB")
                
                # Get final stats
                stats = buffer_handler.get_stats()
                print(f"[{GREEN}JSON EXPORT{END}] Total {stats['total_flushed']} records saved")
                
                # Create metrics object
                crawl_metrics = CrawlMetrics(
                    total_time_seconds=elapsed_time,
                    crawl_time_seconds=crawl_time,
                    urls_visited=len(visited_urls),
                    subdomains_found=len(found_subdomains),
                    paths_found=len(found_paths),
                    crawl_speed=len(visited_urls)/elapsed_time if elapsed_time > 0 else 0,
                    avg_time_per_url=elapsed_time/len(visited_urls) if visited_urls else 0,
                    discovery_rate=(len(found_subdomains) + len(found_paths))/elapsed_time if elapsed_time > 0 else 0,
                    completed_normally=not shutdown_flag
                )
                
                # Complete session
                status = 'interrupted' if shutdown_flag else 'completed'
                db_manager.complete_session(session_id, crawl_metrics, status)
                print(f"[{GREEN}DB SAVED{END}] Session #{session_id} completed and saved to database")
                
                db_manager.close()
            except Exception as e:
                print(f"[{YELLOW}DB WARNING{END}] Failed to save to database: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{BOLD}{'='*60}{END}")
        print(f"[{PURPLE}DONE{END}]")

if __name__ == "__main__":
    # try_connection()
    asyncio.run(main())