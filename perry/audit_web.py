"""Panel web de Perry: control de flota, seguimiento en vivo, arbitraje de zona y calibración.

  py audit_web.py     -> abrir http://localhost:8000  (o http://IP-de-la-PC:8000 desde un teléfono)

Fase 5:
- Muestra en vivo el estado de Perry (FREE, RECEIVING, SCANNING, PICKING, DROPPING, BLOCKED, STOP),
  el ocupante de la zona, los contadores delivered_total / sorted_total y el estado de Ferb y Phineas.
- Inicia automáticamente la clasificación al recibir /zone/release (auto_sort_on_release: true).
- Auto-despeje en estado BLOCKED: si la cámara ve 0 cubos durante 3 s, verifica reposo y pasa a FREE.
- Botones de operador: Habilitar Zona (FREE) y Bloquear Zona (STOP).
- Integración transparente con ROS 2 si rclpy está disponible (vía ros_node.py).
"""
import json
import os
import re
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cv2
import yaml

from audit import draw_plan
from reach import ensure_parked
from ros_node import start_ros_node, get_fleet_state
from sort_cubes import Log, open_arm, sort_loop
from vision import TopCamera
from zone_arbiter import PerryState, ZoneArbiter

YAML = HERE / "config" / "arm.yaml"
PORT = 8000

PAGE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Perry • Control de Flota y Visión</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: rgba(22, 27, 34, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --text: #e6edf3;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #238636;
      --green-glow: #2ea043;
      --red: #da3633;
      --orange: #d29922;
      --purple: #a371f7;
      --blue: #1f6feb;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 16px;
      min-height: 100vh;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 14px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 10px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand h1 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand span {
      font-size: 13px;
      color: var(--text-muted);
      background: rgba(255, 255, 255, 0.05);
      padding: 3px 8px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
      margin-bottom: 16px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 14px;
      backdrop-filter: blur(8px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .card-title {
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    .badge-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }
    .st-FREE { background: rgba(46, 160, 67, 0.2); color: #3fb950; border: 1px solid rgba(46, 160, 67, 0.4); }
    .st-FREE .badge-dot { background: #3fb950; box-shadow: 0 0 6px #3fb950; }
    .st-RECEIVING { background: rgba(56, 139, 253, 0.2); color: #58a6ff; border: 1px solid rgba(56, 139, 253, 0.4); }
    .st-RECEIVING .badge-dot { background: #58a6ff; box-shadow: 0 0 6px #58a6ff; }
    .st-SCANNING { background: rgba(163, 113, 247, 0.2); color: #bc8cff; border: 1px solid rgba(163, 113, 247, 0.4); }
    .st-SCANNING .badge-dot { background: #bc8cff; }
    .st-PICKING, .st-DROPPING { background: rgba(210, 153, 34, 0.2); color: #d29922; border: 1px solid rgba(210, 153, 34, 0.4); }
    .st-PICKING .badge-dot, .st-DROPPING .badge-dot { background: #d29922; }
    .st-BLOCKED { background: rgba(248, 81, 73, 0.2); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.4); }
    .st-BLOCKED .badge-dot { background: #f85149; box-shadow: 0 0 6px #f85149; }
    .st-STOP { background: rgba(110, 118, 129, 0.2); color: #8b949e; border: 1px solid rgba(110, 118, 129, 0.4); }
    .st-STOP .badge-dot { background: #8b949e; }
    .metrics {
      display: flex;
      gap: 14px;
      margin-top: 10px;
    }
    .metric {
      flex: 1;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 6px;
      padding: 8px 10px;
      border: 1px solid rgba(255, 255, 255, 0.04);
    }
    .metric-val {
      font-size: 18px;
      font-weight: 700;
      color: #fff;
    }
    .metric-lbl {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 12px;
    }
    button {
      font-family: inherit;
      font-size: 13px;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: 6px;
      border: 1px solid transparent;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    button:hover { opacity: 0.9; transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    .btn-green { background: #238636; color: #fff; border-color: rgba(255, 255, 255, 0.1); }
    .btn-blue { background: #1f6feb; color: #fff; border-color: rgba(255, 255, 255, 0.1); }
    .btn-red { background: #da3633; color: #fff; border-color: rgba(255, 255, 255, 0.1); }
    .btn-amber { background: #d29922; color: #000; border-color: rgba(255, 255, 255, 0.1); }
    .btn-dark { background: #21262d; color: var(--text); border: 1px solid var(--card-border); }
    .btn-outline { background: transparent; color: var(--text); border: 1px solid var(--card-border); }
    .tabs {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
    }
    .tab-btn {
      background: rgba(255, 255, 255, 0.04);
      color: var(--text-muted);
      border: 1px solid var(--card-border);
      padding: 8px 16px;
      border-radius: 6px;
    }
    .tab-btn.active {
      background: var(--accent);
      color: #0d1117;
      font-weight: 700;
      border-color: var(--accent);
    }
    .views {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }
    .img-box {
      background: #000;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      overflow: hidden;
      aspect-ratio: 4/3;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .img-box img, .img-box canvas {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    #log {
      background: #05070a;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      height: 200px;
      overflow-y: auto;
      white-space: pre-wrap;
      color: #c9d1d9;
      line-height: 1.5;
    }
    #toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #1f6feb;
      color: #fff;
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      box-shadow: 0 6px 16px rgba(0,0,0,0.5);
      display: none;
      z-index: 100;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>Perry</h1>
      <span>Brazo 5 DOF • Árbitro de Zona</span>
      <span id="ros-tag" style="display:none">ROS 2 Conectado</span>
    </div>
    <div id="sub-status" style="font-size: 13px; color: var(--text-muted);">Iniciando panel...</div>
  </header>

  <!-- Métricas de Perry y Flota -->
  <div class="grid">
    <!-- Tarjeta de Perry -->
    <div class="card">
      <div class="card-title">
        <span>Estado de Perry</span>
        <div id="perry-badge" class="badge st-STOP"><div class="badge-dot"></div><span id="perry-state">STOP</span></div>
      </div>
      <div style="font-size: 14px; margin-bottom: 8px;">
        Ocupante Zona: <strong id="perry-occ" style="color:#58a6ff;">perry</strong>
      </div>
      <div class="metrics">
        <div class="metric">
          <div class="metric-val" id="cnt-sorted">0</div>
          <div class="metric-lbl">Clasificados (Perry)</div>
        </div>
        <div class="metric">
          <div class="metric-val" id="cnt-delivered">0</div>
          <div class="metric-lbl">Entregados (Carros)</div>
        </div>
        <div class="metric">
          <div class="metric-val" id="perry-park">--</div>
          <div class="metric-lbl">Reposo Físico</div>
        </div>
      </div>
    </div>

    <!-- Tarjeta de Ferb (Amarillos) -->
    <div class="card" style="border-top: 3px solid #e3b341;">
      <div class="card-title">
        <span>Ferb (Recolector)</span>
        <div id="ferb-badge" class="badge st-STOP"><div class="badge-dot"></div><span id="ferb-state">Offline</span></div>
      </div>
      <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 6px;">
        Carga: <strong id="ferb-carrying" style="color:var(--text);">No</strong>
      </div>
      <div class="metrics">
        <div class="metric">
          <div class="metric-val" id="ferb-delivered">0</div>
          <div class="metric-lbl">Entregas reportadas</div>
        </div>
        <div class="metric">
          <div class="metric-val" id="ferb-seen">--</div>
          <div class="metric-lbl">Último contacto</div>
        </div>
      </div>
    </div>

    <!-- Tarjeta de Phineas (Azules) -->
    <div class="card" style="border-top: 3px solid #58a6ff;">
      <div class="card-title">
        <span>Phineas (Recolector)</span>
        <div id="phineas-badge" class="badge st-STOP"><div class="badge-dot"></div><span id="phineas-state">Offline</span></div>
      </div>
      <div style="font-size: 13px; color: var(--text-muted); margin-bottom: 6px;">
        Carga: <strong id="phineas-carrying" style="color:var(--text);">No</strong>
      </div>
      <div class="metrics">
        <div class="metric">
          <div class="metric-val" id="phineas-delivered">0</div>
          <div class="metric-lbl">Entregas reportadas</div>
        </div>
        <div class="metric">
          <div class="metric-val" id="phineas-seen">--</div>
          <div class="metric-lbl">Último contacto</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Barra de Acciones y Controles de Zona -->
  <div class="controls">
    <button class="btn-green" onclick="postAction('/enable_zone', 'Habilitando zona...')">&#10004; Habilitar Zona (FREE)</button>
    <button class="btn-red" onclick="postAction('/block_zone', 'Bloqueando zona...')">&#9940; Bloquear Zona (STOP)</button>
    <div style="width: 1px; height: 28px; background: var(--card-border); margin: 0 4px;"></div>
    <button class="btn-blue" onclick="start('run')">&#9654; Iniciar</button>
    <button class="btn-dark" onclick="start('amarillo')">&#9654; Todo al Amarillo</button>
    <button class="btn-outline" onclick="start('look')">&#128065; Solo Mirar</button>
    <button class="btn-outline" onclick="start('step')">&#128099; Paso a Paso</button>
    <button id="btn-go" class="btn-amber" style="display:none;" onclick="postAction('/go')">&#10004; Ejecutar Paso</button>
    <button class="btn-red" onclick="postAction('/stop', 'Cancelando...')">&#9209; Cancelar Ciclo</button>
  </div>

  <!-- Pestañas de Visualización -->
  <div class="tabs">
    <button id="t1" class="tab-btn active" onclick="tab('seg')">Seguimiento en Vivo</button>
    <button id="t2" class="tab-btn" onclick="tab('cal')">Calibrar Cámara Cenital</button>
  </div>

  <!-- Contenedor Seguimiento -->
  <div id="seg">
    <div class="views">
      <div>
        <div style="font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">CÁMARA CENITAL (EN VIVO)</div>
        <div class="img-box"><img id="live" alt="Live Camera"></div>
      </div>
      <div>
        <div style="font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">PLANIFICACIÓN Y DECISIÓN</div>
        <div class="img-box"><img id="plan" alt="Planner Decision"></div>
      </div>
    </div>
    <div style="font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">REGISTRO DEL SISTEMA</div>
    <div id="log"></div>
  </div>

  <!-- Contenedor Calibración -->
  <div id="cal" style="display:none">
    <div class="card" style="margin-bottom: 12px;">
      <p style="font-size: 13px; line-height: 1.5; margin-bottom: 10px;">
        Verifica que el brazo esté fuera de la vista (en <code>vista</code>). Haz clic en las 4 esquinas de la hoja milimetrada en este orden:<br>
        <strong>1. Lejana izquierda &rarr; 2. Lejana derecha &rarr; 3. Cercana derecha &rarr; 4. Cercana izquierda</strong>
      </p>
      <div style="display:flex; gap: 8px;">
        <button class="btn-outline" onclick="pts=[];drawc()">Repetir Selección</button>
        <button class="btn-green" onclick="savec()">Guardar en arm.yaml</button>
      </div>
    </div>
    <div class="img-box" style="aspect-ratio: auto; min-height: 400px;">
      <canvas id="cv"></canvas>
    </div>
    <div id="cmsg" style="margin-top: 8px; font-size: 13px; color: var(--accent);"></div>
  </div>

  <div id="toast"></div>

  <script>
    let t = 'seg', pts = [], raw = new Image(), cv = document.getElementById('cv'), cx = cv.getContext('2d');

    function showToast(msg) {
      const el = document.getElementById('toast');
      el.textContent = msg;
      el.style.display = 'block';
      setTimeout(() => el.style.display = 'none', 3000);
    }

    function tab(x) {
      t = x;
      document.getElementById('seg').style.display = x === 'seg' ? 'block' : 'none';
      document.getElementById('cal').style.display = x === 'cal' ? 'block' : 'none';
      document.getElementById('t1').className = x === 'seg' ? 'tab-btn active' : 'tab-btn';
      document.getElementById('t2').className = x === 'cal' ? 'tab-btn active' : 'tab-btn';
    }

    function postAction(url, msg) {
      if (msg) showToast(msg);
      fetch(url, { method: 'POST' }).then(r => r.text()).then(txt => {
        if (txt) showToast(txt);
      }).catch(err => showToast("Error: " + err));
    }

    function start(mode) {
      showToast("Iniciando: " + mode);
      fetch('/start', { method: 'POST', body: mode }).then(r => r.text()).then(x => {
        if (x) showToast(x);
      }).catch(err => showToast("Error: " + err));
    }

    function drawc() {
      cv.width = raw.width; cv.height = raw.height;
      cx.drawImage(raw, 0, 0);
      cx.fillStyle = 'red'; cx.font = '16px sans-serif';
      pts.forEach((p, i) => {
        cx.beginPath(); cx.arc(p[0], p[1], 5, 0, 7); cx.fill();
        cx.fillText(i + 1, p[0] + 8, p[1] - 8);
      });
      if (pts.length > 1) {
        cx.strokeStyle = '#2ea043'; cx.lineWidth = 2;
        cx.beginPath(); cx.moveTo(...pts[0]);
        pts.forEach(p => cx.lineTo(...p));
        if (pts.length === 4) cx.closePath();
        cx.stroke();
      }
    }
    raw.onload = drawc;

    cv.onclick = e => {
      if (pts.length >= 4) return;
      const r = cv.getBoundingClientRect();
      pts.push([(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]);
      drawc();
    };

    function savec() {
      if (pts.length !== 4) { alert('Debes marcar exactamente las 4 esquinas'); return; }
      fetch('/corners', { method: 'POST', body: JSON.stringify(pts) }).then(r => r.text()).then(x => {
        document.getElementById('cmsg').textContent = x;
        pts = [];
        tab('seg');
      });
    }

    // Actualización periódica en vivo
    setInterval(() => {
      const q = '?t=' + Date.now();
      if (t === 'seg') {
        document.getElementById('live').src = '/live.jpg' + q;
        document.getElementById('plan').src = '/plan.jpg' + q;
      } else if (pts.length === 0) {
        raw.src = '/raw.jpg' + q;
      }

      fetch('/status').then(r => r.json()).then(s => {
        // Estado general
        document.getElementById('sub-status').textContent = (s.running ? 'EN EJECUCIÓN: ' : 'Detenido: ') + s.status;
        document.getElementById('btn-go').style.display = s.waiting ? 'inline-flex' : 'none';

        // Perry Arbiter
        const arb = s.arbiter || {};
        const pBadge = document.getElementById('perry-badge');
        pBadge.className = 'badge st-' + (arb.state || 'STOP');
        document.getElementById('perry-state').textContent = arb.state || 'STOP';
        document.getElementById('perry-occ').textContent = arb.occupant ? arb.occupant : (arb.state === 'FREE' ? 'ZONA LIBRE ("")' : 'perry');
        document.getElementById('cnt-sorted').textContent = arb.sorted_total || 0;
        document.getElementById('cnt-delivered').textContent = arb.delivered_total || 0;
        document.getElementById('perry-park').textContent = arb.parked_ok ? 'OK' : 'No';

        // Ferb
        const fl = s.fleet || {};
        const ferb = fl.ferb || {};
        const fBadge = document.getElementById('ferb-badge');
        fBadge.className = 'badge st-' + (ferb.state === 'desconectado' ? 'STOP' : 'RECEIVING');
        document.getElementById('ferb-state').textContent = ferb.state || 'Offline';
        document.getElementById('ferb-carrying').textContent = ferb.carrying ? 'Sí' : 'No';
        document.getElementById('ferb-delivered').textContent = ferb.delivered || 0;
        document.getElementById('ferb-seen').textContent = ferb.updated_at > 0 ? Math.round(Date.now()/1000 - ferb.updated_at) + 's' : '--';

        // Phineas
        const phin = fl.phineas || {};
        const phBadge = document.getElementById('phineas-badge');
        phBadge.className = 'badge st-' + (phin.state === 'desconectado' ? 'STOP' : 'RECEIVING');
        document.getElementById('phineas-state').textContent = phin.state || 'Offline';
        document.getElementById('phineas-carrying').textContent = phin.carrying ? 'Sí' : 'No';
        document.getElementById('phineas-delivered').textContent = phin.delivered || 0;
        document.getElementById('phineas-seen').textContent = phin.updated_at > 0 ? Math.round(Date.now()/1000 - phin.updated_at) + 's' : '--';

        // Log consola
        const l = document.getElementById('log');
        const atEnd = l.scrollTop + l.clientHeight >= l.scrollHeight - 10;
        l.textContent = (s.log || []).join('\\n');
        if (atEnd) l.scrollTop = l.scrollHeight;
      }).catch(e => console.warn(e));
    }, 700);
  </script>
</body>
</html>"""


class S:
    """Estado compartido entre el servidor HTTP, la cámara, el árbitro y el ciclo de control."""
    lock = threading.Lock()
    live = plan = raw = None
    log = deque(maxlen=300)
    status = "listo"
    running = False
    stop = threading.Event()
    go = threading.Event()
    waiting = False
    cfg = None
    cam = None
    arbiter = None
    ros_node = None
    last_blocked_check = 0.0


def jpg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def camera_loop():
    """Mantiene la cámara cenital abierta, actualiza streams y ejecuta chequeos automáticos."""
    while True:
        cfg = S.cfg
        try:
            with TopCamera(cfg) as cam:
                S.cam = cam
                while S.cfg is cfg or S.running:      # no cambiar la cámara en medio de un ciclo
                    cubes, img = cam.find_cubes()
                    live = img if S.running else draw_plan(img, cam, cfg, cubes)
                    with S.lock:
                        S.live, S.raw = jpg(live), jpg(cam.frame())
                        if not S.running and S.plan is None:
                            S.plan = S.live

                    # 1. Chequeo de expiración de lease de carros
                    if S.arbiter.tick():
                        S.log.append("[LEASE] El turno del carro venció (60s). Zona liberada.")

                    # 2. Activación automática tras entrega (trigger_sort activado por /zone/release)
                    if S.arbiter.trigger_sort:
                        if S.cfg.get("auto_sort_on_release", True):
                            if not S.running:
                                S.arbiter.consume_trigger_sort()
                                S.log.append("[AUTO] Cubo entregado por carro. Lanzando ciclo de clasificación...")
                                threading.Thread(target=run_cycle, args=("run",), daemon=True).start()
                            else:
                                S.arbiter.consume_trigger_sort()
                                S.log.append("[AUTO] Perry ya en marcha; atenderá el cubo en el siguiente ciclo.")
                        else:
                            S.arbiter.consume_trigger_sort()

                    # 3. Auto-recuperación de estado BLOCKED cada blocked_check_interval_s (3.0 s)
                    if not S.running and S.arbiter.state == PerryState.BLOCKED:
                        now = time.time()
                        interval = float(S.cfg.get("blocked_check_interval_s", 3.0))
                        if now - S.last_blocked_check >= interval:
                            S.last_blocked_check = now
                            if len(cubes) == 0:
                                S.log.append("[AUTO-DESPEJE] 0 cubos en zona bloqueada. Verificando reposo físico...")
                                try:
                                    m_check = open_arm(cfg)
                                    try:
                                        if ensure_parked(m_check, cfg):
                                            S.arbiter.set_state(PerryState.FREE, carrying=False, parked_ok=True)
                                            S.status = "Zona despejada -> FREE"
                                            S.log.append("[AUTO-DESPEJE] Reposo verificado. Perry volvió a estado FREE.")
                                        else:
                                            S.arbiter.set_state(PerryState.STOP, carrying=False, parked_ok=False)
                                            S.log.append("[AUTO-DESPEJE] Falló verificación de reposo. Estado STOP.")
                                    finally:
                                        m_check.close()
                                except Exception as ex:
                                    S.log.append(f"[AUTO-DESPEJE Error] {ex}")

                    time.sleep(0.25)
        except Exception as e:
            S.status = f"cámara: {e}"
            time.sleep(2)


def wait_approval():
    """Modo paso a paso: espera el botón 'Ejecutar este paso' (o Cancelar)."""
    S.go.clear()
    S.waiting = True
    try:
        while not S.go.is_set() and not S.stop.is_set():
            time.sleep(0.1)
    finally:
        S.waiting = False


def run_cycle(mode):
    """Ejecuta el ciclo de clasificación en un hilo separado."""
    S.running = True
    S.status = "arrancando"
    S.stop.clear()
    m = None
    try:
        cfg = S.cfg
        log = Log(cfg, sink=S.log.append,
                  image_sink=lambda name, img: name.startswith("plan") and setattr(S, "plan", jpg(img)))
        m = open_arm(cfg)
        sort_loop(
            cfg, m, S.cam, log,
            run=(mode != "look"),
            to=("amarillo" if mode == "amarillo" else None),
            stop=S.stop,
            status=lambda t: setattr(S, "status", t),
            approve=wait_approval if mode == "step" else None,
            arbiter=S.arbiter
        )
    except Exception as e:
        S.log.append(f"[ERROR] {e}")
        S.status = f"error: {e}"
        if S.arbiter:
            S.arbiter.set_state(PerryState.STOP, carrying=False, parked_ok=False)
    finally:
        if m:
            m.close()
        S.running = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        for name in ("live", "plan", "raw"):
            if self.path.startswith(f"/{name}.jpg"):
                with S.lock:
                    data = getattr(S, name)
                return self.send(data or b"", "image/jpeg", 200 if data else 503)
        if self.path.startswith("/status"):
            payload = {
                "running": S.running,
                "status": S.status,
                "waiting": S.waiting,
                "log": list(S.log),
                "arbiter": S.arbiter.snapshot() if S.arbiter else {},
                "fleet": get_fleet_state(),
            }
            return self.send(json.dumps(payload).encode(), "application/json")
        self.send(PAGE.encode("utf-8"))

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)).decode()

        # Iniciar ciclo
        if self.path == "/start":
            if S.running:
                return self.send("Ya está en marcha.".encode())
            if S.cam is None:
                return self.send("La cámara todavía no está lista.".encode())
            threading.Thread(target=run_cycle, args=(body,), daemon=True).start()
            return self.send("Ciclo iniciado.".encode())

        # Modo paso a paso
        if self.path == "/go":
            S.go.set()
            return self.send(b"")

        # Cancelar
        if self.path == "/stop":
            S.stop.set()
            S.status = "cancelando: termina el movimiento y estaciona"
            return self.send("Cancelación solicitada.".encode())

        # Habilitar zona manualmente como FREE (Fase 5)
        if self.path == "/enable_zone":
            if S.running:
                return self.send("No se puede habilitar mientras Perry está en marcha.".encode(), code=400)
            if S.cam is None:
                return self.send("La cámara cenital no está lista.".encode(), code=503)

            cubes, _ = S.cam.find_cubes()
            if len(cubes) > 0:
                return self.send(f"No se puede habilitar: aún quedan {len(cubes)} cubos en la zona.".encode(), code=400)

            try:
                with open_arm(S.cfg) as m_enable:
                    if not ensure_parked(m_enable, S.cfg):
                        S.arbiter.set_state(PerryState.STOP, carrying=False, parked_ok=False)
                        return self.send("Fallo físico: el brazo no está energizado o no llegó a vista.".encode(), code=500)
            except Exception as e:
                return self.send(f"Error de comunicación con la Maestro: {e}".encode(), code=500)

            S.arbiter.set_state(PerryState.FREE, carrying=False, parked_ok=True)
            S.status = "Zona habilitada manualmente (FREE)"
            S.log.append("[OPERADOR] Zona habilitada manualmente como FREE (0 cubos y reposo OK).")
            return self.send("Zona habilitada (FREE). Lista para recibir entregas de carros.".encode())

        # Bloquear zona manualmente en STOP (Fase 5)
        if self.path == "/block_zone":
            if S.running:
                S.stop.set()
            S.arbiter.set_state(PerryState.STOP, carrying=False, parked_ok=False)
            S.status = "Zona bloqueada por operador (STOP)"
            S.log.append("[OPERADOR] Zona bloqueada en estado STOP por el operador.")
            return self.send("Zona bloqueada (STOP). Entregas suspendidas.".encode())

        # Calibración de homografía
        if self.path == "/corners":
            if S.running:
                return self.send("No se puede calibrar con el ciclo en marcha.".encode())
            pts = json.loads(body)
            new = "corners_px: [" + ", ".join(f"[{u:.1f}, {v:.1f}]" for u, v in pts) + "]"
            YAML.write_text(re.sub(r"corners_px: \[\[.*?\]\]", new, YAML.read_text(encoding="utf-8"), count=1),
                            encoding="utf-8")
            S.cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))
            S.plan = None
            return self.send(f"Guardado: {new}. Revisá en Seguimiento que la zona coincida.".encode())

        self.send(b"no", code=404)


def main():
    S.cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    S.arbiter = ZoneArbiter(initial_state=PerryState.STOP)

    # Iniciar nodo ROS 2 en background si rclpy está disponible
    S.ros_node = start_ros_node(S.arbiter)

    # Bucle de cámara cenital y supervisión
    threading.Thread(target=camera_loop, daemon=True).start()

    print(f"Panel web de Perry iniciado en http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
