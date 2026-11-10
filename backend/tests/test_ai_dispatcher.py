import pytest
from backend.app.services.ai_dispatcher import AITaskDispatcher


def test_enqueue_returns_task_id_immediately():
    dispatcher = AITaskDispatcher()
    task_id = dispatcher.enqueue_evaluation("evidence-001", "image_hash_001")
    assert task_id is not None

    status = dispatcher.get_task_status(task_id)
    assert status is not None
    assert status["status"] == "ENQUEUED"
    assert status["retries"] == 0


def test_fifo_ordering():
    dispatcher = AITaskDispatcher()
    t1 = dispatcher.enqueue_evaluation("ev-1", "h1")
    t2 = dispatcher.enqueue_evaluation("ev-2", "h2")
    t3 = dispatcher.enqueue_evaluation("ev-3", "h3")

    assert dispatcher.process_next_task() == t1
    assert dispatcher.process_next_task() == t2
    assert dispatcher.process_next_task() == t3


def test_worker_transitions_to_completed():
    dispatcher = AITaskDispatcher()
    t1 = dispatcher.enqueue_evaluation("ev-100", "h100")
    assert dispatcher.get_task_status(t1)["status"] == "ENQUEUED"

    processed = dispatcher.process_next_task(simulate_failure=False)
    assert processed == t1
    assert dispatcher.get_task_status(t1)["status"] == "COMPLETED"


def test_retry_on_worker_failure():
    dispatcher = AITaskDispatcher(max_retries=3)
    t1 = dispatcher.enqueue_evaluation("ev-fail", "hfail")

    # First transient failure
    dispatcher.process_next_task(simulate_failure=True)
    status = dispatcher.get_task_status(t1)
    assert status["status"] == "ENQUEUED"
    assert status["retries"] == 1

    # Second try succeeds
    dispatcher.process_next_task(simulate_failure=False)
    assert dispatcher.get_task_status(t1)["status"] == "COMPLETED"


def test_terminal_failure_after_max_retries():
    dispatcher = AITaskDispatcher(max_retries=3)
    t1 = dispatcher.enqueue_evaluation("ev-term", "hterm")

    dispatcher.process_next_task(simulate_failure=True)
    dispatcher.process_next_task(simulate_failure=True)
    dispatcher.process_next_task(simulate_failure=True)

    status = dispatcher.get_task_status(t1)
    assert status["status"] == "FAILED"
    assert status["retries"] == 3
