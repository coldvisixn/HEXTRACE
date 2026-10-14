import argparse
import os
import shutil
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QSettings, QStandardPaths, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QLineEdit,QComboBox,QListWidget,QListWidgetItem,QPlainTextEdit,
    QSplitter,QTabWidget,QStackedWidget,QInputDialog,QMessageBox,QFileDialog,QProgressBar)
from .store import Store, KINDS
from .scanner import Scanner, ImportWorker
from .graph import Graph, Node
from .theme import STYLE

class Window(QMainWindow):
    def __init__(self, database=None, settings=None):
        super().__init__()
        base=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        self.store=Store(database or base/'projects.sqlite3')
        self.settings=settings or QSettings('GHOSTMAP','GHOSTMAP')
        self.project_id=None; self.node_id=None; self.offset=0; self.task_id=None; self.importer=None
        self.scanner=Scanner(str(self.store.path),self)
        self.setWindowTitle('GHOSTMAP · Native Pentest Workstation')
        self.setWindowIcon(QIcon(str(Path(__file__).parent/'assets/ghostmap.svg')))
        self.resize(1380,860)
        self.build_ui()
        self.scanner.output.connect(self.append_log)
        self.scanner.imported.connect(self.imported)
        self.scanner.complete.connect(self.scan_complete)
        self.scanner.busy_changed.connect(self.set_busy)
        self.search_timer=QTimer(self); self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self.search_changed)
        self.kind.currentTextChanged.connect(self.refresh)
        self.restoreGeometry(self.settings.value('geometry',b''))
        self.horizontal.restoreState(self.settings.value('horizontal',b''))
        self.vertical.restoreState(self.settings.value('vertical',b''))
        with self.store.db:
            self.store.db.execute("UPDATE tasks SET state='interrupted' WHERE state='running'")
        self.load_projects(self.settings.value('project',0,type=int))
    def button(self,text,handler,primary=False):
        button=QPushButton(text); button.clicked.connect(handler)
        if primary: button.setObjectName('Primary')
        return button
    def heading(self,text):
        label=QLabel(text); label.setObjectName('Heading'); return label
    def build_ui(self):
        self.horizontal=QSplitter(); self.vertical=QSplitter(Qt.Vertical)
        self.setCentralWidget(self.horizontal)
        left=QWidget(); sidebar=QVBoxLayout(left)
        brand=QLabel('GHOSTMAP'); brand.setObjectName('Brand'); sidebar.addWidget(brand)
        sidebar.addWidget(QLabel('PROJECT WORKSPACE'))
        self.projects=QComboBox(); self.projects.currentIndexChanged.connect(self.change_project)
        sidebar.addWidget(self.projects)
        sidebar.addWidget(self.button('+ New project',self.new_project))
        self.nav=QListWidget(); self.nav.addItems(['Network Graph','Hosts','Scans','Attack chains','Notes','Tools'])
        self.nav.currentRowChanged.connect(self.navigate); sidebar.addWidget(self.nav)
        hint=QLabel('Local workspace\nSQLite · offline\n\nScan only targets you\nare authorized to test.'); hint.setStyleSheet('color: #93a4ba;')
        sidebar.addWidget(hint)
        self.horizontal.addWidget(left); self.horizontal.addWidget(self.vertical)
        central=QWidget(); center=QVBoxLayout(central)
        center.addWidget(self.heading('Infrastructure map'))
        filters=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('Search labels and notes…  Ctrl+F')
        self.kind=QComboBox(); self.kind.addItems(['All',*KINDS]); filters.addWidget(self.search); filters.addWidget(self.kind)
        center.addLayout(filters)
        actions=QHBoxLayout()
        for text,handler in [('+ IP',self.add_host),('+ Node',self.add_node),('Link',self.link),('Arrange',lambda:self.graph.layout_nodes()),('Fit',lambda:self.graph.fit()),('Import XML',self.import_file)]:
            actions.addWidget(self.button(text,handler))
        center.addLayout(actions)
        self.pages=QStackedWidget(); self.graph=Graph(self.store)
        self.graph.selected.connect(self.select_node)
        self.graph.create_requested.connect(self.add_node); self.graph.link_requested.connect(self.link)
        self.pages.addWidget(self.graph)
        self.listings=[]
        for index in range(5):
            listing=QListWidget(); self.listings.append(listing); self.pages.addWidget(listing)
        self.listings[0].itemClicked.connect(self.list_selected)
        self.listings[3].itemClicked.connect(self.list_selected)
        center.addWidget(self.pages)
        paging=QHBoxLayout(); paging.addWidget(self.button('Previous',lambda:self.page(-400)))
        self.page_label=QLabel(); paging.addWidget(self.page_label); paging.addStretch()
        paging.addWidget(self.button('Next',lambda:self.page(400))); center.addLayout(paging)
        self.vertical.addWidget(central)
        bottom=QWidget(); layout=QVBoxLayout(bottom)
        scan=QHBoxLayout(); self.target=QLineEdit(); self.target.setPlaceholderText('Authorized IPv4 / IPv6 address')
        self.profile=QComboBox(); self.profile.addItems(['Quick','Full','Service Enumeration','Custom'])
        self.ports=QLineEdit(); self.ports.setPlaceholderText('Custom ports: 22,80,443'); self.ports.setMaximumWidth(200)
        self.run_button=self.button('Run Nmap',self.run_scan,True); self.cancel_button=self.button('Cancel',self.scanner.cancel)
        self.cancel_button.setEnabled(False)
        for widget in [self.target,self.profile,self.ports,self.run_button,self.cancel_button]: scan.addWidget(widget)
        layout.addLayout(scan)
        self.progress=QProgressBar(); self.progress.setRange(0,1); self.progress.setValue(0); layout.addWidget(self.progress)
        tabs=QTabWidget(); self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setLineWrapMode(QPlainTextEdit.NoWrap); self.log.document().setMaximumBlockCount(600)
        tabs.addTab(self.log,'Tool output'); self.history=QListWidget(); tabs.addTab(self.history,'Task history'); layout.addWidget(tabs)
        self.vertical.addWidget(bottom)
        right=QWidget(); properties=QVBoxLayout(right); properties.addWidget(self.heading('Node inspector'))
        self.node_title=QLabel('Select a node to inspect'); self.node_title.setWordWrap(True); self.node_title.setTextFormat(Qt.PlainText); properties.addWidget(self.node_title)
        self.evidence=QLabel(); self.evidence.setWordWrap(True); self.evidence.setTextFormat(Qt.PlainText); properties.addWidget(self.evidence)
        self.status=QComboBox(); self.status.addItems(['hypothesis','confirmed']); properties.addWidget(self.status)
        self.detail=QPlainTextEdit(); self.detail.setPlaceholderText('Notes / evidence. Do not enter passwords or tokens.'); properties.addWidget(self.detail)
        self.save_button=self.button('Save notes & status',self.save_node); self.save_button.setEnabled(False); properties.addWidget(self.save_button)
        self.related=QLabel(); self.related.setWordWrap(True); self.related.setTextFormat(Qt.PlainText); properties.addWidget(self.related)
        self.horizontal.addWidget(right); self.horizontal.setSizes([200,900,280]); self.vertical.setSizes([560,240])
        self.nav.setCurrentRow(0)
        for title,shortcut,callback in [('New project','Ctrl+N',self.new_project),('Find','Ctrl+F',self.search.setFocus),('Fit map','Ctrl+0',self.graph.fit),('Save notes','Ctrl+S',self.save_node)]:
            action=QAction(title,self); action.setShortcut(QKeySequence(shortcut)); action.triggered.connect(callback); self.addAction(action)
        self.statusBar().showMessage('Create a project, add an authorized IP, then run Nmap.')
    def append_log(self,text):
        from PySide6.QtGui import QTextCursor
        cursor=self.log.textCursor(); cursor.movePosition(QTextCursor.End); cursor.insertText(text)
        overflow=self.log.document().characterCount()-100000
        if overflow>0:
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor,overflow)
            cursor.removeSelectedText()
        self.log.setTextCursor(cursor); self.log.ensureCursorVisible()
    def error(self,message): QMessageBox.warning(self,'GHOSTMAP',str(message))
    def load_projects(self,selected=None):
        self.projects.blockSignals(True); self.projects.clear()
        for row in self.store.projects(): self.projects.addItem(row['name'],row['id'])
        if selected:
            index=self.projects.findData(selected)
            if index>=0: self.projects.setCurrentIndex(index)
        self.projects.blockSignals(False); self.change_project()
    def change_project(self,*args):
        self.project_id=self.projects.currentData(); self.offset=0; self.node_id=None
        self.select_node(None); self.refresh()
    def require_project(self):
        if not self.project_id:
            self.error('Create a project first.'); return False
        return True
    def new_project(self):
        if self.scanner.busy or self.importer:
            self.error('Wait for the active scan or import.'); return
        name,ok=QInputDialog.getText(self,'New project','Project name')
        if ok:
            try: self.load_projects(self.store.project(name))
            except ValueError as exc: self.error(exc)
    def add_host(self):
        if not self.require_project(): return
        address,ok=QInputDialog.getText(self,'Add authorized host','IP address')
        if ok:
            try:
                self.store.host(self.project_id,address); self.target.setText(address); self.refresh()
            except ValueError as exc: self.error(exc)
    def add_node(self):
        if not self.require_project(): return
        kind,ok=QInputDialog.getItem(self,'New node','Type',KINDS,0,False)
        if not ok: return
        label,ok=QInputDialog.getText(self,'New node','Label (references only; do not enter secrets)')
        if ok:
            try:
                if kind=='Host': self.store.host(self.project_id,label)
                else: self.store.node(self.project_id,kind,label,x=50+(self.store.count(self.project_id)%5)*260,y=50)
                self.refresh()
            except ValueError as exc: self.error(exc)
    def select_node(self,row):
        self.node_id=row['id'] if row else None
        self.node_title.setText(f"{row['kind']}\n{row['label']}" if row else 'Select a node to inspect')
        self.evidence.setText('Observed: '+row['evidence'] if row and row['evidence'] else '')
        self.detail.setPlainText(row['detail'] if row else '')
        self.status.setCurrentText(row['status'] if row else 'hypothesis'); self.save_button.setEnabled(bool(row))
        self.related.setText('')
        if row and row['kind']=='Host': self.target.setText(row['label'])
        if row:
            edges=self.store.db.execute('SELECT label FROM edges WHERE source=? OR target=? LIMIT 20',(row['id'],row['id'])).fetchall()
            self.related.setText('Relationships\n'+'\n'.join(e['label'] for e in edges))
    def save_node(self):
        if self.node_id:
            self.store.details(self.node_id,self.detail.toPlainText(),self.status.currentText()); self.refresh()
            self.statusBar().showMessage('Notes and status saved')
    def link(self):
        if not self.require_project(): return
        items=[n for n in self.graph.scene().selectedItems() if isinstance(n,Node)]
        if len(items)!=2:
            self.error('Select two nodes with Ctrl+click or the selection rectangle.'); return
        items.sort(key=lambda n:n.row['id'])
        reverse=QMessageBox.question(self,'Link direction',f"Use {items[0].row['label']} → {items[1].row['label']}?\nChoose No to reverse.",QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel)
        if reverse==QMessageBox.Cancel: return
        if reverse==QMessageBox.No: items.reverse()
        label,ok=QInputDialog.getText(self,'Relationship','Label',text='related')
        if ok:
            self.store.edge(self.project_id,items[0].row['id'],items[1].row['id'],label[:120]); self.refresh()
    def navigate(self,index):
        self.pages.setCurrentIndex(max(0,index)); self.refresh()
    def search_changed(self):
        self.offset=0; self.search_timer.start(200)
    def page(self,delta):
        self.offset=max(0,self.offset+delta); self.refresh()
    def refresh(self,*args):
        if not hasattr(self,'page_label'): return
        if not self.project_id:
            self.graph.scene().clear(); self.page_label.setText('No project'); return
        rows=self.store.nodes(self.project_id,self.search.text(),self.offset)
        self.graph.load(self.project_id,self.search.text(),self.offset,self.kind.currentText())
        self.page_label.setText(f"{len(rows)} objects on page · offset {self.offset} · {self.store.count(self.project_id)} total")
        for listing in self.listings: listing.clear()
        for row in rows:
            index=0 if row['kind']=='Host' else 3 if row['kind']=='Note' else None
            if index is not None:
                item=QListWidgetItem(f"{row['label']} · {row['status']}\n{row['detail'][:120]}")
                item.setData(Qt.UserRole,dict(row)); self.listings[index].addItem(item)
        self.history.clear()
        for task in self.store.tasks(self.project_id):
            text=f"{task['created']} · {task['target']} · {task['profile']} · {task['state']}"
            self.history.addItem(text); self.listings[1].addItem(text)
        edges=self.store.edges(self.project_id,[r['id'] for r in rows]); labels={r['id']:r['label'] for r in rows}
        for edge in edges: self.listings[2].addItem(f"{labels[edge['source']]} → {labels[edge['target']]} · {edge['label']}")
        self.listings[2].insertItem(0,'Manual chains: add Finding / Access nodes, then link them on the map.')
        for tool in ('nmap','whatweb','httpx','ffuf'):
            path=shutil.which(tool)
            self.listings[4].addItem(f"{tool}: {path or 'not installed'}" + (' · integrated' if tool=='nmap' else ' · adapter planned'))
        self.listings[4].addItem('MVP runs Nmap only. No automatic exploitation. Credential nodes store references only.')
    def list_selected(self,item): self.select_node(item.data(Qt.UserRole))
    def set_busy(self,busy):
        self.projects.setEnabled(not busy); self.run_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy and self.scanner.busy)
        self.progress.setRange(0,0 if busy else 1); self.progress.setValue(0 if busy else 1)
    def run_scan(self):
        if not self.require_project(): return
        profile=self.profile.currentText()
        message=f"I am authorized to scan {self.target.text()}.\nProfile: {profile}.\nVersion probes send traffic to services."
        if profile!='Quick': message+='\nThis profile may generate substantial traffic or take a long time.'
        if QMessageBox.question(self,'Confirm authorized scan',message,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        try:
            self.scanner.start(self.project_id,self.target.text(),profile,self.ports.text())
            self.task_id=self.store.task(self.project_id,self.target.text(),profile)
            self.log.clear(); self.statusBar().showMessage('Nmap running · parsing follows automatically')
        except ValueError as exc: self.error(exc)
    def imported(self,counts):
        self.refresh(); self.graph.fit(); self.statusBar().showMessage(f'Imported {counts[0]} hosts and {counts[1]} open services')
    def scan_complete(self,result):
        if self.task_id:
            self.store.finish_task(self.task_id,result.lower()); self.task_id=None
        self.refresh(); self.append_log('\n'+result)
    def import_file(self):
        if not self.require_project(): return
        if self.scanner.busy or self.importer:
            self.error('Wait for the active scan or import.'); return
        path,_=QFileDialog.getOpenFileName(self,'Import Nmap XML','','XML (*.xml)')
        if not path: return
        self.set_busy(True)
        self.importer=ImportWorker(path,str(self.store.path),self.project_id,self)
        self.importer.done.connect(self.imported); self.importer.failed.connect(self.error)
        self.importer.finished.connect(self.import_done); self.importer.start()
    def import_done(self):
        self.importer.deleteLater(); self.importer=None; self.set_busy(False)
    def closeEvent(self,event):
        if self.scanner.busy or self.importer:
            self.error('Cancel the active scan and wait for the import to finish before closing.'); event.ignore(); return
        self.settings.setValue('project',self.project_id or 0)
        self.settings.setValue('geometry',self.saveGeometry())
        self.settings.setValue('horizontal',self.horizontal.saveState())
        self.settings.setValue('vertical',self.vertical.saveState()); self.settings.sync()
        self.store.close(); super().closeEvent(event)

def main():
    parser=argparse.ArgumentParser(description='GHOSTMAP native desktop workstation')
    parser.add_argument('--database',type=Path,help='Override project SQLite path')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1]); app.setApplicationName('GHOSTMAP'); app.setOrganizationName('GHOSTMAP')
    app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=Window(args.database); window.show()
    sys.exit(app.exec())
