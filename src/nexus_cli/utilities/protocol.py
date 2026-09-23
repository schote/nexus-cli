"""Protocol definition, a sequence of measurement and pause steps loaded from file."""
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field


class SequenceStep(BaseModel):
    """Protocol step which runs a sequence file and exports the data with the given header."""

    type: Literal["sequence"]
    sequence: Path
    header: Path


class PauseStep(BaseModel):
    """Protocol step which pauses the protocol for a given duration in seconds."""

    type: Literal["pause"]
    duration: float | None = None   # None = wait for user
    message: str | None = None


Step = Annotated[Union[SequenceStep, PauseStep], Field(discriminator="type")]


class Protocol(BaseModel):
    """Named list of protocol steps which are executed in order."""

    name: str
    version: int = 1
    steps: list[Step]

    @classmethod
    def load(cls, path: str | Path) -> "Protocol":
        """Load and validate a protocol file.

        Relative sequence and header paths are resolved against the directory of the protocol file.

        Parameters
        ----------
        path
            Path to the protocol file (json or yaml).

        Returns
        -------
            Validated protocol.

        """
        path = Path(path)
        data = yaml.safe_load(path.read_text())
        protocol = cls.model_validate(data)
        # Resolve relative paths against the protocol file's directory
        for step in protocol.steps:
            if isinstance(step, SequenceStep):
                step.sequence = (path.parent / step.sequence).resolve()
                step.header = (path.parent / step.header).resolve()
        return protocol
