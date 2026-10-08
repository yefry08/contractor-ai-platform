import { notFound } from "next/navigation";
import { ARTICLES } from "@/content/datos/articles";
import { POSTS, postBySlug } from "@/content/datos/posts";
import { DATA, NAMES } from "@/content/datos/ui";
import { getServerT } from "@/lib/i18n-server";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const post = postBySlug((await params).slug);
  return post ? { title: `${post.title} — Contractor AI`, description: post.summary } : {};
}

export default async function DatosPost({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = postBySlug(slug);
  const Body = ARTICLES[slug];
  if (!post || !Body) notFound();

  const { t, language, locale } = await getServerT();
  const others = POSTS.filter((p) => p.status === "published" && p.slug !== slug).slice(0, 2);
  const date = new Date(DATA.generated + "T12:00:00").toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <article className="post">
      <a href="/datos" className="wizard-back">
        ← {t("datos.back")}
      </a>
      <span className="datos-tags">
        {post.tags.map((tag) => (
          <span key={tag} className="datos-tag">
            {tag}
          </span>
        ))}
      </span>
      <h1 className="post-title">{post.title}</h1>
      <p className="datos-meta">
        {post.countries.length === 10 ? t("datos.allCountries") : post.countries.map((c) => NAMES[c]).join(" · ")} ·{" "}
        {t("datos.dataAt", { date })} · {t("datos.minutes", { n: post.minutes ?? 5 })}
      </p>
      {language !== "es" && <p className="note">{t("datos.spanishOnly")}</p>}

      <div className="post-body">
        <Body />
      </div>

      <p className="post-disclaimer">{t("datos.disclaimer")}</p>

      <h2 className="wizard-subtitle">{t("datos.more")}</h2>
      <div className="datos-grid">
        {others.map((p) => (
          <a key={p.slug} href={`/datos/${p.slug}`} className="datos-card card">
            <h3>{p.title}</h3>
            <p>{p.summary}</p>
          </a>
        ))}
      </div>
    </article>
  );
}
