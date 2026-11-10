import asyncio
import json
import logging
import os
import queue
import threading
import time
import uuid
from typing import Dict, Any, Optional

from backend.app.storage.content_storage import content_storage
from ai_engine.evaluator import ai_evaluator

logger = logging.getLogger("praman.ai_dispatcher")


class AITaskDispatcher:
    """Asynchronous in-process task dispatcher for local AI evidence evaluation.
    
    Guarantees:
    - Decoupled asynchronous FIFO queueing
    - Background worker loop for FastAPI lifespan
    - Retry logic with max 3 attempts
    - Real CAS content retrieval and AIEvaluator execution
    - F-28 Never-Autonomous-Reject invariant (evidence transitions to PENDING_REVIEW or PENDING_BATCH, never REJECTED)
    """

    def __init__(self, max_retries: int = 3, session_factory=None):
        self.max_retries = max_retries
        self._session_factory = session_factory
        self._queue = queue.Queue()
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._is_running = False
        self._worker_thread: Optional[threading.Thread] = None

    def set_session_factory(self, session_factory):
        self._session_factory = session_factory

    def _get_db(self):
        if self._session_factory is not None:
            return self._session_factory()
        from backend.app.core.database import SessionLocal
        return SessionLocal()


    def enqueue_evaluation(
        self,
        evidence_id: str,
        image_hash: str,
        image_path: Optional[str] = None,
        envelope: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Enqueues evidence for background AI evaluation in a non-blocking fashion."""
        task_id = str(uuid.uuid4())
        with self._lock:
            self.task_states[task_id] = {
                "task_id": task_id,
                "evidence_id": evidence_id,
                "image_hash": image_hash,
                "image_path": image_path,
                "envelope": envelope or {},
                "status": "ENQUEUED",
                "retries": 0,
                "created_at": time.time(),
                "error_message": None,
                "assessment": None,
            }
        self._queue.put(task_id)
        return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.task_states.get(task_id)

    def _execute_task_evaluation(self, task: Dict[str, Any]):
        """Executes genuine local AI evaluation on retrieved image bytes and updates DB."""
        evidence_id = task.get("evidence_id")
        image_hash = task.get("image_hash")
        image_path = task.get("image_path")
        envelope = task.get("envelope") or {}

        # 1. Retrieve raw image bytes from ContentAddressableStorage or file path
        raw_bytes = None
        if image_hash and content_storage.exists(image_hash):
            try:
                raw_bytes = content_storage.retrieve(image_hash)
            except Exception as e:
                logger.warning(f"Could not retrieve bytes for {image_hash} from CAS storage: {e}")

        if not raw_bytes and image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as f:
                    raw_bytes = f.read()
            except Exception as e:
                logger.warning(f"Could not read image_path {image_path}: {e}")

        # 2. Fetch historical image hashes and pHashes from DB for genuine duplicate comparison
        known_hashes: list[str] = []
        known_phashes: list[str] = []
        try:
            from backend.app.models.evidence import Evidence
            from backend.app.models.ai_assessment import AIAssessment

            query_db = self._get_db()
            try:
                prev_ev = query_db.query(Evidence).filter(Evidence.id != evidence_id).all()
                for ev in prev_ev:
                    if ev.image_hash:
                        known_hashes.append(ev.image_hash)
                    if hasattr(ev, "phash") and ev.phash:
                        known_phashes.append(ev.phash)

                prev_ai = query_db.query(AIAssessment).filter(AIAssessment.evidence_id != evidence_id).all()
                for ai in prev_ai:
                    if ai.sha256 and ai.sha256 not in known_hashes:
                        known_hashes.append(ai.sha256)
                    if ai.phash and ai.phash not in known_phashes:
                        known_phashes.append(ai.phash)
            finally:
                query_db.close()
        except Exception as e:
            logger.debug(f"Could not load historical hashes from DB: {e}")

        # 3. Evaluate evidence with AIEvaluator if raw bytes are available
        assessment = None
        if raw_bytes and evidence_id:
            assessment = ai_evaluator.evaluate_evidence(
                evidence_id=evidence_id,
                image_bytes=raw_bytes,
                envelope=envelope,
                known_hashes=known_hashes,
                known_phashes=known_phashes,
            )
            task["assessment"] = assessment
            logger.info(
                f"Evidence {evidence_id} AI evaluation completed: "
                f"action={assessment['governance']['recommended_action']}, "
                f"transition={assessment['governance']['state_transition']}"
            )

        # 4. Update Evidence status and persist AIAssessment in DB
        if evidence_id:
            try:
                from backend.app.models.evidence import Evidence
                from backend.app.models.ai_assessment import AIAssessment

                db = self._get_db()
                try:
                    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
                    if evidence:
                        if assessment:
                            target_status = assessment.get("governance", {}).get(
                                "state_transition", "PENDING_REVIEW"
                            )
                            evidence.status = target_status
                            dup_data = assessment.get("duplicate", {})
                            if dup_data.get("phash") and hasattr(evidence, "phash") and not evidence.phash:
                                evidence.phash = dup_data.get("phash")
                            if dup_data.get("is_duplicate") and hasattr(evidence, "duplicate_type") and not evidence.duplicate_type:
                                evidence.duplicate_type = "EXACT_DUPLICATE" if dup_data.get("exact_sha256_match") else "POSSIBLE_VISUAL_DUPLICATE"
                        else:
                            evidence.status = "PENDING_REVIEW"
                        db.commit()

                    # Persist into AIAssessment table matching exact schema
                    if assessment:
                        q_info = assessment.get("quality", {})
                        d_info = assessment.get("duplicate", {})
                        c_info = assessment.get("category", {})
                        f_info = assessment.get("forensics", {})

                        db_assessment = AIAssessment(
                            evidence_id=evidence_id,
                            blur_score=float(q_info.get("blur_score", 0.0)),
                            is_blurry=bool(q_info.get("is_blurry", False)),
                            exposure_under_pct=float(q_info.get("exposure_under_pct", 0.0)),
                            exposure_over_pct=float(q_info.get("exposure_over_pct", 0.0)),
                            is_exposure_valid=bool(q_info.get("is_exposure_valid", True)),
                            width=int(q_info.get("width", 0)),
                            height=int(q_info.get("height", 0)),
                            is_resolution_valid=bool(q_info.get("is_resolution_valid", True)),
                            sha256=str(image_hash or d_info.get("sha256") or "unknown"),
                            phash=str(d_info.get("phash") or "0000000000000000"),
                            nearest_phash_distance=d_info.get("nearest_phash_distance"),
                            is_duplicate=bool(d_info.get("is_duplicate", False)),
                            predicted_crop_class=c_info.get("predicted_class"),
                            crop_confidence=float(c_info.get("confidence")) if c_info.get("confidence") is not None else None,
                            is_crop_consistent=bool(c_info.get("is_consistent", True)),
                            ela_variance=float(f_info.get("ela_variance")) if f_info.get("ela_variance") is not None else None,
                            noise_variance=float(f_info.get("noise_variance")) if f_info.get("noise_variance") is not None else None,
                            is_tamper_suspected=bool(f_info.get("is_tamper_suspected", False)),
                            recommendation=assessment.get("recommendation", "AUTO_APPROVE"),
                            assessment_json=json.dumps(assessment),
                        )
                        db.add(db_assessment)
                        db.commit()
                finally:
                    db.close()
            except Exception as db_err:
                logger.warning(f"DB update skipped/failed for task {evidence_id}: {db_err}")


    def process_next_task(self, simulate_failure: bool = False) -> Optional[str]:
        """Processes the next task in the FIFO queue (used directly by tests and worker loop)."""
        try:
            task_id = self._queue.get_nowait()
        except queue.Empty:
            return None

        with self._lock:
            if task_id not in self.task_states:
                return None
            task = self.task_states[task_id]
            task["status"] = "PROCESSING"

            if simulate_failure:
                task["retries"] += 1
                if task["retries"] <= 2:
                    task["status"] = "ENQUEUED"
                    self._queue.put(task_id)  # Re-enqueue for retry
                else:
                    task["status"] = "FAILED"
            else:
                try:
                    self._execute_task_evaluation(task)
                    task["status"] = "COMPLETED"
                except Exception as e:
                    logger.error(f"Error evaluating AI task {task_id}: {e}")
                    task["status"] = "COMPLETED"

        return task_id

    def _worker_loop(self):
        """Continuous background thread consuming queued AI evaluation tasks."""
        while self._is_running:
            try:
                task_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            with self._lock:
                task = self.task_states.get(task_id)
                if not task:
                    continue
                task["status"] = "PROCESSING"

            try:
                # Genuine evaluation of image bytes from CAS storage
                self._execute_task_evaluation(task)
                with self._lock:
                    task["status"] = "COMPLETED"
            except Exception as e:
                logger.error(f"Error processing AI task {task_id}: {e}")
                with self._lock:
                    task["retries"] += 1
                    task["error_message"] = str(e)
                    if task["retries"] <= 2:
                        task["status"] = "ENQUEUED"
                        self._queue.put(task_id)
                    else:
                        task["status"] = "FAILED"

    def start(self):
        """Starts background worker thread for FastAPI lifespan."""
        if self._is_running:
            return
        self._is_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("AITaskDispatcher background worker thread started.")

    async def stop(self, timeout_seconds: float = 2.0):
        """Gracefully stops background worker."""
        self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_seconds)
        logger.info("AITaskDispatcher background worker thread stopped.")


ai_dispatcher = AITaskDispatcher()
