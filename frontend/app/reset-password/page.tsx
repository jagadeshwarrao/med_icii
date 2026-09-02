'use client';

import {Suspense, useState} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';

function ResetPasswordForm(){
 const params=useSearchParams(),token=params.get('token')||'',[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[notice,setNotice]=useState(''),[saving,setSaving]=useState(false);
 async function submit(e:React.FormEvent){
  e.preventDefault();
  if(!token){setNotice('This password-reset link is missing its token. Request a new link.');return}
  if(password!==confirm){setNotice('The passwords do not match.');return}
  setSaving(true);setNotice('');
  try{const r=await fetch(api+'/auth/reset-password',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({token,password})});const x=await r.json();setNotice(r.ok?x.message:(x.detail||'Unable to reset password.'));}
  catch{setNotice('Unable to reach Medicii. Please try again.');}
  finally{setSaving(false)}
 }
 return <main className="auth"><Link href="/login">← Back to sign in</Link><section className="panel"><p className="eyebrow">ACCOUNT RECOVERY</p><h1>Choose a new password</h1><p>Use at least 12 characters. This link can be used once and expires after 30 minutes.</p><form onSubmit={submit}><input required minLength={12} type="password" placeholder="New password" value={password} onChange={e=>setPassword(e.target.value)}/><input required minLength={12} type="password" placeholder="Confirm new password" value={confirm} onChange={e=>setConfirm(e.target.value)}/><button disabled={saving}>{saving?'Updating…':'Update password'}</button></form>{notice&&<p className="notice">{notice}</p>}<p><Link href="/login">Return to sign in</Link></p></section></main>
}
export default function ResetPassword(){return <Suspense fallback={<main className="auth"><section className="panel"><p>Loading secure reset link…</p></section></main>}><ResetPasswordForm/></Suspense>}
