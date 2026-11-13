/**
 * Kod → okunabilir etiket çözümü.
 *
 * Etiketler **sunucudan** gelir (`CandidateOut.label`, `GroupOut.product_label`).
 * İstemcide ikinci bir katalog tutulmaz: iki kaynak olsaydı etiketler
 * zamanla ayrışırdı.
 */

import type { AnalyzeRow, CandidateOut, GroupOut } from '../types/api'

/** Satırın adayları arasından kodu bulur. */
export function candidateFor(
  row: AnalyzeRow,
  code: string,
): CandidateOut | undefined {
  return row.match.candidates.find((candidate) => candidate.code === code)
}

/** Satır bağlamında kodun okunabilir adı; bulunamazsa kodun kendisi. */
export function describeCode(row: AnalyzeRow, code: string): string {
  return candidateFor(row, code)?.label ?? code
}

/** Analizdeki tüm adaylardan kod → etiket sözlüğü (sonuç ekranı için). */
export function labelIndex(rows: AnalyzeRow[]): Map<string, string> {
  const index = new Map<string, string>()
  for (const row of rows) {
    for (const candidate of row.match.candidates) {
      if (!index.has(candidate.code)) index.set(candidate.code, candidate.label)
    }
  }
  return index
}

/** Kodun etiketi: önce analiz adayları, yoksa hesaplama grubunun etiketi. */
export function describeGroup(
  group: GroupOut,
  index: Map<string, string>,
): string {
  return index.get(group.code) ?? group.product_label ?? group.code
}
