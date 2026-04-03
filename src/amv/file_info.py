from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    ed2k: str
    watched: bool
    internal: bool
    view_date: float
    id: int | None = field(default=None, compare=False)
