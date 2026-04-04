# -*- coding: utf-8 -*-
"""
ManualFinder - Test Backend Completo
Eseguito con: python test_backend.py
"""
import sys
import os
import io
import json
import traceback
from datetime import datetime

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Setup path
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# Evita import config che carica .env
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy")
os.environ.setdefault("GEMINI_API_KEY", "test-dummy")

passed = 0
failed = 0
warnings = 0
problems = []
report_lines = []

def ok(msg):
    global passed
    passed += 1
    print(f"  [OK] {msg}")
    report_lines.append(f"  [OK] {msg}")

def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")
    if detail:
        print(f"        {detail}")
    report_lines.append(f"  [FAIL] {msg}")
    if detail:
        report_lines.append(f"        {detail}")
    problems.append(f"{msg}: {detail}" if detail else msg)

def warn(msg):
    global warnings
    warnings += 1
    print(f"  [WARN] {msg}")
    report_lines.append(f"  [WARN] {msg}")

def section(title):
    line = f"\n### {title}"
    print(line)
    report_lines.append(line)

print("=" * 60)
print("MANUALFINDER — TEST BACKEND")
print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ─────────────────────────────────────────────────────────────
# TEST 1: allegato_v_data.py — get_machine_category
# ─────────────────────────────────────────────────────────────
section("1. Smart Selector (allegato_v_data) — get_machine_category")

try:
    from app.data.allegato_v_data import get_machine_category, ALLEGATO_V_CATEGORIES, _GENERIC_CATEGORY

    test_cases = [
        # (input, expected_key, descrizione)
        ("piattaforma aerea",      "piattaforme_aeree",   "piattaforma aerea"),
        ("PLE",                    "piattaforme_aeree",   "PLE"),
        ("cestello elevabile",     "piattaforme_aeree",   "cestello elevabile"),
        ("scissor lift",           "piattaforme_aeree",   "scissor lift"),
        ("escavatore",             "escavatori",          "escavatore"),
        ("miniescavatore cingolato","escavatori",         "miniescavatore cingolato"),
        ("pala meccanica",         "escavatori",          "pala meccanica"),
        ("gru mobile",             "gru_mobili",          "gru mobile"),
        ("autogrù",                "gru_mobili",          "autogrù"),
        ("braccio telescopico",    "gru_mobili",          "braccio telescopico"),
        ("carrello elevatore",     "carrelli_elevatori",  "carrello elevatore"),
        ("muletto",                "carrelli_elevatori",  "muletto"),
        ("forklift",               "carrelli_elevatori",  "forklift"),
        ("compressore",            "compressori",         "compressore"),
        ("aria compressa",         "compressori",         "aria compressa"),
        ("betoniera",              "betoniere",           "betoniera"),
        ("mescolatore calcestruzzo","betoniere",          "mescolatore calcestruzzo"),
        ("generatore diesel",      "generatori",          "generatore diesel"),
        ("gruppo elettrogeno",     "generatori",          "gruppo elettrogeno"),
        (None,                     "generico",            "None → generico"),
        ("",                       "generico",            "'' → generico"),
        ("macchinario sconosciuto","generico",            "sconosciuto → generico"),
    ]

    for machine_input, expected_key, desc in test_cases:
        try:
            key, data = get_machine_category(machine_input)
            if key == expected_key:
                ok(f"{desc!r:40s} --> {key}")
            else:
                fail(f"{desc!r:40s} --> atteso={expected_key!r}, ottenuto={key!r}")
        except Exception as e:
            fail(f"{desc!r} --> ECCEZIONE: {e}")

    # Verifica che ogni categoria abbia >= 3 requisiti e >= 1 riga tabella_ce
    print("\n  [Verifica struttura categorie]")
    for cat_key, cat_data in ALLEGATO_V_CATEGORIES.items():
        req_count = len(cat_data.get("requisiti", []))
        tce_count = len(cat_data.get("tabella_ce", []))
        if req_count >= 3:
            ok(f"Categoria '{cat_key}': {req_count} requisiti >= 3")
        else:
            fail(f"Categoria '{cat_key}': solo {req_count} requisiti (minimo 3)")
        if tce_count >= 1:
            ok(f"Categoria '{cat_key}': {tce_count} righe tabella_ce >= 1")
        else:
            fail(f"Categoria '{cat_key}': tabella_ce vuota!")

except Exception as e:
    fail(f"Impossibile importare allegato_v_data", traceback.format_exc(limit=2))

# ─────────────────────────────────────────────────────────────
# TEST 2: responses.py — SafetyCard model
# ─────────────────────────────────────────────────────────────
section("2. SafetyCard Model (responses.py)")

try:
    from app.models.responses import SafetyCard

    # Test 2a: SafetyCard con tutti i campi nuovi
    try:
        card = SafetyCard(
            brand="Test Brand",
            model="Test Model",
            rischi_principali=["Rischio caduta"],
            dispositivi_protezione=["Imbracatura"],
            raccomandazioni_produttore=["Controllare freni"],
            rischi_residui=["Ribaltamento residuo"],
            is_allegato_v=True,
            machine_year="1985",
            machine_type="piattaforma aerea",
            allegato_v_category="piattaforme_aeree",
            allegato_v_label="Piattaforme di lavoro elevabili (PLE)",
            allegato_v_requisiti=[{"id": "1.1", "titolo": "Test"}],
            tabella_ce_ante=[{"aspetto": "Test", "allegato_v": "A", "dir_ce": "B", "gap": "C"}],
            gap_ce_ante="Gap di sicurezza: mancano interblocchi automatici.",
            bozze_prescrizioni=[{
                "req_id": "1.1",
                "titolo": "Resistenza strutturale",
                "criticita": "alta",
                "prescrizione": "Si prescrive al datore di lavoro di effettuare verifica strutturale."
            }],
        )
        d = card.model_dump()
        if d["is_allegato_v"] is True:
            ok("SafetyCard con campi Allegato V: is_allegato_v=True")
        else:
            fail("SafetyCard: is_allegato_v non True nel dump")
        if d["gap_ce_ante"] == "Gap di sicurezza: mancano interblocchi automatici.":
            ok("SafetyCard: gap_ce_ante serializzato correttamente")
        else:
            fail("SafetyCard: gap_ce_ante non corretto")
        if len(d["bozze_prescrizioni"]) == 1:
            ok("SafetyCard: bozze_prescrizioni serializzata (1 elemento)")
        else:
            fail("SafetyCard: bozze_prescrizioni non serializzata correttamente")
        if len(d["tabella_ce_ante"]) == 1:
            ok("SafetyCard: tabella_ce_ante serializzata (1 elemento)")
        else:
            fail("SafetyCard: tabella_ce_ante non serializzata")
    except Exception as e:
        fail("SafetyCard con campi nuovi", traceback.format_exc(limit=2))

    # Test 2b: SafetyCard senza campi ante-CE → default corretti
    try:
        card2 = SafetyCard(
            brand="Caterpillar",
            model="320D",
            rischi_principali=["Ribaltamento"],
            dispositivi_protezione=["ROPS"],
            raccomandazioni_produttore=["Check olio"],
            rischi_residui=["Schiacciamento"],
        )
        d2 = card2.model_dump()
        if d2["is_allegato_v"] is False:
            ok("SafetyCard senza ante-CE: is_allegato_v=False (default)")
        else:
            fail("SafetyCard senza ante-CE: is_allegato_v non False")
        if d2["allegato_v_requisiti"] == []:
            ok("SafetyCard senza ante-CE: allegato_v_requisiti=[] (default)")
        else:
            fail(f"SafetyCard: allegato_v_requisiti non lista vuota: {d2['allegato_v_requisiti']}")
        if d2["bozze_prescrizioni"] == []:
            ok("SafetyCard senza ante-CE: bozze_prescrizioni=[] (default)")
        else:
            fail("SafetyCard: bozze_prescrizioni non vuota per default")
        if d2["gap_ce_ante"] is None:
            ok("SafetyCard senza ante-CE: gap_ce_ante=None (default)")
        else:
            fail("SafetyCard: gap_ce_ante non None per default")
    except Exception as e:
        fail("SafetyCard senza campi ante-CE", traceback.format_exc(limit=2))

    # Test 2c: generated_at auto-popolato
    try:
        card3 = SafetyCard(
            brand="Test",
            model="X",
            rischi_principali=[],
            dispositivi_protezione=[],
            raccomandazioni_produttore=[],
            rischi_residui=[],
        )
        if card3.generated_at and len(card3.generated_at) > 5:
            ok(f"SafetyCard: generated_at auto-popolato = {card3.generated_at[:20]}...")
        else:
            fail(f"SafetyCard: generated_at non auto-popolato: {card3.generated_at!r}")
    except Exception as e:
        fail("SafetyCard generated_at", traceback.format_exc(limit=2))

except Exception as e:
    fail("Impossibile importare SafetyCard", traceback.format_exc(limit=2))

# ─────────────────────────────────────────────────────────────
# TEST 3: analysis_service.py — _parse_json_response
# ─────────────────────────────────────────────────────────────
section("3. Parser JSON (_parse_json_response)")

try:
    from app.services.analysis_service import _parse_json_response

    # 3a: JSON valido
    valid = '{"rischi_principali": ["caduta"], "dispositivi_protezione": ["casco"], "raccomandazioni_produttore": [], "rischi_residui": []}'
    r = _parse_json_response(valid)
    if r.get("rischi_principali") == ["caduta"]:
        ok("JSON valido normale → parsato correttamente")
    else:
        fail("JSON valido: risultato inatteso", str(r))

    # 3b: JSON con markdown code block
    md_json = '```json\n{"rischi_principali": ["ribaltamento"], "dispositivi_protezione": [], "raccomandazioni_produttore": [], "rischi_residui": []}\n```'
    r2 = _parse_json_response(md_json)
    if r2.get("rischi_principali") == ["ribaltamento"]:
        ok("JSON con ```json ... ``` markdown → parsato correttamente")
    else:
        fail("JSON markdown: risultato inatteso", str(r2))

    # 3c: JSON con campi mancanti
    partial = '{"rischi_principali": ["pericolo elettrico"]}'
    r3 = _parse_json_response(partial)
    if "rischi_principali" in r3:
        ok("JSON con campi mancanti → parsato (rischi_principali presente)")
    else:
        fail("JSON campi mancanti: rischi_principali mancante", str(r3))

    # 3d: JSON malformato
    broken = '{"rischi_principali": ["caduta", "rischio_schiacciamento"], "dispositivi_protezione": ["elmetto"'
    r4 = _parse_json_response(broken)
    if "rischi_principali" in r4:
        ok("JSON malformato → recupero parziale funzionante")
    else:
        warn("JSON malformato → fallback finale (non fatale)")

    # 3e: Risposta non-JSON
    not_json = "Mi dispiace, non ho trovato informazioni su questo macchinario."
    r5 = _parse_json_response(not_json)
    if isinstance(r5, dict) and "rischi_principali" in r5:
        ok("Risposta non-JSON → fallback dict restituito")
    else:
        fail("Risposta non-JSON: fallback non restituisce dict", str(r5))

    # 3f: JSON con campi nuovi Allegato V
    allegato_json = json.dumps({
        "rischi_principali": ["caduta dall'alto"],
        "dispositivi_protezione": ["imbracatura"],
        "raccomandazioni_produttore": ["verificare freni"],
        "rischi_residui": ["ribaltamento residuo"],
        "gap_ce_ante": "Mancano interblocchi automatici e marcatura CE.",
        "bozze_prescrizioni": [
            {
                "req_id": "1.1",
                "titolo": "Resistenza strutturale",
                "criticita": "alta",
                "prescrizione": "Si prescrive di eseguire verifica strutturale entro 30 giorni."
            }
        ]
    })
    r6 = _parse_json_response(allegato_json)
    if r6.get("gap_ce_ante"):
        ok("JSON con gap_ce_ante → parsato correttamente")
    else:
        fail("JSON con gap_ce_ante: campo non trovato", str(r6))
    if isinstance(r6.get("bozze_prescrizioni"), list) and len(r6["bozze_prescrizioni"]) == 1:
        ok("JSON con bozze_prescrizioni → lista di 1 dict parsata")
    else:
        fail("JSON con bozze_prescrizioni: non parsato correttamente", str(r6.get("bozze_prescrizioni")))

except Exception as e:
    fail("Impossibile testare _parse_json_response", traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────
# TEST 4: search_service.py — _score_result
# ─────────────────────────────────────────────────────────────
section("4. Score Results (_score_result)")

try:
    from app.services.search_service import _score_result

    # 4a: INAIL — massima priorità
    score_inail = _score_result(
        "https://www.inail.it/manuali/escavatore_sicurezza.pdf",
        "manuale sicurezza escavatore INAIL",
        is_pdf=True,
        is_inail=True,
    )
    print(f"  [INFO] INAIL score = {score_inail}")
    if score_inail >= 60:
        ok(f"INAIL PDF con titolo sicurezza → score={score_inail} (>= 60)")
    else:
        fail(f"INAIL: score={score_inail} < 60 atteso")

    # 4b: manualslib.com — aggregatore
    score_manualslib = _score_result(
        "https://www.manualslib.com/products/Jcb-Forklift-1234",
        "user manual forklift JCB",
        is_pdf=False,
        is_inail=False,
    )
    print(f"  [INFO] manualslib score = {score_manualslib}")
    if 5 <= score_manualslib <= 50:
        ok(f"manualslib HTML → score medio={score_manualslib}")
    else:
        warn(f"manualslib score={score_manualslib} (atteso 5-50)")

    # 4c: dominio casuale con "spare parts"
    score_spareparts = _score_result(
        "https://www.randomsite.com/machinery-docs/excavator-spare-parts-list",
        "Excavator spare parts catalog list",
        is_pdf=False,
        is_inail=False,
    )
    print(f"  [INFO] spare parts score = {score_spareparts}")
    if score_spareparts < 10:
        ok(f"Catalogo ricambi dominio generico → score basso={score_spareparts}")
    else:
        warn(f"Catalogo ricambi: score={score_spareparts} (atteso < 10)")

    # 4d: dominio produttore noto
    score_manitou = _score_result(
        "https://www.manitou.com/docs/MT732_operator_manual.pdf",
        "Manitou MT732 operator manual",
        is_pdf=True,
        is_inail=False,
    )
    print(f"  [INFO] manitou.com score = {score_manitou}")
    if score_manitou >= 20:
        ok(f"manitou.com PDF manuale operatore → score={score_manitou} (>= 20)")
    else:
        fail(f"Produttore noto: score={score_manitou} < 20 atteso")

    # 4e: Verifica INAIL > generico web
    score_generic_web = _score_result(
        "https://www.macchinedocumentazione.eu/manuale-escavatore",
        "manuale escavatore",
        is_pdf=False,
    )
    if score_inail > score_generic_web:
        ok(f"INAIL ({score_inail}) > web generico ({score_generic_web})")
    else:
        fail(f"INAIL ({score_inail}) NON > web generico ({score_generic_web})")

    # liebherr.com
    score_liebherr = _score_result(
        "https://www.liebherr.com/documents/LTM1100_operator.pdf",
        "Liebherr LTM 1100 operator manual",
        is_pdf=True,
    )
    print(f"  [INFO] liebherr.com score = {score_liebherr}")
    if score_liebherr >= 20:
        ok(f"liebherr.com PDF → score={score_liebherr} (>= 20)")
    else:
        fail(f"liebherr: score={score_liebherr} < 20 atteso")

except Exception as e:
    fail("Impossibile testare _score_result", traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────
# TEST 5: safety_gate_service.py — _normalize_risk_level
# ─────────────────────────────────────────────────────────────
section("5. Normalizzazione Risk Level (_normalize_risk_level)")

try:
    from app.services.safety_gate_service import _normalize_risk_level

    test_cases_risk = [
        # (input, expected)
        ("serious",   "serious"),
        ("grave",     "serious"),
        ("alto",      "serious"),
        ("serio",     "serious"),
        ("high",      "serious"),
        ("medium",    "medium"),
        ("medio",     "medium"),
        ("moderate",  "medium"),
        ("low",       "low"),
        ("basso",     "low"),
        ("",          "unknown"),
        (None,        "unknown"),
        ("unknown",   "unknown"),
        ("xyz",       "unknown"),
        # Nota: "moderato" e "lieve" non sono nelle liste
        ("moderato",  None),  # None = non testare output specifico, solo documentare
        ("lieve",     None),
    ]

    for raw, expected in test_cases_risk:
        result = _normalize_risk_level(raw)
        if expected is None:
            # Documenta il comportamento senza asserzione pass/fail
            warn(f"_normalize_risk_level({raw!r}) = {result!r} (non nel dizionario, comportamento documentato)")
        elif result == expected:
            ok(f"_normalize_risk_level({raw!r}) = {result!r}")
        else:
            fail(f"_normalize_risk_level({raw!r}): atteso={expected!r}, ottenuto={result!r}")

except Exception as e:
    fail("Impossibile testare _normalize_risk_level", traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────
# TEST 6: pdf_service.py — score_pdf_safety_relevance
# ─────────────────────────────────────────────────────────────
section("6. PDF Safety Score (pdf_service)")

try:
    from app.services.pdf_service import score_pdf_safety_relevance

    # Controlla se fitz è disponibile
    try:
        import fitz
        fitz_available = True
    except ImportError:
        fitz_available = False
        warn("PyMuPDF (fitz) non installato — test PDF skippati")

    if fitz_available:
        # Crea un PDF valido con testo sicurezza usando fitz direttamente
        try:
            # PDF sicurezza in italiano
            doc_safe = fitz.open()
            page = doc_safe.new_page()
            safety_text = (
                "ISTRUZIONI DI SICUREZZA\n"
                "Dispositivi di protezione individuale: casco, guanti, imbracatura, stivali, occhiali.\n"
                "Rischi principali: caduta dall'alto, ribaltamento, schiacciamento, folgorazione.\n"
                "Rischi residui: rischio investimento, pericolo rumore e vibrazione.\n"
                "Avvertenza: indossare sempre elmetto in cantiere.\n"
                "Warning: always wear safety helmet. Danger: risk of falling objects.\n"
                "Safety precautions: check all safety devices before use.\n"
                "Manuale di uso e manutenzione. Verifiche periodiche obbligatorie D.Lgs. 81/08.\n"
                "Direttiva macchine 2006/42/CE. Marcatura CE. Dichiarazione di conformità.\n"
                "Pericolo: non rimuovere le protezioni organi in moto. Dispositivi di sicurezza.\n"
                "Norme di sicurezza: rispettare le istruzioni di sicurezza del costruttore.\n"
                "Residual risks: electrocution, explosion, fire hazard.\n"
                "Personal protective equipment: harness, boots, gloves, helmet, goggles.\n"
            )
            page.insert_text((50, 50), safety_text, fontsize=10)
            safe_bytes = doc_safe.tobytes()
            doc_safe.close()

            score_safe = score_pdf_safety_relevance(safe_bytes)
            print(f"  [INFO] Score PDF sicurezza = {score_safe}")
            if score_safe > 0:
                ok(f"PDF con testo sicurezza → score={score_safe} (> 0)")
            else:
                fail(f"PDF sicurezza → score=0 (atteso > 0)")

            # PDF catalogo ricambi
            doc_parts = fitz.open()
            page2 = doc_parts.new_page()
            parts_text = (
                "SPARE PARTS CATALOG\n"
                "Parts catalog for excavator XZ-500.\n"
                "Part number: 12345-A, 67890-B, 11111-C\n"
                "Ersatzteile Katalog. Catalogo ricambi macchina.\n"
                "Price list 2024. Listino prezzi ricambi.\n"
                "Wiring diagram engine block. Schema elettrico.\n"
                "Torque specifications: 25 Nm, 50 Nm, 100 Nm.\n"
                "Workshop manual service repair procedure.\n"
                "Manuale officina riparazione motore.\n"
            )
            page2.insert_text((50, 50), parts_text, fontsize=10)
            parts_bytes = doc_parts.tobytes()
            doc_parts.close()

            score_parts = score_pdf_safety_relevance(parts_bytes)
            print(f"  [INFO] Score PDF ricambi = {score_parts}")
            if score_parts < score_safe:
                ok(f"PDF ricambi ({score_parts}) < PDF sicurezza ({score_safe})")
            else:
                fail(f"PDF ricambi ({score_parts}) NON < PDF sicurezza ({score_safe})")

        except Exception as e:
            fail("Creazione PDF di test fallita", traceback.format_exc(limit=3))
    else:
        warn("Test 6 skippato (fitz non disponibile)")

except Exception as e:
    fail("Impossibile importare pdf_service", traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────
# TEST 7: format_requisiti_for_prompt
# ─────────────────────────────────────────────────────────────
section("7. format_requisiti_for_prompt")

try:
    from app.data.allegato_v_data import format_requisiti_for_prompt, ALLEGATO_V_CATEGORIES

    for cat_key, cat_data in ALLEGATO_V_CATEGORIES.items():
        output = format_requisiti_for_prompt(cat_data)

        # Verifica label
        if cat_data["label"] in output:
            ok(f"'{cat_key}': label presente nell'output")
        else:
            fail(f"'{cat_key}': label '{cat_data['label']}' assente nell'output")

        # Verifica almeno 3 voci con "Verifica:"
        verifica_count = output.count("→ Verifica:")
        if verifica_count >= 3:
            ok(f"'{cat_key}': {verifica_count} voci 'Verifica:' (>= 3)")
        else:
            fail(f"'{cat_key}': solo {verifica_count} voci 'Verifica:' (minimo 3)")

        # Verifica simboli criticità
        has_icons = any(icon in output for icon in ["🔴", "🟡", "🟢"])
        if has_icons:
            ok(f"'{cat_key}': simboli criticità presenti (🔴/🟡/🟢)")
        else:
            fail(f"'{cat_key}': nessun simbolo criticità trovato")

except Exception as e:
    fail("Impossibile testare format_requisiti_for_prompt", traceback.format_exc(limit=3))

# ─────────────────────────────────────────────────────────────
# TEST 8: Integrazione SafetyCard + AllegatoV
# ─────────────────────────────────────────────────────────────
section("8. Integrazione SafetyCard + AllegatoV (macchina ante-1996)")

try:
    from app.data.allegato_v_data import get_machine_category
    from app.models.responses import SafetyCard

    # Simula la logica di analysis_service.generate_safety_card per macchina ante-1996
    machine_type = "piattaforma aerea"
    machine_year = "1985"
    brand = "Test Lift"
    model = "TL-85"

    av_category_key, av_category_data = get_machine_category(machine_type)

    if av_category_key != "piattaforme_aeree":
        fail(f"Integrazione: get_machine_category non ha trovato piattaforme_aeree: {av_category_key}")
    else:
        ok(f"Integrazione: categoria trovata = '{av_category_key}'")

    # Costruisci SafetyCard con tutti i dati Allegato V
    card = SafetyCard(
        brand=brand,
        model=model,
        rischi_principali=[
            "Caduta dall'alto dal cestello",
            "Ribaltamento della piattaforma",
            "Schiacciamento durante la discesa"
        ],
        dispositivi_protezione=[
            "Imbracatura anticaduta con punto di ancoraggio nel cestello",
            "Parapetti h >= 1 m su tutti i lati",
            "Stabilizzatori estesi e bloccati"
        ],
        raccomandazioni_produttore=[
            "Non superare la portata massima marcata",
            "Verificare l'integrità dei fine corsa prima di ogni uso"
        ],
        rischi_residui=["Urto del braccio contro ostacoli aerei"],
        is_allegato_v=True,
        machine_year=machine_year,
        machine_type=machine_type,
        allegato_v_category=av_category_key,
        allegato_v_label=av_category_data["label"],
        allegato_v_requisiti=av_category_data["requisiti"],
        tabella_ce_ante=av_category_data["tabella_ce"],
        gap_ce_ante="La macchina ante-1996 non dispone di marcatura CE né di dichiarazione di conformità. Mancano interblocchi automatici tra stabilizzatori e movimenti del braccio, richiesti dalla Direttiva 2006/42/CE.",
        bozze_prescrizioni=[
            {
                "req_id": "1.3",
                "titolo": "Protezioni e parapetti cestello",
                "criticita": "alta",
                "prescrizione": "Si prescrive al datore di lavoro, ai sensi dell'Art. 70 c.1 D.Lgs. 81/08 e del punto 1.3 Allegato V, di: ripristinare i parapetti del cestello alle dimensioni previste (h minima 1 m) e reinstallare la tavola fermapiede. Termine: immediatamente."
            }
        ],
        checklist=["Verifica altezza parapetti cestello >= 1 m", "Controlla funzionamento arresto emergenza"],
        fonte_tipo="fallback_ai",
    )

    # Serializza e verifica struttura JSON
    d = card.model_dump()
    json_str = json.dumps(d, ensure_ascii=False, indent=2)

    checks = {
        "is_allegato_v = True": d.get("is_allegato_v") is True,
        "machine_year = '1985'": d.get("machine_year") == "1985",
        "allegato_v_category presente": bool(d.get("allegato_v_category")),
        "allegato_v_label presente": bool(d.get("allegato_v_label")),
        "allegato_v_requisiti non vuota": len(d.get("allegato_v_requisiti", [])) > 0,
        "tabella_ce_ante non vuota": len(d.get("tabella_ce_ante", [])) > 0,
        "gap_ce_ante stringa non vuota": bool(d.get("gap_ce_ante")),
        "bozze_prescrizioni: 1 elemento": len(d.get("bozze_prescrizioni", [])) == 1,
        "generated_at presente": bool(d.get("generated_at")),
        "brand corretto": d.get("brand") == brand,
        "model corretto": d.get("model") == model,
        "JSON serializzabile": bool(json_str),
    }

    for check_name, result in checks.items():
        if result:
            ok(f"Integrazione: {check_name}")
        else:
            fail(f"Integrazione: {check_name}")

    # Verifica che i requisiti abbiano la struttura attesa
    req = d["allegato_v_requisiti"][0]
    required_fields = ["id", "titolo", "testo", "criticita", "verifica"]
    for field in required_fields:
        if field in req:
            ok(f"Integrazione: requisito[0] ha campo '{field}'")
        else:
            fail(f"Integrazione: requisito[0] manca campo '{field}'")

except Exception as e:
    fail("Test integrazione SafetyCard+AllegatoV", traceback.format_exc(limit=4))

# ─────────────────────────────────────────────────────────────
# REPORT FINALE
# ─────────────────────────────────────────────────────────────
print("\n")
print("=" * 60)
print("RIEPILOGO FINALE")
print("=" * 60)
print(f"[OK]   Passati : {passed}")
print(f"[FAIL] Falliti : {failed}")
print(f"[WARN] Warning : {warnings}")

if problems:
    print("\nPROBLEMI TROVATI:")
    for i, p in enumerate(problems, 1):
        print(f"  {i}. {p}")
else:
    print("\nNessun problema critico rilevato.")

print(f"\nTest completati: {passed + failed} assertions")
