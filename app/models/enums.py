from __future__ import annotations

from enum import Enum


class TrainingMode(str, Enum):
    structure_training = "structure_training"
    behavioral_training = "behavioral_training"


class AttemptStatus(str, Enum):
    active = "active"
    completed = "completed"

class AttemptStage(str, Enum):
    INITIAL = "initial"
    TRAINING = "training"
    FINAL = "final"
