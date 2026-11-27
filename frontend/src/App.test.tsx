import {afterEach,expect,test,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import App,{validatePhotos} from './App'
import VoiceButton,{microphoneError} from './VoiceButton'
import {operationLabel} from './api'

afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear()})
test('photo formats and count are checked before uploading',()=>{
 expect(validatePhotos([new File(['data'],'x.exe',{type:'application/octet-stream'})],0)).toMatch('JPEG')
 expect(validatePhotos([new File(['data'],'x.png',{type:'image/png'})],5)).toMatch('5')
 expect(validatePhotos([new File(['data'],'x.png',{type:'image/png'})],0)).toBeNull()
})
test('permission and missing microphone errors are useful',()=>{
 expect(microphoneError(new DOMException('denied','NotAllowedError'))).toMatch('permission')
 expect(microphoneError(new DOMException('absent','NotFoundError'))).toMatch('No microphone')
})
test('operation cards display extracted fields',()=>{
 expect(operationLabel({id:'x',type:'set_text_overlay',parameters:{text:'25 percent offer',placement:'end_card'}})).toBe('“25 percent offer” · at the end')
 expect(operationLabel({id:'y',type:'set_music_volume',parameters:{direction:'decrease'}})).toBe('Softer background music')
})
test('microphone permission rejection reaches visible error handler',async()=>{
 Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:vi.fn().mockRejectedValue(new DOMException('denied','NotAllowedError'))}})
 vi.stubGlobal('MediaRecorder',{isTypeSupported:()=>true})
 const error=vi.fn()
 render(<VoiceButton disabled={false} onAudio={vi.fn()} onError={error}/>);
 fireEvent.click(screen.getByRole('button',{name:'Start recording'}))
 await waitFor(()=>expect(error).toHaveBeenCalledWith(expect.stringContaining('permission was denied')))
})
function mockServer(output:string|null=null){
 vi.stubGlobal('fetch',vi.fn(async(input:string)=>({ok:true,json:async()=>String(input).includes('capabilities')?{renderer:{available:true},speech:{status:'ready',error:null}}:{id:'project',assets:[],current_output:output,current_render_revision:1,settings:{duration_seconds:15},undo_stack:output?[{}]:[]}})))
}
test('empty screen has upload and disabled download',async()=>{
 mockServer();render(<App/>);
 await screen.findByText('Drop your product photos here')
 expect(screen.getByLabelText('Upload product photos')).toBeInTheDocument()
 expect(screen.getByText('Download MP4').closest('a')).toHaveAttribute('aria-disabled','true')
 expect(screen.getByRole('button',{name:'Undo'})).toBeDisabled()
})
test('completed reel displays video, undo and download',async()=>{
 mockServer('renders/revision-1.mp4');render(<App/>);
 await screen.findByLabelText('Rendered reel preview')
 expect(screen.getByRole('button',{name:'Undo'})).not.toBeDisabled()
 expect(screen.getByText('Download MP4').closest('a')).toHaveAttribute('href','/api/projects/project/download')
})
