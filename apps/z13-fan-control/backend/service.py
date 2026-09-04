#!/usr/bin/python3
"""Restricted ASUS fan control service for the local desktop."""
import json
import math
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0, '/usr/local/lib/bizon-fan-control')
import quiet
from curves import defaults, validate_profile

from gi.repository import Gio, GLib

NAME = 'com.bizon.FanControl'
OBJECT = '/com/bizon/FanControl'
XML = '''<node><interface name="com.bizon.FanControl">
<method name="Status"><arg type="s" direction="out"/></method>
<method name="SetSpeed"><arg type="u" direction="in"/></method>
<method name="Automatic"/>
<method name="KeepAlive"/>
<method name="QuietOn"/>
<method name="QuietOff"/>
<method name="SetProfile"><arg type="s" direction="in"/></method>
</interface></node>'''
QUIET_CONFIG = Path('/var/lib/bizon-fan-control/quiet-profile.json')
TEMPERATURES = [30, 40, 50, 60, 70, 75, 80, 85]


def curve(percent):
    if type(percent) is not int or not 30 <= percent <= 100:
        raise ValueError('Fan speed must be between 30 and 100 percent')
    # Firmware handles the thermal ramp even if the desktop stops responding.
    speeds = [percent] * 6 + [max(percent, 80), 100]
    return list(zip(TEMPERATURES, [math.ceil(v * 255 / 100) for v in speeds]))


class Hardware:
    def __init__(self, root=Path('/sys/class/hwmon')):
        self.root = root
        self.fans = self.find('asus_custom_fan_curve')
        for fan in (1, 2):
            if not (self.fans / f'pwm{fan}_enable').exists():
                raise RuntimeError('Both ASUS fan curve controls are required')

    def find(self, name):
        for p in self.root.glob('hwmon*'):
            if (p / 'name').read_text().strip() == name:
                return p
        raise RuntimeError(f'{name} is not available')

    def automatic(self):
        errors = []
        for fan in (1, 2):
            try:
                (self.fans / f'pwm{fan}_enable').write_text('2\n')
            except OSError as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))

    def apply(self, percent):
        self.apply_points(curve(percent))

    def apply_profile(self, data):
        cpu = [(t, math.ceil(v * 255 / 100)) for t, v in data['cpu']]
        gpu = [(t, math.ceil(v * 255 / 100)) for t, v in data['gpu']]
        self.apply_points(cpu, gpu)

    def apply_points(self, points, gpu_points=None):
        try:
            for fan in (1, 2):
                for index, (temp, pwm) in enumerate(gpu_points if fan == 2 and gpu_points is not None else points, 1):
                    (self.fans / f'pwm{fan}_auto_point{index}_temp').write_text(f'{temp}\n')
                    (self.fans / f'pwm{fan}_auto_point{index}_pwm').write_text(f'{pwm}\n')
            for fan in (1, 2):
                (self.fans / f'pwm{fan}_enable').write_text('1\n')
        except Exception:
            self.automatic()
            raise

    def manual_enabled(self):
        return all((self.fans / f'pwm{fan}_enable').read_text().strip() == '1'
                   for fan in (1, 2))

    def readings(self):
        result = {'rpm': [None, None], 'temperature': None, 'gpu_temperature': None, 'power': None}
        try:
            p = self.find('asus')
            result['rpm'] = [int((p / f'fan{fan}_input').read_text()) for fan in (1, 2)]
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            p = self.find('k10temp')
            result['temperature'] = int((p / 'temp1_input').read_text()) / 1000
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            p = self.find('amdgpu')
            result['gpu_temperature'] = int((p / 'temp1_input').read_text()) / 1000
            result['power'] = int((p / 'power1_average').read_text()) / 1000000
        except (OSError, ValueError, RuntimeError):
            pass
        return result


class Service:
    def __init__(self):
        self.hardware = Hardware()
        self.speed = 0
        self.quiet = False
        self.custom = None
        quiet.restore()
        self.owner = None
        self.deadline = 0
        self.profile = self.read_profile()
        self.loop = GLib.MainLoop()
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.bus.register_object(OBJECT, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
                                 self.call, None, None)
        self.bus.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
            'NameOwnerChanged', '/org/freedesktop/DBus', None, Gio.DBusSignalFlags.NONE,
            self.owner_changed)
        self.bus.signal_subscribe('org.freedesktop.login1', 'org.freedesktop.login1.Manager',
            'PrepareForSleep', '/org/freedesktop/login1', None, Gio.DBusSignalFlags.NONE,
            self.sleep_changed)
        self.name_id = Gio.bus_own_name_on_connection(self.bus, NAME,
            Gio.BusNameOwnerFlags.NONE, None, lambda *args: self.loop.quit())
        GLib.timeout_add_seconds(2, self.watch)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    @staticmethod
    def read_profile():
        return Path('/sys/firmware/acpi/platform_profile').read_text().strip()

    def automatic(self):
        self.stop_quiet()
        self.hardware.automatic()
        self.speed = 0
        self.owner = None
        self.custom = None

    def stop_quiet(self, restore_profile=True):
        if self.quiet or quiet.STATE.exists():
            self.hardware.automatic()
            quiet.restore(restore_profile)
            self.quiet = False
            self.custom = None

    def start_quiet(self):
        data = defaults()[0]
        if QUIET_CONFIG.exists():
            try:
                data = validate_profile(json.loads(QUIET_CONFIG.read_text()))
            except (ValueError, OSError):
                pass
        data['low_power'] = True
        self.set_profile(data, persist=False)

    def set_profile(self, data, persist=True):
        data = validate_profile(data)
        # All validation precedes hardware mutation. Curves remain in firmware
        # when the UI exits; suspend/profile changes/backend exit restore Auto.
        if not data['low_power']:
            self.stop_quiet()
        self.speed = 0
        self.owner = None
        self.custom = None
        try:
            if data['low_power'] and not self.quiet:
                quiet.apply()
                self.quiet = True
            self.hardware.apply_profile(data)
            self.profile = self.read_profile()
            if data['id'] == 'quiet' and persist:
                QUIET_CONFIG.parent.mkdir(mode=0o700, exist_ok=True)
                temp = QUIET_CONFIG.with_suffix('.tmp')
                temp.write_text(json.dumps(data))
                temp.chmod(0o600)
                temp.replace(QUIET_CONFIG)
            self.custom = data
        except Exception:
            self.automatic()
            raise

    def call(self, bus, sender, path, interface, method, parameters, invocation):
        try:
            uid = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'GetConnectionUnixUser', GLib.Variant('(s)', (sender,)),
                GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            if uid not in (0, 1000):
                raise PermissionError('Only the configured desktop user may control the fans')
            if method == 'Status':
                status = self.hardware.readings()
                status.update(speed=self.speed, mode='quiet' if self.quiet else 'curve' if self.custom else 'manual' if self.speed else 'automatic', profile=self.custom)
                invocation.return_value(GLib.Variant('(s)', (json.dumps(status),)))
                return
            if method == 'SetSpeed':
                percent = parameters.unpack()[0]
                curve(percent)
                self.stop_quiet()
                self.custom = None
                self.profile = self.read_profile()
                try:
                    self.hardware.apply(percent)
                except Exception:
                    self.speed = 0
                    self.owner = None
                    raise
                self.speed = percent
                self.owner = sender
                self.deadline = time.monotonic() + 45
            elif method == 'SetProfile':
                raw = parameters.unpack()[0]
                if len(raw) > 8192:
                    raise ValueError('Profile is too large')
                self.set_profile(json.loads(raw))
            elif method == 'QuietOn':
                self.start_quiet()
            elif method == 'QuietOff':
                self.stop_quiet()
            elif method == 'Automatic':
                self.automatic()
            elif method == 'KeepAlive':
                if sender == self.owner:
                    self.deadline = time.monotonic() + 45
            else:
                raise ValueError('Unknown method')
            invocation.return_value(None)
        except Exception as error:
            invocation.return_dbus_error(NAME + '.Error', str(error))

    def owner_changed(self, bus, sender, path, interface, name, parameters):
        owner, old, new = parameters.unpack()
        if owner == self.owner and not new:
            self.safe_auto()

    def sleep_changed(self, bus, sender, path, interface, name, parameters):
        if self.speed or self.quiet or self.custom:
            self.safe_auto()

    def safe_auto(self):
        try:
            self.automatic()
        except Exception as error:
            print(f'Automatic fan restore failed: {error}', flush=True)

    def watch(self):
        if self.quiet:
            try:
                if quiet.profile() != 'power-saver' or self.read_profile() != 'quiet':
                    self.stop_quiet(restore_profile=False)
                elif not self.hardware.manual_enabled() or any(self.hardware.readings()[key] is None for key in ('temperature', 'gpu_temperature')):
                    self.stop_quiet()
            except Exception as error:
                print(f'Quiet Mode monitoring: {error}', flush=True)
                self.safe_auto()
        if self.custom and not self.quiet:
            try:
                readings = self.hardware.readings()
                if self.read_profile() != self.profile or not self.hardware.manual_enabled() or readings['temperature'] is None or readings['gpu_temperature'] is None:
                    self.automatic()
            except Exception:
                self.safe_auto()
        if self.speed:
            try:
                if (time.monotonic() > self.deadline or
                    self.read_profile() != self.profile or
                    not self.hardware.manual_enabled()):
                    self.automatic()
            except Exception as error:
                print(f'Fan monitoring: {error}', flush=True)
                self.safe_auto()
        return GLib.SOURCE_CONTINUE

    def quit(self):
        self.loop.quit()
        return GLib.SOURCE_REMOVE

    def run(self):
        try:
            self.loop.run()
        finally:
            self.safe_auto()


if __name__ == '__main__':
    if sys.argv[1:] == ['--restore']:
        Hardware().automatic()
        quiet.restore()
    elif not sys.argv[1:]:
        Service().run()
    else:
        raise SystemExit('Usage: fan-control [--restore]')
