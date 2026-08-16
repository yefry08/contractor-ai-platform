import { Marquee } from "@/components/ui/marquee";
import { XIcon, LinkedInIcon, MailIcon } from "@/components/ui/social-icons";

type Member = {
  name: string;
  role: string;
  photo?: string;
  initials?: string;
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
    x: "#",
  },
  {
    name: "Dayanni Olivo",
    role: "Journalist",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/16.-Dayanni-Olivo-Bogota-min-600x801.jpeg",
    x: "#",
  },
  {
    name: "Daniel Duque",
    role: "IA Engineer",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/11.-Daniel-Duque-Lozano-min.jpeg",
    x: "#",
  },
  {
    name: "Daniel Sosa",
    role: "Data Science",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/Daniel-Leonardo-Rojas-Acosta-min-600x800.jpg",
    x: "#",
  },
  {
    name: "Yefry Nunez",
    role: "Full-Stack Developer",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/69.-Yefry-Nunez-e1691657328142.jpeg",
    x: "#",
  },
  {
    name: "Natalia Ramírez Pérez",
    role: "Analítica avanzada · IA",
    initials: "NR",
    linkedin: "https://www.linkedin.com/in/natalia-ramirez-datamath",
    email: "narp1212@gmail.com",
  },
  {
    name: "Domingo Aybar Santos",
    role: "Founder @Fligo",
    initials: "DA",
    linkedin: "https://www.linkedin.com/in/domingo-aybar-santos-527a08249",
    email: "domingo8537@gmail.com",
  },
  {
    name: "Nicole Checo",
    role: "Ciencias Políticas",
    initials: "NC",
    linkedin: "https://www.linkedin.com/in/nicole-checo",
    email: "nicolecheco99@gmail.com",
  },
  {
    name: "Jomayris Rosario Medina",
    role: "Economista · Políticas públicas",
    initials: "JR",
    linkedin: "https://www.linkedin.com/in/jomayris-rosario-medina13",
    email: "jomayris13@live.com",
  },
];

function MemberCard({ m }: { m: Member }) {
  return (
    <div className="team-card">
      {m.photo ? (
        <img src={m.photo} alt={m.name} className="team-card-photo" loading="lazy" />
      ) : (
        <div className="team-card-photo team-card-initials" aria-hidden="true">
          {m.initials}
        </div>
      )}
      <div className="team-card-content">
        <h3>{m.name}</h3>
        <p>{m.role}</p>
        <ul>
          {m.x && (
            <li>
              <a href={m.x} aria-label={`${m.name} en X`}>
                <XIcon />
              </a>
            </li>
          )}
          {m.linkedin && (
            <li>
              <a href={m.linkedin} target="_blank" rel="noopener noreferrer" aria-label={`${m.name} en LinkedIn`}>
                <LinkedInIcon />
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
