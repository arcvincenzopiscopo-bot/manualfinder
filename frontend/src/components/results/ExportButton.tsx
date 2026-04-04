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
      const newPageIfNeeded = (needed: number) => {
        if (y + needed > 285) {
          doc.addPage()
          y = MARGIN
        }
      }

      const writeWrapped = (text: string, fontSize: number, color: [number, number, number], indent = 0) => {
        doc.setFontSize(fontSize)
        doc.setTextColor(...color)
        const lines = doc.splitTextToSize(text, CONTENT_W - indent)
        newPageIfNeeded(lines.length * (fontSize * 0.4 + 1))
        doc.text(lines, MARGIN + indent, y)
        y += lines.length * (fontSize * 0.4 + 1) + 1
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

      // Data generazione
      doc.setFontSize(8)
      doc.setTextColor(100, 116, 139)
      doc.setFont('helvetica', 'normal')
      doc.text(
        `Generata il ${new Date(card.generated_at).toLocaleString('it-IT')}  |  ManualFinder`,
        MARGIN, y
      )
      y += 6

      // Riga divisoria
      doc.setDrawColor(226, 232, 240)
      doc.line(MARGIN, y, PAGE_W - MARGIN, y)
      y += 5

      // ── Sezioni ──────────────────────────────────────────────────────────
      type SectionDef = {
        title: string
        items: (string | { testo: string; fonte: string })[]
        color: [number, number, number]
        bg: [number, number, number]
      }
      const sections: SectionDef[] = [
        { title: 'RISCHI PRINCIPALI',            items: card.rischi_principali,          color: [153, 27, 27],  bg: [254, 242, 242] },
        { title: 'DISPOSITIVI DI PROTEZIONE',    items: card.dispositivi_protezione,     color: [22, 101, 52],  bg: [240, 253, 244] },
        { title: 'RACCOMANDAZIONI PRODUTTORE',   items: card.raccomandazioni_produttore, color: [30, 58, 138],  bg: [239, 246, 255] },
        { title: 'RISCHI RESIDUI',               items: card.rischi_residui,             color: [120, 53, 15],  bg: [255, 251, 235] },
      ]

      for (const section of sections) {
        if (!section.items.length) continue
        newPageIfNeeded(14)

        // Sfondo intestazione sezione
        doc.setFillColor(...section.bg)
        doc.roundedRect(MARGIN, y, CONTENT_W, 8, 2, 2, 'F')
        doc.setFontSize(9)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(...section.color)
        doc.text(section.title, MARGIN + 3, y + 5.5)
        y += 10

        // Voci con fonte
        doc.setFont('helvetica', 'normal')
        for (const item of section.items) {
          newPageIfNeeded(6)
          const testo = typeof item === 'string' ? item : (item.testo ?? '')
          const fonte = typeof item === 'string' ? '' : (item.fonte ?? '')
          const fonteTag = fonte ? ` [${fonte}]` : ''
          writeWrapped(`• ${testo}${fonteTag}`, 9, [51, 65, 85], 2)
          y += 1
        }
        y += 3
      }

      // ── Dispositivi di sicurezza ──────────────────────────────────────────
      if (card.dispositivi_sicurezza?.length) {
        newPageIfNeeded(14)
        doc.setFillColor(240, 249, 255)
        doc.roundedRect(MARGIN, y, CONTENT_W, 8, 2, 2, 'F')
        doc.setFontSize(9)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(12, 74, 110)
        doc.text('DISPOSITIVI DI SICUREZZA DA VERIFICARE', MARGIN + 3, y + 5.5)
        y += 10

        doc.setFont('helvetica', 'normal')
        for (const d of card.dispositivi_sicurezza) {
          newPageIfNeeded(14)
          doc.setFont('helvetica', 'bold')
          writeWrapped(`${d.nome} (${d.tipo.replace('_', ' ')}) [${d.fonte}]`, 9, [12, 74, 110], 2)
          doc.setFont('helvetica', 'normal')
          writeWrapped(d.descrizione, 8, [71, 85, 105], 4)
          writeWrapped(`Verifica: ${d.verifica_ispezione}`, 8, [22, 101, 52], 4)
          y += 2
        }
        y += 3
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

      // ── Warning fallback ──────────────────────────────────────────────────
      if (card.fonte_tipo === 'fallback_ai') {
        newPageIfNeeded(12)
        doc.setFillColor(255, 251, 235)
        doc.setDrawColor(252, 211, 77)
        doc.roundedRect(MARGIN, y, CONTENT_W, 10, 2, 2, 'FD')
        doc.setFontSize(8)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(146, 64, 14)
        doc.text('⚠  ATTENZIONE: Scheda generata senza manuale ufficiale. Verificare con la documentazione del costruttore.', MARGIN + 3, y + 4, { maxWidth: CONTENT_W - 6 })
        y += 14
      }

      // ── Footer ────────────────────────────────────────────────────────────
      const pageCount = doc.getNumberOfPages()
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i)
        doc.setFontSize(7)
        doc.setTextColor(148, 163, 184)
        doc.setFont('helvetica', 'normal')
        doc.text(`Pagina ${i} di ${pageCount}`, PAGE_W / 2, 292, { align: 'center' })
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
