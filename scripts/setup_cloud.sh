#!/bin/bash
# Unprivileged, signed Debian packages; no system files are modified.
set -euo pipefail
cd /workspace/HEXTRACE
setup_root=/workspace/ghostmap-tools
mkdir -p "$setup_root/apt/lists/partial" "$setup_root/apt/cache/archives/partial" "$setup_root/root" "$setup_root/bin" "$setup_root/cache"
cat > "$setup_root/apt/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
SOURCES
cat > "$setup_root/apt.conf" <<'CONFIG'
Dir::Etc::main "/dev/null";
Dir::Etc::parts "";
Dir::Etc::sourcelist "/workspace/ghostmap-tools/apt/sources.list";
Dir::Etc::sourceparts "";
Dir::State "/workspace/ghostmap-tools/apt";
Dir::State::status "/var/lib/dpkg/status";
Dir::Cache "/workspace/ghostmap-tools/apt/cache";
Debug::NoLocking "true";
CONFIG
export APT_CONFIG="$setup_root/apt.conf"
if ! /workspace/ghostmap-tools/bin/ghostmap-python -c 'from PySide6 import QtWidgets, QtTest' 2>/dev/null || ! /workspace/ghostmap-tools/bin/nmap --version >/dev/null 2>&1; then
    apt-get update
    download_dir=$(mktemp -d "$setup_root/download.XXXXXX")
    trap 'rm -rf "$download_dir"' EXIT
    cd "$download_dir"
    /usr/bin/python3 - <<'PY'
import subprocess
packages=['python3-pyside6.qtcore','python3-pyside6.qtgui','python3-pyside6.qtwidgets','python3-pyside6.qttest','nmap','nmap-common']
r=subprocess.run(['apt-get','--simulate','install',*packages],capture_output=True,text=True,check=True)
missing=[line.split()[1] for line in r.stdout.splitlines() if line.startswith('Inst ')]
subprocess.run(['apt-get','download',*dict.fromkeys(packages+missing)],check=True)
PY
    for package in "$download_dir"/*.deb; do dpkg-deb -x "$package" "$setup_root/root"; done
fi
cat > "$setup_root/bin/nmap" <<'NMAP'
#!/bin/sh
export LD_LIBRARY_PATH="/workspace/ghostmap-tools/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export NMAPDIR=/workspace/ghostmap-tools/root/usr/share/nmap
exec /workspace/ghostmap-tools/root/usr/bin/nmap "$@"
NMAP
cat > "$setup_root/bin/ghostmap-python" <<'PYTHON'
#!/bin/sh
export LD_LIBRARY_PATH="/workspace/ghostmap-tools/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="/workspace/HEXTRACE:/workspace/ghostmap-tools/root/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export PATH="/workspace/ghostmap-tools/bin:$PATH"
export XDG_CACHE_HOME=/workspace/ghostmap-tools/cache
exec /usr/bin/python3 "$@"
PYTHON
chmod 755 "$setup_root/bin/nmap" "$setup_root/bin/ghostmap-python"
cd /workspace/HEXTRACE
"$setup_root/bin/ghostmap-python" -c 'from PySide6 import QtCore, QtWidgets; print("Qt",QtCore.__version__)'
"$setup_root/bin/nmap" --version
python3 scripts/build_deb.py
# Installed artifacts were verified by APT; indexes and archives are expendable.
find "$setup_root/apt/lists" -maxdepth 1 -type f -delete

find "$setup_root/apt/cache" -maxdepth 1 -type f -name "*.bin" -delete
