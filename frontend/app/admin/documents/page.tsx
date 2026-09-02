'use client';

import {useEffect,useState} from 'react';
import AdminShell from '../../../components/AdminShell';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export default function Documents(){
 const [documents,setDocuments]=useState<any[]|null>(null),[notice,setNotice]=useState('');const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 async function load(){const r=await fetch(api+'/admin/documents',{headers:{Authorization:'Bearer '+token}});if(r.ok)setDocuments(await r.json());else setNotice('Unable to load document records.')}
 useEffect(()=>{load()},[]);
 return <AdminShell title="Documents" description="Private document records associated with customer orders. File contents are not exposed in this view.">{!documents?<p>Loading document records…</p>:<><div className="admin-toolbar"><p>{documents.length} document{documents.length===1?'':'s'} recorded.</p><button onClick={load}>Refresh records</button></div><div className="table"><div className="table-head"><span>Order</span><span>Customer</span><span>Document</span><span>Received</span></div>{documents.map(document=><div className="table-row" key={document.id}><span><b>{document.order_number}</b></span><span><b>{document.customer.name}</b><small>{document.customer.email}</small></span><span><b>{document.kind.replaceAll('_',' ')}</b><small>{document.status.replaceAll('_',' ')}</small></span><span>{new Date(document.created_at).toLocaleString()}</span></div>)}{!documents.length&&<p className="empty">No documents have been uploaded yet.</p>}</div>{notice&&<p className="notice">{notice}</p>}</>}</AdminShell>
}
