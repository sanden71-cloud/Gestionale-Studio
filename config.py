# --- Costanti e definizioni colonne (VLEKT PRO) ---

# Versione app: MAJOR=breaking, MINOR=nuove funzionalità, PATCH=bugfix (dettagli in VERSIONING.md)
VERSION = "1.0.0"
APP_NAME = "VLEKT PRO"

# URL che restituisce la versione più recente (solo testo, es. "1.1.0"). Vuoto = Controlla aggiornamenti disattivato.
# Usa il file latest_version.txt in repo GitHub (raw). Se repo/branch diversi, aggiorna qui.
CHECK_UPDATE_URL = "https://raw.githubusercontent.com/alessandrodente/Studio_AD/main/latest_version.txt"

LISTA_PASTI_UOMO = ['Colazione', 'Spuntino Mattina', 'Pranzo', 'Merenda', 'Cena', 'Dopo Cena']
LISTA_PASTI_DONNA = ['Colazione', 'Spuntino/Merenda', 'Pranzo', 'Cena']
LISTA_PASTI = LISTA_PASTI_UOMO
ORDINE_PASTI = {p: i for i, p in enumerate(LISTA_PASTI_UOMO + ['Spuntino/Merenda'])}

lista_laf = [
    "1.2 - Sedentario",
    "1.375 - Leggermente Attivo",
    "1.55 - Moderatamente Attivo",
    "1.725 - Molto Attivo",
    "1.9 - Estremamente Attivo",
]

COLS_PAZ = [
    'Data_Visita', 'Nome', 'Cognome', 'Codice_Fiscale', 'Data_Nascita',
    'Luogo_Nascita', 'Indirizzo', 'Sesso', 'Cellulare', 'Email', 'Altezza', 'Peso', 'BMI',
    'Addome', 'Fianchi', 'Torace', 'Polso',
    'Analisi_Cliniche', 'Farmaci', 'Note', 'LAF', 'Peso_Target',
    'Circ_Polso_Dx', 'Circ_Polso_Sx',
    'Circ_Avambraccio_Dx', 'Circ_Avambraccio_Sx',
    'Circ_Braccio_Dx', 'Circ_Braccio_Sx',
    'Circ_Spalle', 'Circ_Torace_Ant', 'Circ_Vita', 'Circ_Addome_Ant', 'Circ_Fianchi_Ant',
    'Circ_Coscia_Prox_Dx', 'Circ_Coscia_Prox_Sx',
    'Circ_Coscia_Med_Dx', 'Circ_Coscia_Med_Sx',
    'Circ_Coscia_Dist_Dx', 'Circ_Coscia_Dist_Sx',
    'Circ_Polpaccio_Dx', 'Circ_Polpaccio_Sx',
    'Circ_Caviglia_Dx', 'Circ_Caviglia_Sx',
    'Plica_Avambraccio', 'Plica_Bicipitale', 'Plica_Tricipitale', 'Plica_Ascellare',
    'Plica_Pettorale', 'Plica_Sottoscapolare', 'Plica_Addominale', 'Plica_Soprailiaca',
    'Plica_Coscia_Med', 'Plica_Soprapatellare', 'Plica_Polpaccio_Med', 'Plica_Sopraspinale',
    'Diam_Polso', 'Diam_Gomito', 'Diam_Biacromiale',
    'Diam_Toracico', 'Diam_Bicrestale', 'Diam_Addominale_Sag',
    'Diam_Bitrocanterio', 'Diam_Ginocchio', 'Diam_Caviglia',
    'Note_Antropometria',
]

COLS_ALI = ['Alimento', 'Kcal', 'Carbo_Netti', 'Prot', 'Grassi', 'Porzioni_Confezione']
COLS_DIETA = ['Codice_Fiscale', 'Data_Visita', 'Step', 'Giorni', 'Pasto', 'Alimento', 'Quantita', 'Kcal_Tot', 'Carbo_Tot', 'Prot_Tot', 'Grassi_Tot']
COLS_INTEGR = ['Nome_Integratore', 'Categoria', 'Descrizione']
COLS_PRESCR = ['Codice_Fiscale', 'Data_Visita', 'Data_Inizio', 'Nome_Integratore', 'Posologia', 'Note_Prescrizione']
COLS_PROT = ['Nome', 'Categoria', 'Grammi_Porzione', 'Kcal', 'Prot', 'Grassi', 'Carbo_Netti', 'Note']

# Template PDF piani dieta
PDF_PIANI = {
    ('F', 1): 'Donna_4_pasti_Fase_1_Step_1.pdf',
    ('F', 2): 'Donna_3_pasti_Fase_1_Step_2.pdf',
    ('M', 1): 'Uomo_5_pasti_Fase_1_Step_1.pdf',
    ('M', 2): 'Uomo_4_Pasti_Fase_1_Step_2.pdf',
}

PDF_NOME_CFG = {
    ('F', 1): {'x': 54, 'y_cover_top': 131, 'y_cover_bot': 150},
    ('F', 2): {'x': 54, 'y_cover_top': 138, 'y_cover_bot': 158},
    ('M', 1): {'x': 54, 'y_cover_top': 129, 'y_cover_bot': 149},
    ('M', 2): {'x': 54, 'y_cover_top': 137, 'y_cover_bot': 160},
}
