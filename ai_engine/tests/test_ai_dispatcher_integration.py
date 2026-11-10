import io
import uuid
import pytest
from PIL import Image

from backend.app.storage.content_storage import content_storage
from backend.app.services.ai_dispatcher import AITaskDispatcher


def test_ai_dispatcher_with_real_cas_storage():
    """Verifies AITaskDispatcher retrieves real CAS image bytes and computes evaluation."""
    dispatcher = AITaskDispatcher()

    # Create test image in CAS storage
    img = Image.new("RGB", (256, 256), color=(40, 140, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    raw_bytes = buf.getvalue()

    image_hash = content_storage.store(raw_bytes, ext="jpg")
    evidence_id = str(uuid.uuid4())

    envelope = {
        "evidence_id": evidence_id,
        "lifecycle_stage": "CROP_GROWTH",
        "metadata": {
            "capture_timestamp": "2026-11-09T18:00:00Z",
        },
    }

    task_id = dispatcher.enqueue_evaluation(
        evidence_id=evidence_id,
        image_hash=image_hash,
        envelope=envelope,
    )

    processed_id = dispatcher.process_next_task(simulate_failure=False)
    assert processed_id == task_id

    task_state = dispatcher.get_task_status(task_id)
    assert task_state["status"] == "COMPLETED"
    assert task_state["assessment"] is not None

    assessment = task_state["assessment"]
    assert assessment["evidence_id"] == evidence_id
    assert "quality" in assessment
    assert "category" in assessment
    assert "forensics" in assessment
    assert assessment["governance"]["state_transition"] in ("PENDING_BATCH", "PENDING_REVIEW")
