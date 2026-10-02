#!/usr/bin/env python3
"""Create pages and price-list rows for parts that are in public-prices.json
but have no page yet, and keep price mentions the price sync does not reach
(part-page FAQ answer, "related parts" rows) in step with the catalog.

Run BEFORE sync-public-prices.py:

    python3 scripts/add-part-pages.py            # read-only: lists what would change
    python3 scripts/add-part-pages.py --write
    python3 scripts/sync-public-prices.py --write
    python3 scripts/sync-public-prices.py && python3 scripts/test-public-prices.py

New pages are cloned from an existing, current part page of the same module
type (RDIMM / LRDIMM / UDIMM), so they carry every site-wide change already
applied to part pages. --selftest proves the clone reproduces existing pages.
It never invents prices: everything comes from the approved catalog.
"""
import argparse
from datetime import date
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://ocitech.com'
e = html.escape
# Current, photo-free pages used as the pattern for each module type.
BASES = {'RDIMM': 'sell-sk-hynix-hma82gr7mfr8n-uh', 'LRDIMM': 'sell-sk-hynix-hmaa8gl7amr4n-uh',
         'UDIMM': 'sell-samsung-m378a4g43ab2-cwe'}
# Price-list order (mirrors genall.py): listed capacities first, others after.
HUB_CAPS = {'DDR4': [16, 32, 64, 128, 256], 'DDR5': [16, 24, 32, 48, 64, 96, 128, 256]}
FFWORD = {'LRDIMM': 'load-reduced ECC ', 'RDIMM': 'registered ECC ', 'MRDIMM': 'multiplexed-rank ', 'UDIMM': ''}
_TD = 'style="padding:10px 12px;border-bottom:1px solid var(--line);"'
_TDS = 'style="padding:10px 12px;border-bottom:1px solid var(--line);color:var(--text-secondary);"'
_TDR = 'style="padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;'
REL_ROW = r'<div class="spec-row"><span class="k"><a href="/(sell-[a-z0-9-]+)">[^<]*</a></span><span class="v">[^<]*? &middot; up to \$[\d,]+</span></div>'
RANGE_SENT = r'Two things move your firm offer(?: within \u2014 or above \u2014 the indicative \$[\d,]+&ndash;\$[\d,]+ range)?\. '
FAQ_SENT = r'As of [A-Z][a-z]+ \d+, \d{4}, our indicative offer for [^<]*? is up to \$[\d,]+ per module'


def date_label(value):
    d = date.fromisoformat(value)
    return f'{d:%B} {d.day}, {d.year}'


def rank(p):
    return p['rank'] or '—'


def speed(p):
    return p['spd'].split('-')[1]


def fragments(p):
    """Every part-specific string on a priced part page, in replacement order."""
    pn, mfr, cap, spd, ff = p['pn'], p['manufacturer'], p['cap'], p['spd'], p['ff']
    w = FFWORD[ff]
    return [
        e(f'Sell {pn} — {cap}GB {spd} {ff} | Ocitech'),
        e(f'Sell {mfr} {pn} — {cap}GB {rank(p)} {spd} server memory.'),
        f'this exact {cap}GB {spd} {w}module ({ff})',
        f'<div class="pnx-spec">{mfr} &middot; {cap}GB {rank(p)} {spd} {ff}</div>',
        e(f'{pn} is a {cap}GB {rank(p)} {spd} {w}module ({ff}) from {mfr} — a sought-after server part.'),
        f'<span class="k">Manufacturer</span><span class="v">{mfr}</span>',
        f'<span class="k">Capacity</span><span class="v">{cap}GB</span>',
        f'<span class="k">Speed</span><span class="v">{spd} ({speed(p)} MT/s)</span>',
        f'<span class="k">Rank / Org</span><span class="v">{rank(p)}</span>',
        f"Other {cap}GB {p['gen']} modules we're buying",
    ]


def clone(text, x, n):
    """Turn part x's page into part n's page (same generation and module type)."""
    assert x['gen'] == n['gen'] and x['ff'] == n['ff'] and x['price_ready'] and n['price_ready']
    assert text.count(x['slug']) >= 3
    text = text.replace(x['slug'], n['slug'])
    for a, b in zip(fragments(x), fragments(n)):
        assert a in text, f'pattern page is missing: {a}'
        text = text.replace(a, b)
    assert e(x['pn']) in text
    text = text.replace(e(x['pn']), e(n['pn']))
    assert x['pn'] not in text and x['slug'] not in text
    return text


def related(p, parts):
    rel = [q for q in parts if q['price_ready'] and q['gen'] == p['gen'] and q['cap'] == p['cap'] and q['pn'] != p['pn']]
    rel.sort(key=lambda q: (-q['hi'], q['pn']))
    return rel[:4]


def rel_row(r):
    return (f'<div class="spec-row"><span class="k"><a href="/{r["slug"]}">{e(r["pn"])}</a></span>'
            f'<span class="v">{r["manufacturer"]} {r["spd"]} &middot; up to ${r["hi"]}</span></div>')


def set_related(text, p, parts):
    rows = ''.join(rel_row(r) for r in related(p, parts))
    assert rows, f'{p["pn"]}: no related parts'
    out, n = re.subn(r'(<div class="spec-list reveal" style="width:100%;max-width:640px;margin:0 auto;">)(?:' + REL_ROW + r')+(</div>)',
                     lambda m: m[1] + rows + m[m.lastindex], text)
    assert n == 1, f'{p["pn"]}: related block not found'
    return out


def refresh_mentions(text, p, by_slug):
    """FAQ answer, range sentence and related-part rows: prices the sync script does not rewrite."""
    def rel(m):
        q = by_slug.get(m[1])
        return re.sub(r'up to \$[\d,]+', f'up to ${q["hi"]}', m[0]) if q and q['price_ready'] else m[0]
    text = re.sub(REL_ROW, rel, text)
    if p['price_ready']:
        want = (e(f'our indicative offer for {p["manufacturer"]} {p["pn"]} ({p["cap"]}GB {p["spd"]} {p["ff"]})')
                + f' is up to ${p["hi"]} per module')
        def faq(m):
            if m[0].endswith(want) and p['source_type'] != 'database_offer':
                return m[0]            # price already right; leave its date alone
            return 'As of ' + date_label(p['checked_at']) + ', ' + want
        text = re.sub(FAQ_SENT, faq, text)
        clause = (f' within \u2014 or above \u2014 the indicative ${p["lo"]}&ndash;${p["hi"]} range' if p['lo'] != p['hi'] else '')
        text = re.sub(RANGE_SENT, lambda m: 'Two things move your firm offer' + clause + '. ', text)
    return text


def hub_row(p):
    return (f'<tr><td {_TD}><a href="/{p["slug"]}" style="color:var(--accent);font-weight:600;">{e(p["pn"])}</a></td>'
            f'<td {_TDS}>{e(p["manufacturer"])}</td><td {_TD}>{p["cap"]}GB<span class="hub-ff-m">{e(p["ff"])}</span></td>'
            f'<td {_TD}>{e(p["spd"])}</td><td {_TD}>{e(p["ff"])}</td>'
            f'<td {_TDR}color:var(--green);font-weight:700;">up to ${p["hi"]}</td></tr>')


def hub_tables(text, parts, new):
    """Add rows for new priced parts; a priced capacity replaces its 'Pricing upon request' row."""
    for gen in sorted({p['gen'] for p in new if p['price_ready']}):
        m = re.search(r'(<section id="' + gen.lower() + r'-prices".*?<tbody>)(.*?)(</tbody>)', text, flags=re.S)
        assert m, f'{gen} price table not found'
        rows = re.findall(r'<tr\b.*?</tr>', m[2], flags=re.S)
        assert ''.join(rows) == m[2].strip(), 'unexpected content in price table'
        have, req = {}, {}
        for r in rows:
            s = re.search(r'href="/(sell-[a-z0-9-]+)"', r)
            if s:
                have[s[1]] = r
            else:
                req[int(re.search(r'>(\d+)GB<', r)[1])] = r
        priced = [p for p in parts if p['gen'] == gen and p['price_ready']]
        for p in priced:
            have.setdefault(p['slug'], hub_row(p))
        key = lambda p: (p['cap'], int(speed(p)), p['manufacturer'], p['pn'], p['slug'])
        body = ''
        for cap in HUB_CAPS[gen]:
            ps = sorted((p for p in priced if p['cap'] == cap), key=key)
            body += ''.join(have[p['slug']] for p in ps) if ps else req.get(cap, '')
        body += ''.join(have[p['slug']] for p in sorted((p for p in priced if p['cap'] not in HUB_CAPS[gen]), key=key))
        assert all(v in body for v in have.values()), 'price table lost a row'
        text = text[:m.start(2)] + body + text[m.end(2):]
    return text


def sitemap(text, new, today):
    add = ''.join(f'  <url>\n    <loc>{SITE}/{p["slug"]}</loc>\n    <lastmod>{today}</lastmod>\n'
                  f'    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>\n'
                  for p in new if f'{SITE}/{p["slug"]}<' not in text)
    return text.replace('</urlset>', add + '</urlset>') if add else text


def redirects(text, new):
    lines = text.split('\n')
    last = max(i for i, l in enumerate(lines) if re.match(r'/sell-[a-z0-9-]+\.html  /sell-', l))
    add = [f'/{p["slug"]}.html  /{p["slug"]}  301!' for p in new if f'/{p["slug"]}.html ' not in text]
    return '\n'.join(lines[:last + 1] + add + lines[last + 1:])


def selftest(data, by_slug):
    """Clone each pattern page onto existing pages of the same type and compare."""
    strip = lambda t: re.sub(RANGE_SENT, 'RANGE', re.sub(FAQ_SENT, 'FAQ', re.sub('(?:' + REL_ROW + ')+', 'REL', re.sub(
        r'<div class="pnx-price">.*?</div>|<div class="pnx-note">Indicative.*?</div>|var LO=[\d.]+,HI=[\d.]+;|Indicative offer up to \$[\d,]+/module', 'PRICE', t, flags=re.S))))
    ok = 0
    for ff, base in BASES.items():
        x = by_slug[base]
        src = (ROOT / (base + '.html')).read_text()
        for y in data['parts']:
            page = ROOT / (y['slug'] + '.html')
            if y is x or not y['price_ready'] or (y['gen'], y['ff']) != (x['gen'], ff) or not page.is_file():
                continue
            cur = page.read_text()
            if 'ocitech-product-photos' in cur:
                continue
            assert strip(clone(src, x, y)) == strip(cur), f'clone of {base} does not reproduce {y["slug"]}'
            ok += 1
    print(f'selftest OK: {ok} existing pages reproduced from their pattern page')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    data = json.loads((ROOT / 'public-prices.json').read_text())
    parts = data['parts']
    by_slug = {p['slug']: p for p in parts}
    if args.selftest:
        return selftest(data, by_slug)
    new = [p for p in parts if not (ROOT / (p['slug'] + '.html')).is_file()]
    out = {}
    for p in new:
        assert p['price_ready'], f'{p["pn"]}: quote-only pages are not created by this script'
        assert p['ff'] in BASES and p['gen'] == by_slug[BASES[p['ff']]]['gen'], f'{p["pn"]}: no pattern page for {p["gen"]} {p["ff"]}'
        x = by_slug[BASES[p['ff']]]
        text = clone((ROOT / (x['slug'] + '.html')).read_text(), x, p)
        out[ROOT / (p['slug'] + '.html')] = set_related(text, p, parts)
    for p in parts:
        path = ROOT / (p['slug'] + '.html')
        old = out.get(path) or path.read_text()
        text = refresh_mentions(old, p, by_slug)
        if path in out or text != old:
            out[path] = text
    for name, fn in (('ram-price-list.html', lambda t: hub_tables(t, parts, new)),
                     ('sitemap.xml', lambda t: sitemap(t, new, data['checked_at'])),
                     ('_redirects', lambda t: redirects(t, new))):
        old = (ROOT / name).read_text()
        text = fn(old) if new else old
        if text != old:
            out[ROOT / name] = text
    if not out:
        print('Part pages are complete and their price mentions match the catalog.')
        return
    for path, text in sorted(out.items()):
        print(('Wrote ' if args.write else 'Would write: ') + path.name + (' (new)' if not path.exists() else ''))
        if args.write:
            path.write_text(text)
    print(f'{len(new)} new part pages, {len(out)} files in total')
    if not args.write:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
