"""English presentation must not alter inference evidence or revive stale results."""
import copy
import unittest
from luma_review.presentation import present_guide


class PresentationTests(unittest.TestCase):
    def test_translation_requires_exact_brief_and_matching_input(self):
        raw={'brief':{'id':'brief','work':'Lavoro','looking_for':'Goal','connect_with':'People','can_offer':'Experience'},'criteria_markdown':'Lavoro','people':[{'profile_url':'person','summary':'Original','professional':{'facts':[{'kind':'skill','value':'Sistemi'}]},'assessments':[{'criterion_id':'P1','verdict':'yes','reason':'Original reason','evidence':[{'quote':'Citazione'}]}],'score':{'value':4}}],'graph':{'nodes':[{'id':'topic','label':'Sistemi','type':'topic'}]}}
        overlay={'brief_id':'brief','brief':{'work':'Work'},'people':{'person':{'input_hash':'exact','summary':'English summary','facts':['Systems'],'reasons':{'P1':'English reason'}}}}
        original=copy.deepcopy(raw)
        translated=present_guide(raw,overlay,{'person':{'input_hash':'exact'}})
        self.assertEqual(raw,original)
        self.assertEqual(translated['people'][0]['summary'],'English summary')
        self.assertEqual(translated['people'][0]['assessments'][0]['evidence'],raw['people'][0]['assessments'][0]['evidence'])
        self.assertEqual(translated['people'][0]['score'],raw['people'][0]['score'])
        self.assertEqual(translated['graph']['nodes'][0]['id'],'topic')
        self.assertEqual(present_guide(raw,overlay,{'person':{'input_hash':'changed'}})['people'][0]['summary'],'Original')
        overlay['brief_id']='different'
        self.assertIs(present_guide(raw,overlay,{}),raw)
