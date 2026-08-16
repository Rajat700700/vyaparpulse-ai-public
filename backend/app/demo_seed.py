"""Populated contest sandbox seed.

Generates a coherent synthetic Indian FMCG dataset for the demo enterprise:
- 11 distributors across 4 regions
- 22 salespeople (2 per distributor)
- ~220 outlets
- 32 SKUs across 6 categories
- Jan–Jun 2026 order-line history
- Deliberate LAPSED / DECLINING / MISSED / WHITESPACE patterns

All data is deterministic (seeded), tagged is_demo_ephemeral=False for tenant
docs (persistent seed) but transactions are refreshable via /api/demo/reseed.
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from .db import get_db
from .services.recovery_engine import compute, CALC_VERSION

REGIONS = [
    ("Maharashtra", "West"), ("Karnataka", "South"),
    ("Gujarat", "West"), ("Delhi", "North"),
]

DISTRIBUTORS = [
    ("DIST-01", "Shree Ganesh Distributors", "Mumbai", "Maharashtra"),
    ("DIST-02", "Mahalaxmi Trading Co", "Pune", "Maharashtra"),
    ("DIST-03", "Krishna Sales Corp", "Bengaluru", "Karnataka"),
    ("DIST-04", "Bharat Enterprises", "Mysuru", "Karnataka"),
    ("DIST-05", "Patel Marketing", "Ahmedabad", "Gujarat"),
    ("DIST-06", "Vaibhav Traders", "Surat", "Gujarat"),
    ("DIST-07", "Sundar Sales Agency", "Rajkot", "Gujarat"),
    ("DIST-08", "Kapoor & Sons", "New Delhi", "Delhi"),
    ("DIST-09", "Raj Distribution Hub", "Gurugram", "Delhi"),
    ("DIST-10", "Delhi Metro Trading", "Noida", "Delhi"),
    ("DIST-11", "Om Sai Suppliers", "Faridabad", "Delhi"),
]

SP_NAMES = [
    "Rahul Sharma", "Priya Patel", "Amit Verma", "Sneha Iyer", "Vikram Reddy",
    "Anjali Nair", "Rohit Kumar", "Meera Joshi", "Arjun Menon", "Kavita Rao",
    "Suresh Gupta", "Divya Bhatt", "Ravi Deshmukh", "Sunita Mehta",
    "Karthik Krishnan", "Neha Agarwal", "Manish Yadav", "Pooja Singh",
    "Ankit Choudhary", "Riya Kapoor", "Deepak Malhotra", "Aarti Saxena",
]

OUTLET_PREFIXES = [
    "Shree", "Balaji", "Krishna", "Ganesh", "Jai", "Om", "Sai", "Radhe",
    "Amit", "Sunder", "Ashok", "Ramesh", "Suresh", "Mukesh", "Pankaj",
]
OUTLET_SUFFIXES = [
    "Kirana", "General Store", "Traders", "Enterprises", "Provisions",
    "Wholesalers", "Departmental", "Super Market", "Stores", "Agencies",
]

BEATS = [
    "MB-Bandra", "MB-Andheri", "MB-Dadar", "PN-Kothrud", "PN-Aundh",
    "BN-Whitefield", "BN-Koramangala", "MY-Sayajiganj", "AH-Navrangpura",
    "AH-Vastrapur", "ST-Piplod", "RJ-Kalawad", "DL-Karol Bagh", "DL-Rohini",
    "GG-Sector-14", "GG-Cyber Hub", "ND-Sector-62", "ND-Sector-18",
    "FD-Sector-15", "FD-NIT-3",
]

CATEGORIES_SKUS = {
    "Rice & Grains": [("RG-001", "Basmati Rice 5kg", "Aashirvaad", "5kg", 55000),
                      ("RG-002", "Sona Masuri Rice 10kg", "India Gate", "10kg", 82000),
                      ("RG-003", "Wheat Flour 5kg", "Aashirvaad", "5kg", 24000),
                      ("RG-004", "Idli Rava 500g", "MTR", "500g", 8500),
                      ("RG-005", "Poha 500g", "Manna", "500g", 6500)],
    "Oils & Ghee":    [("OG-001", "Sunflower Oil 1L", "Fortune", "1L", 14500),
                       ("OG-002", "Groundnut Oil 1L", "Sundrop", "1L", 21500),
                       ("OG-003", "Ghee 500ml", "Amul", "500ml", 38500),
                       ("OG-004", "Mustard Oil 1L", "Dhara", "1L", 17500),
                       ("OG-005", "Coconut Oil 500ml", "Parachute", "500ml", 18500)],
    "Snacks":         [("SN-001", "Aloo Bhujia 200g", "Haldiram", "200g", 5500),
                       ("SN-002", "Mixture 400g", "Bikaji", "400g", 9500),
                       ("SN-003", "Namkeen Peanuts 200g", "Haldiram", "200g", 6500),
                       ("SN-004", "Khakhra 200g", "Induben", "200g", 7500),
                       ("SN-005", "Kurkure 90g", "PepsiCo", "90g", 2000)],
    "Beverages":      [("BV-001", "Tea 500g", "Tata Tea Gold", "500g", 24500),
                       ("BV-002", "Coffee 200g", "Bru", "200g", 32500),
                       ("BV-003", "Cold Coffee 180ml", "Amul", "180ml", 3500),
                       ("BV-004", "Fruit Juice 1L", "Real", "1L", 12500),
                       ("BV-005", "Health Drink 500g", "Bournvita", "500g", 26500)],
    "Household":      [("HH-001", "Detergent 1kg", "Surf Excel", "1kg", 21500),
                       ("HH-002", "Dish Wash Bar", "Vim", "300g", 4500),
                       ("HH-003", "Floor Cleaner 1L", "Lizol", "1L", 18500),
                       ("HH-004", "Toilet Cleaner 500ml", "Harpic", "500ml", 12500),
                       ("HH-005", "Room Freshener", "Odonil", "50g", 8500)],
    "Personal Care":  [("PC-001", "Toothpaste 200g", "Colgate", "200g", 15500),
                       ("PC-002", "Hair Oil 200ml", "Parachute", "200ml", 12500),
                       ("PC-003", "Bath Soap 100g", "Lux", "100g", 3500),
                       ("PC-004", "Face Cream 50g", "Fair & Lovely", "50g", 14500),
                       ("PC-005", "Shampoo 340ml", "Head & Shoulders", "340ml", 32500)],
}


def _skus_flat():
    out = []
    for cat, items in CATEGORIES_SKUS.items():
        for code, name, brand, pack, mrp in items:
            out.append({"sku_code": code, "sku_name": name, "brand": brand,
                        "pack": pack, "category": cat, "mrp_paise": mrp})
    return out


async def seed_contest_sandbox() -> dict:
    """Idempotently seed the demo enterprise with a rich synthetic dataset."""
    db = get_db()
    demo = await db.enterprises.find_one({"is_demo": True})
    if not demo:
        return {"skipped": "demo tenant not seeded"}
    ent_oid = demo["_id"]

    # Skip if already populated recently
    existing_count = await db.transactions.count_documents({"enterprise_id": ent_oid})
    if existing_count > 5000:
        return {"skipped": "already populated", "existing_transactions": existing_count}

    # Reset demo transactions/opps/actions/recoveries (persistent demo seed)
    await db.transactions.delete_many({"enterprise_id": ent_oid})
    await db.opportunities.delete_many({"enterprise_id": ent_oid})
    await db.actions.delete_many({"enterprise_id": ent_oid})
    await db.recoveries.delete_many({"enterprise_id": ent_oid})
    await db.import_batches.delete_many({"enterprise_id": ent_oid})

    rnd = random.Random(42)
    skus = _skus_flat()

    # Distribute salespeople 2:2:2... across 11 distributors = 22 total
    sp_records = []
    for i, (dcode, dname, city, state) in enumerate(DISTRIBUTORS):
        for j in range(2):
            sp_idx = i * 2 + j
            sp_records.append({
                "distributor_code": dcode,
                "salesperson_code": f"SP-{sp_idx+1:02d}",
                "salesperson_name": SP_NAMES[sp_idx],
                "beats": [BEATS[(i * 2 + j + k) % len(BEATS)] for k in range(2)],
            })

    # Distribute ~220 outlets across distributors
    outlets = []
    for i, (dcode, dname, city, state) in enumerate(DISTRIBUTORS):
        region = next(r for _, r in REGIONS if any(dr[3] == state for dr in DISTRIBUTORS if dr[0] == dcode)) \
                 if any(dr[3] == state for dr in DISTRIBUTORS) else "West"
        # Match region text more robustly
        region = "West" if state in ("Maharashtra", "Gujarat") else \
                 "South" if state == "Karnataka" else "North"
        n_outlets = 20  # 11 * 20 = 220
        dist_sps = [sp for sp in sp_records if sp["distributor_code"] == dcode]
        for k in range(n_outlets):
            sp = dist_sps[k % len(dist_sps)]
            outlets.append({
                "distributor_code": dcode,
                "outlet_code": f"{dcode}-O{k+1:03d}",
                "outlet_name": f"{rnd.choice(OUTLET_PREFIXES)} {rnd.choice(OUTLET_SUFFIXES)}",
                "salesperson_code": sp["salesperson_code"],
                "salesperson_name": sp["salesperson_name"],
                "beat_or_route": rnd.choice(sp["beats"]),
                "region": region,
                "state": state,
                "city": city,
            })

    # Generate transactions Jan–Jun 2026
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 30, tzinfo=timezone.utc)
    txns = []
    invoice_counter = 1000

    # Precompute per-outlet behaviour patterns:
    #  25% LAPSED (orders stop mid-May), 15% DECLINING (nets halve in June),
    #  10% MISSED CYCLE (irregular gaps), 30% WHITESPACE-eligible (buy only a subset of category peers)
    for idx, o in enumerate(outlets):
        pattern = "NORMAL"
        r = idx % 20
        if r < 5: pattern = "LAPSED"
        elif r < 8: pattern = "DECLINING"
        elif r < 10: pattern = "MISSED"
        elif r < 16: pattern = "WHITESPACE"

        # Category preference for the outlet (subset for whitespace)
        cats = list(CATEGORIES_SKUS.keys())
        rnd.shuffle(cats)
        if pattern == "WHITESPACE":
            cats = cats[:3]  # limited assortment
        outlet_skus = [s for s in skus if s["category"] in cats]

        # Base cadence
        cadence_days = rnd.choice([12, 15, 18, 22])
        day = start + timedelta(days=rnd.randint(0, cadence_days))
        # Cutoff for LAPSED
        cutoff = datetime(2026, 5, 15, tzinfo=timezone.utc) if pattern == "LAPSED" else end

        # DECLINING scales June by 0.4
        while day <= cutoff:
            n_lines = rnd.randint(2, 5)
            invoice_no = f"INV-{o['distributor_code']}-{invoice_counter}"
            invoice_counter += 1
            picks = rnd.sample(outlet_skus, min(n_lines, len(outlet_skus)))
            for sku in picks:
                qty = rnd.randint(1, 6)
                base_paise = sku["mrp_paise"] * qty
                if pattern == "DECLINING" and day >= datetime(2026, 6, 1, tzinfo=timezone.utc):
                    base_paise = int(base_paise * 0.4)
                txns.append({
                    "enterprise_id": ent_oid,
                    "distributor_code": o["distributor_code"],
                    "salesperson_code": o["salesperson_code"],
                    "salesperson_name": o["salesperson_name"],
                    "beat_or_route": o["beat_or_route"],
                    "outlet_code": o["outlet_code"],
                    "outlet_name": o["outlet_name"],
                    "order_date": day,
                    "invoice_no": invoice_no,
                    "sku_code": sku["sku_code"],
                    "sku_name": sku["sku_name"],
                    "quantity": qty,
                    "net_sales_paise": int(base_paise * rnd.uniform(0.9, 1.1)),
                    "region": o["region"],
                    "category": sku["category"],
                    "brand": sku["brand"],
                    "row_hash": f"seed-{o['distributor_code']}-{invoice_no}-{sku['sku_code']}",
                    "import_batch_id": ObjectId(),
                })
            gap = cadence_days
            if pattern == "MISSED" and day > datetime(2026, 5, 1, tzinfo=timezone.utc):
                gap = cadence_days * 3
            day = day + timedelta(days=gap)

    # Batch insert transactions
    if txns:
        # 5k chunks
        for i in range(0, len(txns), 5000):
            await db.transactions.insert_many(txns[i:i+5000], ordered=False)

    # Import batch metadata
    batch = {
        "enterprise_id": ent_oid,
        "filename": "vyaparpulse_synthetic_jan_jun_2026.csv",
        "file_hash": "synthetic-seed-v1",
        "status": "completed",
        "rows_total": len(txns), "rows_ok": len(txns),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "analysis_as_of": end,
    }
    await db.import_batches.insert_one(batch)

    # Compute opportunities
    all_tx = await db.transactions.find({"enterprise_id": ent_oid}).to_list(None)
    for t in all_tx:
        if t["order_date"].tzinfo is None:
            t["order_date"] = t["order_date"].replace(tzinfo=timezone.utc)
    opps = compute(all_tx, end)
    opp_docs = []
    if opps:
        for o in opps:
            opp_docs.append({**o, "enterprise_id": ent_oid,
                             "created_at": datetime.now(timezone.utc), "status": "OPEN"})
        # insert_many populates _id in-place on each dict
        await db.opportunities.insert_many(opp_docs)

    # Seed a small set of assigned/completed actions with matching invoices for
    # the Impact Ledger story. Use opp_docs (which now carry _id) so we can
    # thread opportunity_id all the way through action → recovery for the audit
    # trail (Phase 3 QA correction #6).
    top_opps = sorted(opp_docs, key=lambda o: -o["priority_score"])[:12]
    from datetime import timedelta as _td
    for i, o in enumerate(top_opps):
        # Find a real invoice for this outlet inside the attribution window
        assigned = end - _td(days=20)
        invs = [t for t in all_tx
                if t["distributor_code"] == o["distributor_code"]
                and t["outlet_code"] == o["outlet_code"]
                and t["order_date"] >= assigned]
        invoice_no = invs[0]["invoice_no"] if invs else None
        status = ("COMPLETED" if i < 5 and invoice_no
                  else "IN_PROGRESS" if i < 8 else "ASSIGNED")
        act_doc = {
            "enterprise_id": ent_oid,
            "opportunity_id": o["_id"],
            "distributor_code": o["distributor_code"],
            "outlet_code": o["outlet_code"],
            "outlet_name": o["outlet_name"],
            "opportunity_type": o["type"],
            "salesperson_code": o["salesperson_code"],
            "salesperson_name": o.get("salesperson_name"),
            "assigned_at": assigned,
            "assigned_by": "seed",
            "due_date": end - _td(days=(15 - i)),
            "status": status,
            "recommended_action": o["recommended_action"],
            "est_recovery_paise_snapshot": o["est_recovery_paise"],
            "priority_score_snapshot": o["priority_score"],
        }
        if status == "COMPLETED":
            act_doc["completed_at"] = end - _td(days=(10 - i))
            act_doc["invoice_ref"] = invoice_no
            act_doc["claimed_paise"] = o["est_recovery_paise"]
            act_doc["verified_paise"] = min(o["est_recovery_paise"], invs[0]["net_sales_paise"])
            act_doc["verification_status"] = "VERIFIED"
        ins = await db.actions.insert_one(act_doc)
        if status == "COMPLETED":
            try:
                await db.recoveries.insert_one({
                    "enterprise_id": ent_oid,
                    "action_id": ins.inserted_id,
                    "opportunity_id": o["_id"],
                    "opportunity_type": o["type"],
                    "distributor_code": o["distributor_code"],
                    "outlet_code": o["outlet_code"],
                    "outlet_name": o["outlet_name"],
                    "salesperson_code": o["salesperson_code"],
                    "salesperson_name": o.get("salesperson_name"),
                    "invoice_no": invoice_no,
                    "invoice_order_date": invs[0]["order_date"],
                    "invoice_net_paise": invs[0]["net_sales_paise"],
                    "claimed_paise": o["est_recovery_paise"],
                    "verified_paise": act_doc["verified_paise"],
                    "verification_status": "VERIFIED",
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception:
                pass

    return {
        "distributors": len(DISTRIBUTORS),
        "outlets": len(outlets),
        "salespeople": len(sp_records),
        "skus": len(skus),
        "transactions": len(txns),
        "opportunities": len(opps),
        "actions_seeded": len(top_opps),
        "analysis_as_of": end.isoformat(),
    }
