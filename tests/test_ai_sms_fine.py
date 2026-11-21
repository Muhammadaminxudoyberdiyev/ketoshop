"""AI: Ketoshop SMS yubormaydi va jarima qo'ymaydi (egasi, 2026-11-21)."""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql://test/test")
os.environ.setdefault("BOT_TOKEN", "1:test")

import ai_sales


class SmsFineRuleTest(unittest.TestCase):
    def test_the_rules_say_we_send_no_sms_and_charge_no_fines(self):
        rules = ai_sales._sales_rules()
        self.assertIn("Ketoshop SMS YUBORMAYDI", rules)
        self.assertIn("HECH QACHON jarima qo'ymaydi", rules)
        self.assertIn("havolani ochmang", rules)

    def test_the_phone_is_given_once_not_every_turn(self):
        self.assertIn("Raqamni bitta suhbatda BIR MARTA ber", ai_sales._sales_rules())


if __name__ == "__main__":
    unittest.main()
