from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Step:
    name: str
    run: Optional[str] = None
    timeout: Optional[str] = None
    retries: int = 0
    depends_on: List[str] = field(default_factory=list)
    on_error: Optional[str] = None


@dataclass
class Notify:
    name: str
    email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


@dataclass
class Workflow:
    name: str
    triggers: List[str]
    env: dict
    steps: List[Step]
    notifies: List[Notify]