"""LocalCrawler: a local Traditional Chinese desktop crawler."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import webbrowser
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import Page, crawl_batch, load_results, parse_urls
from insights import DEFAULT_MODEL
from ai_providers import AIProviderConfig, CLOUD_PROVIDERS, LABELS, ProviderError, create_provider

AI_MODES = {'本機 AI（Ollama）': 'ollama', '基本摘錄（免模型）': 'basic', 'OpenAI API': 'openai', 'Gemini API': 'gemini'}

BASE = Path(__file__).resolve().parent
PREFERENCES = BASE / "settings.json"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LocalCrawler 3.2 預覽版 · 把來源變成重點")
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
        self.output = tk.StringVar(value=str(BASE / "downloads"))
        self.delay = tk.StringVar(value="1")
        self.timeout = tk.StringVar(value="30")
        self.selector = tk.StringVar()
        self.retries = tk.StringVar(value="1")
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
            self.last_folder = data.get("last_folder", "")
            models = data.get('provider_models', {})
            if isinstance(models, dict):
                self.provider_models.update({k: v for k, v in models.items() if k in self.provider_models and isinstance(v, str)})
            if data.get("settings_version") not in ('3.1', '3.2') and self.model.get() == "qwen2.5:3b":
                self.model.set(DEFAULT_MODEL)
        except (OSError, ValueError, AttributeError):
            pass

    def save_preferences(self):
        try:
            data = {key: getattr(self, key).get() for key in ("output", "delay", "timeout", "selector", "retries", "ai_mode", "model")}
            self.provider_models[AI_MODES.get(self.ai_mode.get(), 'ollama')] = self.model.get().strip()
            data['provider_models'] = self.provider_models
            data["settings_version"] = "3.2"
            data["last_folder"] = str(self.folder) if self.folder else self.last_folder
            temp = PREFERENCES.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(PREFERENCES)
        except OSError:
            logging.exception("Could not save settings")

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f5f7")
        style.configure("TLabel", background="#f5f5f7", foreground="#1d1d1f", font=("Microsoft JhengHei UI", 10))
        style.configure("TButton", font=("Microsoft JhengHei UI", 10), padding=(14, 8), borderwidth=0, background="#e8e8ed")
        style.configure("Accent.TButton", background="#0071e3", foreground="white")
        style.configure("Treeview", borderwidth=0, background="white", fieldbackground="white")
        style.map("Accent.TButton", background=[("active", "#174899"), ("disabled", "#98a6bb")])
        style.configure("Treeview", rowheight=30, font=("Microsoft JhengHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft JhengHei UI", 10, "bold"))
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x")
        ttk.Label(header, text="LocalCrawler", font=("Segoe UI", 24, "bold")).pack(side="left")
        ttk.Label(header, text="3.2   /   YOUR RESEARCH", foreground="#86868b").pack(side="right", pady=(12, 0))
        ttk.Label(root, text="把來源變成重點。影片筆記、文章摘要，一次整理。", foreground="#6e6e73").pack(anchor="w", pady=(4, 16))
        input_bar = ttk.Frame(root)
        input_bar.pack(fill="x")
        ttk.Label(input_bar, text="貼上連結，每行一個", font=("Microsoft JhengHei UI", 11, "bold")).pack(side="left")
        self.import_button = ttk.Button(input_bar, text="匯入網址 .txt", command=self.import_urls)
        self.import_button.pack(side="right")
        self.paste_button = ttk.Button(input_bar, text="貼上文字／字幕", command=self.paste_text)
        self.paste_button.pack(side="right", padx=8)
        self.urls = tk.Text(root, height=4, wrap="none", font=("Consolas", 11), relief="flat", padx=12, pady=10, undo=True)
        self.urls.pack(fill="x", pady=8)
        self.urls.insert("1.0", "https://example.com")
        self.advanced = ttk.Frame(root)
        self.advanced_toggle = ttk.Button(root, text="設定與模型 ▸", command=self.toggle_advanced)
        self.advanced_toggle.pack(anchor="w", pady=(0, 6))
        settings = ttk.Frame(self.advanced)
        settings.pack(fill="x", pady=(2, 8))
        ttk.Label(settings, text="間隔（秒）").pack(side="left")
        self.delay_input = ttk.Spinbox(settings, from_=0.5, to=60, increment=0.5, textvariable=self.delay, width=5)
        self.delay_input.pack(side="left", padx=(6, 18))
        ttk.Label(settings, text="逾時（秒）").pack(side="left")
        self.timeout_input = ttk.Spinbox(settings, from_=5, to=180, textvariable=self.timeout, width=5)
        self.timeout_input.pack(side="left", padx=(6, 18))
        ttk.Label(settings, text="CSS 範圍（選填，如 article）").pack(side="left")
        self.selector_input = ttk.Entry(settings, textvariable=self.selector, width=12)
        self.selector_input.pack(side="left", padx=6, fill="x", expand=True)
        ttk.Label(settings, text="自動重試").pack(side="left", padx=(8, 4))
        self.retries_input = ttk.Spinbox(settings, from_=0, to=2, textvariable=self.retries, width=3)
        self.retries_input.pack(side="left")
        ai_bar = ttk.Frame(self.advanced)
        ai_bar.pack(fill="x", pady=(2, 8))
        ttk.Label(ai_bar, text="摘要方式").pack(side="left")
        self.mode_input = ttk.Combobox(ai_bar, textvariable=self.ai_mode, values=list(AI_MODES), state="readonly", width=21)
        self.mode_input.bind('<<ComboboxSelected>>', self.change_provider)
        self.mode_input.pack(side="left", padx=8)
        ttk.Label(ai_bar, text="模型 ID").pack(side="left")
        self.model_input = ttk.Combobox(ai_bar, textvariable=self.model, width=22)
        self.model_input.pack(side="left", padx=8)
        self.check_ai_button = ttk.Button(ai_bar, text="更新模型", command=self.check_ai)
        self.check_ai_button.pack(side="left")
        self.key_button = ttk.Button(ai_bar, text="API 金鑰", command=self.key_dialog)
        self.key_button.pack(side='left', padx=5)
        self.ai_hint = ttk.Label(self.advanced, text=self.provider_hint(), foreground='#66738b', wraplength=970)
        self.ai_hint.pack(anchor='w', pady=(0, 8))
        destination = ttk.Frame(self.advanced)
        destination.pack(fill="x")
        ttk.Label(destination, text="儲存位置").pack(side="left")
        self.output_input = ttk.Entry(destination, textvariable=self.output)
        self.output_input.pack(side="left", padx=8, fill="x", expand=True)
        self.choose_button = ttk.Button(destination, text="選擇資料夾", command=self.choose)
        self.choose_button.pack(side="left")
        actions = ttk.Frame(root)
        self.actions = actions
        actions.pack(fill="x", pady=12)
        self.start_button = ttk.Button(actions, text="開始整理", style="Accent.TButton", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="停止", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(actions, text="開啟結果資料夾", command=self.open_folder, state="disabled")
        self.open_button.pack(side="left")
        self.retry_button = ttk.Button(actions, text="重試失敗項目", command=self.retry_failed, state="disabled")
        self.retry_button.pack(side="left", padx=8)
        ttk.Label(actions, text="Markdown  ·  JSON  ·  CSV", foreground="#66738b").pack(side="right")
        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x")
        ttk.Label(root, textvariable=self.status, wraplength=960).pack(anchor="w", pady=(7, 12))
        filter_bar = ttk.Frame(root)
        filter_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_bar, text="搜尋結果").pack(side="left")
        search_input = ttk.Entry(filter_bar, textvariable=self.search, width=26)
        search_input.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Combobox(filter_bar, textvariable=self.filter, values=["全部", "成功", "失敗"], state="readonly", width=6).pack(side="left", padx=4)
        self.history_button = ttk.Button(filter_bar, text="開啟歷史結果", command=self.open_history)
        self.history_button.pack(side="right")
        self.search.trace_add("write", lambda *_: self.refresh_table())
        self.filter.trace_add("write", lambda *_: self.refresh_table())
        panes = ttk.Panedwindow(root, orient="vertical")
        panes.pack(fill="both", expand=True)
        table_frame = ttk.Frame(panes)
        panes.add(table_frame, weight=1)
        self.table = ttk.Treeview(table_frame, columns=("state", "title", "url"), show="headings", height=5)
        for key, title, width in [("state", "狀態", 80), ("title", "網頁標題", 240), ("url", "網址", 550)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=60, stretch=key != "state")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.preview)
        preview_frame = ttk.Frame(panes)
        panes.add(preview_frame, weight=2)
        preview_bar = ttk.Frame(preview_frame)
        preview_bar.pack(fill="x", pady=(8, 6))
        ttk.Label(preview_bar, text="閱讀報告", font=("Microsoft JhengHei UI", 11, "bold")).pack(side="left")
        ttk.Combobox(preview_bar, textvariable=self.preview_mode, values=["重點摘要", "原始內容", "來源對照", "整批比較", "比較來源"], width=10, state="readonly").pack(side="left", padx=12)
        self.preview_mode.trace_add("write", lambda *_: self.preview())
        self.copy_button = ttk.Button(preview_bar, text="複製內容", command=self.copy_content, state="disabled")
        self.copy_button.pack(side="right")
        self.file_button = ttk.Button(preview_bar, text="開啟 Markdown", command=self.open_markdown, state="disabled")
        self.file_button.pack(side="right", padx=6)
        self.preview_text = tk.Text(preview_frame, wrap="word", height=8, font=("Microsoft JhengHei UI", 11), relief="flat", padx=12, pady=10, state="disabled")
        preview_scroll = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side="right", fill="y")
        self.preview_text.pack(fill="both", expand=True)
        self.show_preview("爬取完成後，點選上方結果即可預覽文字。\n\n每次執行會建立獨立資料夾，保留先前結果。")
        ttk.Label(root, text="依 robots.txt 檢查存取規則；僅處理輸入的網址，不自動追蹤整站連結。", foreground="#66738b", font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(12, 0))
        self.inputs = [self.urls, self.delay_input, self.timeout_input, self.selector_input, self.output_input, self.choose_button, self.import_button, self.retries_input, self.history_button]
        self.inputs.extend([self.mode_input, self.model_input, self.paste_button, self.key_button, self.check_ai_button])

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget()
            self.advanced_toggle.configure(text="設定與模型 ▸")
        else:
            self.advanced.pack(fill="x", before=self.actions)
            self.advanced_toggle.configure(text="設定與模型 ▾")

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
                    '每頁最多分析約 36,000 字元。影片分段生成後會逐項核對，另有多來源比較；每次格式失敗最多重試一次。\n'
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
        for widget in self.inputs:
            widget.configure(state="disabled")
        self.status.set("正在啟動瀏覽器…")
        self.show_preview("正在爬取，結果會逐頁出現在上方。")
        self.save_preferences()

        def work():
            try:
                asyncio.run(crawl_batch(urls, output, delay, timeout, selector, self.stop_event, lambda kind, data: self.events.put((kind, data)), retries=retries, summary_mode=mode, model=model, pasted_text=pasted_text, provider=provider))
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
            self.show_preview(path.read_text(encoding="utf-8")[:100000] if available else "兩個以上來源完成後，這裡會顯示共通點、差異與來源對照。")
            return
        selection = self.table.selection()
        if selection:
            page = self.pages[int(selection[0])]
            self.copy_button.configure(state="normal")
            self.file_button.configure(state="normal" if page.success and page.file else "disabled")
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
            if path.parent != self.folder.resolve() or path.suffix != ".md" or not path.is_file():
                messagebox.showerror("無法開啟", "Markdown 檔案不存在或路徑不正確。", parent=self)
                return
            try:
                os.startfile(path)
            except OSError as exc:
                messagebox.showerror("無法開啟", str(exc), parent=self)

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


if __name__ == "__main__":
    logging.basicConfig(filename=BASE / "app.log", level=logging.WARNING, encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")
    App().mainloop()
