import type { MetadataRoute } from "next";

// Crawlers that train AI models or answer questions with the site's content.
// The data stays open through the public API, the CSV export and the model on
// Hugging Face; these bots are asked to use those instead of scraping pages.
// middleware.ts enforces this for the ones that identify themselves.
const AI_BOTS = [
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "ClaudeBot",
  "Claude-User",
  "Claude-SearchBot",
  "anthropic-ai",
  "CCBot",
  "Google-Extended",
  "Applebot-Extended",
  "PerplexityBot",
  "Perplexity-User",
  "Bytespider",
  "Amazonbot",
  "Meta-ExternalAgent",
  "meta-externalfetcher",
  "FacebookBot",
  "cohere-ai",
  "Diffbot",
  "ImagesiftBot",
  "omgili",
  "YouBot",
  "Timpibot",
  "AI2Bot",
  "DuckAssistBot",
  "MistralAI-User",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: AI_BOTS, disallow: "/" },
      // Search engines are welcome; forms and the tracking lookup are not content.
      { userAgent: "*", allow: "/", disallow: ["/reclamos?", "/oportunidades?"] },
    ],
  };
}
