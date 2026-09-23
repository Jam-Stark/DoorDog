#!/usr/bin/env python3
"""Check every file against the delivery manifest; standard library only."""
from pathlib import Path
import argparse,hashlib,json

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[1]);p=ap.parse_args().package.resolve()
 rows=json.loads((p/'MANIFEST_SHA256.json').read_text());errors=[]
 for name,row in rows.items():
  f=(p/name).resolve()
  if not f.is_relative_to(p):raise SystemExit('Unsafe manifest path: '+name)
  if not f.is_file():errors.append(name+': missing');continue
  if f.stat().st_size!=row['bytes'] or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']:errors.append(name+': changed')
 if errors:raise SystemExit('\n'.join(errors))
 print(f'MANIFEST_PASS: {len(rows)} delivered files match their SHA-256 hashes.')
if __name__=='__main__':main()
