#!/usr/bin/env uv run
"""
Substack article extractor - strips away Substack UI to get clean article HTML.

Usage:
    uv run superstack.py <substack_url> [output.html]
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "beautifulsoup4",
# ]
# ///

import sys
import re
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup


def extract_post_id(url: str) -> str | None:
    """Extract post ID from Substack inbox URL."""
    # Pattern: https://substack.com/inbox/post/183535301
    match = re.search(r'/inbox/post/(\d+)', url)
    if match:
        return match.group(1)
    return None


def fetch_page(url: str) -> str:
    """Fetch the HTML content of a Substack page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


def extract_article(html: str) -> dict:
    """Extract article content from Substack HTML."""
    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title_elem = soup.find('h1', class_='post-title')
    title = title_elem.get_text(strip=True) if title_elem else 'Untitled'

    # Extract author from meta tag first, then fallback to page content
    author = 'Unknown Author'
    meta_author = soup.find('meta', attrs={'name': 'author'})
    if meta_author and meta_author.get('content'):
        author = meta_author.get('content')
    else:
        # Try JSON-LD data
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                import json
                data = json.loads(json_ld.string)
                if 'author' in data:
                    if isinstance(data['author'], list) and len(data['author']) > 0:
                        author = data['author'][0].get('name', author)
                    elif isinstance(data['author'], dict):
                        author = data['author'].get('name', author)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    # Extract date from JSON-LD or meta
    date = ''
    json_ld = soup.find('script', type='application/ld+json')
    if json_ld:
        try:
            import json
            data = json.loads(json_ld.string)
            date_str = data.get('datePublished', '')
            if date_str:
                # Parse and format date nicely
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date = dt.strftime('%b %d, %Y')
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass

    if not date:
        meta_date = soup.find('meta', property='article:published_time')
        if meta_date:
            date = meta_date.get('content', '')[:10]

    # Extract the main body content
    body_elem = soup.find('div', class_='body markup')
    if not body_elem:
        # Fallback: try to find available-content div
        body_elem = soup.find('div', class_='available-content')

    if not body_elem:
        raise ValueError("Could not find article body in the HTML")

    # Clean up the body - remove unnecessary classes and attributes
    body_html = clean_body(body_elem)

    return {
        'title': title,
        'author': author,
        'date': date,
        'body': body_html
    }


def clean_body(body_elem) -> str:
    """Clean up the body HTML, keeping only essential content."""
    # Create a copy to avoid modifying original
    from copy import copy
    body = copy(body_elem)

    # Remove all buttons, icons, forms, and interactive elements
    for elem in body.find_all(['button', 'svg', 'form', 'input', 'script']):
        elem.decompose()

    # Remove elements with specific classes that are UI-related
    ui_classes = [
        'image-link-expand', 'icon-container', 'restack-image',
        'like-button', 'share-button', 'comment-button',
        'subscription-widget', 'subscribe-widget', 'paywall'
    ]
    for class_name in ui_classes:
        for elem in body.find_all(class_=re.compile(class_name)):
            elem.decompose()

    # Clean up images - simplify to just src
    for img in body.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        # Keep only essential attributes
        img.attrs = {'src': src, 'alt': alt, 'style': 'max-width: 100%; height: auto;'}

    # Remove picture/source elements, keep just img
    for picture in body.find_all('picture'):
        img = picture.find('img')
        if img:
            picture.replace_with(img)

    # Simplify links
    for a in body.find_all('a'):
        href = a.get('href', '')
        text = a.get_text()
        a.attrs = {'href': href}

    # Remove all class and data attributes from remaining elements
    for elem in body.find_all(True):
        attrs_to_keep = ['href', 'src', 'alt', 'style']
        new_attrs = {k: v for k, v in elem.attrs.items() if k in attrs_to_keep}
        elem.attrs = new_attrs

    return str(body)


def generate_clean_html(article: dict) -> str:
    """Generate a clean HTML page from extracted article content."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{article['title']}</title>
    <style>
        body {{
            max-width: 700px;
            margin: 40px auto;
            padding: 0 20px;
            font-family: Georgia, serif;
            font-size: 18px;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }}
        h1 {{
            font-size: 2em;
            line-height: 1.2;
            margin-bottom: 0.5em;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 2em;
            padding-bottom: 1em;
            border-bottom: 1px solid #eee;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1.5em 0;
        }}
        figure {{
            margin: 1.5em 0;
        }}
        figcaption {{
            font-size: 0.85em;
            color: #666;
            text-align: center;
            margin-top: 0.5em;
        }}
        a {{
            color: #0066cc;
        }}
        blockquote {{
            border-left: 3px solid #ccc;
            margin-left: 0;
            padding-left: 1em;
            color: #555;
        }}
        p {{
            margin: 1em 0;
        }}
    </style>
</head>
<body>
    <article>
        <h1>{article['title']}</h1>
        <div class="meta">
            <span class="author">{article['author']}</span>
            {f'<span class="date"> &middot; {article["date"]}</span>' if article['date'] else ''}
        </div>
        <div class="content">
            {article['body']}
        </div>
    </article>
</body>
</html>'''


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run superstack.py <substack_url> [output.html]")
        print("\nExample:")
        print("  uv run superstack.py https://substack.com/inbox/post/183535301 article.html")
        sys.exit(1)

    url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.html'

    print(f"Fetching: {url}")
    html = fetch_page(url)

    print("Extracting article...")
    article = extract_article(html)

    print(f"Title: {article['title']}")
    print(f"Author: {article['author']}")

    clean_html = generate_clean_html(article)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(clean_html)

    print(f"Saved to: {output_file}")


if __name__ == '__main__':
    main()
