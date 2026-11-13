import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import {
  ApiAbortError,
  ApiConnectionError,
  analyzeFile,
  calculate as callCalculate,
  downloadTemplate,
  triggerDownload,
  type DownloadResult,
} from '../lib/api'
import {
  buildCalculateRequest,
  approveDecision,
  rejectDecision,
  type UnsendableRow,
} from '../lib/payload'
import type { AnalyzeResponse, CalculateRequest, CalculateResponse } from '../types/api'
import {
  aiSuggestionView,
  countStatuses,
  decisionCapability,
  deriveReviewRows,
  type AnalyzeView,
  type ReviewRow,
  type RowDecision,
  type StatusCounts,
  type WorkflowStage,
} from '../types/workflow'

/**
 * İş akışı durumu — uygulamanın tek gerçek kaynağı.
 *
 * Sorumluluk sınırı
 * -----------------
 * Bu katman **hesaplama yapmaz**. Yalnızca:
 * 1. dosyayı `/api/analyze`'e gönderir ve yanıtı saklar,
 * 2. kullanıcı kararlarını `boq_no` anahtarıyla tutar,
 * 3. ham satırlar + kararları `/api/calculate`'e gönderir,
 * 4. dönen `CalculateResponse`'u **olduğu gibi** saklar.
 *
 * Ekranlar `calculation.groups` içindeki değerleri yeniden üretmez; yalnızca
 * biçimlendirir.
 */

export type WorkflowError = {
  /** Hatanın hangi işlemden geldiği — ekranlar buna göre mesaj seçer. */
  stage: 'template' | 'analyze' | 'calculate' | 'report'
  title: string
  message: string
  detail: string
  suggestion: string
  issues: import('../types/api').ApiIssue[]
}

type State = {
  stage: WorkflowStage
  fileName: string | null
  fileSize: number | null
  analysis: AnalyzeResponse | null
  decisions: Record<string, RowDecision>
  calculation: CalculateResponse | null
  /** Rapor üretimi için son hesaplamanın gövdesi. */
  calculationRequest: CalculateRequest | null
  unsendable: UnsendableRow[]
  error: WorkflowError | null
  templateStatus: 'idle' | 'downloading' | 'error'
  templateError: WorkflowError | null
}

const INITIAL_STATE: State = {
  stage: 'idle',
  fileName: null,
  fileSize: null,
  analysis: null,
  decisions: {},
  calculation: null,
  calculationRequest: null,
  unsendable: [],
  error: null,
  templateStatus: 'idle',
  templateError: null,
}

/**
 * Akış bağlamının sözleşmesi.
 *
 * Testler bu tipi kullanır: bağlamın şekli tek yerde tanımlı kalsın, testte
 * elle yeniden yazılmasın.
 */
export type WorkflowContextValue = {
  stage: WorkflowStage
  fileName: string | null
  fileSize: number | null
  analysis: AnalyzeResponse | null
  /** Analizin ekran görünümü — yoksa `null`. */
  analyzeView: AnalyzeView | null
  rows: ReviewRow[]
  counts: StatusCounts
  total: number
  /** Onaya hazır (kural) + kullanıcı onaylı satır sayısı. */
  eligibleCount: number
  /** Hesaba girmeyen satır sayısı. */
  heldCount: number
  calculation: CalculateResponse | null
  calculationRequest: CalculateRequest | null
  unsendable: UnsendableRow[]
  error: WorkflowError | null
  templateStatus: State['templateStatus']
  templateError: WorkflowError | null

  /** Dosyayı analiz eder; hata durumunda `error` dolar. */
  analyze: (file: File) => Promise<void>
  approveRow: (boqNo: string, code: string) => void
  rejectRow: (boqNo: string) => void
  clearDecision: (boqNo: string) => void
  /** Kararları gönderip hesaplamayı çalıştırır. */
  runCalculation: () => Promise<CalculateResponse | null>
  /** Şablonu indirir; başarıda dosya tarayıcıya verilir. */
  saveTemplate: () => Promise<void>
  /** Akışı sıfırlar (dosya + kararlar + sonuçlar). */
  reset: () => void
  /** Hata kutusunu kapatır; durum korunur. */
  dismissError: () => void
}

const WorkflowContext = createContext<WorkflowContextValue | null>(null)

/** `ApiError`, `ApiConnectionError` ve `ApiAbortError` için tek dönüştürücü. */
export function toWorkflowError(
  stage: WorkflowError['stage'],
  error: unknown,
): WorkflowError {
  if (error instanceof ApiAbortError) {
    return {
      stage,
      title: 'İstek iptal edildi',
      message: error.message,
      detail: '',
      suggestion: 'İşlemi yeniden başlatabilirsiniz.',
      issues: [],
    }
  }

  if (error instanceof ApiConnectionError) {
    return {
      stage,
      title: 'Bağlantı kurulamadı',
      message: error.message,
      detail: '',
      suggestion:
        'Backend servisinin çalıştığını ve API adresini kontrol edin.',
      issues: [],
    }
  }

  if (error instanceof Error) {
    const candidate = error as Error & {
      code?: string
      detail?: string
      suggestion?: string
      issues?: import('../types/api').ApiIssue[]
      status?: number
    }

    if (typeof candidate.code === 'string') {
      return {
        stage,
        title: candidate.message,
        message: candidate.message,
        detail: candidate.detail ?? '',
        suggestion: candidate.suggestion ?? '',
        issues: Array.isArray(candidate.issues) ? candidate.issues : [],
      }
    }

    return {
      stage,
      title: 'Bağlantı kurulamadı',
      message: candidate.message,
      detail: '',
      suggestion:
        'Backend servisinin çalıştığını ve API adresini kontrol edin.',
      issues: [],
    }
  }

  return {
    stage,
    title: 'Beklenmeyen bir hata oluştu',
    message: 'İşlem tamamlanamadı.',
    detail: '',
    suggestion: 'Lütfen tekrar deneyin.',
    issues: [],
  }
}

export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(INITIAL_STATE)

  /** Devam eden analiz isteği — yeni dosya seçilirse iptal edilir. */
  const analyzeAbort = useRef<AbortController | null>(null)

  const analyze = useCallback(async (file: File) => {
    analyzeAbort.current?.abort()
    const controller = new AbortController()
    analyzeAbort.current = controller

    setState((previous) => ({
      ...previous,
      stage: 'analyzing',
      fileName: file.name,
      fileSize: file.size,
      analysis: null,
      decisions: {},
      calculation: null,
      calculationRequest: null,
      unsendable: [],
      error: null,
    }))

    try {
      const analysis = await analyzeFile(file, controller.signal)
      setState((previous) => ({
        ...previous,
        stage: 'reviewing',
        analysis,
        error: null,
      }))
    } catch (error) {
      // İptal edilen istek hata olarak gösterilmez: kullanıcı yeni dosya seçti.
      if (error instanceof ApiAbortError) {
        setState((previous) =>
          previous.stage === 'analyzing'
            ? { ...previous, stage: 'idle' }
            : previous,
        )
        return
      }
      setState((previous) => ({
        ...previous,
        stage: 'error',
        error: toWorkflowError('analyze', error),
      }))
    }
  }, [])

  const approveRow = useCallback((boqNo: string, code: string) => {
    setState((previous) => ({
      ...previous,
      decisions: { ...previous.decisions, [boqNo]: approveDecision(code) },
      // Kararlar değişti: eski hesaplama artık güncel değil.
      calculation: null,
      calculationRequest: null,
    }))
  }, [])

  const rejectRow = useCallback((boqNo: string) => {
    setState((previous) => ({
      ...previous,
      decisions: { ...previous.decisions, [boqNo]: rejectDecision() },
      calculation: null,
      calculationRequest: null,
    }))
  }, [])

  const clearDecision = useCallback((boqNo: string) => {
    setState((previous) => {
      if (!(boqNo in previous.decisions)) return previous
      const decisions = { ...previous.decisions }
      delete decisions[boqNo]
      return {
        ...previous,
        decisions,
        calculation: null,
        calculationRequest: null,
      }
    })
  }, [])

  const runCalculation = useCallback(async (): Promise<CalculateResponse | null> => {
    const analysis = state.analysis
    if (!analysis) return null

    const { request, unsendable } = buildCalculateRequest(
      analysis.rows,
      state.decisions,
    )

    setState((previous) => ({
      ...previous,
      stage: 'calculating',
      error: null,
      unsendable,
    }))

    try {
      const calculation = await callCalculate(request)
      setState((previous) => ({
        ...previous,
        stage: 'done',
        calculation,
        calculationRequest: request,
        unsendable,
        error: null,
      }))
      return calculation
    } catch (error) {
      setState((previous) => ({
        ...previous,
        stage: 'error',
        error: toWorkflowError('calculate', error),
      }))
      return null
    }
  }, [state.analysis, state.decisions])

  const saveTemplate = useCallback(async () => {
    setState((previous) => ({
      ...previous,
      templateStatus: 'downloading',
      templateError: null,
    }))

    try {
      const result: DownloadResult = await downloadTemplate()
      triggerDownload(result)
      setState((previous) => ({ ...previous, templateStatus: 'idle' }))
    } catch (error) {
      setState((previous) => ({
        ...previous,
        templateStatus: 'error',
        templateError: toWorkflowError('template', error),
      }))
    }
  }, [])

  const reset = useCallback(() => {
    analyzeAbort.current?.abort()
    analyzeAbort.current = null
    setState(INITIAL_STATE)
  }, [])

  const dismissError = useCallback(() => {
    setState((previous) => ({
      ...previous,
      error: null,
      templateError: null,
      templateStatus: previous.templateStatus === 'error' ? 'idle' : previous.templateStatus,
      // Hata yalnızca kutu kapatıldığında değil, akış da toparlanabilsin.
      stage:
        previous.stage === 'error'
          ? previous.analysis
            ? 'reviewing'
            : 'idle'
          : previous.stage,
    }))
  }, [])

  const value = useMemo<WorkflowContextValue>(() => {
    const rows = state.analysis
      ? deriveReviewRows(state.analysis.rows, state.decisions)
      : []
    const counts = countStatuses(rows)
    const eligibleCount = rows.filter(
      (row) =>
        (row.status === 'rule' || row.status === 'ai-approved') &&
        Boolean(row.matchedCode),
    ).length

    const analyzeView: AnalyzeView | null = state.analysis
      ? {
          fileName: state.fileName ?? '—',
          sheetName: state.analysis.sheet_name,
          summary: {
            total: state.analysis.summary.total_rows,
            valid: state.analysis.summary.valid_rows,
            invalid: state.analysis.summary.invalid_rows,
            blankSkipped: state.analysis.summary.blank_rows_skipped,
            rule: state.analysis.summary.rule,
            pending: state.analysis.summary.pending,
            excluded: state.analysis.summary.excluded,
            invalidRows: state.analysis.summary.invalid,
          },
          aiEnabled: state.analysis.ai.enabled,
          aiProvider: state.analysis.ai.provider,
          aiEvaluated: state.analysis.ai.evaluated_rows,
          aiSuggested: state.analysis.ai.suggested,
          aiAmbiguous: state.analysis.ai.ambiguous,
          aiNoMatch: state.analysis.ai.no_match,
          aiErrors: state.analysis.ai.errors,
          aiSkippedReason: state.analysis.ai.skipped_reason ?? null,
          aiSkippedMessage: state.analysis.ai.skipped_message ?? null,
          warnings: state.analysis.warnings,
          ignoredColumns: state.analysis.ignored_columns,
        }
      : null

    return {
      stage: state.stage,
      fileName: state.fileName,
      fileSize: state.fileSize,
      analysis: state.analysis,
      analyzeView,
      rows,
      counts,
      total: rows.length,
      eligibleCount,
      heldCount: rows.length - eligibleCount,
      calculation: state.calculation,
      calculationRequest: state.calculationRequest,
      unsendable: state.unsendable,
      error: state.error,
      templateStatus: state.templateStatus,
      templateError: state.templateError,
      analyze,
      approveRow,
      rejectRow,
      clearDecision,
      runCalculation,
      saveTemplate,
      reset,
      dismissError,
    }
  }, [
    state,
    analyze,
    approveRow,
    rejectRow,
    clearDecision,
    runCalculation,
    saveTemplate,
    reset,
    dismissError,
  ])

  return (
    <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
  )
}

export function useWorkflow(): WorkflowContextValue {
  const context = useContext(WorkflowContext)
  if (!context) {
    throw new Error('useWorkflow, WorkflowProvider içinde kullanılmalıdır.')
  }
  return context
}

export { aiSuggestionView, decisionCapability }
