import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_prices', Path(__file__).with_name('sync-public-prices.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class PriceSyncTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((sync.ROOT / 'public-prices.json').read_text())

    def test_changed_offer_reaches_card_metadata_calculator_table_and_index(self):
        p = copy.deepcopy(next(x for x in self.data['parts'] if x['pn'] == 'HMA82GR7CJR8N-XN'))
        p['lo'], p['hi'] = 50, 70
        data = {**self.data, 'parts': [p]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page = root / (p['slug'] + '.html')
            page.write_text((sync.ROOT / page.name).read_text())
            hub = root / 'ram-price-list.html'
            hub.write_text('<table><tr><td><a href="/' + p['slug'] + '">Part</a></td><td>up to $66</td></tr></table>')
            changes = sync.outputs(root, data)
            self.assertIn('up to $70<small>', changes[page])
            self.assertIn('Indicative offer up to $70/module', changes[page])
            self.assertIn('var LO=50,HI=70;', changes[page])
            self.assertIn('up to $70<small', changes[hub])
            self.assertEqual(json.loads(changes[root / 'parts-index.json'])[0]['hi'], 70)
            for path, text in changes.items():
                path.write_text(text)
            self.assertEqual(sync.outputs(root, data), {})

    def test_quote_only_record_rejects_numeric_fallback(self):
        data = copy.deepcopy(self.data)
        p = next(x for x in data['parts'] if not x['price_ready'])
        p['hi'] = 575
        with self.assertRaises(AssertionError):
            sync.validate(data)

    def test_withdrawn_price_requires_quote_only_page(self):
        p = copy.deepcopy(self.data['parts'][0])
        p.update(price_ready=False, lo=None, hi=None)
        with self.assertRaises(ValueError):
            sync.render_part('var LO=41,HI=66;', p)

    def test_check_date_never_relabels_old_source_as_new(self):
        p = next(x for x in self.data['parts'] if x['pn'] == 'KP8XPW-MID-11MI')
        note = sync.price_note(p)
        self.assertIn('Source price updated: September 10, 2026', note)
        self.assertIn('Last checked: September 28, 2026', note)
        p = {**p, 'source_updated_at': '2026-09-29'}
        with self.assertRaises(AssertionError):
            sync.validate({**self.data, 'parts': [p]})

    def test_invalid_and_duplicate_prices_rejected(self):
        p = copy.deepcopy(self.data['parts'][0])
        for value in [-1, None, '66', True]:
            with self.assertRaises(AssertionError):
                sync.validate({**self.data, 'parts': [{**p, 'hi': value}]})
        with self.assertRaises(AssertionError):
            sync.validate({**self.data, 'parts': [p, p]})

    def test_approved_ddr5_examples_are_preserved(self):
        parts = {x['pn']: x for x in self.data['parts']}
        for pn, price in [('KP8XPW-MID-11MI', 596), ('KSM56R46BD4PMI-64HAI', 1235),
                          ('M321R8GA0PB1-CCPPC', 1251), ('MTC8C1084S1UC56BD1 BF', 97)]:
            self.assertEqual(parts[pn]['hi'], price)
            self.assertEqual(parts[pn]['lo'], price)


    def test_price_list_structured_data_matches_catalog_and_visible_faq(self):
        page = (sync.ROOT / 'ram-price-list.html').read_text()
        block = re.search(r'<!-- PRICE-LD:START --><script type="application/ld\+json">(.*?)</script><!-- PRICE-LD:END -->', page, re.S)
        self.assertIsNotNone(block, 'price list must keep its generated structured data')
        graph = {g['@type']: g for g in json.loads(block[1])['@graph']}
        self.assertEqual(graph['Dataset']['dateModified'], self.data['checked_at'])
        priced = [p for p in self.data['parts'] if p['price_ready']]
        self.assertEqual(graph['ItemList']['numberOfItems'], len(priced))
        for item, p in zip(graph['ItemList']['itemListElement'], priced):
            self.assertIn(f'up to ${p["hi"]}.', item['item']['description'])
        visible = re.findall(r'<div class="faq-item"><h3>(.*?)</h3>', page)
        self.assertEqual(len(graph['FAQPage']['mainEntity']), len(visible))
        self.assertNotIn('live market', page)

if __name__ == '__main__':
    unittest.main()
