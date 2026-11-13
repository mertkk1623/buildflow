import { Alert, Badge } from '../ui/Status'
import { IconAlert, IconInfo } from '../ui/icons'
import type { WorkflowError } from '../../state/WorkflowContext'

/**
 * API hatasının kullanıcıya gösterimi.
 *
 * Kural: yalnızca sunucunun **güvenli** zarf alanları gösterilir
 * (`message`, `detail`, `suggestion`, `issues`). Stack trace, dosya yolu,
 * sağlayıcı anahtarı veya iç tip adı hiçbir koşulda ekrana basılmaz.
 */
export function ApiErrorNotice({
  error,
  className,
}: {
  error: WorkflowError
  className?: string
}) {
  return (
    <Alert
      tone="danger"
      title={error.title}
      icon={<IconAlert />}
      className={className}
    >
      <div className="space-y-2">
        {error.detail && error.detail !== error.message && (
          <p className="text-sm">{error.detail}</p>
        )}

        {error.issues.length > 0 && (
          <ul className="divide-y divide-danger-br/60 overflow-hidden rounded-md border border-danger-br bg-white">
            {error.issues.slice(0, 12).map((issue, index) => (
              <li
                key={`${issue.code ?? 'issue'}-${issue.boq_no ?? index}-${index}`}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2"
              >
                <span className="w-20 shrink-0 font-mono text-xs whitespace-nowrap text-steel-500">
                  {issue.source_row !== null
                    ? `Satır ${issue.source_row}`
                    : (issue.boq_no ?? '—')}
                </span>
                <span className="min-w-0 flex-1 text-sm text-steel-800">
                  {issue.message}
                </span>
                {issue.suggestion && (
                  <span className="w-full pl-0 text-xs text-steel-500 sm:w-auto sm:pl-0">
                    {issue.suggestion}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        {error.issues.length > 12 && (
          <p className="text-xs text-steel-600">
            +{error.issues.length - 12} satır daha bildirildi.
          </p>
        )}

        {error.suggestion && (
          <p className="flex items-start gap-2 text-sm">
            <IconInfo className="mt-0.5 shrink-0" />
            <span>{error.suggestion}</span>
          </p>
        )}

        <p className="text-xs opacity-75">
          Sunucu iç ayrıntıları kullanıcıya gösterilmez.
          {error.stage === 'analyze' && ' Dosyayı düzelttikten sonra yeniden yükleyin.'}
        </p>
      </div>
    </Alert>
  )
}

/** Uyarı listesi — analiz/hesaplama uyarılarını kaybetmeden gösterir. */
export function WarningList({
  warnings,
  title = 'Uyarılar',
}: {
  warnings: string[]
  title?: string
}) {
  if (warnings.length === 0) return null

  return (
    <div className="rounded-lg border border-warning-br bg-warning-bg px-4 py-3">
      <div className="flex items-center gap-2">
        <IconAlert className="text-warning-fg" />
        <p className="text-body font-semibold text-warning-fg">
          {title}{' '}
          <Badge tone="warning" className="ml-1">
            {warnings.length}
          </Badge>
        </p>
      </div>
      <ul className="mt-2 space-y-1.5">
        {warnings.map((warning) => (
          <li
            key={warning}
            className="flex items-start gap-2 text-sm text-steel-700"
          >
            <span
              aria-hidden
              className="mt-1.5 size-1 shrink-0 rounded-full bg-warning-fg"
            />
            {warning}
          </li>
        ))}
      </ul>
    </div>
  )
}
