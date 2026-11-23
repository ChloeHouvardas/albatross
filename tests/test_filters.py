import pytest

from filters import is_summer_2027, is_target_role, location_label, matches
from jobs import Job


def job(title, locs=(), extra=""):
    return Job("t", "Co", "1", title, "https://x", list(locs), extra=extra)


@pytest.mark.parametrize("title", [
    "Software Engineer Intern (Summer 2027)",
    "Software Engineer, Internship - Infrastructure",
    "Quantitative Trader Intern",
    "Campus Quantitative Researcher, UG/MS (Intern)",
    "iOS Engineer Intern",
    "Site Reliability Engineering Co-op",
    "2027 Summer Analyst - Technology",
    "Security Engineering Intern - 2027",
    "2027 Flight Software Engineer Intern",
    "Stagiaire en développement de logiciels (été 2027) / Software Developer Intern",
    "Machine Learning Engineer Intern - Summer 2027",
])
def test_target_roles(title):
    assert is_target_role(title), title


@pytest.mark.parametrize("title", [
    "Mechanical Engineering Intern",
    "Marketing Intern",
    "Software Engineer Intern, PhD",
    "MBA Summer Associate",
    "Senior Software Engineer",
    "Software Engineer",  # not an internship
    "Recruiting Coordinator Intern",
    "2027 Flight Test Engineer Intern",
    "ASIC Engineer Intern",
    "Product Design Intern",
])
def test_non_target_roles(title):
    assert not is_target_role(title), title


@pytest.mark.parametrize("title,ok", [
    ("Software Engineer Intern (Summer 2027)", True),
    ("Software Engineer Intern", True),
    ("Software Engineer Intern (Fall 2026)", False),
    ("Software Engineer Co-op (Winter 2027)", False),
    ("Spring/Summer 2027 Software Co-Op", True),
    ("Software Engineer Intern 2026", False),
    ("2028 Summer Analyst - Technology", False),
])
def test_term(title, ok):
    assert is_summer_2027(job(title)) is ok


@pytest.mark.parametrize("locs,label", [
    (["Toronto, ON"], "🔥 TOR"),
    (["Montréal, Quebec, Canada"], "🔥 MTL"),
    (["Waterloo, ON"], "🍁 Canada"),
    (["New York, NY"], "🇺🇸 US"),
    (["Mountain View, CA, USA"], "🇺🇸 US"),
    (["Seattle, Washington, USA"], "🇺🇸 US"),
    (["Boston, MA"], "🇺🇸 US"),
    (["Austin, TX"], None),
    (["London, United Kingdom"], None),
    (["Costa Rica, San Jose"], None),
    (["Austin, TX", "Toronto, Canada"], "🔥 TOR"),
    ([], "❔"),
    (["Remote"], "🌐 Remote"),
])
def test_location(locs, label):
    assert location_label(job("x", locs)) == label


def test_matches_end_to_end():
    assert matches(job("Software Engineer Intern (Summer 2027)", ["Toronto"])) == "🔥 TOR"
    assert matches(job("Software Engineer Intern (Summer 2027)", ["Austin, TX"])) is None
    assert matches(job("Marketing Intern", ["Toronto"])) is None
