"""Run the narrow cleanup probes with the existing isolated Linux QA runner."""
from pathlib import Path
import os, sys
source=Path(sys.argv[1]).resolve()
assert sys.platform=='linux'
assert {os.open, os.stat, os.unlink, os.rmdir} <= os.supports_dir_fd
launcher=source/'qa/f14/linux/run_linux.py'
text=launcher.read_text()
old="if mode=='backend':args+=[str(source/'tests/backend')]"
new="if mode=='backend':args+=[str(source/'qa/f24/test_nonempty_cleanup.py')]"
assert text.count(old)==1
text=text.replace(old,new).replace('label=mode;root=', "label='f24-targeted';root=")
sys.argv=[str(launcher),str(source),'backend']
exec(compile(text,str(launcher),'exec'),{'__name__':'__main__','__file__':str(launcher)})
