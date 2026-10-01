#!/usr/bin/env python3
"""Read-only Linux process inventory; never kills and never emits command arguments."""
from __future__ import annotations
import argparse
import collections
import json
import os
from pathlib import Path
import re
import sys
import time

def inventory(pattern: str, limit: int) -> dict:
    if sys.platform != 'linux': raise ValueError('Linux /proc inventory only; use native OS inventory elsewhere.')
    regex = re.compile(pattern, re.I); rows = []; commands = {}
    uptime = float(Path('/proc/uptime').read_text().split()[0]); hz = os.sysconf('SC_CLK_TCK')
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            if p.stat().st_uid != os.getuid(): continue
            name=(p/'comm').read_text().strip(); command=(p/'cmdline').read_bytes()
            if not regex.search(name) and not regex.search(command.split(b'\0')[0].decode(errors='replace')): continue
            fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
            status=(p/'status').read_text().splitlines(); rss=next((int(s.split()[1]) for s in status if s.startswith('VmRSS:')),0)
            rows.append({'pid':int(p.name),'ppid':int(fields[1]),'name':name,'state':fields[0],
                         'start_ticks':int(fields[19]),'age_seconds':round(uptime-int(fields[19])/hz,1),
                         'rss_kib':rss,'command_group':commands.setdefault(command, len(commands) + 1)})
        except (OSError,ValueError,IndexError):continue  # Process may disappear during read-only enumeration.
    rows.sort(key=lambda r:r['rss_kib'],reverse=True)
    counts=collections.Counter((r['name'],r['command_group']) for r in rows)
    return {'read_only':True,'captured_epoch':time.time(),'total_matching':len(rows),
            'total_rss_kib':sum(r['rss_kib'] for r in rows),'rows':rows[:limit],
            'duplicate_command_groups':[{'name':k[0],'command_group':k[1],'count':v} for k,v in counts.most_common() if v>1],
            'warning':'Duplicates/age are diagnostic clues, not permission to kill. Shared RSS may be counted more than once.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pattern',default='codex|mcp|node|python|npx');p.add_argument('--limit',type=int,default=100);a=p.parse_args()
    try:
        if not 1<=a.limit<=1000:raise ValueError('limit must be 1..1000')
        print(json.dumps(inventory(a.pattern,a.limit),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,re.error) as exc:
        print(json.dumps({'error':str(exc)}));return 2
if __name__=='__main__':raise SystemExit(main())
