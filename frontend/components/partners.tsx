import { Marquee } from "@/components/ui/marquee";
import { ImageWithFallback } from "@/components/ui/image-with-fallback";

const PARTNERS = [
  {
    name: "Accountability Lab",
    logo: "https://hackcorruption.org/wp-content/uploads/2022/09/AL_logo-600x87.png",
  },
  {
    name: "HackCorruption",
    logo: "https://hackcorruption.org/wp-content/uploads/2022/09/HC2-e1664374700381.png",
  },
  {
    name: "USAID",
    logo: "https://hackcorruption.org/wp-content/uploads/2023/07/Horizontal_RGB_294-600x233.png",
  },
  {
    name: "OEA",
    logo: "https://upload.wikimedia.org/wikipedia/commons/b/b9/Logo_Organizaci%C3%B3n_de_los_Estados_Americanos_%28OEA%29_-_2025.png",
  },
  {
    name: "Billion Acts",
    logo: "https://www.billionacts.org/assets/img/Logo.svg",
  },
  {
    name: "PeaceJam",
    logo: "https://www.billionacts.org/assets/img/peacejam-footer-logo.png",
  },
  {
    name: "Google",
    logo: "https://www.billionacts.org/assets/img/google-footer-logo.png",
  },
];

export function PartnerLogos({ className = "" }: { className?: string }) {
  return (
    <Marquee className={`partners-marquee ${className}`} durationSeconds={30} reverse>
      {PARTNERS.map((p) => (
        <div key={p.name} className="partner-badge">
          <ImageWithFallback
            src={p.logo}
            alt={p.name}
            className="partner-badge-img"
            fallback={<span className="partner-badge-text">{p.name}</span>}
          />
        </div>
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
