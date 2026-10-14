import tempfile
import unittest
from pathlib import Path
from ghostmap.store import Store
from ghostmap.nmapxml import import_xml

XML='''<nmaprun><host><status state="up"/><address addr="127.0.0.1" addrtype="ipv4"/>
<ports><port protocol="tcp" portid="8080"><state state="open"/><service name="http" product="Fixture" version="1"/></port>
<port protocol="tcp" portid="22"><state state="closed"/></port></ports></host>
<host><status state="down"/><address addr="192.0.2.9" addrtype="ipv4"/></host></nmaprun>'''

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'db.sqlite3'
        self.store=Store(self.path); self.project=self.store.project('Lab')
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def test_import_is_idempotent_and_preserves_layout_and_notes(self):
        xml=Path(self.tmp.name)/'nmap.xml'; xml.write_text(XML)
        self.assertEqual(import_xml(xml,self.path,self.project),(1,1))
        rows=self.store.nodes(self.project); self.assertEqual(len(rows),2)
        service=next(r for r in rows if r['kind']=='Service')
        self.assertEqual(service['evidence'],'http Fixture 1')
        self.assertEqual(len(self.store.edges(self.project,[r['id'] for r in rows])),1)
        self.store.position(service['id'],731,42); self.store.details(service['id'],'manual evidence','confirmed')
        import_xml(xml,self.path,self.project)
        service=next(r for r in self.store.nodes(self.project) if r['kind']=='Service')
        self.assertEqual((service['x'],service['y'],service['detail']),(731,42,'manual evidence'))
        self.assertEqual(self.store.count(self.project),2)
    def test_ip_and_project_isolation(self):
        with self.assertRaises(ValueError): self.store.host(self.project,'127.0.0.1;touch /tmp/no')
        host=self.store.host(self.project,'::1'); other=self.store.project('Other')
        node=self.store.node(other,'Note','a')
        with self.assertRaises(ValueError): self.store.edge(self.project,host,node)
        self.assertEqual(len(self.store.nodes(other)),1)
    def test_pagination_and_reopen(self):
        for i in range(405): self.store.node(self.project,'Note',f'note {i}')
        self.assertEqual(len(self.store.nodes(self.project)),400)
        self.assertEqual(len(self.store.nodes(self.project,offset=400)),5)
        self.store.close(); self.store=Store(self.path)
        self.assertEqual(self.store.count(self.project),405)
    def test_invalid_xml_reports_failure(self):
        xml=Path(self.tmp.name)/'bad.xml'; xml.write_text(XML.replace('</nmaprun>','<broken>'))
        import xml.etree.ElementTree as ET
        with self.assertRaises(ET.ParseError): import_xml(xml,self.path,self.project)
        self.assertEqual(self.store.count(self.project),0)
