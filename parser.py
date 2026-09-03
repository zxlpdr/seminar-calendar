from __future__ import annotations

import html
import re
from datetime import date, timedelta

from models import Resource, Seminar


def _normalise(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\\([@~#*_])", r"\1", text)
    text = text.replace("\u3000", " ")
    return text.strip()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = re.sub(r"\s+", "", value).lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _clean_company(value: str) -> str:
    value = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", value)
    value = re.sub(r"(?:股份有限公司|有限责任公司|有限公司)$", "", value)
    value = value.strip(" -—·丨|：:，,。！!（）()[]【】")
    return value


def extract_company(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title_candidate = ""

    for line in lines[:12]:
        if "宣讲" not in line:
            continue
        cleaned = re.sub(r"^\s*(?:\[[^\]]+\]|【[^】]+】)\s*", "", line)
        cleaned = re.sub(r"^[^A-Za-z0-9\u4e00-\u9fff]+", "", cleaned)
        cleaned = re.sub(r"^加入我们[，,]?", "", cleaned)
        prefix = re.split(
            r"20\d{2}(?:届|年)|(?:秋季|春季)?校园招聘|招聘宣讲会|宣讲会|空中宣讲",
            cleaned,
            maxsplit=1,
        )[0]
        prefix = re.split(r"[-—]\s*(?:大连理工大学|大工)", prefix, maxsplit=1)[0]
        prefix = _clean_company(prefix)
        if 2 <= len(prefix) <= 30 and not any(
            word in prefix for word in ("时间", "地点", "今晚", "明天", "通知")
        ):
            title_candidate = prefix
            break

    legal_entities: list[str] = []
    entity_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fff·（）()]{2,32}?(?:股份有限公司|有限责任公司|有限公司))"
    )
    for line in lines:
        for match in entity_pattern.finditer(line):
            entity = _clean_company(match.group(1))
            if 2 <= len(entity) <= 30:
                legal_entities.append(entity)

    if title_candidate:
        for entity in legal_entities:
            if entity.startswith(title_candidate) or title_candidate.startswith(entity):
                return entity if len(entity) >= len(title_candidate) else title_candidate
        return title_candidate
    if legal_entities:
        return legal_entities[0]
    return ""


def infer_future_date(month: int, day: int, reference_date: date) -> date | None:
    """Resolve a yearless month/day to its next occurrence, including today."""
    for year in range(reference_date.year, reference_date.year + 9):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= reference_date:
            return candidate
    return None


def extract_date(text: str, reference_date: date) -> date | None:
    explicit_chinese = re.search(
        r"(?<!\d)(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text
    )
    explicit_numeric = re.search(
        r"(?<!\d)(20\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})(?!\d)", text
    )
    explicit = explicit_chinese or explicit_numeric
    if explicit:
        try:
            return date(
                int(explicit.group(1)),
                int(explicit.group(2)),
                int(explicit.group(3)),
            )
        except ValueError:
            return None

    month_day = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if month_day:
        return infer_future_date(
            int(month_day.group(1)), int(month_day.group(2)), reference_date
        )

    if re.search(r"后天|后晚", text):
        return reference_date + timedelta(days=2)
    if re.search(r"明天|明晚|明日下午|明日上午", text):
        return reference_date + timedelta(days=1)
    if re.search(r"今天|今晚|今早|今晨|今日", text):
        return reference_date
    return None


def _format_time(hour: int, minute: int, context: str) -> str:
    if re.search(r"下午|晚上|今晚|傍晚", context) and 1 <= hour < 12:
        hour += 12
    if "中午" in context and 1 <= hour < 11:
        hour += 12
    if hour > 23 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def extract_times(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    preferred = [
        line
        for line in lines
        if re.search(r"宣讲时间|(?:^|[🕒⏰\s])时间\s*[：:]|今晚|明晚|今天|明天|上午|下午|晚上", line)
        and "工作时间" not in line
    ]
    candidates = preferred + [line for line in lines[:8] if line not in preferred]
    range_pattern = re.compile(
        r"(?<!\d)(\d{1,2})\s*[：:]\s*(\d{2})\s*(?:[-—–~～至到])\s*"
        r"(\d{1,2})\s*[：:]\s*(\d{2})(?!\d)"
    )
    single_pattern = re.compile(r"(?<!\d)(\d{1,2})\s*[：:]\s*(\d{2})(?!\d)")

    for line in candidates:
        match = range_pattern.search(line)
        if match:
            start = _format_time(int(match.group(1)), int(match.group(2)), line[: match.start() + 1])
            end = _format_time(int(match.group(3)), int(match.group(4)), line[: match.start() + 1])
            return start, end
    for line in candidates:
        match = single_pattern.search(line)
        if match:
            return _format_time(int(match.group(1)), int(match.group(2)), line), ""
    return "", ""


def extract_meetings(text: str) -> list[str]:
    pattern = re.compile(
        r"腾讯会议\s*[：:#]?\s*(?:会议号\s*[：:]?\s*)?"
        r"(\d{3}[\s-]\d{3}[\s-]\d{3})",
        re.IGNORECASE,
    )
    meetings = [re.sub(r"\s", "-", match.group(1)) for match in pattern.finditer(text)]
    return _unique(meetings)


def _clean_location(value: str) -> str:
    value = re.sub(r"^[#\s]+", "", value)
    value = re.sub(r"^大连理工大学\s*", "", value)
    value = re.sub(r"[👈👉📍]+", "", value)
    value = value.strip(" \t，,。；;！!")
    return value


def extract_location(text: str, meetings: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.search(r"工作地点", line):
            continue
        match = re.search(r"(?:宣讲地点|举办地点|会议地点|(?<!工作)地点)\s*[：:]\s*(.*)", line)
        if not match:
            continue
        value = _clean_location(match.group(1))
        if value:
            return value
        for following in lines[index + 1 : index + 4]:
            if re.search(r"工作地点|招聘对象|招聘岗位|简历投递", following):
                break
            meeting_match = re.search(r"腾讯会议\s*[：:]\s*([\d-]+)", following)
            if meeting_match:
                return f"腾讯会议：{meeting_match.group(1)}"
            candidate = _clean_location(following)
            if candidate:
                return candidate

    for block in re.findall(r"【([^】]+)】", text):
        if not re.search(r"\d{1,2}\s*[：:]\s*\d{2}", block):
            continue
        candidate = re.sub(r"\d{1,2}\s*[：:]\s*\d{2}", " ", block)
        candidate = re.sub(r"今天|今晚|明天|明晚|后天|上午|下午|晚上", " ", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" -—，,：:")
        if candidate:
            return _clean_location(candidate)

    if meetings:
        return f"腾讯会议：{meetings[0]}"
    return ""


def _url_label(context: str) -> str:
    labels = (
        ("专属宣讲群链接", "群链接"),
        ("宣讲群链接", "群链接"),
        ("群链接", "群链接"),
        ("立即网申", "网申"),
        ("校招官微", "校招官微"),
        ("投递链接", "投递链接"),
        ("网申", "网申"),
        ("校招官网", "校招官网"),
        ("官网", "官网"),
    )
    best_label = "链接"
    best_position = -1
    for keyword, label in labels:
        position = context.rfind(keyword)
        if position > best_position:
            best_position = position
            best_label = label
    return best_label


def extract_applications(text: str) -> list[Resource]:
    resources: list[Resource] = []
    seen_values: set[str] = set()

    url_pattern = re.compile(r"https?://[^\s\])）>]+", re.IGNORECASE)
    for match in url_pattern.finditer(text):
        url = match.group(0).rstrip(".,，。；;！!")
        if url in seen_values:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        context = text[line_start : match.start()]
        resources.append(Resource(_url_label(context), url))
        seen_values.add(url)

    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    for match in email_pattern.finditer(text):
        email = match.group(0)
        if email.lower() not in {value.lower() for value in seen_values}:
            resources.append(Resource("邮箱", email))
            seen_values.add(email)

    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        contact = re.search(r"联系人\s*[：:]\s*(.+)", stripped)
        if contact:
            resources.append(Resource("联系人", contact.group(1).strip()))
        if "公众号" in stripped and not re.search(r"https?://", stripped):
            account = re.search(r"(?:微信公众号|公众号)[^【\n]*【([^】]+)】", stripped)
            if not account:
                account = re.search(r"(?:微信公众号|公众号)[“\"]([^”\"]+)[”\"]", stripped)
            if account:
                resources.append(Resource("公众号", account.group(1).strip()))

    unique_resources: list[Resource] = []
    resource_keys: set[tuple[str, str]] = set()
    for resource in resources:
        key = (resource.label, resource.value.lower())
        if key not in resource_keys:
            resource_keys.add(key)
            unique_resources.append(resource)
    return unique_resources


def parse_seminar(text: str, reference_date: date | None = None) -> Seminar:
    reference_date = reference_date or date.today()
    normalised = _normalise(text)
    meetings = extract_meetings(normalised)
    start_time, end_time = extract_times(normalised)
    return Seminar(
        company=extract_company(normalised),
        event_date=extract_date(normalised, reference_date),
        start_time=start_time,
        end_time=end_time,
        location=extract_location(normalised, meetings),
        meetings=meetings,
        applications=extract_applications(normalised),
        source_text=normalised,
    )


def missing_required_fields(seminar: Seminar) -> list[str]:
    fields = (
        ("企业", seminar.company),
        ("日期", seminar.event_date),
        ("开始时间", seminar.start_time),
        ("地点", seminar.location),
    )
    return [name for name, value in fields if not value]
