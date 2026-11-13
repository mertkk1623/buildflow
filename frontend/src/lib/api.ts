/**
 * Backend ile konuşan tek nokta.
 *
 * Geliştirmede Vite proxy'si `/api` isteklerini FastAPI'ye yönlendirir.
 * Farklı bir adres gerektiğinde `VITE_API_BASE_URL` ile override edilir.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export type HealthResponse = {
  status: string
  environment: string
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, { signal })

  if (!response.ok) {
    throw new Error(`Sağlık kontrolü başarısız (HTTP ${response.status})`)
  }

  return (await response.json()) as HealthResponse
}
