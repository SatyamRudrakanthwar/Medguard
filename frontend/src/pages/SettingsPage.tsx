import { useState, useEffect } from 'react'

const PROVIDERS = [
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    hint: 'sk-ant-api03-...',
    keyRequired: true,
    description: 'Claude Sonnet — best reasoning, structured output',
    docsUrl: 'https://console.anthropic.com/',
  },
  {
    id: 'openai',
    name: 'OpenAI (GPT-4o)',
    hint: 'sk-...',
    keyRequired: true,
    description: 'GPT-4o or GPT-4o-mini — widely available',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    hint: 'AIzaSy...',
    keyRequired: true,
    description: 'Gemini 1.5 Flash — fast, generous free tier',
    docsUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'huggingface',
    name: 'HuggingFace',
    hint: 'hf_...',
    keyRequired: true,
    description: 'Llama 3, Mixtral and more via Inference API',
    docsUrl: 'https://huggingface.co/settings/tokens',
  },
  {
    id: 'ollama',
    name: 'Ollama (Local)',
    hint: '',
    keyRequired: false,
    description: 'Run models on your own machine — no API key needed',
    docsUrl: 'https://ollama.ai/',
  },
]

export default function SettingsPage() {
  const [provider, setProvider] = useState(() => {
    try { return localStorage.getItem('medguard_provider') ?? 'anthropic' } catch { return 'anthropic' }
  })
  const [keyInput, setKeyInput] = useState('')
  const [saved, setSaved] = useState(false)
  const [hasKey, setHasKey] = useState(false)

  const selectedProvider = PROVIDERS.find(p => p.id === provider) ?? PROVIDERS[0]

  useEffect(() => {
    try {
      setHasKey(Boolean(localStorage.getItem('medguard_api_key')))
    } catch { /* ignore */ }
  }, [provider])

  function saveSettings() {
    try {
      localStorage.setItem('medguard_provider', provider)
      if (keyInput.trim()) {
        localStorage.setItem('medguard_api_key', keyInput.trim())
        setHasKey(true)
        setKeyInput('')
      } else if (provider === 'ollama') {
        localStorage.removeItem('medguard_api_key')
        setHasKey(false)
      }
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch { /* ignore */ }
  }

  function clearKey() {
    try {
      localStorage.removeItem('medguard_api_key')
      setHasKey(false)
      setKeyInput('')
    } catch { /* ignore */ }
  }

  function handleProviderChange(id: string) {
    setProvider(id)
    setKeyInput('')
    try { localStorage.setItem('medguard_provider', id) } catch { /* ignore */ }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-slate-900">Settings</h1>

      {/* Provider selection */}
      <div className="card space-y-4">
        <div>
          <h2 className="font-semibold text-slate-900">AI Provider</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Choose which LLM to use for safety analysis.
          </p>
        </div>

        <div className="space-y-2">
          {PROVIDERS.map(p => (
            <button
              key={p.id}
              onClick={() => handleProviderChange(p.id)}
              className={`w-full text-left rounded-lg border px-4 py-3 transition-all ${
                provider === p.id
                  ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`font-medium text-sm ${provider === p.id ? 'text-blue-900' : 'text-slate-800'}`}>
                  {p.name}
                </span>
                <div className="flex items-center gap-2">
                  {!p.keyRequired && (
                    <span className="text-xs bg-green-100 text-green-700 border border-green-200 rounded-full px-2 py-0.5">
                      Free / No key
                    </span>
                  )}
                  {provider === p.id && (
                    <span className="text-blue-600 text-sm">✓</span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{p.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* API Key */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">
            {selectedProvider.keyRequired ? 'API Key' : 'No Key Required'}
          </h2>
          {selectedProvider.docsUrl && (
            <a
              href={selectedProvider.docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline"
            >
              Get key →
            </a>
          )}
        </div>

        {selectedProvider.id === 'ollama' ? (
          <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800">
            <p className="font-medium mb-1">Ollama runs locally — no key needed</p>
            <p className="text-xs text-green-700">
              Make sure Ollama is running at <code className="bg-green-100 px-1 rounded">http://localhost:11434</code> with a model installed.
              <br />Install: <code className="bg-green-100 px-1 rounded">ollama pull llama3.1</code>
            </p>
          </div>
        ) : hasKey ? (
          <div className="flex items-center justify-between rounded-lg bg-green-50 border border-green-200 px-3 py-2.5">
            <div className="flex items-center gap-2 text-sm text-green-800">
              <span>✓</span>
              <span className="font-medium">API key saved for {selectedProvider.name}</span>
            </div>
            <button onClick={clearKey} className="btn-secondary text-xs text-red-600 border-red-200 hover:bg-red-50">
              Remove
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <input
              type="password"
              value={keyInput}
              onChange={e => setKeyInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') saveSettings() }}
              placeholder={selectedProvider.hint || 'Enter API key…'}
              className="input-field font-mono"
              autoComplete="off"
            />
            <button
              onClick={saveSettings}
              disabled={!keyInput.trim()}
              className="btn-primary w-full"
            >
              Save Key
            </button>
          </div>
        )}

        {saved && (
          <p className="text-sm text-green-700 font-medium">✓ Settings saved.</p>
        )}

        <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-3 space-y-1 text-xs text-slate-500">
          <p className="font-medium text-slate-700">Privacy</p>
          <ul className="space-y-1">
            <li>• Key is stored only in your browser's <code className="bg-slate-200 px-1 rounded">localStorage</code></li>
            <li>• Sent as <code className="bg-slate-200 px-1 rounded">X-API-Key</code> header — never stored server-side</li>
            <li>• Without a key, MedGuard uses built-in stub agents (demo mode)</li>
          </ul>
        </div>
      </div>

      {/* Backend services */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-slate-900">Backend Services</h2>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {[
            { label: 'FastAPI', value: 'localhost:8000' },
            { label: 'PostgreSQL', value: 'localhost:5432' },
            { label: 'Qdrant', value: 'localhost:6333' },
            { label: 'Redis', value: 'localhost:6379' },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
              <span className="text-slate-600">{label}</span>
              <code className="text-xs text-slate-400">{value}</code>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-400">
          Start all with <code className="bg-slate-100 px-1 rounded">docker compose up -d</code>
        </p>
      </div>
    </div>
  )
}
