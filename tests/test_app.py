import unittest
from unittest.mock import patch
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import app


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.docs = [
            'Bail may be granted after considering the risk of flight and interference with witnesses. The court must consider the circumstances of the criminal proceedings.',
            'Municipal property tax assessment concerns valuation of buildings and land. This tax appeal concerns ownership and exemptions under the taxation legislation.'
        ]
        self.meta = [dict(case_id=str(i), citation_id=str(i), authority=a, decision_date=d,
                          court=c, title=c, chunk=1)
                     for i, (a,d,c) in enumerate([(0.6,'2020-01-01','District Court'),(1.0,'2030-01-01','Supreme Court')])]
        vectorizer=TfidfVectorizer(stop_words='english',ngram_range=(1,2))
        matrix=vectorizer.fit_transform(self.docs)
        self.patcher=patch.multiple(app,DOCS=self.docs,META=self.meta,VECTORIZER=vectorizer,
                                   MATRIX=matrix,BM=app.BM25(self.docs),INIT_ERROR=None)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client=app.app.test_client()

    def test_authority_cannot_rescue_irrelevant_case(self):
        for mode in ('normal_rag','lex_rag'):
            results=app.retrieve('bail flight witnesses',mode)
            self.assertEqual([r['case_id'] for r in results],['0'])

    def test_absent_evidence_abstains(self):
        result=app.run_pipeline('quantum bananas superconductivity','lex_rag')
        self.assertTrue(result['abstained'])
        self.assertEqual(result['claims'],[])
        self.assertEqual(result['evidence'],[])

    def test_one_matching_term_is_not_enough(self):
        self.assertEqual(app.retrieve('bail superconductivity bananas','lex_rag'),[])

    def test_date_filter_excludes_future_and_unknown(self):
        self.assertEqual(app.retrieve('municipal property tax','lex_rag',as_of='2025-01-01'),[])
        app.META[0]['decision_date']=''
        self.assertEqual(app.retrieve('bail witnesses','lex_rag',as_of='2025-01-01'),[])

    def test_extracts_are_traceable(self):
        result=app.run_pipeline('bail flight witnesses','lex_rag')
        self.assertFalse(result['abstained'])
        by_id={e['citation_id']:e for e in result['evidence']}
        for claim in result['claims']:
            self.assertIn(claim['claim'],by_id[claim['citation_id']]['text'])
            self.assertEqual(claim['label'],'Exact source extract')

    def test_cited_supreme_court_does_not_override_metadata(self):
        self.assertEqual(app.court_metadata({'court':'High Court of Sikkim','text':'Supreme Court ruled'}),('High Court of Sikkim',0.8))
        self.assertEqual(app.court_metadata({'text':'Supreme Court ruled'})[1],0.0)

    def test_prechunked_records_keep_case_identity(self):
        rows=[{'text':self.docs[i], 'case_id':'same-case','chunk_id':f'chunk-{i}',
               'court':'High Court of Sikkim'} for i in range(2)]
        docs,meta=app.prepare(rows)
        self.assertEqual(len(docs),2)
        self.assertEqual({m['case_id'] for m in meta},{'same-case'})
        self.assertEqual(len({m['citation_id'] for m in meta}),2)

    def test_one_court_has_identical_ranking(self):
        for m in app.META:m['authority']=0.8
        a=app.retrieve('court tax bail','normal_rag')
        b=app.retrieve('court tax bail','lex_rag')
        self.assertEqual([r['citation_id'] for r in a],[r['citation_id'] for r in b])

    def test_invalid_payloads(self):
        for body in ([],{}, {'question':3}, {'question':'ab'}, {'question':'bail', 'as_of':'not-date'}, {'question':'x'*2001}):
            self.assertEqual(self.client.post('/api/research',json=body).status_code,400)

    def test_frontend_and_asset_boundary(self):
        for url in ('/','/static/style.css','/static/app.js'):
            with self.client.get(url) as response:
                self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/static/app.py').status_code,404)

    def test_dataset_error_visible(self):
        with patch.object(app,'INIT_ERROR','Dataset missing'):
            self.assertFalse(self.client.get('/api/status').json['ready'])
            self.assertEqual(self.client.post('/api/research',json={'question':'bail'}).status_code,503)


if __name__=='__main__': unittest.main()
