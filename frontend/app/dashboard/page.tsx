'use client';
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import CustomerShell from '../../components/CustomerShell';
const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
type Summary={quotes:number;ready_quotes:number;orders:number;cart:{items:unknown[];total:string}};
export default function Dashboard(){
 const router=useRouter(); const [data,setData]=useState<Summary|null>(null);
 const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 useEffect(()=>{if(!token){router.replace('/');return;} fetch(api+'/dashboard',{headers:{Authorization:'Bearer '+token}}).then(r=>r.ok?r.json():Promise.reject()).then(setData).catch(()=>router.replace('/'));},[token,router]);
 function logout(){sessionStorage.removeItem('medicii_access_token');router.replace('/');}
 if(!data)return <main className="loading">Loading your Medicii dashboard…</main>;
 return <CustomerShell title="Dashboard"><section className="dashboard"><div><p className="eyebrow">YOUR DASHBOARD</p><h2>Care, <em>on your terms.</em></h2><p className="lead">Request a medicine quote, review a ready quote, and keep accepted medicines in one order cart.</p><Link className="button-link dashboard-cta" href="/quotes/request">Request a quote →</Link></div><aside className="panel"><h2>Order cart</h2><p>{data.cart.items.length?`${data.cart.items.length} medicine(s) ready for checkout.`:'Your cart is empty. Accept a quote to add it here.'}</p><strong>${data.cart.total}</strong></aside></section><section className="stats"><article><b>{data.quotes}</b><span>Quote requests</span></article><article><b>{data.ready_quotes}</b><span>Ready to review</span></article><article><b>{data.orders}</b><span>Orders in progress</span></article></section></CustomerShell>;
}
