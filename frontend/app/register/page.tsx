'use client';

import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
export default function Register(){
 const router=useRouter(),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[accepted,setAccepted]=useState(false),[notice,setNotice]=useState('');
 async function submit(e:React.FormEvent){e.preventDefault();const r=await fetch(api+'/auth/register',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({full_name:name,email,password,agreement_accepted:accepted})});const x=await r.json();if(r.ok){router.push('/login')}else setNotice(typeof x.detail==='string'?x.detail:'Please use a valid email address and a 12-character password.')}
 return <main className="auth"><Link href="/">← Back to Medicii</Link><section className="panel"><p className="eyebrow">GET STARTED</p><h1>Create your account</h1><form onSubmit={submit}><input required placeholder="Full name" value={name} onChange={e=>setName(e.target.value)}/><input required type="email" placeholder="Email address" value={email} onChange={e=>setEmail(e.target.value)}/><input required type="password" minLength={12} placeholder="Password (12+ characters)" value={password} onChange={e=>setPassword(e.target.value)}/><label className="agreement-check"><input required type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/><span>I have read and agree to the <Link href="/user-agreement" target="_blank">Medicii User Agreement</Link>.</span></label><button disabled={!accepted}>Create account →</button></form><small>Already registered? <Link href="/login">Sign in</Link></small>{notice&&<p className="notice">{notice}</p>}</section></main>
}
