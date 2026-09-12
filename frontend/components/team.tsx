import { Marquee } from "@/components/ui/marquee";
import { ImageWithFallback } from "@/components/ui/image-with-fallback";
import { XIcon, LinkedInIcon, MailIcon } from "@/components/ui/social-icons";
import { getServerT } from "@/lib/i18n-server";

type Member = {
  name: string;
  roleKey: string;
  photo: string;
  initials: string;
  x?: string;
  linkedin?: string;
  email?: string;
};

// Photos are served from this repo, under public/team/. They used to be
// hotlinked from LinkedIn, whose CDN signs every URL with an expiry — all four
// of those returned 403 and fell back to initials. Any replacement LinkedIn
// URL would expire the same way, so the files live here instead. A missing
// file still falls back to initials rather than a broken image.
const MEMBERS: Member[] = [
  {
    name: "Cristian Sosa",
    roleKey: "business",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/7.-Cristian-Sosa-min-scaled-e1691679271248.jpg",
    initials: "CS",
    x: "#",
  },
  {
    name: "Dayanni Olivo",
    roleKey: "journalist",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/16.-Dayanni-Olivo-Bogota-min-600x801.jpeg",
    initials: "DO",
    x: "#",
  },
  {
    name: "Daniel Duque",
    roleKey: "researcher",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/11.-Daniel-Duque-Lozano-min.jpeg",
    initials: "DD",
    x: "#",
  },
  {
    name: "Daniel Sosa",
    roleKey: "dataScience",
    photo:
      "https://hackcorruption.org/wp-content/uploads/2023/08/Daniel-Leonardo-Rojas-Acosta-min-600x800.jpg",
    initials: "DS",
    x: "#",
  },
  {
    name: "Yefry Nunez",
    roleKey: "ceo",
    photo: "https://hackcorruption.org/wp-content/uploads/2023/08/69.-Yefry-Nunez-e1691657328142.jpeg",
    initials: "YN",
    x: "#",
  },
  {
    name: "Natalia Ramírez Pérez",
    roleKey: "cto",
    photo: "/team/natalia-ramirez.jpg",
    initials: "NR",
    linkedin: "https://www.linkedin.com/in/natalia-ramirez-datamath",
    email: "narp1212@gmail.com",
  },
  {
    name: "Domingo Aybar Santos",
    roleKey: "information",
    photo: "/team/domingo-aybar.jpg",
    initials: "DA",
    linkedin: "https://www.linkedin.com/in/domingo-aybar-santos-527a08249",
    email: "domingo8537@gmail.com",
  },
  {
    name: "Nicole Checo",
    roleKey: "politics",
    photo: "/team/nicole-checo.jpg",
    initials: "NC",
    linkedin: "https://www.linkedin.com/in/nicole-checo",
    email: "nicolecheco99@gmail.com",
  },
  {
    name: "Jomayris Rosario Medina",
    roleKey: "financial",
    photo: "/team/jomayris-rosario.jpg",
    initials: "JR",
    linkedin: "https://www.linkedin.com/in/jomayris-rosario-medina13",
    email: "jomayris13@live.com",
  },
];

function MemberCard({
  m,
  role,
  linkedinLabel,
  xLabel,
  mailLabel,
}: {
  m: Member;
  role: string;
  linkedinLabel: string;
  xLabel: string;
  mailLabel: string;
}) {
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
        <p>{role}</p>
        <ul>
          {m.linkedin && (
            <li>
              <a href={m.linkedin} target="_blank" rel="noopener noreferrer" aria-label={linkedinLabel}>
                <LinkedInIcon />
              </a>
            </li>
          )}
          {m.x && (
            <li>
              <a href={m.x} aria-label={xLabel}>
                <XIcon />
              </a>
            </li>
          )}
          {m.email && (
            <li>
              <a href={`mailto:${m.email}`} aria-label={mailLabel}>
                <MailIcon />
              </a>
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}

export async function Team() {
  const { t } = await getServerT();

  return (
    <section className="team-section">
      <span className="team-eyebrow">{t("team.eyebrow")}</span>
      <h2 className="team-title">{t("team.title")}</h2>
      <p className="team-lead">{t("team.lead")}</p>

      <Marquee className="team-marquee" durationSeconds={45}>
        {MEMBERS.map((m) => (
          <MemberCard
            key={m.name}
            m={m}
            role={t(`team.roles.${m.roleKey}`)}
            linkedinLabel={t("team.linkedinAria", { name: m.name })}
            xLabel={t("team.xAria", { name: m.name })}
            mailLabel={t("team.mailAria", { name: m.name })}
          />
        ))}
      </Marquee>
    </section>
  );
}
