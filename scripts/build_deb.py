#!/usr/bin/env python3
"""Build a tiny architecture-independent package using system Qt and Python."""
from pathlib import Path
import shutil
import subprocess
root=Path(__file__).resolve().parents[1]
stage=root/'build/deb'
if stage.exists(): shutil.rmtree(stage)
(stage/'DEBIAN').mkdir(parents=True)
(stage/'usr/bin').mkdir(parents=True)
(stage/'usr/share/applications').mkdir(parents=True)
(stage/'usr/share/icons/hicolor/scalable/apps').mkdir(parents=True)
shutil.copytree(root/'ghostmap',stage/'usr/share/ghostmap/ghostmap',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(stage/'usr/bin/ghostmap').write_text('#!/bin/sh\nexport PYTHONPATH="/usr/share/ghostmap${PYTHONPATH:+:$PYTHONPATH}"\nexec /usr/bin/python3 -m ghostmap "$@"\n')
(stage/'usr/bin/ghostmap').chmod(0o755)
(stage/'usr/share/applications/ghostmap.desktop').write_text('''[Desktop Entry]
Type=Application
Name=GHOSTMAP
Comment=Native network map and security project workspace
Exec=ghostmap
Icon=ghostmap
Terminal=false
Categories=Network;Utility;
''')
shutil.copy(root/'ghostmap/assets/ghostmap.svg',stage/'usr/share/icons/hicolor/scalable/apps/ghostmap.svg')
size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
(stage/'DEBIAN/control').write_text(f'''Package: ghostmap
Version: 0.1.0
Section: net
Priority: optional
Architecture: all
Maintainer: GHOSTMAP contributors <ghostmap@localhost>
Depends: python3 (>= 3.10), python3-pyside6.qtcore, python3-pyside6.qtgui, python3-pyside6.qtwidgets, nmap
Installed-Size: {(size+1023)//1024}
Description: Lightweight native network mapping workspace
 Local projects, Nmap integration and an interactive Qt infrastructure graph.
''')
for path in stage.rglob('*'):
    path.chmod(0o755 if path.is_dir() or path == stage/'usr/bin/ghostmap' else 0o644)
stage.chmod(0o755)
(root/'dist').mkdir(exist_ok=True)
subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(root/'dist/ghostmap_0.1.0_all.deb')],check=True)
