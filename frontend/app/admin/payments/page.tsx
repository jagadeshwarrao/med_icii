'use client';

import {useEffect,useState} from 'react';
import AdminShell from '../../../components/AdminShell';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export default function Payments(){
 const [payments,setPayments]=useState<any[]|null>(null),[notice,setNotice]=useState(''); const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 async function load(){setNotice('');await fetch(api+'/admin/payments/sync',{method:'POST',headers:{Authorization:'Bearer '+token}});const r=await fetch(api+'/admin/payments',{headers:{Authorization:'Bearer '+token}});if(r.ok)setPayments(await r.json());else setNotice('Unable to load payment activity.')}
 useEffect(()=>{load()},[]);
 return <AdminShell title="Payments" description="Stripe payment records, verification state, and automatic order confirmation.">{!payments?<p>Loading payment activity…</p>:<><div className="admin-toolbar"><p>{payments.length} payment{payments.length===1?'':'s'} recorded.</p><button onClick={load}>Refresh payment status</button></div><div className="table payments-table"><div className="table-head"><span>Order</span><span>Customer</span><span>Payment</span><span>Order status</span><span>Created</span></div>{payments.map(p=><div className="table-row" key={p.id}><span><b>{p.order_number}</b><small>Session …{p.session_reference}</small></span><span><b>{p.customer.name}</b><small>{p.customer.email}</small></span><span><b>{p.currency} ${p.amount}</b><small>{p.status}</small></span><span className="badge">{p.order_status.replaceAll('_',' ')}</span><span>{new Date(p.created_at).toLocaleString()}</span></div>)}{!payments.length&&<p className="empty">No payment activity yet.</p>}</div>{notice&&<p className="notice">{notice}</p>}</>}</AdminShell>
}
