import { Fragment } from 'react'

import { formatDecimal, formatQuantity, formatWaste } from '../../lib/format'
import type { GroupOut } from '../../types/api'
import { Badge } from '../ui/Status'
import { TBody, TD, TH, THead, TR, TableShell } from '../ui/Table'
import { IconChevronDown, IconChevronRight } from '../ui/icons'

/**
 * Satın alma listesi — `/api/calculate` yanıtındaki `GroupOut` verisiyle.
 *
 * KURAL: bu tablo **hiçbir değer hesaplamaz**. Net m, brüt m, sipariş boyu,
 * ağırlık ve artan değerlerin tamamı sunucudan gelir; `null` ise "—"
 * gösterilir ve `0` yazılmaz. `PARTIAL` grup, eksik alanlarıyla birlikte
 * işaretlenir.
 */
export function PurchaseListTable({
  groups,
  expanded,
  onToggle,
}: {
  groups: GroupOut[]
  expanded: Set<string>
  onToggle: (code: string) => void
}) {
  return (
    <TableShell minWidth={1000}>
      <THead>
        <TR>
          <TH className="w-8">
            <span className="sr-only">Kaynak satırlar</span>
          </TH>
          <TH>Malzeme</TH>
          <TH>Durum</TH>
          <TH>Kaynak BOQ</TH>
          <TH align="right">Brüt m</TH>
          <TH align="right">Sipariş boyu</TH>
          <TH align="right">Adet</TH>
          <TH align="right">Ağırlık</TH>
        </TR>
      </THead>
      <TBody>
        {groups.map((group) => {
          const isOpen = expanded.has(group.code)

          return (
            <Fragment key={group.code}>
              <TR interactive onClick={() => onToggle(group.code)} className="bg-white">
                <TD className="text-steel-500">
                  {isOpen ? <IconChevronDown /> : <IconChevronRight />}
                </TD>
                <TD>
                  <p className="font-mono text-xs text-steel-500">{group.code}</p>
                  <p className="font-medium text-steel-900">{group.product_label}</p>
                  {group.merged && (
                    <p className="mt-0.5 text-[10px] font-medium tracking-wide text-copper-700 uppercase">
                      {group.sources.length} satır birleşti
                    </p>
                  )}
                </TD>
                <TD>
                  <Badge tone={group.status === 'FULL' ? 'success' : 'warning'}>
                    {group.status === 'FULL' ? 'TAM' : 'KISMİ'}
                  </Badge>
                  {group.status === 'PARTIAL' && group.missing_fields.length > 0 && (
                    <p className="mt-1 font-mono text-[10px] text-warning-fg">
                      eksik: {group.missing_fields.join(', ')}
                    </p>
                  )}
                </TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    {group.source_boq_nos.map((no) => (
                      <span
                        key={no}
                        className="rounded-xs bg-steel-100 px-1.5 py-0.5 font-mono text-xs text-steel-700"
                      >
                        {no}
                      </span>
                    ))}
                  </div>
                </TD>
                <TD align="right" className="whitespace-nowrap">
                  <span className="tabular font-mono text-xs text-steel-800">
                    {formatDecimal(group.total_gross_metres, { precise: true })}
                  </span>
                </TD>
                <TD align="right" className="whitespace-nowrap">
                  <span className="tabular font-mono text-xs text-steel-800">
                    {formatDecimal(group.order_length_m, {
                      precise: true,
                      suffix: 'm',
                    })}
                  </span>
                </TD>
                <TD align="right" className="whitespace-nowrap">
                  <span className="tabular font-mono text-xs text-steel-800">
                    {formatDecimal(group.bar_count)}
                  </span>
                </TD>
                <TD align="right" className="whitespace-nowrap">
                  <span className="tabular font-mono text-xs text-steel-800">
                    {formatDecimal(group.weight_kg, {
                      precise: true,
                      suffix: 'kg',
                    })}
                  </span>
                </TD>
              </TR>

              {isOpen && (
                <tr className="bg-steel-25">
                  <td />
                  <td colSpan={7} className="px-3 pt-1 pb-4">
                    <div className="space-y-3">
                      {/* Kaynak satırlar */}
                      <div className="rounded-md border border-steel-200 bg-white">
                        <p className="border-b border-steel-100 px-3 py-2 text-label tracking-[0.08em] text-steel-500 uppercase">
                          Bu gruba giren metraj satırları
                        </p>
                        <ul className="divide-y divide-steel-100">
                          {group.sources.map((source) => (
                            <li
                              key={`${source.boq_no}-${source.source_row ?? 'yok'}`}
                              className="px-3 py-2"
                            >
                              <div className="flex flex-wrap items-baseline justify-between gap-2">
                                <span className="font-mono text-xs text-steel-500">
                                  {source.boq_no}
                                  {source.source_row !== null && (
                                    <span className="ml-1 text-steel-400">
                                      s{source.source_row}
                                    </span>
                                  )}
                                </span>
                                <span className="min-w-0 flex-1 text-sm text-steel-700">
                                  {source.description}
                                </span>
                                <span className="tabular font-mono text-xs text-steel-800">
                                  {formatQuantity(
                                    source.source_quantity,
                                    source.source_unit,
                                  )}
                                </span>
                                <Badge
                                  tone={
                                    source.waste_source === 'none'
                                      ? 'neutral'
                                      : 'success'
                                  }
                                >
                                  fire: {formatWaste(source.waste_percent)}
                                </Badge>
                              </div>

                              {/* Dönüşüm izi — sunucudan geldiği gibi */}
                              {source.conversion_steps.length > 0 && (
                                <ul className="mt-1 space-y-0.5">
                                  {source.conversion_steps.map((step) => (
                                    <li
                                      key={step}
                                      className="font-mono text-[11px] text-steel-500"
                                    >
                                      {step}
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Grup ölçütleri */}
                      <div className="rounded-md border border-steel-200 bg-white px-3 py-2.5">
                        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
                          {[
                            ['m / m', formatDecimal(group.mass_kg_per_m, { precise: true })],
                            ['Ticari boy', formatDecimal(group.commercial_length_m, { precise: true, suffix: 'm' })],
                            ['Artan boy', formatDecimal(group.rounding_surplus_m, { precise: true, suffix: 'm' })],
                            ['Toplam brüt', formatDecimal(group.total_gross_metres, { precise: true, suffix: 'm' })],
                          ].map(([label, value]) => (
                            <div key={label}>
                              <dt className="text-xs text-steel-500">{label}</dt>
                              <dd className="tabular font-mono text-steel-900">
                                {value}
                              </dd>
                            </div>
                          ))}
                        </dl>
                        <p className="mt-2 border-t border-steel-100 pt-2 text-xs text-steel-600">
                          {group.weight_label}: {group.weight_note}
                        </p>
                      </div>

                      {/* PARTIAL eksikleri */}
                      {group.missing.length > 0 && (
                        <ul className="space-y-1 rounded-md border border-warning-br bg-warning-bg px-3 py-2.5">
                          {group.missing.map((item, index) => (
                            <li
                              key={`${item.field}-${item.boq_no ?? index}`}
                              className="text-xs text-steel-700"
                            >
                              <span className="font-mono text-warning-fg">
                                {item.field}
                              </span>
                              {item.boq_no && (
                                <span className="ml-1 font-mono text-steel-500">
                                  ({item.boq_no})
                                </span>
                              )}
                              : {item.message}
                            </li>
                          ))}
                        </ul>
                      )}

                      {/* Grup notları */}
                      {group.notes.length > 0 && (
                        <ul className="space-y-1 rounded-md border border-dashed border-steel-300 px-3 py-2.5">
                          {group.notes.map((note, index) => (
                            <li key={`${note}-${index}`} className="text-xs text-steel-600">
                              {note}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </TBody>
    </TableShell>
  )
}
