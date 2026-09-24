"""Protocol definition, a sequence of measurement and pause steps loaded from file."""
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from nexus_service.acquisition_manager import AcquisitionControlManager, NexusNotRunningError
from pydantic import BaseModel, Field
from pypulseq import Opts, Sequence
from rich.table import Table


class SequenceStep(BaseModel):
    """Protocol step which runs a sequence file and exports the data with the given header."""

    type: Literal["sequence"]
    sequence: Path
    header: Path
    duration: float | None = Field(default=None, exclude=True)  # Set on load, in seconds


class PauseStep(BaseModel):
    """Protocol step which pauses the protocol for a given duration in seconds."""

    type: Literal["pause"]
    duration: float | None = None   # None = wait for user
    message: str | None = None


Step = Annotated[Union[SequenceStep, PauseStep], Field(discriminator="type")]


def _get_sequence_system() -> Opts:
    """Return the sequence system of the running Nexus service, or the pypulseq default if unavailable."""
    try:
        with AcquisitionControlManager() as m:
            return m.acquisition.get_sequence_system()
    except NexusNotRunningError:
        return Opts.default


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as `[h:]mm:ss.s`."""
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:04.1f}"
    return f"{minutes:02d}:{sec:04.1f}"


class Protocol(BaseModel):
    """Named list of protocol steps which are executed in order."""

    name: str
    version: int = 1
    steps: list[Step]

    @classmethod
    def load(cls, path: str | Path) -> "Protocol":
        """Load and validate a protocol file.

        Relative sequence and header paths are resolved against the directory of the protocol file.
        Each sequence is read with the sequence system of the running Nexus service (pypulseq default
        if the service is not running) to determine its duration.

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
        system = _get_sequence_system()
        # Resolve relative paths against the protocol file's directory
        for step in protocol.steps:
            if isinstance(step, SequenceStep):
                step.sequence = (path.parent / step.sequence).resolve()
                step.header = (path.parent / step.header).resolve()
                seq = Sequence(system=system)
                seq.read(step.sequence)
                step.duration = seq.duration()[0]
        return protocol

    def __rich__(self) -> Table:
        """Render the protocol as rich table, used by `rich.print(protocol)` and `Console.print`."""
        total = sum(step.duration or 0.0 for step in self.steps)
        waits_for_user = any(isinstance(step, PauseStep) and step.duration is None for step in self.steps)
        total_str = _format_duration(total) + (" [yellow]+ user[/yellow]" if waits_for_user else "")

        table = Table(
            title=f"\n[bold]{self.name}[/bold] [dim](v{self.version})[/dim]",
            title_justify="left",
            show_footer=True,
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("Step", footer="Total")
        table.add_column("Details")
        table.add_column("Duration", justify="right", footer=total_str)

        for i, step in enumerate(self.steps, start=1):
            match step:
                case SequenceStep():
                    details = f"{step.sequence.name}\n[dim]header: {step.header.name}[/dim]"
                    duration = _format_duration(step.duration) if step.duration is not None else "[dim]n/a[/dim]"
                    table.add_row(str(i), "[cyan]Sequence[/cyan]", details, duration)
                case PauseStep():
                    duration = _format_duration(step.duration) if step.duration is not None else "[yellow]user[/yellow]"
                    table.add_row(str(i), "[magenta]Pause[/magenta]", f"[italic]{step.message or ''}[/italic]", duration)
        return table
