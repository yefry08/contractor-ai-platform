// Deviation figures span several orders of magnitude: most sit near 200%, a
// few reach 65,000%. Printed raw they crowd a table column and read as noise,
// so anything past 999% becomes a multiplier ("×658" = 658 times the
// reference), which keeps every cell at three digits or fewer without
// rounding the extremes away. The exact figure stays in the `title`.

export type Deviation = { label: string; title: string };

/** `fraction` is relative: 0.5 = 50% above the reference, -0.25 = 25% below. */
export function fmtDeviation(
  fraction: number | null | undefined,
  locale: string,
): Deviation | null {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return null;

  const pct = fraction * 100;
  const exact = `${pct >= 0 ? "+" : "−"}${Math.abs(pct).toLocaleString(locale, {
    maximumFractionDigits: 1,
  })}%`;

  if (Math.abs(pct) < 1000) {
    return { label: `${pct >= 0 ? "+" : "−"}${Math.round(Math.abs(pct))}%`, title: exact };
  }

  const times = Math.round(1 + fraction);
  return { label: `×${times.toLocaleString(locale)}`, title: exact };
}

export function fmtPct(fraction: number | null | undefined, locale: string, digits = 1): string {
  if (fraction === null || fraction === undefined) return "—";
  return `${(fraction * 100).toLocaleString(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

export function fmtCompactUsd(n: number, locale: string): string {
  if (n <= 0) return "$0";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toLocaleString(locale, { maximumFractionDigits: 1 })}M`;
  if (n >= 1_000) return `$${(n / 1_000).toLocaleString(locale, { maximumFractionDigits: 0 })}K`;
  return `$${n.toLocaleString(locale, { maximumFractionDigits: 0 })}`;
}
