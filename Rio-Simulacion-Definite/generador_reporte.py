# -*- coding: utf-8 -*-
"""
AQUASENTINEL AI - Monitoreo de calidad del agua (pH y turbidez)
- Integrado de forma compacta para el simulador interactivo de Godot 4.7.2.
- Interfaz gráfica integrada con Tkinter manteniendo intacta la lógica original.
"""

import csv
import io
import json
import os
import sys
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext

# CONFIGURACION ORIGINAL
LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
LMSTUDIO_MODELOS = "http://localhost:1234/v1/models"
MODELO_IA = "qwen2.5-3b-instruct"

PH_MIN_OPTIMO = 6.5
PH_MAX_OPTIMO = 9.0
TURBIDEZ_MAX_OPTIMA = 2.0
MAX_LINEAS_PROMPT = 15

lecturas_memoria = []

# LOGICA DE DESVIACION
def calcular_desviacion_anomala(lectura):
    parametro = str(lectura[2]).lower()
    valor = float(lectura[3])
    if parametro == "ph":
        if valor < PH_MIN_OPTIMO: return round(PH_MIN_OPTIMO - valor, 2)
        elif valor > PH_MAX_OPTIMO: return round(valor - PH_MAX_OPTIMO, 2)
    elif parametro == "turbidez":
        if valor > TURBIDEZ_MAX_OPTIMA: return round(valor - TURBIDEZ_MAX_OPTIMA, 2)
    return 0.0

# ENTRADA DE DATOS
def leer_entero(mensaje, minimo, maximo):
    numero = None
    while numero is None:
        entrada = input(mensaje).strip()
        if entrada.isdigit() and minimo <= int(entrada) <= maximo: numero = int(entrada)
        else: print(f"Ingrese un numero entero entre {minimo} y {maximo}.")
    return numero

def limpiar_ruta(ruta):
    return ruta.strip().strip('"').strip("'").strip()

def abrir_csv(ruta):
    if not os.path.exists(ruta):
        if os.path.exists(ruta + ".csv"): ruta = ruta + ".csv"
        else: return None
    for cod in ["utf-8-sig", "latin-1"]:
        try:
            with open(ruta, "r", encoding=cod) as archivo: return archivo.read()
        except (PermissionError, UnicodeDecodeError): continue
    return None

MESES = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

def clave_fecha(texto):
    try:
        partes = texto.strip().split()
        anio = int(partes[0])
        mes = MESES.get(partes[1].lower()[:3], 0)
        dia = int(partes[2])
        return (anio * 13 + mes) * 32 + dia
    except Exception: return 0

def valor_numerico(texto):
    try:
        n = float(texto.strip().lstrip("<>").strip().replace(",", "."))
        return n if n >= 0 else None
    except ValueError: return None

def cargar_formato_ancho(texto):
    filas = list(csv.reader(io.StringIO(texto, newline="")))
    if len(filas) < 2: return None
    col_ph, col_turb, col_sensor, col_ubic, col_fecha = -1, -1, 0, 1, -1
    for i, nom in enumerate(filas[0]):
        n = nom.lower().replace("\n", " ").strip()
        if n.startswith("ph"): col_ph = i
        elif "turbiedad" in n or "turbidez" in n: col_turb = i
        elif n.startswith("fuente"): col_ubic = i
        elif n.startswith("codigo"): col_sensor = i
        elif n.startswith("fecha"): col_fecha = i
    if col_ph == -1 and col_turb == -1: return None
    lecturas = []
    for f in filas[1:]:
        if len(f) <= max(col_ph, col_turb): continue
        for p, col in [("ph", col_ph), ("turbidez", col_turb)]:
            if col == -1: continue
            val = valor_numerico(f[col])
            if val is not None: lecturas.append([f[col_sensor], f[col_ubic], p, val, f[col_fecha] if col_fecha != -1 else ""])
    lecturas.sort(key=lambda l: clave_fecha(l[4]))
    return lecturas

def cargar_lecturas_archivo(ruta):
    texto = abrir_csv(limpiar_ruta(ruta))
    if not texto: return []
    res_ancho = cargar_formato_ancho(texto)
    if res_ancho is not None: return res_ancho
    filas = list(csv.reader(texto.splitlines(), delimiter=";" if ";" in texto.splitlines()[0] else ","))
    lecturas = []
    for f in filas:
        if len(f) < 4 or f[2].strip().lower() not in ["ph", "turbidez"]: continue
        val = valor_numerico(f[3])
        if val is not None: lecturas.append([f[0].strip(), f[1].strip(), f[2].strip().lower(), val, f[4].strip() if len(f) > 4 else ""])
    return lecturas

def capturar_lecturas_usuario():
    total = leer_entero("Cuantas lecturas va a ingresar?: ", 1, 500)
    lecturas = []
    for i in range(total):
        sid = input("ID Sensor: ").strip()
        ub = input("Ubicacion: ").strip()
        p = input("Parametro ('pH' o 'Turbidez'): ").strip().lower()
        v = float(input("Valor: ").replace(",", "."))
        lecturas.append([sid, ub, p, v, ""])
    return lecturas

# ALGORITMOS
def insertion_sort_alertas(lecturas_base):
    lista = [[l[0], l[1], l[2], l[3], calcular_desviacion_anomala(l)] for l in lecturas_base]
    for i in range(1, len(lista)):
        clave = lista[i]
        j = i - 1
        while j >= 0 and lista[j][4] < clave[4]:
            lista[j + 1] = lista[j]
            j -= 1
        lista[j + 1] = clave
    return lista

def evaluar_secuencia_critica_dp(lecturas, N, K):
    dp = [[0.0] * (K + 1) for _ in range(N + 1)]
    for i in range(1, N + 1):
        desv = calcular_desviacion_anomala(lecturas[i - 1])
        for j in range(1, K + 1):
            dp[i][j] = max(dp[i - 1][j], dp[i - 1][j - 1] + desv)
    indices = []
    i, j = N, K
    while i > 0 and j > 0:
        desv = calcular_desviacion_anomala(lecturas[i - 1])
        if desv > 0 and round(dp[i][j], 2) == round(dp[i - 1][j - 1] + desv, 2):
            indices.append(i - 1)
            j -= 1
        i -= 1
    indices.reverse()
    return dp[N][K], indices

# ESTADISTICAS
def pendiente_recta(valores):
    n = len(valores)
    if n < 2: return 0.0
    x_prom, y_prom = (n - 1) / 2.0, sum(valores) / n
    num = sum((i - x_prom) * (valores[i] - y_prom) for i in range(n))
    den = sum((i - x_prom) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0

def valores_de(lecturas, parametro):
    return [l[3] for l in lecturas if l[2] == parametro]

def estadisticas_parametro(lecturas, parametro):
    valores = valores_de(lecturas, parametro)
    if not valores: return f"Sin datos de {parametro}."
    fuera = sum(1 for l in lecturas if l[2] == parametro and calcular_desviacion_anomala(l) > 0)
    pend = pendiente_recta(valores)
    tend = "estable" if abs(pend) <= 0.01 else ("en aumento" if pend > 0 else "en descenso")
    return f"{parametro.upper()}: {len(valores)} lecturas, prom {round(sum(valores)/len(valores),2)}, {fuera} fuera de rango, tend: {tend}."

def nivel_riesgo(lecturas):
    fuera = sum(1 for l in lecturas if calcular_desviacion_anomala(l) > 0)
    mx = max([calcular_desviacion_anomala(l) for l in lecturas] or [0.0])
    pct = (fuera * 100.0 / len(lecturas)) if lecturas else 0.0
    if pct >= 50 or mx >= 3: return "CRITICO", pct, mx
    if pct >= 20 or mx >= 1.5: return "ALTO", pct, mx
    return ("MODERADO" if pct > 0 else "BAJO"), pct, mx

def mostrar_prediccion_local(lecturas):
    print("\n" + "-"*40 + "\n PREDICCION DE RIESGO LOCAL\n" + "-"*40)
    print(estadisticas_parametro(lecturas, "ph"))
    print(estadisticas_parametro(lecturas, "turbidez"))

# IA (LM STUDIO CONNECTOR)
def construir_prompt(lecturas):
    nivel, pct, mx = nivel_riesgo(lecturas)
    texto = f"DATOS CALIDAD DEL AGUA\nNivel Riesgo: {nivel} ({round(pct,1)}% anomalas, max desv {mx})\n"
    texto += estadisticas_parametro(lecturas, "ph") + "\n" + estadisticas_parametro(lecturas, "turbidez") + "\n\n"
    texto += "ALERTAS CRITICAS:\n"
    for obs in insertion_sort_alertas(lecturas)[:MAX_LINEAS_PROMPT]:
        if obs[4] > 0: texto += f"- Sensor {obs[0]} ({obs[1]}): {obs[2]}={obs[3]} (+{obs[4]})\n"
    return texto

def detectar_modelo():
    try:
        res = urllib.request.urlopen(LMSTUDIO_MODELOS, timeout=3)
        datos = json.loads(res.read().decode("utf-8"))
        res.close()
        return datos["data"][0]["id"]
    except Exception: return MODELO_IA

def consultar_ia(datos_texto):
    instrucciones = "Eres experto en calidad de agua. Responde en espanol con: 1. pH, 2. TURBIDEZ, 3. PREDICCIONES, 4. RECOMENDACIONES."
    cuerpo = {"model": detectar_modelo(), "messages": [{"role": "system", "content": instrucciones}, {"role": "user", "content": datos_texto}], "temperature": 0.3}
    req = urllib.request.Request(LMSTUDIO_URL, data=json.dumps(cuerpo).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        res = urllib.request.urlopen(req, timeout=30)
        datos = json.loads(res.read().decode("utf-8"))
        res.close()
        return datos["choices"][0]["message"]["content"]
    except Exception as e: return f"Error de red con LM Studio: {e}"

def analizar_con_ia(lecturas):
    print("\n--- ANALISIS CON IA (Qwen 2.5 3B Instruct) ---")
    prompt = construir_prompt(lecturas)

    print("\nDatos enviados al modelo:")
    print("-" * 70)
    print(prompt)
    print("-" * 70)
    print("Consultando al modelo local de LM Studio...")

    # Llamada directa a tu función de red urllib
    resultado = consultar_ia(prompt)

    if resultado is None:
        resultado = "Error: El servidor local de LM Studio no respondió. Asegúrate de presionar 'Start Server'."

    print("\n======================= REPORTE DE LA IA =======================")
    print(resultado)
    print("================================================================")

    # GUARDADO INMEDIATO Y SEGURO PARA EL SIMULADOR
    # Usar 'with open' fuerza a Windows a escribir y cerrar el archivo en el disco de inmediato
    with open("reporte_ia.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
        f.write("\n\n====================================================\n")
        f.write("=== ANALISIS DE LA IA ORIGINAL ===\n")
        f.write("====================================================\n\n")
        f.write(str(resultado))
        f.write("\n")
        
    print("[Python] Reporte físico escrito con éxito en el disco duro.")

def mostrar_alertas(lecturas):
    for obs in insertion_sort_alertas(lecturas): print(f"Sensor: {obs[0]} | {obs[2]}: {obs[3]} (Desv: {obs[4]})")

def mostrar_dp(lecturas):
    tot = len(lecturas)
    v = leer_entero(f"Ventana critica (1-{tot}): ", 1, tot)
    rmx, idxs = evaluar_secuencia_critica_dp(lecturas, tot, v)
    print(f"Desviacion Acumulada: {round(rmx, 2)}")

ARCHIVO_HISTORIAL = "historial_simulacion.json"

CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HISTORIAL = os.path.join(CARPETA_BASE, "historial_simulacion.json")
ARCHIVO_REPORTE = os.path.join(CARPETA_BASE, "reporte_ia.txt")

def cargar_historial_disco():
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_historial_disco(datos):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)

# PUENTE INTERACTIVO DE SLIDERS (GODOT)
def revisar_argumentos_godot():
    global lecturas_memoria
    lecturas_memoria = cargar_historial_disco()

    # 1. Orden de borrar desde Godot (índice 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "--limpiar":
        lecturas_memoria = []
        if os.path.exists(ARCHIVO_HISTORIAL):
            os.remove(ARCHIVO_HISTORIAL)
        return True

    # 2. Nuevos datos de los sliders (índices 1, 2 y 3)
    if len(sys.argv) >= 4:
        try:
            ph_godot = float(sys.argv[1])
            contaminacion_godot = float(sys.argv[2])
            turbidez_godot = float(sys.argv[3]) * 4.0
            
            num_muestra = (len(lecturas_memoria) // 2) + 1
            lecturas_memoria.append([f"MUESTRA_{num_muestra}", "Río Simulado", "ph", ph_godot, f"Toma {num_muestra}"])
            lecturas_memoria.append([f"MUESTRA_{num_muestra}", "Río Simulado", "turbidez", turbidez_godot, f"Toma {num_muestra}"])
            
            guardar_historial_disco(lecturas_memoria)
            
            # Si es guardado silencioso (índice 4), termina aquí
            if len(sys.argv) >= 5 and sys.argv[4] == "--solo-guardar":
                return True
                
            # Si es reporte final, consulta a la IA y guarda en la ruta exacta
            prompt = construir_prompt(lecturas_memoria)
            resultado = consultar_ia(prompt)
            if resultado is None:
                resultado = "Error: LM Studio no respondió. Verifica que el servidor local esté activo."
                
            with open(ARCHIVO_REPORTE, "w", encoding="utf-8") as f:
                f.write(prompt)
                f.write("\n\n=== ANALISIS DE LA IA ===\n\n")
                f.write(str(resultado) + "\n")
                
            return True
        except Exception as e:
            with open(ARCHIVO_REPORTE, "w", encoding="utf-8") as err:
                err.write(f"Error al procesar los datos: {e}")
            return True
            
    return False



# INTERFAZ GRAFICA (TKINTER) REEMPLAZANDO A LA CONSOLA
def iniciar_gui():
    global lecturas_memoria

    root = tk.Tk()
    root.title("AquaSentinel AI - Monitoreo de Calidad del Agua")
    root.geometry("850x650")
    root.minsize(700, 500)

    # Marco superior de acciones
    frame_botones = tk.Frame(root, padx=10, pady=10)
    frame_botones.pack(fill=tk.X)

    lbl_estado = tk.Label(root, text="Lecturas en memoria: 0", font=("Arial", 10, "bold"), fg="blue")
    lbl_estado.pack(anchor="w", padx=15)

    def actualizar_estado():
        lbl_estado.config(text=f"Lecturas en memoria: {len(lecturas_memoria)}")

    # Area de texto con scroll para mostrar salidas
    txt_salida = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
    txt_salida.pack(expand=True, fill=tk.BOTH, padx=15, pady=10)

    def escribir_consola(texto):
        txt_salida.insert(tk.END, texto + "\n")
        txt_salida.see(tk.END)

    # Funciones de los Botones conectadas a la lógica original
    def gui_cargar_csv():
        global lecturas_memoria
        ruta = filedialog.askopenfilename(title="Seleccionar archivo CSV", filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")])
        if ruta:
            lecturas_memoria = cargar_lecturas_archivo(ruta)
            actualizar_estado()
            escribir_consola(f"\n[CSV Cargado] Se cargaron {len(lecturas_memoria)} lecturas desde: {ruta}")

    def gui_manual():
        global lecturas_memoria
        total = simpledialog.askinteger("Entrada Manual", "Cuantas lecturas va a ingresar?", minvalue=1, maxvalue=500)
        if total:
            nuevas = []
            for i in range(total):
                sid = simpledialog.askstring("Entrada Manual", f"ID Sensor [{i+1}/{total}]:")
                if not sid: return
                ub = simpledialog.askstring("Entrada Manual", f"Ubicacion [{i+1}/{total}]:")
                if not ub: return
                p = simpledialog.askstring("Entrada Manual", f"Parametro ('pH' o 'Turbidez') [{i+1}/{total}]:").strip().lower()
                v_str = simpledialog.askstring("Entrada Manual", f"Valor numérico [{i+1}/{total}]:").replace(",", ".")
                try:
                    v = float(v_str)
                except ValueError:
                    messagebox.showerror("Error", "Valor numérico inválido.")
                    return
                nuevas.append([sid, ub, p, v, ""])
            lecturas_memoria = nuevas
            actualizar_estado()
            escribir_consola(f"\n[Manual] Se ingresaron {len(lecturas_memoria)} lecturas manualmente.")

    def gui_mostrar_alertas():
        if not lecturas_memoria:
            messagebox.showwarning("Aviso", "No hay lecturas cargadas en memoria.")
            return
        escribir_consola("\n=== ALERTAS (Insertion Sort) ===")
        for obs in insertion_sort_alertas(lecturas_memoria):
            escribir_consola(f"Sensor: {obs[0]} | {obs[2]}: {obs[3]} (Desv: {obs[4]})")

    def gui_prog_dinamica():
        if not lecturas_memoria:
            messagebox.showwarning("Aviso", "No hay lecturas cargadas en memoria.")
            return
        tot = len(lecturas_memoria)
        v = simpledialog.askinteger("Programación Dinámica", f"Ventana crítica (1-{tot}):", minvalue=1, maxvalue=tot)
        if v:
            rmx, idxs = evaluar_secuencia_critica_dp(lecturas_memoria, tot, v)
            escribir_consola(f"\n=== PROGRAMACION DINAMICA ===")
            escribir_consola(f"Ventana: {v} | Desviacion Acumulada Máxima: {round(rmx, 2)}")

    def gui_estadisticas():
        if not lecturas_memoria:
            messagebox.showwarning("Aviso", "No hay lecturas cargadas en memoria.")
            return
        escribir_consola("\n" + "-"*40 + "\n PREDICCION DE RIESGO LOCAL\n" + "-"*40)
        escribir_consola(estadisticas_parametro(lecturas_memoria, "ph"))
        escribir_consola(estadisticas_parametro(lecturas_memoria, "turbidez"))

    def gui_consultar_ia():
        if not lecturas_memoria:
            messagebox.showwarning("Aviso", "No hay lecturas cargadas en memoria.")
            return
        escribir_consola("\n--- CONSULTANDO A LA IA (LM Studio) ---")
        prompt = construir_prompt(lecturas_memoria)
        escribir_consola("Enviando datos al modelo local...")
        
        resultado = consultar_ia(prompt)
        if resultado is None:
            resultado = "Error: El servidor local de LM Studio no respondió."
            
        escribir_consola("\n======================= REPORTE DE LA IA =======================")
        escribir_consola(str(resultado))
        escribir_consola("================================================================")
        
        # Guardado físico igual que el original
        with open("reporte_ia.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
            f.write("\n\n====================================================\n")
            f.write("=== ANALISIS DE LA IA ORIGINAL ===\n")
            f.write("====================================================\n\n")
            f.write(str(resultado))
            f.write("\n")
        escribir_consola("[Python] Reporte físico escrito con éxito en el disco duro ('reporte_ia.txt').")

    # Botones de la Interfaz
    btn_csv = tk.Button(frame_botones, text="1. Cargar CSV", command=gui_cargar_csv, width=15, bg="#e1f5fe")
    btn_csv.grid(row=0, column=0, padx=5, pady=5)

    btn_manual = tk.Button(frame_botones, text="2. Manual", command=gui_manual, width=15, bg="#e1f5fe")
    btn_manual.grid(row=0, column=1, padx=5, pady=5)

    btn_alertas = tk.Button(frame_botones, text="3. Ver Alertas", command=gui_mostrar_alertas, width=15, bg="#e1f5fe")
    btn_alertas.grid(row=0, column=2, padx=5, pady=5)

    btn_dp = tk.Button(frame_botones, text="4. Prog. Dinámica", command=gui_prog_dinamica, width=15, bg="#e1f5fe")
    btn_dp.grid(row=0, column=3, padx=5, pady=5)

    btn_est = tk.Button(frame_botones, text="5. Estadísticas", command=gui_estadisticas, width=15, bg="#e1f5fe")
    btn_est.grid(row=1, column=0, padx=5, pady=5)

    btn_ia = tk.Button(frame_botones, text="6. Consultar IA", command=gui_consultar_ia, width=15, bg="#c8e6c9")
    btn_ia.grid(row=1, column=1, padx=5, pady=5)

    btn_salir = tk.Button(frame_botones, text="Salir", command=root.destroy, width=15, bg="#ffcdd2")
    btn_salir.grid(row=1, column=2, padx=5, pady=5)

    escribir_consola("=== AQUASENTINEL AI INICIADO ===")
    escribir_consola("Utiliza los botones superiores para interactuar con el sistema de análisis.")

    root.mainloop()

def main():
    # Si recibe cualquier argumento (viene de Godot), ejecuta en silencio y cierra
    if len(sys.argv) > 1:
        revisar_argumentos_godot()
        return
        
    # Solo abre la ventana gráfica si se abre el script manualmente sin argumentos
    iniciar_gui()

if __name__ == "__main__":
    try: 
        main()
    except (KeyboardInterrupt, EOFError): 
        pass
