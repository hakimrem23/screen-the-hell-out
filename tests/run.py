"""Deterministic test inventory. No engine token or market-data acquisition."""
import argparse
import json
from pathlib import Path
import sys
import unittest

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    suite=unittest.TestLoader().discover('tests',pattern='test_*.py',top_level_dir='.')
    with (a.output/'tests.log').open('w') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    report=dict(run=r.testsRun,passed=r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped),mode='OFFLINE_SYNTHETIC_ONLY_NOT_STRATEGY_ACCURACY')
    (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not r.wasSuccessful() or r.skipped:sys.exit(1)
if __name__=='__main__':main()
