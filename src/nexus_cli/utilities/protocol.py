from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field


class SequenceStep(BaseModel):
    type: Literal["sequence"]
    sequence: Path
    header: Path


class PauseStep(BaseModel):
    type: Literal["pause"]
    duration: float | None = None   # None = wait for user
    message: str | None = None


Step = Annotated[Union[SequenceStep, PauseStep], Field(discriminator="type")]


class Protocol(BaseModel):
    name: str
    version: int = 1
    steps: list[Step]

    @classmethod
    def load(cls, path: str | Path) -> "Protocol":
        path = Path(path)
        data = yaml.safe_load(path.read_text())
        protocol = cls.model_validate(data)
        # Resolve relative paths against the protocol file's directory
        for step in protocol.steps:
            if isinstance(step, SequenceStep):
                step.sequence = (path.parent / step.sequence).resolve()
                step.header = (path.parent / step.header).resolve()
        return protocol
