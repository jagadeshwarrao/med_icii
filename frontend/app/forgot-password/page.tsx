'use client';

import {useState} from 'react';
import Link from 'next/link';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';

export default function Forgot(){
 const [email,setEmail]=useState(''),[notice,setNotice]=useState(''),[sending,setSending]=useState(false);
 async function submit(e:React.FormEvent){
  e.preventDefault(); setSending(true); setNotice('');
  try{const r=await fetch(api+'/auth/forgot-password',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email})});const x=await r.json();setNotice(r.ok?x.message:(x.detail||'Unable to send the reset link.'));}
  catch{setNotice('Unable to reach Medicii. Please try again.');}
  finally{setSending(false)}
 }
 return <main className="auth"><Link href="/login">← Back to sign in</Link><section className="panel"><p className="eyebrow">ACCOUNT RECOVERY</p><h1>Reset your password</h1><p>Enter your email and we’ll send a secure reset link if an account exists.</p><form onSubmit={submit}><input required type="email" placeholder="Email address" value={email} onChange={e=>setEmail(e.target.value)}/><button disabled={sending}>{sending?'Sending…':'Send reset link'}</button></form>{notice&&<p className="notice">{notice}</p>}</section></main>
}
