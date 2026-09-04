/**
 * `source_url` on a contract comes straight from external government OCDS
 * APIs/CSVs with no validation at ingestion (see backend/scripts/ingest_*.py) --
 * it is untrusted data. React does NOT sanitize `href` values: an
 * `href="javascript:...`" attribute executes on click, so rendering an
 * unvalidated string there is a stored-XSS vector if any upstream source ever
 * returns (by bug, injection, or compromise) something other than a normal
 * link. `target="_blank"` without `rel="noopener"` is a second, separate
 * issue -- the opened page gets a live `window.opener` handle back to us.
 *
 * This is the single choke point every "open an external contract source"
 * link should go through, rather than trusting each call site to remember.
 */
export function isSafeExternalUrl(url: string | null | undefined): url is string {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}
