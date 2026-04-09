import { useState } from 'react'
import type { SafetyCard } from '../../types'

interface Props {
  card: SafetyCard
  onBeforeExport?: () => void
  onAfterExport?: () => void
}

/**
 * Scansiona le righe di pixel attorno a targetY per trovare la riga più "chiara"
 * (meno pixel scuri) entro ±searchPx, così da evitare di tagliare testo a metà.
 */
function findBestSplitY(canvas: HTMLCanvasElement, targetY: number, searchPx = 40): number {
  const ctx = canvas.getContext('2d')
  if (!ctx) return targetY
  const startY = Math.max(0, targetY - searchPx)
  const endY = Math.min(canvas.height, targetY + searchPx)
  const height = endY - startY
  if (height <= 0) return targetY
  const imageData = ctx.getImageData(0, startY, canvas.width, height)
  let minDark = Infinity
  let bestY = targetY
  for (let row = 0; row < height; row++) {
    let darkCount = 0
    for (let col = 0; col < canvas.width; col++) {
      const i = (row * canvas.width + col) * 4
      const brightness = (imageData.data[i] + imageData.data[i + 1] + imageData.data[i + 2]) / 3
      if (brightness < 200) darkCount++
    }
    if (darkCount < minDark) {
      minDark = darkCount
      bestY = startY + row
    }
  }
  return bestY
}

export function ExportButton({ card, onBeforeExport, onAfterExport }: Props) {
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleExport = async () => {
    setLoading(true)
    // Attiva isPrinting in SafetyCard per rendere visibili entrambe le viste durante l'export
    onBeforeExport?.()
    await new Promise(r => setTimeout(r, 80)) // attendi re-render con entrambe le sezioni
    try {
      // Trova il container della scheda nel DOM
      const cardEl = document.querySelector<HTMLElement>('.safety-card-printable')
      if (!cardEl) {
        alert('Impossibile trovare la scheda da esportare.')
        return
      }

      const [{ jsPDF }, html2canvas] = await Promise.all([
        import('jspdf'),
        import('html2canvas').then(m => m.default),
      ])

      const PAGE_W_MM  = 210
      const PAGE_H_MM  = 297
      const MARGIN_MM  = 10
      const CONTENT_W_MM = PAGE_W_MM - MARGIN_MM * 2

      // ── 1. Cattura il DOM come canvas ─────────────────────────────────────
      // scale=1.5 → buon compromesso qualità/dimensione file (~3-5MB invece di 10-15MB)
      const canvas = await html2canvas(cardEl, {
        scale: 1.5,
        useCORS: true,
        allowTaint: false,
        backgroundColor: '#ffffff',
        logging: false,
        ignoreElements: (el) =>
          el.classList.contains('export-btn-wrapper') ||
          el.classList.contains('manual-link-actions'),
      })

      const imgW_px   = canvas.width
      const imgH_px   = canvas.height

      // ── 2. Calcola l'altezza dell'immagine in mm rispettando le proporzioni ─
      const imgW_mm   = CONTENT_W_MM
      const imgH_mm   = (imgH_px / imgW_px) * imgW_mm

      // ── 3. Genera il PDF suddividendo in pagine A4 ────────────────────────
      const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })

      const pageContentH_mm = PAGE_H_MM - MARGIN_MM * 2
      const totalPages = Math.ceil(imgH_mm / pageContentH_mm)

      // Tiene traccia della Y effettiva usata per ogni pagina (in pixel), per evitare
      // di accumulare sfasamenti tra taglio "naturale" e taglio "smart"
      let prevSrcY_px = 0

      for (let page = 0; page < totalPages; page++) {
        if (page > 0) doc.addPage()

        const srcY_px = page === 0
          ? 0
          : findBestSplitY(canvas, Math.round((page * pageContentH_mm / imgH_mm) * imgH_px))

        const sliceH_px = Math.min(
          Math.round(((page + 1) * pageContentH_mm / imgH_mm) * imgH_px) - srcY_px,
          imgH_px - srcY_px,
        )

        const sliceCanvas = document.createElement('canvas')
        sliceCanvas.width  = imgW_px
        sliceCanvas.height = Math.ceil(sliceH_px)
        const ctx = sliceCanvas.getContext('2d')!
        ctx.drawImage(canvas, 0, -srcY_px)

        const sliceData = sliceCanvas.toDataURL('image/jpeg', 0.82)
        const sliceH_mm = (sliceCanvas.height / imgW_px) * imgW_mm

        doc.addImage(sliceData, 'JPEG', MARGIN_MM, MARGIN_MM, imgW_mm, sliceH_mm)

        // Footer: numero pagina
        doc.setFontSize(7)
        doc.setTextColor(148, 163, 184)
        doc.setFont('helvetica', 'normal')
        doc.text(
          `ManualFinder — Scheda di sicurezza ${card.brand} ${card.model}  |  Pagina ${page + 1} di ${totalPages}`,
          PAGE_W_MM / 2,
          PAGE_H_MM - 4,
          { align: 'center' },
        )

        prevSrcY_px = srcY_px
      }
      void prevSrcY_px

      // ── 4. Salva ──────────────────────────────────────────────────────────
      const filename = `scheda_${card.brand}_${card.model}_${new Date().toISOString().slice(0, 10)}.pdf`
        .replace(/\s+/g, '_').toLowerCase()
      doc.save(filename)

      // Feedback visivo: rassicura l'utente (specie su mobile) che la scheda è ancora attiva
      setSaved(true)
      setTimeout(() => setSaved(false), 3500)

    } catch (err) {
      console.error('Export PDF error:', err)
      alert('Errore durante la generazione del PDF. Riprova.')
    } finally {
      onAfterExport?.()
      setLoading(false)
    }
  }

  const bgColor = loading ? '#94a3b8' : saved ? '#16a34a' : '#1e40af'
  const label   = loading ? '⏳ Generazione PDF...' : saved ? '✓ PDF salvato — puoi continuare' : '📄 Scarica scheda PDF'

  return (
    <div className="export-btn-wrapper">
      <button
        onClick={handleExport}
        disabled={loading}
        style={{
          width: '100%',
          padding: '14px',
          background: bgColor,
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
          transition: 'background 0.2s',
        }}
      >
        {label}
      </button>
    </div>
  )
}
