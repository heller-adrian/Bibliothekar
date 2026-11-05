"""Run native F13 probes using the existing isolated Linux QA launcher."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).resolve()
assert sys.platform == 'linux', 'Native Linux required'
launcher = source / 'qa/f14/linux/run_linux.py'
text = launcher.read_text()
start = text.index('selections=')
end = text.index('\nlabel=mode;', start)
selections = [str(source / 'qa/f13/test_f13_ssd_guard.py'),
              str(source / 'qa/f13/test_f13_restart_contract.py')]
text = text[:start] + 'selections=' + repr(selections) + text[end:]
text = text.replace("else:args+=['-p','complete_historical_fixture']+[str(original/n) for n in selections]",
                    'else:args+=selections')
# Native assertions are required to pass. Do not apply historical-red handling.
text = text.replace("if mode=='backend':raise SystemExit(result.returncode)",
                    'raise SystemExit(result.returncode)')
sys.argv = [str(launcher), str(source), 'native-f13']
namespace = {'__name__': '__main__', '__file__': str(launcher)}
exec(compile(text, str(launcher), 'exec'), namespace)
