import streamlit as st
import sqlite3
import pandas as pd
import os
import json
import zipfile
import io
from datetime import date, datetime

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Sistema Contable",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Directorio de empresas ───────────────────────────────────────────────────
EMPRESAS_DIR = "empresas"
EMPRESAS_META = "empresas_meta.json"

os.makedirs(EMPRESAS_DIR, exist_ok=True)

def load_meta():
    if not os.path.exists(EMPRESAS_META):
        return {}
    with open(EMPRESAS_META, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(meta):
    with open(EMPRESAS_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def nombre_a_archivo(nombre):
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in nombre)
    return safe.strip().replace(" ", "_").lower()

def db_path(nombre):
    return os.path.join(EMPRESAS_DIR, nombre_a_archivo(nombre) + ".db")

# ── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp > header { background: transparent; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f36 0%, #242943 100%);
    }
    section[data-testid="stSidebar"] *:not(svg):not(path) {
        color: #e2e8f0 !important;
        border-color: rgba(255,255,255,0.15) !important;
    }
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [role="listbox"] {
        background: rgba(255,255,255,0.08) !important;
    }
    section[data-testid="stSidebar"] .stRadio label { color: #e2e8f0 !important; }

    .card {
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        margin-bottom: 1rem;
        border-left: 4px solid #4f46e5;
    }

    table { background: transparent !important; color: inherit !important; }
    tr:not([style*="background:#1a1f36"]):not([style*="background:#374151"]) { background: transparent !important; }
    td, th { background: transparent !important; color: inherit !important; }

    .alert-ok   { background:#d1fae5; border:1px solid #10b981; border-radius:8px; padding:0.8rem 1rem; color:#065f46; margin-bottom:0.8rem; }
    .alert-err  { background:#fee2e2; border:1px solid #ef4444; border-radius:8px; padding:0.8rem 1rem; color:#991b1b; margin-bottom:0.8rem; }
    .alert-warn { background:#fef3c7; border:1px solid #f59e0b; border-radius:8px; padding:0.8rem 1rem; color:#92400e; margin-bottom:0.8rem; }

    .stButton > button {
        background: #4f46e5;
        color: white !important;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s;
    }
    .stButton > button:hover { background: #4338ca; transform: translateY(-1px); }

    .asiento-badge {
        background: #4f46e5;
        color: white;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* ── Pantalla de bienvenida ── */
    .empresa-card {
        border: 2px solid rgba(79,70,229,0.3);
        border-radius: 14px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.8rem;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .empresa-card:hover { border-color: #4f46e5; box-shadow: 0 4px 12px rgba(79,70,229,0.2); }
    .empresa-nombre { font-size: 1.1rem; font-weight: 700; }
    .empresa-meta   { font-size: 0.82rem; opacity: 0.6; margin-top: 0.2rem; }
    .empresa-moneda { background: #4f46e5; color: white; border-radius: 20px; padding: 0.2rem 0.8rem; font-size: 0.78rem; font-weight: 700; }

    .welcome-header {
        text-align: center;
        padding: 3rem 0 2rem;
    }
    .welcome-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .welcome-sub {
        opacity: 0.5;
        margin-top: 0.5rem;
        font-size: 1rem;
    }

    .badge-empresa {
        background: linear-gradient(135deg,#4f46e5,#7c3aed);
        color: white;
        border-radius: 20px;
        padding: 0.25rem 0.9rem;
        font-size: 0.8rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# ── Monedas ───────────────────────────────────────────────────────────────────
MONEDAS = {
    "S/ - Sol peruano":       "S/",
    "$ - Dólar americano":    "$",
    "EUR - Euro":             "EUR",
    "GBP - Libra esterlina":  "GBP",
    "R$ - Real brasileño":    "R$",
    "CLP - Peso chileno":     "CLP",
    "COP - Peso colombiano":  "COP",
    "MXN - Peso mexicano":    "MXN",
}
MONEDAS_INV = {v: k for k, v in MONEDAS.items()}

# ── Session state inicial ─────────────────────────────────────────────────────
if "empresa_activa" not in st.session_state:
    st.session_state["empresa_activa"] = None
if "moneda" not in st.session_state:
    st.session_state["moneda"] = "S/"

# ═══════════════════════════════════════════════════════════════════════════════
# PANTALLA DE BIENVENIDA
# ═══════════════════════════════════════════════════════════════════════════════
def pantalla_bienvenida():
    meta = load_meta()

    st.markdown("""
    <div class="welcome-header">
        <div class="welcome-title">📒 Sistema Contable</div>
        <div class="welcome-sub">Selecciona una empresa o crea un nuevo registro</div>
    </div>
    """, unsafe_allow_html=True)

    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.markdown("### 📂 Registros existentes")

        if not meta:
            st.markdown('<div class="alert-warn">No hay registros creados aún. Crea uno nuevo desde el panel derecho.</div>', unsafe_allow_html=True)
        else:
            for nombre, datos in meta.items():
                moneda_sim = datos.get("moneda", "S/")
                created    = datos.get("created", "—")
                asientos   = datos.get("asientos", 0)

                col_btn, col_info = st.columns([3, 1])
                with col_btn:
                    st.markdown(f"""
                    <div class="empresa-card">
                        <div>
                            <div class="empresa-nombre">🏢 {nombre}</div>
                            <div class="empresa-meta">Creado: {created} &nbsp;·&nbsp; {asientos} asientos</div>
                        </div>
                        <span class="empresa-moneda">{moneda_sim}</span>
                    </div>
                    """, unsafe_allow_html=True)

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    if st.button(f"▶ Abrir", key=f"open_{nombre}"):
                        # Actualizar conteo de asientos
                        if os.path.exists(db_path(nombre)):
                            conn_tmp = sqlite3.connect(db_path(nombre))
                            try:
                                cnt = pd.read_sql_query("SELECT COUNT(*) as n FROM asientos", conn_tmp)["n"].iloc[0]
                                meta[nombre]["asientos"] = int(cnt)
                                save_meta(meta)
                            except:
                                pass
                            conn_tmp.close()
                        st.session_state["empresa_activa"] = nombre
                        st.session_state["moneda"] = datos.get("moneda", "S/")
                        st.rerun()
                with col_b:
                    if st.button(f"✏ Renombrar", key=f"ren_{nombre}"):
                        st.session_state[f"renaming_{nombre}"] = True
                        st.rerun()
                with col_c:
                    if st.button(f"📥 Exportar", key=f"exp_{nombre}"):
                        st.session_state[f"exporting_{nombre}"] = True
                        st.rerun()
                with col_d:
                    if st.button(f"🗑 Eliminar", key=f"del_{nombre}"):
                        st.session_state[f"confirm_del_{nombre}"] = True
                        st.rerun()

                # Renombrar inline
                if st.session_state.get(f"renaming_{nombre}"):
                    with st.form(key=f"form_ren_{nombre}"):
                        nuevo_nombre = st.text_input("Nuevo nombre", value=nombre)
                        col_ok, col_cancel = st.columns(2)
                        submitted = col_ok.form_submit_button("Guardar")
                        cancelled = col_cancel.form_submit_button("Cancelar")
                        if submitted and nuevo_nombre and nuevo_nombre != nombre:
                            if nuevo_nombre in meta:
                                st.error("Ya existe una empresa con ese nombre.")
                            else:
                                # Mover archivo DB
                                old_path = db_path(nombre)
                                new_path = db_path(nuevo_nombre)
                                if os.path.exists(old_path):
                                    os.rename(old_path, new_path)
                                meta[nuevo_nombre] = meta.pop(nombre)
                                save_meta(meta)
                                del st.session_state[f"renaming_{nombre}"]
                                st.success(f"Renombrado a '{nuevo_nombre}'.")
                                st.rerun()
                        if cancelled:
                            del st.session_state[f"renaming_{nombre}"]
                            st.rerun()

                # Confirmar eliminación
                if st.session_state.get(f"confirm_del_{nombre}"):
                    st.warning(f"¿Seguro que quieres eliminar **{nombre}**? Se borrarán todos sus datos.")
                    cola, colb = st.columns(2)
                    if cola.button("Sí, eliminar", key=f"confirm_yes_{nombre}"):
                        path = db_path(nombre)
                        if os.path.exists(path):
                            os.remove(path)
                        del meta[nombre]
                        save_meta(meta)
                        del st.session_state[f"confirm_del_{nombre}"]
                        st.success("Registro eliminado.")
                        st.rerun()
                    if colb.button("Cancelar", key=f"confirm_no_{nombre}"):
                        del st.session_state[f"confirm_del_{nombre}"]
                        st.rerun()

                # Exportar
                if st.session_state.get(f"exporting_{nombre}"):
                    path = db_path(nombre)
                    if os.path.exists(path):
                        conn_exp = sqlite3.connect(path)

                        # ── Datos base ────────────────────────────────────
                        df_asientos = pd.read_sql_query("SELECT * FROM asientos ORDER BY numero", conn_exp)
                        df_lineas   = pd.read_sql_query("SELECT * FROM lineas ORDER BY asiento_id, id", conn_exp)
                        df_cuentas  = pd.read_sql_query("SELECT * FROM cuentas ORDER BY codigo", conn_exp)

                        # ── Libro Diario ──────────────────────────────────
                        df_diario = pd.read_sql_query("""
                            SELECT a.numero AS 'N Asiento', a.fecha AS 'Fecha', a.glosa AS 'Glosa',
                                   c.codigo AS 'Codigo', c.nombre AS 'Cuenta', l.columna AS 'D/H', l.monto AS 'Monto'
                            FROM asientos a
                            JOIN lineas l ON l.asiento_id = a.id
                            JOIN cuentas c ON c.codigo = l.cuenta
                            ORDER BY a.numero, l.columna DESC
                        """, conn_exp)

                        # ── Libro Mayor ───────────────────────────────────
                        df_mayor = pd.read_sql_query("""
                            SELECT c.codigo AS 'Codigo', c.nombre AS 'Cuenta', c.tipo AS 'Tipo',
                                   a.numero AS 'N Asiento', a.fecha AS 'Fecha', a.glosa AS 'Glosa',
                                   l.columna AS 'D/H', l.monto AS 'Monto'
                            FROM lineas l
                            JOIN asientos a ON a.id = l.asiento_id
                            JOIN cuentas c ON c.codigo = l.cuenta
                            ORDER BY c.codigo, a.numero
                        """, conn_exp)

                        # ── Balance de Comprobación ───────────────────────
                        df_balance = pd.read_sql_query("""
                            SELECT c.codigo AS 'Codigo', c.nombre AS 'Cuenta', c.tipo AS 'Tipo',
                                   c.naturaleza AS 'Naturaleza',
                                   SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) AS 'Suma DEBE',
                                   SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) AS 'Suma HABER'
                            FROM cuentas c
                            JOIN lineas l ON l.cuenta = c.codigo
                            GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
                            ORDER BY c.codigo
                        """, conn_exp)
                        def _saldo_balance(row):
                            if row["Naturaleza"] == "DEUDORA":
                                s = row["Suma DEBE"] - row["Suma HABER"]
                                return (abs(s), 0) if s >= 0 else (0, abs(s))
                            else:
                                s = row["Suma HABER"] - row["Suma DEBE"]
                                return (0, abs(s)) if s >= 0 else (abs(s), 0)
                        if not df_balance.empty:
                            df_balance[["Saldo Deudor","Saldo Acreedor"]] = df_balance.apply(_saldo_balance, axis=1, result_type="expand")

                        # ── Estado de Resultados ──────────────────────────
                        df_er = pd.read_sql_query("""
                            SELECT c.codigo AS 'Codigo', c.nombre AS 'Cuenta', c.tipo AS 'Tipo',
                                   c.naturaleza AS 'Naturaleza',
                                   SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) AS 'Suma DEBE',
                                   SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) AS 'Suma HABER'
                            FROM cuentas c
                            JOIN lineas l ON l.cuenta = c.codigo
                            WHERE c.tipo IN ('INGRESO','GASTO')
                            GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
                            ORDER BY c.codigo
                        """, conn_exp)
                        if not df_er.empty:
                            df_er["Saldo"] = df_er.apply(
                                lambda r: r["Suma DEBE"] - r["Suma HABER"] if r["Naturaleza"] == "DEUDORA"
                                          else r["Suma HABER"] - r["Suma DEBE"], axis=1)

                        # ── Estado de Situación Financiera ────────────────
                        df_esf = pd.read_sql_query("""
                            SELECT c.codigo AS 'Codigo', c.nombre AS 'Cuenta', c.tipo AS 'Tipo',
                                   c.naturaleza AS 'Naturaleza',
                                   SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) AS 'Suma DEBE',
                                   SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) AS 'Suma HABER'
                            FROM cuentas c
                            JOIN lineas l ON l.cuenta = c.codigo
                            WHERE c.tipo IN ('ACTIVO','PASIVO','PATRIMONIO')
                            GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
                            ORDER BY c.codigo
                        """, conn_exp)
                        if not df_esf.empty:
                            df_esf["Saldo"] = df_esf.apply(
                                lambda r: r["Suma DEBE"] - r["Suma HABER"] if r["Naturaleza"] == "DEUDORA"
                                          else r["Suma HABER"] - r["Suma DEBE"], axis=1)

                        conn_exp.close()

                        # ── Generar archivo ───────────────────────────────
                        try:
                            import openpyxl  # noqa
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                                df_asientos.to_excel(writer, sheet_name="Asientos",             index=False)
                                df_lineas.to_excel(  writer, sheet_name="Lineas",               index=False)
                                df_cuentas.to_excel( writer, sheet_name="Plan de Cuentas",      index=False)
                                df_diario.to_excel(  writer, sheet_name="Libro Diario",         index=False)
                                df_mayor.to_excel(   writer, sheet_name="Libro Mayor",          index=False)
                                df_balance.to_excel( writer, sheet_name="Bal. Comprobacion",    index=False)
                                df_er.to_excel(      writer, sheet_name="Estado Resultados",    index=False)
                                df_esf.to_excel(     writer, sheet_name="Situacion Financiera", index=False)
                            output.seek(0)
                            st.download_button(
                                label=f"⬇ Descargar {nombre}.xlsx",
                                data=output,
                                file_name=f"{nombre_a_archivo(nombre)}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"dl_{nombre}"
                            )
                        except ImportError:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                                zf.writestr("asientos.csv",            df_asientos.to_csv(index=False))
                                zf.writestr("lineas.csv",              df_lineas.to_csv(index=False))
                                zf.writestr("plan_de_cuentas.csv",     df_cuentas.to_csv(index=False))
                                zf.writestr("libro_diario.csv",        df_diario.to_csv(index=False))
                                zf.writestr("libro_mayor.csv",         df_mayor.to_csv(index=False))
                                zf.writestr("bal_comprobacion.csv",    df_balance.to_csv(index=False))
                                zf.writestr("estado_resultados.csv",   df_er.to_csv(index=False))
                                zf.writestr("situacion_financiera.csv",df_esf.to_csv(index=False))
                            zip_buffer.seek(0)
                            st.warning("⚠️ openpyxl no instalado. Se exporta como ZIP de CSVs. Instálalo con: `pip install openpyxl`")
                            st.download_button(
                                label=f"⬇ Descargar {nombre}.zip (CSV)",
                                data=zip_buffer,
                                file_name=f"{nombre_a_archivo(nombre)}.zip",
                                mime="application/zip",
                                key=f"dl_{nombre}"
                            )
                    if f"exporting_{nombre}" in st.session_state:
                        del st.session_state[f"exporting_{nombre}"]

                st.markdown("---")

    with col_side:
        st.markdown("### ➕ Nuevo registro")
        with st.form("form_nueva_empresa"):
            nuevo_nombre = st.text_input("Nombre de la empresa", placeholder="Ej: Empresa ABC")
            sel_moneda   = st.selectbox("Moneda predeterminada", list(MONEDAS.keys()))
            crear        = st.form_submit_button("Crear registro")

            if crear:
                nombre_clean = nuevo_nombre.strip()
                if not nombre_clean:
                    st.error("Ingresa un nombre.")
                elif nombre_clean in meta:
                    st.error("Ya existe un registro con ese nombre.")
                else:
                    moneda_sim = MONEDAS[sel_moneda]
                    meta[nombre_clean] = {
                        "moneda":  moneda_sim,
                        "created": date.today().strftime("%Y-%m-%d"),
                        "asientos": 0,
                    }
                    save_meta(meta)
                    # Inicializar DB
                    init_db(db_path(nombre_clean))
                    st.session_state["empresa_activa"] = nombre_clean
                    st.session_state["moneda"] = moneda_sim
                    st.success(f"Registro '{nombre_clean}' creado.")
                    st.rerun()

# ── Base de datos (por empresa) ───────────────────────────────────────────────
def get_conn(path=None):
    if path is None:
        empresa = st.session_state.get("empresa_activa")
        path = db_path(empresa)
    return sqlite3.connect(path, check_same_thread=False)

def init_db(path=None):
    conn = get_conn(path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS cuentas (
        codigo TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        tipo   TEXT NOT NULL,
        naturaleza TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS asientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero INTEGER NOT NULL,
        fecha  TEXT NOT NULL,
        glosa  TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lineas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        asiento_id INTEGER NOT NULL,
        cuenta     TEXT NOT NULL,
        monto      REAL NOT NULL,
        columna    TEXT NOT NULL,
        FOREIGN KEY(asiento_id) REFERENCES asientos(id)
    )""")
    cuentas_base = [
        ("10","Caja y Bancos (Efectivo)","ACTIVO","DEUDORA"),
        ("12","Cuentas por Cobrar Comerciales","ACTIVO","DEUDORA"),
        ("16","Cuentas por Cobrar Diversas","ACTIVO","DEUDORA"),
        ("20","Mercaderias (Inventarios)","ACTIVO","DEUDORA"),
        ("25","Materiales Auxiliares","ACTIVO","DEUDORA"),
        ("33","Inmuebles Maquinaria y Equipo","ACTIVO","DEUDORA"),
        ("34","Intangibles","ACTIVO","DEUDORA"),
        ("36","Desvalorizacion de Activos","ACTIVO","DEUDORA"),
        ("37","Activo Diferido","ACTIVO","DEUDORA"),
        ("39","Depreciacion Acumulada","ACTIVO","ACREEDORA"),
        ("40","Tributos por Pagar","PASIVO","ACREEDORA"),
        ("41","Remuneraciones y Participaciones por Pagar","PASIVO","ACREEDORA"),
        ("42","Cuentas por Pagar Comerciales","PASIVO","ACREEDORA"),
        ("45","Obligaciones Financieras","PASIVO","ACREEDORA"),
        ("46","Cuentas por Pagar Diversas","PASIVO","ACREEDORA"),
        ("50","Capital Social","PATRIMONIO","ACREEDORA"),
        ("57","Excedente de Revaluacion","PATRIMONIO","ACREEDORA"),
        ("58","Reservas","PATRIMONIO","ACREEDORA"),
        ("59","Resultados Acumulados","PATRIMONIO","ACREEDORA"),
        ("60","Compras","GASTO","DEUDORA"),
        ("61","Variacion de Inventarios","GASTO","DEUDORA"),
        ("62","Gastos de Personal","GASTO","DEUDORA"),
        ("63","Gastos de Servicios","GASTO","DEUDORA"),
        ("65","Otros Gastos de Gestion","GASTO","DEUDORA"),
        ("66","Perdida por Medicion de Activos","GASTO","DEUDORA"),
        ("67","Gastos Financieros","GASTO","DEUDORA"),
        ("68","Valuacion y Deterioro de Activos","GASTO","DEUDORA"),
        ("69","Costo de Ventas","GASTO","DEUDORA"),
        ("70","Ventas","INGRESO","ACREEDORA"),
        ("74","Descuentos Concedidos","INGRESO","DEUDORA"),
        ("75","Otros Ingresos de Gestion","INGRESO","ACREEDORA"),
        ("77","Ingresos Financieros","INGRESO","ACREEDORA"),
    ]
    c.executemany("INSERT OR IGNORE INTO cuentas VALUES (?,?,?,?)", cuentas_base)
    conn.commit()
    conn.close()

# ── Helpers ───────────────────────────────────────────────────────────────────
def query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def execute(sql, params=()):
    conn = get_conn()
    c = conn.cursor()
    c.execute(sql, params)
    last = c.lastrowid
    conn.commit()
    conn.close()
    return last

def executemany(sql, data):
    conn = get_conn()
    c = conn.cursor()
    c.executemany(sql, data)
    conn.commit()
    conn.close()

def m(val, sim="S/"):
    if pd.isna(val):
        return "-"
    return f"{sim} {val:,.2f}"

def proximo_numero():
    df = query("SELECT MAX(numero) as n FROM asientos")
    n = df["n"].iloc[0]
    return 1 if pd.isna(n) else int(n) + 1

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["empresa_activa"] is None:
    pantalla_bienvenida()
    st.stop()

# Verificar que la empresa sigue existiendo
meta_check = load_meta()
if st.session_state["empresa_activa"] not in meta_check:
    st.session_state["empresa_activa"] = None
    st.rerun()

# Asegurar que la DB existe e inicializarla si es necesario
empresa_actual = st.session_state["empresa_activa"]
path_actual = db_path(empresa_actual)
if not os.path.exists(path_actual):
    init_db(path_actual)

SIM = st.session_state["moneda"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Sistema Contable")
    st.markdown(f"<div style='margin-bottom:0.5rem'><span class='badge-empresa'>🏢 {empresa_actual}</span></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
    <style>
    /* Ocultar label título del radio */
    section[data-testid="stSidebar"] .stRadio > label {
        display: none !important;
    }
    /* Contenedor principal — ancho completo */
    section[data-testid="stSidebar"] .stRadio,
    section[data-testid="stSidebar"] .stRadio > div {
        width: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        gap: 2px !important;
    }
    /* Cada barra — ancho completo */
    section[data-testid="stSidebar"] .stRadio > div > label {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        box-sizing: border-box !important;
        background: transparent !important;
        border-radius: 8px !important;
        padding: 0.6rem 1rem !important;
        cursor: pointer !important;
        transition: background 0.18s ease !important;
        border: none !important;
        color: #94a3b8 !important;
        font-size: 0.875rem !important;
        font-weight: 400 !important;
        margin: 0 !important;
    }
    /* Hover — sombra/resaltado */
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.08) !important;
        color: #e2e8f0 !important;
    }
    /* Activa — barra resaltada */
    section[data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
        background: rgba(99, 102, 241, 0.25) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-left: 3px solid #6366f1 !important;
        padding-left: calc(1rem - 3px) !important;
    }
    /* Ocultar el círculo */
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
        display: none !important;
    }
    /* El texto ocupa todo el espacio */
    section[data-testid="stSidebar"] .stRadio > div > label > div:last-child {
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)
    pagina = st.radio("Navegación", [
        "Registro de Asientos",
        "Editar / Eliminar Asientos",
        "Libro Diario",
        "Libro Mayor",
        "Balance de Comprobación",
        "Estado de Resultados",
        "Estado de Situación Financiera",
        "Plan de Cuentas",
        "🤖 Asistente IA",
    ])
    st.markdown("---")

    # Selector de moneda
    moneda_key = MONEDAS_INV.get(SIM, list(MONEDAS.keys())[0])
    sel_moneda = st.selectbox("Moneda", list(MONEDAS.keys()),
                               index=list(MONEDAS.keys()).index(moneda_key))
    nueva_sim = MONEDAS[sel_moneda]
    if nueva_sim != SIM:
        st.session_state["moneda"] = nueva_sim
        # Actualizar moneda en meta
        meta_check[empresa_actual]["moneda"] = nueva_sim
        save_meta(meta_check)
        SIM = nueva_sim
        st.rerun()

    st.markdown("---")
    total_asientos = query("SELECT COUNT(*) as n FROM asientos")["n"].iloc[0]
    st.markdown(f"**Asientos:** {total_asientos}")
    st.markdown("---")
    if st.button("🏠 Cambiar empresa"):
        st.session_state["empresa_activa"] = None
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE ASIENTOS
# ═══════════════════════════════════════════════════════════════════════════════
if pagina == "Registro de Asientos":
    st.title("Registro de Asientos Contables")

    if "lineas_asiento" not in st.session_state:
        st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]

    st.markdown("### Cabecera del Asiento")
    col1, col2, col3 = st.columns([1,2,4])
    with col1:
        num = proximo_numero()
        st.markdown(f"**N° Asiento:** <span class='asiento-badge'>{num:03d}</span>", unsafe_allow_html=True)
    with col2:
        fecha = st.date_input("Fecha", value=date.today())
    with col3:
        glosa = st.text_input("Glosa / Descripción (opcional)", placeholder="Ej: Compra de mercadería al contado")

    st.markdown("### Líneas del Asiento")
    cuentas_df = query("SELECT codigo, nombre, tipo FROM cuentas ORDER BY codigo")
    cuentas_opciones = {f"{r.codigo} - {r.nombre}": r.codigo for _, r in cuentas_df.iterrows()}
    cuentas_lista = list(cuentas_opciones.keys())

    h1, h2, h3, h4 = st.columns([3,2,2,1])
    h1.markdown("**Cuenta Contable**")
    h2.markdown(f"**Monto ({SIM})**")
    h3.markdown("**Debe / Haber**")
    h4.markdown("")

    to_delete = None
    for i, linea in enumerate(st.session_state.lineas_asiento):
        c1, c2, c3, c4 = st.columns([3,2,2,1])
        with c1:
            idx = 0
            if linea["cuenta"]:
                match = [j for j, k in enumerate(cuentas_lista) if k.startswith(linea["cuenta"])]
                if match:
                    idx = match[0]
            sel = st.selectbox("", cuentas_lista, index=idx, key=f"cta_{i}", label_visibility="collapsed")
            linea["cuenta"] = cuentas_opciones[sel]
        with c2:
            placeholder_key = f"monto_focus_{i}"
            if placeholder_key not in st.session_state:
                st.session_state[placeholder_key] = False
            monto = st.number_input("", min_value=0.0,
                value=None if st.session_state[placeholder_key] else float(linea["monto"]),
                step=0.01, format="%.2f", key=f"monto_{i}",
                label_visibility="collapsed", placeholder="0.00")
            linea["monto"] = monto if monto is not None else 0.0
        with c3:
            col_idx = 0 if linea["columna"] == "DEBE" else 1
            columna = st.selectbox("", ["DEBE","HABER"], index=col_idx, key=f"col_{i}", label_visibility="collapsed")
            linea["columna"] = columna
        with c4:
            if st.button("✕", key=f"del_{i}") and len(st.session_state.lineas_asiento) > 1:
                to_delete = i

    if to_delete is not None:
        st.session_state.lineas_asiento.pop(to_delete)
        st.rerun()

    if st.button("+ Agregar línea"):
        st.session_state.lineas_asiento.append({"cuenta":"","monto":0.0,"columna":"DEBE"})
        st.rerun()

    total_debe  = sum(l["monto"] for l in st.session_state.lineas_asiento if l["columna"] == "DEBE")
    total_haber = sum(l["monto"] for l in st.session_state.lineas_asiento if l["columna"] == "HABER")
    diff = round(total_debe - total_haber, 2)

    st.markdown("---")
    t1, t2, t3 = st.columns(3)
    t1.metric("Total DEBE",  m(total_debe,  SIM))
    t2.metric("Total HABER", m(total_haber, SIM))
    t3.metric("Diferencia",  m(diff,        SIM))

    if diff == 0 and total_debe > 0:
        st.markdown('<div class="alert-ok">✅ El asiento está cuadrado (Debe = Haber)</div>', unsafe_allow_html=True)
    elif total_debe > 0 or total_haber > 0:
        st.markdown(f'<div class="alert-err">⚠️ El asiento no cuadra. Diferencia: {m(abs(diff), SIM)}</div>', unsafe_allow_html=True)

    col_btn1, col_btn2 = st.columns([1,5])
    with col_btn1:
        if st.button("Guardar Asiento"):
            errores = []
            if total_debe == 0 and total_haber == 0:
                errores.append("El asiento no tiene montos.")
            if diff != 0:
                errores.append(f"El asiento no cuadra (diferencia {m(abs(diff), SIM)}).")
            lineas_con_monto = [l for l in st.session_state.lineas_asiento if l["monto"] > 0]
            if not lineas_con_monto:
                errores.append("Todas las líneas tienen monto 0.")
            if errores:
                for e in errores:
                    st.error(e)
            else:
                asiento_id = execute(
                    "INSERT INTO asientos (numero, fecha, glosa) VALUES (?,?,?)",
                    (num, fecha.strftime("%Y-%m-%d"), glosa.strip())
                )
                data_lineas = [(asiento_id, l["cuenta"], l["monto"], l["columna"]) for l in lineas_con_monto]
                executemany("INSERT INTO lineas (asiento_id, cuenta, monto, columna) VALUES (?,?,?,?)", data_lineas)
                st.success(f"✅ Asiento N° {num:03d} guardado correctamente.")
                st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]
                st.rerun()
    with col_btn2:
        if st.button("Limpiar formulario"):
            st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]
            st.rerun()

    st.markdown("---")
    st.markdown("### Últimos asientos registrados")
    ultimos = query("""
        SELECT a.numero as 'N°', a.fecha as 'Fecha', a.glosa as 'Glosa',
               c.nombre as 'Cuenta', l.columna as 'D/H', l.monto as 'Monto'
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        JOIN cuentas c ON c.codigo = l.cuenta
        ORDER BY a.numero DESC, l.columna
        LIMIT 30
    """)
    if not ultimos.empty:
        ultimos["Monto"] = ultimos["Monto"].apply(lambda x: m(x, SIM))
        st.dataframe(ultimos, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# EDITAR / ELIMINAR ASIENTOS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Editar / Eliminar Asientos":
    st.title("Editar / Eliminar Asientos")

    todos = query("""
        SELECT a.id, a.numero, a.fecha, a.glosa,
               SUM(CASE WHEN l.columna='DEBE' THEN l.monto ELSE 0 END) as total
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        GROUP BY a.id
        ORDER BY a.numero DESC
    """)

    if todos.empty:
        st.info("No hay asientos registrados.")
    else:
        opciones = {
            f"N°{row['numero']:03d} | {row['fecha']} | {row['glosa'] or '(sin glosa)'} | {m(row['total'], SIM)}": row['id']
            for _, row in todos.iterrows()
        }
        seleccion  = st.selectbox("Selecciona el asiento:", list(opciones.keys()))
        asiento_id = opciones[seleccion]

        cabecera   = query("SELECT * FROM asientos WHERE id=?", (asiento_id,)).iloc[0]
        lineas_act = query("SELECT * FROM lineas WHERE asiento_id=? ORDER BY id", (asiento_id,))

        st.markdown("---")
        st.markdown("### Editar cabecera")
        col1, col2 = st.columns([2,4])
        with col1:
            nueva_fecha = st.date_input("Fecha", value=datetime.strptime(cabecera["fecha"], "%Y-%m-%d").date(), key="edit_fecha")
        with col2:
            nueva_glosa = st.text_input("Glosa", value=cabecera["glosa"] or "", key="edit_glosa")

        st.markdown("### Editar líneas")
        cuentas_df = query("SELECT codigo, nombre FROM cuentas ORDER BY codigo")
        cuentas_opciones = {f"{r.codigo} - {r.nombre}": r.codigo for _, r in cuentas_df.iterrows()}
        cuentas_lista = list(cuentas_opciones.keys())

        key_lineas = f"edit_lineas_{asiento_id}"
        if key_lineas not in st.session_state:
            st.session_state[key_lineas] = [
                {"cuenta": row["cuenta"], "monto": row["monto"], "columna": row["columna"]}
                for _, row in lineas_act.iterrows()
            ]

        h1, h2, h3, h4 = st.columns([3,2,2,1])
        h1.markdown("**Cuenta**"); h2.markdown(f"**Monto ({SIM})**"); h3.markdown("**D/H**"); h4.markdown("")

        to_delete_edit = None
        for i, linea in enumerate(st.session_state[key_lineas]):
            c1, c2, c3, c4 = st.columns([3,2,2,1])
            with c1:
                idx = next((j for j, k in enumerate(cuentas_lista) if k.startswith(linea["cuenta"])), 0)
                sel = st.selectbox("", cuentas_lista, index=idx, key=f"ecta_{asiento_id}_{i}", label_visibility="collapsed")
                linea["cuenta"] = cuentas_opciones[sel]
            with c2:
                linea["monto"] = st.number_input("", min_value=0.0,
                    value=float(linea["monto"]) if linea["monto"] > 0 else None,
                    step=0.01, format="%.2f", key=f"emonto_{asiento_id}_{i}",
                    label_visibility="collapsed", placeholder="0.00")
                linea["monto"] = linea["monto"] if linea["monto"] is not None else 0.0
            with c3:
                col_idx = 0 if linea["columna"] == "DEBE" else 1
                linea["columna"] = st.selectbox("", ["DEBE","HABER"], index=col_idx, key=f"ecol_{asiento_id}_{i}", label_visibility="collapsed")
            with c4:
                if st.button("✕", key=f"edel_{asiento_id}_{i}") and len(st.session_state[key_lineas]) > 1:
                    to_delete_edit = i

        if to_delete_edit is not None:
            st.session_state[key_lineas].pop(to_delete_edit)
            st.rerun()

        if st.button("+ Agregar línea", key="edit_add"):
            st.session_state[key_lineas].append({"cuenta": "10", "monto": 0.0, "columna": "DEBE"})
            st.rerun()

        td = sum(l["monto"] for l in st.session_state[key_lineas] if l["columna"]=="DEBE")
        th = sum(l["monto"] for l in st.session_state[key_lineas] if l["columna"]=="HABER")
        t1, t2, t3 = st.columns(3)
        t1.metric("Total DEBE",  m(td, SIM))
        t2.metric("Total HABER", m(th, SIM))
        t3.metric("Diferencia",  m(round(td-th,2), SIM))

        if round(td-th, 2) == 0 and td > 0:
            st.markdown('<div class="alert-ok">✅ El asiento cuadra</div>', unsafe_allow_html=True)
        elif td > 0 or th > 0:
            st.markdown('<div class="alert-err">⚠️ No cuadra</div>', unsafe_allow_html=True)

        col_g, col_e, col_c = st.columns([2,2,4])
        with col_g:
            if st.button("Guardar cambios"):
                if round(td-th, 2) != 0:
                    st.error("El asiento no cuadra. Corrige antes de guardar.")
                else:
                    execute("UPDATE asientos SET fecha=?, glosa=? WHERE id=?",
                            (nueva_fecha.strftime("%Y-%m-%d"), nueva_glosa.strip(), asiento_id))
                    execute("DELETE FROM lineas WHERE asiento_id=?", (asiento_id,))
                    data_lineas = [(asiento_id, l["cuenta"], l["monto"], l["columna"])
                                   for l in st.session_state[key_lineas] if l["monto"] > 0]
                    executemany("INSERT INTO lineas (asiento_id, cuenta, monto, columna) VALUES (?,?,?,?)", data_lineas)
                    del st.session_state[key_lineas]
                    st.success("✅ Asiento actualizado correctamente.")
                    st.rerun()
        with col_e:
            if st.button("🗑 Eliminar asiento"):
                execute("DELETE FROM lineas WHERE asiento_id=?", (asiento_id,))
                execute("DELETE FROM asientos WHERE id=?", (asiento_id,))
                if key_lineas in st.session_state:
                    del st.session_state[key_lineas]
                st.success("Asiento eliminado.")
                st.rerun()
        with col_c:
            if st.button("Descartar cambios"):
                if key_lineas in st.session_state:
                    del st.session_state[key_lineas]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# LIBRO DIARIO
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Libro Diario":
    st.title("Libro Diario")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    df = query("""
        SELECT a.numero, a.fecha, a.glosa, c.codigo, c.nombre, l.columna, l.monto
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        JOIN cuentas c ON c.codigo = l.cuenta
        WHERE a.fecha BETWEEN ? AND ?
        ORDER BY a.numero, l.columna DESC, l.id
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if df.empty:
        st.info("No hay asientos en el periodo seleccionado.")
    else:
        for num_asiento in df["numero"].unique():
            grupo   = df[df["numero"] == num_asiento]
            fecha_a = grupo["fecha"].iloc[0]
            glosa_a = grupo["glosa"].iloc[0] or ""

            rows_html = ""
            tot_debe = tot_haber = 0
            for _, row in grupo.iterrows():
                d = m(row['monto'], SIM) if row["columna"] == "DEBE"  else ""
                h = m(row['monto'], SIM) if row["columna"] == "HABER" else ""
                indent = "" if row["columna"] == "DEBE" else "padding-left:2rem;"
                if row["columna"] == "DEBE":  tot_debe  += row["monto"]
                else:                          tot_haber += row["monto"]
                rows_html += f"""
                <tr>
                    <td style="{indent}padding:0.3rem 0.8rem">{row['codigo']} - {row['nombre']}</td>
                    <td style="text-align:right; padding:0.3rem 0.8rem; color:#2563eb; font-weight:500">{d}</td>
                    <td style="text-align:right; padding:0.3rem 0.8rem; color:#7c3aed; font-weight:500">{h}</td>
                </tr>"""

            st.markdown(f"""
            <div class="card">
            <div style="margin-bottom:0.5rem">
                <b>Asiento N° {num_asiento:03d}</b> &nbsp;&nbsp; {fecha_a} &nbsp;&nbsp;
                <span style="opacity:0.6">{glosa_a}</span>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
                <thead>
                    <tr style="background:rgba(128,128,128,0.15)">
                        <th style="text-align:left; padding:0.4rem 0.8rem">Cuenta</th>
                        <th style="text-align:right; padding:0.4rem 0.8rem; width:160px">DEBE</th>
                        <th style="text-align:right; padding:0.4rem 0.8rem; width:160px">HABER</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
                <tfoot>
                    <tr style="background:#1a1f36; font-weight:700">
                        <td style="padding:0.4rem 0.8rem; color:white">TOTAL</td>
                        <td style="text-align:right; padding:0.4rem 0.8rem; color:white">{m(tot_debe, SIM)}</td>
                        <td style="text-align:right; padding:0.4rem 0.8rem; color:white">{m(tot_haber, SIM)}</td>
                    </tr>
                </tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# LIBRO MAYOR
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Libro Mayor":
    st.title("Libro Mayor")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    cuentas_mov = query("""
        SELECT DISTINCT l.cuenta, c.nombre, c.tipo, c.naturaleza
        FROM lineas l
        JOIN asientos a ON a.id = l.asiento_id
        JOIN cuentas c ON c.codigo = l.cuenta
        WHERE a.fecha BETWEEN ? AND ?
        ORDER BY l.cuenta
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if cuentas_mov.empty:
        st.info("No hay movimientos en el periodo seleccionado.")
    else:
        for _, cuenta_row in cuentas_mov.iterrows():
            codigo = cuenta_row["cuenta"]
            nombre = cuenta_row["nombre"]
            tipo   = cuenta_row["tipo"]
            natura = cuenta_row["naturaleza"]

            movs = query("""
                SELECT a.fecha, a.numero, a.glosa, l.columna, l.monto
                FROM lineas l
                JOIN asientos a ON a.id = l.asiento_id
                WHERE l.cuenta = ? AND a.fecha BETWEEN ? AND ?
                ORDER BY a.numero
            """, (codigo, fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

            tot_debe  = movs[movs["columna"]=="DEBE"]["monto"].sum()
            tot_haber = movs[movs["columna"]=="HABER"]["monto"].sum()
            if natura == "DEUDORA":
                saldo = tot_debe - tot_haber
                saldo_label = "DEUDOR" if saldo >= 0 else "ACREEDOR"
            else:
                saldo = tot_haber - tot_debe
                saldo_label = "ACREEDOR" if saldo >= 0 else "DEUDOR"
            saldo = abs(saldo)

            COLORES = {"ACTIVO":"#3b82f6","PASIVO":"#ef4444","PATRIMONIO":"#8b5cf6","INGRESO":"#10b981","GASTO":"#f59e0b"}
            color_tipo = COLORES.get(tipo, "#6b7280")

            rows_html = ""
            saldo_acum = 0
            for _, mv in movs.iterrows():
                d = m(mv['monto'], SIM) if mv["columna"]=="DEBE"  else ""
                h = m(mv['monto'], SIM) if mv["columna"]=="HABER" else ""
                if natura=="DEUDORA":
                    saldo_acum += mv["monto"] if mv["columna"]=="DEBE" else -mv["monto"]
                else:
                    saldo_acum += mv["monto"] if mv["columna"]=="HABER" else -mv["monto"]
                rows_html += f"""
                <tr style="border-bottom:1px solid rgba(128,128,128,0.15)">
                    <td style="padding:0.3rem 0.6rem">{mv['fecha']}</td>
                    <td style="padding:0.3rem 0.6rem">N°{mv['numero']:03d}</td>
                    <td style="padding:0.3rem 0.6rem; opacity:0.7">{mv['glosa'] or ''}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; color:#2563eb">{d}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; color:#7c3aed">{h}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; font-weight:600">{m(abs(saldo_acum), SIM)}</td>
                </tr>"""

            st.markdown(f"""
            <div class="card" style="border-left-color:{color_tipo}">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem">
                <div>
                    <span style="font-size:1.1rem; font-weight:700">{codigo} - {nombre}</span>
                    <span style="background:{color_tipo}; color:white; border-radius:20px; padding:0.15rem 0.7rem;
                          font-size:0.75rem; font-weight:600; margin-left:0.5rem">{tipo}</span>
                </div>
                <div style="text-align:right">
                    <div style="font-size:0.75rem; opacity:0.6">{saldo_label}</div>
                    <div style="font-size:1.2rem; font-weight:700; color:{color_tipo}">{m(saldo, SIM)}</div>
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                    <tr style="background:rgba(128,128,128,0.15)">
                        <th style="text-align:left; padding:0.4rem 0.6rem">Fecha</th>
                        <th style="text-align:left; padding:0.4rem 0.6rem">Asiento</th>
                        <th style="text-align:left; padding:0.4rem 0.6rem">Glosa</th>
                        <th style="text-align:right; padding:0.4rem 0.6rem">DEBE</th>
                        <th style="text-align:right; padding:0.4rem 0.6rem">HABER</th>
                        <th style="text-align:right; padding:0.4rem 0.6rem">Saldo</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
                <tfoot>
                    <tr style="background:#1a1f36; font-weight:700">
                        <td colspan="3" style="padding:0.4rem 0.6rem">TOTALES</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem; color:white">{m(tot_debe,  SIM)}</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem; color:white">{m(tot_haber, SIM)}</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem; color:white">{m(saldo,     SIM)}</td>
                    </tr>
                </tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# BALANCE DE COMPROBACION
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Balance de Comprobación":
    st.title("Balance de Comprobación")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    df = query("""
        SELECT c.codigo, c.nombre, c.tipo, c.naturaleza,
               SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) as suma_debe,
               SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) as suma_haber
        FROM cuentas c
        JOIN lineas l ON l.cuenta = c.codigo
        JOIN asientos a ON a.id = l.asiento_id
        WHERE a.fecha BETWEEN ? AND ?
        GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
        ORDER BY c.codigo
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if df.empty:
        st.info("No hay movimientos en el periodo.")
    else:
        def calc_saldo(row):
            if row["naturaleza"] == "DEUDORA":
                s = row["suma_debe"] - row["suma_haber"]
                return (abs(s), 0) if s >= 0 else (0, abs(s))
            else:
                s = row["suma_haber"] - row["suma_debe"]
                return (0, abs(s)) if s >= 0 else (abs(s), 0)

        df[["saldo_deudor","saldo_acreedor"]] = df.apply(calc_saldo, axis=1, result_type="expand")

        tot_sd      = df["suma_debe"].sum()
        tot_sh      = df["suma_haber"].sum()
        tot_saldo_d = df["saldo_deudor"].sum()
        tot_saldo_a = df["saldo_acreedor"].sum()
        cuadra      = round(tot_sd - tot_sh, 2) == 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total DEBE",        m(tot_sd,      SIM))
        m2.metric("Total HABER",       m(tot_sh,      SIM))
        m3.metric("Saldos Deudores",   m(tot_saldo_d, SIM))
        m4.metric("Saldos Acreedores", m(tot_saldo_a, SIM))

        if cuadra:
            st.markdown('<div class="alert-ok">✅ El balance cuadra correctamente</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-err">⚠️ El balance no cuadra</div>', unsafe_allow_html=True)

        st.markdown("---")

        COLORES = {"ACTIVO":"#3b82f6","PASIVO":"#ef4444","PATRIMONIO":"#8b5cf6","INGRESO":"#10b981","GASTO":"#f59e0b"}
        rows_html = ""
        for _, row in df.iterrows():
            color = COLORES.get(row["tipo"], "#6b7280")
            sd = m(row['saldo_deudor'],  SIM) if row['saldo_deudor']  > 0 else "-"
            sa = m(row['saldo_acreedor'],SIM) if row['saldo_acreedor'] > 0 else "-"
            rows_html += f"""
            <tr style="border-bottom:1px solid rgba(128,128,128,0.2)">
                <td style="padding:0.4rem 0.8rem; font-weight:600">{row['codigo']}</td>
                <td style="padding:0.4rem 0.8rem">{row['nombre']}</td>
                <td style="padding:0.4rem 0.8rem; text-align:center">
                    <span style="background:{color}; color:white; border-radius:4px;
                          padding:0.1rem 0.5rem; font-size:0.75rem; font-weight:600">{row['tipo']}</span>
                </td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#2563eb">{m(row['suma_debe'],  SIM)}</td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#7c3aed">{m(row['suma_haber'], SIM)}</td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#2563eb; font-weight:600">{sd}</td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#7c3aed; font-weight:600">{sa}</td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%; border-collapse:collapse; font-size:0.88rem;">
            <thead>
                <tr style="background:#1a1f36">
                    <th style="padding:0.6rem 0.8rem; text-align:left; color:white">Código</th>
                    <th style="padding:0.6rem 0.8rem; text-align:left; color:white">Cuenta</th>
                    <th style="padding:0.6rem 0.8rem; text-align:center; color:white">Tipo</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right; color:white">Suma DEBE</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right; color:white">Suma HABER</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right; color:white">Saldo Deudor</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right; color:white">Saldo Acreedor</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            <tfoot>
                <tr style="background:#374151; font-weight:700">
                    <td colspan="3" style="padding:0.6rem 0.8rem; color:white">TOTALES</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem; color:white">{m(tot_sd,      SIM)}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem; color:white">{m(tot_sh,      SIM)}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem; color:white">{m(tot_saldo_d, SIM)}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem; color:white">{m(tot_saldo_a, SIM)}</td>
                </tr>
            </tfoot>
        </table>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Estado de Resultados":
    st.title("Estado de Resultados")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    df = query("""
        SELECT c.codigo, c.nombre, c.tipo, c.naturaleza,
               SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) as suma_debe,
               SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) as suma_haber
        FROM cuentas c
        JOIN lineas l ON l.cuenta = c.codigo
        JOIN asientos a ON a.id = l.asiento_id
        WHERE a.fecha BETWEEN ? AND ?
          AND c.tipo IN ('INGRESO','GASTO')
        GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
        ORDER BY c.codigo
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if df.empty:
        st.info("No hay movimientos de ingresos o gastos en el periodo.")
    else:
        def saldo_cuenta(row):
            if row["naturaleza"] == "DEUDORA":
                return row["suma_debe"] - row["suma_haber"]
            else:
                return row["suma_haber"] - row["suma_debe"]

        df["saldo"] = df.apply(saldo_cuenta, axis=1)
        ingresos = df[df["tipo"]=="INGRESO"]
        gastos   = df[df["tipo"]=="GASTO"]

        ventas_brutas      = ingresos[ingresos["codigo"].str.startswith("70")]["saldo"].sum()
        descuentos         = ingresos[ingresos["codigo"].str.startswith("74")]["saldo"].sum()
        otros_ingresos     = ingresos[~ingresos["codigo"].str.startswith(("70","74"))]["saldo"].sum()
        ventas_netas       = ventas_brutas - descuentos
        costo_ventas       = gastos[gastos["codigo"].str.startswith("69")]["saldo"].sum()
        utilidad_bruta     = ventas_netas - costo_ventas
        gastos_op          = gastos[gastos["codigo"].str.startswith(("62","63","65","68"))]["saldo"].sum()
        utilidad_operativa = utilidad_bruta - gastos_op
        otros_gastos       = gastos[gastos["codigo"].str.startswith(("66","67"))]["saldo"].sum()
        utilidad_antes_imp = utilidad_operativa + otros_ingresos - otros_gastos
        gastos_imp         = gastos[gastos["codigo"].str.startswith("88")]["saldo"].sum()
        utilidad_neta      = utilidad_antes_imp - gastos_imp

        c1, c2, c3 = st.columns(3)
        c1.metric("Ventas Netas",   m(ventas_netas,   SIM))
        c2.metric("Utilidad Bruta", m(utilidad_bruta, SIM))
        c3.metric("Utilidad Neta",  m(utilidad_neta,  SIM),
                  delta=f"{(utilidad_neta/ventas_netas*100):.1f}% margen" if ventas_netas else None)

        st.markdown("---")

        def fila(label, valor, indent=False):
            ind = "padding-left:2rem;" if indent else ""
            neg = "color:#ef4444;" if valor < 0 else ""
            return f"""<tr style="border-bottom:1px solid rgba(128,128,128,0.15)">
                <td style="padding:0.5rem 1rem;{ind}">{label}</td>
                <td style="text-align:right; padding:0.5rem 1rem;{neg}">{m(valor, SIM)}</td>
            </tr>"""

        def subtotal(label, valor, color="#1a1f36"):
            return f"""<tr style="background:{color}25">
                <td style="padding:0.6rem 1rem; font-weight:700; color:{color}">{label}</td>
                <td style="text-align:right; padding:0.6rem 1rem; font-weight:700; color:{color}">{m(valor, SIM)}</td>
            </tr>"""

        def separador():
            return '<tr><td colspan="2" style="padding:0; border-top:2px solid rgba(128,128,128,0.2)"></td></tr>'

        def seccion(titulo):
            return f'<tr style="background:rgba(128,128,128,0.15)"><td colspan="2" style="padding:0.4rem 1rem; font-weight:600; font-size:0.8rem; text-transform:uppercase">{titulo}</td></tr>'

        filas_html = ""
        filas_html += seccion("INGRESOS")
        filas_html += fila("Ventas brutas", ventas_brutas, indent=True)
        if descuentos > 0:
            filas_html += fila("(-) Descuentos concedidos", -descuentos, indent=True)
        filas_html += subtotal("VENTAS NETAS", ventas_netas, "#2563eb")
        filas_html += separador()

        filas_html += seccion("COSTOS")
        filas_html += fila("(-) Costo de ventas", -costo_ventas, indent=True)
        filas_html += subtotal("UTILIDAD BRUTA", utilidad_bruta, "#10b981" if utilidad_bruta >= 0 else "#ef4444")
        filas_html += separador()

        filas_html += seccion("GASTOS OPERATIVOS")
        for _, g in gastos[gastos["codigo"].str.startswith(("62","63","65","68"))].iterrows():
            filas_html += fila(f"(-) {g['codigo']} - {g['nombre']}", -g["saldo"], indent=True)
        filas_html += subtotal("UTILIDAD OPERATIVA", utilidad_operativa, "#2563eb" if utilidad_operativa >= 0 else "#ef4444")
        filas_html += separador()

        if otros_ingresos != 0 or otros_gastos != 0:
            filas_html += seccion("OTROS INGRESOS / GASTOS")
            for _, i in ingresos[~ingresos["codigo"].str.startswith(("70","74"))].iterrows():
                filas_html += fila(f"(+) {i['codigo']} - {i['nombre']}", i["saldo"], indent=True)
            for _, g in gastos[gastos["codigo"].str.startswith(("66","67"))].iterrows():
                filas_html += fila(f"(-) {g['codigo']} - {g['nombre']}", -g["saldo"], indent=True)
            filas_html += subtotal("UTILIDAD ANTES DE IMPUESTOS", utilidad_antes_imp, "#2563eb")
            filas_html += separador()

        bg_un = "#10b981" if utilidad_neta >= 0 else "#ef4444"
        filas_html += f"""<tr style="background:{bg_un}">
            <td style="padding:0.8rem 1rem; font-size:1.1rem; font-weight:700; color:white">UTILIDAD NETA DEL EJERCICIO</td>
            <td style="text-align:right; padding:0.8rem 1rem; font-size:1.1rem; font-weight:700; color:white">{m(utilidad_neta, SIM)}</td>
        </tr>"""

        st.markdown(f"""
        <div class="card">
        <h3 style="text-align:center; margin-bottom:0.2rem">ESTADO DE RESULTADOS</h3>
        <p style="text-align:center; opacity:0.6; margin-bottom:1rem">Del {fecha_ini} al {fecha_fin}</p>
        <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
            <tbody>{filas_html}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ESTADO DE SITUACION FINANCIERA
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Estado de Situación Financiera":
    st.title("Estado de Situación Financiera")

    fecha_corte = st.date_input("Fecha de corte", value=date.today())

    df = query("""
        SELECT c.codigo, c.nombre, c.tipo, c.naturaleza,
               SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) as suma_debe,
               SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) as suma_haber
        FROM cuentas c
        JOIN lineas l ON l.cuenta = c.codigo
        JOIN asientos a ON a.id = l.asiento_id
        WHERE a.fecha <= ?
        GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
        ORDER BY c.codigo
    """, (fecha_corte.strftime("%Y-%m-%d"),))

    if df.empty:
        st.info("No hay movimientos registrados hasta la fecha de corte.")
    else:
        def saldo_cuenta(row):
            if row["naturaleza"] == "DEUDORA":
                return row["suma_debe"] - row["suma_haber"]
            else:
                return row["suma_haber"] - row["suma_debe"]

        df["saldo"] = df.apply(saldo_cuenta, axis=1)

        activos    = df[df["tipo"]=="ACTIVO"]
        pasivos    = df[df["tipo"]=="PASIVO"]
        patrimonio = df[df["tipo"]=="PATRIMONIO"]
        resultado  = df[df["tipo"]=="INGRESO"]["saldo"].sum() - df[df["tipo"]=="GASTO"]["saldo"].sum()

        activos_corr = activos[activos["codigo"].str[:2].isin(["10","12","16","20","25","37"])]
        activos_nc   = activos[~activos["codigo"].str[:2].isin(["10","12","16","20","25","37"])]
        pasivos_corr = pasivos[pasivos["codigo"].str[:2].isin(["40","41","42"])]
        pasivos_nc   = pasivos[~pasivos["codigo"].str[:2].isin(["40","41","42"])]

        tot_ac      = activos_corr["saldo"].sum()
        tot_anc     = activos_nc["saldo"].sum()
        tot_activo  = tot_ac + tot_anc
        tot_pc      = pasivos_corr["saldo"].sum()
        tot_pnc     = pasivos_nc["saldo"].sum()
        tot_pasivo  = tot_pc + tot_pnc
        tot_patrim  = patrimonio["saldo"].sum() + resultado
        tot_pas_pat = tot_pasivo + tot_patrim

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Activo",     m(tot_activo, SIM))
        c2.metric("Total Pasivo",     m(tot_pasivo, SIM))
        c3.metric("Total Patrimonio", m(tot_patrim, SIM))

        cuadra = round(tot_activo - tot_pas_pat, 2) == 0
        if cuadra:
            st.markdown('<div class="alert-ok">✅ Activo = Pasivo + Patrimonio</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-err">⚠️ No cuadra. Diferencia: {m(tot_activo - tot_pas_pat, SIM)}</div>', unsafe_allow_html=True)

        st.markdown("---")

        def bloque(titulo, filas_df, total, color):
            html  = f'<div style="margin-bottom:1.5rem">'
            html += f'<div style="background:{color}; color:white; padding:0.5rem 1rem; border-radius:6px 6px 0 0; font-weight:700">{titulo}</div>'
            html += '<table style="width:100%; border-collapse:collapse; font-size:0.88rem;">'
            for _, r in filas_df.iterrows():
                html += f'<tr style="border-bottom:1px solid rgba(128,128,128,0.15)"><td style="padding:0.4rem 1rem">{r["codigo"]} - {r["nombre"]}</td><td style="text-align:right; padding:0.4rem 1rem">{m(r["saldo"], SIM)}</td></tr>'
            html += f'<tr style="background:rgba(128,128,128,0.1); font-weight:700"><td style="padding:0.5rem 1rem">TOTAL</td><td style="text-align:right; padding:0.5rem 1rem; color:{color}">{m(total, SIM)}</td></tr>'
            html += '</table></div>'
            return html

        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown(f'<h3 style="text-align:center">ACTIVO</h3><p style="text-align:center; opacity:0.6; font-size:0.85rem">Al {fecha_corte}</p>', unsafe_allow_html=True)
            st.markdown(bloque("ACTIVO CORRIENTE",    activos_corr, tot_ac,  "#2563eb"), unsafe_allow_html=True)
            st.markdown(bloque("ACTIVO NO CORRIENTE", activos_nc,   tot_anc, "#1d4ed8"), unsafe_allow_html=True)
            st.markdown(f'<div style="background:#1a1f36; color:white; padding:0.7rem 1rem; border-radius:6px; font-weight:700; display:flex; justify-content:space-between"><span>TOTAL ACTIVO</span><span>{m(tot_activo, SIM)}</span></div>', unsafe_allow_html=True)

        with col_der:
            st.markdown(f'<h3 style="text-align:center">PASIVO Y PATRIMONIO</h3><p style="text-align:center; opacity:0.6; font-size:0.85rem">Al {fecha_corte}</p>', unsafe_allow_html=True)
            st.markdown(bloque("PASIVO CORRIENTE", pasivos_corr, tot_pc, "#ef4444"), unsafe_allow_html=True)
            if not pasivos_nc.empty:
                st.markdown(bloque("PASIVO NO CORRIENTE", pasivos_nc, tot_pnc, "#dc2626"), unsafe_allow_html=True)
            st.markdown(f'<div style="background:#ef444425; border:1px solid #ef4444; border-radius:4px; padding:0.4rem 1rem; margin-bottom:0.8rem; font-weight:700; display:flex; justify-content:space-between"><span style="color:#ef4444">TOTAL PASIVO</span><span>{m(tot_pasivo, SIM)}</span></div>', unsafe_allow_html=True)

            patrim_rows = ""
            for _, r in patrimonio.iterrows():
                patrim_rows += f'<tr style="border-bottom:1px solid rgba(128,128,128,0.15)"><td style="padding:0.4rem 1rem">{r["codigo"]} - {r["nombre"]}</td><td style="text-align:right; padding:0.4rem 1rem">{m(r["saldo"], SIM)}</td></tr>'
            color_res = "#10b981" if resultado >= 0 else "#ef4444"
            patrim_rows += f'<tr style="border-bottom:1px solid rgba(128,128,128,0.15)"><td style="padding:0.4rem 1rem; font-style:italic">Resultado del ejercicio</td><td style="text-align:right; padding:0.4rem 1rem; color:{color_res}">{m(resultado, SIM)}</td></tr>'
            patrim_rows += f'<tr style="background:rgba(128,128,128,0.1); font-weight:700"><td style="padding:0.5rem 1rem">TOTAL</td><td style="text-align:right; padding:0.5rem 1rem; color:#8b5cf6">{m(tot_patrim, SIM)}</td></tr>'

            st.markdown(f"""
            <div style="margin-bottom:1.5rem">
                <div style="background:#8b5cf6; color:white; padding:0.5rem 1rem; border-radius:6px 6px 0 0; font-weight:700">PATRIMONIO</div>
                <table style="width:100%; border-collapse:collapse; font-size:0.88rem;">
                    <tbody>{patrim_rows}</tbody>
                </table>
            </div>
            <div style="background:#1a1f36; color:white; padding:0.7rem 1rem; border-radius:6px; font-weight:700; display:flex; justify-content:space-between">
                <span>TOTAL PASIVO + PATRIMONIO</span><span>{m(tot_pas_pat, SIM)}</span>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN DE CUENTAS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "Plan de Cuentas":
    st.title("Plan de Cuentas")

    tab1, tab2 = st.tabs(["Ver cuentas", "Agregar cuenta"])

    with tab1:
        df = query("SELECT codigo as 'Código', nombre as 'Nombre', tipo as 'Tipo', naturaleza as 'Naturaleza' FROM cuentas ORDER BY codigo")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            nuevo_cod = st.text_input("Código de cuenta", placeholder="Ej: 10, 42, 70")
            nuevo_nom = st.text_input("Nombre de la cuenta", placeholder="Ej: Caja y Bancos")
        with col2:
            nuevo_tipo = st.selectbox("Tipo", ["ACTIVO","PASIVO","PATRIMONIO","INGRESO","GASTO"])
            nuevo_nat  = st.selectbox("Naturaleza", ["DEUDORA","ACREEDORA"])

        if st.button("Agregar Cuenta"):
            if not nuevo_cod or not nuevo_nom:
                st.error("Completa todos los campos.")
            else:
                existe = query("SELECT codigo FROM cuentas WHERE codigo=?", (nuevo_cod,))
                if not existe.empty:
                    st.error(f"El código {nuevo_cod} ya existe.")
                else:
                    execute("INSERT INTO cuentas VALUES (?,?,?,?)", (nuevo_cod, nuevo_nom, nuevo_tipo, nuevo_nat))
                    st.success(f"✅ Cuenta {nuevo_cod} - {nuevo_nom} agregada.")
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# ASISTENTE IA (GROQ)
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🤖 Asistente IA":
    from groq import Groq

    st.title("🤖 Asistente Contable IA")
    st.markdown("Describe una operación para registrarla, o usa los accesos rápidos para ver tus estados financieros.")

    # ── Datos reales de la BD ─────────────────────────────────────────────────
    cuentas_df = query("SELECT codigo, nombre, tipo, naturaleza FROM cuentas ORDER BY codigo")
    cuentas_contexto = "\n".join(
        f"{r.codigo} - {r.nombre} ({r.tipo}, {r.naturaleza})"
        for _, r in cuentas_df.iterrows()
    )

    df_diario = query("""
        SELECT a.numero, a.fecha, a.glosa, c.codigo, c.nombre, l.columna, l.monto
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        JOIN cuentas c ON c.codigo = l.cuenta
        ORDER BY a.numero, l.columna DESC
    """)

    df_mayor = query("""
        SELECT c.codigo, c.nombre, c.tipo, c.naturaleza,
               SUM(CASE WHEN l.columna='DEBE'  THEN l.monto ELSE 0 END) as suma_debe,
               SUM(CASE WHEN l.columna='HABER' THEN l.monto ELSE 0 END) as suma_haber
        FROM cuentas c
        JOIN lineas l ON l.cuenta = c.codigo
        JOIN asientos a ON a.id = l.asiento_id
        GROUP BY c.codigo, c.nombre, c.tipo, c.naturaleza
        ORDER BY c.codigo
    """)

    if not df_mayor.empty:
        def calc_saldo_mayor(row):
            if row["naturaleza"] == "DEUDORA":
                return row["suma_debe"] - row["suma_haber"]
            else:
                return row["suma_haber"] - row["suma_debe"]
        df_mayor["saldo"] = df_mayor.apply(calc_saldo_mayor, axis=1)

    df_er  = df_mayor[df_mayor["tipo"].isin(["INGRESO","GASTO"])]     if not df_mayor.empty else pd.DataFrame()
    df_esf = df_mayor[df_mayor["tipo"].isin(["ACTIVO","PASIVO","PATRIMONIO"])] if not df_mayor.empty else pd.DataFrame()

    total_ingresos = df_er[df_er["tipo"]=="INGRESO"]["saldo"].sum() if not df_er.empty else 0
    total_gastos   = df_er[df_er["tipo"]=="GASTO"]["saldo"].sum()   if not df_er.empty else 0
    utilidad_neta  = total_ingresos - total_gastos
    total_activo   = df_esf[df_esf["tipo"]=="ACTIVO"]["saldo"].sum()     if not df_esf.empty else 0
    total_pasivo   = df_esf[df_esf["tipo"]=="PASIVO"]["saldo"].sum()     if not df_esf.empty else 0
    total_patrim   = df_esf[df_esf["tipo"]=="PATRIMONIO"]["saldo"].sum() if not df_esf.empty else 0
    total_patrim  += utilidad_neta

    # ── Textos para el contexto del LLM ──────────────────────────────────────
    if not df_diario.empty:
        diario_texto = ""
        for num in df_diario["numero"].unique():
            grupo = df_diario[df_diario["numero"] == num]
            diario_texto += f"\nAsiento N°{num:03d} | {grupo['fecha'].iloc[0]} | {grupo['glosa'].iloc[0] or ''}\n"
            for _, r in grupo.iterrows():
                diario_texto += f"  {r['codigo']} - {r['nombre']} | {r['columna']} | {r['monto']:.2f}\n"
    else:
        diario_texto = "Sin asientos registrados."

    if not df_mayor.empty:
        mayor_texto = ""
        for _, r in df_mayor.iterrows():
            mayor_texto += f"{r['codigo']} - {r['nombre']} ({r['tipo']}) | DEBE: {r['suma_debe']:.2f} | HABER: {r['suma_haber']:.2f} | Saldo: {r['saldo']:.2f} ({r['naturaleza']})\n"
    else:
        mayor_texto = "Sin movimientos."

    if not df_er.empty:
        er_texto = ""
        for _, r in df_er.iterrows():
            er_texto += f"{r['tipo']} | {r['codigo']} - {r['nombre']} | Saldo: {r['saldo']:.2f}\n"
        er_texto += f"\nTOTAL INGRESOS: {total_ingresos:.2f}\nTOTAL GASTOS: {total_gastos:.2f}\nUTILIDAD NETA: {utilidad_neta:.2f}"
    else:
        er_texto = "Sin movimientos de ingresos/gastos."

    if not df_esf.empty:
        esf_texto = ""
        for _, r in df_esf.iterrows():
            esf_texto += f"{r['tipo']} | {r['codigo']} - {r['nombre']} | Saldo: {r['saldo']:.2f}\n"
        esf_texto += f"\nTOTAL ACTIVO: {total_activo:.2f}\nTOTAL PASIVO: {total_pasivo:.2f}\nTOTAL PATRIMONIO: {total_patrim:.2f}"
    else:
        esf_texto = "Sin movimientos de activo/pasivo/patrimonio."

    SYSTEM_PROMPT = f"""Eres un asistente contable experto en el Plan Contable General Empresarial (PCGE) de Perú.
Tienes acceso a los datos reales de la empresa "{empresa_actual}" con moneda {SIM}.

━━━ LIBRO DIARIO ━━━
{diario_texto}

━━━ LIBRO MAYOR (saldos) ━━━
{mayor_texto}

━━━ ESTADO DE RESULTADOS ━━━
{er_texto}

━━━ ESTADO DE SITUACIÓN FINANCIERA ━━━
{esf_texto}

━━━ CUENTAS DISPONIBLES ━━━
{cuentas_contexto}

━━━ TUS CAPACIDADES ━━━
Puedes hacer DOS cosas:

1. CONSULTAS: Si el usuario pregunta por sus estados financieros o pide ver el libro diario, mayor, balance de comprobación, estado de resultados o estado de situación financiera, responde usando los datos reales de arriba. Muestra tablas en markdown bien formateadas con todos los registros completos, sin omitir ninguno.

2. REGISTRO DE ASIENTOS: Si el usuario describe una operación contable (puede ser un texto largo con varias operaciones), interpreta CADA operación y genera UN JSON por cada asiento. Devuelve una lista JSON así:
[
  {{
    "glosa": "descripción breve",
    "lineas": [
      {{"cuenta": "10", "monto": 1000.00, "columna": "DEBE"}},
      {{"cuenta": "70", "monto": 1000.00, "columna": "HABER"}}
    ],
    "explicacion": "por qué se usa cada cuenta"
  }}
]

Reglas para asientos:
- DEBE siempre igual a HABER en cada asiento
- Solo usar cuentas de la lista disponible
- Montos positivos
- Si no hay monto claro, usar 0 y avisar en la explicación

Responde siempre en español. Si no queda claro si es consulta o registro, pregunta al usuario.
"""

    # ── Historial ─────────────────────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Input ─────────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ej: El 01/01 vendimos mercadería por S/5000 al contado y compramos útiles por S/200...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        try:
            api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
            if not api_key:
                st.error("❌ No se encontró GROQ_API_KEY.")
                st.stop()

            client = Groq(api_key=api_key)

            messages_groq = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in st.session_state.chat_history:
                messages_groq.append({"role": msg["role"], "content": msg["content"]})

            with st.spinner("Analizando..."):
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_groq,
                    temperature=0.1,
                    max_tokens=4000,
                )

            respuesta_raw = response.choices[0].message.content.strip()

            # Intentar parsear como JSON (lista de asientos)
            try:
                respuesta_limpia = respuesta_raw
                if "```" in respuesta_limpia:
                    respuesta_limpia = respuesta_limpia.split("```")[1]
                    if respuesta_limpia.startswith("json"):
                        respuesta_limpia = respuesta_limpia[4:]

                datos = json.loads(respuesta_limpia)

                # Normalizar: si viene un dict solo, convertir a lista
                if isinstance(datos, dict):
                    datos = [datos]

                with st.chat_message("assistant"):
                    for i, asiento in enumerate(datos):
                        total_debe  = sum(l["monto"] for l in asiento["lineas"] if l["columna"] == "DEBE")
                        total_haber = sum(l["monto"] for l in asiento["lineas"] if l["columna"] == "HABER")
                        cuadra = round(total_debe - total_haber, 2) == 0

                        st.markdown(f"**Asiento {i+1}: {asiento['glosa']}**")
                        st.markdown(f"_{asiento['explicacion']}_")

                        filas = ""
                        for linea in asiento["lineas"]:
                            cuenta_info = cuentas_df[cuentas_df["codigo"] == linea["cuenta"]]
                            nombre_cta  = cuenta_info["nombre"].iloc[0] if not cuenta_info.empty else "?"
                            d = m(linea["monto"], SIM) if linea["columna"] == "DEBE"  else ""
                            h = m(linea["monto"], SIM) if linea["columna"] == "HABER" else ""
                            filas += f"""<tr style="border-bottom:1px solid rgba(128,128,128,0.15)">
                                <td style="padding:0.4rem 0.8rem">{linea['cuenta']} - {nombre_cta}</td>
                                <td style="text-align:right;padding:0.4rem 0.8rem;color:#2563eb;font-weight:500">{d}</td>
                                <td style="text-align:right;padding:0.4rem 0.8rem;color:#7c3aed;font-weight:500">{h}</td>
                            </tr>"""

                        estado_color = "#d1fae5" if cuadra else "#fee2e2"
                        estado_texto = "✅ Cuadra" if cuadra else "⚠️ No cuadra"

                        st.markdown(f"""
                        <div class="card">
                        <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
                            <thead>
                                <tr style="background:rgba(128,128,128,0.15)">
                                    <th style="text-align:left;padding:0.4rem 0.8rem">Cuenta</th>
                                    <th style="text-align:right;padding:0.4rem 0.8rem">DEBE</th>
                                    <th style="text-align:right;padding:0.4rem 0.8rem">HABER</th>
                                </tr>
                            </thead>
                            <tbody>{filas}</tbody>
                            <tfoot>
                                <tr style="background:#1a1f36;font-weight:700">
                                    <td style="padding:0.4rem 0.8rem;color:white">TOTAL</td>
                                    <td style="text-align:right;padding:0.4rem 0.8rem;color:white">{m(total_debe, SIM)}</td>
                                    <td style="text-align:right;padding:0.4rem 0.8rem;color:white">{m(total_haber, SIM)}</td>
                                </tr>
                            </tfoot>
                        </table>
                        </div>
                        <div style="background:{estado_color};padding:0.5rem 1rem;border-radius:6px;margin-top:0.5rem;margin-bottom:1rem">{estado_texto}</div>
                        """, unsafe_allow_html=True)

                        if cuadra and total_debe > 0:
                            if st.button(f"✅ Registrar asiento {i+1}", key=f"reg_{len(st.session_state.chat_history)}_{i}"):
                                num_nuevo = proximo_numero()
                                asiento_id = execute(
                                    "INSERT INTO asientos (numero, fecha, glosa) VALUES (?,?,?)",
                                    (num_nuevo, date.today().strftime("%Y-%m-%d"), asiento["glosa"])
                                )
                                data_lineas = [
                                    (asiento_id, l["cuenta"], l["monto"], l["columna"])
                                    for l in asiento["lineas"] if l["monto"] > 0
                                ]
                                executemany("INSERT INTO lineas (asiento_id, cuenta, monto, columna) VALUES (?,?,?,?)", data_lineas)
                                st.success(f"✅ Asiento N° {num_nuevo:03d} registrado.")

                resumen = " / ".join(a["glosa"] for a in datos)
                st.session_state.chat_history.append({"role": "assistant", "content": f"Asientos generados: {resumen}"})

            except (json.JSONDecodeError, KeyError):
                # Respuesta de texto (consulta de estados financieros)
                with st.chat_message("assistant"):
                    st.markdown(respuesta_raw)
                st.session_state.chat_history.append({"role": "assistant", "content": respuesta_raw})

        except Exception as e:
            st.error(f"Error al conectar con Groq: {e}")

    if st.session_state.chat_history:
        if st.button("🗑 Limpiar conversación"):
            st.session_state.chat_history = []
            st.rerun()
