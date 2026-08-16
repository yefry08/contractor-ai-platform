"use client";

import { useState, type ReactNode } from "react";

type ImageWithFallbackProps = {
  src: string;
  alt: string;
  className?: string;
  fallback: ReactNode;
};

// LinkedIn's profile-photo CDN URLs are signed with a short-lived expiry
// (the `e=` query param), so a hotlinked photo will eventually 403. Rather
// than let that show up as a broken-image icon, swap to the given fallback
// (e.g. an initials avatar) the moment the image fails to load.
//
// Deliberately NOT `loading="lazy"`: every caller of this component lives
// inside a continuously CSS-animated marquee (see components/ui/marquee.tsx).
// The animation keeps translating elements in and out of the viewport via
// `transform`, which churns the IntersectionObserver lazy-loading uses and
// can leave images stuck never firmly triggering a load. There's also no
// real "below the fold" benefit to defer here -- a marquee's whole point is
// that everything scrolls into view within seconds regardless of where the
// page loaded.
export function ImageWithFallback({ src, alt, className, fallback }: ImageWithFallbackProps) {
  const [failed, setFailed] = useState(false);

  if (failed || !src) return <>{fallback}</>;

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
