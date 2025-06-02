# app_pedidos.py — Versión fusionada y mejorada

import dash
from dash import dcc, html, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import datetime
import os
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import plotly.express as px

# === Rutas ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, "data", "PROYECTO_APP_CLIENTES.xlsx")
CSV_PATH = os.path.join(BASE_DIR, "data", "historial_pedidos.csv")
PDF_PREVIEW = os.path.join(BASE_DIR, "preview", "pedido_preview.pdf")
os.makedirs(os.path.dirname(PDF_PREVIEW), exist_ok=True)

# === Cargar datos ===
clientes_df = pd.read_excel(EXCEL_PATH, sheet_name="clientes")
clientes_df.columns = clientes_df.columns.str.strip()
articulos_df = pd.read_excel(EXCEL_PATH, sheet_name="articulos")
articulos_df.columns = articulos_df.columns.str.strip()
comerciales_df = pd.read_excel(EXCEL_PATH, sheet_name="comerciales")
stock_df = pd.read_excel(EXCEL_PATH, sheet_name="stock  por color")
stock_df.columns = stock_df.columns.str.strip()

clientes_options = [{"label": row["Nombre Comercial"], "value": row["Nombre Comercial"]} for _, row in clientes_df.iterrows() if pd.notna(row["Nombre Comercial"])]
comerciales_options = [{"label": str(c), "value": str(c)} for c in comerciales_df["comerciales"] if isinstance(c, str) and c.strip() != ""]
articulos_options = [{"label": f"{row['codigo']} - {row['articulos']}", "value": str(row['codigo'])} for _, row in articulos_df.dropna(subset=["codigo", "articulos"]).iterrows()]
colores_disponibles = sorted(stock_df["COLOR"].dropna().unique())

# === Usuarios y roles ===
USUARIOS = {
    "admin": {"clave": "admin123", "rol": "comercial"},
    "Marton2025": {"clave": "2525", "rol": "admin"}
}
session_user = {"activo": False, "usuario": None, "rol": None}

# === App Init ===
app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.SLATE])
app.title = "Pedidos Comerciales"

app.layout = html.Div([
    dcc.Location(id="url"),
    html.Div(id="page-content")
])

# === Login Layout ===
login_layout = dbc.Container([
    html.H2("Iniciar Sesión", className="text-center mt-5"),
    dbc.Row([
        dbc.Col([
            dbc.Input(id="username", placeholder="Usuario", type="text", className="mb-2"),
            dbc.Input(id="password", placeholder="Contraseña", type="password", className="mb-2"),
            dbc.Button("Entrar", id="login-btn", color="primary", className="w-100"),
            html.Div(id="login-alert", className="mt-2", style={"color": "red"})
        ], width=6)
    ], justify="center")
])

# === Sidebar ===
sidebar = dbc.Col(id="sidebar-content", width=2, className="bg-light p-3")

# === Protected Layout ===
protected_layout = dbc.Container([
    dbc.Row([
        sidebar,
        dbc.Col(html.Div(id="contenido_paginas"), width=10)
    ])
], fluid=True)

@app.callback(Output("sidebar-content", "children"), Input("url", "pathname"))
def mostrar_menu(path):
    if not session_user["activo"]:
        return ""
    
    link_style = {"color": "black", "fontWeight": "bold"}
    
    menu = [dbc.NavLink("Generar Pedido", href="/pedido", active="exact", style=link_style)]
    
    if session_user["rol"] == "admin":
        menu += [
            dbc.NavLink("Stock por Color", href="/stock", active="exact", style=link_style),
            dbc.NavLink("Historial", href="/historial", active="exact", style=link_style),
            dbc.NavLink("Dashboard", href="/dashboard", active="exact", style=link_style)
        ]
    
    menu.append(dbc.NavLink("Cerrar Sesión", href="/logout", active="exact", style=link_style))
    
    return [
        html.H4("Menú", className="text-center", style={"color": "black", "fontWeight": "bold"}),
        dbc.Nav(menu, vertical=True)
    ]

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(path):
    if path == "/" or path == "/logout":
        session_user.update({"activo": False, "usuario": None, "rol": None})
        return login_layout
    if not session_user["activo"]:
        return login_layout
    return protected_layout

@app.callback(
    Output("url", "pathname"), Output("login-alert", "children"),
    Input("login-btn", "n_clicks"), State("username", "value"), State("password", "value"),
    prevent_initial_call=True
)
def login(n, user, pwd):
    if user in USUARIOS and USUARIOS[user]["clave"] == pwd:
        session_user.update({"activo": True, "usuario": user, "rol": USUARIOS[user]["rol"]})
        return "/pedido", ""
    return dash.no_update, "Credenciales incorrectas."

# === Layouts ===
def layout_pedido():
    return dbc.Container([
        html.H3("Generar Pedido"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="cliente", options=clientes_options, placeholder="Selecciona cliente"), md=4),
            dbc.Col(dcc.Dropdown(id="comercial", options=comerciales_options, placeholder="Selecciona comercial"), md=4)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(dcc.Dropdown(id="perfil_selector", options=articulos_options, placeholder="Selecciona artículos", multi=True))
        ]),
        html.Div(id="tabla_articulos"),
        dbc.Button("📄 Generar PDF", id="generar_pdf", className="mt-3", color="primary"),
        html.Div(id="mensaje_validacion", className="mt-3", style={"color": "red"}),
        dcc.Download(id="descarga_pdf")
    ])

def layout_stock():
    series_options = sorted(stock_df["SERIE"].dropna().unique())
    color_options = sorted(stock_df["COLOR"].dropna().unique())
    return html.Div([
        dbc.Row([
            dbc.Col(dcc.Dropdown(options=[{"label": s, "value": s} for s in series_options], id="filtro_serie_stock", placeholder="Serie", multi=True), md=6),
            dbc.Col(dcc.Dropdown(options=[{"label": c, "value": c} for c in color_options], id="filtro_color", placeholder="Color", multi=True), md=6)
        ]),
        html.Div(id="tabla_stock")
    ])

def layout_historial():
    if not os.path.exists(CSV_PATH):
        return html.Div("Sin historial disponible.")
    df = pd.read_csv(CSV_PATH)
    if session_user["rol"] == "comercial":
        df = df[df["Comercial"] == session_user["usuario"]]
    return dbc.Table.from_dataframe(df.tail(20), striped=True, bordered=True, hover=True)

def layout_dashboard():
    if not os.path.exists(CSV_PATH):
        return html.Div("Sin datos de pedidos para análisis.")
    df = pd.read_csv(CSV_PATH)
    kpi1 = len(df)
    kpi2 = df["Color"].value_counts().idxmax() if not df.empty else "-"
    kpi3 = df["Código"].value_counts().idxmax() if not df.empty else "-"

    fig1 = px.histogram(df, x="Cliente", title="Pedidos por Cliente")
    fig2 = px.histogram(df, x="Color", title="Colores más Vendidos")
    fig3 = px.histogram(df, x="Código", title="Artículos más Pedidos")

    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("Total Pedidos"), dbc.CardBody(html.H4(kpi1))], color="info", inverse=True)),
            dbc.Col(dbc.Card([dbc.CardHeader("Color Más Vendido"), dbc.CardBody(html.H5(kpi2))], color="success", inverse=True)),
            dbc.Col(dbc.Card([dbc.CardHeader("Artículo Más Pedido"), dbc.CardBody(html.H5(kpi3))], color="warning", inverse=True))
        ], className="mb-4"),
        dcc.Graph(figure=fig1),
        dcc.Graph(figure=fig2),
        dcc.Graph(figure=fig3)
    ])

# === Routing de contenido ===
@app.callback(Output("contenido_paginas", "children"), Input("url", "pathname"))
def cambiar_contenido(path):
    if path == "/pedido":
        return layout_pedido()
    elif path == "/stock":
        return layout_stock()
    elif path == "/historial":
        return layout_historial()
    elif path == "/dashboard":
        return layout_dashboard()
    return "Página no encontrada."

# === Callbacks de funcionalidad ===
@app.callback(Output("tabla_stock", "children"), Input("filtro_serie_stock", "value"), Input("filtro_color", "value"))
def actualizar_tabla_stock(series, colores):
    df = stock_df.copy()
    if series:
        df = df[df["SERIE"].isin(series)]
    if colores:
        df = df[df["COLOR"].isin(colores)]
    return dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True) if not df.empty else html.Div("No hay resultados.")

@app.callback(Output("tabla_articulos", "children"), Input("perfil_selector", "value"))
def mostrar_tabla(perfiles):
    if not perfiles:
        return html.Div()
    filas = []
    for cod in perfiles:
        fila = articulos_df[articulos_df["codigo"].astype(str) == str(cod)].iloc[0]
        filas.append(html.Tr([
            html.Td(fila["codigo"]),
            html.Td(fila["articulos"]),
            html.Td(dcc.Input(
                type="number",
                min=1,
                step=1,
                id={"type": "cantidad", "index": str(cod)},
                placeholder="Cantidad"
            )),
            html.Td(dcc.Dropdown(
                options=[{"label": c, "value": c} for c in colores_disponibles],
                id={"type": "color", "index": str(cod)},
                placeholder="Color",
                style={"width": "180px", "fontWeight": "bold", "color": "black"}
            ))
        ]))
    return dbc.Table([
        html.Thead(html.Tr(["Código", "Artículo", "Cantidad", "Color"])),
        html.Tbody(filas)
    ], bordered=True)


@app.callback(
    Output("descarga_pdf", "data"),
    Output("mensaje_validacion", "children"),
    Input("generar_pdf", "n_clicks"),
    State("cliente", "value"),
    State("comercial", "value"),
    State("perfil_selector", "value"),
    State({"type": "cantidad", "index": ALL}, "value"),
    State({"type": "color", "index": ALL}, "value"),
    prevent_initial_call=True
)
def generar_pedido(n, cliente, comercial, codigos, cantidades, colores):
    if not cliente or not comercial or not codigos:
        return None, "⚠️ Selecciona cliente, comercial y artículos."
    if not cantidades or any(c is None or c <= 0 for c in cantidades):
        return None, "⚠️ Ingresa cantidad válida."
    if not colores or any(c is None or c == "" for c in colores):
        return None, "⚠️ Selecciona color."

    fecha_actual = datetime.datetime.now().strftime("%d/%m/%Y")
    pedidos = []
    for i, cod in enumerate(codigos):
        articulo = articulos_df[articulos_df["codigo"].astype(str) == str(cod)].iloc[0]["articulos"]
        pedidos.append([cod, articulo, cantidades[i], colores[i], cliente, comercial, fecha_actual])

    df_out = pd.DataFrame(pedidos, columns=["Código", "Artículo", "Cantidad", "Color", "Cliente", "Comercial", "Fecha"])
    if os.path.exists(CSV_PATH):
        df_hist = pd.read_csv(CSV_PATH)
        df_out = pd.concat([df_hist, df_out], ignore_index=True)
    df_out.to_csv(CSV_PATH, index=False)

        # Generar PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elems = []

    # 🧾 Título y datos del pedido
    elems.append(Paragraph("Resumen del Pedido", styles['Title']))
    elems.append(Spacer(1, 12))
    elems.append(Paragraph(f"<b>Cliente:</b> {cliente}", styles['Normal']))
    elems.append(Paragraph(f"<b>Comercial:</b> {comercial}", styles['Normal']))
    elems.append(Paragraph(f"<b>Fecha:</b> {fecha_actual}", styles['Normal']))
    elems.append(Spacer(1, 12))

    # Tabla de artículos
    data = [["Código", "Artículo", "Cantidad", "Color"]] + [
        [p[0], p[1], p[2], p[3]] for p in pedidos
    ]
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))

    elems.append(table)
    doc.build(elems)
    buffer.seek(0)

    return dcc.send_bytes(buffer.read(), filename="pedido.pdf"), "✅ Pedido generado correctamente."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)





