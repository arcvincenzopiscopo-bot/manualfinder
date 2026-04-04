import { get, set, del } from 'idb-keyval'
import type { CachedResult } from '../types'

const CACHE_KEY = 'manualfinder_last_result'

export async function saveResult(result: CachedResult): Promise<void> {
  await set(CACHE_KEY, result)
}

export async function loadResult(): Promise<CachedResult | null> {
  const result = await get<CachedResult>(CACHE_KEY)
  return result ?? null
}

export async function clearResult(): Promise<void> {
  await del(CACHE_KEY)
}
