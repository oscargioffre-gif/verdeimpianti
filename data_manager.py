"""
data_manager.py — Persistenza dati su file JSON per TEKNOIMPIANTI S.R.L.
=========================================================================
Struttura del file JSON:

{
  "2026": {
    "29": {
      "Todaro": {
        "2026-07-13": {
          "turno1_inizio": "08:00", "turno1_fine": "12:00",
          "turno2_inizio": "13:00", "turno2_fine": "17:00",
          "ore_stra": 0.0, "ore_viaggio": 1.5,
          "mezzo": "Furgone Ducato",
          "pranzo": true, "trasferta": false,
          "cliente": "Cantiere XYZ", "collega": "Rossi"
        },
        ...
      }
    }
  }
}

Anno -> Settimana ISO -> Dipendente -> Data (YYYY-MM-DD) -> record giornaliero.

La scrittura è ATOMICA (file temporaneo + os.replace) e protetta da un
file-lock inter-processo (libreria `filelock`), quindi due sessioni
Streamlit concorrenti non possono corrompere il file.

Sync GitHub (opzionale, consigliato su Streamlit Community Cloud):
lo storage di Streamlit Cloud è EFFIMERO — a ogni riavvio dell'app il
filesystem torna allo stato della repository. Se in `.streamlit/secrets.toml`
sono presenti le chiavi:

    [github]
    token = "ghp_..."         # Personal Access Token con permesso `repo`
    repo  = "utente/nome-repo"
    branch = "main"           # opzionale, default "main"

ogni salvataggio viene anche committato su GitHub, rendendo i dati
permanenti. Senza secrets l'app funziona comunque in locale.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from filelock import FileLock

# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "timesheet_data.json"
LOCK_FILE = BASE_DIR / "timesheet_data.json.lock"

# Campi di un record giornaliero e loro valori di default
EMPTY_DAY: Dict[str, Any] = {
    "turno1_inizio": None,
    "turno1_fine": None,
    "turno2_inizio": None,
    "turno2_fine": None,
    "ore_stra": 0.0,
    "ore_viaggio": 0.0,
    "mezzo": "",
    "pranzo": False,
    "trasferta": False,
    "cliente": "",
    "collega": "",
}


# --------------------------------------------------------------------------
# Utilità settimana
# --------------------------------------------------------------------------

def week_days(year: int, week: int) -> list[date]:
    """Le 6 date (lunedì→sabato) della settimana ISO richiesta."""
    monday = date.fromisocalendar(year, week, 1)
    return [monday + timedelta(days=i) for i in range(6)]


def week_bounds_label(year: int, week: int) -> tuple[str, str]:
    """Estremi settimana in formato italiano: ('13/07/2026', '18/07/2026')."""
    days = week_days(year, week)
    return days[0].strftime("%d/%m/%Y"), days[-1].strftime("%d/%m/%Y")


# --------------------------------------------------------------------------
# Lettura / scrittura di basso livello (atomica + lock)
# --------------------------------------------------------------------------

def _read_raw() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        # File corrotto o illeggibile: non distruggere nulla, riparti da zero
        # tenendo una copia di backup del file danneggiato.
        try:
            DATA_FILE.rename(DATA_FILE.with_suffix(".json.corrotto"))
        except OSError:
            pass
        return {}


def _write_raw(data: Dict[str, Any]) -> None:
    """Scrittura atomica: file temporaneo nella stessa dir + os.replace."""
    fd, tmp_path = tempfile.mkstemp(dir=str(BASE_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, DATA_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def load_data() -> Dict[str, Any]:
    """Carica l'intero archivio (thread/process-safe)."""
    with FileLock(str(LOCK_FILE), timeout=10):
        return _read_raw()


def save_data(data: Dict[str, Any]) -> None:
    """Salva l'intero archivio (thread/process-safe)."""
    with FileLock(str(LOCK_FILE), timeout=10):
        _write_raw(data)


# --------------------------------------------------------------------------
# API di alto livello
# --------------------------------------------------------------------------

def get_week(year: int, week: int, employee: str) -> Dict[str, Dict[str, Any]]:
    """Restituisce { 'YYYY-MM-DD': record } per la settimana del dipendente.

    I giorni mancanti vengono restituiti con i valori di default, così la
    UI ha sempre 6 giorni completi su cui lavorare.
    """
    data = load_data()
    stored = (
        data.get(str(year), {})
        .get(str(week), {})
        .get(employee, {})
    )
    out: Dict[str, Dict[str, Any]] = {}
    for d in week_days(year, week):
        key = d.isoformat()
        record = dict(EMPTY_DAY)
        record.update(stored.get(key, {}))
        out[key] = record
    return out


def save_week(
    year: int,
    week: int,
    employee: str,
    days: Dict[str, Dict[str, Any]],
    github_cfg: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Salva la settimana di UN dipendente senza toccare i dati altrui.

    Il lock copre l'intero ciclo read-modify-write, quindi salvataggi
    concorrenti di dipendenti diversi non si sovrascrivono a vicenda.

    Ritorna un messaggio di avviso (str) se il sync GitHub fallisce,
    altrimenti None.
    """
    with FileLock(str(LOCK_FILE), timeout=10):
        data = _read_raw()
        data.setdefault(str(year), {}).setdefault(str(week), {})[employee] = days
        _write_raw(data)
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)

    if github_cfg and github_cfg.get("token") and github_cfg.get("repo"):
        return _push_to_github(payload, github_cfg)
    return None


def get_all_week(year: int, week: int, employees: list[str]) -> Dict[str, Dict[str, Any]]:
    """Vista amministratore: { dipendente: {data: record} } per la settimana."""
    return {emp: get_week(year, week, emp) for emp in employees}


def week_completion(days: Dict[str, Dict[str, Any]]) -> int:
    """Numero di giorni della settimana con almeno il primo turno compilato."""
    return sum(
        1 for rec in days.values()
        if rec.get("turno1_inizio") and rec.get("turno1_fine")
    )


def list_saved_weeks(employee: Optional[str] = None) -> list[tuple[int, int, str]]:
    """Elenco (anno, settimana, dipendente) di tutti i fogli salvati,
    dal più recente al più vecchio. Con `employee` filtra un solo dipendente
    (usato dalla vista dipendente per mostrare SOLO i propri documenti)."""
    data = load_data()
    out: list[tuple[int, int, str]] = []
    for y, weeks in data.items():
        for w, emps in weeks.items():
            for emp in emps:
                if employee is None or emp == employee:
                    try:
                        out.append((int(y), int(w), emp))
                    except ValueError:
                        continue
    return sorted(out, key=lambda t: (t[0], t[1], t[2]), reverse=True)


# --------------------------------------------------------------------------
# Sync GitHub opzionale (persistenza permanente su Streamlit Cloud)
# --------------------------------------------------------------------------

def _push_to_github(content: str, cfg: Dict[str, str]) -> Optional[str]:
    """Committa timesheet_data.json nella repo. Best-effort: in caso di
    errore ritorna il messaggio, senza far fallire il salvataggio locale."""
    try:
        import requests

        token = cfg["token"]
        repo = cfg["repo"]
        branch = cfg.get("branch", "main")
        api = f"https://api.github.com/repos/{repo}/contents/timesheet_data.json"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        # SHA del file esistente (necessario per l'update)
        sha = None
        r = requests.get(api, headers=headers, params={"ref": branch}, timeout=15)
        if r.status_code == 200:
            sha = r.json().get("sha")

        body = {
            "message": "Aggiornamento foglio ore (salvataggio da app)",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        r = requests.put(api, headers=headers, json=body, timeout=15)
        if r.status_code not in (200, 201):
            return f"Sync GitHub non riuscito (HTTP {r.status_code}): i dati sono salvati solo localmente."
        return None
    except Exception as exc:  # noqa: BLE001 — il salvataggio locale è già riuscito
        return f"Sync GitHub non riuscito ({exc}): i dati sono salvati solo localmente."


# --------------------------------------------------------------------------
# Calcolo ore
# --------------------------------------------------------------------------

def _minutes(hhmm: Optional[str]) -> Optional[int]:
    if not hhmm:
        return None
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def shift_minutes(start: Optional[str], end: Optional[str]) -> int:
    """Durata di un turno in minuti. Turni a cavallo di mezzanotte gestiti."""
    s, e = _minutes(start), _minutes(end)
    if s is None or e is None:
        return 0
    if e < s:  # turno notturno oltre mezzanotte
        e += 24 * 60
    return e - s


def day_total_minutes(rec: Dict[str, Any]) -> int:
    return (
        shift_minutes(rec.get("turno1_inizio"), rec.get("turno1_fine"))
        + shift_minutes(rec.get("turno2_inizio"), rec.get("turno2_fine"))
    )


def fmt_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
