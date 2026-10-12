"""Cache approved original images. Stdin: [{source_url, download_url, sha256}].

Temporary download URLs must never be logged or committed. The expected digest
comes from the approved original; stored product/source links remain unchanged.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
import catalog

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--base-url',default='https://api.magelle.com.ua');parser.add_argument('--local-source-dir')
    args=parser.parse_args();path=Path(args.db)
    if not path.is_file(): sys.exit('Existing database required')
    entries=json.load(sys.stdin)
    con=sqlite3.connect(path);con.row_factory=sqlite3.Row
    directory=path.parent/'media';directory.mkdir(exist_ok=True)
    report=[]
    try:
        for entry in entries:
            source=entry['source_url'];expected=entry['sha256']
            if urlsplit(source).hostname!='drive.google.com' or len(expected)!=64: raise ValueError('Invalid approved source')
            if args.local_source_dir:
                drive_id=parse_qs(urlsplit(source).query).get('id',[''])[0]
                candidate=Path(args.local_source_dir)/(drive_id+'.png')
                if not drive_id or not candidate.is_file(): raise ValueError('Approved local original missing')
                raw=candidate.read_bytes()
            else:
                if urlsplit(entry['download_url']).scheme!='https': raise ValueError('HTTPS required')
                with urllib.request.urlopen(entry['download_url'],timeout=60) as response: raw=response.read(12*1024*1024+1)
            if len(raw)>12*1024*1024 or hashlib.sha256(raw).hexdigest()!=expected: raise ValueError('Original image digest mismatch')
            ext='.png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if raw.startswith(b'\xff\xd8\xff') else ''
            if not ext: raise ValueError('Unsupported original image')
            filename=hashlib.sha256(source.encode()).hexdigest()[:48]+ext
            destination=directory/filename
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest()!=expected: raise ValueError('Existing file differs')
            else:
                with destination.open('xb') as output: output.write(raw)
            os.chmod(destination,0o644)
            url=args.base_url.rstrip('/')+'/uploads/'+filename
            con.execute('BEGIN IMMEDIATE')
            before=con.execute('SELECT * FROM media_assets WHERE source_url=?',(source,)).fetchone()
            con.execute('INSERT INTO media_assets(source_url,public_url,sha256) VALUES(?,?,?) ON CONFLICT(source_url) DO UPDATE SET public_url=excluded.public_url,sha256=excluded.sha256',(source,url,expected))
            catalog.audit(con,'migration','cache_approved_original','media:'+filename,dict(before) if before else None,{'source_url':source,'public_url':url,'sha256':expected,'bytes':len(raw)})
            con.commit()
            report.append({'url':url,'sha256':expected,'bytes':len(raw)})
        print(json.dumps(report,indent=2))
    finally: con.close()

if __name__=='__main__': main()
