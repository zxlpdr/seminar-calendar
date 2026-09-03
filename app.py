from __future__ import annotations

import re
import sys
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk
from typing import Callable

from database import SeminarDatabase
from models import Resource, Seminar
from parser import DEFAULT_EVENT_YEAR, missing_required_fields, parse_seminar


APP_TITLE = "宣讲会日历"
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
COLORS = {
    "background": "#F4F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "primary": "#3457D5",
    "primary_hover": "#2746B4",
    "text": "#172033",
    "muted": "#697386",
    "border": "#DDE3EC",
    "today": "#EAF0FF",
    "today_border": "#6681E8",
    "link": "#285BC7",
    "danger": "#C43B42",
    "warning": "#A35A00",
}
FONT_FAMILY = "Microsoft YaHei UI"


def centre_window(window: tk.Misc, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def normalise_time(value: str, required: bool = False) -> str:
    value = value.strip().replace("：", ":")
    if not value and not required:
        return ""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if not match:
        raise ValueError("时间请使用 HH:MM 格式，例如 18:00")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError("请输入有效时间")
    return f"{hour:02d}:{minute:02d}"


def parse_date_input(value: str) -> date:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日?", value)
    if match:
        try:
            return date(DEFAULT_EVENT_YEAR, int(match.group(1)), int(match.group(2)))
        except ValueError:
            pass
    raise ValueError("日期请使用 2026-09-04 或 9月4日 格式")


def application_to_line(resource: Resource) -> str:
    return f"{resource.label}：{resource.value}" if resource.label else resource.value


def parse_application_lines(text: str) -> list[Resource]:
    result: list[Resource] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([^：:]{1,16})[：:]\s*(.+)$", line)
        if match:
            label, value = match.group(1).strip(), match.group(2).strip()
        else:
            value = line
            if re.match(r"https?://", value, re.IGNORECASE):
                label = "链接"
            elif "@" in value:
                label = "邮箱"
            else:
                label = "信息"
        key = (label, value.lower())
        if key not in seen:
            seen.add(key)
            result.append(Resource(label, value))
    return result


def open_resource(resource: Resource) -> None:
    value = resource.value.strip()
    url_match = re.search(r"https?://\S+", value, re.IGNORECASE)
    if url_match:
        webbrowser.open(url_match.group(0).rstrip(".,，。；;"))
        return
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.IGNORECASE)
    if email_match:
        webbrowser.open(f"mailto:{email_match.group(0)}")


def is_clickable(resource: Resource) -> bool:
    return bool(re.search(r"https?://|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", resource.value, re.I))


class SeminarEditor(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        database: SeminarDatabase,
        on_saved: Callable[[], None],
        seminar: Seminar | None = None,
        import_mode: bool = False,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.on_saved = on_saved
        self.seminar = seminar or Seminar()
        self.import_mode = import_mode
        self.title("导入宣讲会" if import_mode else ("编辑宣讲会" if seminar else "手工录入"))
        self.configure(bg=COLORS["background"])
        self.minsize(760, 680 if import_mode else 580)
        centre_window(self, 900, 820 if import_mode else 680)
        self.transient(parent)

        self.company_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.warning_var = tk.StringVar()

        self._build()
        self._load_seminar(self.seminar)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()

    def _build(self) -> None:
        outer = tk.Frame(self, bg=COLORS["background"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)

        title = "粘贴并解析宣讲会消息" if self.import_mode else self.title()
        tk.Label(
            outer,
            text=title,
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        if self.import_mode:
            source_panel = tk.Frame(
                outer,
                bg=COLORS["surface"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            source_panel.pack(fill="x", pady=(0, 12))
            tk.Label(
                source_panel,
                text="原始消息（每次粘贴一场宣讲会）",
                bg=COLORS["surface"],
                fg=COLORS["text"],
                font=(FONT_FAMILY, 10, "bold"),
            ).pack(anchor="w")
            source_frame = tk.Frame(source_panel, bg=COLORS["surface"])
            source_frame.pack(fill="x", pady=(6, 8))
            self.source_text = tk.Text(
                source_frame,
                height=8,
                wrap="word",
                undo=True,
                font=(FONT_FAMILY, 10),
                relief="solid",
                borderwidth=1,
            )
            source_scroll = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_text.yview)
            self.source_text.configure(yscrollcommand=source_scroll.set)
            self.source_text.pack(side="left", fill="both", expand=True)
            source_scroll.pack(side="right", fill="y")
            tk.Button(
                source_panel,
                text="解析消息",
                command=self._parse_source,
                bg=COLORS["primary"],
                fg="white",
                activebackground=COLORS["primary_hover"],
                activeforeground="white",
                relief="flat",
                padx=18,
                pady=6,
                font=(FONT_FAMILY, 10, "bold"),
                cursor="hand2",
            ).pack(anchor="e")
        else:
            self.source_text = None

        panel = tk.Frame(
            outer,
            bg=COLORS["surface"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        panel.pack(fill="both", expand=True)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_columnconfigure(3, weight=1)

        self._entry_row(panel, 0, "企业 *", self.company_var, column_span=3)
        self._entry_row(panel, 1, "日期 *", self.date_var, hint="2026-09-04 或 9月4日")
        self._entry_row(panel, 1, "开始时间 *", self.start_var, start_column=2, hint="15:00")
        self._entry_row(panel, 2, "结束时间", self.end_var, hint="可留空")
        self._entry_row(panel, 2, "地点 *", self.location_var, start_column=2)

        tk.Label(
            panel,
            text="腾讯会议号（每行一个）",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 9),
        ).grid(row=3, column=0, sticky="nw", pady=(10, 4))
        self.meetings_text = tk.Text(panel, height=3, wrap="word", font=(FONT_FAMILY, 10), relief="solid", borderwidth=1)
        self.meetings_text.grid(row=3, column=1, columnspan=3, sticky="nsew", padx=(8, 0), pady=(10, 4))

        tk.Label(
            panel,
            text="投递/联系信息\n（每行一项）",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            justify="left",
            font=(FONT_FAMILY, 9),
        ).grid(row=4, column=0, sticky="nw", pady=(8, 4))
        self.applications_text = tk.Text(panel, height=5, wrap="word", font=(FONT_FAMILY, 10), relief="solid", borderwidth=1)
        self.applications_text.grid(row=4, column=1, columnspan=3, sticky="nsew", padx=(8, 0), pady=(8, 4))
        panel.grid_rowconfigure(4, weight=1)

        tk.Label(
            panel,
            textvariable=self.warning_var,
            bg=COLORS["surface"],
            fg=COLORS["warning"],
            justify="left",
            anchor="w",
            font=(FONT_FAMILY, 9),
        ).grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 0))

        actions = tk.Frame(outer, bg=COLORS["background"])
        actions.pack(fill="x", pady=(12, 0))
        if self.seminar.id is not None:
            tk.Button(
                actions,
                text="删除",
                command=self._delete,
                bg=COLORS["background"],
                fg=COLORS["danger"],
                activeforeground=COLORS["danger"],
                relief="flat",
                padx=12,
                pady=7,
                font=(FONT_FAMILY, 10),
                cursor="hand2",
            ).pack(side="left")
        tk.Button(
            actions,
            text="取消",
            command=self.destroy,
            bg="#E6EAF0",
            fg=COLORS["text"],
            relief="flat",
            padx=18,
            pady=7,
            font=(FONT_FAMILY, 10),
            cursor="hand2",
        ).pack(side="right")
        tk.Button(
            actions,
            text="确认导入" if self.import_mode else "保存",
            command=self._save,
            bg=COLORS["primary"],
            fg="white",
            activebackground=COLORS["primary_hover"],
            activeforeground="white",
            relief="flat",
            padx=22,
            pady=7,
            font=(FONT_FAMILY, 10, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=(0, 8))

    def _entry_row(
        self,
        parent: tk.Misc,
        row: int,
        label: str,
        variable: tk.StringVar,
        start_column: int = 0,
        column_span: int = 1,
        hint: str = "",
    ) -> None:
        tk.Label(
            parent,
            text=label,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 9),
        ).grid(row=row, column=start_column, sticky="w", pady=5)
        entry = tk.Entry(
            parent,
            textvariable=variable,
            font=(FONT_FAMILY, 10),
            relief="solid",
            borderwidth=1,
        )
        entry.grid(
            row=row,
            column=start_column + 1,
            columnspan=column_span,
            sticky="ew",
            padx=(8, 14 if start_column == 0 and column_span == 1 else 0),
            pady=5,
            ipady=4,
        )
        if hint:
            entry.insert(0, "")

    def _load_seminar(self, seminar: Seminar) -> None:
        self.company_var.set(seminar.company)
        self.date_var.set(seminar.event_date.isoformat() if seminar.event_date else "")
        self.start_var.set(seminar.start_time)
        self.end_var.set(seminar.end_time)
        self.location_var.set(seminar.location)
        self.meetings_text.delete("1.0", "end")
        self.meetings_text.insert("1.0", "\n".join(seminar.meetings))
        self.applications_text.delete("1.0", "end")
        self.applications_text.insert(
            "1.0", "\n".join(application_to_line(item) for item in seminar.applications)
        )
        if self.source_text is not None:
            self.source_text.delete("1.0", "end")
            self.source_text.insert("1.0", seminar.source_text)
        self._show_missing(seminar)

    def _parse_source(self) -> None:
        assert self.source_text is not None
        source = self.source_text.get("1.0", "end-1c").strip()
        if not source:
            messagebox.showwarning("没有内容", "请先在文本框中粘贴一场宣讲会消息。", parent=self)
            return
        parsed = parse_seminar(source, date.today())
        parsed.id = self.seminar.id
        self.seminar = parsed
        self._load_seminar(parsed)
        missing = missing_required_fields(parsed)
        if missing:
            messagebox.showwarning(
                "需要补充信息",
                "未识别到：" + "、".join(missing) + "。\n请在预览区补充后再确认导入。",
                parent=self,
            )

    def _show_missing(self, seminar: Seminar) -> None:
        missing = missing_required_fields(seminar)
        if missing:
            self.warning_var.set("需要补充：" + "、".join(missing))
        else:
            self.warning_var.set("已识别完成，请检查内容是否正确后再保存。")

    def _read_form(self) -> Seminar:
        company = self.company_var.get().strip()
        date_value = self.date_var.get().strip()
        start_value = self.start_var.get().strip()
        location = self.location_var.get().strip()
        missing: list[str] = []
        if not company:
            missing.append("企业")
        if not date_value:
            missing.append("日期")
        if not start_value:
            missing.append("开始时间")
        if not location:
            missing.append("地点")
        if missing:
            raise ValueError("请补充必填项：" + "、".join(missing))

        event_date = parse_date_input(date_value)
        start_time = normalise_time(start_value, required=True)
        end_time = normalise_time(self.end_var.get())
        meetings = []
        for line in self.meetings_text.get("1.0", "end-1c").splitlines():
            value = re.sub(r"^腾讯会议\s*[：:]\s*", "", line.strip())
            if value and value not in meetings:
                meetings.append(value)

        source_text = self.seminar.source_text
        if self.source_text is not None:
            source_text = self.source_text.get("1.0", "end-1c").strip()
        return Seminar(
            id=self.seminar.id,
            company=company,
            event_date=event_date,
            start_time=start_time,
            end_time=end_time,
            location=location,
            meetings=meetings,
            applications=parse_application_lines(
                self.applications_text.get("1.0", "end-1c")
            ),
            source_text=source_text,
        )

    def _save(self) -> None:
        try:
            seminar = self._read_form()
        except ValueError as error:
            self.warning_var.set(str(error))
            messagebox.showwarning("信息不完整", str(error), parent=self)
            return

        if self.database.duplicates(seminar):
            proceed = messagebox.askyesno(
                "可能重复",
                f"已有相同企业、日期和开始时间的记录：\n\n"
                f"{seminar.company}  {seminar.event_date:%Y-%m-%d}  {seminar.start_time}\n\n"
                "是否仍然导入？",
                parent=self,
            )
            if not proceed:
                return
        if seminar.id is None:
            self.database.add(seminar)
        else:
            self.database.update(seminar)
        self.on_saved()
        self.destroy()

    def _delete(self) -> None:
        if self.seminar.id is None:
            return
        if not messagebox.askyesno(
            "确认删除",
            f"确定删除“{self.company_var.get().strip()}”这场宣讲会吗？",
            parent=self,
        ):
            return
        self.database.delete(self.seminar.id)
        self.on_saved()
        self.destroy()


class RecordsWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        database: SeminarDatabase,
        on_changed: Callable[[], None],
        history_only: bool,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.on_changed = on_changed
        self.history_only = history_only
        self.title("历史记录" if history_only else "全部记录")
        self.configure(bg=COLORS["background"])
        centre_window(self, 1050, 620)
        self.minsize(780, 450)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = tk.Frame(self, bg=COLORS["background"], padx=18, pady=16)
        outer.pack(fill="both", expand=True)
        tk.Label(
            outer,
            text="历史记录" if self.history_only else "全部宣讲会记录",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 16, "bold"),
        ).pack(anchor="w")
        subtitle = "仅显示今天以前的宣讲会，数据会永久保留。" if self.history_only else "包含过期、当前15天以及更远日期的宣讲会。"
        tk.Label(
            outer,
            text=subtitle,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(2, 12))

        table_frame = tk.Frame(outer, bg=COLORS["surface"])
        table_frame.pack(fill="both", expand=True)
        columns = ("date", "time", "company", "location", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {"date": "日期", "time": "时间", "company": "企业", "location": "地点", "status": "状态"}
        widths = {"date": 110, "time": 125, "company": 220, "location": 390, "status": 80}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=60, anchor="w")
        self.tree.column("status", anchor="center", stretch=False)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _event: self._edit())

        buttons = tk.Frame(outer, bg=COLORS["background"])
        buttons.pack(fill="x", pady=(12, 0))
        tk.Button(
            buttons,
            text="关闭",
            command=self.destroy,
            bg="#E6EAF0",
            fg=COLORS["text"],
            relief="flat",
            padx=18,
            pady=7,
            font=(FONT_FAMILY, 10),
            cursor="hand2",
        ).pack(side="right")
        tk.Button(
            buttons,
            text="编辑所选",
            command=self._edit,
            bg=COLORS["primary"],
            fg="white",
            activebackground=COLORS["primary_hover"],
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=7,
            font=(FONT_FAMILY, 10, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=(0, 8))

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        today = date.today()
        end = today + timedelta(days=14)
        seminars = self.database.history(today) if self.history_only else self.database.all()
        for seminar in seminars:
            if seminar.event_date is None or seminar.id is None:
                continue
            if seminar.event_date < today:
                status = "已过期"
            elif seminar.event_date <= end:
                status = "日历内"
            else:
                status = "未来"
            self.tree.insert(
                "",
                "end",
                iid=str(seminar.id),
                values=(
                    seminar.event_date.strftime("%Y-%m-%d"),
                    seminar.time_display,
                    seminar.company,
                    seminar.location,
                    status,
                ),
            )

    def _edit(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("请选择记录", "请先选择一条宣讲会记录。", parent=self)
            return
        seminar = self.database.get(int(selected[0]))
        if seminar is None:
            self.refresh()
            return

        def changed() -> None:
            self.refresh()
            self.on_changed()

        SeminarEditor(self, self.database, changed, seminar=seminar)


class DayCard(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        day: date,
        seminars: list[Seminar],
        on_edit: Callable[[Seminar], None],
        is_today: bool,
    ) -> None:
        background = COLORS["today"] if is_today else COLORS["surface"]
        border = COLORS["today_border"] if is_today else COLORS["border"]
        super().__init__(parent, bg=background, highlightbackground=border, highlightthickness=1)
        self.background = background

        header = tk.Frame(self, bg=background)
        header.pack(fill="x", padx=8, pady=(7, 4))
        tk.Label(
            header,
            text=f"{day.month}月{day.day}日",
            bg=background,
            fg=COLORS["primary"] if is_today else COLORS["text"],
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left")
        if is_today:
            tk.Label(
                header,
                text="今天",
                bg=COLORS["primary"],
                fg="white",
                font=(FONT_FAMILY, 8),
                padx=5,
                pady=1,
            ).pack(side="right")
        elif seminars:
            tk.Label(
                header,
                text=f"{len(seminars)}场",
                bg=background,
                fg=COLORS["muted"],
                font=(FONT_FAMILY, 8),
            ).pack(side="right")

        body_holder = tk.Frame(self, bg=background)
        body_holder.pack(fill="both", expand=True, padx=(7, 2), pady=(0, 6))
        canvas = tk.Canvas(body_holder, bg=background, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(body_holder, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=background)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def resize_body(event: tk.Event) -> None:
            canvas.itemconfigure(body_window, width=event.width)

        def update_scroll(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", resize_body)
        body.bind("<Configure>", update_scroll)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if not seminars:
            tk.Label(
                body,
                text="暂无宣讲会",
                bg=background,
                fg="#9AA4B5",
                font=(FONT_FAMILY, 9),
                pady=18,
            ).pack(fill="x")
        for index, seminar in enumerate(seminars):
            if index:
                tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", pady=6)
            self._add_seminar(body, seminar, on_edit)

        def wheel(event: tk.Event) -> str:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        for widget in (canvas, body):
            widget.bind("<MouseWheel>", wheel)

    def _add_seminar(
        self,
        parent: tk.Misc,
        seminar: Seminar,
        on_edit: Callable[[Seminar], None],
    ) -> None:
        company = tk.Label(
            parent,
            text=seminar.company,
            bg=self.background,
            fg=COLORS["primary"],
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
            justify="left",
            cursor="hand2",
        )
        company.pack(fill="x")
        company.bind("<Button-1>", lambda _event, item=seminar: on_edit(item))
        tk.Label(
            parent,
            text=f"⏰ {seminar.time_display}",
            bg=self.background,
            fg=COLORS["text"],
            font=(FONT_FAMILY, 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(2, 0))
        tk.Label(
            parent,
            text=f"📍 {seminar.location}",
            bg=self.background,
            fg=COLORS["text"],
            font=(FONT_FAMILY, 8),
            anchor="w",
            justify="left",
            wraplength=170,
        ).pack(fill="x")
        for meeting in seminar.meetings:
            tk.Label(
                parent,
                text=f"腾讯会议：{meeting}",
                bg=self.background,
                fg=COLORS["muted"],
                font=(FONT_FAMILY, 8),
                anchor="w",
                justify="left",
                wraplength=170,
            ).pack(fill="x")
        for resource in seminar.applications:
            label = tk.Label(
                parent,
                text=application_to_line(resource),
                bg=self.background,
                fg=COLORS["link"] if is_clickable(resource) else COLORS["muted"],
                font=(FONT_FAMILY, 8, "underline" if is_clickable(resource) else "normal"),
                anchor="w",
                justify="left",
                wraplength=170,
                cursor="hand2" if is_clickable(resource) else "arrow",
            )
            label.pack(fill="x", pady=(1, 0))
            if is_clickable(resource):
                label.bind("<Button-1>", lambda _event, item=resource: open_resource(item))


class SeminarCalendarApp:
    def __init__(self, root: tk.Tk, database: SeminarDatabase | None = None) -> None:
        self.root = root
        self.database = database or SeminarDatabase()
        self.current_day = date.today()
        self.root.title(APP_TITLE)
        self.root.configure(bg=COLORS["background"])
        self.root.minsize(1180, 720)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        centre_window(self.root, min(1500, screen_width - 40), min(920, screen_height - 70))
        self._configure_style()
        self._build()
        self.refresh_calendar()
        self._watch_date_change()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", font=(FONT_FAMILY, 9), rowheight=30)
        style.configure("Treeview.Heading", font=(FONT_FAMILY, 9, "bold"))

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=COLORS["surface"], padx=20, pady=14)
        header.pack(fill="x")
        title_area = tk.Frame(header, bg=COLORS["surface"])
        title_area.pack(side="left")
        tk.Label(
            title_area,
            text=APP_TITLE,
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=(FONT_FAMILY, 19, "bold"),
        ).pack(anchor="w")
        self.range_var = tk.StringVar()
        tk.Label(
            title_area,
            textvariable=self.range_var,
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=(FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, bg=COLORS["surface"])
        actions.pack(side="right")
        self._toolbar_button(actions, "历史记录", lambda: self._open_records(True)).pack(side="left", padx=4)
        self._toolbar_button(actions, "全部记录", lambda: self._open_records(False)).pack(side="left", padx=4)
        self._toolbar_button(actions, "手工录入", self._manual_add).pack(side="left", padx=4)
        self._toolbar_button(actions, "＋ 导入宣讲会", self._import).pack(side="left", padx=(8, 0))

        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(fill="x")
        self.calendar = tk.Frame(self.root, bg=COLORS["background"], padx=12, pady=10)
        self.calendar.pack(fill="both", expand=True)
        for column in range(7):
            self.calendar.grid_columnconfigure(column, weight=1, uniform="day")
        for row in range(1, 4):
            self.calendar.grid_rowconfigure(row, weight=1, uniform="week")

    def _toolbar_button(self, parent: tk.Misc, text: str, command: Callable[[], None]) -> tk.Button:
        primary = "导入" in text
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLORS["primary"] if primary else "#E9EDF5",
            fg="white" if primary else COLORS["text"],
            activebackground=COLORS["primary_hover"] if primary else "#DDE3ED",
            activeforeground="white" if primary else COLORS["text"],
            relief="flat",
            padx=14,
            pady=7,
            font=(FONT_FAMILY, 9, "bold" if primary else "normal"),
            cursor="hand2",
        )

    def refresh_calendar(self) -> None:
        for child in self.calendar.winfo_children():
            child.destroy()
        today = date.today()
        end = today + timedelta(days=14)
        self.current_day = today
        self.range_var.set(f"滚动显示今天起15天：{today:%Y年%m月%d日} — {end:%Y年%m月%d日}")
        seminars = self.database.between(today, end)
        by_day: dict[date, list[Seminar]] = {}
        for seminar in seminars:
            if seminar.event_date is not None:
                by_day.setdefault(seminar.event_date, []).append(seminar)

        for column, weekday in enumerate(WEEKDAYS):
            tk.Label(
                self.calendar,
                text=weekday,
                bg=COLORS["background"],
                fg=COLORS["muted"],
                font=(FONT_FAMILY, 9, "bold"),
                pady=4,
            ).grid(row=0, column=column, sticky="ew")

        leading = today.weekday()
        for position in range(21):
            row = position // 7 + 1
            column = position % 7
            if position < leading or position >= leading + 15:
                blank = tk.Frame(self.calendar, bg=COLORS["background"])
                blank.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
                continue
            day = today + timedelta(days=position - leading)
            card = DayCard(
                self.calendar,
                day,
                by_day.get(day, []),
                self._edit,
                is_today=day == today,
            )
            card.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)

    def _watch_date_change(self) -> None:
        if date.today() != self.current_day:
            self.refresh_calendar()
        self.root.after(60_000, self._watch_date_change)

    def _import(self) -> None:
        SeminarEditor(self.root, self.database, self.refresh_calendar, import_mode=True)

    def _manual_add(self) -> None:
        SeminarEditor(self.root, self.database, self.refresh_calendar)

    def _edit(self, seminar: Seminar) -> None:
        current = self.database.get(seminar.id) if seminar.id is not None else seminar
        if current is not None:
            SeminarEditor(self.root, self.database, self.refresh_calendar, seminar=current)

    def _open_records(self, history_only: bool) -> None:
        RecordsWindow(self.root, self.database, self.refresh_calendar, history_only)


def main() -> int:
    if "--check" in sys.argv:
        database = SeminarDatabase()
        database.all()
        return 0
    root = tk.Tk()
    SeminarCalendarApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

