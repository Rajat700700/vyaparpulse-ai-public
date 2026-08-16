// Indian ₹ formatting with Lakhs/Crores grouping.
const inr = new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
});
const inrShort = new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 2,
});

export function paiseToInr(paise) {
    if (paise == null) return '—';
    return inr.format(paise / 100);
}

export function paiseToCompact(paise) {
    if (paise == null || paise === 0) return '₹0';
    const r = paise / 100;
    if (r >= 1_00_00_000) return `₹${(r / 1_00_00_000).toFixed(2)} Cr`;
    if (r >= 1_00_000) return `₹${(r / 1_00_000).toFixed(2)} L`;
    if (r >= 1_000) return `₹${(r / 1_000).toFixed(1)} K`;
    return inrShort.format(r);
}

export function formatFreshness(iso) {
    if (!iso) return 'Awaiting first data import';
    const d = new Date(iso);
    return `Data through ${d.toLocaleDateString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
    })}`;
}
