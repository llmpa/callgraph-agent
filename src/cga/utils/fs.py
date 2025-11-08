from abc import ABC, abstractmethod
import os

from pydantic import BaseModel

class FileMetadata(BaseModel):
    lines: int

class FileSystem(ABC):
    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    def read_file_with_lines(self, path: str, start_line: int, end_line: int, with_linenum: bool = False) -> str:
        pass
    
    @abstractmethod
    def get_file_metadata(self, path: str) -> FileMetadata:
        pass

    @abstractmethod
    def write_file(self, path: str, content: str, in_memory: bool = False) -> None:
        pass

    @abstractmethod
    def list_files(self, directory: str) -> list[str]:
        pass

    @abstractmethod
    def add_white_list(self, path: str) -> None:
        pass
    




class CachedLocalFileSystem(FileSystem):
    def __init__(self):
        self._cache: dict[str, str] = {}

        ## white list of file paths
        self._white_list = set()

    def read_file(self, path: str) -> str:
        path = os.path.abspath(path)
        if path in self._cache:
            return self._cache[path]
        
        with open(path, 'r') as f:
            content = f.read()
            self._cache[path] = content
            return content

    def read_file_with_lines(self, path: str, start_line: int, end_line: int, with_linenum: bool = False) -> str:
        path = os.path.abspath(path)
        content = self.read_file(path)
        lines = content.splitlines()

        try:
            if with_linenum:
                return '\n'.join([f"{i+1}: {lines[i]}" for i in range(start_line-1, end_line)])
            return '\n'.join(lines[start_line-1:end_line])
        except Exception as e:
            raise ValueError(f"Error reading lines {start_line}-{end_line} from file {path} ({len(lines)} lines): {e}")

    def write_file(self, path: str, content: str, in_memory: bool = False) -> None:
        path = os.path.abspath(path)
        if not in_memory:
            with open(path, 'w') as f:
                f.write(content)
        self._cache[path] = content

    def add_white_list(self, path: str) -> None:
        path = os.path.abspath(path)
        self._white_list.add(path)

    def _is_in_white_list(self, path: str) -> bool:
        """
        Check if a file path is in the white list.
        
        """
        if self._white_list:
            for white_path in self._white_list:
                if path.startswith(white_path):
                    return True
            return False
        return True

    def list_files(self, directory: str) -> list[str]:
        # make sure directory is absolute path
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            # If it's a file, just return the file itself
            return [directory]
        return [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and self._is_in_white_list(os.path.join(directory, f))]
    
    def get_file_metadata(self, path: str) -> FileMetadata:
        path = os.path.abspath(path)
        content = self.read_file(path)
        lines = content.splitlines()
        return FileMetadata(lines=len(lines))