import {useEffect,useRef,useState} from 'react'
import {Mic,Square} from 'lucide-react'

export function microphoneError(error:unknown):string{
 const name=error&&typeof error==='object'&&'name' in error?String(error.name):''
 if(name==='NotAllowedError')return 'Microphone permission was denied. Allow microphone access in your browser and try again.'
 if(name==='NotFoundError')return 'No microphone found. Connect a microphone and try again.'
 if(name==='NotReadableError')return 'Your microphone is busy or disconnected. Check it and try again.'
 return error instanceof Error?error.message:'Recording was interrupted. Please try again.'
}

export default function VoiceButton({disabled,onAudio,onError}:{disabled:boolean;onAudio:(blob:Blob,extension:string)=>void;onError:(message:string)=>void}){
 const [recording,setRecording]=useState(false),[seconds,setSeconds]=useState(0)
 const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),timer=useRef<ReturnType<typeof setInterval>|null>(null)
 const alive=useRef(true)
 function cleanup(){if(timer.current)clearInterval(timer.current);stream.current?.getTracks().forEach(t=>t.stop());stream.current=null}
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;if(recorder.current?.state==='recording')recorder.current.stop();cleanup()}},[])
 async function start(){
  try{
   if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined')throw new Error('This browser cannot record audio. Use a current browser on localhost or HTTPS.')
   const type=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus','audio/webm'].find(t=>MediaRecorder.isTypeSupported(t))
   if(!type)throw new Error('No supported microphone recording format. Try Chrome, Edge, Firefox or Safari.')
   stream.current=await navigator.mediaDevices.getUserMedia({audio:true})
   if(!alive.current){cleanup();return}
   const chunks:BlobPart[]=[]
   const r=new MediaRecorder(stream.current,{mimeType:type});recorder.current=r
   let interrupted=false
   r.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)}
   r.onerror=()=>{interrupted=true;onError('Recording was interrupted. Please record again.');cleanup();setRecording(false)}
   stream.current.getAudioTracks()[0].onended=()=>{if(r.state==='recording'){interrupted=true;r.stop();onError('The microphone disconnected. Please record again.')}}
   r.onstop=()=>{
    cleanup();if(!alive.current)return;setRecording(false)
    if(interrupted)return
    const blob=new Blob(chunks,{type:r.mimeType})
    if(!blob.size){onError('The recording is empty. Please try again.');return}
    onAudio(blob,type.includes('mp4')?'mp4':type.includes('ogg')?'ogg':'webm')
   }
   r.start(250);setRecording(true);setSeconds(0)
   const began=Date.now()
   timer.current=setInterval(()=>{const elapsed=Math.floor((Date.now()-began)/1000);setSeconds(elapsed);if(elapsed>=29&&r.state==='recording')r.stop()},200)
  }catch(error){cleanup();setRecording(false);onError(microphoneError(error))}
 }
 return <div className="voice-control"><button className={`mic-button ${recording?'recording':''}`} disabled={disabled&&!recording} onClick={()=>recording?recorder.current?.stop():void start()} aria-label={recording?'Stop recording':'Start recording'}>{recording?<Square size={26} fill="currentColor"/>:<Mic size={28}/>}</button><div><strong>{recording?`Listening · ${seconds}s`:'Tap to speak'}</strong><span>{recording?'Tap again when you’re done':'Tamil, Tanglish or English · up to 30 seconds'}</span></div>{recording&&<div className="sound-bars" aria-hidden="true">{[1,2,3,4,5].map(i=><i key={i}/>)}</div>}</div>
}
