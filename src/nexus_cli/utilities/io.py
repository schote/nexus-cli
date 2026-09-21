"""File I/O helpers for Nexus acquisition data."""
from pathlib import Path

import ismrmrd


def load_mrd_header(header_path: Path) -> ismrmrd.xsd.ismrmrdHeader:
    """Load and parse an ISMRMRD XML header from an HDF5 dataset file.

    Opens the ISMRMRD dataset at `header_path`, reads the raw XML header string,
    and parses it into a structured `ismrmrdHeader` object that can be passed to
    `AcquisitionData.save_ismrmrd()`.

    Args:
        header_path: Path to an ISMRMRD `.xml` header file.

    Returns:
        A parsed `ismrmrd.xsd.ismrmrdHeader` object.

    """
    dataset = ismrmrd.Dataset(header_path, 'w')
    xml_header = dataset.read_xml_header()
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
