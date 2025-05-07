"""
InstallerPro v4  –  Humberto Medina  ·  Mayo 2025

◉ Multi‑idioma (Español / English) – selector en menú
◉ Multi‑proyecto  –  añade / actualiza / elimina proyectos Git
◉ Auto‑descubrimiento – detecta carpetas con .git en C:\Workspace
◉ Maneja ‘dubious ownership’, credenciales, Git ausente
"""

import os, subprocess, shutil, webbrowser, json, tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter import filedialog
import pathlib

# ============ Configuración global ============
WORKSPACE = r"C:\Workspace"
DB_FILE   = os.path.join(WORKSPACE, "_projects.json")

LANG = {
    'es': {
        'title': "Instalador Automático de Entorno",
        'add':   "Añadir proyecto",
        'remove':"Eliminar proyecto",
        'update':"Actualizar seleccionados",
        'exit':  "Salir",
        'name?': "Nombre del proyecto:",
        'url?':  "URL del repositorio Git (HTTPS):",
        'ok':    "Proyecto listo en:\n{}",
        'git?':  "Git no está instalado.\nDescárgalo en https://git-scm.com",
        'login': "Autoriza tu cuenta GitHub en el navegador.\nPulsa Aceptar para continuar.",
        'nothing': "No hay proyectos seleccionados.",
        'unknown': "(desconocida)",
        'menu_lang': "Idioma",
        'menu_es':   "Español",
        'menu_en':   "English"
    },
    'en': {
        'title': "Automatic Environment Installer",
        'add':   "Add project",
        'remove':"Remove project",
        'update':"Update selected",
        'exit':  "Exit",
        'name?': "Project name:",
        'url?':  "Git repository URL (HTTPS):",
        'ok':    "Project ready at:\n{}",
        'git?':  "Git is not installed.\nDownload it from https://git-scm.com",
        'login': "Authorize GitHub account in browser.\nPress OK to continue.",
        'nothing':"No project selected.",
        'unknown': "(unknown)",
        'menu_lang': "Language",
        'menu_es':   "Spanish",
        'menu_en':   "English"
    }
}
# idioma inicial
CURRENT = 'es'
TXT = LANG[CURRENT]

# ============ Funciones utilitarias Git ============
def run(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT,
                                      text=True, shell=False)
        return True, out.strip()
    except subprocess.CalledProcessError as e:
        return False, e.output.strip()

def need_auth(text:str)->bool:
    t=text.lower()
    return ("authentication" in t or "could not read" in t or "permission denied" in t)

def ensure_git():
    ok,_ = run(["git","--version"])
    if not ok:
        messagebox.showerror("Git", TXT['git?'])
        raise SystemExit

def safe_dir(path):
    run(["git","config","--global","--add","safe.directory", path.replace("\\","/")])

def auth_flow():
    webbrowser.open("https://github.com/login")
    messagebox.showinfo("Login", TXT['login'])

def clone_or_pull(name:str, url:str):
    dest = os.path.join(WORKSPACE, name)
    safe_dir(dest)

    if not os.path.exists(dest) or not os.path.exists(os.path.join(dest,".git")):
        if os.path.exists(dest): shutil.rmtree(dest, ignore_errors=True)
        ok,out = run(["git","clone",url,dest])
        if not ok and need_auth(out):
            auth_flow(); ok,out = run(["git","clone",url,dest])
        if not ok: raise RuntimeError(out)
    else:
        ok,out = run(["git","-C",dest,"pull"])
        if not ok and need_auth(out):
            auth_flow(); ok,out = run(["git","-C",dest,"pull"])
        if not ok: raise RuntimeError(out)
    return dest

# ============ Base de datos de proyectos ============
def load_db()->dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE,"r",encoding="utf-8") as fh:
            base = json.load(fh)
    else:
        base={}
    base = auto_discover(base)
    save_db(base)
    return base

def save_db(db:dict):
    os.makedirs(WORKSPACE, exist_ok=True)
    with open(DB_FILE,"w",encoding="utf-8") as fh:
        json.dump(db, fh, indent=2)

def auto_discover(db:dict)->dict:
    """Añade a db las carpetas con .git no registradas."""
    if not os.path.isdir(WORKSPACE): return db
    for entry in os.listdir(WORKSPACE):
        path = os.path.join(WORKSPACE, entry)
        if entry.startswith('_') or not os.path.isdir(path): continue
        if entry in db: continue
        if os.path.isdir(os.path.join(path,".git")):
            ok, out = run(["git","-C",path,"config","--get","remote.origin.url"])
            db[entry]= out if ok and out else TXT['unknown']
    return db

# ============ GUI callbacks ============
def refresh_list():
    listbox.delete(0,tk.END)
    for k in sorted(load_db().keys()):
        listbox.insert(tk.END, k)

def add_project():
    name = simpledialog.askstring("name", TXT['name?'])
    if not name: return
    url  = simpledialog.askstring("url", TXT['url?'])
    if not url: return
    db=load_db(); db[name]=url; save_db(db); refresh_list()

def remove_project():
    sel=list(listbox.curselection())
    if not sel: return
    db=load_db()
    for idx in reversed(sel):
        name=listbox.get(idx)
        listbox.delete(idx)
        db.pop(name,None)
    save_db(db)

def update_selected():
    sel=list(listbox.curselection())
    if not sel:
        messagebox.showinfo("Info", TXT['nothing']); return
    ensure_git()
    db=load_db()
    for idx in sel:
        name=listbox.get(idx); url=db[name]
        try:
            path=clone_or_pull(name,url)
            messagebox.showinfo("OK", TXT['ok'].format(path))
        except RuntimeError as e:
            messagebox.showerror("Git error", str(e))

def set_language(lang_code):
    global CURRENT, TXT
    CURRENT=lang_code; TXT=LANG[CURRENT]
    # actualizar textos UI dinámicamente
    root.title("InstallerPro")
    title_lbl.config(text=TXT['title'])
    add_btn.config(text=TXT['add'])
    rem_btn.config(text=TXT['remove'])
    upd_btn.config(text=TXT['update'])
    exit_btn.config(text=TXT['exit'])
    refresh_list()

# ============ GUI ============
root=tk.Tk(); root.title("InstallerPro"); root.geometry("480x400"); root.resizable(False,False)

# Menú superior
menubar=tk.Menu(root)
lang_menu=tk.Menu(menubar, tearoff=0)
lang_menu.add_command(label=LANG['es']['menu_es'], command=lambda:set_language('es'))
lang_menu.add_command(label=LANG['en']['menu_en'], command=lambda:set_language('en'))
menubar.add_cascade(label=LANG['es']['menu_lang'], menu=lang_menu)
root.config(menu=menubar)

title_lbl=tk.Label(root, text=TXT['title'], font=("Segoe UI",14,"bold"))
title_lbl.pack(pady=12)

frame=tk.Frame(root); frame.pack()
scroll=tk.Scrollbar(frame, orient="vertical")
listbox=tk.Listbox(frame, selectmode=tk.EXTENDED, width=42, height=8, yscrollcommand=scroll.set)
scroll.config(command=listbox.yview); scroll.pack(side="right", fill="y"); listbox.pack(side="left")

add_btn=tk.Button(root, text=TXT['add'], width=22, command=add_project);   add_btn.pack(pady=4)
rem_btn=tk.Button(root, text=TXT['remove'], width=22, command=remove_project); rem_btn.pack(pady=4)
upd_btn=tk.Button(root, text=TXT['update'], width=22, command=update_selected); upd_btn.pack(pady=6)
exit_btn=tk.Button(root, text=TXT['exit'], width=22, command=root.destroy);   exit_btn.pack(pady=4)

refresh_list()
root.mainloop()
