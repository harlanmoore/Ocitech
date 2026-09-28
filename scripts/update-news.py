#!/usr/bin/env python3
"""Refresh the static news listings and add article URLs to the sitemap."""
from pathlib import Path
from datetime import date
from html import escape
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def render(items, home=False):
    cards = []
    for item in items:
        published = date.fromisoformat(item['date']) if item.get('date') else None
        meta = escape(item['category'])
        if published:
            label = f'{published:%B} {published.day}, {published.year}'
            meta = f'<time datetime="{published.isoformat()}">{label}</time> · {meta}'
        link = f'<a href="/{escape(item["slug"], quote=True)}">{escape(item["title"])}</a>'
        summary = f'<p>{escape(item["summary"])}</p>'
        cards.append(f'<article><p class="memory-news-meta">{meta}</p><h3>{link}</h3>{summary}</article>' if home else f'<li><small>{meta}</small><h2>{link}</h2>{summary}</li>')
    return '\n'.join(cards)

def replace_region(text, region, content):
    start, end = f'<!-- NEWS:{region}:START -->', f'<!-- NEWS:{region}:END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f'Expected exactly one {region} news region')
    return text[:text.index(start)+len(start)]+'\n'+content+'\n'+text[text.index(end):]

def main():
    items = json.loads((ROOT/'news-articles.json').read_text())
    seen = set()
    for item in items:
        slug = item['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in seen:
            raise ValueError(f'Invalid or duplicate article slug: {slug}')
        seen.add(slug)
        if not (ROOT/f'{slug}.html').is_file():
            raise ValueError(f'Missing article: {slug}.html')
        for field in ('title','summary','category'):
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(f'Missing {field}: {slug}')
        if item.get('date'):
            date.fromisoformat(item['date'])
    # Newest dated articles first; undated guides retain their editorial order.
    items.sort(key=lambda item: item.get('date') or '', reverse=True)
    updates = {
        ROOT/'index.html': replace_region((ROOT/'index.html').read_text(), 'HOME', render(items[:3], True)),
        ROOT/'memory-news.html': replace_region((ROOT/'memory-news.html').read_text(), 'INDEX', render(items)),
    }
    sitemap_path = ROOT/'sitemap.xml'
    sitemap = sitemap_path.read_text()
    tree = ET.fromstring(sitemap)
    existing = {element.text for element in tree.iter() if element.tag.split('}')[-1] == 'loc'}
    additions = []
    for item in items:
        url = 'https://ocitech.com/'+item['slug']
        if url not in existing:
            additions.append(f'  <url><loc>{url}</loc></url>')
    if additions:
        sitemap = sitemap.replace('</urlset>', '\n'.join(additions)+'\n</urlset>')
    ET.fromstring(sitemap)
    updates[sitemap_path] = sitemap
    # Validate everything before updating any output.
    for path, content in updates.items():
        if path.read_text() != content:
            path.write_text(content)
    print(f'Updated homepage (up to 3 articles), Memory News ({len(items)} articles), and sitemap.')

if __name__ == '__main__':
    main()
