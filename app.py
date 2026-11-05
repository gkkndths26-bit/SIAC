import streamlit as st
import pulp
import math
import time
from datetime import datetime
import pytz

# --- CONSTANTES GLOBALES ---
MAX_CAJAS = 16
MAX_PRE_ESCANERES = 7

factores_conversion = {
    "09:30": 0.92, "10:00": 0.92, "10:30": 1.32, "11:00": 1.32,
    "11:30": 1.44, "12:00": 1.44, "12:30": 1.74, "13:00": 1.74,
    "13:30": 1.82, "14:00": 1.82, "14:30": 1.92, "15:00": 1.92,
    "15:30": 2.01, "16:00": 2.01, "16:30": 1.81, "17:00": 1.81,
    "17:30": 1.85, "18:00": 1.85, "18:30": 2.20, "19:00": 2.20,
    "19:30": 2.10, "20:00": 2.10, "20:30": 5.05, "21:00": 5.05,
    "21:30": 5.05, "22:00": 5.05
}

# --- CONFIGURACIÓN DE PÁGINA Y CSS PERSONALIZADO ---
st.set_page_config(page_title="SIAC V2", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    [data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] { display: none !important; }
    p, li, label, .stMarkdown, .stText, span { font-size: 1.3rem !important; color: #333333 !important; }
    .subtitulo-centrado { text-align: center; font-size: 1.8rem !important; color: #004B87 !important; font-weight: 600; margin-top: 5px; padding-top: 0px; margin-bottom: 20px; }
    button[kind="primary"] { background-color: #D32F2F !important; border-color: #D32F2F !important; color: white !important; font-weight: bold !important; }
    .stProgress > div > div > div > div { background-color: #D32F2F !important; }
    .tarjeta-azul { background-color: #004B87; padding: 20px 10px; border-radius: 12px; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border: 1px solid #003366; margin-bottom: 10px; }
    .tarjeta-azul .numero-gigante { color: #ffffff !important; font-size: 4.5rem; font-weight: 900; line-height: 1; margin-bottom: 8px; }
    .tarjeta-azul .etiqueta-gigante { color: #e0e0e0 !important; font-size: 1.3rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- INTERFAZ: TÍTULOS ---
st.markdown("<h1 style='text-align: center; font-size: 7rem !important; color: #004B87 !important; font-weight: 900; margin-bottom: 0px; padding-bottom: 0px; line-height: 1;'>SIAC</h1>", unsafe_allow_html=True)
st.markdown("<h2 class='subtitulo-centrado'>Sistema Inteligente de Asignación de Cajas</h2>", unsafe_allow_html=True)
st.markdown("---")

# --- LÓGICA DE RELOJ DEL SISTEMA (AJUSTADO A ZONA HORARIA LOCAL) ---
zona_local = pytz.timezone('America/Mexico_City')
ahora = datetime.now(zona_local)
minuto_actual = ahora.minute
hora_actual = ahora.hour

# Redondear al próximo bloque de 30 minutos
if minuto_actual < 30:
    minuto_objetivo = "30"
    hora_objetivo = hora_actual
else:
    minuto_objetivo = "00"
    hora_objetivo = hora_actual + 1
    if hora_objetivo == 24:
        hora_objetivo = 0

hora_formateada = f"{hora_objetivo:02d}:{minuto_objetivo}"
lista_horas = list(factores_conversion.keys())

# Interceptar y pre-seleccionar la hora
if hora_formateada in lista_horas:
    indice_defecto = lista_horas.index(hora_formateada)
else:
    indice_defecto = 0 # Si abren el sistema de madrugada, selecciona el primer bloque por defecto

# --- INTERFAZ: CAPTURA DE PARÁMETROS ---
col1, col2 = st.columns(2)
with col1:
    hora_bloque = st.selectbox("Hora de cierre del bloque:", lista_horas, index=indice_defecto)
    D_puerta = st.number_input("Clientes reportados en puerta:", min_value=0, step=1, value=None, placeholder="Ej. 150")
with col2:
    E = st.number_input("Empleados disponibles en piso:", min_value=0, step=1, value=None, placeholder="Ej. 10")

# --- BOTÓN DE EJECUCIÓN ---
if st.button("CALCULAR ASIGNACIÓN", type="primary", use_container_width=True):
    
    if D_puerta is None or E is None or D_puerta == 0 or E == 0:
        st.warning("⚠️ Ingresa un número mayor a 0 en clientes y empleados para calcular.")
        st.stop()

    factor = factores_conversion[hora_bloque]
    D = math.ceil(D_puerta * factor)

    with st.spinner('Analizando variables operativas...'):
        time.sleep(1)
        
    # --- MOTOR MATEMÁTICO (PuLP) ---
    modelo = pulp.LpProblem("Optimizacion_Ideal", pulp.LpMaximize)

    X1 = pulp.LpVariable("Cajeros", lowBound=0, cat='Integer')
    X2 = pulp.LpVariable("Pre_escaners", lowBound=0, cat='Integer')
    T = pulp.LpVariable("Cuentas_Trad", lowBound=0, cat='Integer')
    P = pulp.LpVariable("Cuentas_Pre", lowBound=0, cat='Integer')

    modelo += P, "Maximizar_Cuentas_Preescaneadas"

    modelo += 60 * T + 45 * P <= 1440 * X1, "Tope_Tiempo_Cajas"
    modelo += 25 * P <= 1440 * X2, "Tope_Tiempo_Pasillo"
    modelo += T + P == D, "Absorcion_Total_Demanda"
    modelo += P >= 0.30 * D, "Meta_Corporativa"
    modelo += X1 + X2 <= E, "Limite_Empleados"
    modelo += X1 <= MAX_CAJAS, "Limite_Cajas"
    modelo += X2 <= MAX_PRE_ESCANERES, "Limite_Maquinas"
    modelo += P <= 0.50 * D, "Techo_Realista"
    modelo += X1 >= X2 + 2, "Bufer_Anti_Panico"
    modelo += X1 >= X2, "Prioridad_Cajas"

    modelo.solve(pulp.PULP_CBC_CMD(msg=0))
    estado = pulp.LpStatus[modelo.status]

    # --- RESULTADOS VISUALES ---
    st.markdown("---")
    
    if estado == "Optimal":
        cajeros = int(X1.varValue)
        escaners = int(X2.varValue)
        preescaneadas = int(P.varValue)
        sobrantes = E - (cajeros + escaners)
        porcentaje = (preescaneadas / D) * 100 if D > 0 else 0

        st.success(f"✅ ESTADO: ÓPTIMO | Meta corporativa alcanzable para los **{D} tickets** esperados.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{cajeros}</div><div class='etiqueta-gigante'>Cajas</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{escaners}</div><div class='etiqueta-gigante'>Escáneres</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{sobrantes}</div><div class='etiqueta-gigante'>Libres</div></div>", unsafe_allow_html=True)
        
        st.write("")
        st.progress(porcentaje / 100, text=f"Meta global proyectada: {porcentaje:.1f}%")

        st.markdown("### Metas Individuales")
        if escaners > 0:
            cuentas_por_empleado = preescaneadas // escaners
            minimo_30 = math.ceil((0.30 * D) / escaners)
            st.write(f"- **Objetivo por empleado:** ~{cuentas_por_empleado} carritos c/u")
            st.write(f"- **Mínimo indispensable (30%):** {minimo_30} carritos c/u")

    else:
        cajeros_base = min(E, MAX_CAJAS)
        escaners_A = min(E - cajeros_base, MAX_PRE_ESCANERES)

        if escaners_A <= 0 and E >= 4:
            cajeros_A = cajeros_base - 1
            escaners_A = 1
        else:
            cajeros_A = cajeros_base

        if cajeros_A >= 3:
            pre_A_potencial = escaners_A * 57
            tiempo_cajas_A = cajeros_A * 1440
            max_pre_cajas = int(tiempo_cajas_A / 45)
            techo_realista = int(0.50 * D)
            
            pre_A = min(pre_A_potencial, max_pre_cajas, techo_realista)
            tiempo_restante_A = tiempo_cajas_A - (pre_A * 45)
            trad_A = int(tiempo_restante_A / 60) if tiempo_restante_A > 0 else 0
            
            total_A = pre_A + trad_A
            porcentaje_A = (pre_A / D) * 100 if D > 0 else 0
        else:
            total_A = 0
            escaners_A = 0
            cajeros_A = 0

        cajeros_B = min(E, MAX_CAJAS)
        trad_B = int((cajeros_B * 1440) / 60)
        total_B = trad_B

        st.error("⚠️ DÉFICIT DETECTADO: La demanda supera la capacidad física. El 30% corporativo no es matemáticamente factible.")
        
        st.markdown("### Alternativas de Supervivencia")
        tab1, tab2 = st.tabs(["Opción A (Pasillo Activo)", "Opción B (Todos a cajas)"])
        
        with tab1:
            if total_A > 0:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{cajeros_A}</div><div class='etiqueta-gigante'>Cajas</div></div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{escaners_A}</div><div class='etiqueta-gigante'>Escáneres</div></div>", unsafe_allow_html=True)
                st.write("")
                st.write(f"- **Resultado:** Se procesarán {total_A} de {D} tickets.")
            else:
                st.write("Descartada por seguridad de fila.")
                
        with tab2:
            st.markdown(f"<div class='tarjeta-azul'><div class='numero-gigante'>{cajeros_B}</div><div class='etiqueta-gigante'>Cajas Totales</div></div>", unsafe_allow_html=True)
            st.write("")
            st.write(f"- **Resultado:** Se procesarán {total_B} de {D} tickets.")
