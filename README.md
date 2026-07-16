# ⚡ Foglio Ore — VERDEIMPIANTI S.R.L.

App web per la gestione delle ore di lavoro settimanali, replica digitale del
modulo cartaceo aziendale. Scritta in Python + Streamlit, pronta per il deploy
gratuito su **Streamlit Community Cloud**.

## Funzionalità

**Vista Dipendente** (mobile-first, pensata per lo smartphone in cantiere)

- Selezione del proprio nome e della settimana
- Compilazione giorno per giorno (lun→sab): doppio turno, straordinari,
  ore viaggio, mezzo, pranzo, trasferta, cliente, collega
- Totale ore giornaliero e settimanale calcolati in automatico (HH:MM)
- Privacy: ogni dipendente vede e modifica SOLO il proprio foglio
- Salvataggio settimana ed esportazione PDF

**Vista Amministratore** (protetta da PIN)

- Stato di compilazione di tutti i dipendenti in un'unica schermata
- Selezione di qualunque settimana dell'anno
- Dettaglio per dipendente in tab dedicati
- Download del PDF di ogni dipendente o del report cumulativo

**PDF**: replica esatta del modulo cartaceo (A4 orizzontale, griglia, firme).

## Struttura del progetto

```
app.py                     # interfaccia Streamlit e logica delle viste
data_manager.py            # persistenza JSON (atomica, con file-lock)
pdf_generator.py           # generazione PDF con ReportLab
requirements.txt           # dipendenze
assets/logo.png|svg        # logo aziendale
.streamlit/config.toml     # tema brand Verdeimpianti
.streamlit/secrets.toml.example  # modello per PIN e sync GitHub
timesheet_data.json        # archivio dati (creato al primo salvataggio)
```

## Avvio in locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy su Streamlit Community Cloud (gratuito)

1. Crea una repository GitHub (es. `verdeimpianti-foglio-ore`) e carica
   tutti i file del progetto.
2. Vai su [share.streamlit.io](https://share.streamlit.io), accedi con
   GitHub e scegli **New app** → seleziona la repo, branch `main`,
   file `app.py` → **Deploy**.
3. In *App → Settings → Secrets* incolla almeno (OBBLIGATORIO — il PIN non è
   scritto nel codice per non esporlo su GitHub; senza questo secret la
   dashboard amministratore resta bloccata):

   ```toml
   admin_pin = "1234"
   ```

### ⚠️ Persistenza dei dati su Streamlit Cloud

Lo storage di Streamlit Cloud è **effimero**: a ogni riavvio dell'app
(riavvii automatici, nuovi deploy) il filesystem torna allo stato della
repository e le modifiche a `timesheet_data.json` andrebbero perse.

Soluzione integrata: aggiungi ai Secrets anche

```toml
[github]
token  = "ghp_xxxxxxxxxxxx"   # Personal Access Token con scope `repo`
repo   = "tuo-utente/verdeimpianti-foglio-ore"
branch = "main"
```

e ogni salvataggio verrà **committato automaticamente nella repository**,
rendendo i dati permanenti. (Token: GitHub → Settings → Developer settings →
Personal access tokens.)

## Personalizzazione

- **Dipendenti**: modifica la lista `DIPENDENTI` in cima ad `app.py`
- **Mezzi aziendali**: lista `MEZZI` in `app.py`
- **PIN amministratore**: SOLO nei Secrets (`admin_pin`), mai nel codice
- **Tema grafico**: 3 stili dark pronti in `TEMI` dentro `app.py`
  (attivo: 1 — Enterprise Dark; cambia la variabile d'ambiente `TEKNO_TEMA`
  o il default, e allinea i colori in `.streamlit/config.toml`)

## Archivio documenti

Ogni salvataggio resta archiviato per sempre in `timesheet_data.json`
(con sync GitHub attivo: committato nella repo). In fondo alla pagina:

- il **dipendente** vede «I miei fogli ore salvati» — SOLO i propri, con PDF
- l'**amministratore** vede l'«Archivio completo» di tutti i dipendenti
