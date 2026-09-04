"""Reversible light-work limits using the machine's supported kernel interfaces."""
import json
import subprocess
from pathlib import Path

STATE = Path('/run/bizon-quiet-mode/restore.json')
CPU = Path('/sys/devices/system/cpu/cpufreq')
ATTR = Path('/sys/class/firmware-attributes/asus-armoury/attributes')
LIMITS = {'ppt_pl1_spl': 28, 'ppt_pl2_sppt': 32, 'ppt_pl3_fppt': 45}


def profile(value=None):
    result = subprocess.run(['/usr/bin/powerprofilesctl', 'set', value] if value else
                            ['/usr/bin/powerprofilesctl', 'get'],
                            check=True, capture_output=True, text=True, timeout=5)
    return result.stdout.strip()


def apply():
    if STATE.exists():
        raise RuntimeError('Previous Quiet Mode settings must be restored first')
    paths = [CPU / 'boost']
    for policy in sorted(CPU.glob('policy*')):
        paths += [policy / 'scaling_min_freq', policy / 'scaling_max_freq']
    paths += [ATTR / name / 'current_value' for name in LIMITS]
    snapshot = {'profile': profile(), 'values': {str(p): p.read_text().strip() for p in paths}}
    STATE.parent.mkdir(mode=0o700, exist_ok=True)
    STATE.write_text(json.dumps(snapshot))
    STATE.chmod(0o600)
    try:
        profile('power-saver')
        (CPU / 'boost').write_text('0\n')
        for policy in sorted(CPU.glob('policy*')):
            low = int((policy / 'cpuinfo_min_freq').read_text())
            (policy / 'scaling_min_freq').write_text(f'{low}\n')
            cap = min(int(snapshot['values'][str(policy / 'scaling_max_freq')]), 2200000)
            (policy / 'scaling_max_freq').write_text(f'{cap}\n')
        for name, value in LIMITS.items():
            attr = ATTR / name
            if not int((attr / 'min_value').read_text()) <= value <= int((attr / 'max_value').read_text()):
                raise RuntimeError(f'{name}: unsupported power limit')
            (attr / 'current_value').write_text(f'{value}\n')
    except Exception:
        restore()
        raise


def restore(restore_profile=True):
    if not STATE.exists():
        return
    snapshot = json.loads(STATE.read_text())
    errors = []
    # Restore boost first so the original maximum clocks are accepted.
    values = snapshot['values']
    ordered = sorted(values, key=lambda p: (0 if p.endswith('/boost') else
                     2 if p.endswith('/scaling_min_freq') else 1, p))
    for name in ordered:
        try:
            Path(name).write_text(values[name] + '\n')
        except OSError as error:
            errors.append(str(error))
    if restore_profile:
        try:
            profile(snapshot['profile'])
        except Exception as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError('; '.join(errors))
    STATE.unlink()
