"""Ensure integration cannot weaken existing V5 logic or manual Shariah safeguards."""
import ast
from datetime import date
import hashlib
import json
from pathlib import Path
import unittest
from shariah_gate import review_status

BASE=Path(__file__).resolve().parents[1]
class V5Tests(unittest.TestCase):
    def test_original_strategy_shariah_and_scheduler_files_are_byte_identical(self):
        m=json.loads((BASE/'tests/v5-preservation.json').read_text())
        for name,expected in m['protected_files'].items():
            with self.subTest(path=name):self.assertEqual(hashlib.sha256((BASE/name).read_bytes()).hexdigest(),expected)
    def test_all_existing_v5_functions_unchanged(self):
        m=json.loads((BASE/'tests/v5-preservation.json').read_text());actual={}
        for node in ast.parse((BASE/'app.py').read_text()).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):actual[node.name]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
        self.assertEqual(actual,m['app_functions'])
    def test_unknown_is_never_shariah_cleared(self):self.assertEqual(review_status('DEMOA',{})['gate'],'UNVERIFIED')
    def record(self):return dict(Ticker='DEMOA',Reported_Status='COMPLIANT',Business_Screen='PASS',Financial_Screen='PASS',Methodology='AAOIFI',Provider='Synthetic registry test',Evidence_URL='https://example.test/report/fiction',Checked_On='2000-01-03',Reviewed_By='Synthetic reviewer',Notes='Not an actual report')
    def test_manual_claim_is_not_independent_certification(self):self.assertEqual(review_status('DEMOA',{'DEMOA':[self.record()]},date(2000,1,4))['gate'],'MANUALLY_REVIEWED')
    def test_duplicate_and_stale_evidence_still_blocked(self):
        r=self.record();self.assertEqual(review_status('DEMOA',{'DEMOA':[r,r]},date(2000,1,4))['gate'],'UNVERIFIED');self.assertEqual(review_status('DEMOA',{'DEMOA':[r]},date(2001,1,4))['gate'],'EXPIRED')
    def test_explicit_noncompliance_cannot_be_qualified_by_ui(self):
        r=self.record();r['Reported_Status']='NON_COMPLIANT';self.assertEqual(review_status('DEMOA',{'DEMOA':[r]},date(2000,1,4))['gate'],'BLOCKED')
