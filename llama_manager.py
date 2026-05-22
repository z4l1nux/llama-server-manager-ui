#!/usr/bin/env python3
"""
Llama Server Manager — GUI completa para gerenciar llama.cpp server
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess
import threading
import os
import json
import shutil
import signal
import sys
import time
import socket
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ─── Plataforma ───────────────────────────────────────────────────────────────

IS_WINDOWS = sys.platform == 'win32'

if IS_WINDOWS:
    CONFIG_DIR    = Path.home() / 'AppData' / 'Roaming' / 'llama-manager'
    ICON_SEARCH   = [Path(__file__).parent / 'llama-manager.png',
                     Path.home() / 'AppData' / 'Roaming' / 'llama-manager' / 'icon.png']
    BIN_EXT       = '.exe'
    BIN_DEFAULT   = Path.home() / 'llama.cpp' / 'build' / 'bin' / 'Release' / 'llama-server.exe'
else:
    CONFIG_DIR    = Path.home() / '.config' / 'llama-manager'
    ICON_SEARCH   = [Path.home() / '.local' / 'share' / 'icons' / 'llama-manager.png',
                     Path(__file__).parent / 'llama-manager.png']
    BIN_EXT       = ''
    BIN_DEFAULT   = Path.home() / 'llama.cpp' / 'build' / 'bin' / 'llama-server'

# ─── Configuração ─────────────────────────────────────────────────────────────

CONFIG_FILE       = CONFIG_DIR / 'config.json'
LLAMA_BIN_DEFAULT = str(BIN_DEFAULT)

DEFAULT_CONFIG = {
    # Servidor
    'llama_server_bin': LLAMA_BIN_DEFAULT,
    'host': '127.0.0.1',
    'port': '8080',
    'api_key': '',
    # Modelo
    'models_dir': str(Path.home() / 'models'),
    'current_model': '',
    # Básico
    'ctx_size': '4096',
    'threads': '-1',
    'n_gpu_layers': '0',
    'batch_size': '2048',
    'ubatch_size': '512',
    'parallel': '-1',
    'n_predict': '-1',
    # Memória
    'mmap': True,
    'mlock': False,
    # Performance
    'flash_attn': 'auto',
    'cont_batching': True,
    # Cache KV
    'cache_type_k': 'f16',
    'cache_type_v': 'f16',
    # Especulativo / MTP
    'spec_enabled': False,
    'spec_draft_model': '',
    'spec_draft_n_max': '5',
    'spec_draft_n_min': '0',
    'spec_draft_p_split': '0.10',
    'spec_draft_p_min': '0.00',
    # TurboQuant
    'turbo_enabled': False,
    'turbo_rope_freq_base': '',
    'turbo_rope_freq_scale': '',
    'turbo_rope_scaling': 'linear',
    'turbo_extra_args': '',
    # Raciocínio / Thinking
    'reasoning': 'auto',
    'reasoning_budget': '-1',
    # Custom
    'custom_args': '',
    # Download
    'hf_token': '',
}

KV_TYPES = ['f32', 'f16', 'bf16', 'q8_0', 'q4_0', 'q4_1', 'q5_0', 'q5_1', 'iq4_nl']
ROPE_SCALINGS = ['none', 'linear', 'yarn']
FLASH_ATTN_OPTS = ['auto', 'on', 'off']
REASONING_OPTS  = ['auto', 'on', 'off']

DARK_BG = '#1e1e1e'
DARK_FG = '#d4d4d4'


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def fmt_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} TB'


def detect_quant(name):
    n = name.lower()
    for q in ['iq4_xs', 'iq3_m', 'iq2_m', 'q8_0', 'q6_k_l', 'q6_k', 'q5_k_m', 'q5_k_s',
               'q4_k_m', 'q4_k_s', 'q3_k_l', 'q3_k_m', 'q3_k_s', 'q2_k', 'bf16', 'f16', 'f32']:
        if q in n:
            return q.upper()
    return 'GGUF'


# ─── Aplicação Principal ──────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title('Llama Server Manager')
        self.root.geometry('1150x780')
        self.root.minsize(950, 640)

        self.config = load_config()
        self.server_process = None
        self.is_running = False
        self._server_monitor_id = None

        self._setup_style()
        self._build_ui()
        self.root.after(800, self._probe_server)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── Estilo ──────────────────────────────────────────────────────────────

    def _setup_style(self):
        st = ttk.Style()
        for theme in ('clam', 'alt', 'default'):
            if theme in st.theme_names():
                st.theme_use(theme)
                break
        st.configure('Running.TLabel',  foreground='#27ae60', font=('TkDefaultFont', 10, 'bold'))
        st.configure('Stopped.TLabel',  foreground='#e74c3c', font=('TkDefaultFont', 10, 'bold'))
        st.configure('Section.TLabelframe.Label', font=('TkDefaultFont', 10, 'bold'))
        st.configure('Accent.TButton', font=('TkDefaultFont', 10, 'bold'))

    # ── Layout Raiz ──────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=8, pady=(0, 8))

        self.tab_server   = ServerTab(nb, self)
        self.tab_models   = ModelsTab(nb, self)
        self.tab_params   = ParametersTab(nb, self)
        self.tab_download = DownloadTab(nb, self)

        nb.add(self.tab_server.frame,   text='  Servidor  ')
        nb.add(self.tab_models.frame,   text='  Modelos  ')
        nb.add(self.tab_params.frame,   text='  Parâmetros  ')
        nb.add(self.tab_download.frame, text='  Download  ')

    def _build_topbar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill='x', padx=8, pady=5)

        ttk.Label(bar, text='Status:', font=('TkDefaultFont', 9)).pack(side='left')
        self.lbl_status = ttk.Label(bar, text='● Parado', style='Stopped.TLabel')
        self.lbl_status.pack(side='left', padx=(4, 20))

        ttk.Label(bar, text='Modelo:', font=('TkDefaultFont', 9)).pack(side='left')
        self.lbl_model = ttk.Label(bar, text='—', foreground='gray')
        self.lbl_model.pack(side='left', padx=(4, 20))

        ttk.Label(bar, text='URL:', font=('TkDefaultFont', 9)).pack(side='left')
        self.lbl_url = ttk.Label(bar, text='—', foreground='gray', cursor='hand2')
        self.lbl_url.pack(side='left', padx=(4, 0))
        self.lbl_url.bind('<Button-1>', self._open_browser)

    # ── Estado do Servidor ───────────────────────────────────────────────────

    def _probe_server(self):
        h = self.config.get('host', '127.0.0.1')
        p = int(self.config.get('port', 8080))
        try:
            s = socket.create_connection((h, p), timeout=0.4)
            s.close()
            if not self.is_running:
                self._set_running(f'http://{h}:{p}')
        except OSError:
            if self.is_running and self.server_process is None:
                self._set_stopped()
        self._server_monitor_id = self.root.after(3000, self._probe_server)

    def _set_running(self, url=None):
        self.is_running = True
        self.lbl_status.config(text='● Rodando', style='Running.TLabel')
        if url:
            self.lbl_url.config(text=url, foreground='#2980b9')
        if hasattr(self, 'tab_server'):
            self.tab_server.update_buttons(True)

    def _set_stopped(self):
        self.is_running = False
        self.server_process = None
        self.lbl_status.config(text='● Parado', style='Stopped.TLabel')
        self.lbl_url.config(text='—', foreground='gray')
        if hasattr(self, 'tab_server'):
            self.tab_server.update_buttons(False)

    def set_model_label(self, name):
        self.lbl_model.config(text=name or '—', foreground='black' if name else 'gray')

    # ── Construção do Comando ────────────────────────────────────────────────

    def build_command(self):
        c = self.config
        cmd = [c.get('llama_server_bin', LLAMA_BIN_DEFAULT)]

        model = c.get('current_model', '')
        if model:
            cmd += ['-m', model]

        cmd += ['--host', c.get('host', '127.0.0.1')]
        cmd += ['--port', str(c.get('port', '8080'))]

        ctx = c.get('ctx_size', '').strip()
        if ctx and ctx != '0':
            cmd += ['-c', ctx]

        threads = c.get('threads', '-1').strip()
        if threads and threads != '-1':
            cmd += ['-t', threads]

        ngl = c.get('n_gpu_layers', '0').strip()
        if ngl:
            cmd += ['-ngl', ngl]

        cmd += ['-b',  c.get('batch_size',  '2048')]
        cmd += ['-ub', c.get('ubatch_size', '512')]

        par = c.get('parallel', '-1').strip()
        if par:
            cmd += ['-np', par]

        np_ = c.get('n_predict', '-1').strip()
        if np_ and np_ != '-1':
            cmd += ['-n', np_]

        if not c.get('mmap', True):
            cmd.append('--no-mmap')
        if c.get('mlock', False):
            cmd.append('--mlock')

        fa = c.get('flash_attn', 'auto')
        if fa != 'auto':
            cmd += ['-fa', fa]

        if c.get('cont_batching', True):
            cmd.append('-cb')
        else:
            cmd.append('-nocb')

        ctk = c.get('cache_type_k', 'f16')
        ctv = c.get('cache_type_v', 'f16')
        if ctk != 'f16':
            cmd += ['-ctk', ctk]
        if ctv != 'f16':
            cmd += ['-ctv', ctv]

        # Especulativo / MTP
        if c.get('spec_enabled', False):
            draft_model = c.get('spec_draft_model', '').strip()
            if draft_model:
                cmd += ['--model-draft', draft_model]
            cmd += ['--spec-draft-n-max', c.get('spec_draft_n_max', '5')]
            cmd += ['--spec-draft-n-min', c.get('spec_draft_n_min', '0')]
            cmd += ['--draft-p-split',    c.get('spec_draft_p_split', '0.10')]
            cmd += ['--draft-p-min',      c.get('spec_draft_p_min', '0.00')]

        # TurboQuant
        if c.get('turbo_enabled', False):
            rope_base = c.get('turbo_rope_freq_base', '').strip()
            rope_scale = c.get('turbo_rope_freq_scale', '').strip()
            rope_scaling = c.get('turbo_rope_scaling', 'linear')
            if rope_base:
                cmd += ['--rope-freq-base', rope_base]
            if rope_scale:
                cmd += ['--rope-freq-scale', rope_scale]
            if rope_scaling and rope_scaling != 'linear':
                cmd += ['--rope-scaling', rope_scaling]
            extra = c.get('turbo_extra_args', '').strip()
            if extra:
                cmd += extra.split()

        # Raciocínio / Thinking
        reasoning = c.get('reasoning', 'auto')
        if reasoning != 'auto':
            cmd += ['-rea', reasoning]
        budget = c.get('reasoning_budget', '-1').strip()
        if budget and budget != '-1':
            cmd += ['--reasoning-budget', budget]

        api_key = c.get('api_key', '').strip()
        if api_key:
            cmd += ['--api-key', api_key]

        custom = c.get('custom_args', '').strip()
        if custom:
            cmd += custom.split()

        return cmd

    # ── Controle do Processo ─────────────────────────────────────────────────

    def start_server(self):
        if self.is_running:
            messagebox.showwarning('Aviso', 'Servidor já está rodando.')
            return
        cmd = self.build_command()
        self.tab_server.log(f'$ {" ".join(cmd)}\n', 'cmd')
        try:
            env = os.environ.copy()
            bin_dir = str(Path(cmd[0]).parent)
            if IS_WINDOWS:
                env['PATH'] = bin_dir + os.pathsep + env.get('PATH', '')
            else:
                env['LD_LIBRARY_PATH'] = bin_dir + ':' + env.get('LD_LIBRARY_PATH', '')
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
        except FileNotFoundError:
            messagebox.showerror('Erro', f'Binário não encontrado:\n{cmd[0]}')
            return
        except Exception as e:
            messagebox.showerror('Erro ao iniciar', str(e))
            return

        self._set_running(f'http://{self.config.get("host")}:{self.config.get("port")}')
        model = self.config.get('current_model', '')
        self.set_model_label(Path(model).name if model else '')
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        try:
            for line in self.server_process.stdout:
                self.root.after(0, self.tab_server.log, line)
            self.server_process.wait()
        except Exception:
            pass
        self.root.after(0, self._set_stopped)

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            threading.Thread(target=self._reap, daemon=True).start()
        else:
            # Tenta matar pelo porto
            port = self.config.get('port', '8080')
            try:
                if IS_WINDOWS:
                    subprocess.run(
                        ['powershell', '-NoProfile', '-Command',
                         f'Get-NetTCPConnection -LocalPort {port} -EA SilentlyContinue'
                         f' | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }}'],
                        capture_output=True, timeout=5)
                else:
                    subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)
            except Exception:
                pass
        self._set_stopped()
        self.tab_server.log('[Servidor parado]\n', 'info')

    def _reap(self):
        try:
            self.server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server_process.kill()

    def _open_browser(self, event=None):
        import webbrowser
        h = self.config.get('host', '127.0.0.1')
        p = self.config.get('port', '8080')
        webbrowser.open(f'http://{h}:{p}')

    def _on_close(self):
        if self.is_running and self.server_process:
            if messagebox.askyesno('Fechar', 'Servidor está rodando. Parar antes de fechar?'):
                self.stop_server()
        save_config(self.config)
        self.root.destroy()


# ─── Aba: Servidor ────────────────────────────────────────────────────────────

class ServerTab:
    def __init__(self, nb, app: App):
        self.app = app
        self.frame = ttk.Frame(nb)
        self._build()

    def _build(self):
        # Botões de controle
        ctrl = ttk.Frame(self.frame)
        ctrl.pack(fill='x', padx=10, pady=8)

        self.btn_start = ttk.Button(ctrl, text='▶  Iniciar Servidor', width=22,
                                    style='Accent.TButton', command=self.app.start_server)
        self.btn_start.pack(side='left', padx=4)

        self.btn_stop = ttk.Button(ctrl, text='■  Parar Servidor', width=22,
                                   command=self.app.stop_server, state='disabled')
        self.btn_stop.pack(side='left', padx=4)

        ttk.Separator(ctrl, orient='vertical').pack(side='left', fill='y', padx=10)
        ttk.Button(ctrl, text='Abrir no navegador', command=self.app._open_browser).pack(side='left', padx=4)
        ttk.Button(ctrl, text='Limpar log', command=self._clear).pack(side='left', padx=4)

        # Seleção rápida de modelo
        mf = ttk.LabelFrame(self.frame, text='Modelo Ativo', padding=6, style='Section.TLabelframe')
        mf.pack(fill='x', padx=10, pady=4)

        self.model_var = tk.StringVar(value=self.app.config.get('current_model', ''))
        ttk.Entry(mf, textvariable=self.model_var).pack(side='left', fill='x', expand=True, padx=4)
        ttk.Button(mf, text='Procurar…', command=self._browse).pack(side='left', padx=4)
        ttk.Button(mf, text='Aplicar',   command=self._apply).pack(side='left', padx=4)

        # Comando gerado
        cmd_frame = ttk.LabelFrame(self.frame, text='Comando que será executado', padding=4,
                                   style='Section.TLabelframe')
        cmd_frame.pack(fill='x', padx=10, pady=4)
        self.cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_var, state='readonly', foreground='#555')
        cmd_entry.pack(fill='x', padx=4)
        ttk.Button(cmd_frame, text='Atualizar prévia',
                   command=self._refresh_cmd).pack(anchor='e', pady=2, padx=4)
        self._refresh_cmd()

        # Log
        log_frame = ttk.LabelFrame(self.frame, text='Log do Servidor', padding=4,
                                   style='Section.TLabelframe')
        log_frame.pack(fill='both', expand=True, padx=10, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap='word', font=('Monospace', 9),
            background=DARK_BG, foreground=DARK_FG, insertbackground='white',
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.tag_config('cmd',   foreground='#4fc1ff')
        self.log_text.tag_config('info',  foreground='#4ec9b0')
        self.log_text.tag_config('error', foreground='#f44747')

    def update_buttons(self, running: bool):
        self.btn_start.config(state='disabled' if running else 'normal')
        self.btn_stop.config(state='normal'    if running else 'disabled')

    def log(self, text, tag=None):
        self.log_text.insert('end', text, tag or '')
        self.log_text.see('end')

    def _clear(self):
        self.log_text.delete('1.0', 'end')

    def _browse(self):
        path = filedialog.askopenfilename(
            title='Selecionar modelo GGUF',
            initialdir=self.app.config.get('models_dir', str(Path.home())),
            filetypes=[('GGUF', '*.gguf'), ('Todos', '*.*')],
        )
        if path:
            self.model_var.set(path)
            self._apply()

    def _apply(self):
        path = self.model_var.get().strip()
        self.app.config['current_model'] = path
        self.app.set_model_label(Path(path).name if path else '')
        save_config(self.app.config)
        self._refresh_cmd()

    def _refresh_cmd(self):
        try:
            cmd = self.app.build_command()
            self.cmd_var.set(' '.join(cmd))
        except Exception as e:
            self.cmd_var.set(f'Erro: {e}')


# ─── Aba: Modelos ─────────────────────────────────────────────────────────────

class ModelsTab:
    def __init__(self, nb, app: App):
        self.app = app
        self.frame = ttk.Frame(nb)
        self._build()

    def _build(self):
        # Toolbar
        tb = ttk.Frame(self.frame)
        tb.pack(fill='x', padx=10, pady=6)

        ttk.Label(tb, text='Pasta de modelos:').pack(side='left')
        self.dir_var = tk.StringVar(value=self.app.config.get('models_dir', ''))
        ttk.Entry(tb, textvariable=self.dir_var, width=45).pack(side='left', padx=4)
        ttk.Button(tb, text='…', width=3, command=self._browse_dir).pack(side='left')
        ttk.Button(tb, text='Atualizar', command=self.refresh).pack(side='left', padx=6)

        # Treeview
        tf = ttk.Frame(self.frame)
        tf.pack(fill='both', expand=True, padx=10, pady=4)

        cols = ('nome', 'tamanho', 'quant', 'turbo', 'caminho')
        self.tree = ttk.Treeview(tf, columns=cols, show='headings', selectmode='browse')
        self.tree.heading('nome',     text='Nome')
        self.tree.heading('tamanho',  text='Tamanho')
        self.tree.heading('quant',    text='Quantização')
        self.tree.heading('turbo',    text='TurboQuant')
        self.tree.heading('caminho',  text='Caminho Completo')
        self.tree.column('nome',    width=320)
        self.tree.column('tamanho', width=90,  anchor='e')
        self.tree.column('quant',   width=90,  anchor='center')
        self.tree.column('turbo',   width=80,  anchor='center')
        self.tree.column('caminho', width=400)

        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

        self.tree.bind('<Double-1>', lambda e: self._load())
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        # Ações
        af = ttk.Frame(self.frame)
        af.pack(fill='x', padx=10, pady=6)

        ttk.Button(af, text='▶  Carregar Modelo',   command=self._load).pack(side='left', padx=4)
        ttk.Button(af, text='🗑  Deletar Modelo',   command=self._delete).pack(side='left', padx=4)
        ttk.Button(af, text='📋  Copiar Caminho',   command=self._copy_path).pack(side='left', padx=4)
        ttk.Button(af, text='📂  Abrir Pasta',       command=self._open_folder).pack(side='left', padx=4)

        self.info_var = tk.StringVar(value='Selecione um modelo.')
        ttk.Label(self.frame, textvariable=self.info_var, foreground='gray').pack(
            padx=10, pady=2, anchor='w')

        self.refresh()

    def refresh(self):
        models_dir = self.dir_var.get().strip()
        self.app.config['models_dir'] = models_dir
        save_config(self.app.config)
        self.tree.delete(*self.tree.get_children())

        p = Path(models_dir)
        if not p.exists():
            self.info_var.set(f'Pasta não encontrada: {models_dir}')
            return

        count = 0
        for f in sorted(p.rglob('*.gguf')):
            try:
                size = f.stat().st_size
            except OSError:
                continue
            is_turbo = any(x in f.name.lower() for x in ('turbo', '-tq', '_tq'))
            self.tree.insert('', 'end', values=(
                f.name, fmt_size(size), detect_quant(f.name),
                '✓' if is_turbo else '', str(f),
            ), tags=(str(f),))
            count += 1
        self.info_var.set(f'{count} modelo(s) encontrado(s) em {models_dir}')

    def _get_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0], 'tags')
        return Path(tags[0]) if tags else None

    def _on_select(self, _):
        p = self._get_path()
        if p and p.exists():
            self.info_var.set(f'{p}  |  {fmt_size(p.stat().st_size)}')

    def _load(self):
        p = self._get_path()
        if not p:
            messagebox.showwarning('Aviso', 'Selecione um modelo.')
            return
        self.app.config['current_model'] = str(p)
        self.app.set_model_label(p.name)
        self.app.tab_server.model_var.set(str(p))
        save_config(self.app.config)

        # Auto-detecta TurboQuant
        is_turbo = any(x in p.name.lower() for x in ('turbo', '-tq', '_tq'))
        if is_turbo and not self.app.config.get('turbo_enabled', False):
            self.app.config['turbo_enabled'] = True
            save_config(self.app.config)
            if hasattr(self.app, 'tab_params'):
                self.app.tab_params.turbo_var.set(True)
                self.app.tab_params._toggle_turbo()
            messagebox.showinfo('TurboQuant Detectado',
                                f'{p.name}\n\nParâmetros TurboQuant foram habilitados automaticamente.\n'
                                'Configure RoPE em Parâmetros se necessário.')
        else:
            messagebox.showinfo('Modelo Selecionado',
                                f'{p.name}\n\nInicie o servidor para aplicar.')
        self.app.tab_server._refresh_cmd()

    def _delete(self):
        p = self._get_path()
        if not p:
            messagebox.showwarning('Aviso', 'Selecione um modelo.')
            return
        if messagebox.askyesno('Confirmar Exclusão',
                               f'Excluir permanentemente?\n\n{p.name}\n({fmt_size(p.stat().st_size)})'):
            try:
                p.unlink()
                self.refresh()
            except Exception as e:
                messagebox.showerror('Erro', str(e))

    def _copy_path(self):
        p = self._get_path()
        if p:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(str(p))

    def _open_folder(self):
        p = self._get_path()
        folder = str(p.parent) if p else self.dir_var.get()
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception:
            pass

    def _browse_dir(self):
        d = filedialog.askdirectory(title='Pasta de modelos')
        if d:
            self.dir_var.set(d)
            self.app.config['models_dir'] = d
            save_config(self.app.config)
            self.refresh()


# ─── Aba: Parâmetros ──────────────────────────────────────────────────────────

class ParametersTab:
    def __init__(self, nb, app: App):
        self.app = app
        self.frame = ttk.Frame(nb)
        self._build()

    def _build(self):
        # Canvas + scrollbar
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        vsb = ttk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        self.sf = ttk.Frame(canvas)
        self.sf.bind('<Configure>',
                     lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=self.sf, anchor='nw')
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def _scroll(e):
            canvas.yview_scroll(-1 * (e.delta // 120 or (1 if e.num == 4 else -1)), 'units')
        canvas.bind_all('<MouseWheel>', _scroll)
        canvas.bind_all('<Button-4>',  _scroll)
        canvas.bind_all('<Button-5>',  _scroll)

        self._build_server_section()
        self._build_basic_section()
        self._build_memory_section()
        self._build_perf_section()
        self._build_cache_section()
        self._build_reasoning_section()
        self._build_spec_section()
        self._build_turbo_section()
        self._build_custom_section()

        save_btn = ttk.Button(self.sf, text='💾  Salvar Configurações',
                              command=self.save_all, style='Accent.TButton', width=28)
        save_btn.pack(pady=12)

    # ── Seções ────────────────────────────────────────────────────────────────

    def _section(self, title):
        f = ttk.LabelFrame(self.sf, text=title, padding=10, style='Section.TLabelframe')
        f.pack(fill='x', padx=10, pady=6)
        return f

    def _row(self, parent, row, label, var, width=14, hint='', combo=None, values=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=6, pady=3)
        if combo and values:
            w = ttk.Combobox(parent, textvariable=var, values=values, width=width, state='readonly')
        else:
            w = ttk.Entry(parent, textvariable=var, width=width)
        w.grid(row=row, column=1, sticky='w', padx=6)
        if hint:
            ttk.Label(parent, text=hint, foreground='gray').grid(row=row, column=2, sticky='w', padx=6)
        return w

    def _build_server_section(self):
        f = self._section('Servidor')
        g = ttk.Frame(f); g.pack(fill='x')

        self.bin_var  = tk.StringVar(value=self.app.config.get('llama_server_bin', LLAMA_BIN_DEFAULT))
        self.host_var = tk.StringVar(value=self.app.config.get('host', '127.0.0.1'))
        self.port_var = tk.StringVar(value=self.app.config.get('port', '8080'))
        self.key_var  = tk.StringVar(value=self.app.config.get('api_key', ''))

        ttk.Label(g, text='Binário llama-server:').grid(row=0, column=0, sticky='w', padx=6, pady=3)
        bin_row = ttk.Frame(g)
        bin_row.grid(row=0, column=1, columnspan=2, sticky='w', padx=6)
        ttk.Entry(bin_row, textvariable=self.bin_var, width=50).pack(side='left')
        ttk.Button(bin_row, text='…', width=3,
                   command=lambda: self._pick(self.bin_var)).pack(side='left', padx=4)

        self._row(g, 1, 'Host:', self.host_var, 20, 'Ex: 127.0.0.1  ou  0.0.0.0')
        self._row(g, 2, 'Porta:', self.port_var, 8, 'Padrão: 8080')
        ttk.Label(g, text='API Key:').grid(row=3, column=0, sticky='w', padx=6, pady=3)
        ttk.Entry(g, textvariable=self.key_var, width=30, show='*').grid(row=3, column=1, sticky='w', padx=6)

    def _build_basic_section(self):
        f = self._section('Parâmetros Básicos')
        g = ttk.Frame(f); g.pack(fill='x')

        self.ctx_var     = tk.StringVar(value=self.app.config.get('ctx_size', '4096'))
        self.thr_var     = tk.StringVar(value=self.app.config.get('threads', '-1'))
        self.ngl_var     = tk.StringVar(value=self.app.config.get('n_gpu_layers', '0'))
        self.batch_var   = tk.StringVar(value=self.app.config.get('batch_size', '2048'))
        self.ubatch_var  = tk.StringVar(value=self.app.config.get('ubatch_size', '512'))
        self.par_var     = tk.StringVar(value=self.app.config.get('parallel', '-1'))
        self.np_var      = tk.StringVar(value=self.app.config.get('n_predict', '-1'))

        rows = [
            ('Contexto (-c):', self.ctx_var,    '0 = do modelo, ex: 4096 8192 32768'),
            ('Threads (-t):',  self.thr_var,    '-1 = automático'),
            ('GPU Layers (-ngl):', self.ngl_var, '0 = CPU, -1 = todas no GPU'),
            ('Batch Size (-b):', self.batch_var, 'Padrão: 2048'),
            ('UBatch Size (-ub):', self.ubatch_var, 'Padrão: 512'),
            ('Paralelo (-np):', self.par_var,   '-1 = auto (slots simultâneos)'),
            ('N Predict (-n):', self.np_var,    '-1 = infinito'),
        ]
        for i, (lbl, var, hint) in enumerate(rows):
            self._row(g, i, lbl, var, 12, hint)

    def _build_memory_section(self):
        f = self._section('Memória')
        self.mmap_var  = tk.BooleanVar(value=self.app.config.get('mmap', True))
        self.mlock_var = tk.BooleanVar(value=self.app.config.get('mlock', False))
        ttk.Checkbutton(f, text='Memory Map (--mmap) — mapeia modelo em memória [recomendado]',
                        variable=self.mmap_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(f, text='Memory Lock (--mlock) — trava modelo na RAM, evita swap',
                        variable=self.mlock_var).pack(anchor='w', pady=2)

    def _build_perf_section(self):
        f = self._section('Performance')
        g = ttk.Frame(f); g.pack(fill='x')

        self.fa_var   = tk.StringVar(value=self.app.config.get('flash_attn', 'auto'))
        self.cb_var   = tk.BooleanVar(value=self.app.config.get('cont_batching', True))

        ttk.Label(g, text='Flash Attention (-fa):').grid(row=0, column=0, sticky='w', padx=6, pady=3)
        ttk.Combobox(g, textvariable=self.fa_var, values=FLASH_ATTN_OPTS,
                     width=8, state='readonly').grid(row=0, column=1, sticky='w', padx=6)
        ttk.Label(g, text="'auto' detecta suporte; 'on' força; 'off' desabilita",
                  foreground='gray').grid(row=0, column=2, sticky='w', padx=6)

        cb_frame = ttk.Frame(f)
        cb_frame.pack(fill='x', pady=4)
        ttk.Checkbutton(cb_frame, text='Continuous Batching (-cb) — processa múltiplos requests simultaneamente',
                        variable=self.cb_var).pack(anchor='w')

    def _build_cache_section(self):
        f = self._section('Tipo de Cache KV')
        g = ttk.Frame(f); g.pack(fill='x')

        self.ctk_var = tk.StringVar(value=self.app.config.get('cache_type_k', 'f16'))
        self.ctv_var = tk.StringVar(value=self.app.config.get('cache_type_v', 'f16'))

        ttk.Label(g, text='Cache K (-ctk):').grid(row=0, column=0, sticky='w', padx=6, pady=3)
        ttk.Combobox(g, textvariable=self.ctk_var, values=KV_TYPES,
                     width=10, state='readonly').grid(row=0, column=1, sticky='w', padx=6)
        ttk.Label(g, text='f16 padrão; q8_0/q4_0 reduz VRAM',
                  foreground='gray').grid(row=0, column=2, sticky='w', padx=6)

        ttk.Label(g, text='Cache V (-ctv):').grid(row=1, column=0, sticky='w', padx=6, pady=3)
        ttk.Combobox(g, textvariable=self.ctv_var, values=KV_TYPES,
                     width=10, state='readonly').grid(row=1, column=1, sticky='w', padx=6)
        ttk.Label(g, text='f16 padrão; bf16 melhor para alguns modelos',
                  foreground='gray').grid(row=1, column=2, sticky='w', padx=6)

    def _build_reasoning_section(self):
        f = self._section('Raciocínio / Thinking (-rea)')

        g = ttk.Frame(f); g.pack(fill='x')

        self.reasoning_var = tk.StringVar(value=self.app.config.get('reasoning', 'auto'))
        self.reasoning_budget_var = tk.StringVar(value=self.app.config.get('reasoning_budget', '-1'))

        ttk.Label(g, text='Modo de Raciocínio:').grid(row=0, column=0, sticky='w', padx=6, pady=4)
        rea_cb = ttk.Combobox(g, textvariable=self.reasoning_var,
                              values=REASONING_OPTS, width=8, state='readonly')
        rea_cb.grid(row=0, column=1, sticky='w', padx=6)

        hints = {'auto': 'Modelo decide (padrão — Qwen3 usa thinking)',
                 'on':   'Força thinking ativo em todas as respostas',
                 'off':  'Desativa thinking — mais rápido, sem <think>'}
        self._rea_hint = ttk.Label(g, text=hints.get(self.reasoning_var.get(), ''), foreground='#2980b9')
        self._rea_hint.grid(row=0, column=2, sticky='w', padx=6)

        def _on_rea_change(event=None):
            self._rea_hint.config(text=hints.get(self.reasoning_var.get(), ''))
        rea_cb.bind('<<ComboboxSelected>>', _on_rea_change)

        ttk.Label(g, text='Budget de tokens (-1 = ilimitado, 0 = desabilitado):').grid(
            row=1, column=0, sticky='w', padx=6, pady=4)
        ttk.Entry(g, textvariable=self.reasoning_budget_var, width=8).grid(
            row=1, column=1, sticky='w', padx=6)
        ttk.Label(g, text='Ex: 1024 = limita o raciocínio a 1024 tokens → mais rápido',
                  foreground='gray').grid(row=1, column=2, sticky='w', padx=6)

    def _build_spec_section(self):
        f = self._section('Especulativo / MTP (Multi-Token Prediction)')

        self.spec_var = tk.BooleanVar(value=self.app.config.get('spec_enabled', False))
        ttk.Checkbutton(f,
            text='Habilitar Decodificação Especulativa — usa modelo draft para acelerar geração',
            variable=self.spec_var, command=self._toggle_spec).pack(anchor='w')

        self.spec_frame = ttk.Frame(f)
        self.spec_frame.pack(fill='x', padx=20, pady=6)
        g = ttk.Frame(self.spec_frame); g.pack(fill='x')

        self.spec_model_var   = tk.StringVar(value=self.app.config.get('spec_draft_model', ''))
        self.spec_nmax_var    = tk.StringVar(value=self.app.config.get('spec_draft_n_max', '5'))
        self.spec_nmin_var    = tk.StringVar(value=self.app.config.get('spec_draft_n_min', '0'))
        self.spec_psplit_var  = tk.StringVar(value=self.app.config.get('spec_draft_p_split', '0.10'))
        self.spec_pmin_var    = tk.StringVar(value=self.app.config.get('spec_draft_p_min', '0.00'))

        ttk.Label(g, text='Modelo Draft (--model-draft):').grid(row=0, column=0, sticky='w', padx=6, pady=3)
        draft_row = ttk.Frame(g)
        draft_row.grid(row=0, column=1, columnspan=2, sticky='w', padx=6)
        ttk.Entry(draft_row, textvariable=self.spec_model_var, width=44).pack(side='left')
        ttk.Button(draft_row, text='…', width=3,
                   command=lambda: self._pick(self.spec_model_var, gguf=True)).pack(side='left', padx=4)

        rows = [
            ('N Draft Max (--spec-draft-n-max):', self.spec_nmax_var,   '5', 'Tokens previstos por passo'),
            ('N Draft Min (--spec-draft-n-min):', self.spec_nmin_var,   '0', 'Mínimo aceitável'),
            ('P Split (--draft-p-split):',        self.spec_psplit_var, '0.10', 'Prob. de split especulativo'),
            ('P Min (--draft-p-min):',            self.spec_pmin_var,   '0.00', 'Prob. mínima aceita'),
        ]
        for i, (lbl, var, default, hint) in enumerate(rows, 1):
            self._row(g, i, lbl, var, 8, hint)

        self._toggle_spec()

    def _toggle_spec(self):
        self._set_children_state(self.spec_frame, 'normal' if self.spec_var.get() else 'disabled')

    def _build_turbo_section(self):
        f = self._section('TurboQuant — Parâmetros para modelos quantizados TurboQuant')

        header = ttk.Frame(f)
        header.pack(fill='x')
        self.turbo_var = tk.BooleanVar(value=self.app.config.get('turbo_enabled', False))
        ttk.Checkbutton(header, text='Habilitar parâmetros TurboQuant',
                        variable=self.turbo_var, command=self._toggle_turbo).pack(side='left')
        ttk.Label(header, text=' TQ ', background='#e74c3c', foreground='white',
                  font=('TkDefaultFont', 9, 'bold'), relief='flat').pack(side='left', padx=6)

        ttk.Label(f, text='Modelos TurboQuant usam RoPE customizado e podem precisar de args extras.',
                  foreground='#2980b9').pack(anchor='w', pady=2)

        self.turbo_frame = ttk.Frame(f)
        self.turbo_frame.pack(fill='x', padx=20, pady=6)
        g = ttk.Frame(self.turbo_frame); g.pack(fill='x')

        self.tq_rope_base_var    = tk.StringVar(value=self.app.config.get('turbo_rope_freq_base', ''))
        self.tq_rope_scale_var   = tk.StringVar(value=self.app.config.get('turbo_rope_freq_scale', ''))
        self.tq_rope_scaling_var = tk.StringVar(value=self.app.config.get('turbo_rope_scaling', 'linear'))
        self.tq_extra_var        = tk.StringVar(value=self.app.config.get('turbo_extra_args', ''))

        rows = [
            ('RoPE Freq Base (--rope-freq-base):', self.tq_rope_base_var,  12, 'Ex: 1000000.0', False),
            ('RoPE Freq Scale (--rope-freq-scale):', self.tq_rope_scale_var, 12, 'Ex: 0.25', False),
        ]
        for i, (lbl, var, w, hint, _) in enumerate(rows):
            self._row(g, i, lbl, var, w, hint)

        ttk.Label(g, text='RoPE Scaling (--rope-scaling):').grid(row=2, column=0, sticky='w', padx=6, pady=3)
        ttk.Combobox(g, textvariable=self.tq_rope_scaling_var, values=ROPE_SCALINGS,
                     width=10, state='readonly').grid(row=2, column=1, sticky='w', padx=6)

        ttk.Label(g, text='Args extras TurboQuant:').grid(row=3, column=0, sticky='w', padx=6, pady=3)
        ttk.Entry(g, textvariable=self.tq_extra_var, width=40).grid(row=3, column=1, columnspan=2,
                                                                      sticky='w', padx=6)

        self._toggle_turbo()

    def _toggle_turbo(self):
        self._set_children_state(self.turbo_frame, 'normal' if self.turbo_var.get() else 'disabled')

    def _build_custom_section(self):
        f = self._section('Argumentos Personalizados')
        ttk.Label(f, text='Flags adicionais (separados por espaço, adicionados ao final do comando):').pack(anchor='w')
        self.custom_var = tk.StringVar(value=self.app.config.get('custom_args', ''))
        ttk.Entry(f, textvariable=self.custom_var, width=80).pack(fill='x', pady=4)
        ttk.Label(f, text='Ex: --verbose --log-format json --numa numactl',
                  foreground='gray', font=('TkDefaultFont', 8)).pack(anchor='w')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_children_state(self, widget, state):
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_children_state(child, state)

    def _pick(self, var, gguf=False):
        ft = [('GGUF', '*.gguf'), ('Todos', '*.*')] if gguf else [('Executável', '*'), ('Todos', '*.*')]
        p = filedialog.askopenfilename(filetypes=ft)
        if p:
            var.set(p)

    def save_all(self):
        c = self.app.config
        c['llama_server_bin']      = self.bin_var.get().strip()
        c['host']                  = self.host_var.get().strip()
        c['port']                  = self.port_var.get().strip()
        c['api_key']               = self.key_var.get().strip()
        c['ctx_size']              = self.ctx_var.get().strip()
        c['threads']               = self.thr_var.get().strip()
        c['n_gpu_layers']          = self.ngl_var.get().strip()
        c['batch_size']            = self.batch_var.get().strip()
        c['ubatch_size']           = self.ubatch_var.get().strip()
        c['parallel']              = self.par_var.get().strip()
        c['n_predict']             = self.np_var.get().strip()
        c['mmap']                  = self.mmap_var.get()
        c['mlock']                 = self.mlock_var.get()
        c['flash_attn']            = self.fa_var.get()
        c['cont_batching']         = self.cb_var.get()
        c['cache_type_k']          = self.ctk_var.get()
        c['cache_type_v']          = self.ctv_var.get()
        c['spec_enabled']          = self.spec_var.get()
        c['spec_draft_model']      = self.spec_model_var.get().strip()
        c['spec_draft_n_max']      = self.spec_nmax_var.get().strip()
        c['spec_draft_n_min']      = self.spec_nmin_var.get().strip()
        c['spec_draft_p_split']    = self.spec_psplit_var.get().strip()
        c['spec_draft_p_min']      = self.spec_pmin_var.get().strip()
        c['turbo_enabled']         = self.turbo_var.get()
        c['turbo_rope_freq_base']  = self.tq_rope_base_var.get().strip()
        c['turbo_rope_freq_scale'] = self.tq_rope_scale_var.get().strip()
        c['turbo_rope_scaling']    = self.tq_rope_scaling_var.get()
        c['turbo_extra_args']      = self.tq_extra_var.get().strip()
        c['reasoning']             = self.reasoning_var.get()
        c['reasoning_budget']      = self.reasoning_budget_var.get().strip()
        c['custom_args']           = self.custom_var.get().strip()
        save_config(c)
        self.app.tab_server._refresh_cmd()
        messagebox.showinfo('Salvo', 'Configurações salvas!')


# ─── Aba: Download ────────────────────────────────────────────────────────────

class DownloadTab:
    def __init__(self, nb, app: App):
        self.app = app
        self.frame = ttk.Frame(nb)
        self._cancel = threading.Event()
        self._dl_thread = None
        self._build()

    def _build(self):
        # HuggingFace
        hf = ttk.LabelFrame(self.frame, text='Download do HuggingFace', padding=10,
                             style='Section.TLabelframe')
        hf.pack(fill='x', padx=10, pady=8)
        g = ttk.Frame(hf); g.pack(fill='x')

        self.hf_repo_var  = tk.StringVar()
        self.hf_file_var  = tk.StringVar()
        self.hf_token_var = tk.StringVar(value=self.app.config.get('hf_token', ''))

        ttk.Label(g, text='Repo ID:').grid(row=0, column=0, sticky='w', pady=3)
        ttk.Entry(g, textvariable=self.hf_repo_var, width=55).grid(
            row=0, column=1, sticky='w', padx=6)
        ttk.Label(g, text='Ex: bartowski/Llama-3.2-3B-Instruct-GGUF', foreground='gray').grid(
            row=0, column=2, sticky='w')

        ttk.Label(g, text='Arquivo GGUF:').grid(row=1, column=0, sticky='w', pady=3)
        ttk.Entry(g, textvariable=self.hf_file_var, width=55).grid(
            row=1, column=1, sticky='w', padx=6)
        ttk.Label(g, text='Ex: Llama-3.2-3B-Instruct-Q4_K_M.gguf', foreground='gray').grid(
            row=1, column=2, sticky='w')

        ttk.Label(g, text='Token HF:').grid(row=2, column=0, sticky='w', pady=3)
        ttk.Entry(g, textvariable=self.hf_token_var, width=55, show='*').grid(
            row=2, column=1, sticky='w', padx=6)
        ttk.Label(g, text='Apenas para repos privados', foreground='gray').grid(
            row=2, column=2, sticky='w')

        ttk.Button(hf, text='⬇  Baixar do HuggingFace',
                   command=self._dl_hf).pack(anchor='w', pady=4)

        # URL Direta
        url_f = ttk.LabelFrame(self.frame, text='URL Direta', padding=10,
                               style='Section.TLabelframe')
        url_f.pack(fill='x', padx=10, pady=4)
        url_row = ttk.Frame(url_f)
        url_row.pack(fill='x')
        self.url_var = tk.StringVar()
        ttk.Label(url_row, text='URL:').pack(side='left')
        ttk.Entry(url_row, textvariable=self.url_var, width=65).pack(side='left', padx=6)
        ttk.Button(url_row, text='⬇  Baixar', command=self._dl_url).pack(side='left')

        # Destino
        dest_f = ttk.Frame(self.frame)
        dest_f.pack(fill='x', padx=10, pady=4)
        ttk.Label(dest_f, text='Salvar em:').pack(side='left')
        self.dest_var = tk.StringVar(value=self.app.config.get('models_dir', str(Path.home() / 'models')))
        ttk.Entry(dest_f, textvariable=self.dest_var, width=50).pack(side='left', padx=6)
        ttk.Button(dest_f, text='…', command=self._browse_dest).pack(side='left')

        # Progresso
        pf = ttk.LabelFrame(self.frame, text='Progresso', padding=10,
                            style='Section.TLabelframe')
        pf.pack(fill='x', padx=10, pady=4)
        self.prog_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(pf, variable=self.prog_var, maximum=100, length=600)
        self.prog_bar.pack(fill='x', pady=4)
        self.prog_lbl = ttk.Label(pf, text='Aguardando…')
        self.prog_lbl.pack(anchor='w')
        self.cancel_btn = ttk.Button(pf, text='Cancelar', command=self._do_cancel, state='disabled')
        self.cancel_btn.pack(anchor='e')

        # Modelos Populares
        pop_f = ttk.LabelFrame(self.frame, text='Modelos Populares — clique para preencher',
                               padding=10, style='Section.TLabelframe')
        pop_f.pack(fill='x', padx=10, pady=4)

        popular = [
            ('Llama 3.2 3B Q4_K_M',       'bartowski/Llama-3.2-3B-Instruct-GGUF',
             'Llama-3.2-3B-Instruct-Q4_K_M.gguf'),
            ('Llama 3.2 3B Q8',            'bartowski/Llama-3.2-3B-Instruct-GGUF',
             'Llama-3.2-3B-Instruct-Q8_0.gguf'),
            ('Qwen2.5 7B Q4_K_M',          'Qwen/Qwen2.5-7B-Instruct-GGUF',
             'qwen2.5-7b-instruct-q4_k_m.gguf'),
            ('Mistral 7B Q4_K_M',          'TheBloke/Mistral-7B-Instruct-v0.2-GGUF',
             'mistral-7b-instruct-v0.2.Q4_K_M.gguf'),
            ('DeepSeek R1 8B Q4_K_M',      'bartowski/DeepSeek-R1-Distill-Llama-8B-GGUF',
             'DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf'),
            ('Phi-3.5 Mini Q4_K_M',        'bartowski/Phi-3.5-mini-instruct-GGUF',
             'Phi-3.5-mini-instruct-Q4_K_M.gguf'),
            ('Gemma 3 4B Q4_K_M',          'bartowski/gemma-3-4b-it-GGUF',
             'gemma-3-4b-it-Q4_K_M.gguf'),
            ('SmolLM2 1.7B Q4_K_M',        'bartowski/SmolLM2-1.7B-Instruct-GGUF',
             'SmolLM2-1.7B-Instruct-Q4_K_M.gguf'),
            ('Nomic Embed v1.5 Q4 (embed)', 'nomic-ai/nomic-embed-text-v1.5-GGUF',
             'nomic-embed-text-v1.5.Q4_K_M.gguf'),
        ]
        for i, (name, repo, fname) in enumerate(popular):
            ttk.Button(pop_f, text=name,
                       command=lambda r=repo, f=fname: self._fill(r, f)
                       ).grid(row=i // 3, column=i % 3, padx=4, pady=2, sticky='w')

    # ── Lógica de Download ────────────────────────────────────────────────────

    def _fill(self, repo, fname):
        self.hf_repo_var.set(repo)
        self.hf_file_var.set(fname)

    def _browse_dest(self):
        d = filedialog.askdirectory()
        if d:
            self.dest_var.set(d)
            self.app.config['models_dir'] = d
            save_config(self.app.config)

    def _dl_hf(self):
        repo  = self.hf_repo_var.get().strip()
        fname = self.hf_file_var.get().strip()
        token = self.hf_token_var.get().strip()
        if not repo or not fname:
            messagebox.showwarning('Aviso', 'Preencha Repo ID e nome do arquivo.')
            return
        # Salva token
        self.app.config['hf_token'] = token
        save_config(self.app.config)
        url = f'https://huggingface.co/{repo}/resolve/main/{fname}'
        self._start(url, fname, token or None)

    def _dl_url(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning('Aviso', 'Informe a URL.')
            return
        fname = url.split('/')[-1].split('?')[0] or 'modelo.gguf'
        self._start(url, fname)

    def _start(self, url, fname, token=None):
        if self._dl_thread and self._dl_thread.is_alive():
            messagebox.showwarning('Aviso', 'Já há um download em andamento.')
            return
        dest = Path(self.dest_var.get())
        dest.mkdir(parents=True, exist_ok=True)
        dest_path = dest / fname
        self._cancel.clear()
        self.cancel_btn.config(state='normal')
        self.prog_var.set(0)
        self.prog_lbl.config(text=f'Iniciando: {fname}')
        self._dl_thread = threading.Thread(
            target=self._worker, args=(url, dest_path, token), daemon=True)
        self._dl_thread.start()

    def _worker(self, url, dest_path, token):
        try:
            headers = {'User-Agent': 'llama-manager/1.0'}
            if token:
                headers['Authorization'] = f'Bearer {token}'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                chunk = 1 << 20  # 1 MB
                t0 = time.time()
                with open(dest_path, 'wb') as fh:
                    while True:
                        if self._cancel.is_set():
                            fh.close()
                            dest_path.unlink(missing_ok=True)
                            self.frame.after(0, self._on_cancel)
                            return
                        data = resp.read(chunk)
                        if not data:
                            break
                        fh.write(data)
                        downloaded += len(data)
                        elapsed = max(time.time() - t0, 0.001)
                        speed = downloaded / elapsed
                        pct = (downloaded / total * 100) if total else 0
                        text = (f'{fmt_size(downloaded)} / {fmt_size(total)}'
                                f'  ({fmt_size(speed)}/s)'
                                if total else f'{fmt_size(downloaded)}  ({fmt_size(speed)}/s)')
                        self.frame.after(0, self._upd, pct, text)
            self.frame.after(0, self._on_done, dest_path)
        except Exception as e:
            self.frame.after(0, self._on_err, str(e))

    def _upd(self, pct, text):
        self.prog_var.set(pct)
        self.prog_lbl.config(text=text)

    def _on_done(self, path):
        self.prog_var.set(100)
        self.prog_lbl.config(text=f'Concluído: {path.name}')
        self.cancel_btn.config(state='disabled')
        self.app.tab_models.refresh()
        messagebox.showinfo('Download Concluído', f'Modelo salvo em:\n{path}')

    def _on_err(self, err):
        self.prog_lbl.config(text=f'Erro: {err}')
        self.cancel_btn.config(state='disabled')
        messagebox.showerror('Erro no Download', err)

    def _on_cancel(self):
        self.prog_var.set(0)
        self.prog_lbl.config(text='Download cancelado.')
        self.cancel_btn.config(state='disabled')

    def _do_cancel(self):
        self._cancel.set()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk(className='llama-manager')
    try:
        root.tk.call('tk', 'scaling', 1.2)
    except Exception:
        pass

    # Ícone da janela e da barra de tarefas
    icon_path = None
    for p in ICON_SEARCH:
        if p.exists():
            icon_path = p
            break

    if icon_path:
        try:
            icon = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon)
            root._icon_ref = icon  # evita garbage collection
        except Exception:
            pass

    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
