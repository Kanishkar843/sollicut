import {useState} from 'react'
import VoiceButton from './VoiceButton'
import {api,type Project} from './api'
export default function GeneratePanel({project,onProject}:{project:Project;onProject:(p:Project)=>void}){
 const [prompt,setPrompt]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
 async function record(blob:Blob,ext:string){setBusy(true);setError('');try{const data=new FormData();data.append('file',blob,`idea.${ext}`);data.append('mode','generate');const result=await api<{generation_prompt:string}>(`/projects/${project.id}/voice-command`,{method:'POST',body:data});setPrompt(result.generation_prompt)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function generate(){setBusy(true);setError('');try{onProject(await api<Project>(`/projects/${project.id}/generate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transcript:prompt})}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="generation-panel"><span className="eyebrow">OPTIONAL CLOUD CREATION</span><h2>Speak a new advertisement</h2><p>Describe your product, scene and message. Review the transcript before sending it to Google. Generation needs a server API key, model access and billing.</p><VoiceButton disabled={busy} onAudio={(b,e)=>void record(b,e)} onError={setError}/>{prompt&&<><blockquote>{prompt}</blockquote><button className="lime-button" disabled={busy} onClick={()=>void generate()}>Generate with Gemini</button></>}{busy&&<p role="status">Processing your request…</p>}{error&&<p role="alert" className="error">{error}</p>}</section>
}
