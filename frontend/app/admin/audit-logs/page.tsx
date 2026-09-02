'use client';

import {useEffect,useState} from 'react';
import AdminShell from '../../../components/AdminShell';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export default function AuditLogs(){
 const [events,setEvents]=useState<any[]|null>(null),[notice,setNotice]=useState('');const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 async function load(){const r=await fetch(api+'/admin/audit-events',{headers:{Authorization:'Bearer '+token}});if(r.ok)setEvents(await r.json());else setNotice('Unable to load audit logs.')}
 useEffect(()=>{load()},[]);
 return <AdminShell title="Audit logs" description="The 200 most recent security-relevant Medicii events.">{!events?<p>Loading audit events…</p>:<><div className="admin-toolbar"><p>{events.length} recent event{events.length===1?'':'s'}.</p><button onClick={load}>Refresh logs</button></div><div className="table audit-table"><div className="table-head"><span>Event</span><span>Actor</span><span>Record</span><span>Result</span><span>Time</span></div>{events.map(event=><div className="table-row" key={event.id}><span><b>{event.event_type.replaceAll('_',' ')}</b><small>{Object.keys(event.metadata).length?JSON.stringify(event.metadata):'No extra details'}</small></span><span><b>{event.actor.name}</b><small>{event.actor.email}</small></span><span>{event.entity_type.replaceAll('_',' ')}<small>{event.entity_id}</small></span><span className={event.success?'badge':'badge audit-failure'}>{event.success?'Success':'Failed'}</span><span>{new Date(event.created_at).toLocaleString()}</span></div>)}{!events.length&&<p className="empty">No audit events yet.</p>}</div>{notice&&<p className="notice">{notice}</p>}</>}</AdminShell>
}
