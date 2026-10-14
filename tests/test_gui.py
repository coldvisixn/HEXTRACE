import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import shutil
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import tempfile
import time
import unittest
from pathlib import Path
from PySide6.QtCore import QSettings, QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from ghostmap.app import Window
from ghostmap.scanner import Scanner

APP=QApplication.instance() or QApplication([])

class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)
        self.settings=QSettings(str(self.path/'settings.ini'),QSettings.IniFormat)
        self.window=Window(self.path/'db.sqlite3',self.settings)
        project=self.window.store.project('GUI Lab'); self.window.load_projects(project)
        self.project=project; self.window.show(); APP.processEvents()
    def tearDown(self):
        self.window.close(); APP.processEvents(); self.tmp.cleanup()
    def test_graph_and_splitters_restore(self):
        store=self.window.store
        host=store.host(self.project,'127.0.0.1')
        note=store.node(self.project,'Note','investigate',x=300,y=200)
        store.edge(self.project,host,note,'next step'); self.window.refresh()
        self.assertEqual(len(self.window.graph.nodes),2)
        self.assertEqual(len(store.edges(self.project,[host,note])),1)
        self.window.graph.layout_nodes()
        n=self.window.graph.nodes[host]; n.setPos(231,177)
        store.position(host,n.pos().x(),n.pos().y())
        n.setSelected(True); APP.processEvents(); self.window.detail.setPlainText('saved observation'); self.window.save_node()
        before=self.window.graph.transform().m11(); self.window.graph.scale(1.15,1.15)
        self.assertGreater(self.window.graph.transform().m11(),before)
        self.window.horizontal.setSizes([190,810,260]); self.window.close()
        self.window=Window(self.path/'db.sqlite3',self.settings); self.window.load_projects(self.project)
        self.window.show(); APP.processEvents()
        row=next(r for r in self.window.store.nodes(self.project) if r['id']==host)
        self.assertEqual((row['x'],row['y'],row['detail']),(231,177,'saved observation'))
        self.assertEqual(len(self.window.graph.nodes),2)
        self.assertTrue(self.settings.contains('horizontal'))
    def test_wheel_pan_and_drag_persist(self):
        host=self.window.store.host(self.project,'192.0.2.1')
        self.window.refresh(); self.window.graph.fit(); APP.processEvents()
        graph=self.window.graph; node=graph.nodes[host]
        point=graph.mapFromScene(node.pos()+QPointF(30,30))
        start=node.pos()
        QTest.mousePress(graph.viewport(),Qt.LeftButton,Qt.NoModifier,point)
        end=point+QPoint(40,25)
        APP.sendEvent(graph.viewport(),QMouseEvent(QEvent.MouseMove,QPointF(end),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
        QTest.mouseRelease(graph.viewport(),Qt.LeftButton,Qt.NoModifier,end)
        APP.processEvents()
        self.assertNotEqual(node.pos(),start)
        row=self.window.store.nodes(self.project)[0]
        self.assertAlmostEqual(row['x'],node.pos().x())
        before=graph.transform().m11()
        wheel=QWheelEvent(QPointF(point),QPointF(graph.viewport().mapToGlobal(point)),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        APP.sendEvent(graph.viewport(),wheel)
        self.assertGreater(graph.transform().m11(),before)
        scroll=graph.horizontalScrollBar().value()
        QTest.mousePress(graph.viewport(),Qt.MiddleButton,Qt.NoModifier,point)
        APP.sendEvent(graph.viewport(),QMouseEvent(QEvent.MouseMove,QPointF(point+QPoint(20,0)),Qt.NoButton,Qt.MiddleButton,Qt.NoModifier))
        QTest.mouseRelease(graph.viewport(),Qt.MiddleButton,Qt.NoModifier,point+QPoint(20,0))
        self.assertNotEqual(graph.horizontalScrollBar().value(),scroll)
    def test_log_is_bounded_even_without_newlines(self):
        for _ in range(7): self.window.append_log('x'*16000)
        self.assertLessEqual(self.window.log.document().characterCount(),100000)
    def test_scanner_rejects_targets_and_ports(self):
        scanner=self.window.scanner
        with self.assertRaises(ValueError): scanner.start(self.project,'localhost;whoami','Quick')
        if shutil.which('nmap'):
            with self.assertRaises(ValueError): scanner.start(self.project,'127.0.0.1','Custom','65536')
        self.assertFalse(scanner.busy)
    @unittest.skipUnless(shutil.which('nmap'),'Nmap unavailable')
    def test_real_nmap_qprocess_imports_loopback_service(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'GHOSTMAP local fixture')
            def log_message(self,*args): pass
        class FixtureServer(ThreadingHTTPServer):
            def handle_error(self,request,client_address):
                # TCP reset is expected when a port scanner closes a probe.
                import sys
                if not isinstance(sys.exc_info()[1],ConnectionResetError):
                    super().handle_error(request,client_address)
        server=FixtureServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            port=server.server_port; completed=[]; imported=[]
            self.window.scanner.complete.connect(completed.append)
            self.window.scanner.imported.connect(imported.append)
            self.window.scanner.start(self.project,'127.0.0.1','Custom',str(port))
            # A second scan is rejected before spawning any process.
            with self.assertRaises(ValueError): self.window.scanner.start(self.project,'127.0.0.1','Quick')
            deadline=time.monotonic()+90
            while not completed and time.monotonic()<deadline:
                APP.processEvents(); QTest.qWait(20)
            if not completed:
                self.window.scanner.cancel()
                deadline=time.monotonic()+10
                while self.window.scanner.busy and time.monotonic()<deadline:
                    APP.processEvents(); QTest.qWait(20)
            self.assertEqual(completed,['Completed'])
            self.assertEqual(imported,[(1,1)])
            services=[r for r in self.window.store.nodes(self.project) if r['kind']=='Service']
            self.assertEqual(services[0]['label'],f'127.0.0.1:{port}/tcp')
        finally: server.shutdown(); server.server_close()
