import { Button } from "@/components/Brand";
import styles from "../../RepositoryDetail.module.css";

function RepositoryDetailFooter({ onPrevious, onNext, hasPrevious, hasNext }) {
  return (
    <div className={styles.modalFooter}>
      <div className={styles.navigationButtons}>
        <Button
          variant="secondary"
          size="sm"
          onClick={onPrevious}
          disabled={!hasPrevious}
          aria-label="Previous repository"
        >
          ← Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={onNext}
          disabled={!hasNext}
          aria-label="Next repository"
        >
          Next →
        </Button>
      </div>
      <p className={styles.footerHelp}>Arrow keys to navigate · Esc to close</p>
    </div>
  );
}

export default RepositoryDetailFooter;
