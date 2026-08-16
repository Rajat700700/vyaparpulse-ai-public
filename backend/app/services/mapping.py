"""Column-alias mapping. Rules-first, deterministic. Never alters values."""
import re

ALIASES = {
    "distributor_code": ["distributor code", "dist code", "distributor id", "distributor_id", "dist_id", "party code"],
    "distributor_name": ["distributor name", "dist name", "party name", "distributor"],
    "salesperson_code": ["salesperson code", "sp code", "salesman code", "sales rep code", "sr code", "employee code"],
    "salesperson_name": ["salesperson", "salesman", "sales rep", "sales person", "sr name", "salesman name"],
    "beat_or_route": ["beat", "route", "beat name", "beat code", "route code", "market"],
    "outlet_code": ["outlet code", "customer code", "shop code", "retailer code", "outlet id"],
    "outlet_name": ["outlet name", "customer name", "shop name", "retailer name", "outlet"],
    "order_date": ["order date", "invoice date", "billing date", "date", "bill date", "posting date"],
    "invoice_no": ["invoice no", "invoice number", "invoice #", "bill no", "bill number", "invoice"],
    "sku_code": ["sku code", "product code", "item code", "material code", "sku id"],
    "sku_name": ["sku name", "product name", "item name", "material name", "product description", "sku"],
    "quantity": ["quantity", "billed qty", "billed quantity", "qty", "billed_qty", "order qty"],
    "net_sales": ["net sales", "net value", "net amount", "net_sales_value", "amount", "line total", "net"],
    "enterprise": ["enterprise", "company", "principal"],
    "region": ["region", "state", "zone", "territory"],
    "category": ["category", "product category", "cat"],
    "brand": ["brand", "brand name"],
    "pack": ["pack", "pack size", "sku pack"],
    "gross_sales": ["gross sales", "gross value", "gross amount"],
    "discount": ["discount", "discount value", "disc"],
    "return_value": ["return value", "returns", "return amount"],
}

REQUIRED = [
    "distributor_code", "salesperson_code", "beat_or_route",
    "outlet_code", "outlet_name", "order_date", "invoice_no",
    "sku_code", "sku_name", "quantity", "net_sales",
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def suggest_mapping(headers: list[str]) -> dict:
    """Return {source_header: {target, confidence, source}} for confident hits.
    Uncertain columns are left unmapped for user (or LLM) confirmation."""
    normalised = {h: _norm(h) for h in headers}
    result = {}
    used_targets = set()
    for header, n in normalised.items():
        best = None
        best_score = 0.0
        for target, aliases in ALIASES.items():
            if target in used_targets:
                continue
            for a in aliases + [target.replace("_", " ")]:
                a_n = _norm(a)
                if a_n == n:
                    score = 1.0
                elif a_n in n or n in a_n:
                    # partial-word overlap — must stay below the rules-first
                    # threshold so the AI fallback can weigh in (fixes
                    # "Territory Loop" → region 0.85 false-positive).
                    score = 0.7
                elif set(a_n.split()) & set(n.split()):
                    score = 0.6
                else:
                    score = 0.0
                if score > best_score:
                    best_score = score
                    best = target
        if best and best_score >= 0.85:
            result[header] = {"target": best, "confidence": round(best_score, 2), "source": "rules"}
            used_targets.add(best)
        elif best and best_score >= 0.6:
            result[header] = {"target": best, "confidence": round(best_score, 2), "source": "rules-uncertain"}
    return result
