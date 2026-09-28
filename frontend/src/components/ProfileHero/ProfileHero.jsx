import React from "react";
import styles from "./ProfileHero.module.css";

const StatItem = ({ value, label, icon }) => (
  <div className={styles.statItem}>
    <span className={styles.statIcon}>{icon}</span>
    <span className={styles.statValue}>{value.toLocaleString()}</span>
    <span className={styles.statLabel}>{label}</span>
  </div>
);

export default function ProfileHero({ profile }) {
  if (!profile) return null;

  return (
    <div className={styles.hero}>
      <div className={styles.heroBg} aria-hidden="true" />
      <div className={styles.heroContent}>
        <div className={styles.profileSection}>
          <div className={styles.avatarWrapper}>
            <img
              src={`https://avatars.githubusercontent.com/${encodeURIComponent(profile.username.toLowerCase())}?s=192`}
              alt={`${profile.username} GitHub avatar`}
              className={styles.avatar}
              loading="eager"
              fetchPriority="high"
              width={96}
              height={96}
            />
            <div className={styles.avatarRing} aria-hidden="true" />
          </div>
          <div className={styles.profileInfo}>
            <h1 className={styles.profileName}>{profile.username}</h1>
            <p className={styles.profileHandle}>
              <svg
                className={styles.githubIcon}
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.42-1.305.763-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.49 11.49 0 013.006-.404c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.91 1.235 3.22 0 4.61-2.807 5.625-5.479 5.92.43.372.824 1.102.824 2.222 0 1.606-.015 2.898-.015 3.293 0 .322.216.694.825.576C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
              </svg>
              @{profile.username}
            </p>
            <div className={styles.profileLinks}>
              <a
                href={`https://github.com/${profile.username}`}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.profileLink}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                  className={styles.linkIcon}
                >
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.42-1.305.763-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23a11.49 11.49 0 013.006-.404c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.91 1.235 3.22 0 4.61-2.807 5.625-5.479 5.92.43.372.824 1.102.824 2.222 0 1.606-.015 2.898-.015 3.293 0 .322.216.694.825.576C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
                </svg>
                GitHub
              </a>
              <a
                href="https://makeboldsolutions.com"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.profileLink}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                  className={styles.linkIcon}
                >
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
                Make Bold Solutions
              </a>
            </div>
          </div>
        </div>

        <div className={styles.statsSection}>
          <StatItem
            value={profile.total_repositories}
            label="Repositories"
            icon="📦"
          />
          <StatItem value={profile.total_commits} label="Commits" icon="💻" />
          <StatItem value={profile.total_stars} label="Stars" icon="⭐" />
          <StatItem value={profile.total_forks} label="Forks" icon="🍴" />
        </div>
      </div>
    </div>
  );
}
