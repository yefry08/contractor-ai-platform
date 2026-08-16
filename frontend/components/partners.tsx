import { Marquee } from "@/components/ui/marquee";

const PARTNERS = [
  "Accountability Lab",
  "HackCorruption",
  "USAID",
  "OEA",
  "Billion Acts",
  "PeaceJam",
];

export function PartnerLogos({ className = "" }: { className?: string }) {
  return (
    <Marquee className={`partners-marquee ${className}`} durationSeconds={30} reverse>
      {PARTNERS.map((name) => (
        <span key={name} className="partner-badge">
          {name}
        </span>
      ))}
    </Marquee>
  );
}

export function Partners() {
  return (
    <section className="partners-section">
      <span className="team-eyebrow">respaldado por</span>
      <h2 className="team-title">Aliados</h2>
      <PartnerLogos />
    </section>
  );
}
