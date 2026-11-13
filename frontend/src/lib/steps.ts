/**
 * İş akışı adımları — sidebar, üst ray ve adım başlıkları tek kaynaktan beslenir.
 */

export type StepKey = 'upload' | 'analysis' | 'review' | 'results' | 'export'

export type Step = {
  /** Görünen numara: "01" ... "05" */
  no: string
  key: StepKey
  label: string
  hint: string
  path: string
}

export const STEPS: Step[] = [
  {
    no: '01',
    key: 'upload',
    label: 'Yükle',
    hint: 'Metraj dosyası',
    path: '/upload',
  },
  {
    no: '02',
    key: 'analysis',
    label: 'Analiz',
    hint: 'Satır durumları',
    path: '/analysis',
  },
  {
    no: '03',
    key: 'review',
    label: 'Eşleştirme',
    hint: 'Onay / düzeltme',
    path: '/review',
  },
  {
    no: '04',
    key: 'results',
    label: 'Sonuç',
    hint: 'Malzeme grupları',
    path: '/results',
  },
  {
    no: '05',
    key: 'export',
    label: 'Dışa aktarma',
    hint: 'Excel / PDF',
    path: '/export',
  },
]

export function stepByKey(key: StepKey): Step {
  const step = STEPS.find((item) => item.key === key)
  if (!step) throw new Error(`Bilinmeyen adım: ${key}`)
  return step
}
