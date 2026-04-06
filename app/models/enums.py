from __future__ import annotations

from enum import Enum


class TrainingMode(str, Enum):
    delivery_training = "delivery_training"
    structure_training = "structure_training"
    behavioral_training = "behavioral_training"


class AttemptStatus(str, Enum):
    active = "active"
    completed = "completed"