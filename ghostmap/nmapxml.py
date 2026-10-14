"""Streaming import; no raw output or secrets retained."""
import ipaddress
import xml.etree.ElementTree as ET
from .store import Store

def import_xml(path, database, project):
    store = Store(database)
    hosts = services = 0
    try:
        for event, element in ET.iterparse(path, events=('end',)):
            if element.tag != 'host': continue
            state = element.find('status')
            if state is None or state.get('state') != 'up':
                element.clear(); continue
            address = next((a.get('addr') for a in element.findall('address') if a.get('addrtype') in ('ipv4','ipv6')), None)
            if address is None:
                element.clear(); continue
            address = str(ipaddress.ip_address(address))
            host = store.node(project,'Host',address,'','confirmed',40,hosts*160,evidence='Observed by Nmap')
            hosts += 1
            for port in element.findall('ports/port'):
                state = port.find('state')
                if state is None or state.get('state') != 'open': continue
                service = port.find('service')
                attrs = service.attrib if service is not None else {}
                label = f"{address}:{port.get('portid')}/{port.get('protocol')}"
                detail = ' '.join(attrs.get(k,'') for k in ('name','product','version','extrainfo')).strip()
                node = store.node(project,'Service',label,'','confirmed',320,services*110,evidence=detail)
                store.edge(project,host,node,'exposes')
                services += 1
            element.clear()
        return hosts, services
    finally:
        store.close()
