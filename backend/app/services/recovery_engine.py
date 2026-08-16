"""Deterministic Recovery Engine v1.0.0.

Formulas:
  LAPSED     — 0 positive invoices in last 30d AND >=2 invoices in prior 90d.
  DECLINING  — net(last 30d) <= (1 - decline_pct) * net(prior 30d); require baseline > 0.
               Exact 25.00% decline MUST classify positive (<=).
  MISSED     — days_since_last_order > 1.5 * median_interval_days (last 180d, >=4 orders).
  WHITESPACE — SKU present in >= 40% of peer outlets (same distributor first, then region) in
               last 90d AND 0 orders for target in last 180d.

Priority score 0-100 = value(0-40) + confidence(0-30) + urgency(0-20) + strategic(0-10).

Precedence for overlap dedupe on top-line ₹:
  LAPSED > DECLINING > MISSED > WHITESPACE per outlet.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

CALC_VERSION = "v1.0.0"
DEFAULT_THRESHOLDS = {
    "lapsed_no_order_days": 30,
    "lapsed_prior_orders_min": 2,
    "lapsed_prior_window_days": 90,
    "decline_pct": 0.25,
    "decline_window_days": 30,
    "missed_multiplier": 1.5,
    "whitespace_peer_pct": 0.4,
}

PRECEDENCE = {"LAPSED": 4, "DECLINING": 3, "MISSED": 2, "WHITESPACE": 1}


def _pct(v_now: int, v_prev: int) -> float:
    if v_prev <= 0:
        return 0.0
    return (v_prev - v_now) / v_prev


def _score(value_pct: float, confidence: float, urgency_days: float, strategic: float) -> dict:
    value_score = max(0, min(40, int(round(value_pct * 40))))
    confidence_score = max(0, min(30, int(round(confidence * 30))))
    urgency_score = max(0, min(20, int(round(urgency_days))))
    strategic_score = max(0, min(10, int(round(strategic))))
    return {
        "value": value_score, "confidence": confidence_score,
        "urgency": urgency_score, "strategic": strategic_score,
        "total": value_score + confidence_score + urgency_score + strategic_score,
    }


def compute(transactions: list[dict], analysis_as_of: datetime,
            thresholds: dict[str, Any] | None = None,
            enterprise_id: str = "") -> list[dict]:
    """`transactions` are already tenant-scoped. Returns list of opportunity dicts."""
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    as_of = analysis_as_of

    # Bucket by outlet key (distributor_code, outlet_code)
    by_outlet: dict[tuple, list[dict]] = defaultdict(list)
    for t in transactions:
        key = (t["distributor_code"], t["outlet_code"])
        by_outlet[key].append(t)

    # Peer index: distributor -> outlet -> sku_codes in last 90d
    peer_by_dist: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for (dc, oc), rows in by_outlet.items():
        for t in rows:
            if t["order_date"] >= as_of - timedelta(days=90) and (t.get("net_sales_paise") or 0) > 0:
                peer_by_dist[dc][oc].add(t["sku_code"])

    # Enterprise-wide max opportunity value for percentile scoring
    all_estimates = []
    opps: list[dict] = []

    def add(opp):
        all_estimates.append(opp["est_recovery_paise"])
        opps.append(opp)

    for (dc, oc), rows in by_outlet.items():
        rows_sorted = sorted(rows, key=lambda r: r["order_date"])
        positive = [r for r in rows_sorted if (r.get("net_sales_paise") or 0) > 0]
        if not positive:
            continue

        outlet_meta = {
            "distributor_code": dc, "outlet_code": oc,
            "outlet_name": rows_sorted[-1].get("outlet_name", ""),
            "salesperson_code": rows_sorted[-1].get("salesperson_code", ""),
            "salesperson_name": rows_sorted[-1].get("salesperson_name", ""),
            "beat_or_route": rows_sorted[-1].get("beat_or_route", ""),
            "region": rows_sorted[-1].get("region", ""),
        }

        # Window helpers
        def _sum_between(a, b):
            return sum((r.get("net_sales_paise") or 0) for r in positive if a <= r["order_date"] < b)

        def _invoices_between(a, b):
            return len({r["invoice_no"] for r in positive if a <= r["order_date"] < b})

        w1_start = as_of - timedelta(days=thr["lapsed_no_order_days"])
        w2_start = w1_start - timedelta(days=thr["lapsed_prior_window_days"])
        inv_last = _invoices_between(w1_start, as_of + timedelta(days=1))
        inv_prev = _invoices_between(w2_start, w1_start)

        # ---- LAPSED
        if inv_last == 0 and inv_prev >= thr["lapsed_prior_orders_min"]:
            # baseline: median of POSITIVE monthly nets excluding the last 30d, over
            # up to 6 preceding months. Zero-activity / returns-only months are
            # excluded so a sparse-history outlet is not scored at ₹0.
            monthlies = []
            for m in range(1, 7):
                a = as_of - timedelta(days=30 * (m + 1))
                b = as_of - timedelta(days=30 * m)
                monthlies.append(_sum_between(a, b))
            positive_monthlies = [v for v in monthlies if v > 0]
            active_month_count = len(positive_monthlies)
            selected_baseline = int(median(positive_monthlies)) if positive_monthlies else 0
            est = selected_baseline
            days_gap = (as_of - positive[-1]["order_date"]).days
            conf = min(1.0, inv_prev / 6.0)
            add({
                "type": "LAPSED", "outlet_meta": outlet_meta,
                "est_recovery_paise": est, "confidence": round(conf, 2),
                "reason": f"No positive invoice in last {thr['lapsed_no_order_days']} days, {inv_prev} invoices in prior {thr['lapsed_prior_window_days']} days.",
                "inputs": {
                    "invoices_last_30d": inv_last,
                    "invoices_prior_90d": inv_prev,
                    "monthly_totals_paise": monthlies,
                    "positive_monthly_totals": positive_monthlies,
                    "active_month_count": active_month_count,
                    "selected_baseline_paise": selected_baseline,
                    "days_since_last_order": days_gap,
                },
                "thresholds": {k: thr[k] for k in ("lapsed_no_order_days", "lapsed_prior_orders_min", "lapsed_prior_window_days")},
                "urgency_days": min(20, days_gap - thr["lapsed_no_order_days"]),
                "value_pct_raw": est, "confidence_raw": conf,
            })

        # ---- DECLINING
        w_now_start = as_of - timedelta(days=thr["decline_window_days"])
        w_prev_start = w_now_start - timedelta(days=thr["decline_window_days"])
        v_now = _sum_between(w_now_start, as_of + timedelta(days=1))
        v_prev = _sum_between(w_prev_start, w_now_start)
        if v_prev > 0 and v_now > 0:
            drop = _pct(v_now, v_prev)  # positive number when declining
            if drop >= thr["decline_pct"]:
                est = max(0, v_prev - v_now)
                conf = min(0.9, max(0.4, 0.6 + (drop - thr["decline_pct"])))
                add({
                    "type": "DECLINING", "outlet_meta": outlet_meta,
                    "est_recovery_paise": int(est), "confidence": round(conf, 2),
                    "reason": f"Latest {thr['decline_window_days']}d net sales down {drop*100:.1f}% vs prior {thr['decline_window_days']}d.",
                    "inputs": {"net_now_paise": v_now, "net_prev_paise": v_prev, "drop_pct": round(drop, 4)},
                    "thresholds": {"decline_pct": thr["decline_pct"], "decline_window_days": thr["decline_window_days"]},
                    "urgency_days": min(20, int(drop * 40)),
                    "value_pct_raw": est, "confidence_raw": conf,
                })

        # ---- MISSED CYCLE
        invoices_dates = sorted({r["order_date"].date() for r in positive
                                 if r["order_date"] >= as_of - timedelta(days=180)})
        if len(invoices_dates) >= 4:
            intervals = [(invoices_dates[i+1] - invoices_dates[i]).days
                         for i in range(len(invoices_dates) - 1)]
            med = median(intervals)
            days_gap = (as_of.date() - invoices_dates[-1]).days
            if med > 0 and days_gap > thr["missed_multiplier"] * med:
                aov_90 = 0
                w_start = as_of - timedelta(days=90)
                inv_90 = _invoices_between(w_start, as_of + timedelta(days=1))
                if inv_90 > 0:
                    aov_90 = int(_sum_between(w_start, as_of + timedelta(days=1)) / inv_90)
                overdue_cycles = min(2, days_gap // max(1, int(med))) if med > 0 else 1
                est = aov_90 * overdue_cycles
                conf = min(1.0, len(invoices_dates) / 12.0)
                add({
                    "type": "MISSED", "outlet_meta": outlet_meta,
                    "est_recovery_paise": int(est), "confidence": round(conf, 2),
                    "reason": f"Days since last order ({days_gap}) exceed {thr['missed_multiplier']}× median interval ({med} days).",
                    "inputs": {"median_interval_days": med, "days_since_last_order": days_gap,
                               "aov_last_90d_paise": aov_90, "invoices_last_180d": len(invoices_dates)},
                    "thresholds": {"missed_multiplier": thr["missed_multiplier"]},
                    "urgency_days": min(20, int(days_gap - thr["missed_multiplier"] * med)),
                    "value_pct_raw": est, "confidence_raw": conf,
                })

        # ---- SKU WHITESPACE
        peer_map = peer_by_dist.get(dc, {})
        peers = [o for o in peer_map if o != oc]
        if len(peers) >= 3:
            sku_adoption: dict[str, int] = defaultdict(int)
            for p in peers:
                for s in peer_map[p]:
                    sku_adoption[s] += 1
            outlet_skus_180 = {r["sku_code"] for r in positive
                               if r["order_date"] >= as_of - timedelta(days=180)}
            hits = []
            for sku, count in sku_adoption.items():
                adoption_pct = count / len(peers)
                if adoption_pct >= thr["whitespace_peer_pct"] and sku not in outlet_skus_180:
                    hits.append((sku, adoption_pct))
            hits.sort(key=lambda x: -x[1])
            if hits:
                aov_90 = 0
                w_start = as_of - timedelta(days=90)
                inv_90 = _invoices_between(w_start, as_of + timedelta(days=1))
                if inv_90 > 0:
                    aov_90 = int(_sum_between(w_start, as_of + timedelta(days=1)) / inv_90)
                # Peer median monthly net for the top SKU (approx)
                top_sku = hits[0][0]
                peer_sku_net = []
                for t in transactions:
                    if t["sku_code"] == top_sku and t["distributor_code"] == dc \
                            and t["outlet_code"] != oc \
                            and t["order_date"] >= as_of - timedelta(days=90) \
                            and (t.get("net_sales_paise") or 0) > 0:
                        peer_sku_net.append(t["net_sales_paise"])
                base = int(median(peer_sku_net)) if peer_sku_net else 0
                est = max(0, min(base * 2, aov_90 or base))
                conf = round(min(0.85, hits[0][1] * 0.9), 2)
                add({
                    "type": "WHITESPACE", "outlet_meta": outlet_meta,
                    "sku_code": top_sku,
                    "est_recovery_paise": int(est), "confidence": conf,
                    "reason": f"{int(hits[0][1]*100)}% of peer outlets in distributor {dc} bought SKU {top_sku}; this outlet has not.",
                    "inputs": {"peer_adoption_pct": round(hits[0][1], 3), "peer_count": len(peers),
                               "peer_median_net_paise": base, "aov_last_90d_paise": aov_90},
                    "thresholds": {"whitespace_peer_pct": thr["whitespace_peer_pct"]},
                    "urgency_days": 5,
                    "value_pct_raw": est, "confidence_raw": conf,
                })

    # Compute value_pct percentile relative to max, then finalise scoring + provenance.
    max_est = max((o["est_recovery_paise"] for o in opps), default=1) or 1
    finalised = []
    for o in opps:
        value_pct = min(1.0, o["est_recovery_paise"] / max_est)
        strategic = 5 if o["type"] in ("LAPSED", "DECLINING") else 3
        s = _score(value_pct, o["confidence_raw"], o["urgency_days"], strategic)
        finalised.append({
            "type": o["type"],
            "distributor_code": o["outlet_meta"]["distributor_code"],
            "outlet_code": o["outlet_meta"]["outlet_code"],
            "outlet_name": o["outlet_meta"]["outlet_name"],
            "salesperson_code": o["outlet_meta"]["salesperson_code"],
            "salesperson_name": o["outlet_meta"]["salesperson_name"],
            "beat_or_route": o["outlet_meta"]["beat_or_route"],
            "region": o["outlet_meta"]["region"],
            "sku_code": o.get("sku_code"),
            "est_recovery_paise": o["est_recovery_paise"],
            "confidence": o["confidence"],
            "priority_score": s["total"],
            "score_components": s,
            "reason": o["reason"],
            "inputs_snapshot": o["inputs"],
            "thresholds_snapshot": o["thresholds"],
            "calc_version": CALC_VERSION,
            "analysis_as_of": as_of,
            "recommended_action": _recommend(o["type"]),
        })
    return finalised


def _recommend(t: str) -> str:
    return {
        "LAPSED": "Visit outlet within 3 days; confirm reason for stoppage and re-activate with current top SKUs.",
        "DECLINING": "Call salesperson; audit last two orders and prevent further slide with a targeted assortment refresh.",
        "MISSED": "Trigger next-order reminder; schedule visit before overdue cycle doubles.",
        "WHITESPACE": "Introduce the recommended SKU adopted by peers on the next visit.",
    }[t]


def dedupe_topline(opportunities: list[dict]) -> int:
    """Sum est ₹ across opportunities WITHOUT double-counting overlaps.
    Rule: per (distributor, outlet), only the highest-precedence type contributes."""
    by_outlet: dict[tuple, list[dict]] = defaultdict(list)
    for o in opportunities:
        by_outlet[(o["distributor_code"], o["outlet_code"])].append(o)
    total = 0
    for key, opps in by_outlet.items():
        winner = max(opps, key=lambda o: PRECEDENCE[o["type"]])
        total += winner["est_recovery_paise"]
    return total
