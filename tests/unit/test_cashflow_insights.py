"""Collection-pattern insights: amount tiers, customer rating, standard payment models."""
import unittest

import backend.runtime as r


def node(customer, code, amount, kind, planned, received, contract, received_date=""):
    return {"customer": customer, "project_code": code, "project_name": code, "region": "东区", "project_type": kind,
            "contract_amount": amount, "planned_amount": planned, "received_amount": received,
            "contract_date": contract, "received_date": received_date, "planned_date": "", "status": "", "is_difficult": False, "is_long_term": False}


def fast(customer, i):
    code = f"{customer}-{i}"
    return [node(customer, code, 2_000_000, "预付款30%", 600_000, 600_000, "2020-01-01", "2020-01-20"),
            node(customer, code, 2_000_000, "到货款60%", 1_200_000, 1_200_000, "2020-01-01", "2020-06-01"),
            node(customer, code, 2_000_000, "质保款10%", 200_000, 200_000, "2020-01-01", "2021-01-01")]


def slow(customer, i):
    code = f"{customer}-{i}"
    return [node(customer, code, 2_000_000, "到货款90%", 1_800_000, 1_800_000, "2020-01-01", "2021-06-01"),
            node(customer, code, 2_000_000, "质保款10%", 200_000, 200_000, "2020-01-01", "2023-01-01")]


class CashflowInsightTests(unittest.TestCase):
    def test_amount_tiers_split_small_and_large_projects(self):
        records = [node("甲", "S1", 300_000, "验收款100%", 300_000, 300_000, "2021-01-01", "2021-03-02"),
                   node("甲", "L1", 8_000_000, "预付款30%", 2_400_000, 2_400_000, "2021-01-01", "2021-02-01"),
                   node("甲", "L1", 8_000_000, "验收款70%", 5_600_000, 5_600_000, "2021-01-01", "2022-12-31")]
        tiers = {t["name"]: t for t in r.cashflow_history_insights(records)["tiers"]}
        self.assertEqual(tiers["100万以下"]["median_cycle_days"], 60)
        self.assertEqual(tiers["500万以上"]["median_cycle_days"], 729)

    def test_slow_contractor_rated_below_fast_one_and_gets_terms(self):
        records = [n for i in range(4) for n in fast("快付总包", i)] + [n for i in range(4) for n in slow("慢付总包", i)] \
                  + [n for i in range(3) for n in fast("中性客户", i)]
        customers = {c["name"]: c for c in r.cashflow_history_insights(records)["customers"]}
        self.assertGreater(customers["快付总包"]["credit_score"], customers["慢付总包"]["credit_score"])
        self.assertIn(customers["慢付总包"]["credit_grade"], ("C", "D"))
        self.assertIn("预付", customers["慢付总包"]["terms"])

    def test_small_samples_are_not_rated(self):
        customers = r.cashflow_history_insights(fast("小客户", 1) + fast("小客户", 2))["customers"]
        self.assertEqual(customers[0]["credit_grade"], "样本不足")

    def test_payment_patterns_report_probability_and_node_timing(self):
        records = [n for i in range(3) for n in fast("甲", i)] + slow("乙", 0)
        data = r.cashflow_history_insights(records)
        top = data["patterns"][0]
        self.assertEqual(top["signature"], "前期款 30% → 到货款 60% → 质保款 10%")
        self.assertEqual(top["probability"], 75.0)
        self.assertEqual([n["median_days"] for n in top["nodes"]], [19, 152, 366])

    def test_placeholder_customers_are_ignored(self):
        records = fast("甲", 0) + [node("2026年度订货", "X", 100, "0", 100, 0, "2026-01-01")]
        self.assertEqual(r.cashflow_history_insights(records)["project_count"], 1)


if __name__ == "__main__":
    unittest.main()
