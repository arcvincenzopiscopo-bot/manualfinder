import { useState } from 'react'
import type { SafetyCard } from '../../types'

interface Props {
  card: SafetyCard
}

export function ExportButton({ card }: Props) {
  const [loading, setLoading] = useState(false)

  const handleExport = async () => {
    setLoading(true)
    try {
      const { jsPDF } = await import('jspdf')
      const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })

      const PAGE_W = 210
      const MARGIN = 14
      const CONTENT_W = PAGE_W - MARGIN * 2
      let y = MARGIN

      // ── Helpers ──────────────────────────────────────────────────────────
      const newPage = () => {
        doc.addPage()
        y = MARGIN
      }

      const newPageIfNeeded = (needed: number) => {
        if (y + needed > 284) newPage()
      }

      const writeWrapped = (
        text: string,
        fontSize: number,
        color: [number, number, number],
        indent = 0,
        bold = false,
      ) => {
        doc.setFontSize(fontSize)
        doc.setTextColor(...color)
        doc.setFont('helvetica', bold ? 'bold' : 'normal')
        const lines = doc.splitTextToSize(text, CONTENT_W - indent)
        const lineH = fontSize * 0.42 + 0.8
        newPageIfNeeded(lines.length * lineH + 1)
        doc.text(lines, MARGIN + indent, y)
        y += lines.length * lineH + 1
      }

      const sectionHeader = (
        title: string,
        textColor: [number, number, number],
        bgColor: [number, number, number],
      ) => {
        newPageIfNeeded(12)
        doc.setFillColor(...bgColor)
        doc.roundedRect(MARGIN, y, CONTENT_W, 8, 2, 2, 'F')
        doc.setFontSize(9)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(...textColor)
        doc.text(title, MARGIN + 3, y + 5.5)
        y += 10
      }

      const divider = () => {
        doc.setDrawColor(226, 232, 240)
        doc.line(MARGIN, y, PAGE_W - MARGIN, y)
        y += 4
      }

      const infoBox = (
        text: string,
        bgColor: [number, number, number],
        borderColor: [number, number, number],
        textColor: [number, number, number],
      ) => {
        const lines = doc.splitTextToSize(text, CONTENT_W - 8)
        const lineH = 8 * 0.42 + 0.8
        const boxH = lines.length * lineH + 6
        newPageIfNeeded(boxH + 2)
        doc.setFillColor(...bgColor)
        doc.setDrawColor(...borderColor)
        doc.roundedRect(MARGIN, y, CONTENT_W, boxH, 2, 2, 'FD')
        doc.setFontSize(8)
        doc.setFont('helvetica', 'normal')
        doc.setTextColor(...textColor)
        doc.text(lines, MARGIN + 4, y + lineH + 1)
        y += boxH + 3
      }

      // ── Intestazione ─────────────────────────────────────────────────────
      doc.setFillColor(30, 64, 175)
      doc.roundedRect(MARGIN, y, CONTENT_W, 22, 3, 3, 'F')
      doc.setTextColor(255, 255, 255)
      doc.setFontSize(16)
      doc.setFont('helvetica', 'bold')
      doc.text('SCHEDA DI SICUREZZA', MARGIN + 4, y + 8)
      doc.setFontSize(11)
      doc.setFont('helvetica', 'normal')
      doc.text(`${card.brand}  ${card.model}`, MARGIN + 4, y + 16)
      y += 26

      doc.setFontSize(8)
      doc.setTextColor(100, 116, 139)
      doc.setFont('helvetica', 'normal')
      const sourceLabel = card.fonte_tipo === 'fallback_ai' ? 'AI (senza manuale ufficiale)'
        : card.fonte_tipo === 'inail+produttore' ? 'INAIL + Manuale produttore'
        : card.fonte_tipo === 'inail' ? 'Scheda INAIL'
        : card.fonte_tipo === 'pdf' ? 'Manuale produttore'
        : card.fonte_tipo ?? ''
      doc.text(
        `Generata il ${new Date(card.generated_at).toLocaleString('it-IT')}  |  Fonte: ${sourceLabel}  |  ManualFinder`,
        MARGIN, y
      )
      y += 5

      if (card.fonte_manuale) {
        doc.setFontSize(7)
        doc.text(`Manuale: ${card.fonte_manuale}`, MARGIN, y)
        y += 4
      }
      if (card.fonte_inail) {
        doc.setFontSize(7)
        doc.text(`INAIL: ${card.fonte_inail}`, MARGIN, y)
        y += 4
      }
      y += 1
      divider()

      // ── Warning fallback AI ───────────────────────────────────────────────
      if (card.fonte_tipo === 'fallback_ai') {
        infoBox(
          '⚠  ATTENZIONE: Scheda generata senza manuale ufficiale tramite conoscenza AI. ' +
          'Verificare sempre con la documentazione originale del costruttore prima di utilizzare questi dati per prescrizioni ispettive.',
          [255, 251, 235], [252, 211, 77], [146, 64, 14]
        )
      }

      // ── Safety Gate alerts ────────────────────────────────────────────────
      if (card.safety_alerts?.length) {
        sectionHeader('🚨 AVVISI SAFETY GATE EU', [153, 27, 27], [254, 226, 226])
        doc.setFont('helvetica', 'normal')
        for (const alert of card.safety_alerts) {
          newPageIfNeeded(20)
          writeWrapped(`⚠ ${alert.title}`, 9, [153, 27, 27], 2, true)
          if (alert.description) writeWrapped(alert.description, 8, [51, 65, 85], 4)
          if (alert.measures)    writeWrapped(`Misure: ${alert.measures}`, 8, [51, 65, 85], 4)
          if (alert.reference)   writeWrapped(`Rif.: ${alert.reference}`, 7, [100, 116, 139], 4)
          y += 2
        }
        y += 2
      }

      // ── Abilitazione operatore ────────────────────────────────────────────
      if (card.abilitazione_operatore) {
        sectionHeader('🪪 ABILITAZIONE OPERATORE RICHIESTA', [30, 64, 175], [219, 234, 254])
        writeWrapped(card.abilitazione_operatore, 9, [30, 64, 175], 2)
        y += 3
      }

      // ── Verifiche periodiche ──────────────────────────────────────────────
      if (card.verifiche_periodiche) {
        sectionHeader('🗓 VERIFICHE PERIODICHE OBBLIGATORIE', [154, 52, 18], [255, 237, 213])
        writeWrapped(card.verifiche_periodiche, 9, [154, 52, 18], 2)
        y += 3
      }

      // ── Sezioni principali ────────────────────────────────────────────────
      type SectionDef = {
        title: string
        items: (string | { testo: string; fonte: string })[]
        color: [number, number, number]
        bg: [number, number, number]
      }
      const mainSections: SectionDef[] = [
        { title: 'RISCHI PRINCIPALI',          items: card.rischi_principali,          color: [153, 27, 27],  bg: [254, 242, 242] },
        { title: 'DISPOSITIVI DI PROTEZIONE',  items: card.dispositivi_protezione,     color: [22, 101, 52],  bg: [240, 253, 244] },
        { title: 'RACCOMANDAZIONI PRODUTTORE', items: card.raccomandazioni_produttore, color: [30, 58, 138],  bg: [239, 246, 255] },
        { title: 'RISCHI RESIDUI',             items: card.rischi_residui,             color: [120, 53, 15],  bg: [255, 251, 235] },
      ]

      for (const section of mainSections) {
        if (!section.items?.length) continue
        sectionHeader(section.title, section.color, section.bg)
        doc.setFont('helvetica', 'normal')
        for (const item of section.items) {
          const testo = typeof item === 'string' ? item : (item.testo ?? '')
          const fonte = typeof item === 'string' ? '' : (item.fonte ?? '')
          writeWrapped(`• ${testo}${fonte ? ` [${fonte}]` : ''}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Dispositivi di sicurezza ──────────────────────────────────────────
      if (card.dispositivi_sicurezza?.length) {
        sectionHeader('DISPOSITIVI DI SICUREZZA DA VERIFICARE', [12, 74, 110], [240, 249, 255])
        for (const d of card.dispositivi_sicurezza) {
          newPageIfNeeded(18)
          writeWrapped(`${d.nome} (${d.tipo?.replace('_', ' ')})${d.fonte ? ` [${d.fonte}]` : ''}`, 9, [12, 74, 110], 2, true)
          if (d.descrizione)        writeWrapped(d.descrizione, 8, [71, 85, 105], 4)
          if (d.verifica_ispezione) writeWrapped(`▶ Verifica: ${d.verifica_ispezione}`, 8, [22, 101, 52], 4)
          y += 2
        }
        y += 2
      }

      // ── Limiti operativi ──────────────────────────────────────────────────
      if (card.limiti_operativi?.length) {
        sectionHeader('📐 LIMITI OPERATIVI', [88, 28, 135], [250, 245, 255])
        for (const item of card.limiti_operativi) {
          const testo = typeof item === 'string' ? item : (item.testo ?? '')
          const fonte = typeof item === 'string' ? '' : (item.fonte ?? '')
          writeWrapped(`• ${testo}${fonte ? ` [${fonte}]` : ''}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Procedure di emergenza ────────────────────────────────────────────
      if (card.procedure_emergenza?.length) {
        sectionHeader('🚨 PROCEDURE DI EMERGENZA', [153, 27, 27], [254, 242, 242])
        for (const item of card.procedure_emergenza) {
          const testo = typeof item === 'string' ? item : (item.testo ?? '')
          const fonte = typeof item === 'string' ? '' : (item.fonte ?? '')
          writeWrapped(`• ${testo}${fonte ? ` [${fonte}]` : ''}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Pittogrammi di sicurezza ──────────────────────────────────────────
      if (card.pittogrammi_sicurezza?.length) {
        sectionHeader('⚠ PITTOGRAMMI DI SICUREZZA DA VERIFICARE', [120, 53, 15], [255, 251, 235])
        for (const p of card.pittogrammi_sicurezza) {
          writeWrapped(`• ${p}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Documenti da richiedere ───────────────────────────────────────────
      if (card.documenti_da_richiedere?.length) {
        sectionHeader('📋 DOCUMENTI DA RICHIEDERE AL DATORE DI LAVORO', [22, 101, 52], [240, 253, 244])
        for (const d of card.documenti_da_richiedere) {
          writeWrapped(`• ${d}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Checklist sopralluogo ─────────────────────────────────────────────
      if (card.checklist?.length) {
        sectionHeader('✅ CHECKLIST SOPRALLUOGO', [30, 64, 175], [239, 246, 255])
        for (let i = 0; i < card.checklist.length; i++) {
          newPageIfNeeded(8)
          // Piccolo checkbox vuoto
          doc.setDrawColor(100, 116, 139)
          doc.rect(MARGIN + 2, y - 3.5, 3.5, 3.5)
          writeWrapped(`     ${card.checklist[i]}`, 9, [51, 65, 85], 2)
          y += 0.5
        }
        y += 3
      }

      // ── Allegato V ───────────────────────────────────────────────────────
      if (card.is_allegato_v) {
        sectionHeader('⚠ MACCHINA ANTE-1996 — ALLEGATO V D.LGS. 81/08', [153, 27, 27], [254, 226, 226])
        if (card.machine_year)        writeWrapped(`Anno di fabbricazione: ${card.machine_year}`, 9, [153, 27, 27], 2, true)
        if (card.allegato_v_label)    writeWrapped(`Categoria: ${card.allegato_v_label}`, 9, [51, 65, 85], 2)
        if (card.gap_ce_ante)         writeWrapped(`Gap rispetto alla Direttiva Macchine 2006/42/CE: ${card.gap_ce_ante}`, 8, [71, 85, 105], 2)
        y += 3

        if (card.bozze_prescrizioni?.length) {
          sectionHeader('📝 BOZZE PRESCRIZIONI (Allegato V)', [120, 53, 15], [255, 247, 237])
          for (const p of card.bozze_prescrizioni) {
            newPageIfNeeded(20)
            const critColor: [number, number, number] = p.criticita === 'alta' ? [153, 27, 27] : p.criticita === 'media' ? [120, 53, 15] : [51, 65, 85]
            writeWrapped(`[${(p.criticita ?? '').toUpperCase()}] ${p.titolo ?? ''}`, 9, critColor, 2, true)
            if (p.prescrizione) writeWrapped(p.prescrizione, 8, [51, 65, 85], 4)
            y += 2
          }
          y += 2
        }
      }

      // ── Note ─────────────────────────────────────────────────────────────
      if (card.note) {
        newPageIfNeeded(14)
        doc.setFillColor(248, 250, 252)
        doc.setDrawColor(226, 232, 240)
        doc.roundedRect(MARGIN, y, CONTENT_W, 7, 2, 2, 'FD')
        doc.setFontSize(8)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(71, 85, 105)
        doc.text('NOTE', MARGIN + 3, y + 5)
        y += 9
        writeWrapped(card.note, 8, [71, 85, 105], 2)
        y += 3
      }

      // ── Confidence AI ─────────────────────────────────────────────────────
      if (card.confidence_ai) {
        const confLabel = card.confidence_ai === 'high' ? 'ALTA' : card.confidence_ai === 'medium' ? 'MEDIA' : 'BASSA'
        const confColor: [number, number, number] = card.confidence_ai === 'high' ? [22, 101, 52] : card.confidence_ai === 'medium' ? [120, 53, 15] : [153, 27, 27]
        writeWrapped(`Affidabilità AI: ${confLabel}`, 8, confColor, 0, true)
        y += 2
      }

      // ── Footer numerazione pagine ─────────────────────────────────────────
      const pageCount = doc.getNumberOfPages()
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i)
        doc.setFontSize(7)
        doc.setTextColor(148, 163, 184)
        doc.setFont('helvetica', 'normal')
        doc.text(`ManualFinder — Scheda di sicurezza ${card.brand} ${card.model}  |  Pagina ${i} di ${pageCount}`, PAGE_W / 2, 292, { align: 'center' })
      }

      // ── Salva ─────────────────────────────────────────────────────────────
      const filename = `scheda_${card.brand}_${card.model}_${new Date().toISOString().slice(0, 10)}.pdf`
        .replace(/\s+/g, '_').toLowerCase()
      doc.save(filename)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      style={{
        width: '100%',
        padding: '14px',
        background: loading ? '#94a3b8' : '#1e40af',
        color: '#fff',
        border: 'none',
        borderRadius: 8,
        fontSize: 15,
        fontWeight: 700,
        cursor: loading ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
      }}
    >
      {loading ? '⏳ Generazione PDF...' : '📄 Scarica scheda PDF'}
    </button>
  )
}
