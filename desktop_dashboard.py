import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Принтеры — локальный монитор</title>
<style>
:root{color-scheme:light;--ink:#19231f;--muted:#68756e;--line:#e0e8e2;--green:#157348;--red:#ba3434;--amber:#a56a00}
*{box-sizing:border-box}body{margin:0;background:#f3f6f3;color:var(--ink);font:15px/1.5 system-ui,"Segoe UI",sans-serif}
main{max-width:1080px;margin:38px auto;padding:0 22px}.head{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:22px}
h1{margin:0;font-size:29px}.muted{color:var(--muted)}.layout{display:grid;grid-template-columns:300px 1fr;gap:18px;align-items:start}
.box,.card{background:#fff;border:1px solid var(--line);border-radius:13px;padding:18px;box-shadow:0 5px 20px #18362108}
h2{font-size:17px;margin:0 0 14px}.field{display:grid;gap:5px;margin:11px 0}.field label{font-size:13px;color:var(--muted)}
input{width:100%;padding:10px;border:1px solid #ccd8cf;border-radius:8px;font:inherit}input[type=checkbox]{width:auto}
button{border:0;border-radius:8px;background:#176b47;color:#fff;padding:10px 13px;font:600 14px system-ui;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}.remove{background:#f8e9e9;color:#a32f2f;padding:7px 10px}
.cards{display:grid;gap:12px}.cardhead{display:flex;justify-content:space-between;gap:12px;align-items:start}.name{font-size:18px;font-weight:650}.ip{font:13px ui-monospace,monospace;color:var(--muted)}
.badge{display:inline-block;padding:4px 9px;margin:13px 0;border-radius:20px;background:#edf1ee;color:var(--muted);font-size:13px;font-weight:600}
.online{background:#e7f5ed;color:var(--green)}.offline,.error{color:var(--red)}.offline{background:#ffeded}.checking{background:#fff4df;color:var(--amber)}
.details{border-top:1px solid var(--line);padding-top:9px;color:#46534b}.details p{margin:5px 0}.empty,.notice{padding:20px;background:white;border-radius:12px;color:var(--muted)}
@media(max-width:760px){main{margin:24px auto}.layout{grid-template-columns:1fr}.head{align-items:start;flex-direction:column}}
</style></head><body><main>
<header class="head"><div><h1>Монитор принтеров</h1><div class="muted">Список устройств хранится в локальной базе SQLite</div></div>
<div><button id="check">Проверить сейчас</button> <span id="updated" class="muted">Загружаю…</span></div></header>
<div class="layout"><section class="box"><h2>Добавить принтер</h2><form id="add-form">
<div class="field"><label for="name">Имя</label><input id="name" name="name" required maxlength="100" placeholder="Например, принтер в офисе"></div>
<div class="field"><label for="ip">IP-адрес или имя узла</label><input id="ip" name="ip" required placeholder="192.168.1.100"></div>
<div class="field"><label for="port">TCP-порт печати</label><input id="port" name="port" type="number" value="9100" min="1" max="65535" required></div>
<div class="field"><label><input id="snmp" name="snmp" type="checkbox" checked> Проверять ошибки по SNMP</label></div>
<div class="field"><label for="snmp-port">SNMP-порт</label><input id="snmp-port" name="snmp_port" type="number" value="161" min="1" max="65535" required></div>
<button type="submit">Сохранить принтер</button><p id="form-message" class="muted"></p></form></section>
<section><div id="cards" class="cards"></div></section></div>
<p class="muted">Автопроверка каждые 30 секунд. Панель доступна только на этом компьютере.</p></main>
<script>
const cards=document.querySelector('#cards'),updated=document.querySelector('#updated'),formMessage=document.querySelector('#form-message');
function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}
function draw(data){cards.innerHTML=data.printers.length?data.printers.map(p=>{const badge=p.online===true?'online':p.online===false?'offline':'checking';const state=p.online===true?'В сети':p.online===false?'Недоступен':'Ожидание проверки';let details='';
if(!p.snmp_enabled)details='<p>Проверка ошибок по SNMP выключена.</p>';else if(p.snmp_error)details='<p class="error">SNMP: '+esc(p.snmp_error)+'</p>';else if(p.printer_status||p.errors?.length)details='<p>Состояние: '+esc(p.printer_status||'не определено')+'</p>'+(p.errors?.length?'<p class="error">Ошибки: '+p.errors.map(esc).join(', ')+'</p>':'<p>Ошибок не обнаружено</p>');else details='<p>Ожидаю данные SNMP…</p>';
return '<article class="card"><div class="cardhead"><div><div class="name">'+esc(p.name)+'</div><div class="ip">'+esc(p.ip)+':'+esc(p.port)+'</div></div><button class="remove" data-delete="'+p.id+'">Удалить</button></div><span class="badge '+badge+'">'+state+'</span><div class="details">'+details+(p.checked_at?'<p>Проверено: '+new Date(p.checked_at*1000).toLocaleTimeString()+'</p>':'')+'</div></article>'}).join(''):'<div class="empty">Пока нет принтеров. Добавьте первый через форму.</div>';updated.textContent='Обновлено '+new Date().toLocaleTimeString()}
async function refresh(){try{const r=await fetch('/api/printers',{cache:'no-store'});if(!r.ok)throw Error('Ошибка загрузки');draw(await r.json())}catch(e){cards.innerHTML='<div class="notice">Не удалось загрузить список принтеров.</div>'}}
document.querySelector('#check').addEventListener('click',async e=>{const b=e.currentTarget;b.disabled=true;b.textContent='Проверяю…';try{const r=await fetch('/api/check',{method:'POST'});draw(await r.json())}finally{b.disabled=false;b.textContent='Проверить сейчас'}});
document.querySelector('#add-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;const data=Object.fromEntries(new FormData(f));data.snmp=document.querySelector('#snmp').checked;try{const r=await fetch('/api/printers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await r.json();if(!r.ok)throw Error(result.error);f.reset();document.querySelector('#port').value=9100;document.querySelector('#snmp-port').value=161;document.querySelector('#snmp').checked=true;formMessage.textContent='Добавлено. Проверка начнётся в ближайшее время.';await refresh()}catch(err){formMessage.textContent=err.message}});
cards.addEventListener('click',async e=>{const id=e.target.dataset.delete;if(!id||!confirm('Удалить этот принтер из списка?'))return;const r=await fetch('/api/printers/'+id,{method:'DELETE'});if(r.ok)await refresh()});
refresh();setInterval(refresh,10000);
</script></body></html>"""


def start_desktop_dashboard(get_status, check_now, add_printer, delete_printer, host, port):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10000:
                raise ValueError("Слишком большой запрос")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self):
            if self.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/printers":
                self.send_json(200, get_status())
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/api/check":
                self.send_json(200, check_now())
                return
            if self.path != "/api/printers":
                self.send_error(404)
                return
            try:
                data = self.read_json()
                result = add_printer(
                    data.get("name", ""),
                    data.get("ip", ""),
                    data.get("port", 9100),
                    data.get("snmp", False),
                    data.get("snmp_port", 161),
                )
                self.send_json(201, {"printers": result})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})

        def do_DELETE(self):
            prefix = "/api/printers/"
            if not self.path.startswith(prefix):
                self.send_error(404)
                return
            try:
                printers = delete_printer(self.path[len(prefix):])
                self.send_json(200, {"printers": printers})
            except (ValueError, TypeError) as error:
                self.send_json(400, {"error": str(error)})

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server
