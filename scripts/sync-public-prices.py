#!/usr/bin/env python3
"""Render approved public-prices.json into static pages and calculator data.

Default is a read-only consistency check. --write applies all prepared outputs.
Dates are explicit evidence, never advanced just because the script ran.
"""
import argparse
from datetime import date
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def date_label(value):
    d = date.fromisoformat(value)
    return f'{d:%B} {d.day}, {d.year}'


def validate(data):
    assert data['version'] == 1, 'Unsupported price catalog version'
    date.fromisoformat(data['checked_at'])
    names, slugs = set(), set()
    for p in data['parts']:
        assert p['pn'] not in names and p['slug'] not in slugs, 'Duplicate part or page'
        names.add(p['pn'])
        slugs.add(p['slug'])
        assert re.fullmatch(r'sell-[a-z0-9-]+', p['slug']), 'Invalid page slug'
        assert p['gen'] in ('DDR4', 'DDR5') and p['cap'] > 0
        assert p['source_type'] in ('database_offer', 'approved_competitor_override', 'quote_required')
        assert date.fromisoformat(p['checked_at']) <= date.fromisoformat(data['checked_at'])
        if p['price_ready']:
            assert all(type(p[k]) is int for k in ('lo', 'hi'))
            assert 0 < p['lo'] <= p['hi'], 'Invalid offer range'
            assert date.fromisoformat(p['source_updated_at']) <= date.fromisoformat(p['checked_at'])
            if p['source_type'] == 'approved_competitor_override':
                assert p['gen'] == 'DDR5'
                assert p['source_url'] == 'https://www.sellusedram.com/prices/'
        else:
            assert p['lo'] is None and p['hi'] is None, 'Unpriced parts must not expose fallback prices'


def replace_once(pattern, replacement, text):
    result, count = re.subn(pattern, replacement, text, flags=re.S)
    if count != 1:
        raise ValueError(f'Expected one match, got {count}: {pattern}')
    return result


SITE = 'https://ocitech.com'


def plain(fragment):
    return html.unescape(re.sub(r'<[^>]+>', '', fragment)).strip()


def price_list_ld(text, data):
    """Structured data for the price list, generated from the approved catalog
    and the page's own visible FAQ so the two can never disagree."""
    checked = data['checked_at']
    priced = [p for p in data['parts'] if p['price_ready']]
    items = []
    for i, p in enumerate(priced, 1):
        name = f'{p["manufacturer"]} {p["pn"]} {p["cap"]}GB {p["spd"]} {p["ff"]}'
        amount = (f'${p["lo"]}-${p["hi"]}' if p['lo'] != p['hi'] else f'${p["hi"]}')
        items.append({'@type': 'ListItem', 'position': i, 'item': {
            '@type': 'WebPage', 'name': 'Sell ' + name, 'url': f'{SITE}/{p["slug"]}',
            'description': (f'Indicative buyback offer {amount} per module (working pull), up to ${p["hi"]}. '
                            f'Source date {p["source_updated_at"]}; last checked {p["checked_at"]}. '
                            'A guide, not a guaranteed offer.')}})
    faqs = [{'@type': 'Question', 'name': plain(q), 'acceptedAnswer': {'@type': 'Answer', 'text': plain(a)}}
            for q, a in re.findall(r'<div class="faq-item"><h3>(.*?)</h3><p>(.*?)</p></div>', text, flags=re.S)]
    graph = [
        {'@type': 'WebPage', '@id': f'{SITE}/ram-price-list', 'url': f'{SITE}/ram-price-list',
         'name': 'Server RAM Buyback Price List — DDR4 & DDR5', 'dateModified': checked,
         'publisher': {'@type': 'Organization', 'name': 'Ocitech, LLC', 'url': SITE + '/'}},
        {'@type': 'Dataset', 'name': 'Ocitech server RAM buyback prices (DDR4 and DDR5)',
         'description': ('Indicative per-module buyback offers that Ocitech pays for used DDR4 and DDR5 server memory, '
                         'by manufacturer part number. Prices are a reviewed snapshot, not a live feed; each part '
                         'carries its own source date and last-checked date. Larger quantities may qualify for higher offers.'),
         'url': f'{SITE}/ram-price-list', 'dateModified': checked, 'isAccessibleForFree': True,
         'creator': {'@type': 'Organization', 'name': 'Ocitech, LLC', 'url': SITE + '/'},
         'keywords': ['server RAM buyback prices', 'sell DDR4 RDIMM', 'sell DDR5 RDIMM', 'used server memory prices'],
         'variableMeasured': 'Indicative buyback offer per module, USD',
         'distribution': {'@type': 'DataDownload', 'encodingFormat': 'application/json', 'contentUrl': f'{SITE}/parts-index.json'}},
        {'@type': 'ItemList', 'name': 'Priced server RAM part numbers', 'numberOfItems': len(items), 'itemListElement': items},
    ]
    if faqs:
        graph.append({'@type': 'FAQPage', 'mainEntity': faqs})
    block = ('<script type="application/ld+json">'
             + json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('</', '<\\/')
             + '</script>')
    text = replace_once(r'(<!-- PRICE-LD:START -->).*?(<!-- PRICE-LD:END -->)',
                        lambda m: m[1] + block + m[2], text)
    return re.sub(r'(<span class="faq-checked">)[^<]*(</span>)',
                  lambda m: m[1] + date_label(checked) + m[2], text)


def price_note(p):
    amount = (f'Indicative range ${p["lo"]}&ndash;${p["hi"]}' if p['lo'] != p['hi']
              else f'Indicative figure ${p["hi"]}')
    source_label = 'Source price updated' if p['source_type'] == 'approved_competitor_override' else 'Latest supporting record'
    return (amount + ' for a working pull &middot; a guide, not a guaranteed offer. '
            + source_label + ': ' + date_label(p['source_updated_at'])
            + '. Last checked: ' + date_label(p['checked_at'])
            + '. Your firm offer depends on the exact part, quantity and condition.')


def render_part(text, p):
    if not p['price_ready']:
        # Fail closed if a formerly priced page needs conversion to quote-only.
        if 'var LO=' in text or 'class="pnx-price"' in text:
            raise ValueError(f'{p["pn"]}: convert priced page to quote-only before rebuilding')
        return text
    text = replace_once(r'(<div class="pnx-price">).*?(<small> / module</small></div>)',
                        lambda m: m[1] + f'up to ${p["hi"]}' + m[2], text)
    text = replace_once(r'(<div class="pnx-note">)Indicative (?:range|figure).*?(</div>)',
                        lambda m: m[1] + price_note(p) + m[2], text)
    text = replace_once(r'var LO=[\d.]+,HI=[\d.]+;',
                        f'var LO={p["lo"]},HI={p["hi"]};', text)
    text = re.sub(r'Indicative offer up to \$[\d,]+/module',
                  f'Indicative offer up to ${p["hi"]}/module', text)
    return text


def render_table_rows(text, by_slug):
    def row(match):
        original = match[0]
        links = re.findall(r'href="/?(sell-[a-z0-9-]+)(?:\.html)?"', original)
        parts = [by_slug[x] for x in links if x in by_slug]
        if not parts or not re.search(r'up to \$[\d,]+', original):
            return original
        if len(parts) != 1:
            raise ValueError('Ambiguous priced table row')
        p = parts[0]
        # Remove the dated detail previously generated, then rebuild it.
        original = re.sub(r'<small class="price-dates".*?</small>', '', original, flags=re.S)
        if not p['price_ready']:
            return re.sub(r'up to \$[\d,]+', 'Request a quote', original)
        dates = (f'<small class="price-dates" style="display:block;font-size:11px;font-weight:400;white-space:normal;">'
                 f'Source: {html.escape(p["source_updated_at"])} &middot; Checked: {html.escape(p["checked_at"])}</small>')
        return re.sub(r'up to \$[\d,]+', f'up to ${p["hi"]}' + dates, original)
    return re.sub(r'<tr\b[^>]*>.*?</tr>', row, text, flags=re.S)


def outputs(root, data):
    validate(data)
    by_slug = {p['slug']: p for p in data['parts']}
    for slug in by_slug:
        assert (root / (slug + '.html')).is_file(), f'Missing page: {slug}'
    out = {}
    for path in root.glob('*.html'):
        old = path.read_text()
        text = render_part(old, by_slug[path.stem]) if path.stem in by_slug else old
        text = render_table_rows(text, by_slug)
        if path.name == 'ram-price-list.html':
            text = replace_once(r'(<p class="sub reveal in">)What we\x27re paying.*?(</p>)',
                lambda m: m[1] + 'Indicative DDR4 and DDR5 buyback offers by part number. Larger quantities may qualify for higher per-module offers. '
                + 'Last checked: ' + date_label(data['checked_at'])
                + '. Each row shows its source date separately; checking a price does not mean the underlying source changed.' + m[2], text) if "What we're paying" in text else text
            text = re.sub(r'(Last checked: )[A-Za-z]+ \d+, \d{4}(\. Each row)',
                          lambda m: m[1] + date_label(data['checked_at']) + m[2], text)
            text = text.replace('Live buyback prices', 'Indicative buyback prices')
            if '<!-- PRICE-LD:START -->' in text:
                text = price_list_ld(text, data)
        if text != old:
            out[path] = text
    # All search widgets and lot calculators already consume this generated file.
    index = [{k: p[k] for k in ('pn', 'slug', 'cap', 'gen', 'spd', 'ff', 'lo', 'hi', 'source_updated_at', 'checked_at')}
             for p in data['parts'] if p['price_ready']]
    value = json.dumps(index, indent=2) + '\n'
    path = root / 'parts-index.json'
    if not path.exists() or path.read_text() != value:
        out[path] = value
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'public-prices.json').read_text())
    changes = outputs(ROOT, data)
    if not changes:
        print('Public prices are synchronized.')
        return
    for path, value in changes.items():
        print(('Updated ' if args.write else 'Out of sync: ') + path.name)
        if args.write:
            path.write_text(value)
    if not args.write:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
