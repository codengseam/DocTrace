from pathlib import Path
from typing import Annotated, Dict, List

from typing_extensions import TypedDict


def dict_merge(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    return {**old, **new}


class AgentState(TypedDict):
    book: str
    chapter: str
    event: str
    archetype: str
    user_input: str
    output_path: str
    sections: Annotated[Dict[str, str], dict_merge]
    sources: Annotated[Dict[str, List[str]], dict_merge]
    final_markdown: str
    errors: Annotated[List[str], lambda a, b: a + b]
