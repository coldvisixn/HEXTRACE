import tempfile
from pathlib import Path
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from ghostmap.app import Window
from ghostmap.theme import STYLE
app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
out=Path('/workspace/HEXTRACE/build/screenshots'); out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as d:
 w=Window(Path(d)/'demo.sqlite3',QSettings(d+'/settings.ini',QSettings.IniFormat))
 p=w.store.project('HTB Lab · Demo'); w.load_projects(p)
 h=w.store.node(p,'Host','192.0.2.10',status='confirmed',evidence='Synthetic demonstration host')
 services=[]
 for port,info in [(22,'OpenSSH 9.6'),(80,'nginx · HTTP'),(443,'nginx · HTTPS')]:
  n=w.store.node(p,'Service',f'192.0.2.10:{port}/tcp',status='confirmed',evidence=info+' · demo data')
  w.store.edge(p,h,n,'exposes'); services.append(n)
 f=w.store.node(p,'Finding','Review TLS configuration',detail='Hypothesis: inspect certificate validity and protocol configuration.\nCollect evidence before confirming.',evidence='Manual review pending')
 w.store.edge(p,services[2],f,'review')
 note=w.store.node(p,'Note','Investigation checklist',detail='1. Confirm authorized scope\n2. Review discovered services\n3. Record evidence and findings\n4. Save map and project notes')
 w.store.edge(p,h,note,'notes')
 w.resize(1280,820); w.show(); app.processEvents(); w.refresh(); w.graph.layout_nodes(); app.processEvents()
 positions={h:(0,0),services[0]:(280,0),services[1]:(280,110),services[2]:(280,220),f:(560,110),note:(0,200)}
 for node_id,(x,y) in positions.items():
  w.graph.nodes[node_id].setPos(x,y); w.store.position(node_id,x,y)
 w.graph.fit(); app.processEvents()
 w.target.setText('192.0.2.10')
 w.statusBar().showMessage('Demonstration data · no network scan performed')
 w.grab().save(str(out/'01-overview.png'))
 w.horizontal.setSizes([175,770,335]); w.vertical.setSizes([610,160]); app.processEvents()
 w.graph.fit(); w.graph.nodes[f].setSelected(True); app.processEvents()
 w.grab().save(str(out/'02-map-inspector.png'))
 w.nav.setCurrentRow(4); app.processEvents()
 w.select_node(dict(next(r for r in w.store.nodes(p) if r['id']==note))); app.processEvents()
 w.grab().save(str(out/'03-notes.png'))
 w.close()
print(out)
