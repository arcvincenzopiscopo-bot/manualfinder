import { useCallback } from 'react'

const MAX_DIMENSION = 1920

/**
 * Ridimensiona l'immagine lato client e rimuove i metadati EXIF
 * restituendo un base64 JPEG pulito.
 */
export function useImagePreprocess() {
  const processImage = useCallback(async (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image()
      const url = URL.createObjectURL(file)

      img.onload = () => {
        URL.revokeObjectURL(url)

        let { width, height } = img
        if (Math.max(width, height) > MAX_DIMENSION) {
          const ratio = MAX_DIMENSION / Math.max(width, height)
          width = Math.round(width * ratio)
          height = Math.round(height * ratio)
        }

        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext('2d')!
        ctx.drawImage(img, 0, 0, width, height)

        // toDataURL rimuove EXIF e restituisce JPEG puro
        const dataUrl = canvas.toDataURL('image/jpeg', 0.92)
        const base64 = dataUrl.split(',')[1]
        resolve(base64)
      }

      img.onerror = () => {
        URL.revokeObjectURL(url)
        reject(new Error('Impossibile caricare l\'immagine'))
      }

      img.src = url
    })
  }, [])

  return { processImage }
}
