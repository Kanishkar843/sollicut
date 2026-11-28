import { useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

const THEME_KEY = 'sollicut-theme'
const THEME_EVENT = 'sollicut-theme-change'

/** Read persisted theme safely, defaulting to dark. */
export function getStoredTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

/** Apply theme to the root element, persist it, and notify active hooks. */
export function applyTheme(theme: Theme): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme
  }
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // Ignore storage write errors in restricted browser contexts.
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent<Theme>(THEME_EVENT, { detail: theme }))
  }
}

/** Initialize the root theme before first render. */
export function initTheme(): Theme {
  const initial = getStoredTheme()
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = initial
  }
  return initial
}

/** Synchronized theme state hook shared between Landing and Studio. */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => {
    const initial = getStoredTheme()
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = initial
    }
    return initial
  })

  useEffect(() => {
    const onThemeEvent = (e: Event) => {
      const next = (e as CustomEvent<Theme>).detail
      if (next === 'dark' || next === 'light') {
        setThemeState(next)
      }
    }
    const onStorage = (e: StorageEvent) => {
      if (e.key === THEME_KEY) {
        const next: Theme = e.newValue === 'light' ? 'light' : 'dark'
        if (typeof document !== 'undefined') {
          document.documentElement.dataset.theme = next
        }
        setThemeState(next)
      }
    }
    window.addEventListener(THEME_EVENT, onThemeEvent)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(THEME_EVENT, onThemeEvent)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  function setTheme(next: Theme) {
    applyTheme(next)
    setThemeState(next)
  }

  function toggleTheme() {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return { theme, setTheme, toggleTheme }
}
