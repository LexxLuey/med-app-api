import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .models import TaskStatus
from .schemas import TaskStatusCreate


class TaskManager:
    """Manages background task status and prevents concurrent execution"""

    def __init__(self):
        self._active_tasks = set()  # In-memory tracking for quick checks

    def create_task(self, db: Session, task_data: TaskStatusCreate) -> TaskStatus:
        """Create a new task status record"""
        task_status = TaskStatus(
            task_id=task_data.task_id,
            task_type=task_data.task_type,
            status="pending",
            progress=0,
            message=task_data.message,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            user_id=task_data.user_id,
            details=json.dumps({"start_time": datetime.utcnow().isoformat()}),
        )

        db.add(task_status)
        db.commit()
        db.refresh(task_status)

        self._active_tasks.add(task_data.task_id)
        return task_status

    def update_task_status(
        self,
        db: Session,
        task_id: str,
        status: str,
        progress: int = None,
        message: str = None,
        details: Dict[str, Any] = None,
    ) -> bool:
        """Update task status"""
        task = db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()
        if not task:
            return False

        task.status = status
        task.updated_at = datetime.utcnow().isoformat()

        if progress is not None:
            task.progress = progress
        if message is not None:
            task.message = message
        if details is not None:
            current_details = json.loads(task.details) if task.details else {}
            current_details.update(details)
            current_details["last_update"] = datetime.utcnow().isoformat()
            task.details = json.dumps(current_details)

        db.commit()

        # Update in-memory tracking
        if status in ["completed", "failed"]:
            self._active_tasks.discard(task_id)

        return True

    def get_task_status(self, db: Session, task_id: str) -> Optional[TaskStatus]:
        """Get task status by ID"""
        return db.query(TaskStatus).filter(TaskStatus.task_id == task_id).first()

    def get_active_tasks(self, db: Session, task_type: str = None) -> list:
        """Get all active (running/pending) tasks"""
        query = db.query(TaskStatus).filter(TaskStatus.status.in_(["pending", "running"]))

        if task_type:
            query = query.filter(TaskStatus.task_type == task_type)

        return query.all()

    def can_start_task(self, db: Session, task_type: str, user_id: str) -> tuple[bool, str]:
        """Check if a new task can be started"""
        # Check for existing active tasks of same type
        active_tasks = self.get_active_tasks(db, task_type)

        if active_tasks:
            task = active_tasks[0]
            return False, f"Task '{task.task_id}' is already {task.status}"

        # Check user-specific limits if needed
        user_active_tasks = [t for t in active_tasks if t.user_id == user_id]
        if len(user_active_tasks) >= 1:  # Allow only 1 concurrent task per user
            return False, "You already have an active task running"

        return True, "Task can be started"

    def cleanup_old_tasks(self, db: Session, days_old: int = 7) -> int:
        """Clean up old completed/failed tasks"""
        cutoff_date = datetime.utcnow().timestamp() - (days_old * 24 * 60 * 60)

        deleted_count = (
            db.query(TaskStatus)
            .filter(
                TaskStatus.status.in_(["completed", "failed"]), TaskStatus.created_at < cutoff_date
            )
            .delete()
        )

        db.commit()
        return deleted_count

    def generate_task_id(self, task_type: str) -> str:
        """Generate unique task ID"""
        return f"{task_type}_{uuid.uuid4().hex[:8]}"


# Global task manager instance
task_manager = TaskManager()


def get_task_manager() -> TaskManager:
    """Dependency injection for task manager"""
    return task_manager
