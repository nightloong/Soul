import { useEffect, useState } from 'react'
import { request } from './api'

export function useData<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!path) return
    let active = true
    request<T>(path).then(value => { if (active) setData(value) }).catch(reason => { if (active) setError(String(reason)) })
    return () => { active = false }
  }, [path])
  return { data, error, refresh: () => { if (path) request<T>(path).then(setData).catch(reason => setError(String(reason))) } }
}
