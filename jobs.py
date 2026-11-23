from dataclasses import dataclass, field
import re


@dataclass
class Job:
    source: str          # e.g. "greenhouse", "simplify"
    company: str
    native_id: str
    title: str
    url: str
    locations: list[str] = field(default_factory=list)
    posted: int | None = None  # unix ts if known
    extra: str = ""      # extra text for term detection (e.g. terms field)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.company}:{self.native_id}"

    @property
    def location_text(self) -> str:
        return " / ".join(l for l in self.locations if l)


def norm_url(url: str) -> str:
    url = url.strip().split("#")[0]
    url = re.sub(r"[?&](utm_[^=&]+|ref|source|gh_src|lever-source[^=&]*)=[^&]*", "", url)
    url = url.rstrip("?&/")
    return url.lower()
