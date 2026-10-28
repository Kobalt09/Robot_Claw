"""Panel web de Perry: iniciar / cancelar el ciclo, seguirlo en vivo, auditar y recalibrar la cámara.

  py audit_web.py     -> abrir http://localhost:8000  (o http://IP-de-la-PC:8000 desde un teléfono)

- Iniciar: clasifica cada color a su caja. "Todo al amarillo": para pruebas. "Solo mirar": estaciona,
  planifica y muestra la decisión sin agarrar nada.
- Cancelar: termina el movimiento en curso, sube y estaciona (no corta los servos: el brazo
  caería). Para una emergencia real: el interruptor de la fuente.
- Seguimiento: cámara en vivo + última imagen de planificación + estado + registro.
- Calibrar cámara: clic en las 4 esquinas del rectángulo y Guardar (arm.yaml, camera.corners_px).
La web es la dueña de la cámara: no correr sort_cubes.py en la terminal a la vez.
Puerto de la Maestro: variable PERRY_PORT o el de arm.yaml.
"""
import json
import re
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import cv2
import yaml

from audit import draw_plan
from sort_cubes import Log, open_arm, sort_loop
from vision import TopCamera

HERE = Path(__file__).parent
YAML = HERE / "config" / "arm.yaml"
PORT = 8000

PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Perry</title>
<style>body{font-family:sans-serif;background:#1e1e1e;color:#eee;margin:12px}
button{font-size:15px;margin:3px;padding:7px 12px;border-radius:6px;border:0;cursor:pointer}
.go{background:#2e7d32;color:#fff}.stop{background:#c62828;color:#fff}.alt{background:#555;color:#fff}
#st{font-size:17px;color:#ffd54f;margin:8px 0}#log{background:#111;padding:8px;height:220px;overflow:auto;
font-family:monospace;font-size:12px;white-space:pre-wrap}.row{display:flex;gap:8px;flex-wrap:wrap}
.row>div{flex:1;min-width:300px}img,canvas{max-width:100%;border:1px solid #555}
.tabs button{background:#333;color:#ddd}.tabs .on{background:#1565c0;color:#fff}</style></head><body>
<h2 style="margin:4px 0">Perry</h2>
<div><button class="go" onclick="start('run')">&#9654; Iniciar</button>
<button class="go" onclick="start('amarillo')">&#9654; Iniciar (todo al amarillo)</button>
<button class="alt" onclick="start('look')">&#128065; Solo mirar</button>
<button class="alt" onclick="start('step')">&#128099; Paso a paso</button>
<button id="go" class="go" style="display:none;background:#f9a825;color:#000" onclick="fetch('/go',{method:'POST'})">&#10004; Ejecutar este paso</button>
<button class="stop" onclick="fetch('/stop',{method:'POST'})">&#9209; Cancelar</button></div>
<div id="st">...</div>
<div class="tabs"><button id="t1" class="on" onclick="tab('seg')">Seguimiento</button>
<button id="t2" onclick="tab('cal')">Calibrar cámara</button></div>
<div id="seg"><div class="row"><div><b>Cámara en vivo</b><br><img id="live"></div>
<div><b>Última decisión</b><br><img id="plan"></div></div><b>Registro</b><div id="log"></div></div>
<div id="cal" style="display:none"><p>Brazo fuera de la vista. Clic: 1 lejana izq. &rarr; 2 lejana der. &rarr;
3 cercana der. &rarr; 4 cercana izq. <button class="alt" onclick="pts=[];drawc()">Repetir</button>
<button class="go" onclick="savec()">Guardar en arm.yaml</button></p><canvas id="cv"></canvas><div id="cmsg"></div></div>
<script>
let t='seg',pts=[],raw=new Image(),cv=document.getElementById('cv'),cx=cv.getContext('2d');
function tab(x){t=x;document.getElementById('seg').style.display=x=='seg'?'block':'none';
 document.getElementById('cal').style.display=x=='cal'?'block':'none';
 document.getElementById('t1').className=x=='seg'?'on':'';document.getElementById('t2').className=x=='cal'?'on':''}
function start(mode){fetch('/start',{method:'POST',body:mode}).then(r=>r.text()).then(x=>{if(x)alert(x)})}
function drawc(){cv.width=raw.width;cv.height=raw.height;cx.drawImage(raw,0,0);cx.fillStyle='red';
 cx.font='16px sans-serif';pts.forEach((p,i)=>{cx.beginPath();cx.arc(p[0],p[1],5,0,7);cx.fill();cx.fillText(i+1,p[0]+7,p[1]-7)});
 if(pts.length>1){cx.strokeStyle='lime';cx.beginPath();cx.moveTo(...pts[0]);pts.forEach(p=>cx.lineTo(...p));
 if(pts.length==4)cx.closePath();cx.stroke()}}
raw.onload=drawc;
cv.onclick=e=>{if(pts.length>=4)return;const r=cv.getBoundingClientRect();
 pts.push([(e.clientX-r.left)*cv.width/r.width,(e.clientY-r.top)*cv.height/r.height]);drawc()}
function savec(){if(pts.length!=4){alert('Faltan esquinas');return}
 fetch('/corners',{method:'POST',body:JSON.stringify(pts)}).then(r=>r.text()).then(x=>{
 document.getElementById('cmsg').textContent=x;pts=[];tab('seg')})}
setInterval(()=>{const q='?t='+Date.now();
 if(t=='seg'){document.getElementById('live').src='/live.jpg'+q;document.getElementById('plan').src='/plan.jpg'+q}
 else if(pts.length==0)raw.src='/raw.jpg'+q;
 fetch('/status').then(r=>r.json()).then(s=>{document.getElementById('st').textContent=
 (s.running?'EN MARCHA: ':'Detenido: ')+s.status;document.getElementById('go').style.display=s.waiting?'inline-block':'none';const l=document.getElementById('log');
 const atEnd=l.scrollTop+l.clientHeight>=l.scrollHeight-5;l.textContent=s.log.join('\\n');if(atEnd)l.scrollTop=l.scrollHeight})},700);
</script></body></html>"""


class S:
    """Estado compartido entre el servidor, la cámara y el ciclo."""
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


def jpg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def camera_loop():
    """Mantiene la cámara abierta y la imagen en vivo; reabre si cambia la calibración."""
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
                    time.sleep(0.25)
        except Exception as e:
            S.status = f"cámara: {e}"; time.sleep(2)


def wait_approval():
    """Modo paso a paso: espera el botón 'Ejecutar este paso' (o Cancelar)."""
    S.go.clear(); S.waiting = True
    try:
        while not S.go.is_set() and not S.stop.is_set():
            time.sleep(0.1)
    finally:
        S.waiting = False


def run_cycle(mode):
    S.running, S.status = True, "arrancando"
    S.stop.clear()
    m = None
    try:
        cfg = S.cfg
        log = Log(cfg, sink=S.log.append,
                  image_sink=lambda name, img: name.startswith("plan") and setattr(S, "plan", jpg(img)))
        m = open_arm(cfg)
        sort_loop(cfg, m, S.cam, log, run=(mode != "look"), to=("amarillo" if mode == "amarillo" else None),
                  stop=S.stop, status=lambda t: setattr(S, "status", t),
                  approve=wait_approval if mode == "step" else None)
    except Exception as e:
        S.log.append(f"[ERROR] {e}"); S.status = f"error: {e}"
    finally:
        if m:
            m.close()
        S.running = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="text/html; charset=utf-8", code=200):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        for name in ("live", "plan", "raw"):
            if self.path.startswith(f"/{name}.jpg"):
                with S.lock:
                    data = getattr(S, name)
                return self.send(data or b"", "image/jpeg", 200 if data else 503)
        if self.path.startswith("/status"):
            return self.send(json.dumps({"running": S.running, "status": S.status, "waiting": S.waiting, "log": list(S.log)}).encode(),
                             "application/json")
        self.send(PAGE.encode("utf-8"))

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)).decode()
        if self.path == "/start":
            if S.running:
                return self.send("Ya está en marcha.".encode())
            if S.cam is None:
                return self.send("La cámara todavía no está lista.".encode())
            threading.Thread(target=run_cycle, args=(body,), daemon=True).start()
            return self.send(b"")
        if self.path == "/go":
            S.go.set()
            return self.send(b"")
        if self.path == "/stop":
            S.stop.set(); S.status = "cancelando: termina el movimiento y estaciona"
            return self.send(b"")
        if self.path == "/corners":
            if S.running:
                return self.send("No se puede calibrar con el ciclo en marcha.".encode())
            pts = json.loads(body)
            new = "corners_px: [" + ", ".join(f"[{u:.1f}, {v:.1f}]" for u, v in pts) + "]"
            YAML.write_text(re.sub(r"corners_px: \[\[.*?\]\]", new, YAML.read_text(encoding="utf-8"), count=1),
                            encoding="utf-8")
            S.cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))   # la cámara se reabre con esto
            S.plan = None
            return self.send(f"Guardado: {new}. Revisá en Seguimiento que la zona coincida.".encode())
        self.send(b"no", code=404)


def main():
    S.cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    threading.Thread(target=camera_loop, daemon=True).start()
    print(f"Abrir http://localhost:{PORT}  (desde otro dispositivo: http://IP-de-esta-PC:{PORT})")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
