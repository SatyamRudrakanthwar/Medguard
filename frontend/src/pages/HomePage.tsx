import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import ApiKeyBanner from '../components/ApiKeyBanner'

interface FormState {
  age: string
  conditions: string
  medicationInput: string
  medications: string[]
  question: string
}

export default function HomePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>({
    age: '',
    conditions: '',
    medicationInput: '',
    medications: [],
    question: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function addMedication() {
    const name = form.medicationInput.trim()
    if (!name || form.medications.includes(name)) return
    setForm(f => ({ ...f, medications: [...f.medications, name], medicationInput: '' }))
  }

  function removeMedication(name: string) {
    setForm(f => ({ ...f, medications: f.medications.filter(m => m !== name) }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (form.medications.length === 0) {
      setError('Add at least one medication.')
      return
    }

    setSubmitting(true)
    try {
      const conditions = form.conditions
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)

      const response = await api.createReview({
        age: Number(form.age),
        conditions,
        medications: form.medications,
        question: form.question.trim(),
      })
      navigate(`/review/${response.review_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <ApiKeyBanner />

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Medication Safety Review</h1>
        <p className="mt-1 text-slate-500 text-sm">
          Enter patient details and medications to run an AI-powered safety analysis.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Patient Info */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
            Patient Information
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Age <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                max={120}
                required
                value={form.age}
                onChange={e => setForm(f => ({ ...f, age: e.target.value }))}
                placeholder="e.g. 65"
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Conditions
                <span className="ml-1 text-xs text-slate-400">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={form.conditions}
                onChange={e => setForm(f => ({ ...f, conditions: e.target.value }))}
                placeholder="e.g. type 2 diabetes, hypertension"
                className="input-field"
              />
            </div>
          </div>
        </div>

        {/* Medications */}
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
            Medications <span className="text-red-500">*</span>
          </h2>

          <div className="flex gap-2">
            <input
              type="text"
              value={form.medicationInput}
              onChange={e => setForm(f => ({ ...f, medicationInput: e.target.value }))}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMedication() } }}
              placeholder="Type medication name and press Enter or Add"
              className="input-field flex-1"
            />
            <button
              type="button"
              onClick={addMedication}
              className="btn-secondary flex-shrink-0"
            >
              Add
            </button>
          </div>

          {form.medications.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {form.medications.map(m => (
                <span
                  key={m}
                  className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2.5 py-1 text-sm text-blue-800"
                >
                  {m}
                  <button
                    type="button"
                    onClick={() => removeMedication(m)}
                    className="ml-0.5 text-blue-400 hover:text-blue-700 leading-none"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No medications added yet.</p>
          )}
        </div>

        {/* Question */}
        <div className="card space-y-2">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
            Safety Question <span className="text-red-500">*</span>
          </h2>
          <p className="text-xs text-slate-400">
            Ask about interactions, risks, or side effects — not about starting/stopping medications.
          </p>
          <textarea
            required
            rows={3}
            minLength={5}
            maxLength={1000}
            value={form.question}
            onChange={e => setForm(f => ({ ...f, question: e.target.value }))}
            placeholder="e.g. Are there any known interactions between these medications that could increase bleeding risk?"
            className="input-field resize-none"
          />
          <p className="text-right text-xs text-slate-400">{form.question.length}/1000</p>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="btn-primary w-full py-3 text-base"
        >
          {submitting ? (
            <>
              <span className="h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
              Submitting…
            </>
          ) : (
            'Run Safety Review'
          )}
        </button>
      </form>
    </div>
  )
}
