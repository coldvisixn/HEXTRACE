#!/usr/bin/env python3
"""Linux/offscreen measurement, not a claim about a Kali desktop VM."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import resource
import tempfile
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, __version__ as qt_version
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ghostmap.app import Window
from ghostmap.theme import STYLE

app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
def rss():
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'): return int(line.split()[1])/1024
with tempfile.TemporaryDirectory() as d:
    window=Window(Path(d)/'measure.sqlite3',QSettings(d+'/settings.ini',QSettings.IniFormat))
    project=window.store.project('Authorized lab · demo data'); window.load_projects(project)
    window.show(); QTest.qWait(300)
    start=time.process_time(); QTest.qWait(3000)
    idle={'rss_mib':round(rss(),2),'cpu_seconds_over_3s':round(time.process_time()-start,4)}
    host=window.store.host(project,'192.0.2.10')
    for i in range(399):
        node=window.store.node(project,'Service',f'192.0.2.10:{i+1}/tcp',status='confirmed',evidence='Synthetic benchmark node')
        window.store.edge(project,host,node,'exposes')
    start=time.perf_counter(); window.refresh(); window.graph.layout_nodes(); app.processEvents()
    load=time.perf_counter()-start
    start=time.process_time(); QTest.qWait(3000)
    graph={'nodes':400,'edges':399,'rss_mib':round(rss(),2),'cpu_seconds_over_3s':round(time.process_time()-start,4),'load_layout_seconds':round(load,3)}
    # Screenshot has its own small, clearly labelled synthetic project.
    demo=window.store.project('Demo · synthetic data')
    h=window.store.node(demo,'Host','192.0.2.10',status='confirmed',evidence='Synthetic demo')
    for port,name in [(22,'OpenSSH'),(80,'HTTP'),(443,'HTTPS')]:
        n=window.store.node(demo,'Service',f'192.0.2.10:{port}/tcp',status='confirmed',evidence=name+' · synthetic')
        window.store.edge(demo,h,n,'exposes')
    finding=window.store.node(demo,'Finding','Review HTTP configuration','Collect evidence before confirming')
    window.store.edge(demo,h,finding,'investigate')
    window.load_projects(demo); window.graph.layout_nodes(); app.processEvents()
    window.grab().save(str(Path('build')/'ghostmap-offscreen.png'))
    db_bytes=sum(p.stat().st_size for p in Path(d).glob('measure.sqlite3*'))
    window.close()
    report={'platform':f'Debian 13 x86_64, Python {sys.version.split()[0]}, PySide6 {qt_version}, offscreen',
        'idle':idle,'graph':graph,'max_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),'database_bytes_with_wal':db_bytes}
    print(json.dumps(report,indent=2))
