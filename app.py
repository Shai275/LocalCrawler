"""LocalCrawler: a local Traditional Chinese desktop crawler."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import webbrowser
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from runtime_paths import APP_DIR as BASE, DATA_DIR, DOWNLOADS_DIR, LOG_FILE, PREFERENCES_FILE
from engine import Page, crawl_batch, load_results, parse_urls
from insights import DEFAULT_MODEL
from ai_providers import AIProviderConfig, CLOUD_PROVIDERS, LABELS, ProviderError, create_provider
from deliverables import export_deliverables as build_deliverables

AI_MODES = {'本機 AI（Ollama）': 'ollama', '基本摘錄（免模型）': 'basic', 'OpenAI API': 'openai', 'Gemini API': 'gemini'}

PREFERENCES = PREFERENCES_FILE


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LocalCrawler 3.4 預覽版 · 看懂字幕與畫面")
        self.geometry("1100x820")
        self.minsize(940, 680)
        self.configure(bg="#f5f5f7")
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.pages: list[Page] = []
        self.folder: Path | None = None
        self.comparison_file: Path | None = None
        self.closing = False
        self.total = 0
        self.failure = ""
        self.view_only = False
        self.active_urls = []
        self.output = tk.StringVar(value=str(DOWNLOADS_DIR))
        self.delay = tk.StringVar(value="1")
        self.timeout = tk.StringVar(value="30")
        self.selector = tk.StringVar()
        self.retries = tk.StringVar(value="1")
        self.analyze_frames = tk.BooleanVar(value=False)
        self.vision_model = tk.StringVar(value="qwen2.5vl:3b")
        self.ai_mode = tk.StringVar(value="本機 AI（Ollama）")
        self.model = tk.StringVar(value=DEFAULT_MODEL)
        self.provider_models = {'ollama': DEFAULT_MODEL, 'basic': '', 'openai': '', 'gemini': ''}
        self.session_keys = {}
        self.model_cache = {}
        self.preview_mode = tk.StringVar(value="重點摘要")
        self.search = tk.StringVar()
        self.filter = tk.StringVar(value="全部")
        self.last_folder = ""
        self.read_preferences()
        self.current_provider = AI_MODES.get(self.ai_mode.get(), 'ollama')
        self.status = tk.StringVar(value="就緒 · 貼上網址即可開始")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def read_preferences(self):
        try:
            data = json.loads(PREFERENCES.read_text(encoding="utf-8"))
            for key in ("output", "delay", "timeout", "selector", "retries", "ai_mode", "model"):
                if isinstance(data.get(key), str):
                    getattr(self, key).set(data[key])
            if isinstance(data.get("analyze_frames"), bool):
                self.analyze_frames.set(data["analyze_frames"])
            if isinstance(data.get("vision_model"), str):
                self.vision_model.set(data["vision_model"])
            self.last_folder = data.get("last_folder", "")
            models = data.get('provider_models', {})
            if isinstance(models, dict):
                self.provider_models.update({k: v for k, v in models.items() if k in self.provider_models and isinstance(v, str)})
            if data.get("settings_version") not in ('3.1', '3.2', '3.3', '3.4') and self.model.get() == "qwen2.5:3b":
                self.model.set(DEFAULT_MODEL)
        except (OSError, ValueError, AttributeError):
            pass

    def save_preferences(self):
        try:
            data = {key: getattr(self, key).get() for key in ("output", "delay", "timeout", "selector", "retries", "ai_mode", "model")}
            self.provider_models[AI_MODES.get(self.ai_mode.get(), 'ollama')] = self.model.get().strip()
            data['provider_models'] = self.provider_models
            data["analyze_frames"] = self.analyze_frames.get()
            data["vision_model"] = self.vision_model.get().strip()
            data["settings_version"] = "3.4"
            data["last_folder"] = str(self.folder) if self.folder else self.last_folder
            temp = PREFERENCES.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(PREFERENCES)
        except OSError:
            logging.exception("Could not save settings")

    def _build(self):
        colors = {
            "canvas": "#121317", "panel": "#1a1b1f", "panel_high": "#22242b",
            "input": "#0d0e12", "border": "#30313a", "border_high": "#464754",
            "text": "#f3f4f6", "muted": "#a0a2ae", "subtle": "#666977",
            "primary": "#7376ff", "primary_active": "#5e61e8", "success": "#4edea3",
            "warning": "#ffb95f", "danger": "#ff7b72",
        }
        self.ui_colors = colors
        self.title("LocalCrawler 3.4 · AI Research Workspace")
        self.geometry("1420x900")
        self.minsize(1120, 720)
        self.configure(bg=colors["canvas"])

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=colors["canvas"])
        style.configure("Panel.TFrame", background=colors["panel"])
        style.configure("TLabel", background=colors["canvas"], foreground=colors["text"], font=("Microsoft JhengHei UI", 10))
        style.configure("Panel.TLabel", background=colors["panel"], foreground=colors["text"], font=("Microsoft JhengHei UI", 10))
        style.configure("Muted.TLabel", background=colors["canvas"], foreground=colors["muted"], font=("Microsoft JhengHei UI", 9))
        style.configure("PanelMuted.TLabel", background=colors["panel"], foreground=colors["muted"], font=("Microsoft JhengHei UI", 9))
        style.configure("Eyebrow.TLabel", background=colors["canvas"], foreground=colors["muted"], font=("Consolas", 9, "bold"))
        style.configure("PanelEyebrow.TLabel", background=colors["panel"], foreground=colors["muted"], font=("Consolas", 9, "bold"))
        style.configure("Heading.TLabel", background=colors["canvas"], foreground=colors["text"], font=("Segoe UI", 17, "bold"))
        style.configure("PanelHeading.TLabel", background=colors["panel"], foreground=colors["text"], font=("Segoe UI", 13, "bold"))
        style.configure("TButton", font=("Microsoft JhengHei UI", 9), padding=(11, 7), borderwidth=1,
                        background=colors["panel_high"], foreground=colors["text"], bordercolor=colors["border"])
        style.map("TButton", background=[("active", "#2c2e37"), ("disabled", colors["panel"])],
                  foreground=[("disabled", colors["subtle"])], bordercolor=[("active", colors["border_high"])])
        style.configure("Accent.TButton", background=colors["primary"], foreground="#ffffff", bordercolor=colors["primary"],
                        font=("Microsoft JhengHei UI", 10, "bold"), padding=(14, 9))
        style.map("Accent.TButton", background=[("active", colors["primary_active"]), ("disabled", "#34354d")],
                  foreground=[("disabled", "#77798f")])
        style.configure("Quiet.TButton", padding=(8, 5))
        style.configure("TEntry", fieldbackground=colors["input"], foreground=colors["text"], insertcolor=colors["text"],
                        bordercolor=colors["border"], lightcolor=colors["border"], darkcolor=colors["border"], padding=7)
        style.map("TEntry", bordercolor=[("focus", colors["primary"])])
        style.configure("TSpinbox", fieldbackground=colors["input"], foreground=colors["text"], arrowcolor=colors["muted"],
                        bordercolor=colors["border"], padding=5)
        style.configure("TCombobox", fieldbackground=colors["input"], background=colors["panel_high"], foreground=colors["text"],
                        arrowcolor=colors["muted"], bordercolor=colors["border"], padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", colors["input"])], foreground=[("readonly", colors["text"])],
                  bordercolor=[("focus", colors["primary"])])
        style.configure("TCheckbutton", background=colors["panel"], foreground=colors["text"], font=("Microsoft JhengHei UI", 9))
        style.map("TCheckbutton", background=[("active", colors["panel"])], indicatorcolor=[("selected", colors["primary"])])
        style.configure("Horizontal.TProgressbar", troughcolor=colors["input"], background=colors["primary"], borderwidth=0)
        style.configure("Treeview", borderwidth=0, relief="flat", rowheight=39, background=colors["panel"],
                        fieldbackground=colors["panel"], foreground=colors["text"], font=("Microsoft JhengHei UI", 9))
        style.map("Treeview", background=[("selected", "#343654")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background=colors["input"], foreground=colors["muted"], relief="flat",
                        borderwidth=0, font=("Consolas", 9, "bold"), padding=(8, 8))
        style.map("Treeview.Heading", background=[("active", colors["panel_high"])])
        style.configure("Vertical.TScrollbar", background=colors["panel_high"], troughcolor=colors["canvas"], borderwidth=0,
                        arrowcolor=colors["muted"])

        header = tk.Frame(self, bg=colors["panel"], height=60, highlightthickness=1, highlightbackground=colors["border"])
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg=colors["panel"])
        brand.pack(side="left", padx=20, fill="y")
        tk.Label(brand, text="◆", bg=colors["panel"], fg=colors["primary"], font=("Segoe UI Symbol", 14)).pack(side="left", pady=17)
        tk.Label(brand, text="LocalCrawler", bg=colors["panel"], fg=colors["text"], font=("Segoe UI", 13, "bold")).pack(side="left", padx=(8, 0), pady=17)
        tk.Label(brand, text="AI RESEARCH WORKSPACE", bg=colors["panel"], fg=colors["muted"], font=("Consolas", 9)).pack(side="left", padx=(14, 0), pady=20)
        header_right = tk.Frame(header, bg=colors["panel"])
        header_right.pack(side="right", padx=18, fill="y")
        self.provider_badge = tk.Label(header_right, text="", bg="#13251e", fg=colors["success"],
                                       font=("Consolas", 9, "bold"), padx=9, pady=5,
                                       highlightthickness=1, highlightbackground="#275441")
        self.provider_badge.pack(side="left", pady=15)
        self.model_badge = tk.Label(header_right, text="", bg=colors["panel_high"], fg=colors["muted"],
                                    font=("Consolas", 9), padx=9, pady=5,
                                    highlightthickness=1, highlightbackground=colors["border"])
        self.model_badge.pack(side="left", padx=(8, 0), pady=15)

        workspace = tk.PanedWindow(self, orient="horizontal", bg=colors["border"], sashwidth=1, sashrelief="flat",
                                   borderwidth=0, opaqueresize=True)
        workspace.pack(fill="both", expand=True)

        left = ttk.Frame(workspace, style="Panel.TFrame", padding=(18, 18))
        center = ttk.Frame(workspace, padding=(22, 18))
        right = ttk.Frame(workspace, style="Panel.TFrame", padding=(16, 18))
        workspace.add(left, minsize=300, width=338)
        workspace.add(center, minsize=480, stretch="always")
        workspace.add(right, minsize=315, width=370)

        ttk.Label(left, text="01 / SOURCES", style="PanelEyebrow.TLabel").pack(anchor="w")
        ttk.Label(left, text="建立研究工作", style="PanelHeading.TLabel").pack(anchor="w", pady=(3, 3))
        ttk.Label(left, text="貼上網頁或 YouTube 連結，每行一個。", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 10))
        self.urls = tk.Text(left, height=6, wrap="none", undo=True, relief="flat", borderwidth=0,
                            bg=colors["input"], fg=colors["text"], insertbackground=colors["text"],
                            selectbackground=colors["primary"], font=("Consolas", 10), padx=11, pady=9,
                            highlightthickness=1, highlightbackground=colors["border"], highlightcolor=colors["primary"])
        self.urls.pack(fill="x")
        self.urls.insert("1.0", "https://example.com")
        input_actions = ttk.Frame(left, style="Panel.TFrame")
        self.input_actions = input_actions
        input_actions.pack(fill="x", pady=(8, 11))
        self.import_button = ttk.Button(input_actions, text="匯入 .txt", style="Quiet.TButton", command=self.import_urls)
        self.import_button.pack(side="left", fill="x", expand=True)
        self.paste_button = ttk.Button(input_actions, text="貼上文字／字幕", style="Quiet.TButton", command=self.paste_text)
        self.paste_button.pack(side="left", padx=(7, 0), fill="x", expand=True)

        self.advanced = ttk.Frame(left, style="Panel.TFrame")
        self.advanced_toggle = ttk.Button(left, text="模型與擷取設定  ▸", command=self.toggle_advanced)
        self.advanced_toggle.pack(fill="x", pady=(0, 8))
        timing = ttk.Frame(self.advanced, style="Panel.TFrame")
        timing.pack(fill="x", pady=(0, 7))
        ttk.Label(timing, text="間隔", style="PanelMuted.TLabel").pack(side="left")
        self.delay_input = ttk.Spinbox(timing, from_=0.5, to=60, increment=0.5, textvariable=self.delay, width=4)
        self.delay_input.pack(side="left", padx=(5, 10))
        ttk.Label(timing, text="逾時", style="PanelMuted.TLabel").pack(side="left")
        self.timeout_input = ttk.Spinbox(timing, from_=5, to=180, textvariable=self.timeout, width=4)
        self.timeout_input.pack(side="left", padx=(5, 10))
        ttk.Label(timing, text="重試", style="PanelMuted.TLabel").pack(side="left")
        self.retries_input = ttk.Spinbox(timing, from_=0, to=2, textvariable=self.retries, width=3)
        self.retries_input.pack(side="left", padx=(5, 0))
        selector_row = ttk.Frame(self.advanced, style="Panel.TFrame")
        selector_row.pack(fill="x", pady=(0, 7))
        ttk.Label(selector_row, text="CSS", style="PanelMuted.TLabel", width=7).pack(side="left")
        self.selector_input = ttk.Entry(selector_row, textvariable=self.selector)
        self.selector_input.pack(side="left", fill="x", expand=True)
        provider_row = ttk.Frame(self.advanced, style="Panel.TFrame")
        provider_row.pack(fill="x", pady=(0, 7))
        ttk.Label(provider_row, text="摘要", style="PanelMuted.TLabel", width=7).pack(side="left")
        self.mode_input = ttk.Combobox(provider_row, textvariable=self.ai_mode, values=list(AI_MODES), state="readonly", width=20)
        self.mode_input.bind('<<ComboboxSelected>>', self.change_provider)
        self.mode_input.pack(side="left", fill="x", expand=True)
        model_row = ttk.Frame(self.advanced, style="Panel.TFrame")
        model_row.pack(fill="x", pady=(0, 7))
        ttk.Label(model_row, text="模型", style="PanelMuted.TLabel", width=7).pack(side="left")
        self.model_input = ttk.Combobox(model_row, textvariable=self.model, width=20)
        self.model_input.pack(side="left", fill="x", expand=True)
        ai_actions = ttk.Frame(self.advanced, style="Panel.TFrame")
        ai_actions.pack(fill="x", pady=(0, 7))
        self.check_ai_button = ttk.Button(ai_actions, text="更新模型", style="Quiet.TButton", command=self.check_ai)
        self.check_ai_button.pack(side="left", fill="x", expand=True)
        self.key_button = ttk.Button(ai_actions, text="API 金鑰", style="Quiet.TButton", command=self.key_dialog)
        self.key_button.pack(side="left", padx=(7, 0), fill="x", expand=True)
        self.ai_hint = ttk.Label(self.advanced, text=self.provider_hint(), style="PanelMuted.TLabel", wraplength=285, justify="left")
        self.frames_input = ttk.Checkbutton(self.advanced, text="融合字幕與關鍵影格（最多 12 張）", variable=self.analyze_frames)
        self.frames_input.pack(anchor="w", pady=(0, 7))
        vision_row = ttk.Frame(self.advanced, style="Panel.TFrame")
        vision_row.pack(fill="x", pady=(0, 7))
        ttk.Label(vision_row, text="視覺模型", style="PanelMuted.TLabel", width=9).pack(side="left")
        self.vision_model_input = ttk.Entry(vision_row, textvariable=self.vision_model)
        self.vision_model_input.pack(side="left", fill="x", expand=True)
        destination = ttk.Frame(self.advanced, style="Panel.TFrame")
        destination.pack(fill="x", pady=(0, 8))
        self.output_input = ttk.Entry(destination, textvariable=self.output)
        self.output_input.pack(side="left", fill="x", expand=True)
        self.choose_button = ttk.Button(destination, text="儲存位置", style="Quiet.TButton", command=self.choose)
        self.choose_button.pack(side="left", padx=(7, 0))

        self.actions = ttk.Frame(left, style="Panel.TFrame")
        self.actions.pack(fill="x", pady=(1, 8))
        self.start_button = ttk.Button(self.actions, text="開始整理來源", style="Accent.TButton", command=self.start)
        self.start_button.pack(fill="x")
        secondary_actions = ttk.Frame(self.actions, style="Panel.TFrame")
        secondary_actions.pack(fill="x", pady=(7, 0))
        self.stop_button = ttk.Button(secondary_actions, text="停止", style="Quiet.TButton", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True)
        self.retry_button = ttk.Button(secondary_actions, text="重試失敗", style="Quiet.TButton", command=self.retry_failed, state="disabled")
        self.retry_button.pack(side="left", padx=(7, 0), fill="x", expand=True)
        self.progress = ttk.Progressbar(left, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(3, 8))
        status_card = tk.Frame(left, bg=colors["input"], highlightthickness=1, highlightbackground=colors["border"])
        status_card.pack(fill="x")
        tk.Label(status_card, text="●", bg=colors["input"], fg=colors["success"], font=("Segoe UI", 9)).pack(side="left", padx=(10, 5), pady=9)
        tk.Label(status_card, textvariable=self.status, bg=colors["input"], fg=colors["muted"],
                 font=("Microsoft JhengHei UI", 9), wraplength=270, justify="left", anchor="w").pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)
        folder_actions = ttk.Frame(left, style="Panel.TFrame")
        folder_actions.pack(fill="x", side="bottom", pady=(10, 0))
        self.open_button = ttk.Button(folder_actions, text="開啟結果", style="Quiet.TButton", command=self.open_folder, state="disabled")
        self.open_button.pack(side="left", fill="x", expand=True)
        self.history_button = ttk.Button(folder_actions, text="歷史資料", style="Quiet.TButton", command=self.open_history)
        self.history_button.pack(side="left", padx=(7, 0), fill="x", expand=True)

        center_header = ttk.Frame(center)
        center_header.pack(fill="x", pady=(0, 12))
        title_block = ttk.Frame(center_header)
        title_block.pack(side="left")
        ttk.Label(title_block, text="02 / SYNTHESIS", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(title_block, text="研究報告", style="Heading.TLabel").pack(anchor="w", pady=(2, 0))
        view_actions = ttk.Frame(center_header)
        view_actions.pack(side="right", anchor="s")
        ttk.Combobox(view_actions, textvariable=self.preview_mode,
                     values=["重點摘要", "原始內容", "來源對照", "整批比較", "比較來源"],
                     width=10, state="readonly").pack(side="left", padx=(0, 7))
        self.preview_mode.trace_add("write", lambda *_: self.preview())
        self.copy_button = ttk.Button(view_actions, text="複製", style="Quiet.TButton", command=self.copy_content, state="disabled")
        self.copy_button.pack(side="left")
        self.file_button = ttk.Button(view_actions, text="Markdown", style="Quiet.TButton", command=self.open_markdown, state="disabled")
        self.file_button.pack(side="left", padx=(7, 0))
        report_actions = ttk.Frame(center)
        report_actions.pack(fill="x", pady=(0, 10))
        self.export_button = ttk.Button(report_actions, text="匯出 PDF / Notion / Markdown / Canvas", style="Accent.TButton",
                                        command=self.export_report, state="disabled")
        self.export_button.pack(side="left")
        ttk.Button(report_actions, text="影格與時間證據", command=self.open_evidence).pack(side="left", padx=(8, 0))
        ttk.Label(report_actions, text="MARKDOWN · SOURCE-LINKED", style="Eyebrow.TLabel").pack(side="right", pady=9)
        preview_shell = tk.Frame(center, bg=colors["panel"], highlightthickness=1, highlightbackground=colors["border"])
        preview_shell.pack(fill="both", expand=True)
        self.preview_text = tk.Text(preview_shell, wrap="word", height=8, state="disabled", relief="flat", borderwidth=0,
                                    bg=colors["panel"], fg="#d8d9df", insertbackground=colors["text"],
                                    selectbackground="#3e4172", font=("Microsoft JhengHei UI", 11), spacing1=3,
                                    spacing2=2, spacing3=8, padx=24, pady=22)
        preview_scroll = ttk.Scrollbar(preview_shell, command=self.preview_text.yview, style="Vertical.TScrollbar")
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side="right", fill="y")
        self.preview_text.pack(fill="both", expand=True)
        self.show_preview("研究工作台已就緒。\n\n在左側貼上網頁或 YouTube 連結，選擇摘要方式後開始整理。完成後可在右側切換來源，並由這裡閱讀有時間點與證據連結的報告。")

        ttk.Label(right, text="03 / EVIDENCE", style="PanelEyebrow.TLabel").pack(anchor="w")
        ttk.Label(right, text="來源與驗證", style="PanelHeading.TLabel").pack(anchor="w", pady=(3, 3))
        ttk.Label(right, text="選取來源以切換中央報告。", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 10))
        filter_bar = ttk.Frame(right, style="Panel.TFrame")
        filter_bar.pack(fill="x", pady=(0, 9))
        search_input = ttk.Entry(filter_bar, textvariable=self.search)
        search_input.pack(side="left", fill="x", expand=True)
        ttk.Combobox(filter_bar, textvariable=self.filter, values=["全部", "成功", "失敗"], state="readonly", width=6).pack(side="left", padx=(7, 0))
        table_frame = ttk.Frame(right, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("state", "title", "url"), show="headings", height=10)
        for key, title, width in [("state", "狀態", 58), ("title", "來源", 165), ("url", "網址", 210)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=52, stretch=key != "state")
        table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview, style="Vertical.TScrollbar")
        self.table.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.preview)
        privacy = tk.Frame(right, bg=colors["input"], highlightthickness=1, highlightbackground=colors["border"])
        privacy.pack(fill="x", pady=(12, 0))
        tk.Label(privacy, text="LOCAL-FIRST", bg=colors["input"], fg=colors["success"], font=("Consolas", 9, "bold")).pack(anchor="w", padx=11, pady=(9, 2))
        tk.Label(privacy, text="依 robots.txt 檢查規則。雲端 AI 只有在你選用並確認後才傳送內容。",
                 bg=colors["input"], fg=colors["muted"], font=("Microsoft JhengHei UI", 9),
                 wraplength=310, justify="left").pack(anchor="w", padx=11, pady=(0, 10))
        self.search.trace_add("write", lambda *_: self.refresh_table())
        self.filter.trace_add("write", lambda *_: self.refresh_table())
        self.inputs = [self.urls, self.delay_input, self.timeout_input, self.selector_input, self.output_input, self.choose_button, self.import_button, self.retries_input, self.history_button]
        self.inputs.extend([self.mode_input, self.model_input, self.paste_button, self.key_button, self.check_ai_button, self.frames_input, self.vision_model_input])
        self.model.trace_add("write", self._sync_header_badges)
        self._sync_header_badges()

    def _sync_header_badges(self, *_):
        if not hasattr(self, "provider_badge"):
            return
        mode = AI_MODES.get(self.ai_mode.get(), "basic")
        local = mode in {"ollama", "basic"}
        label = "● LOCAL PROCESSING" if local else "● CLOUD API OPT-IN"
        self.provider_badge.configure(
            text=label,
            bg="#13251e" if local else "#2a2112",
            fg=self.ui_colors["success"] if local else self.ui_colors["warning"],
            highlightbackground="#275441" if local else "#66502a",
        )
        model = self.model.get().strip() or ("NO MODEL" if mode == "basic" else "MODEL NOT SET")
        self.model_badge.configure(text=model[:30])

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget()
            self.urls.pack(fill="x", before=self.advanced_toggle)
            self.input_actions.pack(fill="x", pady=(8, 11), before=self.advanced_toggle)
            self.advanced_toggle.configure(text="模型與擷取設定  ▸")
        else:
            self.urls.pack_forget()
            self.input_actions.pack_forget()
            self.advanced.pack(fill="x", before=self.actions)
            self.advanced_toggle.configure(text="模型與擷取設定  ▾")

    def provider_hint(self):
        mode = AI_MODES.get(self.ai_mode.get(), 'basic')
        if mode in CLOUD_PROVIDERS:
            return '雲端模式：擷取文字會傳至所選 API，可能計費。請先設定金鑰，再更新模型清單或填模型 ID。'
        return '本機模式僅連接 127.0.0.1 的 Ollama；基本摘錄不使用 AI。'

    def change_provider(self, event=None):
        self.provider_models[self.current_provider] = self.model.get().strip()
        self.current_provider = AI_MODES.get(self.ai_mode.get(), 'basic')
        self.model.set(self.provider_models[self.current_provider])
        self.model_input.configure(values=self.model_cache.get(self.current_provider, []))
        self.ai_hint.configure(text=self.provider_hint())
        self._sync_header_badges()

    def selected_backend(self, for_listing=False):
        mode = AI_MODES.get(self.ai_mode.get(), 'basic')
        model = self.model.get().strip() or ('listing' if for_listing else '')
        key = ''
        if mode in CLOUD_PROVIDERS:
            key = self.session_keys.get(mode, '')
            if not key:
                from credentials import load_key
                key = load_key(mode)
        return create_provider(AIProviderConfig(mode, model), api_key=key, cloud_allowed=mode in CLOUD_PROVIDERS)

    def key_dialog(self):
        mode = AI_MODES.get(self.ai_mode.get(), 'basic')
        if mode not in CLOUD_PROVIDERS:
            messagebox.showinfo('不需要金鑰', '請先選擇 OpenAI API 或 Gemini API。', parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title(LABELS[mode] + ' · API 金鑰')
        dialog.geometry('530x235')
        dialog.transient(self)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='貼上 API 金鑰；留空不會覆蓋已儲存的金鑰。').pack(anchor='w')
        entry = ttk.Entry(body, show='•', width=55)
        entry.pack(fill='x', pady=12)
        ttk.Label(body, text='「僅本次」保留至關閉程式；「安全儲存」存入 Windows 認證管理員。\n金鑰不會寫入設定檔或研究報告。', wraplength=480).pack(anchor='w')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=15)
        def use(save=False):
            value = entry.get().strip()
            if not value:
                return
            try:
                if save:
                    from credentials import save_key
                    save_key(mode, value)
                self.session_keys[mode] = value
                entry.delete(0, 'end')
                dialog.destroy()
            except ProviderError as exc:
                messagebox.showerror('金鑰設定', str(exc), parent=dialog)
        def forget():
            try:
                from credentials import delete_key
                delete_key(mode)
                self.session_keys.pop(mode, None)
                entry.delete(0, 'end')
                dialog.destroy()
            except ProviderError as exc:
                messagebox.showerror('金鑰設定', str(exc), parent=dialog)
        ttk.Button(buttons, text='僅本次', command=use).pack(side='left')
        ttk.Button(buttons, text='安全儲存', command=lambda: use(True)).pack(side='left', padx=8)
        ttk.Button(buttons, text='刪除已存金鑰', command=forget).pack(side='right')
        entry.focus_set()

    def check_ai(self):
        try:
            backend = self.selected_backend(for_listing=True)
        except ProviderError as exc:
            messagebox.showerror('AI 設定', str(exc), parent=self)
            return
        self.check_ai_button.configure(state='disabled')
        def check():
            try:
                models = asyncio.run(backend.models())
                self.events.put(('ai_models', (backend.name, models)))
            except ProviderError as exc:
                self.events.put(('ai_check', str(exc)))
            except Exception:
                self.events.put(('ai_check', '模型清單讀取失敗'))
        threading.Thread(target=check, daemon=True).start()

    def paste_text(self):
        dialog = tk.Toplevel(self)
        dialog.title("貼上你已有的文章或字幕")
        dialog.geometry("740x500")
        ttk.Label(dialog, text="貼上全文、SRT 或 VTT 字幕。內容只會在本機整理。", padding=12).pack(anchor="w")
        editor = tk.Text(dialog, wrap="word", font=("Microsoft JhengHei UI", 11))
        editor.pack(fill="both", expand=True, padx=12)
        def submit():
            content = editor.get("1.0", "end").strip()
            if not content or len(content) > 500000:
                messagebox.showerror("請檢查內容", "請貼上 1–500,000 字元的內容。", parent=dialog)
                return
            dialog.destroy()
            self.start(pasted_text=content)
        ttk.Button(dialog, text="整理這段內容", command=submit).pack(pady=12)
        dialog.transient(self)
        dialog.grab_set()
        editor.focus_set()

    def import_urls(self):
        filename = filedialog.askopenfilename(title="選擇網址清單", filetypes=[("文字檔", "*.txt")], parent=self)
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 1024 * 1024:
                raise ValueError("網址清單不可超過 1 MB。")
            urls = parse_urls(path.read_text(encoding="utf-8-sig"))
            self.urls.delete("1.0", "end")
            self.urls.insert("1.0", "\n".join(urls))
            self.status.set(f"已匯入 {len(urls)} 個網址。")
        except (OSError, ValueError) as exc:
            messagebox.showerror("無法匯入", str(exc), parent=self)

    def open_history(self):
        initial = self.last_folder if isinstance(self.last_folder, str) and Path(self.last_folder).is_dir() else self.output.get()
        filename = filedialog.askopenfilename(title="開啟先前的 results.json", initialdir=initial, filetypes=[("爬取結果", "results.json"), ("JSON", "*.json")], parent=self)
        if not filename:
            return
        try:
            pages = load_results(Path(filename))
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("無法開啟", str(exc), parent=self)
            return
        self.pages, self.folder = pages, Path(filename).parent
        self.comparison_file = self.folder / "batch_summary.md"
        self.view_only = True
        self.search.set("")
        self.filter.set("全部")
        self.refresh_table()
        self.progress.configure(maximum=max(1, len(pages)), value=len(pages))
        self.open_button.configure(state="normal")
        self.retry_button.configure(state="normal" if any(not p.success for p in pages) else "disabled")
        self.status.set(f"歷史結果 · {len(pages)} 筆 · {self.folder.name}")
        if self.table.get_children():
            self.table.selection_set(self.table.get_children()[0])
            self.preview()
        else:
            self.show_preview("這份歷史結果尚無已完成的頁面。")
        self.save_preferences()

        if self.comparison_file.is_file():
            self.preview_mode.set("整批比較")

    def refresh_table(self):
        if not hasattr(self, "table"):
            return
        selected = self.table.selection()
        for item in self.table.get_children():
            self.table.delete(item)
        query = self.search.get().casefold().strip()
        for index, page in enumerate(self.pages):
            if self.filter.get() == "成功" and not page.success or self.filter.get() == "失敗" and page.success:
                continue
            if query and query not in (page.url + " " + page.title + " " + page.markdown + " " + page.summary + " " + page.error).casefold():
                continue
            label = "失敗" if not page.success else "整理中" if page.summary_mode == "尚未完成" else "基本摘錄" if page.summary_mode == "基本摘錄" else "完成"
            self.table.insert("", "end", iid=str(index), values=(label, page.title or page.error[:60], page.url))
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
        else:
            self.copy_button.configure(state="disabled")
            self.file_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            if query or self.filter.get() != "全部":
                self.show_preview("請點選篩選後的結果以預覽。" if self.table.get_children() else "沒有符合條件的結果。")

    def retry_failed(self):
        failed = [page.url for page in self.pages if not page.success]
        if failed:
            self.urls.delete("1.0", "end")
            self.urls.insert("1.0", "\n".join(failed))
            self.start()

    def choose(self):
        path = filedialog.askdirectory(initialdir=self.output.get() if Path(self.output.get()).exists() else BASE)
        if path:
            self.output.set(path)

    def start(self, pasted_text=None):
        if self.worker and self.worker.is_alive():
            return
        try:
            urls = parse_urls(self.urls.get("1.0", "end")) if pasted_text is None else ["使用者貼上的文字／字幕"]
            mode = AI_MODES.get(self.ai_mode.get(), 'basic')
            model = self.model.get().strip()
            provider = self.selected_backend()
            if mode in CLOUD_PROVIDERS and not messagebox.askyesno('使用雲端摘要',
                    f'本批 {len(urls)} 個來源的擷取文字／字幕將傳送至 {LABELS[mode]}，使用模型 {model}。\n\n'
                    '每頁最多分析約 36,000 字元。若開啟畫面理解，最多 12 張關鍵影格會逐張傳送並分別核對；另有多來源比較。\n'
                    'API 可能計費，實際費用依模型及帳號而定。是否繼續？', parent=self):
                return
            delay, timeout = float(self.delay.get()), int(self.timeout.get())
            retries = int(self.retries.get())
            if not 0.5 <= delay <= 60 or not 5 <= timeout <= 180:
                raise ValueError("間隔需為 0.5–60 秒，逾時需為 5–180 秒。")
            if not 0 <= retries <= 2:
                raise ValueError("自動重試需為 0–2 次。")
            selector = self.selector.get().strip()
            if selector:
                import soupsieve
                soupsieve.compile(selector)
            if not self.output.get().strip():
                raise ValueError("請選擇儲存資料夾。")
            output = Path(self.output.get()).expanduser().resolve()
            output.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("請檢查輸入", str(exc), parent=self)
            return
        self.pages.clear()
        self.failure = ""
        self.view_only = False
        self.active_urls = urls
        self.search.set("")
        self.filter.set("全部")
        self.folder = None
        self.comparison_file = None
        self.preview_mode.set("重點摘要")
        for item in self.table.get_children():
            self.table.delete(item)
        self.total = len(urls)
        self.progress.configure(maximum=self.total, value=0)
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.open_button.configure(state="disabled")
        self.retry_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.file_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        for widget in self.inputs:
            widget.configure(state="disabled")
        self.status.set("正在啟動瀏覽器…")
        self.show_preview("正在爬取，結果會逐頁出現在上方。")
        self.save_preferences()

        frames_enabled = self.analyze_frames.get()
        visual_model = self.vision_model.get().strip() if mode == 'ollama' else model
        def work():
            try:
                asyncio.run(crawl_batch(urls, output, delay, timeout, selector, self.stop_event, lambda kind, data: self.events.put((kind, data)), retries=retries, summary_mode=mode, model=model, pasted_text=pasted_text, provider=provider, analyze_frames=frames_enabled, vision_model=visual_model))
            except Exception as exc:
                logging.exception("Crawl job failed")
                self.events.put(("fatal", str(exc)))
            finally:
                self.events.put(("done", None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("正在停止並關閉瀏覽器，已完成的結果會保留…")

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "folder":
                    self.folder = Path(data)
                    self.open_button.configure(state="normal")
                elif kind == "fetch":
                    i, url = data
                    self.status.set(f"爬取中 {i + 1}/{self.total} · {url[:100]}")
                elif kind == "page":
                    self.pages.append(data)
                    self.refresh_table()
                    item = str(len(self.pages) - 1)
                    self.progress.configure(value=len(self.pages))
                    if self.table.exists(item):
                        self.table.selection_set(item)
                        self.table.see(item)
                        self.preview()
                elif kind == "retry":
                    url, attempt = data
                    self.status.set(f"暫時連線失敗，正在重試第 {attempt} 次 · {url[:90]}")
                elif kind == "stage":
                    self.status.set(data)
                elif kind == "updated":
                    self.refresh_table()
                    self.preview()
                elif kind == "comparison":
                    self.table.selection_remove(*self.table.selection())
                    self.show_preview(data)
                    self.copy_button.configure(state="normal")
                    self.comparison_file = self.folder / "batch_summary.md" if self.folder else None
                    self.preview_mode.set("整批比較")
                    self.file_button.configure(state="normal" if self.comparison_file and self.comparison_file.is_file() else "disabled")
                elif kind == "ai_check":
                    self.check_ai_button.configure(state="normal")
                    if not self.closing:
                        messagebox.showinfo("AI 連線狀態", data, parent=self)
                elif kind == 'ai_models':
                    name, models = data
                    self.model_cache[name] = models
                    self.check_ai_button.configure(state='normal')
                    if self.current_provider == name:
                        self.model_input.configure(values=models)
                    self.status.set(f'已取得 {len(models)} 個模型，請選擇支援 JSON Schema 的文字模型；清單不保證摘要相容性。')
                elif kind == "fatal":
                    self.failure = data
                    self.show_preview(f"無法完成本次作業：\n{data}")
                    if not self.closing:
                        messagebox.showerror("執行失敗", f"{data}\n\n請查看 README 的安裝與疑難排解說明。", parent=self)
                elif kind == "done":
                    success = sum(p.success for p in self.pages)
                    label = "作業失敗" if self.failure else "已停止" if self.stop_event.is_set() else "作業結束"
                    self.status.set(f"{label} · 已處理 {len(self.pages)}/{self.total} · 成功 {success} · 失敗 {len(self.pages) - success}")
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.retry_button.configure(state="normal" if any(not p.success for p in self.pages) else "disabled")
                    for widget in self.inputs:
                        widget.configure(state="normal")
                    self.mode_input.configure(state="readonly")
                    self.save_preferences()
        except queue.Empty:
            pass
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(100, self.poll)

    def show_preview(self, text):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        for tag in self.preview_text.tag_names():
            if tag.startswith("link_"):
                self.preview_text.tag_delete(tag)
        for index, match in enumerate(re.finditer(r"https?://[^\s)<>]+", text)):
            tag = f"link_{index}"
            self.preview_text.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
            self.preview_text.tag_configure(tag, foreground="#0071e3", underline=True)
            self.preview_text.tag_bind(tag, "<Button-1>", lambda event, url=match.group(): webbrowser.open(url))
        self.preview_text.configure(state="disabled")

    def preview(self, _event=None):
        if self.preview_mode.get() in ("整批比較", "比較來源"):
            name = "batch_summary.md" if self.preview_mode.get() == "整批比較" else "batch_sources.md"
            path = self.folder / name if self.folder else None
            available = bool(path and path.is_file())
            self.copy_button.configure(state="normal" if available else "disabled")
            self.file_button.configure(state="normal" if available else "disabled")
            self.export_button.configure(state="normal" if available else "disabled")
            self.show_preview(path.read_text(encoding="utf-8")[:100000] if available else "兩個以上來源完成後，這裡會顯示共通點、差異與來源對照。")
            return
        selection = self.table.selection()
        if selection:
            page = self.pages[int(selection[0])]
            self.copy_button.configure(state="normal")
            self.file_button.configure(state="normal" if page.success and page.file else "disabled")
            self.export_button.configure(state="normal" if self.export_source() else "disabled")
            meta = f"{page.url}\nHTTP {page.status_code or '—'} · 嘗試 {page.attempts} 次 · {page.elapsed_seconds} 秒\n\n"
            if page.success and self.preview_mode.get() == "來源對照":
                source_path = (self.folder / page.sources_file).resolve() if self.folder and page.sources_file else None
                if source_path and source_path.parent == self.folder.resolve() and source_path.suffix == ".md":
                    try:
                        content = source_path.read_text(encoding="utf-8")
                    except OSError:
                        content = "來源對照檔不存在，請查看原始內容。"
                else:
                    content = "此筆結果尚未產生來源對照。"
            elif page.success and self.preview_mode.get() == "重點摘要" and (page.summary or page.summary_mode):
                content = f"方式：{page.summary_mode}\n{page.summary_warning}\n\n{page.summary or '內容已儲存，摘要尚未完成。'}\n\n來源對照：{page.sources_file}"
            else:
                content = page.markdown if page.success else f"擷取失敗\n\n{page.error}"
            self.show_preview(meta + content[:100000] + ("\n\n[預覽已截短，完整內容請查看檔案]" if len(content) > 100000 else ""))

    def copy_content(self):
        if self.preview_mode.get() in ("整批比較", "比較來源"):
            self.clipboard_clear()
            self.clipboard_append(self.preview_text.get("1.0", "end-1c"))
            return
        selected = self.table.selection()
        if not selected:
            self.clipboard_clear()
            self.clipboard_append(self.preview_text.get("1.0", "end-1c"))
            return
        if selected:
            page = self.pages[int(selected[0])]
            self.clipboard_clear()
            self.clipboard_append(self.preview_text.get("1.0", "end-1c") if self.preview_mode.get() == "來源對照" else (page.summary if self.preview_mode.get() == "重點摘要" and page.summary else page.markdown) if page.success else page.error)

    def open_markdown(self):
        if self.preview_mode.get() in ("整批比較", "比較來源") and self.folder:
            path = self.folder / ("batch_summary.md" if self.preview_mode.get() == "整批比較" else "batch_sources.md")
            if path.is_file():
                os.startfile(path)
            return
        selected = self.table.selection()
        if not selected and self.comparison_file and self.comparison_file.is_file():
            try:
                os.startfile(self.comparison_file)
            except OSError as exc:
                messagebox.showerror("無法開啟", str(exc), parent=self)
            return
        if selected and self.folder:
            page = self.pages[int(selected[0])]
            filename = page.summary_file if self.preview_mode.get() == "重點摘要" and page.summary_file else page.file
            if self.preview_mode.get() == "來源對照" and page.sources_file:
                filename = page.sources_file
            path = (self.folder / filename).resolve()
            if not path.is_relative_to(self.folder.resolve()) or path.suffix != ".md" or not path.is_file():
                messagebox.showerror("無法開啟", "Markdown 檔案不存在或路徑不正確。", parent=self)
                return
            try:
                os.startfile(path)
            except OSError as exc:
                messagebox.showerror("無法開啟", str(exc), parent=self)

    def export_source(self):
        """Return only a saved Markdown report inside the active result folder."""
        if not self.folder:
            return None
        if self.preview_mode.get() in ("整批比較", "比較來源"):
            filename = "batch_summary.md" if self.preview_mode.get() == "整批比較" else "batch_sources.md"
        else:
            selected = self.table.selection()
            if not selected:
                return None
            page = self.pages[int(selected[0])]
            filename = page.file
            if self.preview_mode.get() == "重點摘要" and page.summary_file:
                filename = page.summary_file
            elif self.preview_mode.get() == "來源對照" and page.sources_file:
                filename = page.sources_file
        try:
            path = (self.folder / filename).resolve()
            root = self.folder.resolve()
        except (OSError, TypeError):
            return None
        return path if path.is_relative_to(root) and path.suffix.lower() == ".md" and path.is_file() else None

    def export_report(self):
        source = self.export_source()
        if not source:
            messagebox.showinfo("一鍵匯出成果", "請先選擇一份已保存的報告。", parent=self)
            return
        selected = self.table.selection()
        if self.preview_mode.get() in ("整批比較", "比較來源"):
            title, source_url = "整批研究比較", ""
        elif selected:
            page = self.pages[int(selected[0])]
            title, source_url = page.title or source.stem, page.final_url or page.url
        else:
            title, source_url = source.stem, ""
        self.export_button.configure(state="disabled")
        self.status.set("正在製作 PDF、Notion、Markdown 與 Obsidian Canvas…")
        self.update_idletasks()
        try:
            result = build_deliverables(source, title, source_url)
            self.status.set(f"成果已匯出 · {result['folder'].name}")
            messagebox.showinfo("匯出完成", "已建立 PDF、Notion 匯入包、Markdown 與 Obsidian Canvas。", parent=self)
            os.startfile(result["folder"])
        except Exception as exc:
            logging.exception("Deliverable export failed")
            messagebox.showerror("匯出失敗", str(exc), parent=self)
        finally:
            self.export_button.configure(state="normal" if self.export_source() else "disabled")

    def open_evidence(self):
        selected = self.table.selection()
        if not selected or not self.folder:
            return
        page = self.pages[int(selected[0])]
        prefix = page.summary_file.split('_')[0]
        if not prefix.isdigit():
            return
        target = (self.folder / (prefix + '_frames') / 'evidence.html').resolve()
        if not target.is_relative_to(self.folder.resolve()) or not target.is_file():
            messagebox.showinfo('影格溯源', '這筆結果沒有影格資料鏈；請開啟影片畫面理解後重新整理。', parent=self)
            return
        from evidence_chain import verify_chain
        failures = verify_chain(target.parent)
        if failures:
            messagebox.showerror('來源完整性檢查失敗',
                '檔案缺失或與保存時不符，請重新產生來源資料鏈。\n' + '\n'.join(failures[:5]), parent=self)
            return
        webbrowser.open(target.as_uri())

    def open_folder(self):
        if self.folder and self.folder.exists():
            try:
                os.startfile(self.folder)
            except OSError as exc:
                messagebox.showerror("無法開啟資料夾", str(exc), parent=self)

    def close(self):
        self.save_preferences()
        self.closing = True
        if self.worker and self.worker.is_alive():
            self.stop()
            self.status.set("正在關閉瀏覽器並儲存結果…")
        else:
            self.destroy()


def packaged_smoke_test():
    """Exercise the frozen browser stack without opening Tk; writes machine-readable evidence."""
    target = sys.argv[2] if len(sys.argv) > 2 else "https://example.com/"
    result_file = DATA_DIR / "exe-smoke-test.json"
    record = {"target": target, "success": False}
    try:
        pages = asyncio.run(crawl_batch([target], DATA_DIR / "smoke-tests", .5, 30, "", threading.Event(), lambda *_: None,
                                        retries=0, summary_mode="basic", model=""))
        page = pages[0]
        record.update(success=page.success, title=page.title, status_code=page.status_code,
                      markdown_chars=len(page.markdown), error=page.error)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    result_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if record["success"] else 1


if __name__ == "__main__" and "--smoke-test" in sys.argv:
    raise SystemExit(packaged_smoke_test())
elif __name__ == "__main__":
    logging.basicConfig(filename=LOG_FILE, level=logging.WARNING, encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")
    App().mainloop()
