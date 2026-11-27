import {useEffect,useState} from 'react'
import App from './App'
import Landing from './Landing'
export default function Router(){const [studio,setStudio]=useState(location.hash==='#studio');useEffect(()=>{const change=()=>setStudio(location.hash==='#studio');window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change)},[]);return studio?<App/>:<Landing/>}
