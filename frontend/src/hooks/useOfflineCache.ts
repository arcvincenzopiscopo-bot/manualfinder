import { useState, useEffect } from 'react'
import { saveResult, loadResult } from '../services/offlineStore'
import type { CachedResult, SafetyCard, PlateOCRResult } from '../types'

export function useOfflineCache() {
  const [cached, setCached] = useState<CachedResult | null>(null)
  const [isOnline, setIsOnline] = useState(navigator.onLine)

  useEffect(() => {
    loadResult().then(setCached)

    const onOnline = () => setIsOnline(true)
    const onOffline = () => setIsOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const save = async (safetyCard: SafetyCard, ocr: PlateOCRResult | null) => {
    const result: CachedResult = { safetyCard, ocr, timestamp: Date.now() }
    await saveResult(result)
    setCached(result)
  }

  return { cached, isOnline, save }
}
