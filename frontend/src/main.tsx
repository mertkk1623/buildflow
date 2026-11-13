import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.tsx'
import './index.css'
import { WorkflowProvider } from './state/WorkflowContext'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Kök eleman (#root) bulunamadı.')
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <WorkflowProvider>
        <App />
      </WorkflowProvider>
    </BrowserRouter>
  </StrictMode>,
)
