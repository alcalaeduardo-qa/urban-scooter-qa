"""
launcher.py — Urban Scooter QA Launcher
Selecciona la tarea, actualiza el servidor en .env y ejecuta los tests.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext

# ── Rutas ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
PYTHON = ROOT / ".venv" / "bin" / "python"

# ── Definición de tareas ───────────────────────────────────────────────────────
TASKS = [
    {
        "numero": "Tarea 1",
        "titulo": "Happy Path",
        "descripcion": "Flujo E2E completo: crea courier y pedido vía web (Opera),\n"
                       "acepta y completa en móvil, verifica en DB y web (Chrome).",
        "archivo": "tests/test_tarea_5_happy_path.py",
        "marker": "tarea5",
    },
    {
        "numero": "Tarea 2",
        "titulo": 'Lista de comprobación "estado del pedido"',
        "descripcion": "Verifica que todos los elementos de la pantalla de estado\n"
                       "del pedido sean visibles y funcionen correctamente.",
        "archivo": "tests/test_tarea_2_checklist.py",
        "marker": "tarea2",
    },
    {
        "numero": "Tarea 3",
        "titulo": 'Pruebas de validación de datos "Hacer pedido"',
        "descripcion": "Valida los tipos y límites de datos aceptados por\n"
                       "el formulario de creación de pedido.",
        "archivo": "tests/test_tarea_2_validacion_datos.py",
        "marker": "validation",
    },
    {
        "numero": "Tarea 4",
        "titulo": "Pruebas de aplicación web",
        "descripcion": "Casos de prueba del formulario web: happy path\n"
                       "y casos de borde para el flujo de pedido.",
        "archivo": "tests/test_tarea_3_cases.py",
        "marker": "tarea3",
    },
    {
        "numero": "Tarea 5",
        "titulo": "Lista de comprobación api-backend",
        "descripcion": "Comprueba los endpoints de la API REST (courier y pedidos)\n"
                       "validando códigos de respuesta y datos en DB.",
        "archivo": "tests/test_tarea_4_checklist.py",
        "marker": "tarea4",
    },
]

# ── Colores ────────────────────────────────────────────────────────────────────
BG          = "#1e1e2e"
BG_CARD     = "#2a2a3e"
ACCENT      = "#7c6af7"
ACCENT_DARK = "#5a4bd1"
TEXT        = "#e0e0f0"
TEXT_DIM    = "#9090b0"
SUCCESS     = "#4caf50"
ERROR       = "#f44336"
WARNING     = "#ff9800"


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_url(raw: str) -> tuple[str, str, str] | None:
    """Extrae (base_url, api_url, ssh_user) desde la URL del servidor."""
    url = raw.strip().rstrip("/")
    # Acepta con o sin https://
    if not url.startswith("http"):
        url = "https://" + url
    match = re.match(r"https?://([^/]+)", url)
    if not match:
        return None
    host = match.group(1)                        # cnt-xxxx.containerhub...
    subdomain = host.split(".")[0]               # cnt-xxxx
    base_url = f"https://{host}"
    api_url  = f"https://{host}/api/v1"
    return base_url, api_url, subdomain


def _update_env(base_url: str, api_url: str, ssh_user: str) -> None:
    """Reemplaza SERVER_BASE_URL, API_BASE_URL y SSH_USER en .env."""
    text = ENV_FILE.read_text(encoding="utf-8")

    def _replace(key: str, value: str, content: str) -> str:
        return re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)

    text = _replace("SERVER_BASE_URL", base_url, text)
    text = _replace("API_BASE_URL",    api_url,  text)
    text = _replace("SSH_USER",        ssh_user, text)
    ENV_FILE.write_text(text, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Ventana de output
# ══════════════════════════════════════════════════════════════════════════════

class OutputWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, task: dict) -> None:
        super().__init__(parent)
        self.title(f"Ejecutando — {task['numero']}: {task['titulo']}")
        self.configure(bg=BG)
        self.geometry("900x600")
        self.resizable(True, True)

        # Header
        header = tk.Frame(self, bg=ACCENT, pady=8)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"  {task['numero']} — {task['titulo']}",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=12)

        # Output area
        self._txt = scrolledtext.ScrolledText(
            self, bg="#0d0d1a", fg="#c8ffc8",
            font=("Courier New", 10),
            wrap="word", state="disabled",
            insertbackground=TEXT,
        )
        self._txt.pack(fill="both", expand=True, padx=10, pady=10)

        # Tags de color
        self._txt.tag_config("pass",    foreground="#4caf50")
        self._txt.tag_config("fail",    foreground="#f44336")
        self._txt.tag_config("xfail",   foreground="#ff9800")
        self._txt.tag_config("error",   foreground="#f44336", font=("Courier New", 10, "bold"))
        self._txt.tag_config("section", foreground="#7c6af7", font=("Courier New", 10, "bold"))
        self._txt.tag_config("normal",  foreground="#c8ffc8")

        # Barra inferior: status + botón detener
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        self._status_var = tk.StringVar(value="Ejecutando…")
        self._status_lbl = tk.Label(
            bottom, textvariable=self._status_var,
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._status_lbl.pack(side="left", fill="x", expand=True)

        self._stop_btn = tk.Button(
            bottom, text="⏹ Detener",
            bg="#c0392b", fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat", bd=0,
            padx=12, pady=4,
            cursor="hand2",
            activebackground="#922b21",
            command=self._stop,
        )
        self._stop_btn.pack(side="right")
        self._proc: subprocess.Popen | None = None

    def set_proc(self, proc: "subprocess.Popen") -> None:
        self._proc = proc

    def _stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self.set_status("Detenido por el usuario.", WARNING)
        self._stop_btn.configure(state="disabled")

    def append(self, line: str) -> None:
        self._txt.configure(state="normal")
        tag = "normal"
        lo = line.lower()
        if " passed" in lo or "passed" in lo:
            tag = "pass"
        if "failed" in lo or "error" in lo:
            tag = "fail"
        if "xfail" in lo or "xpass" in lo:
            tag = "xfail"
        if line.startswith("===") or line.startswith("---"):
            tag = "section"
        self._txt.insert("end", line + "\n", tag)
        self._txt.see("end")
        self._txt.configure(state="disabled")

    def set_status(self, text: str, color: str = TEXT_DIM) -> None:
        self._status_var.set(text)
        self._status_lbl.configure(fg=color)


# ══════════════════════════════════════════════════════════════════════════════
# Ventana de URL del servidor
# ══════════════════════════════════════════════════════════════════════════════

class ServerUrlDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, task: dict) -> None:
        super().__init__(parent)
        self.title("Configurar servidor")
        self.configure(bg=BG)
        self.geometry("560x260")
        self.resizable(False, False)
        self.grab_set()
        self._parent = parent
        self._task = task
        self._confirmed = False

        tk.Label(
            self, text="URL del servidor",
            bg=BG, fg=TEXT,
            font=("Segoe UI", 13, "bold"),
        ).pack(pady=(22, 4))

        tk.Label(
            self,
            text="Pega la URL completa del servidor TripleTen.\n"
                 "Se actualizarán SERVER_BASE_URL, API_BASE_URL y SSH_USER en .env",
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            justify="center",
        ).pack(pady=(0, 12))

        self._entry = tk.Entry(
            self, width=58,
            bg=BG_CARD, fg=TEXT,
            insertbackground=TEXT,
            font=("Courier New", 10),
            relief="flat", bd=6,
        )
        self._entry.pack(padx=24, ipady=6)
        self._entry.focus()
        self._entry.bind("<Return>", lambda _: self._confirm())

        # Muestra URL actual como placeholder
        try:
            current = self._read_current_url()
            self._entry.delete(0, "end")
            self._entry.insert(0, current)
            self._entry.select_range(0, "end")
            self._entry.icursor("end")
        except Exception:
            pass

        # Ctrl+A selecciona todo (útil antes de pegar en Linux)
        self._entry.bind("<Control-a>", lambda _: (
            self._entry.select_range(0, "end"), self._entry.icursor("end")
        ))

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=18)

        tk.Button(
            btn_frame, text="Cancelar",
            bg=BG_CARD, fg=TEXT_DIM,
            font=("Segoe UI", 10),
            relief="flat", bd=0, padx=18, pady=8,
            cursor="hand2",
            command=self.destroy,
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="Confirmar y ejecutar",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0, padx=18, pady=8,
            cursor="hand2",
            activebackground=ACCENT_DARK,
            command=self._confirm,
        ).pack(side="left", padx=8)

    def _read_current_url(self) -> str:
        text = ENV_FILE.read_text(encoding="utf-8")
        m = re.search(r"^SERVER_BASE_URL=(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    def _confirm(self) -> None:
        raw = self._entry.get().strip()
        parsed = _parse_url(raw)
        if not parsed:
            messagebox.showerror("URL inválida", "No se pudo parsear la URL.\nEjemplo:\nhttps://cnt-xxxx.containerhub.tripleten-services.com", parent=self)
            return
        base_url, api_url, ssh_user = parsed
        try:
            _update_env(base_url, api_url, ssh_user)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo actualizar .env:\n{exc}", parent=self)
            return
        self._confirmed = True
        self.destroy()
        _run_task(self._parent, self._task)


# ══════════════════════════════════════════════════════════════════════════════
# Ejecutar tarea
# ══════════════════════════════════════════════════════════════════════════════

def _run_task(parent: tk.Tk, task: dict) -> None:
    win = OutputWindow(parent, task)

    cmd = [
        str(PYTHON), "-m", "pytest",
        task["archivo"],
        "-m", task["marker"],
        "-v", "--tb=short",
        "--no-header",
    ]

    def _stream() -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            win.after(0, win.set_proc, proc)
            for line in proc.stdout:
                line = line.rstrip("\n")
                win.after(0, win.append, line)
            proc.wait()
            rc = proc.returncode
            if rc == 0:
                msg, color = "Completado — todos los tests pasaron.", SUCCESS
            elif rc == 1:
                msg, color = "Completado — hay tests fallidos.", ERROR
            elif rc == -15:
                msg, color = "Detenido por el usuario.", WARNING
            else:
                msg, color = f"Proceso terminó con código {rc}.", WARNING
        except Exception as exc:
            msg, color = f"Error al lanzar pytest: {exc}", ERROR
        win.after(0, win.set_status, msg, color)
        win.after(0, lambda: win._stop_btn.configure(state="disabled"))

    threading.Thread(target=_stream, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# Ventana principal
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Urban Scooter — QA Launcher")
        self.configure(bg=BG)
        self.resizable(False, False)

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=ACCENT, pady=14)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🛴  Urban Scooter — QA Launcher",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 16, "bold"),
        ).pack()
        tk.Label(
            header,
            text="Selecciona la tarea que deseas ejecutar",
            bg=ACCENT, fg="#ddd8ff",
            font=("Segoe UI", 10),
        ).pack()

        # ── Tarjetas de tarea ─────────────────────────────────────────────────
        container = tk.Frame(self, bg=BG, padx=20, pady=16)
        container.pack(fill="both", expand=True)

        for task in TASKS:
            self._build_card(container, task)

        # ── Botón reporte de bugs ─────────────────────────────────────────────
        sep = tk.Frame(self, bg="#3a3a55", height=1)
        sep.pack(fill="x", padx=20, pady=(4, 10))

        bug_card = tk.Frame(self, bg="#2a1f3d", pady=12, padx=16)
        bug_card.pack(fill="x", padx=20, pady=(0, 6))

        bug_left = tk.Frame(bug_card, bg="#2a1f3d")
        bug_left.pack(side="left", fill="both", expand=True)

        tk.Label(
            bug_left,
            text="  Generar reporte de bugs para Jira",
            bg="#2a1f3d", fg="#d0b8ff",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")

        tk.Label(
            bug_left,
            text="Escanea los últimos resultados de todas las tareas, extrae las filas\n"
                 "'No Aprobado' y genera un archivo Excel + CSV listos para importar a Jira.",
            bg="#2a1f3d", fg=TEXT_DIM,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        tk.Button(
            bug_card,
            text="Generar 📋",
            bg="#9b59b6", fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0,
            padx=14, pady=8,
            cursor="hand2",
            activebackground="#7d3c98",
            command=self._on_bug_report_click,
        ).pack(side="right", padx=(12, 0))

        # ── Botón subir screenshots a Jira ────────────────────────────────────
        jira_card = tk.Frame(self, bg="#1a2a1f", pady=12, padx=16)
        jira_card.pack(fill="x", padx=20, pady=(0, 6))

        jira_left = tk.Frame(jira_card, bg="#1a2a1f")
        jira_left.pack(side="left", fill="both", expand=True)

        tk.Label(
            jira_left,
            text="  Subir screenshots a Jira",
            bg="#1a2a1f", fg="#a8d5b5",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")

        tk.Label(
            jira_left,
            text="Tras importar el CSV en Jira, selecciona el CSV exportado con claves\n"
                 "asignadas y sube automáticamente los screenshots a cada issue.",
            bg="#1a2a1f", fg=TEXT_DIM,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        tk.Button(
            jira_card,
            text="Subir 🔗",
            bg="#27ae60", fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0,
            padx=14, pady=8,
            cursor="hand2",
            activebackground="#1e8449",
            command=self._on_jira_upload_click,
        ).pack(side="right", padx=(12, 0))

        # ── Footer ────────────────────────────────────────────────────────────
        tk.Label(
            self,
            text="Al seleccionar una tarea se te pedirá la URL del servidor antes de ejecutar.",
            bg=BG, fg=TEXT_DIM,
            font=("Segoe UI", 8),
        ).pack(pady=(4, 10))

        self.eval("tk::PlaceWindow . center")

    def _build_card(self, parent: tk.Frame, task: dict) -> None:
        card = tk.Frame(parent, bg=BG_CARD, pady=12, padx=16, cursor="hand2")
        card.pack(fill="x", pady=6)

        left = tk.Frame(card, bg=BG_CARD)
        left.pack(side="left", fill="both", expand=True)

        # Número + título
        title_frame = tk.Frame(left, bg=BG_CARD)
        title_frame.pack(anchor="w")

        tk.Label(
            title_frame,
            text=task["numero"],
            bg=ACCENT, fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=8, pady=2,
        ).pack(side="left")

        tk.Label(
            title_frame,
            text=f"  {task['titulo']}",
            bg=BG_CARD, fg=TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        # Descripción
        tk.Label(
            left,
            text=task["descripcion"],
            bg=BG_CARD, fg=TEXT_DIM,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        # Botón
        btn = tk.Button(
            card,
            text="Ejecutar ▶",
            bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0,
            padx=14, pady=8,
            cursor="hand2",
            activebackground=ACCENT_DARK,
            command=lambda t=task: self._on_task_click(t),
        )
        btn.pack(side="right", padx=(12, 0))

        # Hover
        card.bind("<Enter>",  lambda e, c=card: c.configure(bg="#33334d"))
        card.bind("<Leave>",  lambda e, c=card: c.configure(bg=BG_CARD))

    def _on_task_click(self, task: dict) -> None:
        ServerUrlDialog(self, task)

    def _on_jira_upload_click(self) -> None:
        from tkinter import filedialog
        import os

        # 1. Verificar credenciales Jira en .env
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
        missing = [v for v in ("JIRA_BASE_URL", "JIRA_USER", "JIRA_API_TOKEN") if not os.getenv(v)]
        if missing:
            messagebox.showerror(
                "Credenciales Jira",
                f"Faltan variables en .env:\n  {chr(10).join(missing)}\n\n"
                "Añádelas y vuelve a intentarlo.",
                parent=self,
            )
            return

        # 2. Pedir CSV exportado de Jira
        jira_csv = filedialog.askopenfilename(
            title="Selecciona el CSV exportado de Jira (con claves asignadas)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=str(ROOT / "results"),
            parent=self,
        )
        if not jira_csv:
            return

        # 3. Detectar manifest más reciente en results/
        manifests = sorted(
            (ROOT / "results").glob("bug_manifest_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not manifests:
            messagebox.showerror(
                "Sin manifest",
                "No se encontró ningún bug_manifest_*.json en results/.\n"
                "Genera primero el reporte de bugs.",
                parent=self,
            )
            return

        manifest_path = manifests[0]

        # 4. Confirmar
        if not messagebox.askyesno(
            "Confirmar",
            f"CSV Jira:  {Path(jira_csv).name}\n"
            f"Manifest:  {manifest_path.name}\n\n"
            "¿Subir screenshots a Jira?",
            parent=self,
        ):
            return

        # 5. Ventana de progreso
        prog_win = tk.Toplevel(self)
        prog_win.title("Subiendo screenshots…")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        log_area = scrolledtext.ScrolledText(
            prog_win, width=70, height=18,
            bg="#1e1e2e", fg="#cdd6f4",
            font=("Courier New", 9),
            state="disabled",
        )
        log_area.pack(padx=12, pady=12)

        def _log(msg: str) -> None:
            log_area.configure(state="normal")
            log_area.insert("end", msg + "\n")
            log_area.see("end")
            log_area.configure(state="disabled")
            prog_win.update_idletasks()

        def _run() -> None:
            try:
                import sys as _sys
                import io
                from contextlib import redirect_stdout
                from jira_uploader import run as jira_run

                buf = io.StringIO()
                with redirect_stdout(buf):
                    jira_run(Path(jira_csv), manifest_path)
                output = buf.getvalue()
                for line in output.splitlines():
                    _log(line)
                _log("\n✓ Proceso completado.")
            except Exception as exc:
                _log(f"\n✗ Error: {exc}")

            close_btn.configure(state="normal")

        close_btn = tk.Button(
            prog_win, text="Cerrar",
            bg="#555", fg="white",
            font=("Segoe UI", 10),
            relief="flat", padx=12, pady=6,
            state="disabled",
            command=prog_win.destroy,
        )
        close_btn.pack(pady=(0, 12))

        threading.Thread(target=_run, daemon=True).start()

    def _on_bug_report_click(self) -> None:
        from bug_reporter import generate_bug_report
        try:
            xlsx_path, csv_path, attachments_dir, manifest_path, total = generate_bug_report()
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo generar el reporte:\n{exc}", parent=self)
            return

        if total == 0:
            messagebox.showinfo(
                "Sin bugs",
                "No se encontraron filas 'No Aprobado' en los resultados.\n"
                "Ejecuta al menos una tarea antes de generar el reporte.",
                parent=self,
            )
            return

        attachments_count = len(list(attachments_dir.glob("*"))) if attachments_dir.exists() else 0
        messagebox.showinfo(
            "Reporte generado",
            f"Se encontraron {total} bug(s).\n\n"
            f"Excel:       {xlsx_path.name}\n"
            f"CSV:         {csv_path.name}\n"
            f"Screenshots: {attachments_dir.name}/ ({attachments_count} archivos)\n"
            f"Manifest:    {manifest_path.name}\n\n"
            f"Guardados en: results/\n\n"
            f"Para subir screenshots a Jira tras importar el CSV:\n"
            f"  python jira_uploader.py <jira_export.csv> {manifest_path.name}",
            parent=self,
        )


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
