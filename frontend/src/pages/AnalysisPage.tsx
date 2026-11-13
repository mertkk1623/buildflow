import { Link, useNavigate } from 'react-router-dom'

import { ActionBar, AppShell, PageHeader } from '../components/layout/AppShell'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Alert, Badge, EmptyState } from '../components/ui/Status'
import { TBody, TD, TH, THead, TR, TableShell } from '../components/ui/Table'
import {
  IconAlert,
  IconArrowRight,
  IconCheck,
  IconInfo,
  IconUpload,
} from '../components/ui/icons'
import { WarningList } from '../components/workflow/ApiErrorNotice'
import { cn } from '../lib/ui'
import { useWorkflow } from '../state/WorkflowContext'

/**
 * Analysis — 02.
 *
 * `/api/analyze` yanıtının özeti: satır dağılımı, AI kullanımı, uyarılar ve
 * yok sayılan sütunlar. Hiçbir sayı istemcide hesaplanmaz; hepsi sunucudan
 * geldiği gibi gösterilir.
 */

export default function AnalysisPage() {
  const navigate = useNavigate()
  const { analyzeView, counts, total, eligibleCount, heldCount, stage, reset } =
    useWorkflow()

  if (!analyzeView) {
    return (
      <AppShell current="analysis">
        <PageHeader
          stepNo="02"
          title="Metraj analizi"
          description="Analiz sonucu burada gösterilir."
        />
        <div className="rounded-lg border border-steel-200 bg-white">
          <EmptyState
            title="Henüz analiz edilmiş bir dosya yok"
            description="Bir metraj dosyası yükleyin; satırlar okunur, eşleştirme yapılır ve sonuç burada görünür."
            icon={<IconUpload className="size-6" />}
            action={
              <Link
                to="/upload"
                className="inline-flex h-10 items-center gap-2 rounded-md border border-ink bg-ink px-4 text-body font-medium text-white transition-colors hover:bg-steel-800"
              >
                Metraj yükle
                <IconArrowRight />
              </Link>
            }
          />
        </div>
      </AppShell>
    )
  }

  const { summary, aiEnabled, aiProvider } = analyzeView

  return (
    <AppShell current="analysis">
      <PageHeader
        stepNo="02"
        title="Metraj analizi"
        description="Sunucunun okuma ve eşleştirme sonucu. Deterministik eşleşmeler ile AI önerileri ayrı tutulur."
        badge={<Badge tone="neutral">{analyzeView.sheetName}</Badge>}
        actions={
          <span className="text-sm text-steel-600">
            <span className="tabular font-mono text-steel-900">
              {eligibleCount}
            </span>{' '}
            / {total} hesaba uygun
          </span>
        }
      />

      {/* Dosya kimliği */}
      <div className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-steel-200 bg-white px-3.5 py-2.5 text-sm text-steel-600">
        <span className="font-mono text-xs text-steel-900">
          {analyzeView.fileName}
        </span>
        <span aria-hidden className="text-steel-300">·</span>
        <span>
          Sayfa: <span className="font-mono text-steel-900">{analyzeView.sheetName}</span>
        </span>
        {summary.blankSkipped > 0 && (
          <>
            <span aria-hidden className="text-steel-300">·</span>
            <span>{summary.blankSkipped} boş satır atlandı</span>
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        {/* AI kullanımı */}
        <Card className="min-w-0 overflow-hidden">
          <CardHeader
            title="AI değerlendirmesi"
            description="AI yalnızca onay bekleyen satırlar için öneri üretir; hiçbir öneri otomatik onaylanmaz."
            action={
              <Badge tone={aiEnabled ? 'copper' : 'neutral'}>
                {aiEnabled ? `Açık · ${aiProvider}` : 'Kapalı'}
              </Badge>
            }
          />
          {aiEnabled ? (
            <TableShell minWidth={520}>
              <THead>
                <TR>
                  <TH>Ölçüt</TH>
                  <TH align="right">Satır</TH>
                  <TH>Anlamı</TH>
                </TR>
              </THead>
              <TBody>
                {[
                  {
                    label: 'Değerlendirilen',
                    value: analyzeView.aiEvaluated,
                    note: 'Yalnızca onay bekleyen satırlar AI’ya gönderildi.',
                  },
                  {
                    label: 'Öneri üretildi',
                    value: analyzeView.aiSuggested,
                    note: 'Öneri karar değildir; kullanıcı onayı gerekir.',
                  },
                  {
                    label: 'Belirsiz',
                    value: analyzeView.aiAmbiguous,
                    note: 'Birden fazla aday geçerli; kullanıcı seçer.',
                  },
                  {
                    label: 'Eşleşme yok',
                    value: analyzeView.aiNoMatch,
                    note: 'Katalogda uygun kalem bulunamadı.',
                  },
                  {
                    label: 'Hata',
                    value: analyzeView.aiErrors,
                    note: 'AI hatası analizi durdurmadı; satır onay bekliyor.',
                  },
                ].map((item) => (
                  <TR key={item.label}>
                    <TD>
                      <p className="font-medium text-steel-900">{item.label}</p>
                    </TD>
                    <TD align="right">
                      <span className="tabular font-mono text-steel-900">
                        {item.value}
                      </span>
                    </TD>
                    <TD>
                      <p className="text-xs text-steel-500">{item.note}</p>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </TableShell>
          ) : (
            <CardBody>
              <Alert tone="info" title="AI sağlayıcısı kapalı" icon={<IconInfo />}>
                Deterministik akış çalışmaya devam ediyor. Onay bekleyen satırlar
                kullanıcı kararına düşer; hiçbir satır otomatik onaylanmaz.
              </Alert>
              <p className="mt-3 text-xs text-steel-500">
                AI sağlayıcısını etkinleştirmek için sunucuda{' '}
                <span className="font-mono">BUILDFLOW_AI_PROVIDER</span> ayarlanır.
                Kapalıyken hiçbir ağ çağrısı yapılmaz.
              </p>
            </CardBody>
          )}
        </Card>

        {/* Satır dağılımı */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Satır dağılımı"
              description={`${summary.total} satır · sunucu yanıtı`}
            />
            <CardBody className="space-y-2.5">
              {[
                {
                  label: 'Kural ile eşleşti',
                  value: counts.rule,
                  tone: 'success' as const,
                  icon: <IconCheck className="size-3.5" />,
                },
                {
                  label: 'Kullanıcı onayladı',
                  value: counts['ai-approved'],
                  tone: 'copper' as const,
                },
                {
                  label: 'Onay bekliyor',
                  value: counts.pending,
                  tone: 'warning' as const,
                },
                {
                  label: 'Reddedildi',
                  value: counts.rejected,
                  tone: 'danger' as const,
                },
                {
                  label: 'Hariç tutuldu',
                  value: counts.excluded,
                  tone: 'neutral' as const,
                },
                {
                  label: 'Geçersiz',
                  value: counts.invalid,
                  tone: 'danger' as const,
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between gap-3"
                >
                  <Badge tone={item.tone} className="min-w-0">
                    {item.icon}
                    {item.label}
                  </Badge>
                  <span className="tabular font-mono text-body text-steel-900">
                    {item.value}
                  </span>
                </div>
              ))}

              <div className="mt-1 space-y-1 border-t border-steel-200 pt-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-steel-600">Hesaba uygun</span>
                  <span className="tabular font-mono font-medium text-steel-900">
                    {eligibleCount}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-steel-600">Hesap dışı</span>
                  <span className="tabular font-mono font-medium text-steel-900">
                    {heldCount}
                  </span>
                </div>
              </div>
            </CardBody>
          </Card>

          {heldCount > 0 && (
            <Alert tone="warning" title="Hesap dışı satırlar var" icon={<IconAlert />}>
              {heldCount} satır hesaba katılmayacak. Bu satırlar raporda{' '}
              <span className="font-semibold">Hesaba Alınmayanlar</span>{' '}
              bölümünde nedenleriyle listelenir; ağırlık toplamını etkilemez.
              Onay bekleyen satırları eşleştirme ekranında karara bağlayabilirsiniz.
            </Alert>
          )}

          {summary.invalidRows > 0 && (
            <Alert tone="danger" title={`${summary.invalidRows} geçersiz satır`} icon={<IconAlert />}>
              Bu satırlar veri olarak okunamadı ve hesaba gönderilemez. Ayrıntı
              eşleştirme ekranındaki satır kartında görünür.
            </Alert>
          )}
        </div>
      </div>

      {analyzeView.warnings.length > 0 && (
        <div className="mt-5">
          <WarningList warnings={analyzeView.warnings} title="Analiz uyarıları" />
        </div>
      )}

      {analyzeView.ignoredColumns.length > 0 && (
        <Alert tone="info" title="Yok sayılan sütunlar" icon={<IconInfo />} className="mt-5">
          <p className="font-mono text-xs">{analyzeView.ignoredColumns.join(', ')}</p>
        </Alert>
      )}

      <div
        className={cn(
          'mt-5 rounded-lg border border-steel-200 bg-white px-4 py-3',
        )}
      >
        <p className="text-sm text-steel-600">
          <span className="font-semibold text-steel-800">
            Eşleştirme sunucuda yapıldı.
          </span>{' '}
          Bu ekran hiçbir değeri yeniden hesaplamaz; yalnızca `/api/analyze`
          yanıtını gösterir. Nihai satın alma miktarları{' '}
          <span className="font-mono text-xs">/api/calculate</span> ile üretilir.
        </p>
      </div>

      <ActionBar
        hint={
          stage === 'reviewing'
            ? 'Kararlar bekleniyor · onaysız satır hesaba girmez'
            : 'Analiz tamamlandı'
        }
      >
        <Link
          to="/upload"
          className="inline-flex h-10 items-center gap-2 rounded-md border border-steel-300 bg-white px-4 text-body font-medium text-steel-800 transition-colors hover:bg-steel-50"
        >
          Geri
        </Link>
        <Button
          variant="secondary"
          onClick={reset}
          className="hidden sm:inline-flex"
        >
          Yeni dosya
        </Button>
        <Button
          variant="primary"
          trailingIcon={<IconArrowRight />}
          onClick={() => navigate('/review')}
        >
          Eşleştirmeye geç
        </Button>
      </ActionBar>
    </AppShell>
  )
}
