"""
Genera il manuale del pannello admin di ManualFinder in PDF.
Output: manuale_admin_manualfinder.pdf
"""
from fpdf import FPDF
import datetime

FONT_DIR = "C:/Windows/Fonts/"

class ManualePDF(FPDF):
    def _setup_fonts(self):
        self.add_font("Arial", "",  FONT_DIR + "arial.ttf")
        self.add_font("Arial", "B", FONT_DIR + "arialbd.ttf")
        self.add_font("Arial", "I", FONT_DIR + "ariali.ttf")
        self.add_font("Arial", "BI", FONT_DIR + "arialbi.ttf")

    def header(self):
        self.set_font("Arial", "B", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 8, "ManualFinder \u2014 Manuale Pannello Admin", align="L")
        self.set_text_color(100, 116, 139)
        self.cell(0, 8, f"Pag. {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-13)
        self.set_font("Arial", "", 8)
        self.set_text_color(148, 163, 184)
        today = datetime.date.today().strftime("%d/%m/%Y")
        self.cell(0, 8, f"ManualFinder Admin \u2014 {today}", align="C")

    # ── helpers ──────────────────────────────────────────────────────────────

    def h1(self, text):
        self.ln(4)
        self.set_font("Arial", "B", 18)
        self.set_text_color(30, 41, 59)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 64, 175)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y(), self.l_margin + 40, self.get_y())
        self.ln(4)

    def h2(self, text):
        self.ln(5)
        self.set_fill_color(239, 246, 255)
        self.set_font("Arial", "B", 13)
        self.set_text_color(30, 64, 175)
        self.cell(0, 8, "  " + text, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def h3(self, text):
        self.ln(3)
        self.set_font("Arial", "B", 11)
        self.set_text_color(51, 65, 85)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def body(self, text, indent=0):
        self.set_font("Arial", "", 10)
        self.set_text_color(30, 41, 59)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 5.5, text)

    def bullet(self, text, level=0):
        indent = 6 + level * 6
        bullet_char = "\u2022" if level == 0 else "\u25e6"
        self.set_font("Arial", "", 10)
        self.set_text_color(30, 41, 59)
        x0 = self.l_margin + indent
        self.set_x(x0)
        self.cell(5, 5.5, bullet_char)
        self.multi_cell(0, 5.5, text)

    def note(self, text):
        self.ln(1)
        self.set_fill_color(255, 251, 235)
        self.set_draw_color(252, 211, 77)
        self.set_line_width(0.3)
        self.set_font("Arial", "I", 9)
        self.set_text_color(146, 64, 14)
        self.set_x(self.l_margin)
        self.multi_cell(0, 5, "  Nota: " + text, border="L", fill=True)
        self.set_draw_color(226, 232, 240)
        self.ln(2)

    def info_box(self, text):
        self.ln(1)
        self.set_fill_color(239, 246, 255)
        self.set_draw_color(147, 197, 253)
        self.set_line_width(0.3)
        self.set_font("Arial", "", 9)
        self.set_text_color(30, 64, 175)
        self.multi_cell(0, 5, "  " + text, border="L", fill=True)
        self.set_draw_color(226, 232, 240)
        self.ln(2)

    def table_header(self, cols):
        self.set_fill_color(248, 250, 252)
        self.set_font("Arial", "B", 9)
        self.set_text_color(100, 116, 139)
        for label, w in cols:
            self.cell(w, 7, label, border=1, fill=True)
        self.ln()

    def table_row(self, cells, cols, fill=False):
        self.set_font("Arial", "", 9)
        self.set_text_color(30, 41, 59)
        if fill:
            self.set_fill_color(248, 250, 252)
        else:
            self.set_fill_color(255, 255, 255)
        for i, (_, w) in enumerate(cols):
            text = cells[i] if i < len(cells) else ""
            self.cell(w, 6, text, border=1, fill=fill)
        self.ln()

    def spacer(self, h=4):
        self.ln(h)


# ── Costruzione documento ─────────────────────────────────────────────────────

pdf = ManualePDF()
pdf._setup_fonts()
pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(18, 18, 18)

# ── Copertina ─────────────────────────────────────────────────────────────────

pdf.add_page()
pdf.set_font("Arial", "B", 32)
pdf.set_text_color(30, 41, 59)
pdf.ln(20)
pdf.cell(0, 14, "ManualFinder", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Arial", "", 18)
pdf.set_text_color(100, 116, 139)
pdf.cell(0, 10, "Pannello Amministratore", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)
pdf.set_font("Arial", "", 13)
pdf.set_text_color(148, 163, 184)
pdf.cell(0, 8, "Manuale d'uso completo", align="C", new_x="LMARGIN", new_y="NEXT")

pdf.ln(16)
pdf.set_draw_color(30, 64, 175)
pdf.set_line_width(1.2)
cx = pdf.w / 2
pdf.line(cx - 30, pdf.get_y(), cx + 30, pdf.get_y())
pdf.ln(16)

pdf.set_font("Arial", "", 10)
pdf.set_text_color(100, 116, 139)
pdf.cell(0, 6, f"Versione: {datetime.date.today().strftime('%B %Y')}", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, "Accesso: http://localhost/#admin  (o dominio di produzione)", align="C", new_x="LMARGIN", new_y="NEXT")

pdf.ln(30)
pdf.set_font("Arial", "B", 11)
pdf.set_text_color(30, 41, 59)
pdf.cell(0, 7, "Indice", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

indice = [
    ("1.",  "Panoramica"),
    ("2.",  "Tab Statistiche"),
    ("3.",  "Tab Proposte"),
    ("4.",  "Tab Proposte disco"),
    ("5.",  "Tab Alias"),
    ("6.",  "Tab Flags normativi"),
    ("7.",  "Tab Ricerche"),
    ("8.",  "Tab Log scansioni"),
    ("9.",  "Tab Corpus RAG"),
    ("10.", "Tab Manuali INAIL"),
    ("11.", "Tab Normative"),
    ("12.", "Tab Riferimenti normativi"),
    ("13.", "Flusso di lavoro tipico"),
]
pdf.set_font("Arial", "", 10)
pdf.set_text_color(30, 41, 59)
for num, title in indice:
    pdf.set_x(pdf.w / 2 - 40)
    pdf.cell(12, 6, num)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")

# ── 1. PANORAMICA ─────────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("1. Panoramica")

pdf.body(
    "Il pannello admin di ManualFinder \u00e8 accessibile all'URL /#admin. "
    "Permette di gestire il catalogo dei tipi macchina, i quaderni INAIL locali, "
    "il corpus RAG e le normative tecniche senza modificare il codice sorgente."
)
pdf.spacer()
pdf.body(
    "Ogni modifica ha effetto immediato sulle schede ispettive generate dal sistema. "
    "Non \u00e8 necessario riavviare il backend."
)
pdf.spacer()

pdf.h3("Struttura del pannello")
pdf.body("Il pannello \u00e8 organizzato in 11 tab accessibili dalla barra orizzontale:")
pdf.spacer(2)

tabs = [
    ("Statistiche",        "KPI generali del catalogo"),
    ("Proposte",           "Nuovi tipi proposti dall'OCR da classificare"),
    ("Proposte disco",     "PDF rilevati su disco senza tipo associato"),
    ("Alias",              "Varianti testuali per ogni tipo canonico"),
    ("Flags normativi",    "Patentino, verifiche, vita utile, hazard, hint INAIL"),
    ("Ricerche",           "Scansioni senza manuale: genera email al produttore"),
    ("Log scansioni",      "Archivio completo di tutte le analisi"),
    ("Corpus RAG",         "Gestione del corpus normativo AI (ChromaDB)"),
    ("Manuali INAIL",      "Associazione PDF locali \u2194 tipo macchina"),
    ("Normative",          "Normative tecniche per tipo macchina"),
    ("Riferimenti",        "Articoli D.Lgs. 81/08 per tipo macchina"),
]
cols = [("Tab", 52), ("Descrizione", 120)]
pdf.table_header(cols)
for i, (tab, desc) in enumerate(tabs):
    pdf.table_row([tab, desc], cols, fill=(i % 2 == 0))

pdf.spacer(6)
pdf.info_box(
    "Nessuna autenticazione \u00e8 richiesta per accedere al pannello. "
    "Si raccomanda di limitarne l'accesso tramite rete locale o VPN in produzione."
)

# ── 2. TAB STATISTICHE ────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("2. Tab Statistiche")

pdf.body(
    "La schermata iniziale mostra una panoramica rapida dello stato del catalogo. "
    "I dati vengono ricaricati cliccando il pulsante Aggiorna in fondo alla pagina."
)
pdf.spacer()

pdf.h3("KPI principali")
cols2 = [("Indicatore", 60), ("Descrizione", 112)]
pdf.table_header(cols2)
kpi = [
    ("Tipi canonici",       "Numero totale di tipi macchina nel catalogo (es. 39)"),
    ("Alias totali",        "Quante varianti testuali sono registrate"),
    ("Proposte in attesa",  "Quante proposte OCR non ancora classificate"),
]
for i, row in enumerate(kpi):
    pdf.table_row(list(row), cols2, fill=(i % 2 == 0))

pdf.spacer()
pdf.h3("Top 10 tipi per utilizzo")
pdf.body(
    "Tabella con i dieci tipi macchina pi\u00f9 cercati dagli ispettori. "
    "Per ogni tipo mostra il numero di utilizzi e i flag di patentino e verifiche."
)
pdf.spacer()

pdf.h3("Proposte stale")
pdf.body(
    "Se presenti, vengono elencate le proposte in attesa da pi\u00f9 di 7 giorni "
    "con un avviso giallo. Andare nella tab Proposte per risolverle."
)

# ── 3. TAB PROPOSTE ───────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("3. Tab Proposte")

pdf.body(
    "Quando l'OCR riconosce un tipo macchina non presente nel catalogo, "
    "il sistema crea automaticamente una proposta pending. "
    "Questa tab mostra tutte le proposte non ancora classificate."
)
pdf.spacer()
pdf.note(
    "Un sistema AI suggerisce automaticamente se la proposta \u00e8 simile "
    "a un tipo gi\u00e0 esistente (campo 'Simile a' con punteggio %)."
)
pdf.spacer()

pdf.h3("Azioni disponibili per ogni proposta")
pdf.spacer(2)

actions = [
    ("Salva come alias",
     "La stringa proposta diventa un alias di un tipo esistente. "
     "Selezionare il tipo dal dropdown. "
     "Usare quando il tipo esiste gi\u00e0 con nome diverso (es. 'muletto' \u2192 'carrello elevatore')."),
    ("Nuovo tipo canonico",
     "Crea un nuovo tipo nel catalogo. "
     "Modificare il nome se necessario, impostare i flag patentino e verifiche. "
     "Usare solo se il tipo \u00e8 genuinamente nuovo e non coperto da nessun alias."),
    ("Rifiuta",
     "Scarta la proposta. La stringa non viene registrata. "
     "Usare per tipi generici, errori OCR o macchine accessorie."),
]
for label, desc in actions:
    pdf.h3("  >> " + label)
    pdf.body(desc, indent=6)
    pdf.spacer(2)

pdf.h3("Indicatori visivi")
pdf.bullet("Bordo arancione = proposta attiva da pi\u00f9 di 7 giorni")
pdf.bullet("Bordo blu = proposta recente (meno di 7 giorni)")
pdf.bullet("Riquadro giallo 'Simile a' = l'AI suggerisce un possibile merge")

# ── 4. TAB PROPOSTE DISCO ─────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("4. Tab Proposte disco")

pdf.body(
    "Permette di rilevare file PDF presenti nella cartella 'pdf manuali/' "
    "sul server che non hanno ancora un tipo macchina associato."
)
pdf.spacer()

pdf.h3("Flusso di lavoro")
pdf.bullet("Aggiungere un nuovo PDF nella cartella 'pdf manuali/' del server")
pdf.bullet("Cliccare 'Scansiona nuovi file su disco' per rilevare i nuovi file")
pdf.bullet("Per ogni proposta: modificare il nome canonico se necessario")
pdf.bullet("Cliccare 'Approva' per creare un nuovo tipo associato al file")
pdf.bullet("Cliccare 'Rifiuta' per ignorare il file")
pdf.spacer()

pdf.info_box(
    "La scansione \u00e8 idempotente: eseguirla pi\u00f9 volte non crea duplicati. "
    "I file gi\u00e0 assegnati non vengono riproposti."
)
pdf.spacer()

pdf.h3("Campi della proposta")
cols3 = [("Campo", 52), ("Descrizione", 120)]
pdf.table_header(cols3)
rows3 = [
    ("Nome proposto",   "Estratto automaticamente dal nome del file PDF"),
    ("Hint INAIL",      "Termine di ricerca suggerito (se rilevabile dal nome file)"),
    ("Rilevato il",     "Data di prima scansione del file"),
    ("Nome finale",     "Campo modificabile: nome canonico che verr\u00e0 creato nel DB"),
]
for i, r in enumerate(rows3):
    pdf.table_row(list(r), cols3, fill=(i % 2 == 0))

# ── 5. TAB ALIAS ─────────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("5. Tab Alias")

pdf.body(
    "Gli alias permettono al sistema di riconoscere varianti testuali di uno stesso tipo: "
    "termini inglesi, abbreviazioni, varianti OCR, sinonimi di settore."
)
pdf.spacer()
pdf.body(
    "Esempio: il tipo canonico 'carrello elevatore' ha alias 'forklift', 'muletto', "
    "'fork lift', 'carrello frontale', 'carrello elevatore frontale'."
)
pdf.spacer()

pdf.h3("Come aggiungere un alias")
pdf.bullet("Selezionare il tipo macchina dal dropdown")
pdf.bullet("Digitare il nuovo alias nel campo (es. 'PLE', 'scissor lift', 'muletto')")
pdf.bullet("Premere Enter oppure cliccare '+ Aggiungi'")
pdf.spacer()

pdf.h3("Come eliminare un alias")
pdf.bullet("Cliccare l'icona cestino sulla riga dell'alias")
pdf.spacer()

pdf.h3("Badge 'source'")
pdf.body("Ogni alias mostra l'origine con un badge:")
pdf.spacer(2)
cols4 = [("Source", 30), ("Significato", 142)]
pdf.table_header(cols4)
sources = [
    ("seed",  "Predefinito al primo avvio (da _SEED_ALIASES nel codice)"),
    ("admin", "Aggiunto manualmente tramite questa tab"),
    ("ai",    "Suggerito automaticamente dal sistema di riconoscimento"),
]
for i, r in enumerate(sources):
    pdf.table_row(list(r), cols4, fill=(i % 2 == 0))

pdf.spacer()
pdf.note(
    "Gli alias sono case-insensitive e normalizzati automaticamente. "
    "Non \u00e8 necessario aggiungere varianti maiuscole."
)

# ── 6. TAB FLAGS NORMATIVI ────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("6. Tab Flags normativi")

pdf.body(
    "Editor principale per i metadati normativi di ogni tipo macchina. "
    "Le modifiche si riflettono immediatamente nelle schede ispettive."
)
pdf.spacer()

pdf.h3("Layout")
pdf.body(
    "La schermata \u00e8 divisa in due colonne: a sinistra la lista di tutti i tipi "
    "(filtrabile), a destra l'editor per il tipo selezionato."
)
pdf.spacer()

pdf.h3("Flag normativi")
pdf.spacer(2)
cols5 = [("Flag", 62), ("Norma di riferimento", 110)]
pdf.table_header(cols5)
rows5 = [
    ("Patentino / abilitazione", "Accordo Stato-Regioni 22/02/2012 \u2014 PLE, carrelli, gru, ecc."),
    ("Verifiche periodiche INAIL", "Art. 71 c.11 D.Lgs. 81/08 \u2014 Allegato VII"),
]
for i, r in enumerate(rows5):
    pdf.table_row(list(r), cols5, fill=(i % 2 == 0))

pdf.spacer()
pdf.h3("Termine di ricerca INAIL (online)")
pdf.body(
    "Testo libero usato per costruire le query di ricerca su inail.it. "
    "Esempi: 'PLE piattaforma lavoro elevabile', 'carrello elevatore frontale'. "
    "Se lasciato vuoto viene usato il nome canonico del tipo. "
    "L'associazione di un PDF locale si gestisce nella tab 'Manuali INAIL'."
)
pdf.spacer()

pdf.h3("Vita utile stimata (anni)")
pdf.body(
    "Numero intero (es. 15). Mostrato nella scheda ispettiva come "
    "indicazione sulla durata tipica dell'attrezzatura."
)
pdf.spacer()

pdf.h3("Hazard Intelligence")
pdf.bullet("Categoria INAIL (agente materiale): classificazione statistica INAIL "
           "es. 'Apparecchi di sollevamento'")
pdf.bullet("Focus rischi di categoria: 2-3 frasi sui rischi pi\u00f9 frequenti "
           "secondo le statistiche INAIL \u2014 iniettato nel prompt AI")
pdf.spacer()

pdf.h3("Pulsanti AI globali")
pdf.spacer(2)
cols6 = [("Pulsante", 72), ("Azione", 100)]
pdf.table_header(cols6)
ai_btns = [
    ("Popola vita utile",      "Stima con AI la vita utile per i tipi con campo NULL"),
    ("Popola hazard INAIL",    "Aggiorna categoria e focus rischi per tipi mancanti"),
    ("Associa quaderni INAIL", "Associa i PDF locali ai tipi con hint NULL (AI)"),
]
for i, r in enumerate(ai_btns):
    pdf.table_row(list(r), cols6, fill=(i % 2 == 0))

pdf.note(
    "I pulsanti AI operano solo sui campi NULL o non aggiornati di recente. "
    "Non sovrascrivono i valori gi\u00e0 impostati manualmente."
)

# ── 7. TAB RICERCHE ───────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("7. Tab Ricerche")

pdf.body(
    "Mostra le scansioni per cui non \u00e8 stato trovato un manuale specifico del produttore. "
    "Usata per richiedere al costruttore il manuale mancante."
)
pdf.spacer()

pdf.h3("Colonne della tabella")
cols7 = [("Colonna", 30), ("Descrizione", 142)]
pdf.table_header(cols7)
rows7 = [
    ("Foto",      "Miniatura etichetta. Clic per ingrandire, icona graffetta per scaricare"),
    ("Data",      "Data e ora della ricerca"),
    ("Marca",     "Brand riconosciuto dall'OCR"),
    ("Modello",   "Modello riconosciuto dall'OCR"),
    ("Tipo",      "Tipo macchina identificato"),
    ("Matricola", "Numero di serie (se leggibile)"),
    ("Anno",      "Anno di fabbricazione (se leggibile)"),
    ("Fonte",     "Strategia usata (fallback_ai, pdf, inail, ecc.)"),
]
for i, r in enumerate(rows7):
    pdf.table_row(list(r), cols7, fill=(i % 2 == 0))

pdf.spacer()
pdf.h3("Azioni per riga")
pdf.bullet("Invia ricerca \u2014 cerca l'email del produttore e apre il client email "
           "con la richiesta precompilata (oggetto + corpo formali con dati macchina)")
pdf.bullet("X \u2014 nasconde la riga dalla lista (il log resta nel DB)")
pdf.spacer()

pdf.info_box(
    "Il sistema cerca automaticamente l'email del reparto assistenza tecnica. "
    "Se non trovata, il client email si apre con il campo 'A:' vuoto "
    "e il corpo gi\u00e0 compilato con i dati della macchina."
)

# ── 8. TAB LOG SCANSIONI ─────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("8. Tab Log scansioni")

pdf.body(
    "Archivio completo di tutte le analisi effettuate (ultime 200). "
    "A differenza della tab Ricerche, qui sono visibili anche le analisi con manuale trovato."
)
pdf.spacer()

pdf.h3("Filtro per fonte")
cols8 = [("Valore", 44), ("Significato", 128)]
pdf.table_header(cols8)
fonti = [
    ("pdf",              "Manuale produttore trovato come PDF"),
    ("inail+produttore", "Analisi combinata: PDF produttore + quaderno INAIL"),
    ("inail",            "Solo quaderno INAIL (manuale non trovato)"),
    ("fallback_ai",      "Nessun documento, solo inferenza AI"),
]
for i, r in enumerate(fonti):
    pdf.table_row(list(r), cols8, fill=(i % 2 == 0))

pdf.spacer()
pdf.h3("Lightbox")
pdf.body(
    "Cliccando su una miniatura si apre l'immagine a schermo intero. "
    "Clic ovunque per chiudere."
)

# ── 9. TAB CORPUS RAG ────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("9. Tab Corpus RAG")

pdf.body(
    "Gestisce il corpus normativo indicizzato (ChromaDB) usato come contesto "
    "aggiuntivo per le analisi AI. Il corpus NON sostituisce il PDF manuale del "
    "produttore: lo integra con citazioni da normative e quaderni INAIL."
)
pdf.spacer()

pdf.h3("KPI")
pdf.bullet("Chunk indicizzati \u2014 frammenti di testo nel vettore store")
pdf.bullet("Fonti presenti \u2014 numero di documenti indicizzati")
pdf.bullet("Corpus attivo \u2014 verde se contiene almeno un documento")
pdf.spacer()

pdf.h3("Tipi di documento indicizzabili")
cols9 = [("Tipo", 52), ("Descrizione", 120)]
pdf.table_header(cols9)
tipi_corpus = [
    ("quaderno_inail",  "Quaderni e schede tecniche INAIL per tipo macchina"),
    ("normativa_EU",    "Direttive europee (Direttiva Macchine, ATEX, ecc.)"),
]
for i, r in enumerate(tipi_corpus):
    pdf.table_row(list(r), cols9, fill=(i % 2 == 0))

pdf.spacer()
pdf.h3("Carica PDF singolo")
pdf.body(
    "Aggiunge un singolo PDF al corpus con indicizzazione immediata (modello MiniLM). "
    "Selezionare prima la categoria, poi scegliere il file."
)
pdf.note(
    "MiniLM \u00e8 un modello embedding leggero. Per qualit\u00e0 ottimale: "
    "indicizzare in locale con 'python -m app.local_indexer' e caricare il DB ZIP."
)
pdf.spacer()

pdf.h3("Carica DB pre-indicizzato (ZIP)")
pdf.body(
    "Metodo raccomandato per aggiornamenti importanti. "
    "Genera il file ZIP dalla GUI locale ('Esporta ZIP ChromaDB'), "
    "poi caricalo qui. Sostituisce integralmente il corpus esistente."
)
pdf.spacer()

pdf.h3("Re-indicizza tutto")
pdf.body(
    "Rielabora con MiniLM tutti i PDF del corpus. "
    "Da eseguire dopo l'upload di PDF singoli per sincronizzare l'indice."
)

# ── 10. TAB MANUALI INAIL ────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("10. Tab Manuali INAIL")

pdf.body(
    "Gestisce la tabella inail_manual_assignments: mappa ogni tipo macchina "
    "a un PDF fisicamente presente nella cartella 'pdf manuali/'. "
    "Questo PDF viene usato come fonte primaria (priorit\u00e0 massima, affidabilit\u00e0 100%)."
)
pdf.spacer()

pdf.info_box(
    "Questa tab gestisce i PDF fisici locali (quaderni INAIL scaricati). "
    "Non ha relazione con il corpus RAG (ChromaDB), che si gestisce "
    "nella tab 'Corpus RAG'."
)
pdf.spacer()

pdf.h3("Come aggiungere un'assegnazione")
pdf.bullet("Scegliere il Tipo macchina dal dropdown")
pdf.bullet("Scegliere il PDF dal dropdown (mostra i file in 'pdf manuali/')")
pdf.bullet("Inserire un Titolo opzionale (es. 'Scheda INAIL \u2014 PLE')")
pdf.bullet("Cliccare 'Salva assegnazione'")
pdf.spacer()

pdf.h3("Tabella assegnazioni")
cols10 = [("Colonna", 36), ("Descrizione", 136)]
pdf.table_header(cols10)
rows10 = [
    ("Tipo macchina", "Nome canonico del tipo"),
    ("PDF locale",    "Nome del file nella cartella 'pdf manuali/'"),
    ("Titolo",        "Etichetta visualizzata nella scheda (opzionale)"),
    ("Su disco",      "Spunta verde = file trovato; triangolo = file mancante"),
    ("Cestino",       "Elimina l'assegnazione (non elimina il file fisico)"),
]
for i, r in enumerate(rows10):
    pdf.table_row(list(r), cols10, fill=(i % 2 == 0))

pdf.spacer()
pdf.note(
    "Al primo avvio il sistema esegue automaticamente il seed delle assegnazioni "
    "predefinite. Se la tabella \u00e8 vuota andare a inserirle manualmente."
)

# ── 11. TAB NORMATIVE ────────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("11. Tab Normative")

pdf.body(
    "Gestione delle normative tecniche per tipo macchina (machine_type_normative). "
    "Vengono incluse nella sezione 'Normative applicabili' della scheda ispettiva."
)
pdf.spacer()

pdf.h3("Norma globale vs. specifica")
pdf.body(
    "Se il campo 'Tipo macchina' \u00e8 lasciato vuoto (opzione 'Globale'), "
    "la norma appare in tutte le schede. "
    "Se si seleziona un tipo specifico, appare solo per quel tipo."
)
pdf.spacer()

pdf.h3("Come aggiungere una norma")
pdf.bullet("Selezionare il tipo (o lasciare vuoto per norma globale)")
pdf.bullet("Impostare il campo Ordine per controllare la posizione nella scheda")
pdf.bullet("Inserire il testo della norma (es. 'EN ISO 3691-1:2015+A1:2020 \u2014 Carrelli')")
pdf.bullet("Cliccare 'Aggiungi norma'")
pdf.spacer()

pdf.h3("Come eliminare una norma")
pdf.bullet("Cliccare il pulsante X sulla riga della norma")

# ── 12. TAB RIFERIMENTI ───────────────────────────────────────────────────────

pdf.add_page()
pdf.h1("12. Tab Riferimenti normativi")

pdf.body(
    "Gestisce i riferimenti D.Lgs. 81/08 nella sezione 'Riferimenti normativi' "
    "della scheda ispettiva. I riferimenti sono pre-caricati dal seed; "
    "questa tab modifica solo l'associazione ai tipi macchina."
)
pdf.spacer()

pdf.h3("Globale vs. specifico")
pdf.body(
    "Un riferimento Globale viene incluso in ogni scheda. "
    "Un riferimento specifico appare solo per i tipi macchina selezionati."
)
pdf.spacer()

pdf.h3("Come modificare l'associazione")
pdf.bullet("Cliccare 'Modifica' sulla riga del riferimento")
pdf.bullet("Spuntare 'Globale' per applicarlo a tutti i tipi")
pdf.bullet("Oppure deselezionare 'Globale' e scegliere i tipi con le chip colorate")
pdf.bullet("Cliccare 'Salva' per confermare")
pdf.spacer()

pdf.info_box(
    "Le chip mostrano i nomi dei tipi macchina (non gli ID). "
    "Le chip selezionate diventano blu. "
    "Salvare con zero tipi selezionati equivale a impostare il riferimento come Globale."
)

# ── 13. FLUSSO DI LAVORO TIPICO ───────────────────────────────────────────────

pdf.add_page()
pdf.h1("13. Flusso di lavoro tipico")

scenari = [
    (
        "Nuovo PDF quaderno INAIL ricevuto",
        [
            "Salvare il PDF nella cartella 'pdf manuali/' del server",
            "Aprire la tab 'Manuali INAIL'",
            "Selezionare tipo macchina e PDF dal dropdown",
            "Inserire un titolo descrittivo (es. 'Scheda INAIL \u2014 Carrello elevatore')",
            "Cliccare 'Salva assegnazione' e verificare la spunta verde 'Su disco'",
        ]
    ),
    (
        "Nuovo tipo macchina sconosciuto (da OCR)",
        [
            "Aprire la tab 'Proposte' \u2014 il tipo appare nell'elenco",
            "Valutare il suggerimento AI ('Simile a')",
            "Se \u00e8 un alias: cliccare 'Salva come alias' e selezionare il tipo esistente",
            "Se \u00e8 un tipo genuinamente nuovo: 'Nuovo tipo canonico', impostare i flag",
            "Se \u00e8 un errore OCR o accessorio: 'Rifiuta'",
        ]
    ),
    (
        "Aggiornare le normative per un tipo",
        [
            "Aprire la tab 'Normative'",
            "Selezionare il tipo o lasciare vuoto per norma globale",
            "Inserire il testo della norma e l'ordine di visualizzazione",
            "Cliccare 'Aggiungi norma'",
            "Se necessario aggiornare i Riferimenti nella tab apposita",
        ]
    ),
    (
        "Aggiornare il corpus RAG con nuovi documenti",
        [
            "Indicizzare i PDF in locale con 'python -m app.local_indexer'",
            "Esportare il database ChromaDB come ZIP dalla GUI locale",
            "Aprire la tab 'Corpus RAG'",
            "Cliccare 'Carica chroma_db.zip' e selezionare il file",
            "Verificare che il contatore 'Chunk indicizzati' sia aggiornato",
        ]
    ),
    (
        "Richiedere un manuale al produttore",
        [
            "Aprire la tab 'Ricerche'",
            "Individuare la riga della macchina di interesse",
            "Cliccare 'Invia ricerca' \u2014 il sistema cerca l'email e prepara la richiesta",
            "Verificare il corpo del messaggio nel client email e inviare",
            "Cliccare X per nascondere la riga dopo l'invio",
        ]
    ),
]

for titolo, passi in scenari:
    pdf.h2(titolo)
    for i, passo in enumerate(passi, 1):
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(30, 64, 175)
        pdf.set_x(pdf.l_margin + 4)
        pdf.cell(10, 5.5, f"{i}.")
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 5.5, passo)
    pdf.spacer(2)

# ── Output ────────────────────────────────────────────────────────────────────

output_path = "manuale_admin_manualfinder.pdf"
pdf.output(output_path)
print(f"PDF generato: {output_path}")
