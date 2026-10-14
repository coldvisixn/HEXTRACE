#!/usr/bin/env python3
"""Exercise extracted package and its launcher without requiring root."""
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
root=Path(__file__).resolve().parents[1]
package=root/'dist/ghostmap_0.1.0_all.deb'
with tempfile.TemporaryDirectory(prefix='ghostmap-package-') as d:
    stage=Path(d)/'root'
    subprocess.run(['dpkg-deb','-x',str(package),str(stage)],check=True)
    assert (stage/'usr/share/applications/ghostmap.desktop').is_file()
    assert (stage/'usr/share/icons/hicolor/scalable/apps/ghostmap.svg').is_file()
    env=os.environ.copy()
    env['QT_QPA_PLATFORM']='offscreen'
    env['PYTHONPATH']=str(stage/'usr/share/ghostmap')+':/workspace/ghostmap-tools/root/usr/lib/python3/dist-packages'
    env['LD_LIBRARY_PATH']='/workspace/ghostmap-tools/root/usr/lib/x86_64-linux-gnu'
    env['XDG_CONFIG_HOME']=str(Path(d)/'config')
    env['XDG_DATA_HOME']=str(Path(d)/'data')
    env['XDG_CACHE_HOME']='/workspace/ghostmap-tools/cache'
    program='''
import sys
from pathlib import Path
import ghostmap
assert str(Path(ghostmap.__file__).resolve()).startswith(sys.argv[1])
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from ghostmap.app import Window
from ghostmap.nmapxml import import_xml
app=QApplication([])
path=Path(sys.argv[2])
w=Window(path,QSettings(str(path)+'.ini',QSettings.IniFormat))
p=w.store.project('Packaged lab'); w.load_projects(p)
h=w.store.host(p,'192.0.2.1'); n=w.store.node(p,'Note','Investigate')
w.store.edge(p,h,n,'next step'); w.refresh(); w.show(); app.processEvents()
assert len(w.graph.nodes)==2
w.store.position(h,112,334); w.close()
w=Window(path,QSettings(str(path)+'.ini',QSettings.IniFormat)); w.load_projects(p)
assert len(w.graph.nodes)==2
assert w.store.nodes(p)[0]['x']==112
w.close()
print('Extracted package: project, graph, relationships and persistence PASS')
'''
    subprocess.run(['/usr/bin/python3','-c',program,str(stage),str(Path(d)/'functional.sqlite3')],env=env,cwd=d,check=True)
    database=Path(d)/'launcher.sqlite3'
    process=subprocess.Popen([str(stage/'usr/bin/ghostmap'),'--database',str(database)],env=env,cwd=d,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        ready=False
        deadline=time.monotonic()+10
        while time.monotonic()<deadline and process.poll() is None:
            if database.exists():
                with sqlite3.connect(database) as connection:
                    ready=connection.execute("SELECT count(*) FROM sqlite_master WHERE name='projects'").fetchone()[0]==1
                if ready: break
            time.sleep(.05)
        assert ready, 'Packaged launcher did not initialize the application'
        print('Actual packaged launcher with system Python/PySide6: PASS')
    finally:
        process.terminate()
        try: output,error=process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); output,error=process.communicate()
        if 'Traceback' in error: raise RuntimeError(error)
print('Root installation, desktop menu registration and removal still require target Kali validation.')
