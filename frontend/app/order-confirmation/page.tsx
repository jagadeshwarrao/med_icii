'use client';

import {Suspense,useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import CustomerEmpty from '../../components/CustomerEmpty';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';

function ConfirmationStatus(){
 const [result,setResult]=useState<any>(null),[notice,setNotice]=useState(''),reconcileAttempted=useRef(false);
 const sessionId=typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('session_id');
 useEffect(()=>{
  if(!sessionId){setNotice('Your payment confirmation link is missing. You can review your order status in My Orders.');return}
  const token=sessionStorage.getItem('medicii_access_token')||'';
  let active=true;
  const load=async()=>{try{const r=await fetch(api+'/orders/confirmation?session_id='+encodeURIComponent(sessionId),{headers:{Authorization:'Bearer '+token}});if(!active)return;if(!r.ok){setNotice('We could not load this order confirmation. Please check My Orders.');return}let confirmation=await r.json();if(confirmation.status==='PAYMENT_PENDING'&&!reconcileAttempted.current){reconcileAttempted.current=true;const verified=await fetch(api+'/orders/confirmation/reconcile?session_id='+encodeURIComponent(sessionId),{method:'POST',headers:{Authorization:'Bearer '+token}});if(verified.ok)confirmation=await verified.json();}if(active)setResult(confirmation);}catch{if(active)setNotice('We could not load this order confirmation. Please check My Orders.')}};
  load(); const timer=setInterval(load,4000); return()=>{active=false;clearInterval(timer)};
 },[sessionId]);
 if(!result)return <CustomerEmpty title="Order confirmation"><p className="eyebrow">PAYMENT UPDATE</p><h2>{notice||'Confirming your payment…'}</h2><p>{notice?'':'This page refreshes automatically while Medicii receives Stripe’s verified payment confirmation.'}</p><p><Link href="/orders">View My Orders →</Link></p></CustomerEmpty>;
 const confirmed=result.status==='CONFIRMED'||result.status==='PAID';
 return <CustomerEmpty title="Order confirmation"><p className="eyebrow">{confirmed?'PAYMENT CONFIRMED':'PAYMENT PROCESSING'}</p><h2>{confirmed?'Thank you for your order.':'Your payment is being confirmed.'}</h2><p>{confirmed?`Order ${result.number} is confirmed. We sent your confirmation email and will send future fulfillment updates.`:`Stripe has returned you to Medicii. We are waiting for its verified webhook before confirming order ${result.number}. This page refreshes automatically.`}</p><p><Link href="/orders">View My Orders →</Link></p></CustomerEmpty>;
}

export default function Confirmation(){return <Suspense fallback={<CustomerEmpty title="Order confirmation"><p>Loading payment confirmation…</p></CustomerEmpty>}><ConfirmationStatus/></Suspense>}
