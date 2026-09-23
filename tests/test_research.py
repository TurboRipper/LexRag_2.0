import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import json
import numpy as np
import app
from research_models import evidence_windows, aggregate_nli
from evaluate import retrieval_metrics, load_labels


class SpaceTokenizer:
    def __call__(self,text,**kwargs):
        import re
        spans=[(m.start(),m.end()) for m in re.finditer(r'\S+',text)]
        return {'offset_mapping':spans,'input_ids':list(range(len(spans)))}


class ResearchTests(unittest.TestCase):
    def test_windows_include_tail_and_exact_offsets(self):
        text=' '.join(f'word{i}' for i in range(1000))
        windows=evidence_windows(text,SpaceTokenizer())
        self.assertIn('word999',windows[-1]['text'])
        for w in windows:self.assertEqual(text[w['char_start']:w['char_end']],w['text'])
        covered=set()
        for w in windows:covered.update(range(w['char_start'],w['char_end']))
        self.assertTrue(all(i in covered for i,c in enumerate(text) if not c.isspace()))

    def test_nli_does_not_hide_contradiction(self):
        support={'entailment':0.9,'contradiction':0.02,'neutral':0.08}
        contra={'entailment':0.02,'contradiction':0.92,'neutral':0.06}
        self.assertEqual(aggregate_nli([support,contra])['label'],'Mixed evidence signals')
        self.assertEqual(aggregate_nli([])['label'],'Not established')
        self.assertEqual(aggregate_nli([contra])['label'],'Model-contradicted')

    def test_nli_windows_keep_later_evidence(self):
        from research_models import NeuralEngine
        engine=object.__new__(NeuralEngine)
        engine.tokenizers={'nli':SpaceTokenizer()}
        engine.manifest={'nli':{'repo':'test','revision':'test'}}
        engine.nli_labels={0:'contradiction',1:'entailment',2:'neutral'}
        engine.predict_pairs=lambda name,pairs:np.array([[0.01,0.98,0.01] if 'FINAL_SUPPORT' in a else [0.01,0.01,0.98] for a,b in pairs])
        evidence=[{'text':('irrelevant '*400)+'FINAL_SUPPORT', 'citation_id':'a','case_id':'case'}]
        result=engine.verify('Short claim',evidence)
        self.assertEqual(result['label'],'Model-supported')
        self.assertGreater(result['support'][0]['char_start'],1000)
        self.assertTrue(result['coverage_complete'])

    def test_retry_preserves_cutoff_and_exclusions(self):
        class Engine:
            def verify(self,claim,evidence):return {'label':'Not established','claim':claim}
        with patch.object(app,'get_neural',return_value=Engine()),patch.object(app,'retrieve_research',return_value=[]) as retrieve:
            result=app.verify_with_retry('question',['claim'],'2020-01-01',True,['removed'])
            self.assertEqual(retrieve.call_count,2)
            for call in retrieve.call_args_list:
                self.assertEqual(call.args[1],'2020-01-01')
                self.assertEqual(call.kwargs['excluded'],['removed'])
            self.assertEqual(result['checks'][0]['retrieval_rounds'],2)

    def test_retry_can_be_disabled(self):
        class Engine:
            def verify(self,claim,evidence):return {'label':'Not established','claim':claim}
        with patch.object(app,'get_neural',return_value=Engine()),patch.object(app,'retrieve_research',return_value=[]) as retrieve:
            app.verify_with_retry('question',['claim'],retry=False)
            self.assertEqual(retrieve.call_count,1)

    def test_real_metrics_do_not_inflate_duplicate_cases(self):
        m=retrieval_metrics(['a','a','b'],['a','c'])
        self.assertEqual(m['recall_at_5'],0.5)
        self.assertEqual(m['precision_at_5'],0.2)
        self.assertEqual(m['mrr'],1)
        self.assertIsNone(retrieval_metrics([],[])['recall_at_5'])

    def test_unreviewed_labels_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'labels.jsonl'
            p.write_text(json.dumps({'id':'q','question':'bail','reviewed':False}))
            with self.assertRaises(ValueError):load_labels(p)

    def test_invalid_verification_input(self):
        client=app.app.test_client()
        for body in ({},[],{'question':'bail','claims':[]},{'question':'bail','claims':['claim'],'retry':'yes'},
                     {'question':'bail','claims':['claim'],'as_of':'2020-13-01'}):
            self.assertEqual(client.post('/api/verify',json=body).status_code,400)


if __name__=='__main__':unittest.main()
