#!/usr/bin/env python3
"""Recreate platform files from PostgreSQL in a NEW directory only."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.datacenter_db import db_connect
from backend.datacenter_archive import restore_project
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('target');p.add_argument('--run-id')
a=p.parse_args()
c=db_connect()
try:
    print(json.dumps(restore_project(c,a.target,a.run_id)))
finally:
    c.close()
