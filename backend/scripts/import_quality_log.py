"""
Script one-shot per importare i record quality_log salvati prima della migrazione su DB.
Esegui con: python -m scripts.import_quality_log
dalla cartella backend/
"""
import json
import sys
import os

# Aggiungi la root del backend al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

HISTORICAL_DATA = [
    {"ts":"2026-04-06T17:55:35.896861+00:00","macchina":"Rozzi RR800","machine_type":"benna a polipo","fonte_tipo":"pdf","producer_url":"https://www.idrobenne.com/uploads/flipbook/2019/it/catalogo_it.pdf","inail_url":"","producer_match":"category","producer_pages":36,"n_rischi":5,"n_checklist":6,"has_abilitazione":True,"has_verifiche":True,"issues":[{"type":"suspicious_producer_url","severity":"medium","message":"URL produttore contiene 'catalog' — potrebbe essere un catalogo, non un manuale d'uso: https://www.idrobenne.com/uploads/flipbook/2019/it/catalogo_it.pdf"}],"n_issues":1,"has_high":False},
    {"ts":"2026-04-06T17:49:22.033371+00:00","macchina":"VAIA CAR S.p.A. BCO-7/120","machine_type":"benna carico-pietrisco","fonte_tipo":"fallback_ai","producer_url":"https://iris.polito.it/bitstream/11583/2979244/1/RIVISTA%2BINGEGNERIA_rid.pdf","inail_url":"","producer_match":"unrelated","producer_pages":81,"n_rischi":6,"n_checklist":6,"has_abilitazione":True,"has_verifiche":True,"issues":[{"type":"unrelated_producer_pdf","severity":"high","message":"Il PDF produttore è stato classificato come 'unrelated' ma è stato usato lo stesso"}],"n_issues":1,"has_high":True},
    {"ts":"2026-04-06T17:40:21.496584+00:00","macchina":"VAIA CAR KUBE","machine_type":"saldatrice","fonte_tipo":"pdf","producer_url":"https://d347awuzx0kdse.cloudfront.net/pacsolutions/content-file/Brochure%20Kube.pdf","inail_url":"","producer_match":"exact","producer_pages":158,"n_rischi":7,"n_checklist":10,"has_abilitazione":True,"has_verifiche":False,"issues":[{"type":"suspicious_producer_url","severity":"medium","message":"URL produttore contiene 'brochure' — potrebbe essere un catalogo, non un manuale d'uso"},{"type":"wrong_abilitazione_cited","severity":"medium","message":"'saldatrice' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita"}],"n_issues":2,"has_high":False},
    {"ts":"2026-04-06T17:33:30.375914+00:00","macchina":" EF-450GS","machine_type":"saldatrice","fonte_tipo":"fallback_ai","producer_url":"","inail_url":"","producer_match":"unknown","producer_pages":0,"n_rischi":8,"n_checklist":8,"has_abilitazione":True,"has_verifiche":True,"issues":[{"type":"wrong_abilitazione_cited","severity":"medium","message":"'saldatrice' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita"},{"type":"spurious_verifiche","severity":"low","message":"'saldatrice' NON è soggetta ad Allegato VII ma verifiche_periodiche è valorizzato"}],"n_issues":2,"has_high":False},
    {"ts":"2026-04-06T17:26:13.343172+00:00","macchina":"IMER IM 4680","machine_type":"piattaforma aerea a braccio","fonte_tipo":"inail","producer_url":"https://www.officinadelcarrello.it/wp-content/uploads/2023/10/MANUALE-PLE-2020.pdf","inail_url":"/manuals/local/Scheda 3 - PIATTAFORME MOBILI DI LAVORO ELEVABILI.pdf","producer_match":"unrelated","producer_pages":60,"n_rischi":7,"n_checklist":10,"has_abilitazione":True,"has_verifiche":True,"issues":[{"type":"unrelated_producer_pdf","severity":"high","message":"Il PDF produttore è stato classificato come 'unrelated' ma è stato usato lo stesso"}],"n_issues":1,"has_high":True},
    {"ts":"2026-04-06T17:21:41.921643+00:00","macchina":"OMC RONDA 700","machine_type":"troncatrice per alluminio","fonte_tipo":"pdf","producer_url":"https://www.mtm-online.it/pdf/01_2010.pdf","inail_url":"","producer_match":"category","producer_pages":84,"n_rischi":0,"n_checklist":0,"has_abilitazione":True,"has_verifiche":False,"issues":[{"type":"empty_rischi","severity":"high","message":"Nessun rischio estratto — il documento potrebbe essere un catalogo o non pertinente"},{"type":"empty_checklist","severity":"medium","message":"Nessuna voce checklist — il documento non contiene istruzioni ispettive"},{"type":"empty_dispositivi","severity":"low","message":"Nessun dispositivo di sicurezza estratto dal documento"}],"n_issues":3,"has_high":True},
    {"ts":"2026-04-06T17:16:30.675362+00:00","macchina":"LEADERMEC P26","machine_type":"pressa piegatrice","fonte_tipo":"fallback_ai","producer_url":"","inail_url":"","producer_match":"unknown","producer_pages":0,"n_rischi":7,"n_checklist":7,"has_abilitazione":True,"has_verifiche":True,"issues":[{"type":"expected_manual_not_found","severity":"medium","message":"Nessun manuale trovato per 'pressa piegatrice' — atteso per questa categoria"},{"type":"wrong_abilitazione_cited","severity":"medium","message":"'pressa piegatrice' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita"}],"n_issues":2,"has_high":False},
    {"ts":"2026-04-06T17:11:51.817265+00:00","macchina":"COELMO PDT113","machine_type":"generatore","fonte_tipo":"pdf","producer_url":"https://jubaili.com/wp-content/uploads/2018/09/Italian.pdf","inail_url":"","producer_match":"exact","producer_pages":71,"n_rischi":8,"n_checklist":10,"has_abilitazione":True,"has_verifiche":False,"issues":[{"type":"wrong_abilitazione_cited","severity":"medium","message":"'generatore' NON è coperta dall'Accordo S-R 2012 ma l'abilitazione la cita"}],"n_issues":1,"has_high":False},
]

def main():
    import psycopg2
    from app.config import settings

    if not settings.database_url:
        print("ERROR: DATABASE_URL non configurata")
        sys.exit(1)

    conn = psycopg2.connect(settings.database_url)
    inserted = 0
    skipped = 0
    try:
        with conn.cursor() as cur:
            for entry in HISTORICAL_DATA:
                # Evita duplicati per ts+macchina
                cur.execute(
                    "SELECT 1 FROM quality_log WHERE ts = %s AND macchina = %s",
                    (entry["ts"], entry["macchina"])
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO quality_log (
                        ts, macchina, machine_type, fonte_tipo,
                        producer_url, inail_url, producer_match, producer_pages,
                        n_rischi, n_checklist, has_abilitazione, has_verifiche,
                        issues, n_issues, has_high
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        entry["ts"], entry["macchina"], entry["machine_type"], entry["fonte_tipo"],
                        entry.get("producer_url",""), entry.get("inail_url",""),
                        entry["producer_match"], entry["producer_pages"],
                        entry["n_rischi"], entry["n_checklist"],
                        entry["has_abilitazione"], entry["has_verifiche"],
                        json.dumps(entry["issues"]), entry["n_issues"], entry["has_high"],
                    )
                )
                inserted += 1
        conn.commit()
        print(f"Importati {inserted} record, saltati {skipped} duplicati.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
