import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Sistema Contable",
    page_icon="📒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background: #f8f9fa; }
    .stApp > header { background: transparent; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f36 0%, #242943 100%);
    }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    section[data-testid="stSidebar"] .stRadio label { color: #e2e8f0 !important; }

    /* Cards */
    .card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        border-left: 4px solid #4f46e5;
    }
    .card-green { border-left-color: #10b981; }
    .card-red { border-left-color: #ef4444; }
    .card-yellow { border-left-color: #f59e0b; }

    /* Métricas */
    .metric-box {
        background: white;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        text-align: center;
    }
    .metric-label { font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #1a1f36; }
    .metric-value.green { color: #10b981; }
    .metric-value.red { color: #ef4444; }

    /* Tablas */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    thead tr th { background: #1a1f36 !important; color: white !important; font-weight: 600 !important; }

    /* Botones */
    .stButton > button {
        background: #4f46e5;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s;
    }
    .stButton > button:hover { background: #4338ca; transform: translateY(-1px); }

    /* Títulos */
    h1 { color: #1a1f36; font-weight: 700; }
    h2 { color: #1a1f36; font-weight: 600; font-size: 1.3rem; }
    h3 { color: #374151; font-weight: 600; }

    /* Asiento counter */
    .asiento-badge {
        background: #4f46e5;
        color: white;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* Alert personalizada */
    .alert-ok { background:#d1fae5; border:1px solid #10b981; border-radius:8px; padding:0.8rem 1rem; color:#065f46; }
    .alert-err { background:#fee2e2; border:1px solid #ef4444; border-radius:8px; padding:0.8rem 1rem; color:#991b1b; }
    .alert-warn { background:#fef3c7; border:1px solid #f59e0b; border-radius:8px; padding:0.8rem 1rem; color:#92400e; }
</style>
""", unsafe_allow_html=True)

# ── Base de datos ─────────────────────────────────────────────────────────────
DB = "contabilidad.db"

def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Catálogo de cuentas
    c.execute("""CREATE TABLE IF NOT EXISTS cuentas (
        codigo TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        tipo   TEXT NOT NULL,   -- ACTIVO, PASIVO, PATRIMONIO, INGRESO, GASTO
        naturaleza TEXT NOT NULL  -- DEUDORA, ACREEDORA
    )""")
    # Asientos (cabecera)
    c.execute("""CREATE TABLE IF NOT EXISTS asientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero INTEGER NOT NULL,
        fecha  TEXT NOT NULL,
        glosa  TEXT
    )""")
    # Líneas del asiento
    c.execute("""CREATE TABLE IF NOT EXISTS lineas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        asiento_id INTEGER NOT NULL,
        cuenta     TEXT NOT NULL,
        monto      REAL NOT NULL,
        columna    TEXT NOT NULL,   -- DEBE | HABER
        FOREIGN KEY(asiento_id) REFERENCES asientos(id)
    )""")
    # Plan de cuentas PCGE básico
    cuentas_base = [
        ("10","Caja y Bancos (Efectivo)","ACTIVO","DEUDORA"),
        ("12","Cuentas por Cobrar Comerciales","ACTIVO","DEUDORA"),
        ("16","Cuentas por Cobrar Diversas","ACTIVO","DEUDORA"),
        ("20","Mercaderías (Inventarios)","ACTIVO","DEUDORA"),
        ("25","Materiales Auxiliares","ACTIVO","DEUDORA"),
        ("33","Inmuebles Maquinaria y Equipo","ACTIVO","DEUDORA"),
        ("34","Intangibles","ACTIVO","DEUDORA"),
        ("36","Desvalorización de Activos","ACTIVO","DEUDORA"),
        ("37","Activo Diferido","ACTIVO","DEUDORA"),
        ("39","Depreciación Acumulada","ACTIVO","ACREEDORA"),
        ("40","Tributos por Pagar","PASIVO","ACREEDORA"),
        ("41","Remuneraciones y Participaciones por Pagar","PASIVO","ACREEDORA"),
        ("42","Cuentas por Pagar Comerciales","PASIVO","ACREEDORA"),
        ("45","Obligaciones Financieras","PASIVO","ACREEDORA"),
        ("46","Cuentas por Pagar Diversas","PASIVO","ACREEDORA"),
        ("50","Capital Social","PATRIMONIO","ACREEDORA"),
        ("57","Excedente de Revaluación","PATRIMONIO","ACREEDORA"),
        ("58","Reservas","PATRIMONIO","ACREEDORA"),
        ("59","Resultados Acumulados","PATRIMONIO","ACREEDORA"),
        ("60","Compras","GASTO","DEUDORA"),
        ("61","Variación de Inventarios","GASTO","DEUDORA"),
        ("62","Gastos de Personal","GASTO","DEUDORA"),
        ("63","Gastos de Servicios","GASTO","DEUDORA"),
        ("65","Otros Gastos de Gestión","GASTO","DEUDORA"),
        ("66","Pérdida por Medición de Activos","GASTO","DEUDORA"),
        ("67","Gastos Financieros","GASTO","DEUDORA"),
        ("68","Valuación y Deterioro de Activos","GASTO","DEUDORA"),
        ("69","Costo de Ventas","GASTO","DEUDORA"),
        ("70","Ventas","INGRESO","ACREEDORA"),
        ("74","Descuentos Concedidos","INGRESO","DEUDORA"),
        ("75","Otros Ingresos de Gestión","INGRESO","ACREEDORA"),
        ("77","Ingresos Financieros","INGRESO","ACREEDORA"),
    ]
    c.executemany("INSERT OR IGNORE INTO cuentas VALUES (?,?,?,?)", cuentas_base)
    conn.commit()
    conn.close()

init_db()

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

def fmt(val):
    """Formatea número como moneda."""
    if pd.isna(val) or val == 0:
        return "-"
    return f"S/ {val:,.2f}"

def proximo_numero():
    df = query("SELECT MAX(numero) as n FROM asientos")
    n = df["n"].iloc[0]
    return 1 if pd.isna(n) else int(n) + 1

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📒 Sistema Contable")
    st.markdown("---")
    pagina = st.radio("Navegación", [
        "📝 Registro de Asientos",
        "📖 Libro Diario",
        "📊 Libro Mayor",
        "⚖️ Balance de Comprobación",
        "📈 Estado de Resultados",
        "🏦 Estado de Situación Financiera",
        "⚙️ Plan de Cuentas",
    ])
    st.markdown("---")
    # Mini resumen
    total_asientos = query("SELECT COUNT(*) as n FROM asientos")["n"].iloc[0]
    st.markdown(f"**Asientos registrados:** {total_asientos}")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: REGISTRO DE ASIENTOS
# ═══════════════════════════════════════════════════════════════════════════════
if pagina == "📝 Registro de Asientos":
    st.title("📝 Registro de Asientos Contables")

    # Inicializar líneas en session_state
    if "lineas_asiento" not in st.session_state:
        st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]

    # ── Cabecera ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Cabecera del Asiento")
    col1, col2, col3 = st.columns([1,2,4])
    with col1:
        num = proximo_numero()
        st.markdown(f"**Nº Asiento:** <span class='asiento-badge'>{num:03d}</span>", unsafe_allow_html=True)
    with col2:
        fecha = st.date_input("Fecha", value=date.today())
    with col3:
        glosa = st.text_input("Glosa / Descripción", placeholder="Ej: Compra de mercadería al contado")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Líneas ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Líneas del Asiento")

    cuentas_df = query("SELECT codigo, nombre, tipo FROM cuentas ORDER BY codigo")
    cuentas_opciones = {f"{r.codigo} - {r.nombre}": r.codigo for _, r in cuentas_df.iterrows()}
    cuentas_lista = list(cuentas_opciones.keys())

    # Encabezados de tabla
    h1, h2, h3, h4 = st.columns([3,2,2,1])
    h1.markdown("**Cuenta Contable**")
    h2.markdown("**Monto (S/)**")
    h3.markdown("**Debe / Haber**")
    h4.markdown("")

    lineas_validas = []
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
            monto = st.number_input("", min_value=0.0, value=float(linea["monto"]), step=0.01, format="%.2f", key=f"monto_{i}", label_visibility="collapsed")
            linea["monto"] = monto
        with c3:
            col_idx = 0 if linea["columna"] == "DEBE" else 1
            columna = st.selectbox("", ["DEBE","HABER"], index=col_idx, key=f"col_{i}", label_visibility="collapsed")
            linea["columna"] = columna
        with c4:
            if st.button("🗑", key=f"del_{i}") and len(st.session_state.lineas_asiento) > 1:
                to_delete = i

        lineas_validas.append(linea)

    if to_delete is not None:
        st.session_state.lineas_asiento.pop(to_delete)
        st.rerun()

    # Botón agregar línea
    if st.button("➕ Agregar línea"):
        st.session_state.lineas_asiento.append({"cuenta":"","monto":0.0,"columna":"DEBE"})
        st.rerun()

    # ── Totales y validación ──
    total_debe  = sum(l["monto"] for l in st.session_state.lineas_asiento if l["columna"] == "DEBE")
    total_haber = sum(l["monto"] for l in st.session_state.lineas_asiento if l["columna"] == "HABER")
    diff = round(total_debe - total_haber, 2)

    st.markdown("---")
    t1, t2, t3 = st.columns(3)
    t1.metric("Total DEBE", f"S/ {total_debe:,.2f}")
    t2.metric("Total HABER", f"S/ {total_haber:,.2f}")
    t3.metric("Diferencia", f"S/ {diff:,.2f}", delta=None)

    if diff == 0 and total_debe > 0:
        st.markdown('<div class="alert-ok">✅ El asiento está cuadrado (Debe = Haber)</div>', unsafe_allow_html=True)
    elif total_debe > 0 or total_haber > 0:
        st.markdown(f'<div class="alert-err">❌ El asiento no cuadra. Diferencia: S/ {abs(diff):,.2f}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Guardar ──
    col_btn1, col_btn2 = st.columns([1,5])
    with col_btn1:
        if st.button("💾 Guardar Asiento"):
            errores = []
            if total_debe == 0 and total_haber == 0:
                errores.append("El asiento no tiene montos.")
            if diff != 0:
                errores.append(f"El asiento no cuadra (diferencia S/ {abs(diff):,.2f}).")
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
                st.success(f"✅ Asiento Nº {num:03d} guardado correctamente.")
                st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]
                st.rerun()

    with col_btn2:
        if st.button("🗑️ Limpiar formulario"):
            st.session_state.lineas_asiento = [{"cuenta":"","monto":0.0,"columna":"DEBE"}]
            st.rerun()

    # ── Últimos asientos ──
    st.markdown("---")
    st.markdown("### Últimos asientos registrados")
    ultimos = query("""
        SELECT a.numero as 'Nº', a.fecha as 'Fecha', a.glosa as 'Glosa',
               c.nombre as 'Cuenta', l.columna as 'D/H',
               l.monto as 'Monto'
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        JOIN cuentas c ON c.codigo = l.cuenta
        ORDER BY a.numero DESC, l.columna
        LIMIT 30
    """)
    if not ultimos.empty:
        ultimos["Monto"] = ultimos["Monto"].apply(lambda x: f"S/ {x:,.2f}")
        st.dataframe(ultimos, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LIBRO DIARIO
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📖 Libro Diario":
    st.title("📖 Libro Diario")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    df = query("""
        SELECT a.numero, a.fecha, a.glosa, c.codigo, c.nombre,
               l.columna, l.monto
        FROM asientos a
        JOIN lineas l ON l.asiento_id = a.id
        JOIN cuentas c ON c.codigo = l.cuenta
        WHERE a.fecha BETWEEN ? AND ?
        ORDER BY a.numero, l.columna DESC, l.id
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if df.empty:
        st.info("No hay asientos en el período seleccionado.")
    else:
        asientos = df["numero"].unique()
        for num_asiento in asientos:
            grupo = df[df["numero"] == num_asiento]
            fecha_a = grupo["fecha"].iloc[0]
            glosa_a = grupo["glosa"].iloc[0]

            st.markdown(f"""
            <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem">
                <span><b>Asiento Nº {num_asiento:03d}</b> &nbsp;&nbsp; {fecha_a} &nbsp;&nbsp; <span style="color:#6b7280">{glosa_a}</span></span>
            </div>
            """, unsafe_allow_html=True)

            rows_html = ""
            tot_debe = tot_haber = 0
            for _, row in grupo.iterrows():
                d = f"S/ {row['monto']:,.2f}" if row["columna"] == "DEBE" else ""
                h = f"S/ {row['monto']:,.2f}" if row["columna"] == "HABER" else ""
                indent = "" if row["columna"] == "DEBE" else "padding-left:2rem;"
                if row["columna"] == "DEBE": tot_debe += row["monto"]
                else: tot_haber += row["monto"]
                rows_html += f"""
                <tr>
                    <td style="{indent}">{row['codigo']} - {row['nombre']}</td>
                    <td style="text-align:right; color:#2563eb; font-weight:500">{d}</td>
                    <td style="text-align:right; color:#7c3aed; font-weight:500">{h}</td>
                </tr>"""

            st.markdown(f"""
            <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
                <thead>
                    <tr style="background:#f3f4f6; color:#374151">
                        <th style="text-align:left; padding:0.4rem 0.8rem">Cuenta</th>
                        <th style="text-align:right; padding:0.4rem 0.8rem; width:150px">DEBE</th>
                        <th style="text-align:right; padding:0.4rem 0.8rem; width:150px">HABER</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
                <tfoot>
                    <tr style="background:#1a1f36; color:white; font-weight:700">
                        <td style="padding:0.4rem 0.8rem">TOTAL</td>
                        <td style="text-align:right; padding:0.4rem 0.8rem">S/ {tot_debe:,.2f}</td>
                        <td style="text-align:right; padding:0.4rem 0.8rem">S/ {tot_haber:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LIBRO MAYOR
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📊 Libro Mayor":
    st.title("📊 Libro Mayor")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    # Cuentas con movimiento
    cuentas_mov = query("""
        SELECT DISTINCT l.cuenta, c.nombre, c.tipo, c.naturaleza
        FROM lineas l
        JOIN asientos a ON a.id = l.asiento_id
        JOIN cuentas c ON c.codigo = l.cuenta
        WHERE a.fecha BETWEEN ? AND ?
        ORDER BY l.cuenta
    """, (fecha_ini.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))

    if cuentas_mov.empty:
        st.info("No hay movimientos en el período seleccionado.")
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

            color_tipo = {"ACTIVO":"#3b82f6","PASIVO":"#ef4444","PATRIMONIO":"#8b5cf6","INGRESO":"#10b981","GASTO":"#f59e0b"}.get(tipo,"#6b7280")

            rows_html = ""
            saldo_acum = 0
            for _, m in movs.iterrows():
                d = f"S/ {m['monto']:,.2f}" if m["columna"]=="DEBE" else ""
                h = f"S/ {m['monto']:,.2f}" if m["columna"]=="HABER" else ""
                if natura=="DEUDORA":
                    saldo_acum += m["monto"] if m["columna"]=="DEBE" else -m["monto"]
                else:
                    saldo_acum += m["monto"] if m["columna"]=="HABER" else -m["monto"]
                rows_html += f"""
                <tr style="border-bottom:1px solid #f3f4f6">
                    <td style="padding:0.3rem 0.6rem">{m['fecha']}</td>
                    <td style="padding:0.3rem 0.6rem">Nº{m['numero']:03d}</td>
                    <td style="padding:0.3rem 0.6rem; color:#6b7280">{m['glosa']}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; color:#2563eb">{d}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; color:#7c3aed">{h}</td>
                    <td style="text-align:right; padding:0.3rem 0.6rem; font-weight:600">S/ {abs(saldo_acum):,.2f}</td>
                </tr>"""

            st.markdown(f"""
            <div class="card" style="border-left-color:{color_tipo}">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem">
                <div>
                    <span style="font-size:1.1rem; font-weight:700">{codigo} – {nombre}</span>
                    <span style="background:{color_tipo}20; color:{color_tipo}; border-radius:20px; padding:0.15rem 0.7rem; font-size:0.75rem; font-weight:600; margin-left:0.5rem">{tipo}</span>
                </div>
                <div style="text-align:right">
                    <div style="font-size:0.75rem; color:#6b7280">{saldo_label}</div>
                    <div style="font-size:1.2rem; font-weight:700; color:{color_tipo}">S/ {saldo:,.2f}</div>
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <thead>
                    <tr style="background:#f9fafb; color:#374151">
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
                    <tr style="background:#1a1f36; color:white; font-weight:700">
                        <td colspan="3" style="padding:0.4rem 0.6rem">TOTALES</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem">S/ {tot_debe:,.2f}</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem">S/ {tot_haber:,.2f}</td>
                        <td style="text-align:right; padding:0.4rem 0.6rem">S/ {saldo:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: BALANCE DE COMPROBACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚖️ Balance de Comprobación":
    st.title("⚖️ Balance de Comprobación")

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
        st.info("No hay movimientos en el período.")
    else:
        def calc_saldo(row):
            if row["naturaleza"] == "DEUDORA":
                s = row["suma_debe"] - row["suma_haber"]
                return (abs(s), 0) if s >= 0 else (0, abs(s))
            else:
                s = row["suma_haber"] - row["suma_debe"]
                return (0, abs(s)) if s >= 0 else (abs(s), 0)

        df[["saldo_deudor","saldo_acreedor"]] = df.apply(calc_saldo, axis=1, result_type="expand")

        tot_sd = df["suma_debe"].sum()
        tot_sh = df["suma_haber"].sum()
        tot_saldo_d = df["saldo_deudor"].sum()
        tot_saldo_a = df["saldo_acreedor"].sum()

        # Métricas
        m1, m2, m3, m4 = st.columns(4)
        cuadra = round(tot_sd - tot_sh, 2) == 0
        with m1:
            st.metric("Total DEBE", f"S/ {tot_sd:,.2f}")
        with m2:
            st.metric("Total HABER", f"S/ {tot_sh:,.2f}")
        with m3:
            st.metric("Saldos Deudores", f"S/ {tot_saldo_d:,.2f}")
        with m4:
            st.metric("Saldos Acreedores", f"S/ {tot_saldo_a:,.2f}")

        if cuadra:
            st.markdown('<div class="alert-ok">✅ El balance cuadra correctamente</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-err">❌ El balance no cuadra</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Tabla
        color_tipo = {"ACTIVO":"#dbeafe","PASIVO":"#fee2e2","PATRIMONIO":"#ede9fe","INGRESO":"#d1fae5","GASTO":"#fef3c7"}
        rows_html = ""
        for _, row in df.iterrows():
            bg = color_tipo.get(row["tipo"],"#f9fafb")
            rows_html += f"""
            <tr style="border-bottom:1px solid #e5e7eb">
                <td style="padding:0.4rem 0.8rem; font-weight:600">{row['codigo']}</td>
                <td style="padding:0.4rem 0.8rem">{row['nombre']}</td>
                <td style="padding:0.4rem 0.8rem; text-align:center">
                    <span style="background:{bg}; border-radius:4px; padding:0.1rem 0.5rem; font-size:0.75rem">{row['tipo']}</span>
                </td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#2563eb">S/ {row['suma_debe']:,.2f}</td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#7c3aed">S/ {row['suma_haber']:,.2f}</td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#2563eb; font-weight:600">
                    {"S/ {:,.2f}".format(row['saldo_deudor']) if row['saldo_deudor'] > 0 else "-"}
                </td>
                <td style="padding:0.4rem 0.8rem; text-align:right; color:#7c3aed; font-weight:600">
                    {"S/ {:,.2f}".format(row['saldo_acreedor']) if row['saldo_acreedor'] > 0 else "-"}
                </td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%; border-collapse:collapse; font-size:0.88rem;">
            <thead>
                <tr style="background:#1a1f36; color:white">
                    <th style="padding:0.6rem 0.8rem; text-align:left">Código</th>
                    <th style="padding:0.6rem 0.8rem; text-align:left">Cuenta</th>
                    <th style="padding:0.6rem 0.8rem; text-align:center">Tipo</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right">Suma DEBE</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right">Suma HABER</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right">Saldo Deudor</th>
                    <th style="padding:0.6rem 0.8rem; text-align:right">Saldo Acreedor</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
            <tfoot>
                <tr style="background:#374151; color:white; font-weight:700">
                    <td colspan="3" style="padding:0.6rem 0.8rem">TOTALES</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem">S/ {tot_sd:,.2f}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem">S/ {tot_sh:,.2f}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem">S/ {tot_saldo_d:,.2f}</td>
                    <td style="text-align:right; padding:0.6rem 0.8rem">S/ {tot_saldo_a:,.2f}</td>
                </tr>
            </tfoot>
        </table>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: ESTADO DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📈 Estado de Resultados":
    st.title("📈 Estado de Resultados")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_ini = st.date_input("Desde", value=date(date.today().year, 1, 1))
    with col_f2:
        fecha_fin = st.date_input("Hasta", value=date.today())

    # Saldos por cuenta
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
        st.info("No hay movimientos de ingresos o gastos en el período.")
    else:
        def saldo_cuenta(row):
            if row["naturaleza"] == "DEUDORA":
                return row["suma_debe"] - row["suma_haber"]
            else:
                return row["suma_haber"] - row["suma_debe"]

        df["saldo"] = df.apply(saldo_cuenta, axis=1)

        ingresos = df[df["tipo"]=="INGRESO"]
        gastos   = df[df["tipo"]=="GASTO"]

        # Ventas netas (70) vs descuentos (74)
        ventas_brutas = ingresos[ingresos["codigo"].str.startswith("70")]["saldo"].sum()
        descuentos    = ingresos[ingresos["codigo"].str.startswith("74")]["saldo"].sum()
        otros_ingresos = ingresos[~ingresos["codigo"].str.startswith(("70","74"))]["saldo"].sum()
        ventas_netas  = ventas_brutas - descuentos

        costo_ventas  = gastos[gastos["codigo"].str.startswith("69")]["saldo"].sum()
        utilidad_bruta = ventas_netas - costo_ventas

        # Gastos operativos (62,63,65,68)
        gastos_op = gastos[gastos["codigo"].str.startswith(("62","63","65","68"))]["saldo"].sum()
        utilidad_operativa = utilidad_bruta - gastos_op

        # Otros gastos (66,67)
        otros_gastos = gastos[gastos["codigo"].str.startswith(("66","67"))]["saldo"].sum()
        utilidad_antes_imp = utilidad_operativa + otros_ingresos - otros_gastos

        # Impuestos (gasto 40x si aplica)
        gastos_imp = gastos[gastos["codigo"].str.startswith("88")]["saldo"].sum()
        utilidad_neta = utilidad_antes_imp - gastos_imp

        # Métricas resumen
        m1, m2, m3 = st.columns(3)
        m1.metric("Ventas Netas", f"S/ {ventas_netas:,.2f}")
        m2.metric("Utilidad Bruta", f"S/ {utilidad_bruta:,.2f}")
        m3.metric("Utilidad Neta", f"S/ {utilidad_neta:,.2f}", delta=f"{(utilidad_neta/ventas_netas*100):.1f}% margen" if ventas_netas else None)

        st.markdown("---")

        def fila(label, valor, bold=False, color=None, indent=False):
            ind = "padding-left:2rem;" if indent else ""
            fw = "font-weight:700;" if bold else ""
            col = f"color:{color};" if color else ""
            neg = f"color:#ef4444;" if valor < 0 else ""
            return f"""
            <tr style="border-bottom:1px solid #f3f4f6">
                <td style="padding:0.5rem 1rem;{ind}{fw}{col}">{label}</td>
                <td style="text-align:right; padding:0.5rem 1rem;{fw}{neg}">S/ {valor:,.2f}</td>
            </tr>"""

        def subtotal(label, valor, color="#1a1f36"):
            return f"""
            <tr style="background:{color}20">
                <td style="padding:0.6rem 1rem; font-weight:700; color:{color}">{label}</td>
                <td style="text-align:right; padding:0.6rem 1rem; font-weight:700; color:{color}">S/ {valor:,.2f}</td>
            </tr>"""

        def separador():
            return '<tr><td colspan="2" style="padding:0; border-top:2px solid #e5e7eb"></td></tr>'

        filas_html = ""
        filas_html += '<tr style="background:#f3f4f6"><td colspan="2" style="padding:0.4rem 1rem; font-weight:600; color:#374151; font-size:0.8rem; text-transform:uppercase">INGRESOS</td></tr>'
        filas_html += fila(f"Ventas brutas", ventas_brutas, indent=True)
        if descuentos > 0:
            filas_html += fila(f"(-) Descuentos concedidos", -descuentos, indent=True)
        filas_html += subtotal("VENTAS NETAS", ventas_netas, "#2563eb")
        filas_html += separador()

        filas_html += '<tr style="background:#f3f4f6"><td colspan="2" style="padding:0.4rem 1rem; font-weight:600; color:#374151; font-size:0.8rem; text-transform:uppercase">COSTOS</td></tr>'
        filas_html += fila(f"(-) Costo de ventas", -costo_ventas, indent=True)
        filas_html += subtotal("UTILIDAD BRUTA", utilidad_bruta, "#10b981" if utilidad_bruta >= 0 else "#ef4444")
        filas_html += separador()

        filas_html += '<tr style="background:#f3f4f6"><td colspan="2" style="padding:0.4rem 1rem; font-weight:600; color:#374151; font-size:0.8rem; text-transform:uppercase">GASTOS OPERATIVOS</td></tr>'
        for _, g in gastos[gastos["codigo"].str.startswith(("62","63","65","68"))].iterrows():
            filas_html += fila(f"(-) {g['codigo']} - {g['nombre']}", -g["saldo"], indent=True)
        filas_html += subtotal("UTILIDAD OPERATIVA", utilidad_operativa, "#2563eb" if utilidad_operativa >= 0 else "#ef4444")
        filas_html += separador()

        if otros_ingresos != 0 or otros_gastos != 0:
            filas_html += '<tr style="background:#f3f4f6"><td colspan="2" style="padding:0.4rem 1rem; font-weight:600; color:#374151; font-size:0.8rem; text-transform:uppercase">OTROS INGRESOS / GASTOS</td></tr>'
            for _, i in ingresos[~ingresos["codigo"].str.startswith(("70","74"))].iterrows():
                filas_html += fila(f"(+) {i['codigo']} - {i['nombre']}", i["saldo"], indent=True)
            for _, g in gastos[gastos["codigo"].str.startswith(("66","67"))].iterrows():
                filas_html += fila(f"(-) {g['codigo']} - {g['nombre']}", -g["saldo"], indent=True)
            filas_html += subtotal("UTILIDAD ANTES DE IMPUESTOS", utilidad_antes_imp, "#2563eb")
            filas_html += separador()

        bg_un = "#10b981" if utilidad_neta >= 0 else "#ef4444"
        filas_html += f"""
        <tr style="background:{bg_un}; color:white">
            <td style="padding:0.8rem 1rem; font-size:1.1rem; font-weight:700">UTILIDAD NETA DEL EJERCICIO</td>
            <td style="text-align:right; padding:0.8rem 1rem; font-size:1.1rem; font-weight:700">S/ {utilidad_neta:,.2f}</td>
        </tr>"""

        st.markdown(f"""
        <div class="card">
        <h3 style="text-align:center; margin-bottom:0.2rem">ESTADO DE RESULTADOS</h3>
        <p style="text-align:center; color:#6b7280; margin-bottom:1rem">Del {fecha_ini} al {fecha_fin}</p>
        <table style="width:100%; border-collapse:collapse; font-size:0.9rem;">
            <tbody>{filas_html}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: ESTADO DE SITUACIÓN FINANCIERA
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🏦 Estado de Situación Financiera":
    st.title("🏦 Estado de Situación Financiera")

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

        # Resultado del período = Ingresos - Gastos
        ingresos_df = df[df["tipo"]=="INGRESO"]
        gastos_df   = df[df["tipo"]=="GASTO"]
        resultado   = ingresos_df["saldo"].sum() - gastos_df["saldo"].sum()

        # Activos corrientes (10,12,16,20,25) vs no corrientes (33,34,36,37,39)
        activos_corr = activos[activos["codigo"].str[:2].isin(["10","12","16","20","25","37"])]
        activos_nc   = activos[~activos["codigo"].str[:2].isin(["10","12","16","20","25","37"])]

        tot_ac  = activos_corr["saldo"].sum()
        tot_anc = activos_nc["saldo"].sum()
        tot_activo = tot_ac + tot_anc

        # Pasivos corrientes (40,41,42) vs no corrientes (45,46)
        pasivos_corr = pasivos[pasivos["codigo"].str[:2].isin(["40","41","42"])]
        pasivos_nc   = pasivos[~pasivos["codigo"].str[:2].isin(["40","41","42"])]

        tot_pc  = pasivos_corr["saldo"].sum()
        tot_pnc = pasivos_nc["saldo"].sum()
        tot_pasivo = tot_pc + tot_pnc

        tot_patrim = patrimonio["saldo"].sum() + resultado
        tot_pas_pat = tot_pasivo + tot_patrim

        # Métricas
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Activo", f"S/ {tot_activo:,.2f}")
        m2.metric("Total Pasivo", f"S/ {tot_pasivo:,.2f}")
        m3.metric("Total Patrimonio", f"S/ {tot_patrim:,.2f}")

        cuadra = round(tot_activo - tot_pas_pat, 2) == 0
        if cuadra:
            st.markdown('<div class="alert-ok">✅ Activo = Pasivo + Patrimonio ✓</div>', unsafe_allow_html=True)
        else:
            diff_esf = tot_activo - tot_pas_pat
            st.markdown(f'<div class="alert-err">❌ No cuadra. Diferencia: S/ {diff_esf:,.2f}</div>', unsafe_allow_html=True)

        st.markdown("---")

        def bloque(titulo, filas_df, total, color):
            html = f'<div style="margin-bottom:1.5rem"><div style="background:{color}; color:white; padding:0.5rem 1rem; border-radius:6px 6px 0 0; font-weight:700">{titulo}</div>'
            html += '<table style="width:100%; border-collapse:collapse; font-size:0.88rem;">'
            for _, r in filas_df.iterrows():
                html += f'<tr style="border-bottom:1px solid #f3f4f6"><td style="padding:0.4rem 1rem; color:#374151">{r["codigo"]} - {r["nombre"]}</td><td style="text-align:right; padding:0.4rem 1rem">S/ {r["saldo"]:,.2f}</td></tr>'
            html += f'<tr style="background:#f9fafb; font-weight:700"><td style="padding:0.5rem 1rem">TOTAL</td><td style="text-align:right; padding:0.5rem 1rem; color:{color}">S/ {total:,.2f}</td></tr>'
            html += '</table></div>'
            return html

        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<h3 style="text-align:center">ACTIVO</h3><p style="text-align:center; color:#6b7280; font-size:0.85rem">Al {fecha_corte}</p>', unsafe_allow_html=True)
            st.markdown(bloque("ACTIVO CORRIENTE", activos_corr, tot_ac, "#2563eb"), unsafe_allow_html=True)
            st.markdown(bloque("ACTIVO NO CORRIENTE", activos_nc, tot_anc, "#1d4ed8"), unsafe_allow_html=True)
            st.markdown(f'<div style="background:#1a1f36; color:white; padding:0.7rem 1rem; border-radius:6px; font-weight:700; font-size:1rem; display:flex; justify-content:space-between"><span>TOTAL ACTIVO</span><span>S/ {tot_activo:,.2f}</span></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_der:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<h3 style="text-align:center">PASIVO Y PATRIMONIO</h3><p style="text-align:center; color:#6b7280; font-size:0.85rem">Al {fecha_corte}</p>', unsafe_allow_html=True)
            st.markdown(bloque("PASIVO CORRIENTE", pasivos_corr, tot_pc, "#ef4444"), unsafe_allow_html=True)
            if not pasivos_nc.empty:
                st.markdown(bloque("PASIVO NO CORRIENTE", pasivos_nc, tot_pnc, "#dc2626"), unsafe_allow_html=True)
            st.markdown(f'<div style="background:#ef444420; border:1px solid #ef4444; border-radius:4px; padding:0.4rem 1rem; margin-bottom:0.5rem; font-weight:700; display:flex; justify-content:space-between"><span style="color:#ef4444">TOTAL PASIVO</span><span>S/ {tot_pasivo:,.2f}</span></div>', unsafe_allow_html=True)

            # Patrimonio
            st.markdown('<div style="background:#8b5cf6; color:white; padding:0.5rem 1rem; border-radius:6px 6px 0 0; font-weight:700">PATRIMONIO</div><table style="width:100%; border-collapse:collapse; font-size:0.88rem;">', unsafe_allow_html=True)
            patrim_html = ""
            for _, r in patrimonio.iterrows():
                patrim_html += f'<tr style="border-bottom:1px solid #f3f4f6"><td style="padding:0.4rem 1rem">{r["codigo"]} - {r["nombre"]}</td><td style="text-align:right; padding:0.4rem 1rem">S/ {r["saldo"]:,.2f}</td></tr>'
            patrim_html += f'<tr style="border-bottom:1px solid #f3f4f6"><td style="padding:0.4rem 1rem; font-style:italic">Resultado del ejercicio</td><td style="text-align:right; padding:0.4rem 1rem; color:{"#10b981" if resultado >= 0 else "#ef4444"}">S/ {resultado:,.2f}</td></tr>'
            patrim_html += f'<tr style="background:#f9fafb; font-weight:700"><td style="padding:0.5rem 1rem">TOTAL</td><td style="text-align:right; padding:0.5rem 1rem; color:#8b5cf6">S/ {tot_patrim:,.2f}</td></tr>'
            st.markdown(patrim_html + '</table>', unsafe_allow_html=True)

            st.markdown(f'<div style="background:#1a1f36; color:white; padding:0.7rem 1rem; border-radius:6px; font-weight:700; font-size:1rem; display:flex; justify-content:space-between; margin-top:0.5rem"><span>TOTAL PASIVO + PATRIMONIO</span><span>S/ {tot_pas_pat:,.2f}</span></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: PLAN DE CUENTAS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ Plan de Cuentas":
    st.title("⚙️ Plan de Cuentas")

    tab1, tab2 = st.tabs(["📋 Ver cuentas", "➕ Agregar cuenta"])

    with tab1:
        df = query("SELECT codigo as 'Código', nombre as 'Nombre', tipo as 'Tipo', naturaleza as 'Naturaleza' FROM cuentas ORDER BY codigo")
        color_tipo = {"ACTIVO":"🔵","PASIVO":"🔴","PATRIMONIO":"🟣","INGRESO":"🟢","GASTO":"🟡"}
        df["Tipo"] = df["Tipo"].apply(lambda x: f"{color_tipo.get(x,'')} {x}")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            nuevo_cod  = st.text_input("Código de cuenta", placeholder="Ej: 10, 42, 70")
            nuevo_nom  = st.text_input("Nombre de la cuenta", placeholder="Ej: Caja y Bancos")
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
        st.markdown('</div>', unsafe_allow_html=True)