"""
app.py — Foglio Ore digitale TEKNOIMPIANTI S.R.L.
==================================================
App Streamlit con doppia vista:
  • Dipendente  → compila e vede SOLO il proprio foglio ore (mobile-first)
  • Amministratore → dashboard protetta da PIN con tutti i dipendenti

Deploy: Streamlit Community Cloud (vedi README.md).
"""

from __future__ import annotations

import urllib.parse
from datetime import date, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import data_manager as dm
import pdf_generator as pdfgen

# ============================================================================
# CONFIGURAZIONE AZIENDALE (modificare qui liste e impostazioni)
# ============================================================================

DIPENDENTI = [
    "Daniele Todaro",
    "Luca Simonetta",
    "Federico Bernacchi",
    "Alessandro Trotti",
]

MEZZI = [
    "",  # nessun mezzo
    "Furgone 1",
    "Furgone 2",
    "Auto aziendale",
    "Mezzo proprio",
]

# Il PIN amministratore NON è scritto nel codice (che finisce su GitHub):
# va impostato nei Secrets di Streamlit Cloud (o in .streamlit/secrets.toml
# in locale, file escluso da git):   admin_pin = "1234"

GIORNI_NOME = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
GIORNI_SIGLA = ["L", "M", "M", "G", "V", "S"]

# ----------------------------------------------------------------------------
# TEMA GRAFICO — 3 stili professionali dark (selezione: variabile TEMA)
# Deve corrispondere ai colori in .streamlit/config.toml
# ----------------------------------------------------------------------------
import os

TEMA = int(os.environ.get("TEKNO_TEMA", "1"))

TEMI = {
    # 1 — Enterprise dark in stile gestionale (Zucchetti-like): superfici
    #     antracite, accento blu aziendale, angoli morbidi, molto sobrio.
    1: dict(
        nome="Enterprise Dark",
        bg="#0e1117", surface="#171d26", bordo="#28303c",
        testo="#f4f7fa", muted="#c2cedb",
        accento="#3aa3e3", accento_forte="#1b9cd8",
        badge_bg="#1b9cd8", badge_testo="#06121c",
        radius="14px",
    ),
    # 2 — Industrial Steel: nero-acciaio, angoli netti squadrati, accento
    #     ciano brand pieno. Look "quadro elettrico / officina".
    2: dict(
        nome="Industrial Steel",
        bg="#101214", surface="#181c1f", bordo="#3a4147",
        testo="#e6e8ea", muted="#98a2ab",
        accento="#1b9cd8", accento_forte="#1b9cd8",
        badge_bg="#e8b917", badge_testo="#111111",
        radius="3px",
    ),
    # 3 — Premium Graphite: nero profondo, superfici in grafite, accento
    #     azzurro luminoso, angoli molto arrotondati. Look "app premium".
    3: dict(
        nome="Premium Graphite",
        bg="#0a0a0c", surface="#15151a", bordo="#26262e",
        testo="#f0f0f2", muted="#a0a0ab",
        accento="#59c9f7", accento_forte="#2196d6",
        badge_bg="#59c9f7", badge_testo="#04141d",
        radius="20px",
    ),
}

T = TEMI[TEMA]
BLU_SCURO = T["accento_forte"]   # usato per pulsanti primari / accenti forti
BLU_CHIARO = T["accento"]

# ============================================================================
# SETUP PAGINA + STILE
# ============================================================================

st.set_page_config(
    page_title="Foglio Ore — Teknoimpianti S.r.l.",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Filigrana: scritta TEKNOIMPIANTI blu, tenue, ripetuta su tutto lo sfondo ---
_WM_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='460' height='320'>"
    "<text x='230' y='160' font-family='Arial,Helvetica,sans-serif' font-size='36' "
    f"font-weight='bold' fill='{T['accento']}' fill-opacity='0.055' "
    "text-anchor='middle' letter-spacing='6' "
    "transform='rotate(-24 230 160)'>TEKNOIMPIANTI</text></svg>"
)
_WM_URL = "data:image/svg+xml," + urllib.parse.quote(_WM_SVG)

st.markdown(
    f"""
    <style>
      /* ---- Mobile-first: caratteri e controlli grandi ---- */
      html, body {{ font-size: 17px; }}
      .block-container {{ padding-top: 2.4rem; max-width: 980px; }}

      /* Barra superiore di Streamlit in tinta col tema (niente fascia bianca
         che copre il logo) */
      header[data-testid="stHeader"] {{
        background: {T['bg']} !important;
      }}
      header[data-testid="stHeader"] * {{
        color: {T['muted']} !important;
      }}

      .stApp {{
        background-color: {T['bg']};
        background-image: url("{_WM_URL}");
        background-repeat: repeat;
        background-attachment: fixed;
      }}
      h1, h2, h3, h4 {{ color: {T['testo']} !important; }}

      /* ---- Etichette e testi LUMINOSI (Streamlit di default le attenua) ---- */
      label p,
      div[data-testid="stWidgetLabel"] p,
      div[data-testid="stWidgetLabel"] label {{
        color: {T['testo']} !important;
        font-weight: 600;
      }}
      div[data-testid="stRadio"] p,
      div[data-testid="stCheckbox"] p,
      div[data-testid="stMetricLabel"] p,
      details summary p,
      .stMarkdown p, .stMarkdown li {{
        color: {T['testo']} !important;
      }}
      div[data-testid="stMetricValue"] {{ color: {T['testo']} !important; }}
      div[data-testid="stCaptionContainer"] p, .stCaption p {{
        color: {T['muted']} !important;
        opacity: 1 !important;
      }}

      /* Pulsanti grandi, comodi col pollice in cantiere */
      .stButton > button, .stDownloadButton > button, .stLinkButton > a {{
        width: 100%;
        padding: 0.85rem 1rem;
        font-size: 1.12rem;
        font-weight: 700;
        border-radius: {T['radius']};
        border: 1px solid {T['bordo']};
      }}
      .stButton > button[kind="primary"] {{
        background: {T['accento_forte']};
        color: #ffffff;
        border: none;
      }}

      /* Input più alti e leggibili */
      input, .stTimeInput input, .stNumberInput input, .stTextInput input {{
        font-size: 1.08rem !important;
      }}

      /* Card giorno — leggermente traslucida: la filigrana traspare appena */
      div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: {T['radius']};
        background: {'rgba(%d,%d,%d,0.82)' % tuple(int(T['surface'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))};
        border: 1px solid {T['bordo']};
      }}

      /* Badge totale ore */
      .tk-badge {{
        display: inline-block;
        background: {T['badge_bg']};
        color: {T['badge_testo']};
        font-weight: 800;
        font-size: 1.05rem;
        padding: 0.35rem 0.9rem;
        border-radius: {T['radius']};
      }}
      .tk-day-title {{
        color: {T['accento']};
        font-weight: 800;
        font-size: 1.18rem;
        margin-bottom: 0.2rem;
      }}
      .tk-header-sub {{
        text-align: center;
        color: {T['muted']};
        letter-spacing: 0.14em;
        font-weight: 600;
        font-size: 0.82rem;
        margin-top: -0.4rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def intestazione() -> None:
    """Logo aziendale sempre visibile e centrato in cima alla pagina."""
    logo = Path(__file__).parent / "assets" / "logo.png"
    col_l, col_c, col_r = st.columns([1, 3, 1])
    with col_c:
        if logo.exists():
            st.image(str(logo), use_container_width=True)
        else:
            st.markdown(
                f"<h1 style='text-align:center;color:{BLU_SCURO};margin-bottom:0'>"
                "TEKNOIMPIANTI S.R.L.</h1>",
                unsafe_allow_html=True,
            )
    st.markdown(
        "<div class='tk-header-sub'>FOGLIO ORE SETTIMANALE — VENEGONO INFERIORE (VA)</div>",
        unsafe_allow_html=True,
    )
    st.divider()


# ============================================================================
# UTILITÀ
# ============================================================================

def parse_time(hhmm: str | None) -> time | None:
    if not hhmm:
        return None
    try:
        h, m = hhmm.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return None


def time_to_str(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None


def selettore_settimana(key_prefix: str) -> tuple[int, int]:
    """Selettore settimana basato su una data qualsiasi. Ritorna (anno_iso, settimana_iso)."""
    giorno = st.date_input(
        "📅 Settimana (scegli un giorno qualsiasi della settimana)",
        value=date.today(),
        format="DD/MM/YYYY",
        key=f"{key_prefix}_giorno",
    )
    iso = giorno.isocalendar()
    dal, al = dm.week_bounds_label(iso.year, iso.week)
    st.markdown(
        f"**Settimana n. {iso.week}** — dal **{dal}** al **{al}**"
    )
    return iso.year, iso.week


def leggi_secret(chiave: str, default):
    """Accesso sicuro ai secrets: senza secrets.toml Streamlit lancia
    StreamlitSecretNotFoundError, che qui diventa semplicemente il default."""
    try:
        return st.secrets.get(chiave, default)
    except Exception:  # noqa: BLE001 — nessun file secrets = usa default
        return default


def github_cfg_da_secrets() -> dict | None:
    gh = leggi_secret("github", None)
    if not gh:
        return None
    return {
        "token": gh.get("token", ""),
        "repo": gh.get("repo", ""),
        "branch": gh.get("branch", "main"),
    }


# ============================================================================
# VISTA DIPENDENTE
# ============================================================================

def vista_dipendente() -> None:
    st.subheader("👷 Compilazione foglio ore")

    dipendente = st.selectbox(
        "Il tuo nome",
        options=DIPENDENTI,
        index=None,
        placeholder="Seleziona il tuo nome…",
        key="dip_nome",
    )
    if not dipendente:
        st.info("Seleziona il tuo nome per iniziare.")
        return

    anno, settimana = selettore_settimana("dip")
    dal, al = dm.week_bounds_label(anno, settimana)
    giorni_settimana = dm.week_days(anno, settimana)

    # ---- Carica i dati salvati e pre-popola lo stato dei widget ----
    prefix = f"ts|{dipendente}|{anno}|{settimana}|"
    salvati = dm.get_week(anno, settimana, dipendente)

    for iso_day, rec in salvati.items():
        seeds = {
            f"{prefix}{iso_day}|t1i": parse_time(rec["turno1_inizio"]),
            f"{prefix}{iso_day}|t1f": parse_time(rec["turno1_fine"]),
            f"{prefix}{iso_day}|t2i": parse_time(rec["turno2_inizio"]),
            f"{prefix}{iso_day}|t2f": parse_time(rec["turno2_fine"]),
            f"{prefix}{iso_day}|stra": float(rec["ore_stra"] or 0.0),
            f"{prefix}{iso_day}|viaggio": float(rec["ore_viaggio"] or 0.0),
            f"{prefix}{iso_day}|mezzo": rec["mezzo"] or "",
            f"{prefix}{iso_day}|pranzo": bool(rec["pranzo"]),
            f"{prefix}{iso_day}|trasf": bool(rec["trasferta"]),
            f"{prefix}{iso_day}|cliente": rec["cliente"] or "",
            f"{prefix}{iso_day}|collega": rec["collega"] or "",
        }
        for k, v in seeds.items():
            if k not in st.session_state:
                st.session_state[k] = v

    st.caption("Compila i giorni lavorati. Il totale ore si calcola da solo.")

    # ---- Card per ogni giorno ----
    tot_settimana_min = 0
    for idx, d in enumerate(giorni_settimana):
        iso_day = d.isoformat()
        k = lambda campo: f"{prefix}{iso_day}|{campo}"  # noqa: E731

        with st.container(border=True):
            st.markdown(
                f"<div class='tk-day-title'>{GIORNI_NOME[idx]} {d.strftime('%d/%m')}"
                f" &nbsp;·&nbsp; giorno {d.day}</div>",
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2)
            with c1:
                st.time_input("1° turno — DALLE ORE", key=k("t1i"), step=timedelta(minutes=15))
                st.time_input("2° turno — DALLE ORE", key=k("t2i"), step=timedelta(minutes=15))
            with c2:
                st.time_input("1° turno — ALLE ORE", key=k("t1f"), step=timedelta(minutes=15))
                st.time_input("2° turno — ALLE ORE", key=k("t2f"), step=timedelta(minutes=15))

            c3, c4 = st.columns(2)
            with c3:
                st.number_input("ORE STRA. (straordinari)", min_value=0.0, max_value=24.0,
                                step=0.5, key=k("stra"))
            with c4:
                st.number_input("ORE VIAGGIO", min_value=0.0, max_value=24.0,
                                step=0.5, key=k("viaggio"))

            # Mezzo: menu a tendina; se il valore salvato non è in lista lo aggiungiamo
            opzioni_mezzi = list(MEZZI)
            if st.session_state[k("mezzo")] not in opzioni_mezzi:
                opzioni_mezzi.append(st.session_state[k("mezzo")])
            st.selectbox(
                "MEZZO (veicolo aziendale)",
                options=opzioni_mezzi,
                key=k("mezzo"),
                format_func=lambda v: v if v else "— nessuno —",
            )

            c5, c6 = st.columns(2)
            with c5:
                st.toggle("🍽️ PRANZO", key=k("pranzo"))
            with c6:
                st.toggle("🧳 TRASFERTA", key=k("trasf"))

            st.text_input("CLIENTE / cantiere", key=k("cliente"),
                          placeholder="Es. Cantiere Rossi — Varese")
            st.text_input("COLLEGA in squadra", key=k("collega"),
                          placeholder="Es. Bianchi")

            # Totale giorno calcolato in automatico
            rec_tmp = {
                "turno1_inizio": time_to_str(st.session_state[k("t1i")]),
                "turno1_fine": time_to_str(st.session_state[k("t1f")]),
                "turno2_inizio": time_to_str(st.session_state[k("t2i")]),
                "turno2_fine": time_to_str(st.session_state[k("t2f")]),
            }
            tot_min = dm.day_total_minutes(rec_tmp)
            tot_settimana_min += tot_min
            st.markdown(
                f"<span class='tk-badge'>TOTALE ORE: {dm.fmt_hhmm(tot_min)}</span>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(
        f"<h3 style='text-align:center'>Totale settimana: "
        f"<span class='tk-badge'>{dm.fmt_hhmm(tot_settimana_min)}</span></h3>",
        unsafe_allow_html=True,
    )

    # ---- Raccolta dati correnti dai widget ----
    def dati_correnti() -> dict:
        out = {}
        for d in giorni_settimana:
            iso_day = d.isoformat()
            kk = lambda campo: f"{prefix}{iso_day}|{campo}"  # noqa: E731
            out[iso_day] = {
                "turno1_inizio": time_to_str(st.session_state[kk("t1i")]),
                "turno1_fine": time_to_str(st.session_state[kk("t1f")]),
                "turno2_inizio": time_to_str(st.session_state[kk("t2i")]),
                "turno2_fine": time_to_str(st.session_state[kk("t2f")]),
                "ore_stra": float(st.session_state[kk("stra")]),
                "ore_viaggio": float(st.session_state[kk("viaggio")]),
                "mezzo": st.session_state[kk("mezzo")].strip(),
                "pranzo": bool(st.session_state[kk("pranzo")]),
                "trasferta": bool(st.session_state[kk("trasf")]),
                "cliente": st.session_state[kk("cliente")].strip(),
                "collega": st.session_state[kk("collega")].strip(),
            }
        return out

    # ---- Azioni ----
    if st.button("💾 SALVA SETTIMANA", type="primary", use_container_width=True):
        avviso = dm.save_week(anno, settimana, dipendente, dati_correnti(),
                              github_cfg=github_cfg_da_secrets())
        st.success(f"Foglio ore salvato — settimana dal {dal} al {al}.")
        if avviso:
            st.warning(avviso)

    pdf_bytes = pdfgen.generate_week_pdf(anno, settimana, dipendente, dati_correnti())
    st.download_button(
        "📄 ESPORTA PDF SETTIMANALE",
        data=pdf_bytes,
        file_name=f"foglio_ore_{dipendente.lower()}_settimana_{settimana}_{anno}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    testo_wa = (
        f"Ciao, ho compilato il foglio ore per la settimana dal {dal} al {al}. "
        f"— {dipendente} (Teknoimpianti)"
    )
    st.link_button(
        "🟢 NOTIFICA SU WHATSAPP",
        f"https://wa.me/?text={urllib.parse.quote(testo_wa)}",
        use_container_width=True,
    )
    st.caption(
        "WhatsApp non permette di allegare file da link: scarica prima il PDF, "
        "poi allegalo al messaggio precompilato."
    )

    # ---- Archivio personale: SOLO i documenti del dipendente selezionato ----
    st.divider()
    st.markdown("#### 📂 I miei fogli ore salvati")
    archivio = dm.list_saved_weeks(dipendente)
    if not archivio:
        st.caption("Nessun foglio salvato finora. Usa «SALVA SETTIMANA» qui sopra.")
    else:
        for a_anno, a_sett, _ in archivio[:26]:  # ultime ~26 settimane
            a_dal, a_al = dm.week_bounds_label(a_anno, a_sett)
            giorni_arch = dm.get_week(a_anno, a_sett, dipendente)
            tot_min = sum(dm.day_total_minutes(r) for r in giorni_arch.values())
            compilati = dm.week_completion(giorni_arch)
            with st.expander(
                f"Settimana {a_sett}/{a_anno} — dal {a_dal} al {a_al} "
                f"· {dm.fmt_hhmm(tot_min)} · {compilati}/6 giorni"
            ):
                st.download_button(
                    "📄 Scarica PDF",
                    data=pdfgen.generate_week_pdf(a_anno, a_sett, dipendente, giorni_arch),
                    file_name=(
                        f"foglio_ore_{dipendente.split()[-1].lower()}"
                        f"_settimana_{a_sett}_{a_anno}.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"arch_{dipendente}_{a_anno}_{a_sett}",
                )
        if len(archivio) > 26:
            st.caption(f"…e altre {len(archivio) - 26} settimane più vecchie in archivio.")


# ============================================================================
# VISTA AMMINISTRATORE
# ============================================================================

def _tabella_settimana(anno: int, settimana: int, giorni: dict) -> pd.DataFrame:
    righe = []
    for idx, d in enumerate(dm.week_days(anno, settimana)):
        rec = giorni.get(d.isoformat(), dict(dm.EMPTY_DAY))
        tot = dm.day_total_minutes(rec)
        righe.append({
            "N.": d.day,
            "GG": GIORNI_SIGLA[idx],
            "Dalle (1°)": rec.get("turno1_inizio") or "",
            "Alle (1°)": rec.get("turno1_fine") or "",
            "Dalle (2°)": rec.get("turno2_inizio") or "",
            "Alle (2°)": rec.get("turno2_fine") or "",
            "Totale": dm.fmt_hhmm(tot) if tot else "",
            "Stra.": rec.get("ore_stra") or "",
            "Viaggio": rec.get("ore_viaggio") or "",
            "Mezzo": rec.get("mezzo") or "",
            "Pranzo": "SI" if rec.get("pranzo") else "NO",
            "Trasf.": "SI" if rec.get("trasferta") else "NO",
            "Cliente": rec.get("cliente") or "",
            "Collega": rec.get("collega") or "",
        })
    return pd.DataFrame(righe)


def vista_amministratore() -> None:
    st.subheader("🔐 Dashboard Amministratore")

    # ---- Login con PIN (solo da Secrets: mai nel codice su GitHub) ----
    if not st.session_state.get("admin_ok"):
        pin_atteso = leggi_secret("admin_pin", None)
        if not pin_atteso:
            st.error(
                "🔒 PIN amministratore non configurato.\n\n"
                "Su Streamlit Cloud: **App → Settings → Secrets** e aggiungi\n\n"
                "```toml\nadmin_pin = \"1234\"\n```\n\n"
                "In locale: crea il file `.streamlit/secrets.toml` con la stessa riga "
                "(il file è escluso da git, quindi il PIN non finirà mai su GitHub)."
            )
            return
        pin_atteso = str(pin_atteso)
        with st.form("login_admin"):
            pin = st.text_input("PIN amministratore", type="password",
                                placeholder="Inserisci il PIN…")
            invia = st.form_submit_button("ACCEDI", type="primary",
                                          use_container_width=True)
        if invia:
            if pin == pin_atteso:
                st.session_state["admin_ok"] = True
                st.rerun()
            else:
                st.error("PIN errato.")
        return

    col_a, col_b = st.columns([3, 1])
    with col_b:
        if st.button("Esci 🔓", use_container_width=True):
            st.session_state["admin_ok"] = False
            st.rerun()

    with col_a:
        anno, settimana = selettore_settimana("adm")

    dati = dm.get_all_week(anno, settimana, DIPENDENTI)

    # ---- Riepilogo stato compilazione ----
    st.markdown("#### Stato compilazione settimana")
    cols = st.columns(len(DIPENDENTI))
    for col, emp in zip(cols, DIPENDENTI):
        giorni = dati[emp]
        compilati = dm.week_completion(giorni)
        tot_min = sum(dm.day_total_minutes(r) for r in giorni.values())
        icona = "✅" if compilati == 6 else ("🟡" if compilati else "🔴")
        col.metric(
            label=f"{icona} {emp}",
            value=dm.fmt_hhmm(tot_min),
            delta=f"{compilati}/6 giorni",
            delta_color="off",
        )

    st.divider()

    # ---- Dettaglio per dipendente ----
    tabs = st.tabs([f"👤 {e}" for e in DIPENDENTI])
    for tab, emp in zip(tabs, DIPENDENTI):
        with tab:
            giorni = dati[emp]
            st.dataframe(
                _tabella_settimana(anno, settimana, giorni),
                use_container_width=True,
                hide_index=True,
            )
            stra = sum(float(r.get("ore_stra") or 0) for r in giorni.values())
            viaggio = sum(float(r.get("ore_viaggio") or 0) for r in giorni.values())
            tot_min = sum(dm.day_total_minutes(r) for r in giorni.values())
            st.markdown(
                f"**Totale: {dm.fmt_hhmm(tot_min)}** &nbsp;·&nbsp; "
                f"Straordinari: **{stra:g} h** &nbsp;·&nbsp; "
                f"Viaggio: **{viaggio:g} h**"
            )
            st.download_button(
                f"📄 Scarica PDF di {emp}",
                data=pdfgen.generate_week_pdf(anno, settimana, emp, giorni),
                file_name=f"foglio_ore_{emp.lower()}_settimana_{settimana}_{anno}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"pdf_{emp}",
            )

    st.divider()
    st.download_button(
        "📚 SCARICA REPORT CUMULATIVO (tutti i dipendenti)",
        data=pdfgen.generate_admin_report(anno, settimana, dati),
        file_name=f"report_fogli_ore_settimana_{settimana}_{anno}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

    # ---- Archivio completo: TUTTI i documenti di TUTTI i dipendenti ----
    st.divider()
    st.markdown("#### 📂 Archivio completo fogli ore")
    archivio = dm.list_saved_weeks()  # nessun filtro: l'admin vede tutto
    if not archivio:
        st.caption("Archivio vuoto: nessun foglio salvato finora.")
    else:
        # Raggruppa per settimana (più recente in alto)
        settimane: dict[tuple[int, int], list[str]] = {}
        for a_anno, a_sett, emp in archivio:
            settimane.setdefault((a_anno, a_sett), []).append(emp)

        for (a_anno, a_sett), emps in list(settimane.items())[:30]:
            a_dal, a_al = dm.week_bounds_label(a_anno, a_sett)
            with st.expander(
                f"Settimana {a_sett}/{a_anno} — dal {a_dal} al {a_al} "
                f"· {len(emps)} dipendenti"
            ):
                for emp in sorted(emps):
                    giorni_arch = dm.get_week(a_anno, a_sett, emp)
                    tot_min = sum(dm.day_total_minutes(r) for r in giorni_arch.values())
                    compilati = dm.week_completion(giorni_arch)
                    c_info, c_btn = st.columns([2, 1])
                    with c_info:
                        st.markdown(
                            f"**{emp}** — {dm.fmt_hhmm(tot_min)} · {compilati}/6 giorni"
                        )
                    with c_btn:
                        st.download_button(
                            "📄 PDF",
                            data=pdfgen.generate_week_pdf(a_anno, a_sett, emp, giorni_arch),
                            file_name=(
                                f"foglio_ore_{emp.split()[-1].lower()}"
                                f"_settimana_{a_sett}_{a_anno}.pdf"
                            ),
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"admarch_{emp}_{a_anno}_{a_sett}",
                        )
        if len(settimane) > 30:
            st.caption(f"…e altre {len(settimane) - 30} settimane più vecchie in archivio.")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    intestazione()

    ruolo = st.radio(
        "Modalità",
        options=["👷 Dipendente", "🔐 Amministratore"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if ruolo == "👷 Dipendente":
        vista_dipendente()
    else:
        vista_amministratore()

    st.divider()
    st.caption(
        "TEKNOIMPIANTI S.R.L. — Impianti civili ed industriali · Quadri di "
        "distribuzione e di controllo · Automazione — Venegono Inferiore (VA)"
    )


if __name__ == "__main__":
    main()
