#!/usr/bin/python3
"""Install this app and the restricted backend on a compatible ASUS Z13."""
import datetime
import argparse
import os
from pathlib import Path
import pwd
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def run(*args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Preview installation without changing files or hardware')
    args = parser.parse_args()
    if os.getuid() == 0:
        raise SystemExit('Run as your desktop user, without sudo; the installer requests sudo where needed.')
    if args.dry_run:
        print('Would validate GZ302EAC hardware, install the user app and launcher, back up and replace the restricted root backend.')
        print('Existing profiles are preserved. Replacing the backend restores automatic cooling.')
        return
    model = Path('/sys/class/dmi/id/product_name')
    if not model.exists() or 'GZ302EAC' not in model.read_text():
        raise SystemExit('This installer supports the ROG Flow Z13 GZ302EAC only. No files were changed.')
    import gi
    gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')
    import cairo
    if not any((p / 'name').read_text().strip() == 'asus_custom_fan_curve'
               for p in Path('/sys/class/hwmon').glob('hwmon*')):
        raise SystemExit('The supported ASUS custom fan interface was not found.')
    attrs = Path('/sys/class/firmware-attributes/asus-armoury/attributes')
    if not all((attrs / name / 'current_value').exists() for name in ('ppt_pl1_spl', 'ppt_pl2_sppt', 'ppt_pl3_fppt')):
        raise SystemExit('The supported ASUS power-limit interfaces were not found.')
    user, uid = pwd.getpwuid(os.getuid()).pw_name, os.getuid()
    destination = Path.home() / '.local/share/z13-fan-control'
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('app.py', 'curves.py', 'style.css', 'icon.svg', 'README.md'):
        shutil.copy2(HERE / name, destination / name)
    commands = Path.home() / '.local/bin'
    commands.mkdir(parents=True, exist_ok=True)
    command = commands / 'z13-fan-control'
    command.write_text(f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(str(destination / "app.py"))} "$@"\n')
    command.chmod(0o755)
    launchers = Path.home() / '.local/share/applications'; launchers.mkdir(parents=True, exist_ok=True)
    (launchers / 'com.bizon.Z13FanControl.desktop').write_text(f'''[Desktop Entry]
Type=Application
Name=Z13 Fan Control
Comment=Fan curves, quiet profiles and live cooling readings
Exec=/usr/bin/python3 "{destination / 'app.py'}"
Icon={destination / 'icon.svg'}
Terminal=false
Categories=Settings;HardwareSettings;System;
Keywords=z13;fan;fans;quiet;temperature;cooling;curves;
StartupNotify=true
''')
    run('sudo', '-v')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path('/var/backups') / f'z13-fan-control-{stamp}'
    run('sudo', 'mkdir', '-p', str(backup))
    for source in ('/usr/local/lib/bizon-fan-control', '/etc/systemd/system/bizon-fan-control.service',
                   '/etc/dbus-1/system.d/com.bizon.FanControl.conf'):
        if Path(source).exists(): run('sudo', 'cp', '-a', source, str(backup))
    subprocess.run(['sudo', 'systemctl', 'stop', 'bizon-fan-control.service'], check=False)
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        service = (HERE / 'backend/service.py').read_text().replace('(0, 1000)', f'(0, {uid})')
        (tmp / 'service.py').write_text(service)
        run('sudo', 'install', '-d', '-m', '755', '/usr/local/lib/bizon-fan-control')
        for source in (tmp / 'service.py', HERE / 'backend/quiet.py', HERE / 'curves.py'):
            run('sudo', 'install', '-m', '644', str(source), f'/usr/local/lib/bizon-fan-control/{source.name}')
        (tmp / 'backend.service').write_text('''[Unit]
Description=Z13 fan and quiet-profile control
After=dbus.service

[Service]
Type=dbus
BusName=com.bizon.FanControl
ExecStart=/usr/bin/python3 -I /usr/local/lib/bizon-fan-control/service.py
ExecStopPost=/usr/bin/python3 -I /usr/local/lib/bizon-fan-control/service.py --restore
Restart=on-failure
RestartSec=2
RuntimeDirectory=bizon-quiet-mode
RuntimeDirectoryMode=0700
StateDirectory=bizon-fan-control
StateDirectoryMode=0700
ReadWritePaths=/run/bizon-quiet-mode /var/lib/bizon-fan-control
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
RestrictAddressFamilies=AF_UNIX
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
''')
        (tmp / 'policy.conf').write_text(f'''<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
<policy user="root"><allow own="com.bizon.FanControl"/><allow send_destination="com.bizon.FanControl"/></policy>
<policy context="default"><deny send_destination="com.bizon.FanControl"/></policy>
<policy user="{user}"><allow send_destination="com.bizon.FanControl" send_interface="com.bizon.FanControl"/><allow send_destination="com.bizon.FanControl" send_interface="org.freedesktop.DBus.Introspectable"/></policy>
</busconfig>
''')
        run('sudo', 'install', '-m', '644', str(tmp / 'backend.service'), '/etc/systemd/system/bizon-fan-control.service')
        run('sudo', 'install', '-m', '644', str(tmp / 'policy.conf'), '/etc/dbus-1/system.d/com.bizon.FanControl.conf')
    run('sudo', 'systemctl', 'daemon-reload')
    run('sudo', 'systemctl', 'enable', '--now', 'bizon-fan-control.service')
    run('update-desktop-database', str(launchers))
    print('Installed. Open Z13 Fan Control from your launcher. Automatic cooling is active.')


if __name__ == '__main__': main()
