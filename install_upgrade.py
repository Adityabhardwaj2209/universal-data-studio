"""Install this reviewed bundle into an existing Windows project with backups."""
from pathlib import Path
from datetime import datetime
import argparse
import py_compile
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('--target',type=Path,default=Path.home()/'sales-report-automation')
args=parser.parse_args();source=Path(__file__).resolve().parent;target=args.target.resolve()
if source==target:raise SystemExit('Extract the upgrade into a separate folder before installing.')
if not (target/'app.py').exists():raise SystemExit('Existing app.py not found: '+str(target))
files=[Path('app.py'),Path('requirements.txt'),Path('.gitignore')]+[p.relative_to(source) for p in (source/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.ttf','.txt']]
for relative in files:
    if relative.suffix=='.py':py_compile.compile(str(source/relative),doraise=True)
backup=target/'upgrade_backups'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
backup.mkdir(parents=True)
written=[]
try:
    for relative in files:
        destination=target/relative
        if destination.exists():
            saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,saved)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/relative,destination);written.append(relative)
except Exception:
    for relative in reversed(written):
        saved=backup/relative
        if saved.exists():shutil.copy2(saved,target/relative)
        else:(target/relative).unlink(missing_ok=True)
    raise
print('UPGRADE INSTALLED')
print('Backup:',backup)
print('Private accounts, mail settings and databases were not copied or replaced.')
