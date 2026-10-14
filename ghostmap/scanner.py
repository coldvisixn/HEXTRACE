"""One QProcess scanner, a bounded output buffer, off-thread XML import."""
import ipaddress
import os
import shutil
import tempfile
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QThread, Signal, QTimer
from .nmapxml import import_xml

class ImportWorker(QThread):
    done = Signal(object)
    failed = Signal(str)
    def __init__(self, path, database, project, parent=None):
        super().__init__(parent)
        self.args = (path, database, project)
    def run(self):
        try: self.done.emit(import_xml(*self.args))
        except Exception as exc: self.failed.emit(str(exc))

class Scanner(QObject):
    output = Signal(str)
    complete = Signal(str)
    imported = Signal(object)
    busy_changed = Signal(bool)
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.error)
        self.worker = None
        self.temp = None
        self.busy = False
        self.cancelled = False
    def start(self, project, target, profile, ports=''):
        if self.busy: raise ValueError('A scan or import is already running')
        target = str(ipaddress.ip_address(target.strip()))
        executable = shutil.which('nmap')
        if not executable: raise ValueError('Nmap is missing. Install the nmap system package.')
        args = ['-sT','-sV','--version-light','--stats-every','2s','--host-timeout','15m']
        if ':' in target: args += ['-6']
        if profile == 'Quick': args += ['--top-ports','100']
        elif profile == 'Full': args += ['-p-']
        elif profile == 'Service Enumeration': args += ['--top-ports','1000','--version-all']
        elif profile == 'Custom':
            import re
            if not re.fullmatch(r'\d{1,5}(-\d{1,5})?(,\d{1,5}(-\d{1,5})?)*',ports):
                raise ValueError('Custom ports: 22,80,443 or 1-1024')
            for part in ports.split(','):
                values = list(map(int,part.split('-')))
                if any(v<1 or v>65535 for v in values) or values[0]>values[-1]:
                    raise ValueError('Ports must be in range 1–65535')
            args += ['-p',ports]
        else: raise ValueError('Unknown profile')
        self.temp = tempfile.TemporaryDirectory(prefix='ghostmap-')
        os.chmod(self.temp.name,0o700)
        self.path = str(Path(self.temp.name)/'scan.xml')
        self.project = project
        self.cancelled = False
        self.busy = True
        self.busy_changed.emit(True)
        self.process.start(executable,[*args,'-oX',self.path,target])
    def read(self):
        data = bytes(self.process.readAllStandardOutput())
        self.output.emit(data[-16384:].decode(errors='replace'))
    def error(self, error):
        if error == QProcess.FailedToStart:
            self.cleanup('Failed to start Nmap: '+self.process.errorString())
    def finished(self, code, status):
        self.read()
        if self.cancelled:
            self.cleanup('Cancelled'); return
        if code != 0 or status != QProcess.NormalExit:
            self.cleanup(f'Nmap failed (exit {code})'); return
        self.worker = ImportWorker(self.path,self.database,self.project,self)
        self.worker.done.connect(self.imported.emit)
        self.worker.failed.connect(lambda msg: self.output.emit('Import error: '+msg))
        self.import_error = False
        self.worker.failed.connect(self.mark_error)
        self.worker.finished.connect(self.import_finished)
        self.worker.start()
    def mark_error(self, message): self.import_error = True
    def import_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.cleanup('Import failed' if self.import_error else 'Completed')
    def cancel(self):
        if self.process.state() != QProcess.NotRunning:
            self.cancelled = True
            self.process.terminate()
            QTimer.singleShot(2000,self.kill_if_cancelled)
    def kill_if_cancelled(self):
        if self.cancelled and self.process.state()!=QProcess.NotRunning: self.process.kill()
    def cleanup(self, result):
        if self.temp: self.temp.cleanup(); self.temp = None
        self.busy = False
        self.busy_changed.emit(False)
        self.complete.emit(result)
