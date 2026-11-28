import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './Router'
import { initTheme } from './theme'
import './style.css'
initTheme()
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
