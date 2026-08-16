import type { CSSProperties, ReactNode } from "react";

type MarqueeProps = {
  children: ReactNode;
  className?: string;
  reverse?: boolean;
  durationSeconds?: number;
};

export function Marquee({ children, className = "", reverse = false, durationSeconds = 40 }: MarqueeProps) {
  const style = {
    "--marquee-duration": `${durationSeconds}s`,
    animationDirection: reverse ? "reverse" : "normal",
  } as CSSProperties;

  return (
    <div className={`marquee ${className}`}>
      <div className="marquee-track" style={style}>
        <div className="marquee-group">{children}</div>
        <div className="marquee-group" aria-hidden="true">
          {children}
        </div>
      </div>
    </div>
  );
}
