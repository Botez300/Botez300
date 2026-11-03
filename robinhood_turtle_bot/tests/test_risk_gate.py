import unittest
from decimal import Decimal as D
from robinhood_turtle_bot.risk_gate import Position, PendingBuy, Snapshot, max_buy_shares

class TestGates(unittest.TestCase):
    def test_fifth_new_symbol_blocked(self):
        p = tuple(Position(s, D("1000")) for s in ("A", "B", "C", "D", "E"))
        result = max_buy_shares(Snapshot(D("10000"), D("4000"), p, ()), "F", D("50"), D("1"))
        self.assertEqual(result.permitted_shares, 0)

    def test_pending_order_occupies_slot(self):
        p = tuple(Position(s, D("1000")) for s in ("A", "B", "C", "D"))
        orders = (PendingBuy("E", D("500")),)
        result = max_buy_shares(Snapshot(D("10000"), D("4000"), p, orders), "F", D("50"), D("1"))
        self.assertEqual(result.permitted_shares, 0)

    def test_cash_floor_not_spent(self):
        s = Snapshot(D("10000"), D("550"), tuple(), tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertGreaterEqual(result.remaining_cash_after_proposed_purchase, D("500"))

    def test_insufficient_cash_blocks(self):
        s = Snapshot(D("10000"), D("499"), tuple(), tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertEqual(result.permitted_shares, 0)

    def test_symbol_allocation_cap(self):
        s = Snapshot(D("10000"), D("6000"), (Position("A", D("1900")),), tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertEqual(result.permitted_shares, 0)

    def test_stop_risk_cap(self):
        s = Snapshot(D("10000"), D("6000"), tuple(), tuple())
        result = max_buy_shares(s, "A", D("50"), D("5"))
        self.assertEqual(result.permitted_shares, 4)  # 0.5% of ($10k - $500 reserve) / $10 2N stop risk

    def test_open_order_reserved_against_cash(self):
        s = Snapshot(D("10000"), D("1500"), tuple(), (PendingBuy("B", D("950")),))
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertGreaterEqual(result.remaining_cash_after_proposed_purchase, D("500"))

    def test_same_symbol_doesnt_add_new_slot(self):
        p = tuple(Position(s, D("1000")) for s in ("A", "B", "C", "D", "E"))
        s = Snapshot(D("10000"), D("4500"), p, tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertGreater(result.permitted_shares, 0)
        self.assertEqual(result.distinct_symbols_after_proposed_purchase, 5)

    def test_flat_500_reserve_independent_of_nav(self):
        # $100k account: a 5% rule would block, the flat $500 reserve allows 2 shares.
        s = Snapshot(D("100000"), D("610"), tuple(), tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"))
        self.assertEqual(result.required_cash_floor, D("500"))
        self.assertEqual(result.permitted_shares, 2)
        self.assertGreaterEqual(result.remaining_cash_after_proposed_purchase, D("500"))

    def test_custom_reserve(self):
        s = Snapshot(D("10000"), D("1000"), tuple(), tuple())
        result = max_buy_shares(s, "A", D("50"), D("1"), min_cash_usd=D("1000"))
        self.assertEqual(result.permitted_shares, 0)

    def test_reserve_excluded_from_sizing_nav(self):
        s = Snapshot(D("10000"), D("6000"), tuple(), tuple())
        on = max_buy_shares(s, "A", D("10"), D("0.01"))
        off = max_buy_shares(s, "A", D("10"), D("0.01"), exclude_reserve_from_sizing_nav=False)
        self.assertEqual(on.permitted_shares, 180)   # 19% of 9,500 / $10.025
        self.assertEqual(off.permitted_shares, 189)  # 19% of 10,000 / $10.025

    def test_split_across_open_slots_no_caps(self):
        p = (Position("A", D("1000")),)
        s = Snapshot(D("10000"), D("4500"), p, tuple())
        r = max_buy_shares(s, "B", D("100"), D("1"), max_symbol_fraction=None,
                           max_symbol_stop_risk_fraction=None, split_cash_across_open_slots=True)
        self.assertEqual(r.permitted_shares, 9)  # ($4,500 - $500) / 4 free slots / $100.25

    def test_last_slot_spends_down_to_reserve(self):
        p = tuple(Position(x, D("1000")) for x in "ABCD")
        s = Snapshot(D("10000"), D("2000"), p, tuple())
        r = max_buy_shares(s, "E", D("100"), D("1"), max_symbol_fraction=None,
                           max_symbol_stop_risk_fraction=None, split_cash_across_open_slots=True)
        self.assertEqual(r.permitted_shares, 14)
        self.assertGreaterEqual(r.remaining_cash_after_proposed_purchase, D("500"))

if __name__ == '__main__':
    unittest.main()
