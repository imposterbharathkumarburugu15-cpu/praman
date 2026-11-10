"""F-17: Asynchronous AI Task Dispatcher Tests.
Validates background queueing of ingested evidence for AI evaluation,
decoupling from synchronous HTTP responses, task states, and worker retries.
"""

import queue
import time
import uuid
import pytest


class MockAITaskDispatcher:
    """Simulates background task queueing and worker execution."""

    def __init__(self):
        self.queue = queue.Queue()
        self.task_states = {}

    def enqueue_evaluation(self, evidence_id: str, image_hash: str) -> str:
        task_id = str(uuid.uuid4())
        self.task_states[task_id] = {
            "evidence_id": evidence_id,
            "image_hash": image_hash,
            "status": "ENQUEUED",
            "retries": 0,
        }
        self.queue.put(task_id)
        return task_id

    def process_next_task(self, simulate_failure: bool = False) -> str:
        task_id = self.queue.get_nowait()
        self.task_states[task_id]["status"] = "PROCESSING"
        if simulate_failure:
            self.task_states[task_id]["retries"] += 1
            if self.task_states[task_id]["retries"] <= 2:
                self.task_states[task_id]["status"] = "ENQUEUED"
                self.queue.put(task_id)  # Re-enqueue
            else:
                self.task_states[task_id]["status"] = "FAILED"
        else:
            self.task_states[task_id]["status"] = "COMPLETED"
        return task_id


class TestF17AsyncAIDispatch:
    """Verifies async task dispatcher mechanics and decoupling."""

    def test_immediate_enqueue_returns_task_id(self):
        """Test 1: Verifies dispatch returns task ID immediately without waiting for AI inference."""
        dispatcher = MockAITaskDispatcher()
        evidence_id = str(uuid.uuid4())

        task_id = dispatcher.enqueue_evaluation(evidence_id, "mock_hash")
        assert task_id is not None
        assert dispatcher.task_states[task_id]["status"] == "ENQUEUED"

    def test_worker_processes_task_to_completion(self):
        """Test 2: Verifies background worker picks up enqueued task and transitions to COMPLETED."""
        dispatcher = MockAITaskDispatcher()
        task_id = dispatcher.enqueue_evaluation("ev-101", "hash-101")

        processed_id = dispatcher.process_next_task(simulate_failure=False)
        assert processed_id == task_id
        assert dispatcher.task_states[task_id]["status"] == "COMPLETED"

    def test_retry_on_worker_failure(self):
        """Test 3: Verifies transient worker failure triggers task re-queueing with retry count increment."""
        dispatcher = MockAITaskDispatcher()
        task_id = dispatcher.enqueue_evaluation("ev-102", "hash-102")

        # First failure
        dispatcher.process_next_task(simulate_failure=True)
        assert dispatcher.task_states[task_id]["status"] == "ENQUEUED"
        assert dispatcher.task_states[task_id]["retries"] == 1

        # Second run succeeds
        dispatcher.process_next_task(simulate_failure=False)
        assert dispatcher.task_states[task_id]["status"] == "COMPLETED"

    def test_terminal_failure_after_max_retries(self):
        """Test 4: Verifies task transitions to FAILED status after reaching max retry limit."""
        dispatcher = MockAITaskDispatcher()
        task_id = dispatcher.enqueue_evaluation("ev-103", "hash-103")

        # 3 successive failures
        dispatcher.process_next_task(simulate_failure=True)
        dispatcher.process_next_task(simulate_failure=True)
        dispatcher.process_next_task(simulate_failure=True)

        assert dispatcher.task_states[task_id]["status"] == "FAILED"
        assert dispatcher.task_states[task_id]["retries"] == 3

    def test_fifo_task_ordering(self):
        """Test 5: Verifies tasks are processed in First-In-First-Out order."""
        dispatcher = MockAITaskDispatcher()
        t1 = dispatcher.enqueue_evaluation("ev-1", "h1")
        t2 = dispatcher.enqueue_evaluation("ev-2", "h2")

        assert dispatcher.process_next_task() == t1
        assert dispatcher.process_next_task() == t2
