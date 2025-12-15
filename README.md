# CRWLR - URL Crawler Bot🔍

A powerful and fast asynchronous web crawler designed to discover subdomains and internal paths from any website/API by analyzing HTML source code and headers responses, following internal links recursively.

## Features:

- **Subdomain Discovery**: Automatically finds all subdomains belonging to the target domain
- **Path Extraction**: Maps all internal paths and routes
- **Async/Await Architecture**: Lightning-fast concurrent crawling with configurable async workers
- **Smart Crawling**: Respects rate limits and avoids duplicate visits
- **Progress Tracking**: Real-time progress bar with statistics using tqdm
- **Multiple Export Formats**: Save results as TXT and/or JSON
- **Custom Headers**: Support for custom HTTP headers and authentication
- **Headers from File**: Load multiple custom headers from a file
- **Proxy Support**: HTTP/HTTPS and SOCKS proxy support
- **Pattern Exclusion**: Exclude specific paths and subdomains using regex patterns
- **Custom User-Agent**: Avoid being blocked with customizable headers
- **Depth Control**: Prevent infinite loops with max depth limiting
- **Database Integration**: PostgreSQL database support via psycopg2
- **Environment Configuration**: .env file support for configuration management
- **Colorful Output**: Beautiful terminal output with color-coded messages
- **Detailed Logging**: Debug logging to file for troubleshooting

## Requirements 📋

### Prerequisites

- **Python 3.7 or higher** - The crawler uses async/await syntax and modern Python features
- **pip** - Python package manager for installing dependencies
- **Virtual environment** (recommended) - For isolated dependency management
- **PostgreSQL** (optional) - For legacy database features
- **SQLite** (built-in) - Used for crawl data storage via the `--db` flag

### Python Dependencies

The following packages are required and listed in `requirements.txt`:

```
requests>=2.31.0          # HTTP library for making web requests
beautifulsoup4>=4.12.0    # HTML parsing and extraction
tldextract>=5.1.0         # Domain and subdomain extraction
tqdm>=4.66.0              # Progress bars and status updates
aiohttp>=3.9.0            # Async HTTP client/server framework
aiosocks>=0.1.0           # SOCKS proxy support for aiohttp
psycopg2-binary>=2.9.0    # PostgreSQL adapter (optional, for legacy DB)
python-dotenv>=1.0.0      # Environment variable management from .env files
```

**Core Dependencies:**
- **requests**: Synchronous HTTP requests (legacy compatibility)
- **beautifulsoup4**: Parse HTML and extract links from web pages
- **tldextract**: Intelligent domain/subdomain extraction and validation
- **tqdm**: Beautiful progress bars with real-time statistics
- **aiohttp**: High-performance async HTTP client for concurrent crawling
- **aiosocks**: SOCKS4/SOCKS5 proxy support for aiohttp sessions

**Optional Dependencies:**
- **psycopg2-binary**: PostgreSQL database support for legacy features
- **python-dotenv**: Load database configuration from `.env` files

### Setup

1. Clone the repository:

```bash
git clone https://github.com/AUCB21/CRWLR.git
cd CRWLR
```

2. Create and activate virtual environment:

```bash
python -m venv env
# On Windows:
env\Scripts\activate
# On Linux/Mac:
source env/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. (Optional) Configure database connection:

Create a `.env` file in the project root:

```bash
DB_HOST='your_db_host_here'
DB_PORT='your_db_port_here'
```

## Usage 🚀

### Quick Start

Simplest way to start crawling:

```bash
python crwlr_async.py -u https://example.com
```

This will:
- Crawl `https://example.com` with default settings
- Display real-time progress in the terminal
- Show discovered subdomains and paths
- Use 5 concurrent workers with 0.5s delay between requests
- Crawl up to 3 levels deep

### Common Usage Patterns

#### Basic Scan with Output Files

```bash
python crwlr_async.py -u https://example.com -o results
```

Creates:
- `results_subdomains.txt` - List of discovered subdomains
- `results_paths.txt` - List of all discovered paths

#### Fast Scan (Performance Optimized)

```bash
python crwlr_async.py -u https://example.com -w 10 -r 0.2
```

- `-w 10`: Uses 10 concurrent workers (faster)
- `-r 0.2`: Reduces delay to 0.2 seconds between requests

#### Deep Scan (Maximum Coverage)

```bash
python crwlr_async.py -u https://example.com -d 5
```

- `-d 5`: Crawls up to 5 levels deep (finds more hidden paths)

#### Save to Database

```bash
python crwlr_async.py -u https://example.com --db results/crawl.db
```

Stores all crawl data in a SQLite database for later analysis.

#### Export to JSON Format

```bash
python crwlr_async.py -u https://example.com -o results -j
```

Creates `results_results.json` with structured data including:
- All discovered subdomains
- All discovered paths  
- Statistics and metadata

#### Verbose Mode (Detailed Output)

```bash
python crwlr_async.py -u https://example.com -v
```

Shows:
- All visited URLs in real-time
- Error messages and warnings
- Detailed crawling progress

#### Custom User-Agent

```bash
python crwlr_async.py -u https://example.com -a "MyBot/1.0"
```

Helps avoid being blocked or identified as a bot.

### Advanced Examples

#### Authentication with Cookies

#### Authentication with Cookies

```bash
python crwlr_async.py -u https://example.com -H "Cookie: session=abc123"
```

Access authenticated areas by passing session cookies.

#### Multiple Custom Headers

```bash
python crwlr_async.py -u https://example.com -H "Cookie: session=abc" -H "Authorization: Bearer token123"
```

Add multiple headers for complex authentication scenarios.

#### Load Headers from File

```bash
python crwlr_async.py -u https://example.com --headers-file headers.txt
```

**headers.txt format:**
```
Cookie: session=abc123
Authorization: Bearer token456
X-API-Key: your-api-key
```

#### Pattern Exclusion (Filtering)

```bash
python crwlr_async.py -u https://example.com --exclude-paths "/admin/.*" --exclude-subdomains "test\..*"
```

- `--exclude-paths`: Skip paths matching regex (e.g., admin panels)
- `--exclude-subdomains`: Skip subdomains matching regex (e.g., test environments)

#### Proxy Support (HTTP/HTTPS)

```bash
python crwlr_async.py -u https://example.com --proxy http://proxy.example.com:8080
```

Route all traffic through an HTTP or HTTPS proxy.

#### SOCKS Proxy Support

```bash
python crwlr_async.py -u https://example.com --socks socks5://user:pass@proxy.example.com:1080
```

Supports SOCKS4 and SOCKS5 proxies with authentication.

#### Full-Featured Production Scan

```bash
python crwlr_async.py -u https://example.com -w 10 -d 4 -r 0.3 -o results -j -v --db crawl.db
```

Combines multiple features:
- 10 concurrent workers (`-w 10`)
- 4 levels deep (`-d 4`)
- 0.3s delay (`-r 0.3`)
- Save to files (`-o results`)
- JSON export (`-j`)
- Verbose output (`-v`)
- Database storage (`--db crawl.db`)

#### Timeout Configuration

```bash
python crwlr_async.py -u https://example.com -t 10
```

Increase timeout for slow servers (default is 5 seconds).

#### Custom Buffer Size for Database

```bash
python crwlr_async.py -u https://example.com --db crawl.db --buffer-size 200
```

Buffer 200 records before flushing to database (default: 100).

## Parametrization Guide 🎛️

### Core Parameters

#### `-u, --url` (Required)
**Type:** String  
**Description:** Target URL to scan. Must include protocol (`http://` or `https://`)  
**Example:** `-u https://example.com`

#### `-v, --verbose`
**Type:** Flag (boolean)  
**Description:** Enable detailed output showing all visited URLs, errors, and debugging information  
**Default:** False  
**Example:** `-v`

### Output Parameters

#### `-o, --output`
**Type:** String  
**Description:** Output file prefix for saving results. Creates `PREFIX_subdomains.txt` and `PREFIX_paths.txt`  
**Default:** None (no files created)  
**Example:** `-o results`

#### `-j, --json`
**Type:** Flag (boolean)  
**Description:** Export results in JSON format to `PREFIX_results.json`  
**Default:** False  
**Requires:** `-o` flag must be set  
**Example:** `-j -o output`

#### `--db`
**Type:** String  
**Description:** SQLite database file path for storing crawl data. Creates database if it doesn't exist  
**Default:** None  
**Example:** `--db results/crawl.db`

#### `--buffer-size`
**Type:** Integer  
**Description:** Number of records to buffer in memory before flushing to database  
**Default:** 100  
**Valid Range:** 1-10000  
**Example:** `--buffer-size 200`

### Performance Parameters

#### `-w, --workers`
**Type:** Integer  
**Description:** Number of concurrent async workers for parallel crawling  
**Default:** 5  
**Recommended Range:** 3-20  
**Impact:** Higher = faster but more aggressive  
**Example:** `-w 10`

#### `-r, --rate-limit`
**Type:** Float  
**Description:** Delay in seconds between requests to avoid overwhelming servers  
**Default:** 0.5  
**Recommended Range:** 0.1-2.0  
**Impact:** Lower = faster but more aggressive  
**Example:** `-r 0.3`

#### `-t, --timeout`
**Type:** Integer  
**Description:** HTTP request timeout in seconds  
**Default:** 5  
**Recommended Range:** 3-30  
**Example:** `-t 10`

#### `-d, --max-depth`
**Type:** Integer  
**Description:** Maximum crawling depth to prevent infinite loops and limit scope  
**Default:** 3  
**Recommended Range:** 2-6  
**Impact:** Higher = more coverage but slower and more URLs  
**Example:** `-d 4`

### HTTP Configuration Parameters

#### `-a, --user-agent`
**Type:** String  
**Description:** Custom User-Agent header to identify your crawler or mimic browsers  
**Default:** `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"`  
**Example:** `-a "MyBot/1.0 (https://mysite.com)"`

#### `-H, --header`
**Type:** String (can be used multiple times)  
**Description:** Add custom HTTP headers. Format: `'Header-Name: value'`  
**Default:** None  
**Example:** `-H "Authorization: Bearer token123" -H "Cookie: session=abc"`

#### `--headers-file`
**Type:** String (file path)  
**Description:** Load custom headers from a file (one header per line)  
**Format:** Each line should be `Header-Name: value`. Lines starting with `#` are ignored  
**Example:** `--headers-file headers.txt`

### Filtering Parameters

#### `--exclude-paths`
**Type:** String (regex pattern)  
**Description:** Regular expression to exclude specific URL paths from crawling  
**Default:** None  
**Example:** `--exclude-paths "/admin/.*|/test/.*"`  
**Use Cases:** Skip admin panels, test pages, logout URLs

#### `--exclude-subdomains`
**Type:** String (regex pattern)  
**Description:** Regular expression to exclude specific subdomains from crawling  
**Default:** None  
**Example:** `--exclude-subdomains "test\..*|dev\..*"`  
**Use Cases:** Skip test/dev environments, staging servers

### Proxy Parameters

#### `--proxy`
**Type:** String (URL)  
**Description:** HTTP or HTTPS proxy server URL  
**Format:** `http://[user:pass@]host:port` or `https://[user:pass@]host:port`  
**Default:** None  
**Example:** `--proxy http://proxy.example.com:8080`

#### `--socks`
**Type:** String (URL)  
**Description:** SOCKS proxy server URL (supports SOCKS4 and SOCKS5)  
**Format:** `socks4://[user:pass@]host:port` or `socks5://[user:pass@]host:port`  
**Default:** None  
**Example:** `--socks socks5://user:pass@proxy.example.com:1080`

### Parameter Combinations & Recommendations

#### For Small Websites (< 100 pages)
```bash
python crwlr_async.py -u https://small-site.com -w 3 -d 4 -r 0.5
```

#### For Medium Websites (100-1000 pages)
```bash
python crwlr_async.py -u https://medium-site.com -w 5 -d 3 -r 0.3 -o results
```

#### For Large Websites (> 1000 pages)
```bash
python crwlr_async.py -u https://large-site.com -w 10 -d 2 -r 0.2 --db crawl.db
```

#### For Slow or Unstable Servers
```bash
python crwlr_async.py -u https://slow-site.com -w 3 -r 1.0 -t 15
```

#### For Authenticated Scanning
```bash
python crwlr_async.py -u https://app.example.com -H "Cookie: session=token" -d 4 -o results
```

#### For Stealth/Respectful Scanning
```bash
python crwlr_async.py -u https://target.com -w 2 -r 1.5 -a "ResearchBot/1.0"
```

## Command Line Options 🎛️

### Complete Options Table

| Option                  | Type    | Description                                              | Default    | Required |
| ----------------------- | ------- | -------------------------------------------------------- | ---------- | -------- |
| `-u, --url`            | String  | Target URL to scan                                       | -          | ✅ Yes   |
| `-v, --verbose`        | Flag    | Show detailed output including errors                    | False      | No       |
| `-o, --output`         | String  | Save results with this prefix                            | None       | No       |
| `-t, --timeout`        | Integer | HTTP request timeout in seconds                          | 5          | No       |
| `-d, --max-depth`      | Integer | Maximum crawling depth                                   | 3          | No       |
| `-w, --workers`        | Integer | Number of concurrent async workers                       | 5          | No       |
| `-r, --rate-limit`     | Float   | Delay between requests (seconds)                         | 0.5        | No       |
| `-a, --user-agent`     | String  | Custom User-Agent string                                 | Chrome/120 | No       |
| `-j, --json`           | Flag    | Export results to JSON format                            | False      | No       |
| `-H, --header`         | String  | Custom HTTP header (repeatable)                          | None       | No       |
| `--headers-file`       | String  | File containing custom headers (one per line)            | None       | No       |
| `--exclude-paths`      | String  | Regex pattern to exclude paths                           | None       | No       |
| `--exclude-subdomains` | String  | Regex pattern to exclude subdomains                      | None       | No       |
| `--proxy`              | String  | HTTP/HTTPS proxy URL                                     | None       | No       |
| `--socks`              | String  | SOCKS proxy URL (socks4/socks5)                          | None       | No       |
| `--db`                 | String  | SQLite database file for storing results                 | None       | No       |
| `--buffer-size`        | Integer | Records to buffer before DB flush                        | 100        | No       |
| `-h, --help`           | Flag    | Show help message and exit                               | -          | No       |

## Output Formats 📄

### Terminal Output

The tool displays:

- Real-time progress bar
- Discovered subdomains as they're found
- Final statistics (URLs visited, subdomains found, paths discovered)
- Crawling speed (URLs/second)

### Text Files

When using `-o PREFIX`:

- `PREFIX_subdomains.txt`: List of discovered subdomains
- `PREFIX_paths.txt`: List of all discovered paths

### JSON Output

When using `-j` flag, creates `PREFIX_results.json`:

```json
{
  "subdomains": ["sub1.example.com", "sub2.example.com"],
  "paths": ["https://example.com/path1", "https://example.com/path2"],
  "visited_urls": ["..."],
  "stats": {
    "total_subdomains": 2,
    "total_paths": 150,
    "total_visited": 200
  }
}
```

## How It Works 🔧

1. **Initial Request**: Fetches the base URL's HTML content using aiohttp
2. **Link Extraction**: Parses all `<a>` tags and their `href` attributes using BeautifulSoup4
3. **URL Normalization**: Converts relative URLs to absolute URLs
4. **Domain Validation**: Checks if URLs belong to the target domain using tldextract
5. **Subdomain Detection**: Identifies and reports subdomains
6. **Recursive Crawling**: Follows internal links up to max depth asynchronously
7. **Async Safety**: Uses asyncio locks to prevent race conditions
8. **Rate Limiting**: Adds delays between requests to be respectful
9. **Pattern Filtering**: Applies regex exclusion patterns for paths and subdomains
10. **Proxy Support**: Routes requests through HTTP/HTTPS or SOCKS proxies if configured

## Best Practices 💡

- **Start Conservative**: Use default settings first, then optimize
- **Respect Servers**: Don't set rate limit too low or workers too high
- **Use Appropriate Depth**: Level 3-4 is usually sufficient for most sites
- **Monitor Resources**: High worker count may consume significant bandwidth
- **Check robots.txt**: Ensure you're allowed to crawl the target site
- **Use Responsibly**: Only scan sites you have permission to test
- **Custom Headers**: Use authentication headers when needed for protected areas
- **Proxy Configuration**: Use proxies to distribute load and avoid IP blocking
- **Pattern Exclusion**: Exclude test/staging subdomains and sensitive paths
- **Debug Logging**: Check debug.log file for detailed error information

## Performance Tips ⚡

- **More Workers**: Increase `-w` for faster scanning (be careful with rate limits)
- **Lower Rate Limit**: Decrease `-r` if the server can handle more requests
- **Adjust Depth**: Lower `-d` for quicker scans of large sites
- **JSON Output**: Use `-j` for easier post-processing and automation
- **Async Advantage**: The async architecture allows handling hundreds of concurrent requests efficiently
- **Proxy Rotation**: Use different proxies to distribute load and avoid rate limiting
- **Exclude Patterns**: Use regex exclusions to skip unnecessary paths and speed up scans

## Troubleshooting 🔧

**Script is slow:**

- Increase workers: `-w 10`
- Decrease rate limit: `-r 0.2`

**Getting blocked:**

- Increase rate limit: `-r 1.0`
- Use custom User-Agent: `-a "YourBot/1.0"`

**Too many URLs:**

- Reduce max depth: `-d 2`
- Check if site has pagination loops

**Timeout errors:**

- Increase timeout: `-t 10`
- Check internet connection
- Use proxy if connection is unstable

**Header issues:**

- Check header format: `'Name: Value'`
- Verify headers file syntax (one header per line)
- Test authentication tokens separately

**Database connection issues:**

- Verify `.env` file configuration
- Check PostgreSQL is running
- Review `debug.log` for connection errors

## Project Structure 📁

```
CRWLR/
├── crwlr_async.py          # Main crawler application
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── .env                    # Environment configuration (create this)
├── debug.log               # Debug logging output (auto-generated)
├── DataBase/               # Database module
│   ├── config.py          # Database configuration
│   └── db_commands.py     # Database commands
└── env/                    # Virtual environment (auto-generated)
```

## Pending Features 🚧

The following features are planned for future releases:

### File-Based Input for Rotation

Currently, the crawler supports single values for most configuration options. Future versions will support reading from files for automatic rotation:

#### User-Agent Rotation
**Status:** Planned  
**Current:** Single user-agent via `-a "User-Agent String"`  
**Planned:** `--agents-file agents.txt` - Load multiple user-agents from file and rotate automatically

**Use Case:** Avoid detection by varying user-agent strings across requests

**Example agents.txt:**
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15
Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0
```

#### Proxy Rotation
**Status:** Planned  
**Current:** Single HTTP/HTTPS proxy via `--proxy http://proxy.com:8080`  
**Planned:** `--proxies-file proxies.txt` - Load multiple proxies and rotate per request

**Use Case:** Distribute load across multiple proxies, avoid rate limiting and IP bans

**Example proxies.txt:**
```
http://proxy1.example.com:8080
http://user:pass@proxy2.example.com:3128
https://proxy3.example.com:8443
```

#### SOCKS Proxy Rotation
**Status:** Planned  
**Current:** Single SOCKS proxy via `--socks socks5://proxy.com:1080`  
**Planned:** `--socks-file socks.txt` - Load multiple SOCKS proxies and rotate

**Use Case:** Similar to HTTP proxy rotation but using SOCKS protocol

**Example socks.txt:**
```
socks5://user:pass@proxy1.example.com:1080
socks4://proxy2.example.com:1080
socks5://proxy3.example.com:9050
```

#### Cookie File Support
**Status:** Planned  
**Current:** Cookies can be passed via `-H "Cookie: name=value"` or `--headers-file`  
**Planned:** `--cookies-file cookies.txt` - Dedicated cookie file support with Netscape/JSON formats

**Use Case:** Easier cookie management, browser export compatibility, session rotation

**Example cookies.txt (Netscape format):**
```
# Netscape HTTP Cookie File
.example.com    TRUE    /    FALSE    1735689600    session_id    abc123xyz
.example.com    TRUE    /    FALSE    1735689600    user_token   token456
```

**Example cookies.json:**
```json
[
  {"name": "session_id", "value": "abc123xyz", "domain": ".example.com"},
  {"name": "user_token", "value": "token456", "domain": ".example.com"}
]
```

### Additional Planned Features

- **Custom DNS Resolvers:** `--dns-file resolvers.txt` for custom DNS server rotation
- **Request Header Rotation:** Rotate multiple header configurations from file
- **Credential Rotation:** `--credentials-file creds.txt` for testing multiple auth combinations
- **Advanced Rate Limiting:** Per-domain and per-subdomain rate limit configuration
- **Resume Capability:** Save crawl state and resume from interruption
- **Export to Multiple Formats:** CSV, XML, and Markdown export options
- **Automated Screenshot Capture:** Option to capture screenshots of discovered pages
- **JavaScript Rendering:** Support for dynamic content loaded via JavaScript
- **API Mode:** RESTful API interface for integration with other tools

### Contributing Ideas

If you'd like to help implement any of these features or suggest new ones, please:
1. Open an issue on GitHub to discuss the feature
2. Fork the repository and submit a pull request
3. Ensure code follows the existing style and includes tests
4. Update documentation accordingly

## Contributing 🤝

Contributions are welcome! Feel free to:

- Report bugs
- Suggest new features
- Submit pull requests
- Improve documentation

## License 📝

This project is open source and available under the [MIT License](LICENSE).

## Disclaimer ⚠️

This tool is intended for educational and ethical security testing purposes only. Always:

- Obtain proper authorization before scanning any website
- Respect robots.txt and terms of service
- Follow responsible disclosure practices
- Use rate limiting to avoid overwhelming servers

The authors are not responsible for misuse of this tool.

## Author 👤

Created by [@aucb21](https://github.com/AUCB21)

---

⭐ If you find this tool useful, please consider giving it a star on GitHub!
