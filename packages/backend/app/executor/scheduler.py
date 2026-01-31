from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set

from ..db.models import Task, TaskStatus


def _parse_depends_on(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return [value]
        return [value]
    return [str(value)]


@dataclass
class TaskNode:
    task: Task
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)


class TaskScheduler:
    def __init__(self, tasks: List[Task]):
        self.nodes: Dict[str, TaskNode] = {}
        self._build_graph(tasks)

    def _build_graph(self, tasks: List[Task]) -> None:
        for task in tasks:
            self.nodes[task.id] = TaskNode(
                task=task,
                dependencies=set(_parse_depends_on(task.depends_on)),
            )

        for task_id, node in self.nodes.items():
            for dep_id in node.dependencies:
                if dep_id in self.nodes:
                    self.nodes[dep_id].dependents.add(task_id)

        self._detect_cycles()

    def _detect_cycles(self) -> None:
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            stack.add(task_id)

            for dep_id in self.nodes[task_id].dependencies:
                if dep_id not in self.nodes:
                    continue
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in stack:
                    return True

            stack.remove(task_id)
            return False

        for task_id in self.nodes:
            if task_id not in visited:
                if dfs(task_id):
                    raise ValueError("Circular dependency detected")

    def get_ready_tasks(self, max_count: int = 5) -> List[Task]:
        ready: List[Task] = []
        for node in self.nodes.values():
            task = node.task
            if task.status != TaskStatus.PENDING.value:
                continue

            deps_completed = all(
                self.nodes[dep_id].task.status
                in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value)
                for dep_id in node.dependencies
                if dep_id in self.nodes
            )

            if deps_completed:
                ready.append(task)
                if len(ready) >= max_count:
                    break
        return ready

    def mark_completed(self, task_id: str) -> List[str]:
        if task_id not in self.nodes:
            return []

        self.nodes[task_id].task.status = TaskStatus.DONE.value
        unblocked: List[str] = []
        for dependent_id in self.nodes[task_id].dependents:
            dependent_node = self.nodes[dependent_id]
            if dependent_node.task.status == TaskStatus.BLOCKED.value:
                all_deps_done = all(
                    self.nodes[dep_id].task.status
                    in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value)
                    for dep_id in dependent_node.dependencies
                )
                if all_deps_done:
                    dependent_node.task.status = TaskStatus.PENDING.value
                    unblocked.append(dependent_id)
        return unblocked

    def mark_skipped(self, task_id: str) -> List[str]:
        if task_id not in self.nodes:
            return []

        self.nodes[task_id].task.status = TaskStatus.SKIPPED.value
        unblocked: List[str] = []
        for dependent_id in self.nodes[task_id].dependents:
            dependent_node = self.nodes[dependent_id]
            if dependent_node.task.status == TaskStatus.BLOCKED.value:
                all_deps_done = all(
                    self.nodes[dep_id].task.status
                    in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value)
                    for dep_id in dependent_node.dependencies
                )
                if all_deps_done:
                    dependent_node.task.status = TaskStatus.PENDING.value
                    unblocked.append(dependent_id)
        return unblocked

    def reset_task(self, task_id: str) -> None:
        if task_id not in self.nodes:
            return
        self.nodes[task_id].task.status = TaskStatus.PENDING.value

    def mark_failed(self, task_id: str) -> List[str]:
        if task_id not in self.nodes:
            return []

        self.nodes[task_id].task.status = TaskStatus.FAILED.value
        blocked: List[str] = []
        for dependent_id in self.nodes[task_id].dependents:
            dependent_node = self.nodes[dependent_id]
            if dependent_node.task.status == TaskStatus.PENDING.value:
                dependent_node.task.status = TaskStatus.BLOCKED.value
                blocked.append(dependent_id)
        return blocked

    def is_all_done(self) -> bool:
        return all(
            node.task.status
            in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value)
            for node in self.nodes.values()
        )

    def has_failed(self) -> bool:
        return any(
            node.task.status == TaskStatus.FAILED.value
            for node in self.nodes.values()
        )


__all__ = ["TaskScheduler", "TaskNode"]
