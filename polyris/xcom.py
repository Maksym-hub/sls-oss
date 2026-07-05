"""
XCom - Data passing between tasks.
Airflow-compatible implementation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task import TaskInstance


class XComArg:
    """
    Represents output of a task, used for data passing.
    Airflow-compatible: task() returns XComArg, can be passed to other tasks.
    """
    def __init__(self, task_instance: 'TaskInstance', key: str = "return_value"):
        self.task_instance = task_instance
        self.key = key
    
    @property
    def task_id(self) -> str:
        return self.task_instance.task.task_id
    
    def __repr__(self):
        return f"XComArg({self.task_id}.{self.key})"
