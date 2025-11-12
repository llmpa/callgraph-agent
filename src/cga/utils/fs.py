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
    def read_file_with_lines(self, 
                             path: str, 
                             start_line: int, 
                             end_line: int, 
                             with_linenum: bool = False,
                             omitted_lines: str = "") -> str:
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
    
def parse_omitted_lines(omitted_lines: str) -> set[int]:
    """
    Parse omitted lines string into a set of line numbers.
    
    Args:
        omitted_lines: String in the format "5-10,15-20"
    
    Returns:
        Set of omitted line numbers
    """
    omitted_set = set()
    if not omitted_lines:
        return omitted_set

    ranges = omitted_lines.split(',')
    for r in ranges:
        if '-' in r:
            start, end = r.split('-')
            omitted_set.update(range(int(start), int(end) + 1))
        else:
            omitted_set.add(int(r))
    return omitted_set
    
def omit_lines(lines: list[tuple[int, str]], omitted_lines: set[int]) -> list[tuple[int, str]]:
    """
    Omit specified lines from the list of lines.
    And insert omitted lines info [omitted lines: xxx-xxx] for continuous omitted lines.
    
    Args:
        lines: List of tuples (line_number, line_content)
        omitted_lines: Set of line numbers to omit

    Returns:
        List of tuples with specified lines omitted
    """
    result = []
    omitted_lines = sorted(omitted_lines)
    omitted_ranges = []
    if not omitted_lines:
        return lines

    # Identify continuous ranges
    start = omitted_lines[0]
    end = omitted_lines[0]
    for line in omitted_lines[1:]:
        if line == end + 1:
            end = line
        else:
            omitted_ranges.append((start, end))
            start = line
            end = line
    omitted_ranges.append((start, end))

    omitted_idx = 0
    current_range = omitted_ranges[omitted_idx] if omitted_ranges else None
    i = 0
    while i < len(lines):
        line_num, line_content = lines[i]
        if current_range and current_range[0] <= line_num <= current_range[1]:
            # Skip this line
            if line_num == current_range[1]:
                # Insert omitted lines info
                if current_range[0] == current_range[1]:
                    result.append((-1, f"[omitted lines: {current_range[0]}]"))
                else:
                    result.append((-1, f"[omitted lines: {current_range[0]}-{current_range[1]}]"))
                omitted_idx += 1
                current_range = omitted_ranges[omitted_idx] if omitted_idx < len(omitted_ranges) else None
            i += 1
        else:
            result.append((line_num, line_content))
            i += 1

    return result



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

    def read_file_with_lines(self, path: str, start_line: int, end_line: int, with_linenum: bool = False, omitted_lines: str = "") -> str:
        path = os.path.abspath(path)
        content = self.read_file(path)
        lines = content.splitlines()

        try:
            selected_lines = [(i+1, lines[i]) for i in range(start_line-1, end_line)]
            if omitted_lines:
                omitted_set = parse_omitted_lines(omitted_lines)
                selected_lines = omit_lines(selected_lines, omitted_set)
            if with_linenum:
                str_lines = []
                for line_num, line_content in selected_lines:
                    if line_num == -1:
                        str_lines.append(line_content)
                    else:
                        str_lines.append(f"{line_num}: {line_content}")
                return '\n'.join(str_lines)
            return '\n'.join([line_content for _, line_content in selected_lines])
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