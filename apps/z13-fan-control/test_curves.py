import copy
import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch
from curves import defaults, validate_profile
sys.path.append(str(Path(__file__).parent / 'backend'))


class CurvesTest(unittest.TestCase):
    def test_all_presets(self):
        for profile in defaults():
            self.assertEqual(validate_profile(profile), profile)

    def test_rejects_invalid_curves(self):
        for mutate in [lambda p: p['cpu'].pop(),
                       lambda p: p['cpu'].__setitem__(2, [45, 0]),
                       lambda p: p['gpu'].__setitem__(-1, [100, 100]),
                       lambda p: p['gpu'].__setitem__(-1, [95, 50]),
                       lambda p: p['cpu'].__setitem__(6, [90, 10]),
                       lambda p: p.__setitem__('id', '../../etc/passwd'),
                       lambda p: p['cpu'].__setitem__(0, [True, 0]),
                       lambda p: p.__setitem__('low_power', 'yes')]:
            profile = defaults()[0]; mutate(profile)
            with self.assertRaises(ValueError):
                validate_profile(profile)

    def test_validation_copies_data(self):
        p = defaults()[0]; valid = validate_profile(p)
        valid['cpu'][0][1] = 20
        self.assertEqual(p['cpu'][0][1], 0)

    def test_hardware_separate_fans_and_recovery(self):
        spec = importlib.util.spec_from_file_location('backend', Path(__file__).parent / 'backend/service.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fan = root / 'hwmon0'; fan.mkdir()
            (fan / 'name').write_text('asus_custom_fan_curve')
            for f in (1, 2): (fan / f'pwm{f}_enable').write_text('2')
            hardware = module.Hardware(root)
            profile = defaults()[0]; profile['gpu'] = defaults()[2]['gpu']
            hardware.apply_profile(profile)
            self.assertEqual((fan / 'pwm1_auto_point1_pwm').read_text().strip(), '0')
            self.assertEqual((fan / 'pwm2_auto_point1_pwm').read_text().strip(), '51')
            self.assertTrue(hardware.manual_enabled())
            (fan / 'pwm2_auto_point3_pwm').unlink()
            (fan / 'pwm2_auto_point3_pwm').mkdir()
            with self.assertRaises(OSError): hardware.apply_profile(profile)
            self.assertEqual((fan / 'pwm1_enable').read_text().strip(), '2')
            self.assertEqual((fan / 'pwm2_enable').read_text().strip(), '2')

    def test_invalid_profile_cannot_touch_hardware(self):
        spec = importlib.util.spec_from_file_location('backend', Path(__file__).parent / 'backend/service.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        service = module.Service.__new__(module.Service)
        service.hardware = Mock()
        invalid = defaults()[0]; invalid['cpu'][-1] = [95, 0]
        with self.assertRaises(ValueError): service.set_profile(invalid)
        self.assertEqual(service.hardware.mock_calls, [])


if __name__ == '__main__': unittest.main()
