"""Matching rules for company career pages (PRD: 'What counts as a match')."""
import re

from jobs import Job

INTERN = re.compile(r"\bintern(ship)?s?\b|\bco-?op\b|\bsummer (analyst|engineer|developer|internship)\b|\bstagiaire\b|\bstage\b", re.I)
TECH = re.compile(
    r"software|\bswe\b|\bsde\b|developer|\bdev\b|back-?\s?end|front-?\s?end|full-?\s?stack|mobile|\bios\b|android|"
    r"infrastructure|platform|devops|\bsre\b|reliability|security|cyber|quant|trad(ing|er)|technology|"
    r"machine learning|\bml\b|\bai\b|tools engineer|data engineer|systems|cloud|compiler|programm|computer science|"
    r"production engineer|forward deployed|research engineer|engineering intern|\bintern(ship)?,? engineering|"
    r"\bengineer(ing)? (intern|co-?op)|technical (intern|program)|technology (analyst|intern|program)|\bit\b", re.I)
EXCLUDE = re.compile(
    r"\bph\.?d\b|doctoral|high school|\bmba\b|mechanical|electrical|civil|chemical|manufactur|hardware|industrial|mechatronic|"
    r"marketing|\bsales\b|human resources|\bhr\b|recruit|talent|people ops|account(ing|ant)|legal|counsel|"
    r"\bdesign(er)?\b(?! engineer)|product manag|program manag|business (analyst|develop)|communications|"
    r"\bfinance\b(?! tech)|audit|tax\b|supply chain|procurement|operations intern|clinical|nurs|pharma|"
    r"facilities|construction|environmental|aerospace|propulsion|avionics|structural|materials|"
    r"new grad|full[- ]time|senior|staff|principal|\bmanager\b|\blead\b|\bdirector\b|"
    r"flight (test|operations|sciences)|\btest engineer|quality|\bart\b|product design|people|asic|\brtl\b|silicon|analog|\brf\b|"
    r"power (integrity|electronics|management)|physical design|verification|validation|photonic|optical|"
    r"business operations engineer|operations engineering|investment banking|\bm&a\b|wealth|insurance|actuar", re.I)

OTHER_TERM = re.compile(r"\b(fall|autumn|winter|spring)\b|\b(automne|hiver|printemps)\b", re.I)
OLD_YEAR = re.compile(r"\b20(2[0-68-9])\b")
SUMMER = re.compile(r"\bsummer\b|\bété\b", re.I)


def is_target_role(title: str) -> bool:
    return bool(INTERN.search(title) and TECH.search(title) and not EXCLUDE.search(title))


def is_summer_2027(job: Job) -> bool:
    text = f"{job.title} {job.extra}"
    if "2027" in text:
        if OTHER_TERM.search(text) and not SUMMER.search(text):
            return False
        return True
    if OLD_YEAR.search(text):
        return False
    if OTHER_TERM.search(text) and not SUMMER.search(text):
        return False
    return True  # no term stated -> assume it could be summer 2027


HOT = {"TOR": ["toronto"], "VAN": ["vancouver"], "MTL": ["montreal", "montréal"]}
CANADA = re.compile(
    r"canada|\bontario\b|british columbia|qu[eé]bec|alberta|manitoba|saskatchewan|nova scotia|new brunswick|"
    r"waterloo|ottawa|calgary|edmonton|kitchener|mississauga|markham|burnaby|halifax|winnipeg|victoria, bc|"
    r"richmond hill|vaughan|oakville|guelph|hamilton, on|london, on|regina|saskatoon|laval|gatineau|"
    r",\s*(on|bc|qc|ab|mb|sk|ns|nb)\b|\bcan\b", re.I)
US = re.compile(
    r"new york|\bnyc\b|\bny\b|brooklyn|manhattan|jersey city|"
    r"california|\bca\b|san francisco|\bsf\b|bay area|palo alto|mountain view|menlo park|sunnyvale|san jose|"
    r"santa clara|cupertino|redwood city|san mateo|foster city|south san francisco|oakland|berkeley|emeryville|"
    r"san bruno|fremont|milpitas|los angeles|santa monica|culver city|playa vista|irvine|san diego|hawthorne|el segundo|"
    r"seattle|bellevue|redmond|kirkland|\bwa\b|washington state|"
    r"boston|cambridge, ma|\bma\b|massachusetts|somerville|waltham", re.I)
FOREIGN = re.compile(
    r"costa rica|mexico|brazil|argentina|colombia|chile|peru|india|china|japan|korea|taiwan|singapore|"
    r"hong kong|vietnam|philippines|malaysia|indonesia|thailand|australia|new zealand|israel|"
    r"united kingdom|\buk\b|england|london|ireland|dublin|germany|france|paris|spain|italy|netherlands|"
    r"amsterdam|poland|switzerland|zurich|sweden|denmark|norway|finland|belgium|austria|portugal|czech|"
    r"romania|hungary|greece|turkey|uae|dubai|saudi|egypt|south africa|nigeria|kenya|"
    r"\bbra\b|\bind\b|\bchn\b|\bjpn\b|\bgbr\b|\bdeu\b|\bfra\b|\bisr\b|\birl\b|\bsgp\b|\bmex\b|\bpol\b|\bcri\b", re.I)
GENERIC_US = re.compile(r"^(remote|united states|usa|us|u\.s\.|north america|remote[ ,-]+(us|usa|united states|north america|canada)?|anywhere|hybrid|multiple locations)$", re.I)


def location_label(job: Job) -> str | None:
    """Return a display label, or None if the role is outside target locations."""
    raw = [l.strip() for l in job.locations if l and l.strip()]
    if not raw:
        return "❔"
    locs = [l for l in raw if not FOREIGN.search(l)]
    if not locs:
        return None
    text = " / ".join(locs)
    hot = [k for k, names in HOT.items() if any(n in text.lower() for n in names)]
    if hot:
        return "🔥 " + "/".join(hot)
    if CANADA.search(text):
        return "🍁 Canada"
    if US.search(text):
        return "🇺🇸 US"
    if all(GENERIC_US.match(l) for l in locs):
        return "🌐 " + locs[0]
    return None


# #albatross-toronto: the three metros only (incl. suburbs), separate from the 🔥 labels above.
METRO = {
    "TOR": re.compile(r"toronto|mississauga|markham|north york|scarborough|etobicoke|vaughan|richmond hill|brampton", re.I),
    "VAN": re.compile(r"vancouver|burnaby|richmond,? bc|surrey,? bc|coquitlam", re.I),
    "MTL": re.compile(r"montr[eé]al|laval|longueuil|saint-laurent", re.I),
}


def metro_label(job: Job) -> str | None:
    text = " / ".join(l for l in job.locations if l and not FOREIGN.search(l))
    hit = [k for k, pat in METRO.items() if pat.search(text)]
    return "📍 " + "/".join(hit) if hit else None


def matches_metro(job: Job, intern_only: bool = False) -> str | None:
    """Label if this job belongs in #albatross-toronto. intern_only: source lists only internships."""
    title = job.title if not intern_only or INTERN.search(job.title) else job.title + " intern"
    if not is_target_role(title) or not is_summer_2027(job):
        return None
    return metro_label(job)


def matches(job: Job) -> str | None:
    """Label if this company-page job should alert, else None."""
    if not is_target_role(job.title) or not is_summer_2027(job):
        return None
    return location_label(job)
