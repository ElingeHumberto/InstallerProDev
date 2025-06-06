# installerpro/ui_dialogs.py
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class HelpPopup:
    def __init__(self, anchor_widget, title_key, help_text_key, t_func):
        self.anchor_widget = anchor_widget
        self.t = t_func
        self.title = self.t(title_key)
        self.help_text = self.t(help_text_key, fallback=self.t("help.not_available_placeholder"))
        self.popup_window = None
        
        if not self.help_text.strip(): return
        self._create_popup()

    def _create_popup(self):
        if self.popup_window and self.popup_window.winfo_exists(): return
        try:
            if not self.anchor_widget.winfo_exists(): return
            self.anchor_widget.update_idletasks()
        except tk.TclError: return

        self.popup_window = tk.Toplevel(self.anchor_widget)
        self.popup_window.title(self.title)
        self.popup_window.transient(self.anchor_widget.winfo_toplevel())
        
        main_frame = tk.Frame(self.popup_window, bg="#F0F0F0", padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        content_message = tk.Message(main_frame, text=self.help_text, bg="#F0F0F0", fg="#202020",
                                     width=280, justify=tk.LEFT, font=("tahoma", 9))
        content_message.pack(fill=tk.BOTH, expand=True)

        self.popup_window.update_idletasks()
        self._position_window()
        self.popup_window.deiconify()
        self.popup_window.lift()
        self.popup_window.protocol("WM_DELETE_WINDOW", self.close)
        self.popup_window.bind("<Escape>", lambda e: self.close())

    def _position_window(self):
        popup_width = self.popup_window.winfo_reqwidth()
        popup_height = self.popup_window.winfo_reqheight()
        anchor_x = self.anchor_widget.winfo_rootx()
        anchor_y = self.anchor_widget.winfo_rooty()
        anchor_width = self.anchor_widget.winfo_width()
        screen_width = self.popup_window.winfo_screenwidth()
        screen_height = self.popup_window.winfo_screenheight()
        x_pos = anchor_x + anchor_width + 5
        if x_pos + popup_width > screen_width: x_pos = anchor_x - popup_width - 5
        if x_pos < 5: x_pos = 5
        y_pos = anchor_y
        if y_pos + popup_height > screen_height: y_pos = screen_height - popup_height - 5
        if y_pos < 5: y_pos = 5
        self.popup_window.geometry(f"+{x_pos}+{y_pos}")

    def close(self):
        if self.popup_window and self.popup_window.winfo_exists():
            try: self.popup_window.destroy()
            except tk.TclError: pass
        self.popup_window = None

class AddProjectDialog(tk.Toplevel):
    def __init__(self, master, t_func, base_folder):
        super().__init__(master)
        self.t = t_func
        self.base_folder = base_folder
        self.current_help_popup = None
        self.result = None

        self.title(self.t("Add Project Title"))
        self.transient(master)
        
        self._create_widgets()
        self._center_window()
        self.name_entry.focus_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.name_entry.bind("<KeyRelease>", self._update_local_path_on_name_change)
        self.bind("<Destroy>", self._on_dialog_destroy, add='+')

    def _on_cancel(self):
        if self.current_help_popup: self.current_help_popup.close()
        self.destroy()

    def _on_dialog_destroy(self, event=None):
        if event and event.widget != self: return
        if self.current_help_popup: self.current_help_popup.close()

    def _show_field_help(self, anchor_widget, help_key):
        if self.current_help_popup: self.current_help_popup.close()
        self.current_help_popup = HelpPopup(anchor_widget, "help.popup_title", help_key, self.t)
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        fields = {'name': "Project Name", 'local_path': "Local Path Label",
                  'repo_url': "Repository URL Label", 'branch': "Branch Optional Label"}
        self.entries = {}
        for i, (key, label_key) in enumerate(fields.items()):
            help_key = f"tooltip.{key}_entry"
            ttk.Label(frame, text=self.t(label_key)).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            
            entry = ttk.Entry(frame, width=40)
            if key == "local_path":
                self.local_path_var = tk.StringVar()
                entry.config(textvariable=self.local_path_var)
            
            self.entries[key] = entry
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            
            info_button = ttk.Button(frame, text="ⓘ", width=2, command=lambda w=entry, hk=help_key: self._show_field_help(w, hk))
            info_button.grid(row=i, column=2, padx=(0, 5), pady=5, sticky="w")
            
            if key == "local_path":
                ttk.Button(frame, text=self.t("Browse Button"), command=self._browse_local_path).grid(row=i, column=3, padx=5, pady=5)
        
        self.name_entry = self.entries['name']
        self._update_local_path_on_name_change()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=len(fields), column=0, columnspan=4, pady=10)
        ttk.Button(button_frame, text=self.t("Add Button"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=self.t("Cancel Button"), command=self._on_cancel).pack(side=tk.LEFT, padx=5)

    def _update_local_path_on_name_change(self, event=None):
        name = self.name_entry.get().strip()
        new_path = os.path.join(self.base_folder, name if name else self.t("New Project Default Name"))
        self.local_path_var.set(new_path)

    def _browse_local_path(self):
        folder = filedialog.askdirectory(parent=self, initialdir=self.base_folder, title=self.t("Select Local Path Title"))
        if folder: self.local_path_var.set(folder)

    def _on_ok(self):
        if self.current_help_popup: self.current_help_popup.close()
        name = self.entries['name'].get().strip()
        local_path = self.local_path_var.get().strip()
        repo_url = self.entries['repo_url'].get().strip()
        
        if not name or not local_path or not repo_url:
            messagebox.showerror(self.t("Input Error"), self.t("Input error empty fields message"))
            return
            
        self.result = {'name': name, 'local_path_full': local_path, 'repo_url': repo_url, 'branch': self.entries['branch'].get().strip() or 'main'}
        self.destroy()

    def exec_(self):
        self.wait_window(self)
        return self.result

    def _center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width()//2) - (self.winfo_reqwidth()//2)
        y = self.master.winfo_y() + (self.master.winfo_height()//2) - (self.winfo_reqheight()//2)
        self.geometry(f"+{x}+{y}")

class Tooltip:
    """
    Crea un tooltip (mensaje emergente) para un widget de tkinter.
    """
    def __init__(self, widget, text_key, t_func):
        self.widget = widget
        self.text_key = text_key
        self.t = t_func
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.t(self.text_key):
            return

        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.t(self.text_key),
                         background="#FFFFE0", relief="solid", borderwidth=1,
                         font=("tahoma", 8, "normal"), wraplength=200)
        label.pack(ipadx=5, ipady=3)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None