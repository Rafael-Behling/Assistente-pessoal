#!/usr/bin/env python3
import sys
import os
import subprocess
from pathlib import Path

# Inicia script pra forçar posição
subprocess.Popen(['/tmp/fix_orb.sh'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Inicia a bolinha
orb_path = Path(__file__).parent / "ui" / "orb.py"
env = os.environ.copy()
env['QT_QPA_PLATFORM'] = 'wayland'
subprocess.Popen([sys.executable, str(orb_path)], env=env)
