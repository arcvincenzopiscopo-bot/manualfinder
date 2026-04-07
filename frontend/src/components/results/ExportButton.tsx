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

      // ── 1. Cattura il DOM come canvas ad alta risoluzione ─────────────────
      // scale=2 → 2× pixel density (equivale a 144 DPI su schermo 72 DPI)
      // useCORS=true → permette immagini da domini esterni (es. Supabase storage)
      const canvas = await html2canvas(cardEl, {
        scale: 2,
        useCORS: true,
        allowTaint: false,
        backgroundColor: '#ffffff',
        logging: false,
        // Ignora elementi interattivi che non devono finire nel PDF
        ignoreElements: (el) =>
          el.classList.contains('export-btn-wrapper') ||
          el.classList.contains('manual-link-actions'),
      })

      const imgData   = canvas.toDataURL('image/jpeg', 0.92)
      const imgW_px   = canvas.width
      const imgH_px   = canvas.height

      // ── 2. Calcola l'altezza dell'immagine in mm rispettando le proporzioni ─
      const imgW_mm   = CONTENT_W_MM
      const imgH_mm   = (imgH_px / imgW_px) * imgW_mm

      // ── 3. Genera il PDF suddividendo in pagine A4 ────────────────────────
      const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })

      const pageContentH_mm = PAGE_H_MM - MARGIN_MM * 2  // altezza area stampabile per pagina
      const totalPages = Math.ceil(imgH_mm / pageContentH_mm)

      for (let page = 0; page < totalPages; page++) {
        if (page > 0) doc.addPage()

        // Offset verticale in mm del "ritaglio" sull'immagine totale
        const srcOffsetMm = page * pageContentH_mm

        // Porzione di canvas (in pixel) da inserire in questa pagina
        const srcY_px = (srcOffsetMm / imgH_mm) * imgH_px
        const sliceH_px = Math.min(
          (pageContentH_mm / imgH_mm) * imgH_px,
          imgH_px - srcY_px,
        )

        // Ritaglia il canvas per questa pagina
        const sliceCanvas = document.createElement('canvas')
        sliceCanvas.width  = imgW_px
        sliceCanvas.height = Math.ceil(sliceH_px)
        const ctx = sliceCanvas.getContext('2d')!
        ctx.drawImage(canvas, 0, -srcY_px)

        const sliceData = sliceCanvas.toDataURL('image/jpeg', 0.92)
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
      }

      // ── 4. Salva ──────────────────────────────────────────────────────────
      const filename = `scheda_${card.brand}_${card.model}_${new Date().toISOString().slice(0, 10)}.pdf`
        .replace(/\s+/g, '_').toLowerCase()
      doc.save(filename)

    } catch (err) {
      console.error('Export PDF error:', err)
      alert('Errore durante la generazione del PDF. Riprova.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="export-btn-wrapper">
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
    </div>
  )
}
