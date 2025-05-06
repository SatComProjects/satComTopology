import html
import re
from typing import Any

from pydantic import BaseModel


def _snake_to_title(key: str) -> str:
    return re.sub(r"_+", " ", key).title()


class HtmlFormatter:
    """
    Html formatter
    """

    def __init__(self, model: BaseModel):
        self.model = model

    def format(self) -> str:
        return self._format_dict(self.model.model_dump())

    def _format_dict(self, data: dict, level: int = 0) -> str:
        html_output = "<table border='1' style='border-collapse: collapse;'>"
        for key, value in data.items():
            readable_key = _snake_to_title(str(key))
            html_output += "<tr>"
            html_output += f"<td style='padding: 4px;'><b>{html.escape(str(readable_key))}</b></td>"
            html_output += "<td style='padding: 4px;'>"
            html_output += self._format_value(value, level + 1)
            html_output += "</td></tr>"
        html_output += "</table>"
        return html_output

    def _format_value(self, value: Any, level: int) -> str:
        if isinstance(value, dict):
            return self._format_dict(value, level)
        elif isinstance(value, list):
            return (
                "<ul>"
                + "".join(f"<li>{self._format_value(v, level)}</li>" for v in value)
                + "</ul>"
            )
        else:
            return html.escape(str(value))
