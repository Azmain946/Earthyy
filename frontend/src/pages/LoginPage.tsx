import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('analyst@earthyy.io')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full flex items-center justify-center bg-surface-container-low">
      <div className="w-full max-w-sm bg-surface-container-lowest border border-outline-variant rounded-xl shadow-xl p-6">
        <div className="flex items-center gap-3 mb-5">
          <img src="/earthyy.svg" alt="Earthyy" className="w-10 h-10 rounded-lg" />
          <div>
            <h1 className="font-semibold text-on-surface leading-tight">Earthyy</h1>
            <p className="text-label-coord font-mono text-outline uppercase tracking-wider">Observation Intelligence</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label htmlFor="email" className="block text-telemetry font-mono text-on-surface mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-9 px-3 bg-surface-container-low border border-outline-variant rounded text-sm focus:outline-none focus:border-primary focus:ring-0"
              required
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-telemetry font-mono text-on-surface mb-1">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-9 px-3 bg-surface-container-low border border-outline-variant rounded text-sm focus:outline-none focus:border-primary focus:ring-0"
              required
            />
          </div>
          {error && (
            <div className="p-2 bg-error-container/50 border border-error/40 rounded text-xs text-on-error-container" role="alert">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-container transition-colors disabled:opacity-50"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-4 text-label-coord font-mono text-outline text-center">
          Default dev account: analyst@earthyy.io / earthyy-analyst
        </p>
      </div>
    </div>
  )
}
