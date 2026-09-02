'use client';

import {useEffect,useState} from 'react';
import CustomerShell from '../../components/CustomerShell';

const api=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api/v1';
const emptyAddress={line1:'',city:'',state:'',postal_code:'',country:''};

export default function Profile(){
 const [profile,setProfile]=useState<any>(null),[editing,setEditing]=useState(false),[name,setName]=useState(''),[phone,setPhone]=useState(''),[address,setAddress]=useState(emptyAddress),[notice,setNotice]=useState('');
 const token=typeof window==='undefined'?'':sessionStorage.getItem('medicii_access_token');
 async function load(){const r=await fetch(api+'/profile',{headers:{Authorization:'Bearer '+token}});if(r.ok){const x=await r.json();setProfile(x);setName(x.full_name||'');setPhone(x.phone||'');setAddress({...emptyAddress,...(x.address||{})})}}
 useEffect(()=>{load()},[]);
 function edit(){setNotice('');setEditing(true)}
 function cancel(){setNotice('');setEditing(false);if(profile){setName(profile.full_name||'');setPhone(profile.phone||'');setAddress({...emptyAddress,...(profile.address||{})})}}
 async function save(e:React.FormEvent){e.preventDefault();const r=await fetch(api+'/profile',{method:'PUT',headers:{'content-type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({full_name:name,phone,address})});const x=await r.json();if(r.ok){setNotice('Profile updated.');setEditing(false);load()}else setNotice(x.detail||'Unable to update profile.')}
 const changeAddress=(key:string,value:string)=>setAddress(old=>({...old,[key]:value}));
 return <CustomerShell title="Profile">{!profile?<p>Loading your profile…</p>:<section className="panel form-card profile-card"><div className="profile-heading"><div><p className="eyebrow">YOUR ACCOUNT</p><h2>Personal details</h2></div>{!editing&&<button type="button" className="ghost" onClick={edit}>Edit profile</button>}</div><form onSubmit={save}><label>Full name<input required disabled={!editing} value={name} onChange={e=>setName(e.target.value)}/></label><label className="email-label">Email address <span className="info-icon" title="Contact support to change your email address." aria-label="Contact support to change your email address">ⓘ</span><input value={profile.email} disabled/></label><label>Phone number<input disabled={!editing} value={phone} onChange={e=>setPhone(e.target.value)} placeholder="Phone number"/></label><fieldset disabled={!editing}><legend>Saved address</legend><label>Address line<input required={editing} value={address.line1} onChange={e=>changeAddress('line1',e.target.value)} placeholder="Street address, apartment or suite"/></label><div className="address-grid"><label>City<input required={editing} value={address.city} onChange={e=>changeAddress('city',e.target.value)}/></label><label>State / province<input required={editing} value={address.state} onChange={e=>changeAddress('state',e.target.value)}/></label><label>Postal code<input required={editing} value={address.postal_code} onChange={e=>changeAddress('postal_code',e.target.value)}/></label><label>Country<input required={editing} value={address.country} onChange={e=>changeAddress('country',e.target.value)}/></label></div></fieldset><p>Member since {new Date(profile.created_at).toLocaleDateString()}</p>{editing&&<div className="profile-actions"><button type="button" className="ghost" onClick={cancel}>Cancel</button><button>Save changes</button></div>}</form>{notice&&<p className="notice">{notice}</p>}</section>}</CustomerShell>
}
