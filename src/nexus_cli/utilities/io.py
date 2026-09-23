"""File I/O helpers for Nexus acquisition data."""
from pathlib import Path

import ismrmrd


def load_mrd_header(header_path: Path) -> ismrmrd.xsd.ismrmrdHeader:
    """Load and parse an ISMRMRD XML header file.

    Reads the raw XML header string from `header_path` and parses it into a
    structured `ismrmrdHeader` object that can be passed to
    `AcquisitionData.save_ismrmrd()`.

    Parameters
    ----------
    header_path
        Path to an ISMRMRD `.xml` header file.

    Returns
    -------
        A parsed `ismrmrd.xsd.ismrmrdHeader` object.

    """
    xml_header = Path(header_path).read_text()
    header = ismrmrd.xsd.CreateFromDocument(xml_header)
    return header

def ensure_valid_seq_file(path: Path) -> None:
    """Ensure that sequence file is valid.

    Parameters
    ----------
    path
        Path to sequence file

    Raises
    ------
    ValueError
        Invalid file suffix.

    """
    if path.suffix != ".seq":
        raise ValueError("Invalid sequence file, `.seq` file required.")

def ensure_valid_header_file(path: Path) -> None:
    """Ensure that ismrmrd header file is valid.

    Parameters
    ----------
    path
        Path to header file

    Raises
    ------
    ValueError
        Invalid file suffix.

    """
    if path.suffix != ".xml":
        raise ValueError("Invalid header file, `.xml` file required.")
