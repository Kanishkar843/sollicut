export type Asset = {id:string;filename:string;media_type:'image'|'video'|'audio'}
export type Operation = {id:string;type:string;parameters:Record<string,unknown>}
export type Project = {id:string;assets:Asset[];current_output:string|null;current_render_revision:number;undo_stack:unknown[];settings:{duration_seconds:number}}
export type Parsed = {original_transcript:string;operations:Operation[];requires_clarification:boolean;clarification_question:string|null;warnings:string[]}
export type Command = {parsed_command:Parsed;job_id?:string;project?:Project;download_url?:string;transcript?:string}
export type Capabilities = {renderer:{available:boolean};speech:{status:string;error:string|null}}
export async function api<T>(path:string,init?:RequestInit):Promise<T>{
 const response=await fetch(`/api${path}`,init)
 if(!response.ok){const error=await response.json().catch(()=>({detail:'The server could not complete this request.'}));throw new Error(typeof error.detail==='string'?error.detail:'Please check the submitted file and try again.')}
 return response.json()
}
export function operationLabel(op:Operation):string{
 const p=op.parameters
 switch(op.type){
 case 'create_reel':return `${p.duration_seconds}-second vertical reel · all photos`
 case 'set_duration':return `${p.duration_seconds}-second reel`
 case 'set_zoom_style':return p.style==='smooth'?'Smooth photo zoom':'Zoom off'
 case 'set_music':return p.enabled?'Background music on':'Music off'
 case 'set_music_volume':return p.direction==='decrease'?'Softer background music':'Louder background music'
 case 'set_text_overlay':return `“${p.text}” · ${p.placement==='end_card'?'at the end':'on the reel'}`
 case 'set_aspect_ratio':return 'Vertical 9:16 format'
 case 'set_brightness':return Number(p.value)>0?'Brighter photos':'Darker photos'
 case 'undo':return 'Restore the previous edit'
 case 'export':return 'Download your MP4'
 default:return op.type
 }
}
