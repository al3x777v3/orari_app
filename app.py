from nicegui import ui, app
from datetime import datetime, time, timedelta
import os, json

# ---------- PATHS ----------
# Montiamo una cartella statica servita dall'app: /static -> ./static
# Così le immagini restano visibili anche dopo il refresh

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'static')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
SEED_FILE = os.path.join(BASE_DIR, 'seed_data.json')
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.add_static_files('/static', UPLOAD_DIR)

# ---------- DATA LAYER (file JSON locale) ----------
DEFAULT_DATA = {
    'schedule_image_name': '',
    'routes': {},   # { name: { 'line': 'M6', 'times': ['07:10','08:00'] } }
    'settings': {'theme': 'auto'}
}

def load_data():
    # 1) prova a leggere data.json; 2) se manca, prova seed_data.json; 3) altrimenti DEFAULT
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif os.path.exists(SEED_FILE):
            with open(SEED_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # crea data.json dalla seed al primo avvio
                save_data(data)
                return data
        else:
            return DEFAULT_DATA.copy()
    except Exception:
        return DEFAULT_DATA.copy()


def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        ui.notify(f'Errore salvataggio: {e}', type='negative')

# in memoria
DATA = load_data()

# ---------- HELPERS ----------

def parse_times(text: str):
    tokens = [t.strip() for t in text.replace('\n', ' ').replace(',', ' ').split(' ') if t.strip()]
    times = []
    for tok in tokens:
        try:
            h, m = tok.split(':')
            t = time(hour=int(h), minute=int(m))
            times.append(t)
        except Exception:
            pass
    times = sorted(set(times))
    return times


def times_to_str(times):
    return ', '.join(t.strftime('%H:%M') for t in times)


def now_local():
    return datetime.now().astimezone()


def next_times(times, n=5, from_dt=None):
    if from_dt is None:
        from_dt = now_local()
    today = from_dt.date()
    dts = []
    for t in times:
        dt = datetime.combine(today, t, from_dt.tzinfo)
        if dt < from_dt:
            dt += timedelta(days=1)
        dts.append(dt)
    dts.sort()
    return dts[:n]

# ---------- UI ----------
ui.colors(primary='#2563eb', secondary='#0ea5e9')
ui.markdown('# Orari lezioni + autobus')
ui.label('App minimale per avere a portata di mano orario lezioni (immagine) e prossime corse dei bus per le tratte che usi.').classes('text-sm text-gray-600')

with ui.tabs().classes('w-full') as tabs:
    tab_orario = ui.tab('Orario lezioni')
    tab_bus = ui.tab('Autobus')
    tab_impostazioni = ui.tab('Impostazioni')

with ui.tab_panels(tabs, value=tab_orario).classes('w-full'):
    # ---- TAB: ORARIO ----
    with ui.tab_panel(tab_orario):
        ui.markdown('### Immagine orario lezioni')
        img = ui.image().classes('w-full max-w-3xl rounded-xl shadow')

        def refresh_image():
            name = DATA.get('schedule_image_name', '')
            if name:
                img.set_source(f'/static/{name}')
            else:
                img.set_source('')
        refresh_image()

        def on_upload(e):
            # NiceGUI >= 2: e è UploadEventArguments, usa e.content (BytesIO)
            filename = e.name
            safe = filename.replace(' ', '_')
            dest = os.path.join(UPLOAD_DIR, safe)
            try:
                # scrivi i bytes sul disco
                with open(dest, 'wb') as f:
                    f.write(e.content.read())
                # reset del cursore per eventuali usi successivi
                try:
                    e.content.seek(0)
                except Exception:
                    pass
                DATA['schedule_image_name'] = safe
                save_data(DATA)
                refresh_image()
                ui.notify('Orario aggiornato!', type='positive')
            except Exception as ex:
                ui.notify(f'Errore upload: {ex}', type='negative')
            ui.notify('Orario aggiornato!', type='positive')

        ui.upload(on_upload=on_upload, label='Carica/aggiorna immagine orario (PNG/JPG)').props('accept="image/*"')
        ui.separator()
        ui.markdown('**Suggerimento:** fai uno screenshot del calendario lezioni ufficiale e caricalo qui. I dati sono salvati nel file `data.json` accanto all\'app.')

    # ---- TAB: AUTOBUS ----
    with ui.tab_panel(tab_bus):
        ui.markdown('### Tratte e orari')

        with ui.row().classes('items-center gap-4'):
            route_name = ui.input('Nome tratta (es. Casa → Terminal)')
            route_line = ui.input('Linea/numero bus (es. M6)')
        times_area = ui.textarea('Orari (HH:MM separati da spazio o virgola)').props('rows=4')

        @ui.refreshable
        def routes_list():
            ui.separator()
            routes = DATA.get('routes', {})
            if not routes:
                ui.label('Nessuna tratta salvata. Aggiungine una sopra.').classes('text-gray-500')
                return
            for name, info in routes.items():
                with ui.card().classes('w-full max-w-3xl'):
                    ui.label(f'{name} — Linea {info.get("line")}').classes('font-bold')
                    ui.label(times_to_str([time.fromisoformat(t) for t in info.get('times', [])]))
                    with ui.row().classes('gap-2 mt-2'):
                        def make_show_next(nm=name):
                            def _():
                                times = [time.fromisoformat(t) for t in DATA['routes'][nm]['times']]
                                upcoming = next_times(times)
                                with ui.dialog() as d:
                                    with ui.card():
                                        ui.label(f'Prossime corse: {nm}').classes('font-bold')
                                        for dt in upcoming:
                                            ui.label(dt.strftime('%a %d/%m %H:%M'))
                                        ui.button('Chiudi', on_click=d.close)
                                    d.open()
                            return _
                        ui.button('Prossime corse', on_click=make_show_next())
                        def make_delete(nm=name):
                            def _():
                                DATA['routes'].pop(nm, None)
                                save_data(DATA)
                                routes_list.refresh()
                                update_selects()
                                ui.notify('Tratta eliminata', type='warning')
                            return _
                        ui.button('Elimina', on_click=make_delete())

        routes_list()

        # --- Selects per andata/ritorno (no lambda) ---
        route_names = list(DATA.get('routes', {}).keys())
        sel_out = ui.select(route_names, label='1ª tratta (es. Casa → Terminal)')
        sel_out2 = ui.select(route_names, label='2ª tratta (es. Terminal → Uni)')
        n_input = ui.number('Quante corse mostrare', value=5, min=1, max=10)

        def update_selects():
            names = list(DATA.get('routes', {}).keys())
            sel_out.set_options(names)
            sel_out2.set_options(names)

        @ui.refreshable
        def compute_panel():
            ui.separator()
            if not sel_out.value or not sel_out2.value:
                ui.label('Scegli entrambe le tratte per calcolare.').classes('text-gray-500')
                return
            t1 = [time.fromisoformat(t) for t in DATA['routes'][sel_out.value]['times']]
            t2 = [time.fromisoformat(t) for t in DATA['routes'][sel_out2.value]['times']]
            upcoming1 = next_times(t1, n=n_input.value)
            upcoming2 = next_times(t2, n=n_input.value)
            with ui.row().classes('gap-8'):
                with ui.card():
                    ui.label(sel_out.value).classes('font-bold')
                    for dt in upcoming1:
                        ui.label(dt.strftime('%a %d/%m %H:%M'))
                with ui.card():
                    ui.label(sel_out2.value).classes('font-bold')
                    for dt in upcoming2:
                        ui.label(dt.strftime('%a %d/%m %H:%M'))

        def add_route():
            name = route_name.value.strip()
            line = route_line.value.strip()
            times = parse_times(times_area.value or '')
            if not name or not times:
                ui.notify('Inserisci almeno nome tratta e orari validi (HH:MM).', type='warning')
                return
            DATA.setdefault('routes', {})[name] = {
                'line': line or '-',
                'times': [t.isoformat(timespec='minutes') for t in times],
            }
            save_data(DATA)
            route_name.value = ''
            route_line.value = ''
            times_area.value = ''
            routes_list.refresh()
            update_selects()
            ui.notify('Tratta salvata!', type='positive')

        ui.button('Salva tratta', on_click=add_route).classes('mt-2')

        ui.separator()
        ui.markdown('#### Calcola le prossime corse per andata/ritorno')
        compute_panel()
        ui.button('Calcola/aggiorna', on_click=compute_panel.refresh)

    # ---- TAB: IMPOSTAZIONI ----
    with ui.tab_panel(tab_impostazioni):
        ui.markdown('### Impostazioni')
        theme = ui.select(['auto', 'chiaro', 'scuro'], label='Tema', value=DATA.get('settings', {}).get('theme', 'auto'))

        def save_settings_tab():
            DATA.setdefault('settings', {})['theme'] = theme.value
            save_data(DATA)
            ui.notify('Impostazioni salvate.', type='positive')

        ui.button('Salva', on_click=save_settings_tab)
        ui.label('I dati sono salvati nel file `data.json` accanto all\'app.').classes('text-gray-600')

@ui.refreshable
def clock():
    ui.label(now_local().strftime('Ora attuale: %a %d/%m %H:%M')).classes('text-xs text-gray-500')
clock()
ui.timer(60, clock.refresh)

port = int(os.environ.get('PORT', 10000))
ui.run(title='Lezioni + Autobus', host='0.0.0.0', port=port)

