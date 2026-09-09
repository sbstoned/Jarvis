import os, subprocess, shutil, time, threading, re

def _pyauto():
    try:
        import pyautogui
        pyautogui.FAILSAFE=True; pyautogui.PAUSE=.06
        return pyautogui
    except Exception: return None

def _pywin():
    try:
        import pygetwindow as gw
        return gw
    except Exception: return None

APPS={
"steam":[r"C:\\Program Files (x86)\\Steam\\steam.exe",r"C:\\Program Files\\Steam\\steam.exe","steam"],
"visual studio":[r"C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\Common7\\IDE\\devenv.exe",r"C:\\Program Files\\Microsoft Visual Studio\\2022\\Professional\\Common7\\IDE\\devenv.exe"],
"vs code":["code"],"vscode":["code"],
"android studio":[r"C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe"],
"unreal":[r"C:\\Program Files\\Epic Games\\UE_5.7\\Engine\\Binaries\\Win64\\UnrealEditor.exe",r"C:\\Program Files\\Epic Games\\UE_5.6\\Engine\\Binaries\\Win64\\UnrealEditor.exe",r"C:\\Program Files\\Epic Games\\UE_5.5\\Engine\\Binaries\\Win64\\UnrealEditor.exe"],
"unreal engine":[r"C:\\Program Files\\Epic Games\\UE_5.7\\Engine\\Binaries\\Win64\\UnrealEditor.exe",r"C:\\Program Files\\Epic Games\\UE_5.6\\Engine\\Binaries\\Win64\\UnrealEditor.exe"],
"blender":[r"C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",r"C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",r"C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe","blender"],
"chrome":[r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe","chrome"],
"edge":[r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"],
"discord":[os.path.expandvars(r"%LOCALAPPDATA%\\Discord\\Update.exe")],
"epic games":[r"C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe"],
"obs":[r"C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"],
"github desktop":[os.path.expandvars(r"%LOCALAPPDATA%\\GitHubDesktop\\GitHubDesktop.exe")],
"explorer":["explorer.exe"],"file explorer":["explorer.exe"],"notepad":["notepad.exe"],
"calculator":["calc.exe"],"terminal":["powershell.exe"],"powershell":["powershell.exe"],"command prompt":["cmd.exe"]}

def _resolve(x):
    x=os.path.expandvars(os.path.expanduser(x))
    if os.path.isabs(x) and os.path.exists(x): return x
    return shutil.which(x)

def _spawn_application(target, alias):
    try:
        flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            if os.name == "nt"
            else 0
        )
        cmd = (
            [target, "--processStart", "Discord.exe"]
            if alias == "discord" and target.lower().endswith("update.exe")
            else [target]
        )
        subprocess.Popen(
            cmd,
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception:
        pass


def open_application(name):
    key = str(name or "").lower().strip()

    for alias, candidates in APPS.items():
        if key == alias or key in alias or alias in key:
            for candidate in candidates:
                target = _resolve(candidate)
                if target:
                    # App startup happens on a daemon thread. Jarvis immediately
                    # returns to listening even if the application itself takes
                    # several seconds to initialize.
                    import threading
                    threading.Thread(
                        target=_spawn_application,
                        args=(target, alias),
                        daemon=True,
                        name=f"JarvisLaunch-{alias.replace(' ', '-')}",
                    ).start()
                    return True, f"Opening {alias}."

    return False, f"I couldn't find or open {name}."


def focus_window(title):
    gw=_pywin()
    if not gw: return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    wanted=str(title).lower()
    wins=[w for w in gw.getAllWindows() if getattr(w,"title","") and wanted in w.title.lower()]
    if not wins:return False,f"I couldn't find an open window matching {title}."
    w=wins[0]
    try:
        if w.isMinimized:w.restore()
        w.activate(); return True,f"Focused {w.title}."
    except Exception as e:return False,f"Could not focus that window: {e}"

def type_text(text):
    p=_pyauto()
    if not p:return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    try:p.write(str(text),interval=.015);return True,"Typed the text."
    except Exception as e:return False,f"Could not type text: {e}"

def hotkey(keys):
    p=_pyauto()
    if not p:return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    try:p.hotkey(*[str(k).lower() for k in keys]);return True,"Pressed "+" + ".join(keys)+"."
    except Exception as e:return False,f"Could not press shortcut: {e}"

def press_key(key):
    p=_pyauto()
    if not p:return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    try:p.press(str(key).lower());return True,f"Pressed {key}."
    except Exception as e:return False,f"Could not press key: {e}"

def close_active_window(): return hotkey(["alt","f4"])


def open_web(target):
    """Open a URL or Google search in Chrome without blocking Jarvis."""
    import urllib.parse, re, threading
    raw=str(target or '').strip()
    if not raw:
        return False,"Tell me what page or topic to open."
    if re.match(r'^https?://', raw, re.I):
        url=raw
    elif re.match(r'^[\w.-]+\.[a-z]{2,}(?:/.*)?$', raw, re.I):
        url='https://'+raw
    else:
        url='https://www.google.com/search?q='+urllib.parse.quote_plus(raw)
    chrome=None
    for c in APPS.get('chrome',[]):
        chrome=_resolve(c)
        if chrome: break
    try:
        if chrome:
            threading.Thread(target=lambda: subprocess.Popen([chrome,url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL),daemon=True).start()
        else:
            import webbrowser; webbrowser.open(url)
        return True,f"Opening {raw} in Chrome."
    except Exception as e:
        return False,f"I couldn't open that page: {e}"


def browser_scroll(direction='down', amount=6):
    p=_pyauto()
    if not p:return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    try:
        direction=str(direction).lower(); amount=max(1,min(30,int(amount or 6)))
        p.scroll(amount if direction in {'up','top'} else -amount)
        return True,f"Scrolled {direction}."
    except Exception as e:return False,f"I couldn't scroll: {e}"


def browser_back(): return hotkey(['alt','left'])
def browser_forward(): return hotkey(['alt','right'])

def browser_address(target):
    p=_pyauto()
    if not p:return False,"Run SETUP_DESKTOP_AUTOMATION.bat first."
    try:
        p.hotkey('ctrl','l'); p.write(str(target),interval=.01); p.press('enter')
        return True,f"Navigating to {target}."
    except Exception as e:return False,f"I couldn't navigate there: {e}"


def _clipboard_get():
    try:
        import tkinter as tk
        root=tk.Tk(); root.withdraw()
        try:return str(root.clipboard_get())
        finally:root.destroy()
    except Exception:
        try:
            import pyperclip
            return str(pyperclip.paste())
        except Exception:return ""

def _clipboard_set(value):
    try:
        import tkinter as tk
        root=tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(str(value)); root.update(); root.destroy()
        return True
    except Exception:
        try:
            import pyperclip; pyperclip.copy(str(value)); return True
        except Exception:return False

def browser_current_url():
    p=_pyauto()
    if not p:return False,"Desktop automation is unavailable."
    old=_clipboard_get()
    try:
        p.hotkey("ctrl","l"); time.sleep(.08); p.hotkey("ctrl","c"); time.sleep(.12)
        value=_clipboard_get().strip(); p.press("esc")
        if old:_clipboard_set(old)
        return (True,value) if value else (False,"I couldn't read the current URL.")
    except Exception as exc:return False,f"I couldn't read the current URL: {exc}"

def browser_read_page(max_chars=16000):
    p=_pyauto()
    if not p:return False,"Desktop automation is unavailable."
    old=_clipboard_get()
    try:
        p.hotkey("ctrl","a"); time.sleep(.12); p.hotkey("ctrl","c"); time.sleep(.18)
        value=_clipboard_get(); p.press("esc")
        if old:_clipboard_set(old)
        value=re.sub(r"\n{3,}","\n\n",str(value or "")).strip()
        return (True,value[:max_chars]) if value else (False,"I couldn't read text from the active page.")
    except Exception as exc:return False,f"I couldn't read the active page: {exc}"

def browser_find(text):
    p=_pyauto()
    if not p:return False,"Desktop automation is unavailable."
    try:p.hotkey("ctrl","f");p.write(str(text),interval=.015);p.press("enter");return True,f"Searching this page for {text}."
    except Exception as exc:return False,f"I couldn't search the page: {exc}"

def browser_new_tab():return hotkey(["ctrl","t"])
def browser_close_tab():return hotkey(["ctrl","w"])
def browser_next_tab():return hotkey(["ctrl","tab"])
def browser_previous_tab():return hotkey(["ctrl","shift","tab"])
def browser_zoom(direction="in"):
    if direction=="out":return hotkey(["ctrl","-"])
    if direction=="reset":return hotkey(["ctrl","0"])
    return hotkey(["ctrl","+"])

def mouse_click(x=None,y=None,clicks=1):
    p=_pyauto()
    if not p:return False,"Desktop automation is unavailable."
    try:
        if x is None or y is None:p.click(clicks=max(1,min(3,int(clicks))))
        else:p.click(int(x),int(y),clicks=max(1,min(3,int(clicks))),interval=.08)
        return True,"Clicked."
    except Exception as exc:return False,f"I couldn't click there: {exc}"

def mouse_move(x,y,duration=.2):
    p=_pyauto()
    if not p:return False,"Desktop automation is unavailable."
    try:p.moveTo(int(x),int(y),duration=max(0,min(2,float(duration))));return True,f"Moved pointer to {x}, {y}."
    except Exception as exc:return False,f"I couldn't move the pointer: {exc}"

def window_list():
    gw=_pywin()
    if not gw:return False,"Window automation is unavailable."
    try:
        titles=[]
        for w in gw.getAllWindows():
            t=str(getattr(w,"title","") or "").strip()
            if t and t not in titles:titles.append(t)
        return True,titles[:40]
    except Exception as exc:return False,f"I couldn't enumerate windows: {exc}"
