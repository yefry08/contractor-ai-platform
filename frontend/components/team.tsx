import { Marquee } from "@/components/ui/marquee";
import { ImageWithFallback } from "@/components/ui/image-with-fallback";
import { XIcon, LinkedInIcon, MailIcon } from "@/components/ui/social-icons";

type Member = {
  name: string;
  role: string;
  photo: string;
  initials: string;
  x?: string;
  linkedin?: string;
  email?: string;
};

const MEMBERS: Member[] = [
  {
    name: "Cristian Sosa",
    role: "Business Guru",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/7.-Cristian-Sosa-min-scaled-e1691679271248.jpg",
    initials: "CS",
    x: "#",
  },
  {
    name: "Dayanni Olivo",
    role: "Journalist",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/16.-Dayanni-Olivo-Bogota-min-600x801.jpeg",
    initials: "DO",
    x: "#",
  },
  {
    name: "Daniel Duque",
    role: "IA Engineer",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/11.-Daniel-Duque-Lozano-min.jpeg",
    initials: "DD",
    x: "#",
  },
  {
    name: "Daniel Sosa",
    role: "Data Science",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/Daniel-Leonardo-Rojas-Acosta-min-600x800.jpg",
    initials: "DS",
    x: "#",
  },
  {
    name: "Yefry Nunez",
    role: "Full-Stack Developer",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/69.-Yefry-Nunez-e1691657328142.jpeg",
    initials: "YN",
    x: "#",
  },
  {
    name: "Natalia Ramírez Pérez",
    role: "Analítica avanzada · IA",
    photo:
      "https://media.licdn.com/dms/image/v2/D4E03AQHI4Vu3-_lhJA/profile-displayphoto-shrink_800_800/profile-displayphoto-shrink_800_800/0/1705888131569?e=1788393600&v=beta&t=waFNn0Uxt1pKD9xSQNkrkeEl0XzgKThtCa87gCWohQk",
    initials: "NR",
    linkedin: "https://www.linkedin.com/in/natalia-ramirez-datamath",
    email: "narp1212@gmail.com",
  },
  {
    name: "Domingo Aybar Santos",
    role: "Founder @Fligo",
    photo:
      "https://media.licdn.com/dms/image/v2/D4E03AQFq3lOQgCc0EQ/profile-displayphoto-crop_800_800/B4EZ1y6gMTG4AM-/0/1775749434786?e=1788393600&v=beta&t=jrVhtSfnQdB_qkAzvBKUcV3yKBTbG9uxY2mRhUCcino",
    initials: "DA",
    linkedin: "https://www.linkedin.com/in/domingo-aybar-santos-527a08249",
    email: "domingo8537@gmail.com",
  },
  {
    name: "Nicole Checo",
    role: "Ciencias Políticas",
    photo:
      "https://media.licdn.com/dms/image/v2/D4D03AQEnnpNfubEZKQ/profile-displayphoto-scale_200_200/B4DZthZ9l4IYAc-/0/1766865759214?e=1788393600&v=beta&t=H9uaHkbHhYQo2XhYXNMeMKkkagf88dk9iCspQI_SIjs",
    initials: "NC",
    linkedin: "https://www.linkedin.com/in/nicole-checo",
    email: "nicolecheco99@gmail.com",
  },
  {
    name: "Jomayris Rosario Medina",
    role: "Economista · Políticas públicas",
    photo:
      "https://media.licdn.com/dms/image/v2/D4E03AQF-tJtL6Gqa4w/profile-displayphoto-scale_200_200/B4EZwCZnhLGcAY-/0/1769566798483?e=1788393600&v=beta&t=P6ROHGDSjYiFWIJxudqSmm02YK1efi7Uj9jCAbpG0Qw",
    initials: "JR",
    linkedin: "https://www.linkedin.com/in/jomayris-rosario-medina13",
    email: "jomayris13@live.com",
  },
];

function MemberCard({ m }: { m: Member }) {
  return (
    <div className="team-card">
      <ImageWithFallback
        src={m.photo}
        alt={m.name}
        className="team-card-photo"
        fallback={
          <div className="team-card-photo team-card-initials" aria-hidden="true">
            {m.initials}
          </div>
        }
      />
      <div className="team-card-content">
        <h3>{m.name}</h3>
        <p>{m.role}</p>
        <ul>
          {m.linkedin && (
            <li>
              <a href={m.linkedin} target="_blank" rel="noopener noreferrer" aria-label={`${m.name} en LinkedIn`}>
                <LinkedInIcon />
              </a>
            </li>
          )}
          {m.x && (
            <li>
              <a href={m.x} aria-label={`${m.name} en X`}>
                <XIcon />
              </a>
            </li>
          )}
          {m.email && (
            <li>
              <a href={`mailto:${m.email}`} aria-label={`Escribir a ${m.name}`}>
                <MailIcon />
              </a>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}

export function Team() {
  return (
    <section className="team-section">
      <span className="team-eyebrow">meet our</span>
      <h2 className="team-title">Founders</h2>
      <p className="team-lead">
        Esta solución la construye un equipo que combina capacidades de producto y
        capacidades técnicas entre sus integrantes:
      </p>

      <Marquee className="team-marquee" durationSeconds={45}>
        {MEMBERS.map((m) => (
          <MemberCard key={m.name} m={m} />
        ))}
      </Marquee>
    </section>
  );
}
