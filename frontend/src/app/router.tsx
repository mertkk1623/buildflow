import { Link, Route, Routes } from 'react-router-dom'

import { AppShell, PageHeader } from '../components/layout/AppShell'
import { EmptyState } from '../components/ui/Status'
import AnalysisPage from '../pages/AnalysisPage'
import ExportPage from '../pages/ExportPage'
import LandingPage from '../pages/LandingPage'
import ResultsPage from '../pages/ResultsPage'
import ReviewPage from '../pages/ReviewPage'
import UploadPage from '../pages/UploadPage'

/** Rotalar — her adım kendi URL'ine sahiptir; yenilenebilir ve paylaşılabilir. */
export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/analysis" element={<AnalysisPage />} />
      <Route path="/review" element={<ReviewPage />} />
      <Route path="/results" element={<ResultsPage />} />
      <Route path="/export" element={<ExportPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

function NotFoundPage() {
  return (
    <AppShell current="upload">
      <PageHeader stepNo="—" title="Sayfa bulunamadı" />
      <div className="rounded-lg border border-steel-200 bg-white">
        <EmptyState
          title="Bu adres tanımlı değil"
          description="Aradığınız sayfa bu prototipte bulunmuyor."
          action={
            <Link
              to="/"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-ink bg-ink px-4 text-body font-medium text-white transition-colors hover:bg-steel-800"
            >
              Ana sayfaya dön
            </Link>
          }
        />
      </div>
    </AppShell>
  )
}
