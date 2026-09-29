import styles from "../../RepositoryDetail.module.css";

function RankingSection({ repository }) {
  if (repository.has_readme == null) return null;

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>README Availability</h3>
      <dl className={styles.detailList}>
        <div className={styles.detailItem}>
          <dt>Has README</dt>
          <dd>{repository.has_readme ? "Yes" : "No"}</dd>
        </div>
      </dl>
    </section>
  );
}

export default RankingSection;
