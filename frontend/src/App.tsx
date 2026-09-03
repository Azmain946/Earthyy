import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import SideNav from './components/layout/SideNav'
import ZoneModal from './components/ZoneModal'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import ModulePage from './pages/ModulePage'
import { useAuth } from './hooks/useAuth'

export default function App() {
  const { user, loading } = useAuth()
  const [globalZoneModal, setGlobalZoneModal] = useState(false)

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-surface-container-low">
        <div className="flex items-center gap-3 text-on-surface-variant">
          <span className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" aria-hidden />
          <span className="text-sm font-mono">Initializing Earthyy…</span>
        </div>
      </div>
    )
  }

  if (!user) return <LoginPage />

  return (
    <div className="h-full">
      <SideNav onCreateZone={() => setGlobalZoneModal(true)} />
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/river" element={<ModulePage key="river" module="river" />} />
        <Route path="/agriculture" element={<ModulePage key="agriculture" module="agriculture" />} />
        <Route path="/forest" element={<ModulePage key="forest" module="forest" />} />
        <Route path="/brick-kilns" element={<ModulePage key="brick_kiln" module="brick_kiln" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ZoneModal open={globalZoneModal} onClose={() => setGlobalZoneModal(false)} geometry={null} />
    </div>
  )
}
