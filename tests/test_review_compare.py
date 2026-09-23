import unittest
from unittest.mock import patch
from review_compare import prefix_evidence, compare
import app


def passage(key, text):
    return {'citation_id': key, 'case_id': key, 'text': text}


class Engine:
    manifest = {'nli': {'repo': 'test', 'revision': 'fixed'}}

    def verify(self, claim, evidence):
        return {'label': 'Model-supported' if any('SUPPORT' in e['text'] for e in evidence)
                else 'Not established', 'claim': claim}


class ComparisonTests(unittest.TestCase):
    def test_prefix_budget_keeps_sources_without_mutation(self):
        original = [passage('a', 'a' * 800), passage('b', 'b' * 800)]
        selected = prefix_evidence(original)
        self.assertEqual([len(p['text']) for p in selected], [800, 200])
        self.assertEqual(selected[1]['citation_id'], 'b')
        self.assertEqual(len(original[1]['text']), 800)

    def test_late_support_changes_label_without_retry(self):
        evidence = [passage('a', 'x' * 1100 + ' SUPPORT')]
        with patch('review_compare.time.perf_counter', side_effect=range(6)):
            result = compare('question', 'claim', Engine(), lambda query: evidence)
        self.assertEqual([v['check']['label'] for v in result['variants']],
                         ['Not established', 'Model-supported', 'Model-supported'])
        self.assertFalse(result['retry_attempted'])
        self.assertEqual(result['variants'][2]['strategy_seconds'], result['variants'][1]['strategy_seconds'])

    def test_retry_deduplicates_and_shares_initial_search(self):
        initial = passage('a', 'irrelevant')
        added = passage('b', 'SUPPORT')
        calls = []
        def retrieve(query):
            calls.append(query)
            return [initial] if query == 'question' else [initial, added, added]
        result = compare('question', 'claim', Engine(), retrieve)
        self.assertEqual(calls, ['question', 'claim'])
        self.assertEqual(result['variants'][2]['added_passages'], 1)
        self.assertEqual(result['variants'][2]['check']['label'], 'Model-supported')
        self.assertEqual(result['variants'][0]['check']['label'], 'Not established')

    def test_no_evidence_does_not_manufacture_support(self):
        result = compare('question', 'claim', Engine(), lambda query: [])
        self.assertTrue(all(v['check']['label'] == 'Not established' for v in result['variants']))
        self.assertFalse(result['controls']['independent_gold_labels'])

    def test_endpoint_validation_and_asset_boundary(self):
        client = app.app.test_client()
        for body in ([], {}, {'question': 'ab', 'claim': 'valid claim'},
                     {'question': 'question', 'claim': 42}):
            self.assertEqual(client.post('/api/compare-verification', json=body).status_code, 400)
        for url in ('/review', '/static/review.js', '/static/review.css'):
            with client.get(url) as response:
                self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get('/static/review_compare.py').status_code, 404)
        self.assertEqual(client.get('/api/review-record/unknown').status_code, 404)


if __name__ == '__main__':
    unittest.main()
