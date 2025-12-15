"""
CRWLR REST API - Web Crawler as a Service
A FastAPI-based RESTful API for managing web crawling jobs.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import asyncio
import uuid
import json
import os
import re
import time
import aiohttp
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import tldextract
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s: %(message)s',
    handlers=[
        logging.FileHandler('./results/api.log'),
        logging.StreamHandler()
    ]
)

load_dotenv()

# FastAPI app initialization
app = FastAPI(
    title="CRWLR API",
    description="RESTful API for managing web crawling jobs - Subdomain & Path Discovery",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global job storage (in production, use a database)
active_jobs: Dict[str, Dict[str, Any]] = {}
completed_jobs: Dict[str, Dict[str, Any]] = {}

# Job status enumeration
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Request models
class CrawlRequest(BaseModel):
    """Request model for starting a new crawl job"""
    url: str = Field(..., description="Target URL to crawl (must include http:// or https://)")
    max_depth: int = Field(3, ge=1, le=10, description="Maximum crawling depth")
    workers: int = Field(5, ge=1, le=50, description="Number of concurrent workers")
    rate_limit: float = Field(0.5, ge=0.1, le=5.0, description="Delay between requests in seconds")
    timeout: int = Field(5, ge=1, le=60, description="Request timeout in seconds")
    user_agent: Optional[str] = Field(None, description="Custom User-Agent string")
    verbose: bool = Field(False, description="Enable verbose logging")
    exclude_paths: Optional[str] = Field(None, description="Regex pattern to exclude paths")
    exclude_subdomains: Optional[str] = Field(None, description="Regex pattern to exclude subdomains")
    proxy: Optional[str] = Field(None, description="HTTP/HTTPS proxy URL")
    socks: Optional[str] = Field(None, description="SOCKS proxy URL")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers as key-value pairs")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class CrawlConfig(BaseModel):
    """Configuration for updating existing crawl job (future use)"""
    max_depth: Optional[int] = Field(None, ge=1, le=10)
    workers: Optional[int] = Field(None, ge=1, le=50)
    rate_limit: Optional[float] = Field(None, ge=0.1, le=5.0)

# Response models
class JobResponse(BaseModel):
    """Response model for job operations"""
    job_id: str
    status: JobStatus
    message: str
    created_at: str
    url: str

class JobStatusResponse(BaseModel):
    """Detailed job status response"""
    job_id: str
    status: JobStatus
    url: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    config: Dict[str, Any]
    progress: Dict[str, Any]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

class JobListResponse(BaseModel):
    """List of jobs response"""
    total: int
    active: int
    completed: int
    jobs: List[Dict[str, Any]]


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """API root endpoint with service information"""
    return {
        "service": "CRWLR API",
        "version": "1.0.0",
        "description": "RESTful API for web crawling - Subdomain & Path Discovery",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "jobs": {
                "create": "POST /api/v1/crawl",
                "list": "GET /api/v1/jobs",
                "get": "GET /api/v1/jobs/{job_id}",
                "cancel": "DELETE /api/v1/jobs/{job_id}",
                "results": "GET /api/v1/jobs/{job_id}/results"
            }
        }
    }

@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_jobs": len(active_jobs),
        "completed_jobs": len(completed_jobs)
    }

@app.post("/api/v1/crawl", response_model=JobResponse, tags=["Crawl Operations"])
async def create_crawl_job(
    request: CrawlRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new web crawling job
    
    - **url**: Target website URL to crawl
    - **max_depth**: How deep to crawl (1-10, default: 3)
    - **workers**: Concurrent workers (1-50, default: 5)
    - **rate_limit**: Delay between requests in seconds (0.1-5.0, default: 0.5)
    - **timeout**: Request timeout in seconds (1-60, default: 5)
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Create job record
    job_data = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "url": request.url,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "config": request.dict(),
        "progress": {
            "urls_visited": 0,
            "subdomains_found": 0,
            "paths_found": 0,
            "current_depth": 0
        },
        "results": None,
        "error": None,
        "task": None
    }
    
    # Store job
    active_jobs[job_id] = job_data
    
    # Start crawling in background
    background_tasks.add_task(run_crawl_job, job_id, request)
    
    logging.info(f"Created crawl job {job_id} for {request.url}")
    
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Crawl job created and queued successfully",
        created_at=job_data["created_at"],
        url=request.url
    )

@app.get("/api/v1/jobs", response_model=JobListResponse, tags=["Job Management"])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip")
):
    """
    List all crawl jobs with optional filtering
    
    - **status**: Filter by job status (queued, running, completed, failed, cancelled)
    - **limit**: Maximum number of results (default: 100)
    - **offset**: Pagination offset (default: 0)
    """
    # Combine active and completed jobs
    all_jobs = {**active_jobs, **completed_jobs}
    
    # Filter by status if specified
    if status:
        filtered_jobs = {
            job_id: job for job_id, job in all_jobs.items()
            if job["status"] == status
        }
    else:
        filtered_jobs = all_jobs
    
    # Sort by created_at (newest first)
    sorted_jobs = sorted(
        filtered_jobs.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )
    
    # Apply pagination
    paginated_jobs = sorted_jobs[offset:offset + limit]
    
    # Format response
    job_list = [
        {
            "job_id": job["job_id"],
            "status": job["status"],
            "url": job["url"],
            "created_at": job["created_at"],
            "completed_at": job.get("completed_at"),
            "progress": job["progress"]
        }
        for job in paginated_jobs
    ]
    
    return JobListResponse(
        total=len(all_jobs),
        active=len(active_jobs),
        completed=len(completed_jobs),
        jobs=job_list
    )

@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Job Management"])
async def get_job_status(job_id: str):
    """
    Get detailed status of a specific crawl job
    
    - **job_id**: Unique identifier of the crawl job
    """
    # Check active jobs first
    if job_id in active_jobs:
        job = active_jobs[job_id]
    elif job_id in completed_jobs:
        job = completed_jobs[job_id]
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        url=job["url"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        config=job["config"],
        progress=job["progress"],
        results=job.get("results"),
        error=job.get("error")
    )

@app.get("/api/v1/jobs/{job_id}/results", tags=["Results"])
async def get_job_results(job_id: str):
    """
    Get the results of a completed crawl job
    
    - **job_id**: Unique identifier of the crawl job
    """
    # Check for job
    if job_id in active_jobs:
        job = active_jobs[job_id]
    elif job_id in completed_jobs:
        job = completed_jobs[job_id]
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Check if job is completed, failed, or cancelled
    if job["status"] not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not yet completed. Current status: {job['status']}"
        )
    
    if job["status"] == JobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": job.get("error", "Unknown error occurred"),
            "partial_results": job.get("results", {})
        }
    
    if job["status"] == JobStatus.CANCELLED:
        return {
            "job_id": job_id,
            "status": "cancelled",
            "url": job["url"],
            "completed_at": job.get("completed_at"),
            "partial_results": job.get("results", {})
        }
    
    return {
        "job_id": job_id,
        "status": "completed",
        "url": job["url"],
        "completed_at": job["completed_at"],
        "results": job.get("results", {})
    }

@app.delete("/api/v1/jobs/{job_id}", tags=["Job Management"])
async def cancel_job(job_id: str):
    """
    Cancel a running or queued crawl job
    
    - **job_id**: Unique identifier of the crawl job to cancel
    """
    # Check if job exists in active jobs
    if job_id not in active_jobs:
        if job_id in completed_jobs:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is already completed and cannot be cancelled"
            )
        else:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = active_jobs[job_id]
    
    # Set cancellation flag (will be picked up by crawler loop)
    job["_cancelled"] = True
    
    # Cancel the task if it's running
    if job.get("task") and not job["task"].done():
        job["task"].cancel()
    
    # Update job status
    job["status"] = JobStatus.CANCELLED
    job["completed_at"] = datetime.utcnow().isoformat()
    
    # Move to completed jobs
    completed_jobs[job_id] = job
    del active_jobs[job_id]
    
    logging.info(f"Cancelled job {job_id}")
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully",
        "cancelled_at": job["completed_at"]
    }

@app.delete("/api/v1/jobs", tags=["Job Management"])
async def clear_completed_jobs():
    """Clear all completed jobs from memory"""
    count = len(completed_jobs)
    completed_jobs.clear()
    
    logging.info(f"Cleared {count} completed jobs")
    
    return {
        "message": f"Cleared {count} completed jobs",
        "remaining_active": len(active_jobs)
    }

@app.get("/api/v1/stats", tags=["Statistics"])
async def get_statistics():
    """Get overall API statistics"""
    all_jobs = {**active_jobs, **completed_jobs}
    
    total_urls = sum(job["progress"].get("urls_visited", 0) for job in all_jobs.values())
    total_subdomains = sum(job["progress"].get("subdomains_found", 0) for job in all_jobs.values())
    total_paths = sum(job["progress"].get("paths_found", 0) for job in all_jobs.values())
    
    status_counts = {}
    for status in JobStatus:
        status_counts[status.value] = sum(
            1 for job in all_jobs.values() if job["status"] == status
        )
    
    return {
        "total_jobs": len(all_jobs),
        "active_jobs": len(active_jobs),
        "completed_jobs": len(completed_jobs),
        "status_breakdown": status_counts,
        "aggregate_stats": {
            "total_urls_crawled": total_urls,
            "total_subdomains_discovered": total_subdomains,
            "total_paths_discovered": total_paths
        }
    }


# ============================================================================
# BACKGROUND TASK - CRAWL EXECUTION
# ============================================================================

# Crawler utility functions (adapted from crwlr_async.py)

def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and ensuring proper format"""
    parsed = urlparse(url)
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ''  # Remove fragment
    ))
    return normalized

def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs belong to the same domain"""
    ext1 = tldextract.extract(url1)
    ext2 = tldextract.extract(url2)
    return ext1.domain == ext2.domain and ext1.suffix == ext2.suffix

def get_subdomain(url: str) -> Optional[str]:
    """Extract subdomain from URL"""
    ext = tldextract.extract(url)
    if ext.subdomain and ext.subdomain != 'www':
        return f"{ext.subdomain}.{ext.domain}.{ext.suffix}"
    return None

def should_exclude(url: str, exclude_paths: Optional[str], exclude_subdomains: Optional[str]) -> bool:
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

def extract_urls_from_json(data: Any, base_url: str) -> List[str]:
    """Recursively extract potential URLs from JSON data"""
    urls = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                if value.startswith(('http://', 'https://', '/')):
                    absolute_url = urljoin(base_url, value)
                    urls.append(normalize_url(absolute_url))
            elif isinstance(value, (dict, list)):
                urls.extend(extract_urls_from_json(value, base_url))
    elif isinstance(data, list):
        for item in data:
            urls.extend(extract_urls_from_json(item, base_url))
    return urls


class CrawlerState:
    """State container for a single crawl job - isolated per job"""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.visited_urls: set = set()
        self.found_subdomains: set = set()
        self.found_paths: set = set()
        self.urls_lock = asyncio.Lock()
        self.subdomains_lock = asyncio.Lock()
        self.paths_lock = asyncio.Lock()
        self.shutdown_flag = False
        self.start_time = time.time()


async def crawl_url_api(
    session: aiohttp.ClientSession,
    url: str,
    base_domain: str,
    depth: int,
    config: 'CrawlRequest',
    custom_headers: Dict[str, str],
    semaphore: asyncio.Semaphore,
    state: CrawlerState,
    job: Dict[str, Any]
) -> List[tuple]:
    """Crawl a single URL and extract links - API version"""
    
    if state.shutdown_flag:
        return []
    
    async with state.urls_lock:
        if url in state.visited_urls:
            return []
        state.visited_urls.add(url)
    
    # Update job progress
    job["progress"]["urls_visited"] = len(state.visited_urls)
    
    if config.verbose:
        logging.debug(f"[{state.job_id}] Visiting {url} (depth: {depth})")
    
    new_urls = []
    
    try:
        # Rate limiting
        await asyncio.sleep(config.rate_limit)
        
        # Build headers
        user_agent = config.user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        headers.update(custom_headers)
        
        async with semaphore:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=config.timeout),
                headers=headers,
                allow_redirects=True
            ) as response:
                
                if response.status == 200:
                    final_url = str(response.url)
                    
                    async with state.paths_lock:
                        if is_same_domain(url, base_domain):
                            if url not in state.found_paths:
                                state.found_paths.add(url)
                        if final_url != url and is_same_domain(final_url, base_domain):
                            if final_url not in state.found_paths:
                                state.found_paths.add(final_url)
                    
                    # Update progress
                    job["progress"]["paths_found"] = len(state.found_paths)
                    
                    # Extract subdomain from final URL
                    subdomain = get_subdomain(final_url)
                    if subdomain:
                        async with state.subdomains_lock:
                            if subdomain not in state.found_subdomains:
                                state.found_subdomains.add(subdomain)
                                job["progress"]["subdomains_found"] = len(state.found_subdomains)
                                logging.info(f"[{state.job_id}] Found subdomain: {subdomain}")
                    
                    content_type = response.headers.get('Content-Type', '').lower()
                    potential_urls = []
                    
                    if 'application/json' in content_type:
                        try:
                            data = await response.json()
                            potential_urls = extract_urls_from_json(data, url)
                        except json.JSONDecodeError:
                            pass
                    
                    elif 'text/html' in content_type:
                        text = await response.text()
                        soup = BeautifulSoup(text, 'html.parser')
                        
                        for link in soup.find_all('a', href=True):
                            if state.shutdown_flag:
                                break
                            
                            href = link.get('href')
                            absolute_url = urljoin(url, href)
                            normalized = normalize_url(absolute_url)
                            potential_urls.append(normalized)
                    
                    # Process potential URLs
                    for normalized in potential_urls:
                        if state.shutdown_flag:
                            break
                        
                        parsed = urlparse(normalized)
                        
                        if parsed.scheme not in ['http', 'https']:
                            continue
                        
                        if should_exclude(normalized, config.exclude_paths, config.exclude_subdomains):
                            continue
                        
                        if is_same_domain(normalized, base_domain):
                            subdomain = get_subdomain(normalized)
                            if subdomain:
                                async with state.subdomains_lock:
                                    if subdomain not in state.found_subdomains:
                                        state.found_subdomains.add(subdomain)
                                        job["progress"]["subdomains_found"] = len(state.found_subdomains)
                                        logging.info(f"[{state.job_id}] Found subdomain: {subdomain}")
                            
                            if depth < config.max_depth:
                                new_urls.append((normalized, depth + 1))
    
    except asyncio.TimeoutError:
        if config.verbose:
            logging.debug(f"[{state.job_id}] Timeout: {url}")
    except aiohttp.ClientError as e:
        if config.verbose:
            logging.debug(f"[{state.job_id}] Client error for {url}: {str(e)[:50]}")
    except Exception as e:
        if config.verbose:
            logging.debug(f"[{state.job_id}] Error for {url}: {str(e)[:50]}")
    
    # Update current depth
    job["progress"]["current_depth"] = depth
    
    return new_urls


async def run_crawl_job(job_id: str, config: CrawlRequest):
    """
    Execute the actual crawling job in the background
    Full integration with crawler logic from crwlr_async.py
    """
    job = active_jobs.get(job_id)
    if not job:
        return
    
    # Initialize crawler state for this job
    state = CrawlerState(job_id)
    
    try:
        # Update status to running
        job["status"] = JobStatus.RUNNING
        job["started_at"] = datetime.utcnow().isoformat()
        
        logging.info(f"Starting crawl job {job_id} for {config.url}")
        
        # Normalize base URL
        base_url = normalize_url(config.url)
        
        # Parse custom headers
        custom_headers = config.custom_headers or {}
        
        # Setup connector for proxy support
        connector = None
        if config.socks:
            try:
                from aiosocks.connector import ProxyConnector
                connector = ProxyConnector.from_url(config.socks)
                logging.info(f"[{job_id}] Using SOCKS proxy: {config.socks}")
            except Exception as e:
                logging.warning(f"[{job_id}] Failed to setup SOCKS proxy: {e}")
        elif config.proxy:
            connector = aiohttp.TCPConnector()
            logging.info(f"[{job_id}] Using HTTP proxy: {config.proxy}")
        
        # Queue of URLs to visit (url, depth)
        urls_to_visit = [(base_url, 0)]
        
        # Create semaphore for concurrent workers
        semaphore = asyncio.Semaphore(config.workers)
        
        # Create aiohttp session
        async with aiohttp.ClientSession(connector=connector) as session:
            while urls_to_visit and not state.shutdown_flag:
                # Check if job was cancelled
                if job.get("_cancelled", False):
                    state.shutdown_flag = True
                    break
                
                # Get batch of URLs to process
                batch_size = min(config.workers * 2, len(urls_to_visit))
                batch = []
                for _ in range(batch_size):
                    if urls_to_visit and not state.shutdown_flag:
                        batch.append(urls_to_visit.pop(0))
                
                # Create tasks
                tasks = [
                    crawl_url_api(
                        session, url, base_url, depth,
                        config, custom_headers, semaphore, state, job
                    )
                    for url, depth in batch
                ]
                
                # Run tasks concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect new URLs
                for result in results:
                    if isinstance(result, Exception):
                        if config.verbose:
                            logging.debug(f"[{job_id}] Task error: {str(result)[:50]}")
                        continue
                    if result:
                        async with state.urls_lock:
                            new_unique_urls = [u for u in result if u[0] not in state.visited_urls]
                        urls_to_visit.extend(new_unique_urls)
        
        # Calculate metrics
        elapsed_time = time.time() - state.start_time
        crawl_speed = len(state.visited_urls) / elapsed_time if elapsed_time > 0 else 0
        
        # Update final progress
        job["progress"] = {
            "urls_visited": len(state.visited_urls),
            "subdomains_found": len(state.found_subdomains),
            "paths_found": len(state.found_paths),
            "current_depth": config.max_depth
        }
        
        # Store results
        job["results"] = {
            "subdomains": sorted(list(state.found_subdomains)),
            "paths": sorted(list(state.found_paths)),
            "visited_urls": sorted(list(state.visited_urls)),
            "stats": {
                "total_subdomains": len(state.found_subdomains),
                "total_paths": len(state.found_paths),
                "total_visited": len(state.visited_urls)
            },
            "metrics": {
                "total_time_seconds": round(elapsed_time, 2),
                "crawl_speed_urls_per_second": round(crawl_speed, 2),
                "avg_time_per_url_seconds": round(elapsed_time / len(state.visited_urls), 3) if state.visited_urls else 0
            }
        }
        
        # Mark as completed
        job["status"] = JobStatus.COMPLETED
        job["completed_at"] = datetime.utcnow().isoformat()
        
        # Move to completed jobs
        completed_jobs[job_id] = job
        if job_id in active_jobs:
            del active_jobs[job_id]
        
        logging.info(f"Completed crawl job {job_id}: {len(state.visited_urls)} URLs, {len(state.found_subdomains)} subdomains, {len(state.found_paths)} paths")
        
    except asyncio.CancelledError:
        job["status"] = JobStatus.CANCELLED
        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = {
            "urls_visited": len(state.visited_urls),
            "subdomains_found": len(state.found_subdomains),
            "paths_found": len(state.found_paths),
            "current_depth": job["progress"].get("current_depth", 0)
        }
        # Save partial results
        job["results"] = {
            "subdomains": sorted(list(state.found_subdomains)),
            "paths": sorted(list(state.found_paths)),
            "visited_urls": sorted(list(state.visited_urls)),
            "stats": {
                "total_subdomains": len(state.found_subdomains),
                "total_paths": len(state.found_paths),
                "total_visited": len(state.visited_urls),
                "partial": True
            }
        }
        completed_jobs[job_id] = job
        if job_id in active_jobs:
            del active_jobs[job_id]
        logging.info(f"Job {job_id} was cancelled")
        
    except Exception as e:
        job["status"] = JobStatus.FAILED
        job["error"] = str(e)
        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = {
            "urls_visited": len(state.visited_urls),
            "subdomains_found": len(state.found_subdomains),
            "paths_found": len(state.found_paths),
            "current_depth": job["progress"].get("current_depth", 0)
        }
        # Save partial results even on failure
        job["results"] = {
            "subdomains": sorted(list(state.found_subdomains)),
            "paths": sorted(list(state.found_paths)),
            "visited_urls": sorted(list(state.visited_urls)),
            "stats": {
                "total_subdomains": len(state.found_subdomains),
                "total_paths": len(state.found_paths),
                "total_visited": len(state.visited_urls),
                "partial": True,
                "error": str(e)
            }
        }
        logging.error(f"Job {job_id} failed: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        
        completed_jobs[job_id] = job
        if job_id in active_jobs:
            del active_jobs[job_id]


# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize API on startup"""
    logging.info("CRWLR API starting up...")
    
    # Create results directory if it doesn't exist
    os.makedirs("./results", exist_ok=True)
    
    logging.info("CRWLR API ready to accept requests")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logging.info("CRWLR API shutting down...")
    
    # Cancel all active jobs
    for job_id, job in list(active_jobs.items()):
        if job.get("task") and not job["task"].done():
            job["task"].cancel()
    
    logging.info("CRWLR API shutdown complete")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )