import { ExternalLink } from "lucide-react";
import { Card, Button, Eyebrow } from "@/components/Brand";
import { formatSourceDate } from "@/utils/repositoryPresentation";
import styles from "./ProfileHero.module.css";

const STATS = [
  { key: "total_repositories", label: "Repositories" },
  { key: "total_commits", label: "Commits" },
  { key: "total_stars", label: "Stars" },
  { key: "total_forks", label: "Forks" },
];

export default function ProfileHero({ profile, generatedAt }) {
  if (!profile) return null;

  const username = profile.username;

  return (
    <div className={styles.hero}>
      <div className={styles.left}>
        <Eyebrow>Open-source portfolio</Eyebrow>
        <h1 className={styles.headline}>
          Built to scale,{" "}
          <span className={styles.headlineAccent}>in the open.</span>
        </h1>
        <p className={styles.lead}>
          Explore {username}&rsquo;s public GitHub repositories — an AI-powered
          analytics dashboard showcasing .NET, React, Python, and more.
        </p>
        <div className={styles.actions}>
          <Button
            variant="primary"
            size="lg"
            iconRight={<ExternalLink size={18} aria-hidden="true" />}
            onClick={() =>
              window.open(
                `https://github.com/${username}`,
                "_blank",
                "noopener,noreferrer",
              )
            }
          >
            View on GitHub
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={() =>
              window.open(
                "https://makeboldspark.com",
                "_blank",
                "noopener,noreferrer",
              )
            }
          >
            Visit Make Bold Spark
          </Button>
        </div>
      </div>

      <Card padding="lg" accent className={styles.statsCard}>
        <div className={styles.statsHeader}>
          <span className={styles.handle}>@{username}</span>
          <span className={styles.updated}>
            Updated {formatSourceDate(generatedAt)}
          </span>
        </div>
        <div className={styles.statsGrid}>
          {STATS.map(({ key, label }) => (
            <div key={key} className={styles.statCell}>
              <span className={styles.statValue}>
                {(profile[key] ?? 0).toLocaleString()}
              </span>
              <Eyebrow as="span" color="muted" className={styles.statLabel}>
                {label}
              </Eyebrow>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
