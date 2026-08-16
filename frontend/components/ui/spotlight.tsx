type SpotlightProps = {
  className?: string;
  fill?: string;
};

export function Spotlight({ className = "", fill = "white" }: SpotlightProps) {
  return (
    <svg
      className={`spotlight ${className}`}
      viewBox="0 0 1600 900"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <g filter="url(#spotlight-blur)">
        <ellipse cx="700" cy="280" rx="520" ry="260" fill={fill} fillOpacity="0.16" />
      </g>
      <defs>
        <filter id="spotlight-blur" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="120" />
        </filter>
      </defs>
    </svg>
  );
}
