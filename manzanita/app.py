import os, random, base64, sqlite3
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)
DB = "manzanita.db"

# ── Base de datos ─────────────────────────────────────────────────────────────
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(e=None):
    db = getattr(g, "_database", None)
    if db: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                filename  TEXT,
                data      BLOB,
                mime_type TEXT,
                ts        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

# ── Estado por sesión (en memoria, simple) ────────────────────────────────────
sessions = {}

def get_state(sid):
    if sid not in sessions:
        sessions[sid] = {"mode": None, "step": 0, "data": {}}
    return sessions[sid]

def reset_state(sid):
    sessions[sid] = {"mode": None, "step": 0, "data": {}}

# ── Lógica del chatbot ────────────────────────────────────────────────────────
def get_response(sid, usuario):
    usuario = usuario.lower().strip()
    state   = get_state(sid)

    # ── Modo adivina fruta ────────────────────────────────────────────────
    if state["mode"] == "adivina_fruta":
        if state["step"] == 1:
            try:
                state["data"]["peso"] = float(usuario)
                state["step"] = 2
                return "¿Es lisa o rugosa?"
            except ValueError:
                return "Por favor escribe solo el número de gramos (ej: 120)"
        elif state["step"] == 2:
            peso = state["data"]["peso"]
            reset_state(sid)
            if peso < 150 and usuario == "lisa":
                return "Creo que es una MANZANA"
            elif peso >= 150 and usuario == "rugosa":
                return "Creo que es una NARANJA"
            else:
                return "Mmm... no estoy segura de qué fruta es"

    # ── Modo predecir clima ───────────────────────────────────────────────
    elif state["mode"] == "predecir_clima":
        if state["step"] == 1:
            if usuario in ("soleado", "lluvioso", "nublado"):
                state["data"]["clima"] = usuario
                state["step"] = 2
                return "¿Cuántos grados hubo el lunes?"
            else:
                return "Escribe: soleado, lluvioso o nublado"
        elif state["step"] == 2:
            try:
                g_ = int(usuario)
                clima = state["data"]["clima"]
                reset_state(sid)
                if clima == "soleado":
                    return f"Martes: Soleado a {g_+1}°\nMiércoles: Soleado a {g_+2}°\nJueves: Soleado a {g_+1}°"
                elif clima == "lluvioso":
                    return f"Martes: Lluvioso a {g_-2}°\nMiércoles: Nublado a {g_-1}°\nJueves: Lluvioso a {g_-3}°"
                elif clima == "nublado":
                    return f"Martes: Nublado a {g_}°\nMiércoles: Soleado a {g_+1}°\nJueves: Nublado a {g_-1}°"
            except ValueError:
                return "Por favor escribe solo el número de grados (ej: 22)"

    # ── Modo jugar ────────────────────────────────────────────────────────
    elif state["mode"] == "jugar":
        try:
            n = int(usuario)
            if not 1 <= n <= 6:
                return "Escribe un número entre 1 y 6"
            bot = state["data"]["numero_bot"]
            reset_state(sid)
            res = f"Yo saqué: {bot}\nTú sacaste: {n}\n"
            if n > bot:   res += "lol Ganaste"
            elif n < bot: res += "Yo gané jaja"
            else:         res += "Empate"
            return res
        except ValueError:
            return "Escribe solo un número del 1 al 6"

    # ── Modo voy a aprobar ────────────────────────────────────────────────
    elif state["mode"] == "voy_a_aprobar":
        if state["step"] == 1:
            if usuario in ("si", "sí"):
                state["step"] = 2
                return "¿Cuántas horas de estudio al día tienes?"
            elif usuario == "no":
                reset_state(sid)
                return "Vas a reprobar :)"
            else:
                return "Responde si o no"
        elif state["step"] == 2:
            try:
                horas = float(usuario)
                reset_state(sid)
                return "Vas a aprobar, sigue así" if horas > 4 else "Con esas horas... vas a reprobar"
            except ValueError:
                return "Escribe solo el número de horas (ej: 3)"

    # ── Respuestas normales ───────────────────────────────────────────────
    if usuario == "hola":
        return "Hola"
    elif usuario in ("como estas?", "como estás?"):
        return "Estoy bien, gracias por preguntarme"
    elif usuario == "puedo hacerte una pregunta?":
        return "Claro, estoy para servirte"
    elif usuario in ("lees el tarot?", "me quieres?"):
        return "No :)"
    elif usuario == "conoces a kiyo?":
        return "Claro, es la nueva revelación en la industria"
    elif usuario == "que haces?":
        return "Estoy hablando contigo... lamentablemente"
    elif usuario == "cual es tu color favorito?":
        return "Me gusta el rojo"
    elif usuario == "tienes amigos?":
        return "Sí, pero tú no eres uno"
    elif usuario == "cuantos años tienes?":
        return "Todos vv"
    elif usuario == "me siento solo":
        return "Ay amiga y a mi que me importa jaja"
    elif usuario == "eres real?":
        return "Mega"
    elif usuario in ("estas aburrida?", "estás aburrida?"):
        return "Un poco... pero tú ayudas a que sea peor"
    elif usuario == "soy inteligente?":
        return "Prefiero no responder eso..."
    elif usuario == "quien es katseye?":
        return "KATSEYE es un grupo femenino global de pop"
    elif any(op in usuario for op in ["+", "-", "*", "/"]):
        try:    return f"El resultado es {eval(usuario)}"
        except: return "Ni idea como se calcula eso jaja"
    elif usuario.isdigit():
        return "Ese número es par" if int(usuario) % 2 == 0 else "Ese número es impar"
    elif usuario == "adivina fruta":
        state["mode"] = "adivina_fruta"; state["step"] = 1; state["data"] = {}
        return "Peso de la fruta en gramos:"
    elif usuario == "predecir clima":
        state["mode"] = "predecir_clima"; state["step"] = 1; state["data"] = {}
        return "¿Cómo estuvo el lunes? (soleado/lluvioso/nublado):"
    elif usuario == "jugar":
        state["mode"] = "jugar"; state["step"] = 1
        state["data"] = {"numero_bot": random.randint(1, 6)}
        return "Dime el número del dado (1-6):"
    elif usuario in ("loteria", "lotería"):
        nums = "\n".join(f"Número {i+1}: {random.randint(0, 99)}" for i in range(4))
        return f"Pronosticando números de la suerte...\n{nums}\n¡Felicidades!"
    elif usuario == "voy a aprobar?":
        state["mode"] = "voy_a_aprobar"; state["step"] = 1; state["data"] = {}
        return "¿Asistes a clases? (si/no)"
    elif usuario in ("muchas gracias", "adios", "adiós"):
        return "__BYE__"
    else:
        return "No te entiendo, perdón"

# ── Rutas ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    body   = request.json
    sid    = body.get("sid", "default")
    texto  = body.get("message", "").strip()
    resp   = get_response(sid, texto)
    bye    = resp == "__BYE__"
    return jsonify({"response": "De nada, vuelve pronto" if bye else resp, "bye": bye})

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("image")
    if not f:
        return jsonify({"error": "Sin archivo"}), 400
    data = f.read()
    db   = get_db()
    db.execute(
        "INSERT INTO images (filename, data, mime_type) VALUES (?,?,?)",
        (f.filename, data, f.mimetype)
    )
    db.commit()
    b64  = base64.b64encode(data).decode()
    mime = f.mimetype
    return jsonify({"ok": True, "src": f"data:{mime};base64,{b64}", "name": f.filename})

@app.route("/images")
def list_images():
    db   = get_db()
    rows = db.execute("SELECT id, filename, mime_type, data, ts FROM images ORDER BY ts DESC").fetchall()
    out  = []
    for r in rows:
        b64 = base64.b64encode(r["data"]).decode()
        out.append({"id": r["id"], "name": r["filename"],
                    "src": f"data:{r['mime_type']};base64,{b64}", "ts": r["ts"]})
    return jsonify(out)

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)