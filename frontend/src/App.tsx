import {useEffect,useRef,useState} from 'react'
import {AudioLines,Check,ChevronDown,Download,Film,ImagePlus,LoaderCircle,Music2,ShieldCheck,Sparkles,Trash2,Undo2,X} from 'lucide-react'
import {api,operationLabel,type Capabilities,type Command,type Parsed,type Project} from './api'
import VoiceButton from './VoiceButton'

export function validatePhotos(files:File[],count:number):string|null{
 if(files.length+count>5)return 'Choose up to 5 product photos in total.'
 if(files.some(f=>!['image/jpeg','image/png','image/webp'].includes(f.type)))return 'Use JPEG, PNG or WebP product photos.'
 if(files.some(f=>f.size>15*1024*1024))return 'Each photo must be smaller than 15 MB.'
 return null
}

export default function App(){
 const [project,setProject]=useState<Project|null>(null),[caps,setCaps]=useState<Capabilities|null>(null)
 const [busy,setBusy]=useState(false),[stage,setStage]=useState('Ready'),[error,setError]=useState('')
 const [parsed,setParsed]=useState<Parsed|null>(null),[language,setLanguage]=useState(''),[resetting,setResetting]=useState(false)
 const [jobId,setJobId]=useState<string|null>(null)
 const initial=useRef<Promise<Project>|null>(null),upload=useRef<HTMLInputElement>(null),music=useRef<HTMLInputElement>(null)
 const photos=project?.assets.filter(a=>a.media_type==='image')??[]
 useEffect(()=>{
  let live=true
  const saved=localStorage.getItem('sollicut-project')
  if(!initial.current)initial.current=saved?api<Project>(`/projects/${saved}`).catch(()=>api<Project>('/projects',{method:'POST'})):api<Project>('/projects',{method:'POST'})
  initial.current.then(p=>{if(live){setProject(p);localStorage.setItem('sollicut-project',p.id)}}).catch(e=>live&&setError(e.message))
  const refresh=()=>api<Capabilities>('/capabilities').then(c=>live&&setCaps(c)).catch(e=>live&&setError(e.message))
  void refresh();const timer=setInterval(refresh,5000)
  return()=>{live=false;clearInterval(timer)}
 },[])
 useEffect(()=>{
  if(!jobId||!project)return
  let live=true
  const poll=async()=>{try{
   const job=await api<{status:string;stage:string;error?:string}>(`/jobs/${jobId}`)
   if(!live)return
   setStage(job.stage)
   if(job.status==='done'){const p=await api<Project>(`/projects/${project.id}`);if(live){setProject(p);setBusy(false);setJobId(null)}}
   if(job.status==='failed'){setError(job.error||'Rendering failed');setBusy(false);setJobId(null)}
  }catch(e){if(live){setError((e as Error).message);setBusy(false);setJobId(null)}}}
  void poll();const timer=setInterval(poll,1000)
  return()=>{live=false;clearInterval(timer)}
 },[jobId,project?.id])
 async function filesSelected(files:File[],audio=false){
  if(!project||busy)return
  const validation=audio?null:validatePhotos(files,photos.length)
  if(validation){setError(validation);return}
  setError('');setBusy(true);setStage('Uploading your media')
  try{for(const file of files){const form=new FormData();form.append('file',file);setProject(await api<Project>(`/projects/${project.id}/assets`,{method:'POST',body:form}))}setStage('Ready')}catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function handleAudio(blob:Blob,extension:string){
  if(!project)return
  setBusy(true);setError('');setStage('Processing speech');setParsed(null)
  try{
   const form=new FormData();form.append('file',blob,`command.${extension}`);if(language)form.append('language_hint',language)
   const result=await api<Command>(`/projects/${project.id}/voice-command`,{method:'POST',body:form})
   setParsed(result.parsed_command)
   if(result.parsed_command.requires_clarification){setStage('A little more detail');setBusy(false)}
   else if(result.job_id){setStage('Rendering reel');setJobId(result.job_id)}
   else{if(result.project)setProject(result.project);if(result.download_url){const a=document.createElement('a');a.href=result.download_url;a.download='SolliCut-reel.mp4';a.click()}setStage(result.download_url?'Ready to download':'Previous edit restored');setBusy(false)}
  }catch(e){setError((e as Error).message);setBusy(false);setStage('Ready')}
 }
 async function undo(){if(!project)return;setBusy(true);setError('');try{setProject(await api<Project>(`/projects/${project.id}/undo`,{method:'POST'}));setParsed(null);setStage('Previous edit restored')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function reset(){if(!project)return;setBusy(true);try{await api(`/projects/${project.id}`,{method:'DELETE'});const p=await api<Project>('/projects',{method:'POST'});setProject(p);localStorage.setItem('sollicut-project',p.id);setParsed(null);setError('');setStage('Ready');setResetting(false)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function remove(id:string){if(!project)return;setBusy(true);try{setProject(await api<Project>(`/projects/${project.id}/assets/${id}`,{method:'DELETE'}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <div className="app-shell">
  <header><a className="brand" href="/"><span className="brand-icon"><AudioLines size={24}/></span>SolliCut<span className="beta">BETA</span></a><div className="header-right"><span>Made for your next big little thing.</span><button className="quiet" disabled={!project||busy} onClick={()=>setResetting(true)}>New reel</button></div></header>
  <main>
   <div className="intro"><div><span className="eyebrow">YOUR PRODUCTS. YOUR WORDS.</span><h1>Speak it. Cut it. <em>Sell it.</em></h1><p>Turn product photos into a reel, just by saying what you have in mind.</p></div><div className="format-tag"><Film size={18}/><span>Made for social<br/><strong>9:16 · Vertical MP4</strong></span></div></div>
   <div className="workspace">
    <section className="editor" aria-label="Reel editor">
     <div className="section-heading"><div><h2>Your media</h2><p>Add 3–5 photos. We’ll bring them to life.</p></div><span className="count">{photos.length}/5 photos</span></div>
     <input ref={upload} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" multiple aria-label="Upload product photos" onChange={e=>{void filesSelected(Array.from(e.target.files??[]));e.target.value=''}}/>
     <div className={`photo-area ${photos.length?'filled':''}`} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();void filesSelected(Array.from(e.dataTransfer.files))}}>
      {photos.length?<div className="photo-grid">{photos.map((asset,i)=><div className="photo" key={asset.id}><img src={`/api/projects/${project!.id}/assets/${asset.id}`} alt={asset.filename}/><span>{i+1}</span><button aria-label={`Remove ${asset.filename}`} disabled={busy} onClick={()=>void remove(asset.id)}><X size={14}/></button></div>)}{photos.length<5&&<button className="add-photo" disabled={busy} onClick={()=>upload.current?.click()} aria-label="Add more photos"><ImagePlus size={24}/></button>}</div>:<button className="dropzone" disabled={busy||!project} onClick={()=>upload.current?.click()}><div className="upload-symbol"><ImagePlus size={28}/></div><strong>Drop your product photos here</strong><span>or click to choose from your device</span><small>JPG, PNG or WebP · up to 15 MB each</small></button>}
     </div>
     <div className="music-row"><Music2 size={16}/><span>{project?.assets.find(a=>a.media_type==='audio')?.filename??'Original demo music included'}</span>{project?.assets.some(a=>a.media_type==='audio')?<button className="text-button" disabled={busy} onClick={()=>void remove(project.assets.find(a=>a.media_type==='audio')!.id)}>Remove</button>:<button className="text-button" disabled={busy||!project} onClick={()=>music.current?.click()}>Use my music</button>}<input className="sr-only" ref={music} type="file" accept="audio/mpeg,audio/wav,audio/mp4,audio/ogg" aria-label="Upload background music" onChange={e=>{void filesSelected(Array.from(e.target.files??[]),true);e.target.value=''}}/></div>
     <div className="voice-section"><div className="section-heading"><div><span className="eyebrow">VOICE DIRECTOR</span><h2>{project?.current_output?'What would you change?':'What should we create?'}</h2></div><div className="select-wrap"><select aria-label="Speech language" value={language} disabled={busy} onChange={e=>setLanguage(e.target.value)}><option value="">Auto language</option><option value="ta">Tamil / Tanglish</option><option value="en">English</option></select><ChevronDown size={14}/></div></div>
      <VoiceButton disabled={busy||photos.length<3||caps?.speech.status!=='ready'} onAudio={(b,e)=>void handleAudio(b,e)} onError={setError}/>
      <div className="status" role="status">{busy?<LoaderCircle className="spin" size={15}/>:<span className="status-dot"/>}{stage}{photos.length<3&&!busy?' · Add at least 3 photos to begin':''}</div>
      {caps&&caps.speech.status!=='ready'&&<div className="notice">{caps.speech.status==='loading'?'Loading the local speech model…':caps.speech.error}</div>}
      {caps&&!caps.renderer.available&&<div className="notice">The media renderer is unavailable. Check the server setup before creating a reel.</div>}
      <div className="try-saying"><span>TRY SAYING</span><p>{project?.current_output?'“Offer ah 25 percent nu maathu. Background music konjam kammi pannu.”':'“Indha photos use panni 15 seconds reel create pannu. Smooth zoom, music, last la 20 percent offer podu.”'}</p><small>{project?.current_output?'Change the offer to 25 percent and lower the music.':'Use these photos for a 15-second reel, with zoom, music and an offer.'}</small></div>
     </div>
     {error&&<div className="error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={17}/></button></div>}
     {parsed&&<div className="interpretation"><span className="eyebrow">{parsed.requires_clarification?'LET’S CLARIFY':'I UNDERSTOOD'}</span><blockquote>{parsed.original_transcript}</blockquote>{parsed.requires_clarification?<p>{parsed.clarification_question}</p>:<div className="operation-list">{parsed.operations.map(op=><span key={op.id}><Check size={14}/>{operationLabel(op)}</span>)}</div>}{parsed.warnings.map(w=><p key={w} className="muted">{w}</p>)}</div>}
    </section>
    <aside className="preview-panel"><div className="section-heading"><h2>Your reel</h2><span className="preview-label">{project?.current_output?'READY TO PLAY':'PREVIEW'}</span></div><div className="video-frame">{project?.current_output?<video key={project.current_render_revision} controls playsInline src={`/api/projects/${project.id}/video?revision=${project.current_render_revision}`} aria-label="Rendered reel preview"/>:<div className="empty-preview"><div className="preview-art"><div/><div/><div><Sparkles size={32}/></div></div><h3>A little story.<br/>A big first impression.</h3><p>Your finished reel will appear here.</p><span>720 × 1280 · MP4</span></div>}{busy&&jobId&&<div className="render-cover"><LoaderCircle className="spin" size={32}/><strong>{stage}</strong><span>Making your photos move.</span></div>}</div><div className="preview-meta"><span>{project?.settings.duration_seconds??15} seconds</span><span>30 fps · 9:16</span></div><div className="preview-actions"><button className="undo" disabled={busy||!project?.undo_stack.length} onClick={()=>void undo()}><Undo2 size={17}/>Undo</button><a className={`download ${busy||!project?.current_output?'disabled':''}`} aria-disabled={busy||!project?.current_output} href={!busy&&project?.current_output?`/api/projects/${project.id}/download`:undefined} download><Download size={17}/>Download MP4</a></div><div className="local-note"><ShieldCheck size={18}/><p>Processed by this SolliCut server.<br/>No cloud AI API needed.</p></div></aside>
   </div>
   <footer><span>Every business has a story.</span><span>Tamil · Tanglish · English</span><span>Livelihoods & small business</span></footer>
  </main>
  {resetting&&<div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title"><Trash2 size={26}/><h2 id="reset-title">Start a fresh reel?</h2><p>This deletes this project’s photos, recordings and rendered videos from the server. Download your reel first if you want to keep it.</p><div><button className="quiet" onClick={()=>setResetting(false)}>Keep editing</button><button className="danger" disabled={busy} onClick={()=>void reset()}>Delete and start fresh</button></div></div></div>}
 </div>
}
