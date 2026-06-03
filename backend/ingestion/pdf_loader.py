import logging
from pathlib import Path
from typing import List, Union

# Configure basic logging for the ingestion module
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class PDFLoader:
    """
    A production-grade component responsible for discovering, validating,
    and managing local PDF file paths.
    """

    def __init__(self, default_directory: Union[str, Path] = "backend/datasets/raw_pdfs") -> None:
        """
        Initializes the PDFLoader with a default directory for PDF discovery.

        Args:
            default_directory (Union[str, Path]): Default folder path to scan for PDFs.
        """
        self.default_directory = Path(default_directory).resolve()

    def load_from_directory(self, directory_path: Union[str, Path, None] = None) -> List[Path]:
        """
        Scans a directory for files with a '.pdf' extension (case-insensitive) 
        and returns their resolved absolute paths.

        Args:
            directory_path (Union[str, Path], optional): Directory path to scan.
                If None, defaults to self.default_directory.

        Returns:
            List[Path]: A sorted list of resolved absolute Path objects to the discovered PDF files.

        Raises:
            FileNotFoundError: If the target directory does not exist.
            NotADirectoryError: If the target path is not a directory.
        """
        target_dir = Path(directory_path).resolve() if directory_path else self.default_directory

        if not target_dir.exists():
            raise FileNotFoundError(f"Target directory does not exist: {target_dir}")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"Target path is not a directory: {target_dir}")

        pdf_paths: List[Path] = []
        for file_path in target_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == ".pdf":
                pdf_paths.append(file_path.resolve())

        logger.info(f"Discovered {len(pdf_paths)} PDF(s) in directory: {target_dir}")
        return sorted(pdf_paths)

    def load_specific_files(self, file_paths: List[Union[str, Path]]) -> List[Path]:
        """
        Validates and returns resolved absolute paths for a specific list of PDF files.

        Args:
            file_paths (List[Union[str, Path]]): List of explicit file paths to load.

        Returns:
            List[Path]: A list of validated, resolved absolute Path objects.

        Raises:
            FileNotFoundError: If any of the specified files do not exist.
            ValueError: If any file path is not a file or does not have a '.pdf' extension.
        """
        resolved_paths: List[Path] = []
        for path_entry in file_paths:
            path = Path(path_entry).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Specified PDF file does not exist: {path}")
            if not path.is_file():
                raise ValueError(f"Specified path is not a file: {path}")
            if path.suffix.lower() != ".pdf":
                raise ValueError(f"File is not a PDF (missing/invalid extension): {path}")
            resolved_paths.append(path)

        logger.info(f"Successfully validated {len(resolved_paths)} specific PDF file(s).")
        return resolved_paths


# Example usage block
if __name__ == "__main__":
    loader = PDFLoader()
    print(f"Default target directory: {loader.default_directory}")
    try:
        pdfs = loader.load_from_directory()
        print(f"Loaded PDFs: {pdfs}")
    except Exception as e:
        print(f"Directory load failed: {e}")
