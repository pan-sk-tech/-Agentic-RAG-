from collections import defaultdict
from typing import Dict, Iterable, Tuple

from fin_compliance.domain.schemas import ReimbursementItem


class FinanceCalculator:
    def total_amount(self, items: Iterable[ReimbursementItem]) -> float:
        return round(sum(item.amount for item in items), 2)

    def amount_by_type(self, items: Iterable[ReimbursementItem]) -> Dict[str, float]:
        totals = defaultdict(float)
        for item in items:
            totals[item.item_type] += item.amount
        return {key: round(value, 2) for key, value in totals.items()}

    def duplicate_keys(self, items: Iterable[ReimbursementItem]) -> Dict[Tuple, list[str]]:
        buckets = defaultdict(list)
        for item in items:
            key = (
                item.item_type,
                item.date,
                round(item.amount, 2),
                item.invoice_type,
                item.seller_name,
            )
            buckets[key].append(item.item_id)
        return {key: ids for key, ids in buckets.items() if len(ids) > 1}

