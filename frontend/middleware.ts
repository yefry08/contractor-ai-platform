import { NextResponse, type NextRequest } from "next/server";

/**
 * Turns away AI crawlers and bulk-scraping clients before they reach a page.
 *
 * robots.txt (app/robots.ts) asks the same bots to stay out; this enforces
 * it for the ones that identify themselves. Search engines (Googlebot,
 * Bingbot...) are not on the list, and people browsing are unaffected. Bots
 * that lie about their user agent are Cloudflare's job (Bot Fight Mode and
 * "Block AI bots", see docs/security/cloudflare.md) -- a user-agent check
 * can't see them.
 *
 * The data stays open on purpose: the API, the CSV export and the Hugging
 * Face model are the sanctioned ways to reuse it.
 */
const BLOCKED = new RegExp(
  [
    // AI training and answer-engine crawlers
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai",
    "CCBot", "PerplexityBot", "Perplexity-User", "Bytespider", "Amazonbot", "Meta-ExternalAgent",
    "meta-externalfetcher", "FacebookBot", "cohere-ai", "cohere-training-data-crawler", "Diffbot",
    "ImagesiftBot", "omgili", "YouBot", "Timpibot", "AI2Bot", "Ai2Bot-Dolma", "PanguBot", "Kangaroo Bot",
    "Webzio-Extended", "DuckAssistBot", "MistralAI-User",
    // Generic scraping libraries and tools
    "python-requests", "python-urllib", "Scrapy", "aiohttp", "httpx", "Go-http-client", "libwww-perl",
    "Wget", "curl/", "HTTrack", "node-fetch", "axios/",
  ]
    .map((s) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&"))
    .join("|"),
  "i",
);

export function middleware(req: NextRequest) {
  const ua = req.headers.get("user-agent") ?? "";
  if (!ua || BLOCKED.test(ua)) {
    return new NextResponse(
      "Automated access to this site is not allowed. Use the public API: https://contractor-ai-api.onrender.com/docs\n",
      { status: 403, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  }
  return NextResponse.next();
}

export const config = {
  // Everything except Next's own assets, robots.txt and security.txt: bots
  // must be able to read the rules that turn them away.
  matcher: ["/((?!_next/|robots\\.txt|\\.well-known/|favicon|icon\\.png|apple-icon\\.png|logo\\.png).*)"],
};
