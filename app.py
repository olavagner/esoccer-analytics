# app.py — E-Soccer Fifa Analytics v6.5.8 (Dark Neon + HT/FT Radar + avg_pct fix)
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import re
import math
import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from collections import Counter
from io import BytesIO

from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER

import streamlit.components.v1 as components

if not hasattr(st, 'fragment'):
    def _fake_fragment(*args, **kwargs):
        def deco(fn): return fn
        return deco
    st.fragment = _fake_fragment

st.set_page_config(page_title="E-Soccer Fifa Analytics | FIFAlgorithm", page_icon="💀",
                   layout="wide", initial_sidebar_state="expanded")

if 'modo_claro' not in st.session_state: st.session_state.modo_claro = False
if 'som_ativo' not in st.session_state: st.session_state.som_ativo = True
if 'notif_alerta' not in st.session_state: st.session_state.notif_alerta = True
if 'ultima_oportunidade' not in st.session_state: st.session_state.ultima_oportunidade = set()
if 'page' not in st.session_state: st.session_state.page = 'jogos_dia'
if '_fetch_errors' not in st.session_state: st.session_state['_fetch_errors'] = []

N_SIMULATIONS = 5000
H2H_RECENCY = 0.85
H2H_MAX_WEIGHT = 0.70
H2H_FULL_TRUST_N = 10
HT_FACTOR = 0.45
SHRINKAGE_K = 6.0
DC_RHO = -0.10
DC_MAX_GOALS = 8
HT_OVER_25_THRESHOLD = 5.50
RADAR_GAMES = 10
ACEODDS_TIMEOUT = 45
ACEODDS_MAX_RETRIES = 3
FORM_GAMES = 5

SAFE_LINE_TABLE = [
    (6.70, 'Over 5.5', 'MUITA alta'), (5.70, 'Over 4.5', 'alta'),
    (4.50, 'Over 3.5', 'boa'), (3.45, 'Over 2.5', 'média'),
    (2.40, 'Over 1.5', 'baixa'), (2.00, 'Over 0.5', 'muito baixa'),
]

LEAGUES = {
    'Battle - 8 Min': {'id': '179369', 'icon': '🎮'},
    'Battle Volta - 6 Min': {'id': '179371', 'icon': '🎮'},
    'GT League – 12 Min': {'id': '179375', 'icon': '🎮'},
    'H2H GG - 8 Min': {'id': '179367', 'icon': '🎮'},
    'Adriatic - 10 Min': {'id': '179373', 'icon': '🎮'}
}

LEAGUE_NAME_MAP = {
    'E-Soccer - Battle - 8 minutos de jogo': 'Battle - 8 Min',
    'E-Soccer - H2H GG League - 8 minutos de jogo': 'H2H GG - 8 Min',
    'E-Soccer - Battle Volta - 6 minutos de jogo': 'Battle Volta - 6 Min',
    'E-Soccer - GT Leagues - 12 minutos de jogo': 'GT League – 12 Min',
    'E-Soccer - Adriatic - 10 minutos de jogo': 'Adriatic - 10 Min',
}

EXTRA_COLUMNS = [
    'Gols HT', 'Over 0.5 HT', 'Over 1.5 HT', 'Over 2.5 HT', 'BTTS HT',
    'Gols FT', 'Over 0.5 FT', 'Over 1.5 FT', 'Over 2.5 FT',
    'Over 3.5 FT', 'Over 4.5 FT', 'Over 5.5 FT', 'BTTS FT',
    'O1.5 Jogador', 'O2.5 Jogador',
    'xG Casa', 'xG Fora', 'Linha Seg FT', 'O2.5 HT?', 'Conf',
    'Prob Casa', 'Prob Empate', 'Prob Fora',
    'Rec HT', 'Prob Rec HT'
]


# ============================================
# CSS — DARK NEON THEME
# ============================================
def get_css(modo_claro=False):
    bg_card = "rgba(15,20,35,0.85)"
    bg_card2 = "rgba(20,25,45,0.65)"
    txt = "#f0f5ff"
    txt_dim = "#7a89a8"
    border = "rgba(0,229,255,0.22)"
    accent = "#00f5ff"
    accent2 = "#b537ff"
    accent3 = "#00ff88"
    accent4 = "#ff2e88"
    bg_gradient = ("radial-gradient(circle at 15% 0%, rgba(0,245,255,0.09), transparent 45%), "
                   "radial-gradient(circle at 85% 100%, rgba(181,55,255,0.09), transparent 45%), "
                   "radial-gradient(circle at 50% 50%, rgba(0,255,136,0.03), transparent 60%), #05070f")
    sidebar_bg = "linear-gradient(180deg, #070a14 0%, #05070f 100%)"
    sidebar_border = "rgba(0,245,255,0.18)"
    return f"""<style>
* {{ font-family: 'Inter', -apple-system, sans-serif; }}
.stApp {{ background: {bg_gradient}; }}

html, body {{ margin: 0 !important; padding: 0 !important; }}
.stApp {{ margin-top: 0 !important; padding-top: 0 !important; }}
[data-testid="stAppViewContainer"] {{ padding-top: 0 !important; margin-top: 0 !important; }}
[data-testid="stAppViewContainer"] > .main {{ padding-top: 0 !important; margin-top: 0 !important; }}
[data-testid="stAppViewContainer"] .main .block-container {{
    padding-top: 0 !important;
    margin-top: -30px !important;
    padding-bottom: 0.1rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
    max-width: 100% !important;
}}
[data-testid="stHeader"], .stApp > header, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
    display: none !important; height: 0 !important; min-height: 0 !important;
}}
section.main {{ padding-top: 0 !important; margin-top: 0 !important; }}
section.main > div:first-child {{ padding-top: 0 !important; margin-top: 0 !important; }}
[data-testid="stVerticalBlock"] {{ gap: 0.55rem !important; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ padding: 0 !important; }}
[data-testid="stVerticalBlock"] > div:first-child {{ margin-top: 0 !important; padding-top: 0 !important; }}
.main .block-container > div > [data-testid="stVerticalBlock"]:first-child > div:first-child {{
    margin-top: 0 !important; padding-top: 0 !important;
}}

.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {accent} 0%, {accent2} 100%) !important;
    border: none !important; color: #05070f !important;
    font-weight: 800 !important; border-radius: 8px !important;
    padding: 6px 14px !important; font-size: 12.5px !important;
    box-shadow: 0 0 22px rgba(0,245,255,0.45), 0 0 40px rgba(181,55,255,0.25) !important;
    transition: all 0.2s !important;
    height: 32px !important;
    min-height: 32px !important;
    letter-spacing: 0.3px;
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 0 32px rgba(0,245,255,0.7), 0 0 60px rgba(181,55,255,0.4) !important;
    transform: translateY(-1px);
}}
.stButton > button {{
    background: {bg_card2} !important;
    border: 1px solid {border} !important;
    color: {txt} !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    font-size: 12.5px !important;
    transition: all 0.2s !important;
    height: 32px !important;
    min-height: 32px !important;
}}
.stButton > button:hover {{
    border-color: {accent} !important;
    color: {accent} !important;
    box-shadow: 0 0 18px rgba(0,245,255,0.35) !important;
}}

.top-hero {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    margin-top: -15px !important;
    margin-bottom: 14px;
    background: linear-gradient(135deg, rgba(0,245,255,0.08) 0%, rgba(181,55,255,0.08) 100%);
    border: 1px solid rgba(0,245,255,0.35);
    border-radius: 12px;
    box-shadow: 0 0 30px rgba(0,245,255,0.15), inset 0 0 30px rgba(0,245,255,0.03);
}}
.top-hero-left {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
.top-hero-icon {{ font-size: 22px; flex-shrink: 0; filter: drop-shadow(0 0 10px rgba(0,245,255,0.6)); }}
.top-hero-title {{
    font-size: 15.5px; font-weight: 900; letter-spacing: -0.3px;
    color: {txt}; white-space: nowrap;
    text-shadow: 0 0 20px rgba(0,245,255,0.4);
}}
.top-hero-title b {{
    background: linear-gradient(135deg, {accent}, {accent2});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 900;
    filter: drop-shadow(0 0 12px rgba(0,245,255,0.5));
}}
.top-hero-sep {{ color: {txt_dim}; opacity: 0.5; font-weight: 600; margin: 0 2px; }}
.top-hero-dev {{ font-size: 12.5px; font-weight: 700; color: {accent}; white-space: nowrap;
                 text-shadow: 0 0 14px rgba(0,245,255,0.6); }}
.top-hero-right {{ display: flex; align-items: center; gap: 8px; flex-shrink: 0; }}

.pill-actions {{ margin-bottom: 14px; margin-top: 0; }}
.pill-actions .stButton > button {{
    background: linear-gradient(135deg, rgba(0,245,255,0.12), rgba(181,55,255,0.12)) !important;
    border: 1px solid rgba(0,245,255,0.45) !important;
    color: {accent} !important;
    border-radius: 100px !important;
    font-weight: 800 !important;
    padding: 6px 18px !important;
    font-size: 12.5px !important;
    height: 32px !important;
    transition: all 0.2s !important;
    text-shadow: 0 0 10px rgba(0,245,255,0.5);
}}
.pill-actions .stButton > button:hover {{
    background: linear-gradient(135deg, rgba(0,245,255,0.25), rgba(181,55,255,0.25)) !important;
    box-shadow: 0 0 24px rgba(0,245,255,0.5) !important;
    transform: translateY(-1px);
}}
.pill-actions .stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {accent} 0%, {accent2} 100%) !important;
    color: #05070f !important;
    border: none !important;
    box-shadow: 0 0 24px rgba(0,245,255,0.6), 0 0 50px rgba(181,55,255,0.35) !important;
}}

.stat-mini-row {{ display: flex; gap: 12px; margin-bottom: 14px; }}
.stat-mini {{
    position: relative;
    display: flex; align-items: center; gap: 14px;
    padding: 12px 18px;
    background: linear-gradient(135deg, rgba(0,245,255,0.06) 0%, rgba(181,55,255,0.04) 100%);
    border: 1px solid rgba(0,245,255,0.28);
    border-radius: 14px;
    flex: 1;
    box-shadow: 0 0 24px rgba(0,245,255,0.08), inset 0 0 20px rgba(0,245,255,0.04);
    transition: all 0.25s ease;
    overflow: hidden;
}}
.stat-mini::before {{
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, {accent}, {accent2});
    box-shadow: 0 0 15px {accent};
}}
.stat-mini:hover {{
    border-color: rgba(0,245,255,0.6);
    box-shadow: 0 0 36px rgba(0,245,255,0.2), inset 0 0 25px rgba(0,245,255,0.08);
    transform: translateY(-1px);
}}
.stat-mini .sm-icon {{
    font-size: 26px; flex-shrink: 0;
    width: 52px; height: 52px;
    border-radius: 12px;
    background: linear-gradient(135deg, rgba(0,245,255,0.18), rgba(181,55,255,0.15));
    border: 1px solid rgba(0,245,255,0.35);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 18px rgba(0,245,255,0.25), inset 0 0 15px rgba(0,245,255,0.06);
    filter: drop-shadow(0 0 8px rgba(0,245,255,0.5));
}}
.stat-mini .sm-info {{ display: flex; flex-direction: column; gap: 2px; min-width: 0; }}
.stat-mini .sm-lbl {{
    font-size: 10px; color: {txt_dim}; font-weight: 800;
    text-transform: uppercase; letter-spacing: 1.4px;
    text-shadow: 0 0 6px rgba(0,245,255,0.15);
}}
.stat-mini .sm-val {{
    font-size: 26px; font-weight: 900;
    background: linear-gradient(135deg, #FFFFFF, {accent});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-family: 'JetBrains Mono', 'Inter', monospace;
    line-height: 1.05; letter-spacing: -1px;
    filter: drop-shadow(0 0 12px rgba(0,245,255,0.6));
}}
.stat-mini .sm-val.time {{
    background: linear-gradient(135deg, #FFFFFF, {accent2});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 12px rgba(181,55,255,0.6));
}}

::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: linear-gradient(180deg, {accent}, {accent2}); border-radius: 4px;
                             box-shadow: 0 0 8px rgba(0,245,255,0.5); }}

[data-testid="stSidebar"] {{ background: {sidebar_bg} !important; border-right: 1px solid {sidebar_border}; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 0.5rem !important; }}

.sb-brand {{ display: flex; align-items: center; gap: 12px;
    padding: 14px 14px 18px 14px;
    border-bottom: 1px solid {sidebar_border}; margin-bottom: 10px; }}
.sb-logo {{ width: 40px; height: 40px; border-radius: 10px;
    background: linear-gradient(135deg, {accent}, {accent2});
    display: flex; align-items: center; justify-content: center; font-size: 20px;
    box-shadow: 0 0 24px rgba(0,245,255,0.5), 0 0 50px rgba(181,55,255,0.3); }}
.sb-brand-name {{ font-size: 14px; font-weight: 900;
    background: linear-gradient(135deg, {accent}, {accent2});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 10px rgba(0,245,255,0.5)); }}
.sb-brand-sub {{ font-size: 10.5px; color: {txt_dim}; margin-top: 2px; font-weight: 600; }}

.sb-section {{ font-size: 10px; font-weight: 800; text-transform: uppercase;
    letter-spacing: 1px; color: {txt_dim}; padding: 12px 14px 6px 14px; }}

[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important; border: none !important;
    color: {txt_dim} !important; border-radius: 8px !important;
    font-weight: 700 !important; padding: 10px 14px !important;
    font-size: 13.5px !important; text-align: left !important;
    justify-content: flex-start !important; transition: all 0.15s !important;
    margin-bottom: 2px !important; height: auto !important;
    min-height: auto !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(0,245,255,0.1) !important; color: {accent} !important;
    text-shadow: 0 0 10px rgba(0,245,255,0.6);
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: rgba(0,245,255,0.14) !important; color: {accent} !important;
    border-left: 3px solid {accent} !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: 0 0 20px rgba(0,245,255,0.25) !important;
    text-shadow: 0 0 10px rgba(0,245,255,0.6);
}}

.sb-footer {{ padding: 12px 14px; border-top: 1px solid {sidebar_border};
    margin-top: 16px; font-size: 11px; color: {txt_dim}; }}
.sb-footer-user {{ display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: 8px;
    background: rgba(0,245,255,0.05); border: 1px solid {sidebar_border}; margin-top: 8px; }}
.sb-avatar {{ width: 28px; height: 28px; border-radius: 50%;
    background: linear-gradient(135deg, {accent}, {accent2});
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 900; color: #05070f;
    box-shadow: 0 0 16px rgba(0,245,255,0.5); }}

.methodology-badge {{
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 11px; font-weight: 800; padding: 6px 16px;
    border-radius: 100px;
    background: linear-gradient(135deg, rgba(0,245,255,0.15), rgba(181,55,255,0.15));
    border: 1px solid rgba(0,245,255,0.6);
    color: #00f5ff;
    letter-spacing: 0.5px;
    box-shadow: 0 0 25px rgba(0,245,255,0.4), inset 0 0 15px rgba(0,245,255,0.1);
    white-space: nowrap;
    text-shadow: 0 0 10px rgba(0,245,255,0.8);
    overflow: hidden;
    text-overflow: ellipsis;
}}
.methodology-badge .icon {{
    font-size: 14px;
    filter: drop-shadow(0 0 6px #00f5ff);
}}

.status-dot {{ display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 100px;
    background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.4);
    font-size: 11px; font-weight: 800; color: {accent3};
    white-space: nowrap;
    text-shadow: 0 0 10px rgba(0,255,136,0.6); }}
.status-dot .dot {{ width: 6px; height: 6px; border-radius: 50%; background: {accent3};
    box-shadow: 0 0 12px {accent3}; animation: pulse 2s infinite; }}
@keyframes pulse {{ 0%,100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.5; transform: scale(1.2); }} }}

.warning-banner {{
    background: linear-gradient(90deg, rgba(255,214,0,0.15), rgba(255,140,0,0.08));
    padding: 12px 18px;
    border-radius: 10px;
    border-left: 4px solid #ffd600;
    color: {txt};
    font-size: 13.5px;
    margin: 10px 0 14px 0;
    box-shadow: 0 0 24px rgba(255,214,0,0.15);
}}
.warning-banner b {{ color: #ffd600; }}
.warning-banner code {{
    background: rgba(0,0,0,0.4);
    padding: 1px 6px;
    border-radius: 4px;
    color: {accent};
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
}}

div[data-baseweb="select"] > div {{ background: {bg_card2} !important; border: 1px solid {border} !important;
    border-radius: 8px !important; color: {txt} !important; min-height: 32px !important;
    font-size: 12.5px !important; }}
div[data-baseweb="select"] svg {{ fill: {accent} !important; }}
div[data-baseweb="input"] input {{ background: {bg_card2} !important; border: 1px solid {border} !important;
    border-radius: 8px !important; color: {txt} !important; font-size: 12.5px !important;
    padding: 6px 12px !important; min-height: 32px !important; }}

.mc-list {{ display: flex; flex-direction: column; gap: 5px; margin-top: 4px; }}

.mc-header-row,
.mc-row {{
    display: grid;
    grid-template-columns: 80px 380px 140px 130px 135px minmax(260px, 1.7fr);
    gap: 8px;
    align-items: stretch;
}}

.mc-header-row {{
    padding: 7px 10px;
    background: linear-gradient(135deg, rgba(0,245,255,0.1), rgba(181,55,255,0.06));
    border: 1px solid rgba(0,245,255,0.5);
    border-radius: 10px;
    margin-bottom: 2px;
    box-shadow: 0 0 20px rgba(0,245,255,0.15);
}}
.mc-hcell {{
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: {accent};
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2px 6px;
    text-shadow: 0 0 10px rgba(0,245,255,0.6);
}}

.mc-row {{
    padding: 7px 10px;
    background: {bg_card};
    border: 1px solid {border};
    border-radius: 10px;
    transition: all 0.15s;
}}
.mc-row:hover {{
    border-color: rgba(0,245,255,0.55);
    box-shadow: 0 0 24px rgba(0,245,255,0.2);
}}
.mc-row > * {{ min-width: 0; }}

.mc-box {{
    background: rgba(0,245,255,0.04);
    border: 1px solid rgba(0,245,255,0.32);
    border-radius: 10px;
    padding: 6px 10px;
    min-height: 62px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 3px;
    box-shadow: inset 0 0 15px rgba(0,245,255,0.05);
    transition: all 0.15s;
    box-sizing: border-box;
    overflow: hidden;
}}
.mc-box:hover {{
    border-color: rgba(0,245,255,0.7);
    box-shadow: inset 0 0 22px rgba(0,245,255,0.1), 0 0 20px rgba(0,245,255,0.15);
}}

.mc-hora-block {{ align-items: center; text-align: center; }}
.mc-hora-block .h {{
    font-size: 16px; font-weight: 900; color: {txt};
    font-family: 'JetBrains Mono', monospace; line-height: 1;
    letter-spacing: -0.5px;
    text-shadow: 0 0 12px rgba(0,245,255,0.4);
}}
.mc-hora-block .l {{
    font-size: 8px; color: {txt_dim}; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 100%;
}}

.mc-teams-box {{
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 10px;
    white-space: nowrap;
    overflow: hidden;
    text-align: center;
    padding: 0 10px;
}}

.mc-team-side {{
    display: flex;
    align-items: center;
    min-width: 0;
    flex: 1;
}}
.mc-team-side.left {{ justify-content: flex-end; }}
.mc-team-side.right {{ justify-content: flex-start; }}

.mc-team-side .name {{
    font-size: 15px;
    font-weight: 900;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    letter-spacing: 0.5px;
    min-width: 0;
}}

.mc-team-side.left .name {{
    background: linear-gradient(135deg, #FFFFFF, #00F5FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 10px rgba(0, 245, 255, 0.6));
}}

.mc-team-side.right .name {{
    background: linear-gradient(135deg, #FFFFFF, #B537FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 10px rgba(181, 55, 255, 0.6));
}}

.mc-vs {{
    font-size: 11px;
    font-weight: 900;
    color: #64748B;
    letter-spacing: 1px;
    padding: 3px 8px;
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
}}

.mc-media {{ align-items: center; justify-content: center; }}
.mc-media .vals {{
    display: flex; align-items: center; gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
}}
.mc-media .ht {{ font-weight: 700; color: #c77dff; text-shadow: 0 0 10px rgba(199,125,255,0.5); }}
.mc-media .ft {{ font-weight: 900; color: {accent}; text-shadow: 0 0 12px rgba(0,245,255,0.5); }}
.mc-media .sep {{ color: {txt_dim}; opacity: 0.4; font-weight: 600; }}

.mc-status {{
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 4px;
}}
.mc-status .top {{
    font-size: 16px; font-weight: 900;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.3px;
    line-height: 1.15;
    text-shadow: 0 0 14px currentColor;
}}
.mc-status .sub {{
    font-size: 11px; font-weight: 900;
    text-transform: uppercase; letter-spacing: 0.6px;
    opacity: 0.95;
    text-shadow: 0 0 10px currentColor;
}}

.mc-player-box {{ gap: 6px; }}
.mc-player-box .phdr {{
    font-size: 11px; color: {accent}; font-weight: 900;
    text-transform: uppercase; letter-spacing: 1.1px; text-align: center;
    padding-bottom: 4px; margin: 0;
    border-bottom: 1px solid rgba(0,245,255,0.22);
    text-shadow: 0 0 10px rgba(0,245,255,0.5);
}}
.mc-pnames {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    margin: 0;
}}
.mc-pnames .pn {{
    font-size: 13.5px; font-weight: 900;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    text-align: center; letter-spacing: -0.2px; line-height: 1.15;
}}
.mc-pstats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
.mc-pcol {{ display: flex; flex-direction: column; gap: 3px; }}
.mc-pstat {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 5px; font-size: 11.5px; line-height: 1.25;
}}
.mc-pstat .lbl {{ color: {txt_dim}; font-weight: 700;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 11px; }}
.mc-pstat .val {{ font-weight: 900;
    font-family: 'JetBrains Mono', monospace; font-size: 13.5px; flex-shrink: 0;
    text-shadow: 0 0 10px currentColor; }}

.streamlit-expanderHeader, details > summary {{
    background: rgba(20,25,45,0.5) !important;
    border: 1px solid {border} !important;
    border-radius: 8px !important;
    padding: 4px 10px !important;
    color: {txt_dim} !important;
    font-size: 11px !important; font-weight: 700 !important;
    cursor: pointer !important; margin: 2px 0 !important;
    list-style: none !important;
}}
.streamlit-expanderHeader:hover, details > summary:hover {{
    border-color: {accent} !important; color: {accent} !important;
    box-shadow: 0 0 16px rgba(0,245,255,0.2) !important;
}}
details[open] > summary {{
    border-color: {accent} !important; color: {accent} !important;
    background: rgba(0,245,255,0.08) !important; margin-bottom: 8px !important;
    box-shadow: 0 0 16px rgba(0,245,255,0.2) !important;
}}
details[open] > summary svg {{ color: {accent} !important; fill: {accent} !important; }}

.section-label {{ font-size: 12px; font-weight: 900; text-transform: uppercase;
    letter-spacing: 1.2px; color: {accent}; margin: 14px 0 10px 0;
    display: flex; align-items: center; gap: 8px;
    text-shadow: 0 0 12px rgba(0,245,255,0.5); }}
.section-label::before {{ content: ''; width: 3px; height: 14px;
    background: linear-gradient(180deg, {accent}, {accent2}); border-radius: 2px;
    box-shadow: 0 0 10px {accent}; }}

.pbar {{ height: 8px; background: rgba(0,245,255,0.06); border-radius: 100px;
    overflow: hidden; margin-top: 6px; }}
.pbar > div {{ height: 100%; border-radius: 100px; }}
.prog-row {{ display: grid; grid-template-columns: 70px 75px 1fr; gap: 14px;
    align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(0,245,255,0.06); }}
.prog-lbl {{ font-size: 14px; font-weight: 700; color: {txt};
    font-family: 'JetBrains Mono', monospace; }}
.prog-val {{ font-size: 14px; font-weight: 800; font-family: 'JetBrains Mono', monospace;
    text-shadow: 0 0 8px currentColor; }}

.insight-box {{ background: linear-gradient(90deg, rgba(255,214,0,0.1) 0%, rgba(255,214,0,0.02) 100%);
    padding: 12px 16px; border-radius: 10px; border-left: 3px solid #ffd600;
    font-size: 14px; margin-top: 10px; color: {txt}; line-height: 1.7;
    box-shadow: 0 0 20px rgba(255,214,0,0.1); }}

[data-testid="stDataFrame"] {{ background: {bg_card2}; border-radius: 12px; border: 1px solid {border}; }}
.stAlert {{ background: {bg_card2} !important; border-radius: 10px !important;
    border: 1px solid {border} !important; font-size: 13px !important;
    padding: 6px 12px !important; }}
.stat-card {{ background: {bg_card2}; padding: 14px 12px; border-radius: 10px;
    border: 1px solid {border}; text-align: center; }}
.stat-card .sc-icon {{ font-size: 22px; }}
.stat-card .sc-val {{ font-size: 24px; font-weight: 900; margin-top: 4px;
    color: {accent}; font-family: 'JetBrains Mono', monospace;
    text-shadow: 0 0 14px rgba(0,245,255,0.5); }}
.stat-card .sc-label {{ font-size: 10.5px; color: {txt_dim}; text-transform: uppercase;
    letter-spacing: 1px; margin-top: 4px; font-weight: 700; }}

.league-card {{ padding: 14px 18px; margin: 8px 0; border-radius: 12px;
    background: {bg_card2}; border: 1px solid {border}; border-left: 3px solid {accent};
    box-shadow: 0 0 20px rgba(0,245,255,0.08); }}
.league-card-best {{
    padding: 18px 22px; margin: 10px 0 16px 0; border-radius: 14px;
    background: linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,245,255,0.08) 100%);
    border: 2px solid rgba(0,255,136,0.55);
    box-shadow: 0 0 40px rgba(0,255,136,0.35), inset 0 0 40px rgba(0,255,136,0.08);
    position: relative;
    overflow: hidden;
    animation: glow-best 2.5s ease-in-out infinite alternate;
}}
@keyframes glow-best {{
    0% {{ box-shadow: 0 0 40px rgba(0,255,136,0.35), inset 0 0 40px rgba(0,255,136,0.08); }}
    100% {{ box-shadow: 0 0 60px rgba(0,255,136,0.6), inset 0 0 50px rgba(0,255,136,0.15); }}
}}
.league-card-best::before {{
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,255,136,0.15), transparent);
    animation: shine 3s infinite;
}}
@keyframes shine {{
    0% {{ left: -100%; }}
    100% {{ left: 100%; }}
}}
.best-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 14px; border-radius: 100px;
    background: linear-gradient(135deg, #00ff88, #00cc6a);
    color: #05070f;
    font-size: 11px; font-weight: 900;
    letter-spacing: 0.6px; text-transform: uppercase;
    box-shadow: 0 0 20px rgba(0,255,136,0.6);
    animation: badge-pulse 2s ease-in-out infinite;
}}
@keyframes badge-pulse {{
    0%,100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.05); }}
}}
.best-reason {{
    margin-top: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    background: rgba(0,255,136,0.08);
    border-left: 3px solid #00ff88;
    font-size: 13px;
    line-height: 1.6;
    color: {txt};
}}
.best-reason b {{ color: #00ff88; text-shadow: 0 0 10px rgba(0,255,136,0.6); }}
.best-reason .hl {{ color: {accent}; font-weight: 800; text-shadow: 0 0 10px rgba(0,245,255,0.5); }}

.thermometer {{ height: 6px; border-radius: 100px; background: rgba(0,245,255,0.08);
    margin-top: 8px; overflow: hidden; border: 1px solid {border}; }}
.thermometer > div {{ height: 100%; background: linear-gradient(90deg, {accent2}, {accent});
    box-shadow: 0 0 12px {accent}; }}
.badge-ofensivo {{ background: linear-gradient(135deg, #00ff88, #00cc6a); color: #05070f;
    padding: 4px 12px; border-radius: 100px; font-size: 10.5px; font-weight: 900;
    box-shadow: 0 0 15px rgba(0,255,136,0.5); }}
.badge-equilibrado {{ background: linear-gradient(135deg, {accent}, #0099cc); color: #05070f;
    padding: 4px 12px; border-radius: 100px; font-size: 10.5px; font-weight: 900;
    box-shadow: 0 0 15px rgba(0,245,255,0.5); }}
.badge-defensivo {{ background: linear-gradient(135deg, {accent2}, #7c3aed); color: #fff;
    padding: 4px 12px; border-radius: 100px; font-size: 10.5px; font-weight: 900;
    box-shadow: 0 0 15px rgba(181,55,255,0.5); }}

.badge-ht-heavy {{ 
    background: linear-gradient(135deg, #ff8c00, #ff2e88); 
    color: #fff; padding: 4px 12px; border-radius: 100px; 
    font-size: 10.5px; font-weight: 900; 
    box-shadow: 0 0 15px rgba(255,140,0,0.5); 
}}
.badge-ft-heavy {{ 
    background: linear-gradient(135deg, #00f5ff, #0099cc); 
    color: #05070f; padding: 4px 12px; border-radius: 100px; 
    font-size: 10.5px; font-weight: 900; 
    box-shadow: 0 0 15px rgba(0,245,255,0.5); 
}}
.badge-balanced {{ 
    background: linear-gradient(135deg, #7a89a8, #4a5568); 
    color: #fff; padding: 4px 12px; border-radius: 100px; 
    font-size: 10.5px; font-weight: 900; 
    box-shadow: 0 0 15px rgba(122,137,168,0.5); 
}}
.dual-bar {{ 
    display: flex; height: 8px; border-radius: 100px; 
    overflow: hidden; margin-top: 10px; 
    border: 1px solid rgba(255,255,255,0.1); 
    background: rgba(0,0,0,0.3);
}}
.dual-bar .ht {{ 
    background: linear-gradient(90deg, #ff8c00, #ff2e88); 
    box-shadow: 0 0 10px rgba(255,140,0,0.5);
}}
.dual-bar .ft {{ 
    background: linear-gradient(90deg, #00f5ff, #b537ff); 
    box-shadow: 0 0 10px rgba(0,245,255,0.5);
}}

#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}

.top-actions-row {{ display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }}
</style>"""

st.markdown(get_css(st.session_state.modo_claro), unsafe_allow_html=True)


# ============================================
# HELPERS
# ============================================
def safe_int(v, default=0):
    try:
        if v is None or v == '': return default
        if isinstance(v, float) and math.isnan(v): return default
        return int(v)
    except (ValueError, TypeError):
        return default


def get_safe_over_line_ft(g):
    if g is None or g == '': return '', ''
    try:
        g = float(g)
    except:
        return '', ''
    for m, l, lb in SAFE_LINE_TABLE:
        if g >= m: return l, lb
    return 'Sem Over', 'muito baixa'


def is_over_25_ht_safe(g):
    if g is None or g == '': return False
    try:
        return float(g) >= HT_OVER_25_THRESHOLD
    except:
        return False


def parse_pct(v):
    try:
        return float(str(v).replace('%', '').strip())
    except:
        return 0.0


def normalize_league_name(n):
    if not n: return n
    x = n.strip()
    if x in LEAGUE_NAME_MAP: return LEAGUE_NAME_MAP[x]
    for f, s in LEAGUE_NAME_MAP.items():
        if f in x or x in f: return s
    return x


def find_league_key(n, ld):
    if not n: return None
    norm = n.replace('–', '-').replace('—', '-').strip().lower()
    for k in ld.keys():
        kk = k.replace('–', '-').replace('—', '-').strip().lower()
        if kk == norm: return k
    for k in ld.keys():
        kk = k.replace('–', '-').replace('—', '-').strip().lower()
        if norm in kk or kk in norm: return k
    return None


def extract_alias(n):
    if not n: return ''
    s = str(n).strip()
    m = re.search(r'\(([^)]+)\)', s)
    return m.group(1).strip() if m else s


def pbar_color(pct):
    if pct >= 75: return '#00ff88'
    if pct >= 60: return '#ffd600'
    if pct >= 45: return '#ff8c00'
    return '#ff4444'


def team_color(name):
    colors = ['#00f5ff', '#b537ff', '#00ff88', '#ffd600', '#ff8c00',
              '#ff2e88', '#ec4899', '#3b82f6', '#14b8a6', '#f59e0b']
    h = sum(ord(c) for c in str(name))
    return colors[h % len(colors)]


def team_initial(name):
    s = str(name).strip()
    if not s: return '?'
    parts = re.split(r'[\s_\-]+', s)
    if len(parts) >= 2 and parts[0] and parts[1]:
        return (parts[0][0] + parts[1][0]).upper()
    return s[:2].upper()


# ============================================
# ANÁLISE
# ============================================
def build_league_counters(ad):
    cs = {}
    for ln, ldf in ad.items():
        if ldf is None or ldf.empty: continue
        c = Counter()
        for _, r in ldf.iterrows():
            h = str(r.get('home_team', '')).strip().lower()
            a = str(r.get('away_team', '')).strip().lower()
            if h: c[h] += 1
            if a: c[a] += 1
        cs[ln] = c
    return cs


def compute_jc_jf(df, ad, ld):
    cs = build_league_counters(ad)
    jc_l, jf_l = [], []
    for _, r in df.iterrows():
        lk = find_league_key(r.get('competicao', ''), ld)
        jc = jf = 0
        if lk and lk in cs:
            c = cs[lk]
            jc = c.get(str(r.get('casa', '')).strip().lower(), 0)
            jf = c.get(str(r.get('fora', '')).strip().lower(), 0)
        jc_l.append(jc);
        jf_l.append(jf)
    return jc_l, jf_l


def get_league_avg(ldf):
    if ldf is None or ldf.empty: return None
    t = ldf['home_score'].sum() + ldf['away_score'].sum()
    n = 2 * len(ldf)
    if n == 0: return None
    af = t / n
    ht = ldf.dropna(subset=['ht_home', 'ht_away'])
    ah = (ht['ht_home'].sum() + ht['ht_away'].sum()) / (2 * len(ht)) if len(ht) > 0 else af * HT_FACTOR
    return {'ataque_ft': af, 'defesa_ft': af, 'ataque_ht': ah, 'defesa_ht': ah}


def get_team_stats(ldf, team):
    if ldf is None or ldf.empty: return None
    tl = str(team).strip().lower()
    if not tl: return None
    tg = ldf[(ldf['home_team'].str.lower() == tl) | (ldf['away_team'].str.lower() == tl)]
    if tg.empty: return None
    fs, fc, hs, hc = [], [], [], []
    o25 = bt = 0;
    gl = []
    for _, g in tg.iterrows():
        is_h = str(g['home_team']).strip().lower() == tl
        a = safe_int(g.get('home_score'));
        b = safe_int(g.get('away_score'))
        hth = g.get('ht_home');
        hta = g.get('ht_away')
        if is_h:
            fs.append(a);
            fc.append(b)
            if hth is not None and hta is not None:
                hs.append(safe_int(hth));
                hc.append(safe_int(hta))
        else:
            fs.append(b);
            fc.append(a)
            if hth is not None and hta is not None:
                hs.append(safe_int(hta));
                hc.append(safe_int(hth))
        tg_t = a + b;
        gl.append(tg_t)
        if tg_t > 2.5: o25 += 1
        if a > 0 and b > 0: bt += 1
    nf = len(fs);
    nh = len(hs)
    if nf == 0: return None
    ak = sum(fs) / nf;
    df = sum(fc) / nf
    ah = (sum(hs) / nh) if nh > 0 else ak * HT_FACTOR
    dh = (sum(hc) / nh) if nh > 0 else df * HT_FACTOR
    va = float(np.var(fs)) if nf > 1 else 0
    vd = float(np.var(fc)) if nf > 1 else 0
    liga = get_league_avg(ldf)
    if liga:
        k = SHRINKAGE_K
        ak = (ak * nf + liga['ataque_ft'] * k) / (nf + k)
        df = (df * nf + liga['defesa_ft'] * k) / (nf + k)
        ah = (ah * nf + liga['ataque_ht'] * k) / (nf + k)
        dh = (dh * nf + liga['defesa_ht'] * k) / (nf + k)
    media = ak + df
    perfil = 'OFENSIVO' if media >= 4.5 else ('EQUILIBRADO' if media >= 3.5 else 'DEFENSIVO')
    return {'ataque_ft': ak, 'defesa_ft': df, 'ataque_ht': ah, 'defesa_ht': dh,
            'n_ft': nf, 'n_ht': nh, 'var_atk_ft': va, 'var_def_ft': vd,
            'over_25_pct': o25 / nf, 'btts_pct': bt / nf, 'perfil': perfil,
            'total_goals_list': gl, 'media_gols_jogos': media}


def compute_team_form(ldf, team, n=FORM_GAMES):
    if ldf is None or ldf.empty: return []
    tl = str(team).strip().lower()
    tg = ldf[(ldf['home_team'].str.lower() == tl) | (ldf['away_team'].str.lower() == tl)].copy()
    if tg.empty: return []
    if 'datetime_obj' in tg.columns and not tg['datetime_obj'].isna().all():
        tg = tg.sort_values('datetime_obj', ascending=False)
    results = []
    for _, g in tg.head(n).iterrows():
        is_h = str(g['home_team']).strip().lower() == tl
        a = safe_int(g.get('home_score'));
        b = safe_int(g.get('away_score'))
        my = a if is_h else b;
        opp = b if is_h else a
        if my > opp:
            results.append('V')
        elif my < opp:
            results.append('D')
        else:
            results.append('E')
    return results


def compute_team_over_under(ldf, team):
    if ldf is None or ldf.empty: return {}
    tl = str(team).strip().lower()
    tg = ldf[(ldf['home_team'].str.lower() == tl) | (ldf['away_team'].str.lower() == tl)]
    if tg.empty: return {}
    gs = []
    for _, g in tg.iterrows():
        is_h = str(g['home_team']).strip().lower() == tl
        gs.append(safe_int(g.get('home_score')) if is_h else safe_int(g.get('away_score')))
    n = len(gs)
    if n == 0: return {}
    return {
        '1.5': sum(1 for g in gs if g >= 2) / n,
        '2.5': sum(1 for g in gs if g >= 3) / n,
        '3.5': sum(1 for g in gs if g >= 4) / n,
        '4.5': sum(1 for g in gs if g >= 5) / n,
        '5.5': sum(1 for g in gs if g >= 6) / n,
    }


def compute_h2h_details(ldf, pa_n, pb_n):
    if ldf is None or ldf.empty: return None
    pa = str(pa_n).strip().lower();
    pb = str(pb_n).strip().lower()
    if not pa or not pb: return None
    h2h = ldf[((ldf['home_team'].str.lower() == pa) & (ldf['away_team'].str.lower() == pb)) |
              ((ldf['home_team'].str.lower() == pb) & (ldf['away_team'].str.lower() == pa))].reset_index(drop=True)
    if h2h.empty: return None
    a_f, b_f, a_h, b_h, w = [], [], [], [], []
    o05 = o15 = o25 = o35 = o45 = o55 = bt = 0
    va = vb = emp = 0
    o05h = o15h = o25h = bth = 0
    nh = 0
    for i, (_, g) in enumerate(h2h.iterrows()):
        ww = H2H_RECENCY ** i;
        w.append(ww)
        is_h = str(g['home_team']).strip().lower() == pa
        if is_h:
            af = safe_int(g.get('home_score'));
            bf = safe_int(g.get('away_score'))
            ah = g.get('ht_home');
            bh = g.get('ht_away')
        else:
            af = safe_int(g.get('away_score'));
            bf = safe_int(g.get('home_score'))
            ah = g.get('ht_away');
            bh = g.get('ht_home')
        a_f.append(af);
        b_f.append(bf);
        a_h.append(ah);
        b_h.append(bh)
        t = af + bf
        if t > 0.5: o05 += 1
        if t > 1.5: o15 += 1
        if t > 2.5: o25 += 1
        if t > 3.5: o35 += 1
        if t > 4.5: o45 += 1
        if t > 5.5: o55 += 1
        if af > 0 and bf > 0: bt += 1
        if af > bf:
            va += 1
        elif bf > af:
            vb += 1
        else:
            emp += 1
        if ah is not None and bh is not None:
            ah_i = safe_int(ah);
            bh_i = safe_int(bh);
            nh += 1
            th = ah_i + bh_i
            if th > 0.5: o05h += 1
            if th > 1.5: o15h += 1
            if th > 2.5: o25h += 1
            if ah_i > 0 and bh_i > 0: bth += 1
    n = len(h2h);
    tw = sum(w)
    la = sum(v * ww for v, ww in zip(a_f, w)) / tw if tw else 0
    lb = sum(v * ww for v, ww in zip(b_f, w)) / tw if tw else 0
    mf = (sum(a_f) + sum(b_f)) / n if n else 0
    perfil = 'OFENSIVO' if mf >= 4.5 else ('EQUILIBRADO' if mf >= 3.0 else 'DEFENSIVO')
    mh = 0
    if nh > 0:
        mh = sum((safe_int(a_h[i]) + safe_int(b_h[i])) for i in range(n)
                 if a_h[i] is not None and b_h[i] is not None) / nh
    return {'n': n, 'lambda_a': la, 'lambda_b': lb, 'media_gols_h2h': mf,
            'media_ft': mf, 'media_ht': mh,
            'over_05': o05 / n if n else 0, 'over_15': o15 / n if n else 0,
            'over_25': o25 / n if n else 0, 'over_35': o35 / n if n else 0,
            'over_45': o45 / n if n else 0, 'over_55': o55 / n if n else 0,
            'btts': bt / n if n else 0,
            'over_05_ht': o05h / nh if nh else 0, 'over_15_ht': o15h / nh if nh else 0,
            'over_25_ht': o25h / nh if nh else 0, 'btts_ht': bth / nh if nh else 0,
            'vitorias_a': va, 'vitorias_b': vb, 'empates': emp, 'perfil_h2h': perfil}


def estimate_lambdas(ldf, casa, fora):
    sc = get_team_stats(ldf, casa);
    sf = get_team_stats(ldf, fora)
    if not sc or not sf: return None
    if sc['n_ft'] == 0 or sf['n_ft'] == 0: return None
    lcf_f = (sc['ataque_ft'] + sf['defesa_ft']) / 2
    lff_f = (sf['ataque_ft'] + sc['defesa_ft']) / 2
    lch_f = (sc['ataque_ht'] + sf['defesa_ht']) / 2
    lfh_f = (sf['ataque_ht'] + sc['defesa_ht']) / 2
    h2h = compute_h2h_details(ldf, casa, fora)
    nh = 0
    if h2h:
        nh = h2h['n']
        ph = min(nh / H2H_FULL_TRUST_N, H2H_MAX_WEIGHT)
        pf = 1 - ph
        lcf = ph * h2h['lambda_a'] + pf * lcf_f
        lff = ph * h2h['lambda_b'] + pf * lff_f
        lch, lfh = lch_f, lfh_f
    else:
        lcf, lff, lch, lfh = lcf_f, lff_f, lch_f, lfh_f
    av = (sc['var_atk_ft'] + sf['var_atk_ft'] + sc['var_def_ft'] + sf['var_def_ft']) / 4
    ns = min(nh, 8) / 8 * 30 + min(min(sc['n_ft'], sf['n_ft']), 15) / 15 * 30
    cs = max(0, 1 - min(av / 4.0, 1)) * 40
    conf = int(min(ns + cs, 100))
    em = "🟢" if conf >= 70 else ("🟡" if conf >= 45 else "🔴")
    return {'lam_casa_ft': lcf, 'lam_fora_ft': lff, 'lam_casa_ht': lch, 'lam_fora_ht': lfh,
            'conf_score': conf, 'conf_emoji': em}


def poisson_pmf(lam, mx):
    ks = np.arange(mx + 1)
    f = np.array([math.factorial(int(k)) for k in ks], dtype=float)
    lam = max(lam, 1e-9)
    return np.exp(-lam) * np.power(lam, ks) / f


def dc_tau(i, j, lam, mu, rho=DC_RHO):
    if i == 0 and j == 0: return 1 - lam * mu * rho
    if i == 0 and j == 1: return 1 + lam * rho
    if i == 1 and j == 0: return 1 + mu * rho
    if i == 1 and j == 1: return 1 - rho
    return 1.0


def build_dc(lam, mu, mx=DC_MAX_GOALS):
    pl = poisson_pmf(lam, mx);
    pm = poisson_pmf(mu, mx)
    m = np.outer(pl, pm)
    for i in range(min(2, mx + 1)):
        for j in range(min(2, mx + 1)):
            m[i, j] *= dc_tau(i, j, lam, mu)
    m = np.clip(m, 0, None)
    s = m.sum()
    if s > 0: m /= s
    return m


def sample_dc(lam, mu, ns, rng, mx=DC_MAX_GOALS):
    m = build_dc(lam, mu, mx);
    flat = m.flatten()
    idx = rng.choice(len(flat), size=ns, p=flat)
    return idx // (mx + 1), idx % (mx + 1)


def compute_1x2_probs(ldf, casa, fora):
    lam = estimate_lambdas(ldf, casa, fora)
    if not lam: return (0.33, 0.33, 0.34)
    lcf = lam['lam_casa_ft'];
    lff = lam['lam_fora_ft']
    if lcf <= 0 or lff <= 0: return (0.33, 0.33, 0.34)
    m = build_dc(lcf, lff, mx=8)
    p_home = p_draw = p_away = 0
    for i in range(9):
        for j in range(9):
            if i > j:
                p_home += m[i, j]
            elif i == j:
                p_draw += m[i, j]
            else:
                p_away += m[i, j]
    return (p_home, p_draw, p_away)


def compute_top_scores(ldf, pa, pb, top_n=3):
    lam = estimate_lambdas(ldf, pa.strip().lower(), pb.strip().lower())
    if not lam: return []
    lcf = lam['lam_casa_ft'];
    lff = lam['lam_fora_ft']
    if lcf <= 0 or lff <= 0: return []
    m = build_dc(lcf, lff, mx=6)
    flat = []
    for i in range(7):
        for j in range(7):
            flat.append((i, j, float(m[i, j])))
    flat.sort(key=lambda x: -x[2])
    return [(f"{i}-{j}", p) for i, j, p in flat[:top_n]]


def compute_top3_tips(row, ldf, casa, fora):
    tips = []
    top_scores = compute_top_scores(ldf, casa, fora, top_n=1)
    if top_scores:
        sc, prob = top_scores[0]
        tips.append({'icon': '🎲', 'label': 'PLACAR PROVÁVEL', 'value': sc,
                     'detail': f"{prob * 100:.1f}% de chance", 'color': '#00f5ff'})
    linha_seg = row.get('Linha Seg FT', '')
    gols_ft = row.get('Gols FT', '-')
    if linha_seg and linha_seg != 'Sem Over':
        pct_map = {
            'Over 5.5': row.get('Over 5.5 FT', '-'), 'Over 4.5': row.get('Over 4.5 FT', '-'),
            'Over 3.5': row.get('Over 3.5 FT', '-'), 'Over 2.5': row.get('Over 2.5 FT', '-'),
            'Over 1.5': row.get('Over 1.5 FT', '-'), 'Over 0.5': row.get('Over 0.5 FT', '-'),
        }
        pct = pct_map.get(linha_seg, '-')
        tips.append({'icon': '🔥', 'label': 'APOSTAR', 'value': linha_seg,
                     'detail': f"{pct} │ média {gols_ft}", 'color': '#00ff88'})
    o25ht = row.get('O2.5 HT?', '')
    pct_o25ht = row.get('Over 2.5 HT', '-')
    if o25ht == '✅':
        tips.append({'icon': '⏱️', 'label': 'OVER 2.5 HT', 'value': 'INDICADO',
                     'detail': f"{pct_o25ht} na 1ª etapa", 'color': '#b537ff'})
    else:
        btts_val = parse_pct(row.get('BTTS FT', '0%'))
        if btts_val >= 55:
            tips.append({'icon': '👥', 'label': 'BTTS FT', 'value': row.get('BTTS FT', '-'),
                         'detail': 'Ambas marcam', 'color': '#ffd600'})
        else:
            tips.append({'icon': '⚽', 'label': 'OVER 3.5 FT', 'value': row.get('Over 3.5 FT', '-'),
                         'detail': f"média {gols_ft}", 'color': '#ff8c00'})
    return tips


def generate_pdf(df, title="E-Soccer — Jogos do Dia"):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=0.4 * cm, rightMargin=0.4 * cm,
                            topMargin=0.8 * cm, bottomMargin=0.6 * cm)
    els = [];
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Title'], fontSize=14, spaceAfter=4)
    ss = ParagraphStyle('S', parent=styles['Normal'], fontSize=8, textColor=rl_colors.grey)
    els.append(Paragraph(title, ts))
    els.append(Paragraph(f"FIFAlgorithm │ {datetime.now().strftime('%d/%m/%Y %H:%M')} │ {len(df)} jogos", ss))
    els.append(Spacer(1, 6))
    header = [str(c) for c in df.columns];
    data = [header]
    for _, r in df.iterrows():
        data.append([str(v) if v is not None else '' for v in r.values])
    nc = len(df.columns);
    avail = 28.5 * cm;
    cw = [avail / nc] * nc
    table = Table(data, colWidths=cw, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0099cc')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 6), ('FONTSIZE', (0, 1), (-1, -1), 5.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, rl_colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f8f9fa')])]))
    els.append(table);
    doc.build(els)
    return buf.getvalue()


def monte_carlo(df, ad, ld, ns=N_SIMULATIONS, seed=42):
    rng = np.random.default_rng(seed)
    out = {c: [] for c in EXTRA_COLUMNS}
    for idx, r in df.iterrows():
        lk = find_league_key(r.get('competicao', ''), ld)
        casa = str(r.get('casa', '')).strip().lower()
        fora = str(r.get('fora', '')).strip().lower()
        res = {c: '' for c in EXTRA_COLUMNS}
        if lk and lk in ad:
            ldf = ad[lk]
            try:
                lam = estimate_lambdas(ldf, casa, fora)
                if lam:
                    lcf, lff = lam['lam_casa_ft'], lam['lam_fora_ft']
                    lch, lfh = lam['lam_casa_ht'], lam['lam_fora_ht']
                    if lcf > 0 and lff > 0:
                        gc, gf = sample_dc(lcf, lff, ns, rng);
                        t = gc + gf
                        res['xG Casa'] = round(float(lcf), 2)
                        res['xG Fora'] = round(float(lff), 2)
                        gm = round(float(t.mean()), 2)
                        res['Gols FT'] = gm
                        res['Over 0.5 FT'] = f"{(t > 0.5).mean() * 100:.1f}%"
                        res['Over 1.5 FT'] = f"{(t > 1.5).mean() * 100:.1f}%"
                        res['Over 2.5 FT'] = f"{(t > 2.5).mean() * 100:.1f}%"
                        res['Over 3.5 FT'] = f"{(t > 3.5).mean() * 100:.1f}%"
                        res['Over 4.5 FT'] = f"{(t > 4.5).mean() * 100:.1f}%"
                        res['Over 5.5 FT'] = f"{(t > 5.5).mean() * 100:.1f}%"
                        res['BTTS FT'] = f"{((gc > 0) & (gf > 0)).mean() * 100:.1f}%"
                        res['O1.5 Jogador'] = f"{((gc >= 2) | (gf >= 2)).mean() * 100:.1f}%"
                        res['O2.5 Jogador'] = f"{((gc >= 3) | (gf >= 3)).mean() * 100:.1f}%"
                        ln, _ = get_safe_over_line_ft(gm)
                        res['Linha Seg FT'] = ln
                        p_h, p_d, p_a = compute_1x2_probs(ldf, casa, fora)
                        res['Prob Casa'] = f"{p_h * 100:.0f}%"
                        res['Prob Empate'] = f"{p_d * 100:.0f}%"
                        res['Prob Fora'] = f"{p_a * 100:.0f}%"
                    if lch and lfh and lch > 0 and lfh > 0:
                        gch, gfh = sample_dc(lch, lfh, ns, rng);
                        th = gch + gfh
                        p_o25ht = (th > 2.5).mean() * 100
                        p_o15ht = (th > 1.5).mean() * 100
                        p_o05ht = (th > 0.5).mean() * 100

                        res['Gols HT'] = round(float(th.mean()), 2)
                        res['Over 0.5 HT'] = f"{p_o05ht:.1f}%"
                        res['Over 1.5 HT'] = f"{p_o15ht:.1f}%"
                        res['Over 2.5 HT'] = f"{p_o25ht:.1f}%"
                        res['BTTS HT'] = f"{((gch > 0) & (gfh > 0)).mean() * 100:.1f}%"

                        if p_o25ht >= 65:
                            res['Rec HT'] = 'Over 2.5 HT'
                            res['Prob Rec HT'] = f"{p_o25ht:.0f}%"
                            res['O2.5 HT?'] = '✅'
                        elif p_o15ht >= 75:
                            res['Rec HT'] = 'Over 1.5 HT'
                            res['Prob Rec HT'] = f"{p_o15ht:.0f}%"
                            res['O2.5 HT?'] = '❌'
                        elif p_o05ht >= 85:
                            res['Rec HT'] = 'Over 0.5 HT'
                            res['Prob Rec HT'] = f"{p_o05ht:.0f}%"
                            res['O2.5 HT?'] = '❌'
                        else:
                            res['Rec HT'] = 'Evitar HT'
                            res['Prob Rec HT'] = '-'
                            res['O2.5 HT?'] = '❌'
                    res['Conf'] = f"{lam['conf_emoji']} {lam['conf_score']}"
            except Exception:
                pass
        for c in EXTRA_COLUMNS: out[c].append(res[c])
    return out


# ============================================
# SCRAPERS
# ============================================
class EFootballScraper:
    def __init__(self):
        self.base_url = "https://24live.com/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://24live.com/pt/',
            'Origin': 'https://24live.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })

    def get_league_matches(self, sid, max_retries=3, timeout=30):
        url = f"{self.base_url}/match-list-data/105"
        now = datetime.now()
        st_ = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        en = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        params = {
            'lang': 'pt', 'type': 'all', 'subtournamentIds': str(sid),
            'sort': 'alpha', 'short': 0,
            'from': st_.strftime('%Y-%m-%d %H:%M:%S'),
            'to': en.strftime('%Y-%m-%d %H:%M:%S'),
            'defaultSubtournamentLimit': 1000, 'orderBy': 'desc'
        }
        last_err = None
        for attempt in range(max_retries):
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code in (429, 503):
                    time.sleep(2 ** attempt)
                    continue
                else:
                    last_err = f"HTTP {r.status_code}"
                    time.sleep(1 + attempt)
                    continue
            except requests.exceptions.ReadTimeout:
                last_err = "Read timeout"
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                last_err = "Connection error"
                time.sleep(2 ** attempt)
            except Exception as e:
                last_err = str(e)
                time.sleep(1)
        if '_fetch_errors' not in st.session_state:
            st.session_state['_fetch_errors'] = []
        st.session_state['_fetch_errors'].append(f"{sid}: {last_err}")
        return []

    def extract(self, data):
        out = []
        today = datetime.now().strftime('%d/%m')
        total = ended = mt = 0;
        sm = []
        for m in data:
            total += 1
            cs = m.get('code_state', 'unknown')
            if cs != 'ended': continue
            ended += 1
            p = m.get('participants', [])
            h = next((x for x in p if x.get('type') == 'home_team'), {})
            a = next((x for x in p if x.get('type') == 'away_team'), {})
            sc = m.get('score', {});
            periods = sc.get('periods', [])
            hth = hta = None
            for per in periods:
                if per.get('period') == 1:
                    hth = per.get('home_team');
                    hta = per.get('away_team');
                    break
            hth = safe_int(hth, None) if hth is not None else None
            hta = safe_int(hta, None) if hta is not None else None
            sd = m.get('start_date', '');
            ds = ts = '';
            dl = None
            if sd:
                try:
                    x = sd[:-1] if sd.endswith('Z') else sd
                    x = x.replace('+00:00', '')
                    dt = datetime.fromisoformat(x);
                    dl = dt - timedelta(hours=3)
                    ds = dl.strftime('%d/%m');
                    ts = dl.strftime('%H:%M')
                except:
                    ds = sd[:10] if len(sd) >= 10 else ''
                    ts = sd[11:16] if len(sd) >= 16 else ''
            if len(sm) < 8: sm.append(f"{ds} {ts} ({cs})")
            if ds != today: continue
            mt += 1
            out.append({'id': m.get('id'), 'status': cs, 'date': ds, 'time': ts,
                        'start_date': sd, 'datetime_obj': dl,
                        'home_team': extract_alias(h.get('name', 'N/A')),
                        'away_team': extract_alias(a.get('name', 'N/A')),
                        'home_team_full': h.get('name', 'N/A'),
                        'away_team_full': a.get('name', 'N/A'),
                        'home_score': safe_int(sc.get('home_team')),
                        'away_score': safe_int(sc.get('away_team')),
                        'ht_home': hth, 'ht_away': hta,
                        'winner': m.get('winner', 0),
                        'tournament': m.get('tournament_name', 'N/A'),
                        'category': m.get('category_name', 'N/A')})
        self.last_debug = {'total': total, 'ended': ended, 'matched_today': mt,
                           'today_str': today, 'sample_dates': sm}
        return out


def test_24live_connectivity():
    try:
        r = requests.get("https://24live.com/", timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return r.status_code == 200, f"HTTP {r.status_code}"
    except requests.exceptions.ReadTimeout:
        return False, "Timeout — site lento ou bloqueando"
    except requests.exceptions.ConnectionError:
        return False, "Sem conexão — verifique internet/firewall"
    except Exception as e:
        return False, str(e)


def scrape_aceodds(max_retries=ACEODDS_MAX_RETRIES, timeout=ACEODDS_TIMEOUT):
    url = "https://www.aceodds.com/pt/bet365-transmissao-ao-vivo/futebol.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8', 'Upgrade-Insecure-Requests': '1',
    }
    if 'aceodds_session' not in st.session_state:
        sess = requests.Session();
        sess.headers.update(headers)
        st.session_state['aceodds_session'] = sess
    sess = st.session_state['aceodds_session']
    r = None
    for attempt in range(max_retries):
        try:
            with st.spinner(f"Conectando AceOdds... ({attempt + 1}/{max_retries})"):
                r = sess.get(url, timeout=timeout);
                r.raise_for_status();
                break
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError):
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt);
                continue
            else:
                if 'aceodds_games' in st.session_state and st.session_state['aceodds_games']:
                    return st.session_state['aceodds_games']
                return []
        except Exception:
            return st.session_state.get('aceodds_games', [])
    if r is None: return st.session_state.get('aceodds_games', [])
    try:
        soup = BeautifulSoup(r.text, 'html.parser');
        jogos = []
        for row in soup.find_all('tr'):
            rt = row.get_text(" ", strip=True)
            if 'E-Soccer' not in rt: continue
            cells = row.find_all('td')
            if len(cells) < 3: continue
            ct = [c.get_text(" ", strip=True) for c in cells]
            hora = casa = fora = comp = status = ''
            for c in ct:
                cc = c.strip()
                if not cc: continue
                if not hora and re.match(r'^\d{1,2}:\d{2}$', cc): hora = cc; continue
                if 'E-Soccer' in cc: comp = cc; continue
                if not casa and (' x ' in cc or ' vs ' in cc):
                    sep = ' x ' if ' x ' in cc else ' vs '
                    parts = cc.split(sep, 1)
                    casa = parts[0].strip();
                    fora = parts[1].strip() if len(parts) > 1 else ''
                    continue
                cu = cc.upper()
                if 'AO VIVO' in cu or 'LIVE' in cu or 'AGENDADO' in cu: status = cc; continue
            if not casa and len(ct) > 1: casa = ct[1]
            if not fora and len(ct) > 2: fora = ct[2]
            casa = re.sub(r'^(Ao Vivo Agora|Ao Vivo|Agendado)\s*', '', casa, flags=re.IGNORECASE).strip()
            fora = re.sub(r'^(Ao Vivo Agora|Ao Vivo|Agendado)\s*', '', fora, flags=re.IGNORECASE).strip()
            if casa and ' x ' in casa and not fora:
                p = casa.split(' x ', 1);
                casa = p[0].strip();
                fora = p[1].strip()
            su = (status + ' ' + rt).upper()
            is_live = 'AO VIVO' in su or 'LIVE' in su
            ca = extract_alias(casa);
            fa = extract_alias(fora)
            if ca or fa:
                jogos.append({'hora': hora, 'casa': ca, 'fora': fa,
                              'casa_full': casa, 'fora_full': fora,
                              'competicao': comp, 'status': status, 'is_live': is_live})
        return jogos
    except Exception as e:
        st.error(f"Erro ao processar AceOdds: {e}")
        return st.session_state.get('aceodds_games', [])


# ============================================
# SOM / ALERTA
# ============================================
def play_alert_sound():
    try:
        html = """<script>
try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    function beep(f, d, w) {
      const o = ctx.createOscillator(); const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = f; o.type = 'sine';
      g.gain.setValueAtTime(0.001, ctx.currentTime + w);
      g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + w + 0.02);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + w + d);
      o.start(ctx.currentTime + w); o.stop(ctx.currentTime + w + d + 0.05);
    }
    beep(880, 0.15, 0); beep(1320, 0.15, 0.2); beep(1760, 0.25, 0.4);
} catch(e) {}
</script>"""
        b64 = base64.b64encode(html.encode('utf-8')).decode('ascii')
        try:
            st.iframe(f"data:text/html;base64,{b64}", height=1)
        except AttributeError:
            components.html(html, height=0)
    except Exception:
        pass


def check_oportunidades(df):
    if df is None or df.empty: return []
    opps = df[df['O2.5 HT?'].eq('✅') & df['Conf'].astype(str).str.contains('🟢', na=False)]
    novas = []
    for _, r in opps.iterrows():
        key = f"{r.get('hora', '')}|{r.get('casa', '')}|{r.get('fora', '')}"
        if key not in st.session_state.ultima_oportunidade:
            novas.append(r);
            st.session_state.ultima_oportunidade.add(key)
    return novas


def emitir_alerta(novas):
    if not novas: return
    if st.session_state.notif_alerta:
        for r in novas[:5]:
            st.toast(f"🎯 **{r['casa']} × {r['fora']}**\n\n"
                     f"🟢 Alta confiança + Over 2.5 HT │ {r.get('Over 2.5 HT', '')}", icon="🚨")
    if st.session_state.som_ativo: play_alert_sound()


# ============================================
# RENDER HELPERS
# ============================================
def render_progress_row(label, pct):
    color = pbar_color(pct * 100)
    return f'''<div class="prog-row">
        <div class="prog-lbl">{label}</div>
        <div class="prog-val" style="color:{color};">{pct * 100:.1f}%</div>
        <div class="pbar"><div style="width:{min(pct * 100, 100)}%; background:{color}; box-shadow:0 0 10px {color};"></div></div>
    </div>'''


def render_card_header():
    return (
        '<div class="mc-header-row">'
        '<div class="mc-hcell">Hora</div>'
        '<div class="mc-hcell">Confronto</div>'
        '<div class="mc-hcell">⚽️ Média De Gols</div>'
        '<div class="mc-hcell">🎯 Apostar HT</div>'
        '<div class="mc-hcell">🎯 Apostar FT</div>'
        '<div class="mc-hcell">⭐️ Over Players</div>'
        '</div>'
    )


def render_card_row(row, casa_raw, fora_raw, ldf=None):
    hora = str(row.get('hora', '--:--'))
    liga = str(row.get('competicao', '')).upper()
    gols_ft = row.get('Gols FT', '-')
    gols_ht = row.get('Gols HT', '-')
    linha_seg = row.get('Linha Seg FT', '') or '—'
    linha_atende = linha_seg not in ('—', 'Sem Over', '')
    ou_a = compute_team_over_under(ldf, casa_raw.lower()) if ldf is not None else {}
    ou_b = compute_team_over_under(ldf, fora_raw.lower()) if ldf is not None else {}
    p_a_15 = ou_a.get('1.5', 0) * 100
    p_a_25 = ou_a.get('2.5', 0) * 100
    p_b_15 = ou_b.get('1.5', 0) * 100
    p_b_25 = ou_b.get('2.5', 0) * 100

    def color_pct(p):
        if p >= 60: return '#00ff88'
        if p >= 40: return '#ffd600'
        return '#ff8c00'

    rec_ht = row.get('Rec HT', 'Evitar HT')
    prob_rec_ht = row.get('Prob Rec HT', '-')

    if 'Over 2.5' in rec_ht:
        o25_color = '#00ff88'
    elif 'Over 1.5' in rec_ht:
        o25_color = '#ffd600'
    elif 'Over 0.5' in rec_ht:
        o25_color = '#ff8c00'
    else:
        o25_color = '#ff2e88'

    o25_top = f'{prob_rec_ht}'
    o25_sub = f'{rec_ht}'

    if linha_atende:
        linha_num = linha_seg.replace('Over ', '').strip()
        ap_top = f'Over {linha_num} FT'
        ap_color = '#00f5ff'
    else:
        ap_top = 'Sem linha'
        ap_color = '#ff2e88'

    return (
        '<div class="mc-row">'
        f'<div class="mc-box mc-hora-block"><div class="h">{hora}</div><div class="l">{liga}</div></div>'
        '<div class="mc-box mc-teams-box">'
        f'<div class="mc-team-side left"><span class="name">{casa_raw}</span></div>'
        '<span class="mc-vs">VS</span>'
        f'<div class="mc-team-side right"><span class="name">{fora_raw}</span></div>'
        '</div>'
        f'<div class="mc-box mc-media"><div class="vals"><span class="ht">HT {gols_ht}</span><span class="sep">|</span><span class="ft">FT {gols_ft}</span></div></div>'
        f'<div class="mc-box mc-status"><div class="top" style="color:{o25_color};">{o25_top}</div><div class="sub" style="color:{o25_color};">{o25_sub}</div></div>'
        f'<div class="mc-box mc-status"><div class="top" style="color:{ap_color};">{ap_top}</div></div>'
        '<div class="mc-box mc-player-box">'
        '<div class="phdr">OVER INDIVIDUAL</div>'
        f'<div class="mc-pnames"><span class="pn" style="color:#00ff88;">{casa_raw[:14]}</span><span class="pn" style="color:#00f5ff;">{fora_raw[:14]}</span></div>'
        '<div class="mc-pstats">'
        '<div class="mc-pcol">'
        f'<div class="mc-pstat"><span class="lbl">Marcar 1.5 Gols</span><span class="val" style="color:{color_pct(p_a_15)};">{p_a_15:.0f}%</span></div>'
        f'<div class="mc-pstat"><span class="lbl">Marcar 2.5 Gols</span><span class="val" style="color:{color_pct(p_a_25)};">{p_a_25:.0f}%</span></div>'
        '</div>'
        '<div class="mc-pcol">'
        f'<div class="mc-pstat"><span class="lbl">Marcar 1.5 Gols</span><span class="val" style="color:{color_pct(p_b_15)};">{p_b_15:.0f}%</span></div>'
        f'<div class="mc-pstat"><span class="lbl">Marcar 2.5 Gols</span><span class="val" style="color:{color_pct(p_b_25)};">{p_b_25:.0f}%</span></div>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'
    )


def render_match_card(row, ad, ld, idx=0):
    lk = find_league_key(row.get('competicao', ''), ld)
    casa_raw = str(row.get('casa', ''));
    fora_raw = str(row.get('fora', ''))
    casa = casa_raw.strip().lower();
    fora = fora_raw.strip().lower()
    if not lk or lk not in ad:
        st.info("Sem dados da liga.");
        return
    ldf = ad[lk]

    st.markdown('<div class="section-label">📊 OVER/UNDER PARTIDA (HT → FT)</div>', unsafe_allow_html=True)
    ou_parts = []
    for line in ['0.5', '1.5', '2.5']:
        col = f'Over {line} HT'
        if col in row and row[col]:
            try:
                pct = parse_pct(row[col]) / 100
            except:
                continue
            ou_parts.append(render_progress_row(f'{line} HT', pct))
    for line in ['0.5', '1.5', '2.5', '3.5', '4.5', '5.5']:
        col = f'Over {line} FT'
        if col in row and row[col]:
            try:
                pct = parse_pct(row[col]) / 100
            except:
                continue
            ou_parts.append(render_progress_row(f'{line} FT', pct))
    if ou_parts:
        st.markdown(
            f'<div style="background: rgba(0,0,0,0.4); padding: 10px 16px; border-radius:10px; border:1px solid rgba(0,245,255,0.15);">{"".join(ou_parts)}</div>',
            unsafe_allow_html=True)

    st.markdown('<div class="section-label">🎯 OVER INDIVIDUAL (gols do time)</div>', unsafe_allow_html=True)
    ou_a = compute_team_over_under(ldf, casa);
    ou_b = compute_team_over_under(ldf, fora)
    c1, c2 = st.columns(2)
    for col, team_name, ou_data, cor in [(c1, casa_raw, ou_a, '#00ff88'), (c2, fora_raw, ou_b, '#00f5ff')]:
        with col:
            if not ou_data:
                st.markdown(
                    f'<div style="font-size:12.5px; color:#7a89a8; padding:10px;">Sem dados p/ {team_name[:15]}</div>',
                    unsafe_allow_html=True)
                continue
            rows_html = ''
            for line, pct in ou_data.items():
                rows_html += render_progress_row(line, pct)
            st.markdown(f'''<div style="background: rgba(0,0,0,0.4); padding: 10px 14px; 
                border-radius:10px; border:1px solid rgba(0,245,255,0.15);">
                <div style="font-size:13px; font-weight:800; color:{cor}; margin-bottom:8px;
                    text-shadow: 0 0 10px {cor};">
                    {team_name[:20]}
                </div>
                {rows_html}
            </div>''', unsafe_allow_html=True)

    st.markdown('<div class="section-label">📈 MÉDIAS & BTTS</div>', unsafe_allow_html=True)
    med_ft = row.get('Gols FT', '-');
    med_ht = row.get('Gols HT', '-')
    btts_ft = row.get('BTTS FT', '-');
    btts_ht = row.get('BTTS HT', '-')
    st.markdown(f"""<div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
        <div style="background: rgba(0,0,0,0.4); padding:12px 16px; border-radius:10px; 
            border:1px solid rgba(0,245,255,0.15);">
            <div style="font-size:11.5px; color:#7a89a8; text-transform:uppercase; 
                letter-spacing:1px; font-weight:700; margin-bottom:10px;">Média de Gols</div>
            <div style="display:flex; justify-content:space-between; font-size:15px; padding:6px 0;
                border-bottom:1px solid rgba(0,245,255,0.06);">
                <span style="color:#f0f5ff; font-weight:600;">HT</span>
                <span style="color:#b537ff; font-weight:800; font-family:'JetBrains Mono',monospace;
                    text-shadow: 0 0 10px rgba(181,55,255,0.5);">{med_ht}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:15px; padding:6px 0;">
                <span style="color:#f0f5ff; font-weight:600;">FT</span>
                <span style="color:#00f5ff; font-weight:800; font-family:'JetBrains Mono',monospace;
                    text-shadow: 0 0 10px rgba(0,245,255,0.5);">{med_ft}</span>
            </div>
        </div>
        <div style="background: rgba(0,0,0,0.4); padding:12px 16px; border-radius:10px; 
            border:1px solid rgba(0,245,255,0.15);">
            <div style="font-size:11.5px; color:#7a89a8; text-transform:uppercase; 
                letter-spacing:1px; font-weight:700; margin-bottom:10px;">Ambas Marcam</div>
            <div style="display:flex; justify-content:space-between; font-size:15px; padding:6px 0;
                border-bottom:1px solid rgba(0,245,255,0.06);">
                <span style="color:#f0f5ff; font-weight:600;">BTTS HT</span>
                <span style="color:#b537ff; font-weight:800; font-family:'JetBrains Mono',monospace;
                    text-shadow: 0 0 10px rgba(181,55,255,0.5);">{btts_ht}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:15px; padding:6px 0;">
                <span style="color:#f0f5ff; font-weight:600;">BTTS FT</span>
                <span style="color:#00ff88; font-weight:800; font-family:'JetBrains Mono',monospace;
                    text-shadow: 0 0 10px rgba(0,255,136,0.5);">{btts_ft}</span>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)


# ============================================
# RADAR
# ============================================
def compute_radar_from_fixtures(df_aceodds, ng=RADAR_GAMES):
    radar = {}
    if df_aceodds is None or df_aceodds.empty: return radar
    for liga in df_aceodds['competicao'].dropna().unique():
        df_liga = df_aceodds[df_aceodds['competicao'] == liga].copy()
        if df_liga.empty: continue
        if 'hora' in df_liga.columns:
            df_liga['_h'] = df_liga['hora'].apply(lambda x: safe_int(str(x).split(':')[0]) if x else 0)
            df_liga = df_liga.sort_values('_h')
        df_liga = df_liga.head(ng);
        n = len(df_liga)

        def avg_pct(col):
            if col not in df_liga.columns: return 0
            vals = []
            for v in df_liga[col]:
                s = str(v).strip()
                if s and s not in ('', '-', 'nan', 'None', 'NaN'):
                    try:
                        vals.append(float(s.replace('%', '').strip()))
                    except:
                        pass
            return (sum(vals) / len(vals) / 100) if vals else 0

        gh = pd.to_numeric(df_liga.get('Gols HT', pd.Series()), errors='coerce').mean()
        gf = pd.to_numeric(df_liga.get('Gols FT', pd.Series()), errors='coerce').mean()
        gh = 0 if pd.isna(gh) else gh;
        gf = 0 if pd.isna(gf) else gf

        if gf > 0:
            pct_ht = (gh / gf) * 100
            pct_ft = 100 - pct_ht
        else:
            pct_ht = 50.0;
            pct_ft = 50.0

        if pct_ht >= 55:
            tendencia_tempo = '1º Tempo Forte'
            badge_class = 'badge-ht-heavy'
            tempo_icon = '🔥'
        elif pct_ft >= 55:
            tendencia_tempo = '2º Tempo Forte'
            badge_class = 'badge-ft-heavy'
            tempo_icon = '❄️'
        else:
            tendencia_tempo = 'Equilibrado'
            badge_class = 'badge-balanced'
            tempo_icon = '⚖️'

        tendencia = 'stable';
        tendencia_delta = 0
        if n >= 4 and 'Gols FT' in df_liga.columns:
            half = n // 2
            gf_old = pd.to_numeric(df_liga['Gols FT'].iloc[:half], errors='coerce').mean()
            gf_new = pd.to_numeric(df_liga['Gols FT'].iloc[half:], errors='coerce').mean()
            if not pd.isna(gf_old) and not pd.isna(gf_new) and gf_old > 0:
                delta = (gf_new - gf_old) / gf_old
                tendencia_delta = delta
                if delta >= 0.15:
                    tendencia = 'up'
                elif delta <= -0.15:
                    tendencia = 'down'

        o25f = avg_pct('Over 2.5 FT');
        o35f = avg_pct('Over 3.5 FT')
        o45f = avg_pct('Over 4.5 FT');
        o25h = avg_pct('Over 2.5 HT')
        btf = avg_pct('BTTS FT')
        perfil = 'OFENSIVA' if gf >= 4.5 else ('EQUILIBRADA' if gf >= 3.2 else 'DEFENSIVA')
        score = round(min(gf / 6.0, 1) * 40 + o25f * 20 + o25h * 20 + btf * 20)

        radar[liga] = {'n': n, 'avg_ft': gf, 'avg_ht': gh,
                       'pct_ht': pct_ht, 'pct_ft': pct_ft,
                       'tendencia_tempo': tendencia_tempo,
                       'badge_class': badge_class, 'tempo_icon': tempo_icon,
                       'o25_ft': o25f, 'o35_ft': o35f, 'o45_ft': o45f,
                       'o25_ht': o25h, 'btts_ft': btf,
                       'perfil': perfil, 'score': score,
                       'tendencia': tendencia, 'tendencia_delta': tendencia_delta}
    return radar


def _build_reason_best(info, lg):
    reasons = []
    if info['avg_ft'] >= 5.5:
        reasons.append(f"média de <b>{info['avg_ft']:.2f}</b> gols/jogo (altíssima)")
    elif info['avg_ft'] >= 4.5:
        reasons.append(f"média de <b>{info['avg_ft']:.2f}</b> gols/jogo (alta)")
    else:
        reasons.append(f"média de <b>{info['avg_ft']:.2f}</b> gols/jogo")
    if info['o25_ft'] >= 0.75:
        reasons.append(f"<span class='hl'>{info['o25_ft'] * 100:.0f}%</span> dos jogos com Over 2.5 FT")
    if info['o35_ft'] >= 0.55:
        reasons.append(f"<span class='hl'>{info['o35_ft'] * 100:.0f}%</span> Over 3.5 FT")
    if info['o45_ft'] >= 0.4:
        reasons.append(f"<span class='hl'>{info['o45_ft'] * 100:.0f}%</span> Over 4.5 FT")
    if info['o25_ht'] >= 0.55:
        reasons.append(f"<span class='hl'>{info['o25_ht'] * 100:.0f}%</span> no 1º tempo")
    if info['btts_ft'] >= 0.7:
        reasons.append(f"BTTS em <span class='hl'>{info['btts_ft'] * 100:.0f}%</span>")
    if info.get('tendencia') == 'up':
        delta_pct = info.get('tendencia_delta', 0) * 100
        reasons.append(f"tendência de <b>alta</b> ({delta_pct:+.0f}%)")
    return " · ".join(reasons)


def render_radar_tab():
    st.markdown("""<div class="top-hero">
        <div class="top-hero-left">
            <span class="top-hero-icon">📡</span>
            <span class="top-hero-title">Radar FIFA — <b>Análise de Ligas</b> <span class="top-hero-sep">|</span> <span class="top-hero-dev">@FIFAlgorithm</span></span>
        </div>
        <div class="top-hero-right">
            <span class="status-dot"><span class="dot"></span> Online</span>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="pill-actions">', unsafe_allow_html=True)
    cb1, _sp = st.columns([1.2, 6])
    with cb1:
        if st.button("⬅️ Voltar ao Menu", key="radar_back", width='stretch', type="primary"):
            st.session_state.page = 'jogos_dia'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    df_ac = st.session_state.get('aceodds_games', None)
    if df_ac is None or (isinstance(df_ac, list) and not df_ac):
        st.warning("⚠️ Carregue os **Jogos do Dia** primeiro.");
        return
    if isinstance(df_ac, list): df_ac = pd.DataFrame(df_ac)
    if df_ac.empty: st.info("Sem dados."); return
    df_ac = df_ac.copy()
    df_ac['competicao'] = df_ac['competicao'].apply(normalize_league_name)
    radar = compute_radar_from_fixtures(df_ac, RADAR_GAMES)
    if not radar: st.warning("Sem dados."); return
    rank = sorted(radar.items(), key=lambda x: -x[1]['score'])

    if rank:
        best_lg, best_info = rank[0]
        reason = _build_reason_best(best_info, best_lg)
        st.markdown(f"""<div class="league-card-best">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                    <span class="best-badge">🏆 MELHOR PARA OVER GOLS</span>
                    <span style="font-size:22px; font-weight:900; color:#f0f5ff;
                        text-shadow: 0 0 18px rgba(0,255,136,0.5);">
                        {LEAGUES.get(best_lg, {}).get('icon', '⚽')} {best_lg}
                    </span>
                    <span class="{best_info['badge_class']}" style="font-size:12px; padding:6px 14px;">
                        {best_info['tempo_icon']} {best_info['tendencia_tempo']} ({best_info['pct_ht']:.0f}% HT)
                    </span>
                </div>
                <div style="display:flex; align-items:center; gap:14px;">
                    <div style="text-align:right;">
                        <div style="font-size:10.5px; color:#7a89a8; text-transform:uppercase;
                            letter-spacing:1px; font-weight:800;">Score</div>
                        <div style="font-size:32px; font-weight:900; color:#00ff88;
                            font-family:'JetBrains Mono',monospace; line-height:1;
                            text-shadow: 0 0 20px rgba(0,255,136,0.8);">{best_info['score']}</div>
                    </div>
                </div>
            </div>
            <div class="best-reason">
                <div style="font-size:11.5px; color:#7a89a8; text-transform:uppercase;
                    letter-spacing:1px; font-weight:800; margin-bottom:4px;">
                    💡 Por que está em destaque:
                </div>
                <div>{reason}</div>
            </div>
            <div class="thermometer" style="margin-top:14px;">
                <div style="width:{best_info['score']}%; background: linear-gradient(90deg, #00ff88, #00f5ff);
                    box-shadow: 0 0 15px rgba(0,255,136,0.7);"></div>
            </div>
            <div style="margin-top:12px;">
                <div style="font-size:10.5px; color:#7a89a8; text-transform:uppercase; letter-spacing:1px; font-weight:800; margin-bottom:4px;">
                    ⏱️ Distribuição de Gols (1º Tempo vs 2º Tempo)
                </div>
                <div class="dual-bar">
                    <div class="ht" style="width:{best_info['pct_ht']}%;" title="1º Tempo"></div>
                    <div class="ft" style="width:{best_info['pct_ft']}%;" title="2º Tempo"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:#7a89a8; margin-top:4px;">
                    <span>🔥 HT: {best_info['pct_ht']:.0f}%</span>
                    <span>❄️ FT: {best_info['pct_ft']:.0f}%</span>
                </div>
            </div>
            <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:8px 18px;
                font-size:13px; color:#f0f5ff;">
                <span>⚽ Média FT: <b style="color:#00ff88; text-shadow:0 0 10px rgba(0,255,136,0.5);">{best_info['avg_ft']:.2f}</b></span>
                <span>⏱️ Over 2.5 HT: <b style="color:#b537ff; text-shadow:0 0 10px rgba(181,55,255,0.5);">{best_info['o25_ht'] * 100:.0f}%</b></span>
                <span>🎯 Over 2.5 FT: <b style="color:#00ff88; text-shadow:0 0 10px rgba(0,255,136,0.5);">{best_info['o25_ft'] * 100:.0f}%</b></span>
                <span>🔥 Over 3.5 FT: <b style="color:#00f5ff; text-shadow:0 0 10px rgba(0,245,255,0.5);">{best_info['o35_ft'] * 100:.0f}%</b></span>
                <span>💥 Over 4.5 FT: <b style="color:#ff8c00; text-shadow:0 0 10px rgba(255,140,0,0.5);">{best_info['o45_ft'] * 100:.0f}%</b></span>
                <span>👥 BTTS FT: <b style="color:#b537ff; text-shadow:0 0 10px rgba(181,55,255,0.5);">{best_info['btts_ft'] * 100:.0f}%</b></span>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-label">📊 Ranking Completo de Ligas</div>', unsafe_allow_html=True)
    trend_map = {'up': ('📈', 'SUBINDO', '#00ff88'),
                 'down': ('📉', 'CAINDO', '#00f5ff'),
                 'stable': ('➖', 'ESTÁVEL', '#7a89a8')}
    for i, (lg, info) in enumerate(rank[1:], 2):
        md = {2: '🥈', 3: '🥉'}.get(i, f'#{i}')
        bc = {'OFENSIVA': 'badge-ofensivo', 'EQUILIBRADA': 'badge-equilibrado', 'DEFENSIVA': 'badge-defensivo'}[
            info['perfil']]
        t_ic, t_txt, t_cor = trend_map.get(info.get('tendencia', 'stable'), ('➖', 'ESTÁVEL', '#7a89a8'))
        delta_pct = info.get('tendencia_delta', 0) * 100
        delta_txt = f"{delta_pct:+.0f}%" if abs(delta_pct) > 0.5 else ""
        st.markdown(f"""<div class="league-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span style="font-size:16px; font-weight:800;">{md} {lg}</span>
                    <span style="font-size:11px; color:#7a89a8; font-weight:700;">
                        ({info['n']} jogos)
                    </span>
                    <span class="{bc}">{info['perfil']}</span>
                    <span style="font-size:11px; color:{t_cor}; font-weight:800;
                        background: rgba(0,245,255,0.05); padding:4px 10px; border-radius:100px;
                        border: 1px solid {t_cor}66;">{t_ic} {t_txt} {delta_txt}</span>
                    <span class="{info['badge_class']}">
                        {info['tempo_icon']} {info['tendencia_tempo']} ({info['pct_ht']:.0f}% HT)
                    </span>
                </div>
                <div style="font-size:24px; font-weight:900; color:#00f5ff;
                    text-shadow: 0 0 14px rgba(0,245,255,0.5);">{info['score']}</div>
            </div>
            <div class="thermometer"><div style="width:{info['score']}%;"></div></div>
            <div style="margin-top:10px;">
                <div class="dual-bar">
                    <div class="ht" style="width:{info['pct_ht']}%;"></div>
                    <div class="ft" style="width:{info['pct_ft']}%;"></div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:10.5px; color:#7a89a8; margin-top:3px;">
                    <span>🔥 1º T: {info['pct_ht']:.0f}%</span>
                    <span>❄️ 2º T: {info['pct_ft']:.0f}%</span>
                </div>
            </div>
            <div style="margin-top:10px; display:flex; flex-wrap:wrap; gap:6px 16px;
                font-size:12.5px; color:#7a89a8;">
                <span>Over 2.5 HT: <b style="color:#b537ff;">{info['o25_ht'] * 100:.0f}%</b></span>
                <span>Over 2.5 FT: <b style="color:#00ff88;">{info['o25_ft'] * 100:.0f}%</b></span>
                <span>Over 3.5 FT: <b style="color:#00f5ff;">{info['o35_ft'] * 100:.0f}%</b></span>
                <span>Over 4.5 FT: <b style="color:#ff8c00;">{info['o45_ft'] * 100:.0f}%</b></span>
                <span>BTTS FT: <b style="color:#b537ff;">{info['btts_ft'] * 100:.0f}%</b></span>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    rb1, _sp = st.columns([1.2, 6])
    with rb1:
        if st.button("⬅️ Voltar ao Menu Principal", key="radar_back_bottom", width='stretch'):
            st.session_state.page = 'jogos_dia'
            st.rerun()


# ============================================
# PAGE: JOGOS DO DIA
# ============================================
def page_jogos_do_dia():
    st.markdown("""<div class="top-hero">
        <div class="top-hero-left">
            <span class="top-hero-icon">💀</span>
            <span class="top-hero-title">E-Soccer <b>Fifa Analytics</b> <span class="top-hero-sep">⚡️</span> <span class="top-hero-dev">@FIFAlgorithm</span></span>
        </div>
        <div class="top-hero-right">
            <span class="methodology-badge">
                <span class="icon">🧠</span>
                Probabilidades Baseadas em (Monte Carlo + Dixon-Coles) · 5.000 Simulações por jogo
            </span>
            <span class="status-dot"><span class="dot"></span> Online</span>
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="pill-actions">', unsafe_allow_html=True)
    ac1, ac2, ac3, _spacer = st.columns([1.1, 1.1, 1.1, 4])
    with ac1:
        if st.button("💀 Carregar Dados", key="load_leagues", width='stretch', type="primary"):
            with st.spinner("Carregando dados..."):
                try:
                    st.session_state['_fetch_errors'] = []
                    ad = {};
                    dbg = {}
                    prog = st.progress(0, text="Buscando ligas...")
                    for i, (ln, li) in enumerate(LEAGUES.items(), 1):
                        prog.progress(i / len(LEAGUES), text=f"Buscando {ln}...")
                        m = scraper.get_league_matches(li['id'])
                        if m:
                            rs = scraper.extract(m);
                            dbg[ln] = scraper.last_debug
                            if rs:
                                d = pd.DataFrame(rs)
                                if 'datetime_obj' in d.columns and not d['datetime_obj'].isna().all():
                                    d = d.sort_values(by='datetime_obj', ascending=False)
                                else:
                                    d = d.sort_values(by='time', ascending=False)
                            else:
                                d = pd.DataFrame()
                            ad[ln] = d
                        else:
                            ad[ln] = pd.DataFrame();
                            dbg[ln] = {'matched_today': 0}
                    prog.empty()
                    st.session_state['all_data'] = ad
                    st.session_state['debug_info'] = dbg
                    total_jogos = sum(len(x) for x in ad.values() if x is not None and not x.empty)
                    if total_jogos > 0:
                        st.success(f"✅ {total_jogos} partidas carregadas")
                    else:
                        erros = st.session_state.get('_fetch_errors', [])
                        if erros:
                            st.warning(f"⚠️ Nenhuma partida carregada.")
                        else:
                            st.info("Sem partidas finalizadas hoje ainda.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro inesperado: {e}")
    with ac2:
        if st.button("⚡️ Atualizar Jogos", key="load_games", width='stretch'):
            with st.spinner(f"Atualizando jogos..."):
                jogos = scrape_aceodds(max_retries=ACEODDS_MAX_RETRIES, timeout=ACEODDS_TIMEOUT)
                if jogos:
                    st.session_state['aceodds_games'] = jogos
                    st.session_state['aceodds_last_update'] = datetime.now()
                    st.session_state.ultima_oportunidade = set()

                    if not st.session_state.get('all_data'):
                        prog = st.progress(0, text="📚 Carregando dados das ligas automaticamente...")
                        ad = {};
                        dbg = {}
                        for i, (ln, li) in enumerate(LEAGUES.items(), 1):
                            prog.progress(i / len(LEAGUES), text=f"Buscando {ln}...")
                            m = scraper.get_league_matches(li['id'])
                            if m:
                                rs = scraper.extract(m);
                                dbg[ln] = scraper.last_debug
                                if rs:
                                    d = pd.DataFrame(rs)
                                    if 'datetime_obj' in d.columns and not d['datetime_obj'].isna().all():
                                        d = d.sort_values(by='datetime_obj', ascending=False)
                                    else:
                                        d = d.sort_values(by='time', ascending=False)
                                else:
                                    d = pd.DataFrame()
                                ad[ln] = d
                            else:
                                ad[ln] = pd.DataFrame();
                                dbg[ln] = {'matched_today': 0}
                        prog.empty()
                        st.session_state['all_data'] = ad
                        st.session_state['debug_info'] = dbg
                        total_ligas = sum(len(x) for x in ad.values() if x is not None and not x.empty)
                        st.success(f"✅ {len(jogos)} jogos + {total_ligas} partidas de {len(LEAGUES)} ligas carregadas!")
                    else:
                        st.success(f"✅ {len(jogos)} jogos!")
                    st.rerun()
                else:
                    st.error("❌ Não foi possível carregar.")
    with ac3:
        if st.button("🔥 Radar FIFA", key="go_radar", width='stretch'):
            st.session_state.page = 'radar';
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if (st.session_state.get('aceodds_games')
            and not st.session_state.get('all_data')):
        st.markdown("""<div class="warning-banner">
            <b>⚠️ Dados de liga não carregados</b> — os cards vão mostrar
            <code>nan</code> / <code>0%</code>. Clique em
            <b style="color:#00f5ff;">💀 Carregar Dados</b> para gerar as estatísticas completas.
        </div>""", unsafe_allow_html=True)

    if 'aceodds_games' not in st.session_state or not st.session_state['aceodds_games']:
        st.markdown("""<div style="background: linear-gradient(90deg, rgba(255,214,0,0.15), rgba(255,140,0,0.08));
            padding: 16px 20px; border-radius: 10px; border-left: 4px solid #ffd600;
            color: #f0f5ff; font-size: 14px; margin: 15px 0; box-shadow: 0 0 24px rgba(255,214,0,0.15);">
            <b style="color:#ffd600; font-size:16px;">⚠️ Atenção</b> — Para dar início, favor clicar em 
            <b style="color:#00f5ff;">💀 Carregar Dados</b> e, na sequência, 
            <b style="color:#00f5ff;">⚡️ Atualizar Jogos</b>. Após isso, o Radar FIFA irá disponibilizar os dados.
        </div>""", unsafe_allow_html=True)
        return

    df = pd.DataFrame(st.session_state['aceodds_games'])
    df['competicao'] = df['competicao'].apply(normalize_league_name)
    ad = st.session_state.get('all_data', {})
    if ad:
        jc, jf = compute_jc_jf(df, ad, LEAGUES)
        df['JC'] = jc;
        df['JF'] = jf
        with st.spinner("Rodando Monte Carlo..."):
            r = monte_carlo(df, ad, LEAGUES)
        for c, v in r.items(): df[c] = v
        for c in ['Gols HT', 'Gols FT', 'xG Casa', 'xG Fora']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        for c in EXTRA_COLUMNS:
            if c in df.columns and c not in ['Gols HT', 'Gols FT', 'xG Casa', 'xG Fora']:
                df[c] = df[c].fillna('').astype(str)
        st.session_state['aceodds_games'] = df.to_dict('records')
    else:
        df['JC'] = 0;
        df['JF'] = 0
        for c in EXTRA_COLUMNS: df[c] = ''
    novas = check_oportunidades(df)
    if novas: emitir_alerta(novas)

    upd = st.session_state.get('aceodds_last_update', datetime.now()).strftime('%H:%M')
    st.markdown(f"""<div class="stat-mini-row">
        <div class="stat-mini">
            <div class="sm-icon">⚽️</div>
            <div class="sm-info">
                <div class="sm-lbl">Jogos Disponíveis</div>
                <div class="sm-val">{len(df)}</div>
            </div>
        </div>
        <div class="stat-mini">
            <div class="sm-icon">🕐</div>
            <div class="sm-info">
                <div class="sm-lbl">Última Atualização</div>
                <div class="sm-val time">{upd}</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    fc1, _spacer = st.columns([2.4, 5])
    with fc1:
        liga_opts = ['🎮 Escolher Liga'] + [f"{info['icon']} {lg}" for lg, info in LEAGUES.items()]
        liga_sel = st.selectbox("Liga", liga_opts, key='sel_liga', label_visibility='collapsed')
        if liga_sel == '🎮 Escolher Liga':
            f_liga = '(todas)'
        else:
            f_liga = '(todas)'
            for lg in LEAGUES.keys():
                if lg in liga_sel: f_liga = lg; break

    df_f = df.copy()
    if f_liga != '(todas)': df_f = df_f[df_f['competicao'] == f_liga]
    if df_f.empty:
        st.info("Nenhum jogo atende aos filtros.")
        return

    st.markdown(render_card_header(), unsafe_allow_html=True)
    st.markdown('<div class="mc-list">', unsafe_allow_html=True)
    for i, (_, row) in enumerate(df_f.iterrows()):
        casa_raw = str(row.get('casa', ''))
        fora_raw = str(row.get('fora', ''))
        lk = find_league_key(row.get('competicao', ''), LEAGUES)
        ldf = ad.get(lk) if lk and lk in ad else None
        st.markdown(render_card_row(row, casa_raw, fora_raw, ldf=ldf), unsafe_allow_html=True)
        with st.expander(f"🔍 Ver análise completa — {casa_raw} × {fora_raw}", expanded=False):
            render_match_card(row, ad, LEAGUES, idx=i)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📊 Ver tabela completa + Downloads", expanded=False):
        cols = ['hora', 'competicao', 'casa', 'fora',
                'Gols HT', 'Gols FT', 'Linha Seg FT',
                'Over 0.5 HT', 'Over 1.5 HT', 'Over 2.5 HT',
                'Over 0.5 FT', 'Over 1.5 FT', 'Over 2.5 FT',
                'Over 3.5 FT', 'Over 4.5 FT', 'Over 5.5 FT', 'BTTS FT']
        df_sum = df_f[[c for c in cols if c in df_f.columns]]
        st.dataframe(df_sum, width='stretch', hide_index=True, height=400)
        c1, c2 = st.columns(2)
        with c1:
            csv = df_sum.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV", data=csv,
                               file_name=f"esoccer_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                               mime="text/csv", width='stretch')
        with c2:
            try:
                pdf = generate_pdf(df_sum, "E-Soccer — Jogos do Dia")
                st.download_button("📄 PDF", data=pdf,
                                   file_name=f"esoccer_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                   mime="application/pdf", width='stretch')
            except Exception as e:
                st.warning(f"PDF: {e}")


# ============================================
# PAGE: LIGA INDIVIDUAL
# ============================================
def page_liga(league_name):
    st.markdown(f"""<div class="top-hero">
        <div class="top-hero-left">
            <span class="top-hero-icon">💀</span>
            <span class="top-hero-title">E-Soccer <b>Fifa Analytics</b> <span class="top-hero-sep">⚡️</span> <span class="top-hero-dev">@FIFAlgorithm</span></span>
        </div>
        <div class="top-hero-right">
            <span class="methodology-badge">
                <span class="icon">🧠</span>
                Probabilidades Baseadas em (Monte Carlo + Dixon-Coles) · 5.000 Simulações por jogo
            </span>
            <span class="status-dot"><span class="dot"></span> Online</span>
        </div>
    </div>""", unsafe_allow_html=True)
    d = st.session_state.get('all_data', {}).get(league_name, pd.DataFrame())
    if d.empty:
        st.info(f"Sem partidas finalizadas para **{league_name}** hoje.")
        return
    st.caption(f"{len(d)} partidas finalizadas")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="stat-card"><div class="sc-icon">📊</div>
            <div class="sc-val">{len(d)}</div><div class="sc-label">Total</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-card"><div class="sc-icon">✅</div>
            <div class="sc-val">100%</div><div class="sc-label">Fin.</div></div>""", unsafe_allow_html=True)
    with c3:
        tg = int(d['home_score'].sum() + d['away_score'].sum())
        st.markdown(f"""<div class="stat-card"><div class="sc-icon">⚽</div>
            <div class="sc-val">{tg}</div><div class="sc-label">Gols</div></div>""", unsafe_allow_html=True)
    with c4:
        ag = (d['home_score'] + d['away_score']).mean()
        st.markdown(f"""<div class="stat-card"><div class="sc-icon">📈</div>
            <div class="sc-val">{ag:.2f}</div><div class="sc-label">Média</div></div>""", unsafe_allow_html=True)
    dd = d.copy();
    dd['sl'] = '✅'
    dd['hh'] = dd['ht_home'].fillna('-').astype(str)
    dd['ha'] = dd['ht_away'].fillna('-').astype(str)
    cs = ['time', 'date', 'home_team', 'away_team', 'home_score', 'away_score', 'hh', 'ha', 'sl']
    cm = {'time': '🕐', 'date': '📅', 'home_team': '🏠', 'away_team': '✈️',
          'home_score': 'FT Casa', 'away_score': 'FT Fora',
          'hh': 'HT Casa', 'ha': 'HT Fora', 'sl': '📌'}
    st.dataframe(dd[cs].rename(columns=cm), width='stretch', hide_index=True, height=500)


# ============================================
# GLOBAL + SIDEBAR
# ============================================
scraper = EFootballScraper()
with st.sidebar:
    st.markdown("""<div class="sb-brand">
        <div class="sb-logo">💀</div>
        <div>
            <div class="sb-brand-name">FIFAlgorithm</div>
            <div class="sb-brand-sub">E-Soccer Analytics</div>
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div class="sb-section">NAVEGAÇÃO</div>', unsafe_allow_html=True)
    nav_items = [
        ('jogos_dia', '📅 Jogos do Dia'),
        ('radar', '📡 Radar FIFA'),
    ]
    for key, label in nav_items:
        active = st.session_state.page == key
        if st.button(label, key=f'nav_{key}', width='stretch',
                     type='primary' if active else 'secondary'):
            st.session_state.page = key;
            st.rerun()
    st.markdown('<div class="sb-section">LIGAS</div>', unsafe_allow_html=True)
    for lg_name, lg_info in LEAGUES.items():
        key = f'liga_{lg_name}'
        active = st.session_state.page == key
        if st.button(f"{lg_info['icon']} {lg_name}", key=f'nav_{key}', width='stretch',
                     type='primary' if active else 'secondary'):
            st.session_state.page = key;
            st.rerun()
    st.markdown("---")
    modo = st.toggle("☀️ Modo Claro", value=st.session_state.modo_claro, key='toggle_modo')
    if modo != st.session_state.modo_claro:
        st.session_state.modo_claro = modo;
        st.rerun()
    st.session_state.som_ativo = st.toggle("🔊 Som", value=st.session_state.som_ativo, key='toggle_som')
    st.session_state.notif_alerta = st.toggle("🔔 Notificações", value=st.session_state.notif_alerta, key='toggle_notif')
    if st.button("🔔 Testar Alerta", width='stretch'):
        play_alert_sound();
        st.toast("🎯 Teste!", icon="🚨")
    if st.button("🌐 Testar Conexão 24live", width='stretch'):
        ok, msg = test_24live_connectivity()
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")
    st.markdown(f"""<div class="sb-footer">
        FIFAlgorithm v6.5.8 - Streamlit
        <div class="sb-footer-user">
            <div class="sb-avatar">V</div>
            <div>
                <div style="font-size:12px; font-weight:700; color:#f0f5ff;">Vagner S</div>
                <div style="font-size:10px;">Conta ativa</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

# ============================================
# ROUTER
# ============================================
page = st.session_state.get('page', 'jogos_dia')
if page == 'jogos_dia':
    page_jogos_do_dia()
elif page == 'radar':
    render_radar_tab()
elif page.startswith('liga_'):
    lg_name = page.replace('liga_', '')
    if lg_name in LEAGUES: page_liga(lg_name)
else:
    page_jogos_do_dia()
st.markdown("---")
st.caption("💀 E-Soccer Fifa Analytics ⚡️ @FIFAlgorithm")