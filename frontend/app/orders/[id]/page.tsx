'use client';

import {useEffect,useState} from 'react';
import {useParams} from 'next/navigation';
import CustomerShell from '../../../components/CustomerShell';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export default function OrderDetails(){
 const {id}=useParams<{id:string}>(),[order,setOrder]=useState<any>(null),[error,setError]=useState('');const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 useEffect(()=>{fetch(api+'/orders/'+id,{headers:{Authorization:'Bearer '+token}}).then(async r=>r.ok?setOrder(await r.json()):setError('This order could not be found.'))},[id,token]);
 return <CustomerShell title="Order details">{error?<section className="empty-card"><h2>{error}</h2></section>:!order?<p>Loading your order…</p>:<section className="panel checkout-card"><p className="eyebrow">{order.number}</p><h2>{order.status.replaceAll('_',' ')}</h2><div className="medicine-summary">{order.items.map((item:any,index:number)=><p key={index}><b>{item.medicine} × {item.quantity}</b><strong>${item.medicine_price}</strong></p>)}</div><div className="order-fees"><p>Medicine subtotal <strong>${order.medicine_subtotal}</strong></p><p>Shipping <strong>${order.shipping_total}</strong></p><p>Service fee <strong>${order.service_fee_total}</strong></p></div><hr/><h2>Order total: ${order.total}</h2>{order.address&&<section className="order-address"><p className="eyebrow">DELIVERY ADDRESS</p><p><b>{order.address.full_name}</b><br/>{order.address.line1}<br/>{order.address.city}, {order.address.state} {order.address.postal_code}<br/>{order.address.country}<br/>{order.address.phone}</p></section>}<section className="order-documents"><p className="eyebrow">DOCUMENTS</p>{order.documents.length?<p>{order.documents.map((document:any)=>`${document.kind.replaceAll('_',' ')}: ${document.status.replaceAll('_',' ')}`).join(' · ')}</p>:<p>No documents have been uploaded for this order.</p>}</section></section>}</CustomerShell>
}
