"""Check resistor-network design corners; not proof of physical wiring or sensor health."""
import itertools
import unittest


class E18InterfaceTests(unittest.TestCase):
    def corners(self):
        # Regulated 5 V +/-5%, resistors +/-5%, GPIO powered at nominal 3.3 V.
        return itertools.product((4.75, 5.25), (950, 1050), (9500, 10500), (14250, 15750))

    def test_open_collector_high_is_valid_and_below_3v3(self):
        for voltage, r1, r2, r3 in self.corners():
            gpio = voltage * r3 / (r1 + r2 + r3)
            self.assertGreater(gpio, 0.75 * 3.3)
            self.assertLess(gpio, 3.3)

    def test_internal_5v_pullup_high_is_below_3v3(self):
        for voltage, _, r2, r3 in self.corners():
            gpio = voltage * r3 / (r2 + r3)
            self.assertGreater(gpio, 0.75 * 3.3)
            self.assertLess(gpio, 3.3)

    def test_low_and_resistor_power(self):
        for voltage, r1, r2, r3 in self.corners():
            # NPN output assumed <=0.4 V at the applied pull-up current; verify physically.
            self.assertLess(0.4 * r3 / (r2 + r3), 0.25 * 3.3)
            self.assertLess(voltage ** 2 / r1, 0.25)


if __name__ == '__main__':
    unittest.main()
