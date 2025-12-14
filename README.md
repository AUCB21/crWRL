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

## Installation 📦

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- PostgreSQL (optional, for database features)

### Dependencies

- requests>=2.31.0
- beautifulsoup4>=4.12.0
- tldextract>=5.1.0
- tqdm>=4.66.0
- aiohttp>=3.9.0
- aiosocks>=0.1.0
- psycopg2-binary>=2.9.0 (if using PostgreSQL)
- python-dotenv (for environment configuration)

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

### Basic Usage

```bash
python crwlr_async.py -u https://example.com
```

### Advanced Examples

**Fast scan with more workers:**

```bash
python crwlr_async.py -u https://example.com -w 10 -r 0.2
```

**Deep scan with maximum depth:**

```bash
python crwlr_async.py -u https://example.com -d 5
```

**Save results to files:**

```bash
python crwlr_async.py -u https://example.com -o results
```

**Export to JSON:**

```bash
python crwlr_async.py -u https://example.com -o output -j
```

**Verbose mode with custom User-Agent:**

```bash
python crwlr_async.py -u https://example.com -v -a "MyBot/1.0"
```

**Scan with authentication cookie:**

```bash
python crwlr_async.py -u https://example.com -H "Cookie: session=abc123"
```

**Multiple custom headers:**

```bash
python crwlr_async.py -u https://example.com -H "Cookie: session=abc" -H "Authorization: Bearer token123"
```

**Load headers from file:**

```bash
python crwlr_async.py -u https://example.com --headers-file headers.txt
```

**Exclude specific paths and subdomains:**

```bash
python crwlr_async.py -u https://example.com --exclude-paths "/admin/.*" --exclude-subdomains "test\..*"
```

**Use HTTP/HTTPS proxy:**

```bash
python crwlr_async.py -u https://example.com --proxy http://proxy.example.com:8080
```

**Use SOCKS proxy:**

```bash
python crwlr_async.py -u https://example.com --socks socks5://user:pass@proxy.example.com:1080
```

**Full-featured scan:**

```bash
python crwlr_async.py -u https://example.com -w 10 -d 4 -r 0.3 -o results -j -v
```

## Command Line Options 🎛️

| Option                  | Description                                              | Default    |
| ----------------------- | -------------------------------------------------------- | ---------- |
| `-u, --url`            | Target URL to scan (required)                            | -          |
| `-v, --verbose`        | Show detailed output including errors                    | False      |
| `-o, --output`         | Save results with this prefix                            | None       |
| `-t, --timeout`        | HTTP request timeout in seconds                          | 5          |
| `-d, --max-depth`      | Maximum crawling depth                                   | 3          |
| `-w, --workers`        | Number of concurrent async workers                       | 5          |
| `-r, --rate-limit`     | Delay between requests (seconds)                         | 0.5        |
| `-a, --user-agent`     | Custom User-Agent string                                 | Chrome/120 |
| `-j, --json`           | Export results to JSON format                            | False      |
| `-H, --header`         | Custom HTTP header (can be used multiple times)          | None       |
| `--headers-file`       | File containing custom headers (one per line)            | None       |
| `--exclude-paths`      | Regex pattern to exclude paths                           | None       |
| `--exclude-subdomains` | Regex pattern to exclude subdomains                      | None       |
| `--proxy`              | HTTP/HTTPS proxy URL                                     | None       |
| `--socks`              | SOCKS proxy URL (e.g., socks5://user:pass@host:port)    | None       |
| `-h, --help`           | Show help message                                        | -          |

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
