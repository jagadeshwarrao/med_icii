import os, hashlib, uuid, secrets
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .database import Base, engine, db_session
from .models import User, QuoteRequest, Quote, QuoteGroup, QuoteGroupRequest, QuoteGroupQuote, Order, OrderItem, Document, Payment, WebhookEvent, PasswordResetToken
from .security import hash_password, verify_password, token_for, current_user, role, audit
from .services import email, storage

app=FastAPI(title='Medicii API', version='1.0.0')
USER_AGREEMENT_VERSION='2026-09-02'
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:3000').split(','),allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def start():
 Base.metadata.create_all(engine)
 db=next(db_session())
 production=os.getenv('ENVIRONMENT','development').lower()=='production'
 demo_admin=db.scalar(select(User).where(User.email=='admin@medicii.example.com'))
 if not production and not demo_admin:
  db.add(User(email='admin@medicii.example.com',full_name='Medicii Operations',password_hash=hash_password('ChangeMe123!'),role='ADMIN',verified_at=datetime.utcnow()))
 if production and demo_admin:
  demo_admin.password_hash=hash_password(secrets.token_urlsafe(48)); demo_admin.role='DISABLED'
 bootstrap_email=os.getenv('INITIAL_ADMIN_EMAIL','').strip().lower()
 bootstrap_password=os.getenv('INITIAL_ADMIN_PASSWORD','')
 if production and bootstrap_email and len(bootstrap_password)>=12:
  bootstrap_admin=db.scalar(select(User).where(User.email==bootstrap_email))
  if not bootstrap_admin:
   db.add(User(email=bootstrap_email,full_name='Medicii Operations',password_hash=hash_password(bootstrap_password),role='ADMIN',verified_at=datetime.utcnow()))
  elif bootstrap_admin.role!='ADMIN':
   bootstrap_admin.role='ADMIN'
 db.commit()
class Register(BaseModel): full_name:str; email:EmailStr; password:str=Field(min_length=12); agreement_accepted:bool=False
class Login(BaseModel): email:EmailStr; password:str
class ForgotPassword(BaseModel): email:EmailStr
class ResetPassword(BaseModel): token:str=Field(min_length=20,max_length=512); password:str=Field(min_length=12,max_length=256)
class RequestQuote(BaseModel): medicine:str; strength:str; form:str; quantity:int=Field(gt=0); notes:str|None=None; draft_order_id:str|None=None
class BatchRequestItem(BaseModel): medicine:str=Field(min_length=1); strength:str=Field(min_length=1); form:str=Field(min_length=1); quantity:int=Field(gt=0); notes:str|None=None
class BatchRequest(BaseModel): items:list[BatchRequestItem]=Field(min_length=1,max_length=20)
class GroupPriceItem(BaseModel): request_id:str; medicine_price:Decimal=Field(ge=0)
class ReviewGroup(BaseModel): items:list[GroupPriceItem]=Field(min_length=1); shipping:Decimal=0; service_fee:Decimal=0; expires_at:datetime
class AdminCustomerUpdate(BaseModel): full_name:str=Field(min_length=1,max_length=160)
class AdminOrderUpdate(BaseModel): status:str
class ProfileAddress(BaseModel): line1:str=Field(min_length=1,max_length=240); city:str=Field(min_length=1,max_length=120); state:str=Field(min_length=1,max_length=120); postal_code:str=Field(min_length=1,max_length=32); country:str=Field(min_length=2,max_length=80)
class ProfileUpdate(BaseModel): full_name:str=Field(min_length=1,max_length=160); phone:str|None=Field(default=None,max_length=40); address:ProfileAddress|None=None
class CreateQuote(BaseModel): request_id:str; medicine_price:Decimal=Field(ge=0); shipping:Decimal=0; service_fee:Decimal=0; expires_at:datetime
class Address(BaseModel): full_name:str=Field(min_length=1,max_length=160); phone:str=Field(min_length=5,max_length=40); line1:str=Field(min_length=1,max_length=240); city:str=Field(min_length=1,max_length=120); state:str=Field(min_length=1,max_length=120); postal_code:str=Field(min_length=1,max_length=32); country:str=Field(min_length=2,max_length=80)
def number(db,prefix,model): return f'{prefix}{(db.scalar(select(func.count()).select_from(model)) or 0)+10001}'
def owned_order(db, oid, user):
 o=db.get(Order,oid)
 if not o or (o.user_id!=user.id and user.role not in ('ADMIN','PHARMACY')): raise HTTPException(404,'Order not found')
 return o
def transition(current,target,edges):
 if target not in edges.get(current,set()): raise HTTPException(409,f'Invalid transition {current} → {target}')
def operations_recipients():
 recipients=set()
 for name in ('ORDERS_EMAIL','OPERATIONS_EMAIL','ADMIN_NOTIFICATION_EMAIL'):
  recipients.update(address.strip().lower() for address in os.getenv(name,'').split(',') if address.strip())
 return recipients
def notify_operations(template,details):
 for recipient in operations_recipients(): email.send(recipient,template,details)
def payment_email_details(db,order,payment):
 customer=db.get(User,order.user_id); items=list(db.scalars(select(OrderItem).where(OrderItem.order_id==order.id)))
 return {'order_number':order.number,'customer_name':customer.full_name,'customer_email':customer.email,'shipping_address':order.address,'items':[{'medicine':i.medicine,'quantity':i.quantity,'price':str(i.medicine_price_snapshot),'shipping':str(i.shipping_snapshot),'service_fee':str(i.service_fee_snapshot)} for i in items],'total':str(payment.amount)}
def confirm_paid_order(db,order,payment,actor=None):
 if order.status=='CONFIRMED' and payment.status=='PAID': return False
 payment.status='PAID'; order.status='CONFIRMED'; audit(db,actor,'PAYMENT_CONFIRMED','order',order.id); db.commit()
 details=payment_email_details(db,order,payment); email.send(details['customer_email'],'order-confirmed',details); notify_operations('new-order-confirmed',details)
 return True
def paid_stripe_session(payment,order):
 stripe_key=os.getenv('STRIPE_SECRET_KEY')
 if not stripe_key: return None
 try:
  import stripe; stripe.api_key=stripe_key; checkout_session=stripe.checkout.Session.retrieve(payment.stripe_session_id)
  if checkout_session.payment_status=='paid' and checkout_session.status=='complete' and checkout_session.amount_total==int(payment.amount*100) and checkout_session.currency==payment.currency and checkout_session.metadata.get('order_id')==order.id: return checkout_session
 except Exception: return None
 return None
def sync_pending_payments(db):
 confirmed=[]
 for payment in db.scalars(select(Payment).where(Payment.status=='PENDING')).all():
  order=db.get(Order,payment.order_id)
  if not order or order.status not in ('PAYMENT_PENDING','READY_FOR_PAYMENT'): continue
  checkout_session=paid_stripe_session(payment,order)
  if checkout_session:
   payment.stripe_payment_intent_id=str(checkout_session.payment_intent or '') or None
   if confirm_paid_order(db,order,payment): confirmed.append(order.number)
 return confirmed

@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/api/v1/auth/register')
def register(data:Register,db:Session=Depends(db_session)):
 if db.scalar(select(User).where(User.email==data.email.lower())): raise HTTPException(409,'Email already registered')
 if not data.agreement_accepted: raise HTTPException(422,'You must accept the Medicii User Agreement to create an account.')
 u=User(email=data.email.lower(),full_name=data.full_name,password_hash=hash_password(data.password),agreement_version=USER_AGREEMENT_VERSION,agreement_accepted_at=datetime.utcnow()); db.add(u); db.flush(); audit(db,u,'AUTH_REGISTER','user',u.id,metadata={'agreement_version':USER_AGREEMENT_VERSION}); db.commit(); email.send(u.email,'verify-account',{}); return {'message':'Account created. Verify email through the configured transactional email provider.'}
@app.post('/api/v1/auth/login')
def login(data:Login,db:Session=Depends(db_session)):
 u=db.scalar(select(User).where(User.email==data.email.lower()))
 if not u or u.role not in ('CUSTOMER','ADMIN','PHARMACY') or not verify_password(data.password,u.password_hash): audit(db,u,'AUTH_LOGIN','user',getattr(u,'id','unknown'),False); db.commit(); raise HTTPException(401,'Invalid credentials')
 audit(db,u,'AUTH_LOGIN','user',u.id); db.commit(); return {'access_token':token_for(u),'role':u.role,'user':{'name':u.full_name,'email':u.email}}
@app.post('/api/v1/auth/forgot-password')
def forgot_password(data:ForgotPassword,db:Session=Depends(db_session)):
 generic={'message':'If an account exists for that email, we sent a password-reset link.'}
 user=db.scalar(select(User).where(User.email==data.email.lower()))
 if not user: return generic
 now=datetime.utcnow()
 for existing in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id==user.id,PasswordResetToken.used_at.is_(None))).all(): existing.used_at=now
 raw_token=secrets.token_urlsafe(32)
 db.add(PasswordResetToken(user_id=user.id,token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),expires_at=now+timedelta(minutes=30)))
 audit(db,user,'PASSWORD_RESET_REQUESTED','user',user.id)
 db.commit()
 reset_url=f"{os.getenv('APP_URL','http://localhost:3000').rstrip('/')}/reset-password?token={raw_token}"
 email.send(user.email,'password-reset',{'reset_url':reset_url})
 return generic
@app.post('/api/v1/auth/reset-password')
def reset_password(data:ResetPassword,db:Session=Depends(db_session)):
 now=datetime.utcnow(); token_hash=hashlib.sha256(data.token.encode()).hexdigest()
 reset=db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash==token_hash,PasswordResetToken.used_at.is_(None)))
 if not reset or reset.expires_at<now: raise HTTPException(400,'This password-reset link is invalid or has expired. Request a new link.')
 user=db.get(User,reset.user_id)
 if not user: raise HTTPException(400,'This password-reset link is invalid or has expired. Request a new link.')
 reset.used_at=now
 for existing in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id==user.id,PasswordResetToken.used_at.is_(None))).all(): existing.used_at=now
 user.password_hash=hash_password(data.password)
 audit(db,user,'PASSWORD_RESET_COMPLETED','user',user.id)
 db.commit()
 return {'message':'Password updated. You can now sign in.'}
@app.get('/api/v1/profile')
def profile(user=Depends(current_user)):
 return {'id':user.id,'full_name':user.full_name,'email':user.email,'phone':user.phone,'address':user.address,'role':user.role,'created_at':user.created_at,'verified':bool(user.verified_at)}
@app.put('/api/v1/profile')
def update_profile(data:ProfileUpdate,user=Depends(current_user),db:Session=Depends(db_session)):
 user.full_name=data.full_name; user.phone=data.phone.strip() if data.phone and data.phone.strip() else None; user.address=data.address.model_dump() if data.address else None; audit(db,user,'PROFILE_UPDATED','user',user.id); db.commit(); email.send(user.email,'account-updated',{}); return {'full_name':user.full_name,'phone':user.phone,'address':user.address}
@app.get('/api/v1/dashboard')
def dashboard(user=Depends(current_user),db:Session=Depends(db_session)):
 return {'quotes':db.scalar(select(func.count()).select_from(QuoteGroup).where(QuoteGroup.user_id==user.id)),'ready_quotes':db.scalar(select(func.count()).select_from(QuoteGroup).where(QuoteGroup.user_id==user.id,QuoteGroup.status=='REVIEWED')),'cart':cart(db,user),'orders':db.scalar(select(func.count()).select_from(Order).where(Order.user_id==user.id,Order.status!='DRAFT'))}
@app.get('/api/v1/orders/confirmation')
def order_confirmation(session_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 order=db.scalar(select(Order).where(Order.user_id==user.id,Order.checkout_session_id==session_id))
 if not order: raise HTTPException(404,'Order confirmation was not found')
 payment=db.scalar(select(Payment).where(Payment.order_id==order.id))
 return {'id':order.id,'number':order.number,'status':order.status,'payment_status':getattr(payment,'status',None)}
@app.post('/api/v1/orders/confirmation/reconcile')
def reconcile_order_confirmation(session_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 order=db.scalar(select(Order).where(Order.user_id==user.id,Order.checkout_session_id==session_id))
 if not order: raise HTTPException(404,'Order confirmation was not found')
 payment=db.scalar(select(Payment).where(Payment.order_id==order.id))
 if not payment: raise HTTPException(404,'Payment record was not found')
 if order.status=='CONFIRMED' and payment.status=='PAID': return {'id':order.id,'number':order.number,'status':order.status,'payment_status':payment.status,'confirmed':True}
 checkout_session=paid_stripe_session(payment,order)
 if not checkout_session: raise HTTPException(409,'Stripe has not verified this payment yet')
 payment.stripe_payment_intent_id=str(checkout_session.payment_intent or '') or None
 confirm_paid_order(db,order,payment,user)
 return {'id':order.id,'number':order.number,'status':order.status,'payment_status':payment.status,'confirmed':True}
@app.post('/api/v1/quotes/requests')
def request_quote(data:RequestQuote,user=Depends(current_user),db:Session=Depends(db_session)):
 q=QuoteRequest(number=number(db,'QR',QuoteRequest),user_id=user.id,**data.model_dump()); db.add(q); db.flush(); audit(db,user,'QUOTE_REQUEST_CREATED','quote_request',q.id); db.commit(); return {'id':q.id,'number':q.number,'status':q.status}
@app.post('/api/v1/quotes/requests/batch')
def request_quote_batch(data:BatchRequest,user=Depends(current_user),db:Session=Depends(db_session)):
 group=QuoteGroup(number=number(db,'QRG',QuoteGroup),user_id=user.id); db.add(group); db.flush(); created=[]
 for item in data.items:
  q=QuoteRequest(number=number(db,'QR',QuoteRequest),user_id=user.id,**item.model_dump())
  db.add(q); db.flush(); db.add(QuoteGroupRequest(group_id=group.id,request_id=q.id)); audit(db,user,'QUOTE_REQUEST_CREATED','quote_request',q.id,metadata={'group_id':group.id}); created.append({'id':q.id,'number':q.number})
 db.commit(); email.send(user.email,'quote-request-received',{'quote_number':group.number})
 notify_operations('new-quote-request',{'quote_number':group.number,'customer_name':user.full_name,'customer_email':user.email,'items':[{'medicine':item.medicine,'strength':item.strength,'form':item.form,'quantity':item.quantity,'notes':item.notes or ''} for item in data.items]})
 return {'group_id':group.id,'number':group.number,'items':created,'status':group.status}
def group_requests(db, group_id):
 ids=db.scalars(select(QuoteGroupRequest.request_id).where(QuoteGroupRequest.group_id==group_id)).all(); return list(db.scalars(select(QuoteRequest).where(QuoteRequest.id.in_(ids)))) if ids else []
@app.get('/api/v1/admin/quote-request-groups')
def quote_request_groups(user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 groups=db.scalars(select(QuoteGroup).where(QuoteGroup.status=='PENDING_REVIEW').order_by(QuoteGroup.created_at.desc())).all()
 return [{'id':g.id,'number':g.number,'status':g.status,'items':[{'request_id':r.id,'medicine':r.medicine,'strength':r.strength,'form':r.form,'quantity':r.quantity} for r in group_requests(db,g.id)]} for g in groups]
@app.post('/api/v1/admin/quote-request-groups/{group_id}/review')
def review_quote_group(group_id:str,data:ReviewGroup,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.status!='PENDING_REVIEW': raise HTTPException(404,'Quote request group not found')
 requests={r.id:r for r in group_requests(db,g.id)}
 if set(requests)!=set(x.request_id for x in data.items): raise HTTPException(422,'Prices must be supplied for every medicine in the group')
 for index,price in enumerate(data.items):
  r=requests[price.request_id]; r.status='DRAFT'; q=Quote(number=number(db,'Q',Quote),request_id=r.id,user_id=g.user_id,status='SENT',medicine_price=price.medicine_price,shipping=data.shipping if index==0 else 0,service_fee=data.service_fee if index==0 else 0,expires_at=data.expires_at); db.add(q); db.flush(); db.add(QuoteGroupQuote(group_id=g.id,quote_id=q.id)); audit(db,user,'QUOTE_SENT','quote',q.id)
 g.status='REVIEWED'; audit(db,user,'QUOTE_GROUP_REVIEWED','quote_group',g.id); db.commit()
 customer=db.get(User,g.user_id); total=sum((x.medicine_price for x in data.items),Decimal('0'))+data.shipping+data.service_fee
 email.send(customer.email,'quote-reviewed',{'quote_number':g.number,'total':str(total)})
 return {'id':g.id,'number':g.number,'status':g.status}
@app.get('/api/v1/admin/reviewed-quotes')
def reviewed_quotes(user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 groups=db.scalars(select(QuoteGroup).where(QuoteGroup.status.in_(('REVIEWED','ACCEPTED'))).order_by(QuoteGroup.created_at.desc())).all(); result=[]
 for g in groups:
  qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids)))) if qids else []
  customer=db.get(User,g.user_id); result.append({'id':g.id,'number':g.number,'status':g.status,'total':str(sum((q.medicine_price+q.shipping+q.service_fee for q in qs),Decimal('0'))),'items':len(qs),'customer':{'id':customer.id,'name':customer.full_name,'email':customer.email}})
 return result
@app.delete('/api/v1/admin/reviewed-quotes/{group_id}')
def delete_reviewed_quote(group_id:str,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.status not in ('REVIEWED','ACCEPTED'): raise HTTPException(404,'Reviewed quote not found')
 if g.status=='ACCEPTED': raise HTTPException(409,'Accepted quotes cannot be deleted because they are part of an order cart')
 mappings=list(db.scalars(select(QuoteGroupQuote).where(QuoteGroupQuote.group_id==g.id)))
 for mapping in mappings:
  db.delete(mapping)
 db.flush()
 for mapping in mappings:
  q=db.get(Quote,mapping.quote_id)
  if q: db.delete(q)
 db.flush()
 for mapping in db.scalars(select(QuoteGroupRequest).where(QuoteGroupRequest.group_id==g.id)):
  db.delete(mapping)
 db.flush()
 customer=db.get(User,g.user_id); quote_number=g.number; audit(db,user,'QUOTE_GROUP_DELETED','quote_group',g.id); db.delete(g); db.commit(); email.send(customer.email,'quote-withdrawn',{'quote_number':quote_number}); return {'deleted':True}
@app.get('/api/v1/admin/reviewed-quotes/{group_id}')
def reviewed_quote_detail(group_id:str,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.status!='REVIEWED': raise HTTPException(404,'Reviewed quote not found')
 qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids))))
 return {'id':g.id,'number':g.number,'items':[{'request_id':q.request_id,'medicine':db.get(QuoteRequest,q.request_id).medicine,'medicine_price':str(q.medicine_price)} for q in qs],'shipping':str(sum((q.shipping for q in qs),Decimal('0'))),'service_fee':str(sum((q.service_fee for q in qs),Decimal('0')))}
@app.put('/api/v1/admin/reviewed-quotes/{group_id}')
def update_reviewed_quote(group_id:str,data:ReviewGroup,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.status!='REVIEWED': raise HTTPException(404,'Reviewed quote not found')
 qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids)))); by_request={q.request_id:q for q in qs}
 if set(by_request)!=set(x.request_id for x in data.items): raise HTTPException(422,'All quote medicines must be priced')
 for index,item in enumerate(data.items):
  q=by_request[item.request_id]; q.medicine_price=item.medicine_price; q.shipping=data.shipping if index==0 else 0; q.service_fee=data.service_fee if index==0 else 0; q.expires_at=data.expires_at
 audit(db,user,'QUOTE_GROUP_UPDATED','quote_group',g.id); db.commit(); customer=db.get(User,g.user_id); total=sum((x.medicine_price for x in data.items),Decimal('0'))+data.shipping+data.service_fee; email.send(customer.email,'quote-reviewed',{'quote_number':g.number,'total':str(total)}); return {'updated':True}
@app.get('/api/v1/quotes')
def quotes(user=Depends(current_user),db:Session=Depends(db_session)):
 if user.role=='CUSTOMER':
  groups=db.scalars(select(QuoteGroup).where(QuoteGroup.user_id==user.id).order_by(QuoteGroup.created_at.desc())).all(); out=[]
  for g in groups:
   qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids)))) if qids else []
   out.append({'id':g.id,'number':g.number,'status':g.status,'total':str(sum((q.medicine_price+q.shipping+q.service_fee for q in qs),Decimal('0'))),'expires_at':min((q.expires_at for q in qs),default=None),'items':len(qs)})
  return out
 stmt=select(Quote)
 return [{'id':q.id,'number':q.number,'request_id':q.request_id,'status':q.status,'total':str(q.medicine_price+q.shipping+q.service_fee),'expires_at':q.expires_at} for q in db.scalars(stmt.order_by(Quote.created_at.desc()))]
@app.get('/api/v1/admin/quote-requests')
def quote_requests(user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 return [{'id':x.id,'number':x.number,'medicine':x.medicine,'strength':x.strength,'form':x.form,'quantity':x.quantity,'status':x.status} for x in db.scalars(select(QuoteRequest).order_by(QuoteRequest.created_at.desc()))]
@app.get('/api/v1/admin/customers')
def customers(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 return [{'id':u.id,'full_name':u.full_name,'email':u.email,'created_at':u.created_at} for u in db.scalars(select(User).where(User.role=='CUSTOMER').order_by(User.created_at.desc()))]
@app.get('/api/v1/admin/customers/{customer_id}')
def customer_detail(customer_id:str,user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 customer=db.get(User,customer_id)
 if not customer or customer.role!='CUSTOMER': raise HTTPException(404,'Customer not found')
 groups=db.scalars(select(QuoteGroup).where(QuoteGroup.user_id==customer.id).order_by(QuoteGroup.created_at.desc())).all(); orders=db.scalars(select(Order).where(Order.user_id==customer.id).order_by(Order.created_at.desc())).all()
 return {'id':customer.id,'full_name':customer.full_name,'email':customer.email,'created_at':customer.created_at,'quotes':[{'id':g.id,'number':g.number,'status':g.status} for g in groups],'orders':[{'id':o.id,'number':o.number,'status':o.status,'created_at':o.created_at} for o in orders]}
@app.put('/api/v1/admin/customers/{customer_id}')
def update_customer(customer_id:str,data:AdminCustomerUpdate,user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 customer=db.get(User,customer_id)
 if not customer or customer.role!='CUSTOMER': raise HTTPException(404,'Customer not found')
 customer.full_name=data.full_name; audit(db,user,'CUSTOMER_UPDATED','user',customer.id); db.commit(); email.send(customer.email,'account-updated',{}); return {'id':customer.id,'full_name':customer.full_name}
@app.delete('/api/v1/admin/customers/{customer_id}')
def delete_customer(customer_id:str,user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 customer=db.get(User,customer_id)
 if not customer or customer.role!='CUSTOMER': raise HTTPException(404,'Customer not found')
 if db.scalar(select(func.count()).select_from(Order).where(Order.user_id==customer.id)) or db.scalar(select(func.count()).select_from(QuoteGroup).where(QuoteGroup.user_id==customer.id)):
  raise HTTPException(409,'Customer with quote or order history cannot be deleted')
 audit(db,user,'CUSTOMER_DELETED','user',customer.id); db.delete(customer); db.commit(); return {'deleted':True}
@app.get('/api/v1/admin/orders')
def admin_orders(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 sync_pending_payments(db)
 out=[]
 for o in db.scalars(select(Order).order_by(Order.created_at.desc())):
  customer=db.get(User,o.user_id); items=list(db.scalars(select(OrderItem).where(OrderItem.order_id==o.id))); total=sum((x.medicine_price_snapshot+x.shipping_snapshot+x.service_fee_snapshot for x in items),Decimal('0'))
  out.append({'id':o.id,'number':o.number,'status':o.status,'customer':{'id':customer.id,'name':customer.full_name,'email':customer.email},'items':len(items),'total':str(total),'created_at':o.created_at})
 return out
@app.post('/api/v1/admin/payments/sync')
def sync_admin_payments(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 return {'confirmed_orders':sync_pending_payments(db)}
@app.get('/api/v1/admin/payments')
def admin_payments(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 sync_pending_payments(db); out=[]
 for payment in db.scalars(select(Payment).order_by(Payment.created_at.desc())):
  order=db.get(Order,payment.order_id); customer=db.get(User,order.user_id) if order else None
  out.append({'id':payment.id,'order_number':getattr(order,'number','Removed order'),'order_status':getattr(order,'status','UNKNOWN'),'customer':{'name':getattr(customer,'full_name','Unknown'),'email':getattr(customer,'email','')},'amount':str(payment.amount),'currency':payment.currency.upper(),'status':payment.status,'session_reference':payment.stripe_session_id[-14:],'created_at':payment.created_at})
 return out
@app.get('/api/v1/admin/documents')
def admin_documents(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 out=[]
 for document in db.scalars(select(Document).order_by(Document.created_at.desc())):
  order=db.get(Order,document.order_id); customer=db.get(User,document.user_id)
  out.append({'id':document.id,'kind':document.kind,'status':document.status,'order_number':getattr(order,'number','Removed order'),'customer':{'name':getattr(customer,'full_name','Unknown'),'email':getattr(customer,'email','')},'created_at':document.created_at})
 return out
@app.get('/api/v1/admin/audit-events')
def admin_audit_events(user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 out=[]
 for event in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)):
  actor=db.get(User,event.actor_id) if event.actor_id else None
  out.append({'id':event.id,'event_type':event.event_type,'entity_type':event.entity_type,'entity_id':event.entity_id,'success':event.success,'actor':{'name':getattr(actor,'full_name','System'),'email':getattr(actor,'email','')},'metadata':event.metadata_ or {},'created_at':event.created_at})
 return out
@app.put('/api/v1/admin/orders/{order_id}')
def update_order(order_id:str,data:AdminOrderUpdate,user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 o=db.get(Order,order_id)
 if not o: raise HTTPException(404,'Order not found')
 allowed={'PROCESSING','SHIPPED','DELIVERED','CANCELLED'}
 if data.status not in allowed: raise HTTPException(422,'Invalid order status')
 o.status=data.status; audit(db,user,'ORDER_UPDATED','order',o.id,metadata={'status':data.status}); db.commit(); customer=db.get(User,o.user_id); email.send(customer.email,'order-status-updated',{'order_number':o.number,'status':o.status}); return {'id':o.id,'status':o.status}
@app.delete('/api/v1/admin/orders/{order_id}')
def delete_order(order_id:str,user=Depends(role('ADMIN')),db:Session=Depends(db_session)):
 o=db.get(Order,order_id)
 if not o: raise HTTPException(404,'Order not found')
 if o.status in ('PAID','CONFIRMED','PROCESSING','SHIPPED','DELIVERED'):
  raise HTTPException(409,'Paid or fulfilled orders cannot be deleted; cancel or refund them through the approved process')
 customer=db.get(User,o.user_id); order_number=o.number; items=list(db.scalars(select(OrderItem).where(OrderItem.order_id==o.id)))
 for item in items:
  quote=db.get(Quote,item.quote_id)
  if quote:
   quote.status='SENT'
   group_id=db.scalar(select(QuoteGroupQuote.group_id).where(QuoteGroupQuote.quote_id==quote.id))
   if group_id:
    group=db.get(QuoteGroup,group_id)
    if group: group.status='REVIEWED'
  db.delete(item)
 for document in db.scalars(select(Document).where(Document.order_id==o.id)): db.delete(document)
 for payment in db.scalars(select(Payment).where(Payment.order_id==o.id)): db.delete(payment)
 db.flush()
 audit(db,user,'ORDER_DELETED','order',o.id); db.delete(o); db.commit(); email.send(customer.email,'order-removed',{'order_number':order_number}); return {'deleted':True}
@app.post('/api/v1/admin/quotes')
def create_quote(data:CreateQuote,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 r=db.get(QuoteRequest,data.request_id)
 if not r: raise HTTPException(404,'Quote request not found')
 transition(r.status,'DRAFT',{'PENDING_REVIEW':{'DRAFT'},'PHARMACY_REVIEW':{'DRAFT'}}); r.status='DRAFT'
 q=Quote(number=number(db,'Q',Quote),user_id=r.user_id,**data.model_dump()); db.add(q); db.flush(); audit(db,user,'QUOTE_CREATED','quote',q.id); db.commit(); return {'id':q.id,'number':q.number}
@app.post('/api/v1/admin/quotes/{quote_id}/send')
def send_quote(quote_id:str,user=Depends(role('ADMIN','PHARMACY')),db:Session=Depends(db_session)):
 q=db.get(Quote,quote_id);
 if not q: raise HTTPException(404,'Quote not found')
 transition(q.status,'SENT',{'DRAFT':{'SENT'}}); q.status='SENT'; audit(db,user,'QUOTE_SENT','quote',q.id); db.commit(); return {'status':q.status}
@app.post('/api/v1/quotes/{quote_id}/accept')
def accept(quote_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 q=db.get(Quote,quote_id)
 if not q or q.user_id!=user.id: raise HTTPException(404,'Quote not found')
 if q.expires_at < datetime.utcnow(): q.status='EXPIRED'; db.commit(); raise HTTPException(409,'Quote has expired')
 transition(q.status,'ACCEPTED',{'SENT':{'ACCEPTED'},'VIEWED':{'ACCEPTED'}}); q.status='ACCEPTED'
 o=db.scalar(select(Order).where(Order.user_id==user.id,Order.status=='DRAFT'))
 if not o: o=Order(number=number(db,'ORD',Order),user_id=user.id); db.add(o); db.flush()
 if not db.scalar(select(OrderItem).where(OrderItem.quote_id==q.id)): 
  r=db.get(QuoteRequest,q.request_id); db.add(OrderItem(order_id=o.id,quote_id=q.id,medicine=r.medicine,quantity=r.quantity,medicine_price_snapshot=q.medicine_price,shipping_snapshot=q.shipping,service_fee_snapshot=q.service_fee))
 audit(db,user,'QUOTE_ACCEPTED','quote',q.id); db.commit(); return cart(db,user)
@app.get('/api/v1/quote-groups/{group_id}')
def quote_group(group_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.user_id!=user.id: raise HTTPException(404,'Quote not found')
 qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids)))) if qids else []; items=[]
 for q in qs:
  r=db.get(QuoteRequest,q.request_id); items.append({'medicine':r.medicine,'strength':r.strength,'form':r.form,'quantity':r.quantity,'total':str(q.medicine_price+q.shipping+q.service_fee)})
 return {'id':g.id,'number':g.number,'status':g.status,'items':items,'total':str(sum((q.medicine_price+q.shipping+q.service_fee for q in qs),Decimal('0'))),'expires_at':min((q.expires_at for q in qs),default=None)}
@app.post('/api/v1/quote-groups/{group_id}/accept')
def accept_group(group_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 g=db.get(QuoteGroup,group_id)
 if not g or g.user_id!=user.id: raise HTTPException(404,'Quote not found')
 if g.status=='ACCEPTED':
  qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all()
  item=db.scalar(select(OrderItem).where(OrderItem.quote_id.in_(qids))) if qids else None
  existing=db.get(Order,item.order_id) if item else None
  label=f'order {existing.number} ({existing.status.replace("_"," ").lower()})' if existing else 'an existing order'
  raise HTTPException(409,f'This quote is already in {label}. Open My Orders to continue or review its status.')
 if g.status!='REVIEWED': raise HTTPException(409,'Quote is not ready to add to cart')
 qids=db.scalars(select(QuoteGroupQuote.quote_id).where(QuoteGroupQuote.group_id==g.id)).all(); qs=list(db.scalars(select(Quote).where(Quote.id.in_(qids))))
 if not qs or any(q.expires_at<datetime.utcnow() for q in qs): raise HTTPException(409,'Quote has expired')
 o=db.scalar(select(Order).where(Order.user_id==user.id,Order.status=='DRAFT'))
 if not o: o=Order(number=number(db,'ORD',Order),user_id=user.id); db.add(o); db.flush()
 for q in qs:
  q.status='ACCEPTED'; r=db.get(QuoteRequest,q.request_id)
  if not db.scalar(select(OrderItem).where(OrderItem.quote_id==q.id)): db.add(OrderItem(order_id=o.id,quote_id=q.id,medicine=r.medicine,quantity=r.quantity,medicine_price_snapshot=q.medicine_price,shipping_snapshot=q.shipping,service_fee_snapshot=q.service_fee))
  audit(db,user,'QUOTE_ACCEPTED','quote',q.id)
 g.status='ACCEPTED'; audit(db,user,'QUOTE_GROUP_ACCEPTED','quote_group',g.id); db.commit(); email.send(user.email,'quote-accepted',{'quote_number':g.number,'order_number':o.number}); return cart(db,user)
def cart(db,user):
 # Keep the in-progress order visible at every checkout stage. Paid and fulfilled
 # orders belong in order history, not in the customer cart.
 o=db.scalar(select(Order).where(Order.user_id==user.id,Order.status.in_(('DRAFT','AWAITING_DOCUMENTS','READY_FOR_PAYMENT','PAYMENT_PENDING'))).order_by(Order.created_at.desc()))
 if not o:return {'order':None,'items':[],'medicine_subtotal':'0.00','shipping_total':'0.00','service_fee_total':'0.00','total':'0.00'}
 its=list(db.scalars(select(OrderItem).where(OrderItem.order_id==o.id))); medicine_subtotal=sum((i.medicine_price_snapshot for i in its),Decimal('0')); shipping_total=sum((i.shipping_snapshot for i in its),Decimal('0')); service_fee_total=sum((i.service_fee_snapshot for i in its),Decimal('0')); total=medicine_subtotal+shipping_total+service_fee_total
 return {'order':{'id':o.id,'number':o.number,'status':o.status},'items':[{'id':i.id,'medicine':i.medicine,'quantity':i.quantity,'medicine_price':str(i.medicine_price_snapshot)} for i in its],'medicine_subtotal':str(medicine_subtotal),'shipping_total':str(shipping_total),'service_fee_total':str(service_fee_total),'total':str(total)}
@app.get('/api/v1/cart')
def get_cart(user=Depends(current_user),db:Session=Depends(db_session)): return cart(db,user)
def order_summary(db,o):
 items=list(db.scalars(select(OrderItem).where(OrderItem.order_id==o.id)))
 medicine_subtotal=sum((i.medicine_price_snapshot for i in items),Decimal('0')); shipping_total=sum((i.shipping_snapshot for i in items),Decimal('0')); service_fee_total=sum((i.service_fee_snapshot for i in items),Decimal('0'))
 return {'id':o.id,'number':o.number,'status':o.status,'created_at':o.created_at,'items':[{'medicine':i.medicine,'quantity':i.quantity,'medicine_price':str(i.medicine_price_snapshot)} for i in items],'medicine_subtotal':str(medicine_subtotal),'shipping_total':str(shipping_total),'service_fee_total':str(service_fee_total),'total':str(medicine_subtotal+shipping_total+service_fee_total)}
@app.get('/api/v1/orders')
def customer_orders(user=Depends(current_user),db:Session=Depends(db_session)):
 sync_pending_payments(db)
 return [order_summary(db,o) for o in db.scalars(select(Order).where(Order.user_id==user.id).order_by(Order.created_at.desc()))]
@app.get('/api/v1/orders/{order_id}')
def customer_order_detail(order_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 o=owned_order(db,order_id,user); summary=order_summary(db,o)
 summary['address']=o.address
 summary['documents']=[{'kind':d.kind,'status':d.status,'created_at':d.created_at} for d in db.scalars(select(Document).where(Document.order_id==o.id).order_by(Document.created_at.desc()))]
 return summary
@app.get('/api/v1/orders/{order_id}/checkout-state')
def checkout_state(order_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 o=owned_order(db,order_id,user)
 return {'address':o.address,'documents':[d.kind for d in db.scalars(select(Document).where(Document.order_id==o.id))]}
@app.put('/api/v1/orders/{order_id}/address')
def address(order_id:str,data:Address,user=Depends(current_user),db:Session=Depends(db_session)):
 o=owned_order(db,order_id,user)
 if o.status not in ('DRAFT','AWAITING_DOCUMENTS','READY_FOR_PAYMENT'): raise HTTPException(409,'Order is no longer editable')
 o.address=data.model_dump(); o.status='READY_FOR_PAYMENT'; audit(db,user,'ORDER_ADDRESS_UPDATED','order',o.id); db.commit(); email.send(user.email,'delivery-updated',{'order_number':o.number}); return {'ok':True}
@app.post('/api/v1/orders/{order_id}/documents/{kind}')
async def document(order_id:str,kind:str,file:UploadFile=File(...),user=Depends(current_user),db:Session=Depends(db_session)):
 if kind not in ('PRESCRIPTION','GOVERNMENT_ID'): raise HTTPException(422,'Invalid document type')
 o=owned_order(db,order_id,user); blob=await file.read()
 if o.status not in ('DRAFT','AWAITING_DOCUMENTS','READY_FOR_PAYMENT'): raise HTTPException(409,'Order is no longer editable')
 if len(blob)>10*1024*1024 or file.content_type!='application/pdf' or not blob.startswith(b'%PDF-'): raise HTTPException(422,'Only PDF files up to 10 MB are accepted')
 # Storage abstraction: production adapter writes encrypted private S3 object after malware scan.
 key=storage.put_pdf(f'users/{user.id}/orders/{o.id}/documents/{uuid.uuid4()}.pdf',blob)
 for previous in db.scalars(select(Document).where(Document.order_id==o.id,Document.kind==kind)):
  db.delete(previous)
 d=Document(order_id=o.id,user_id=user.id,kind=kind,storage_key=key,checksum=hashlib.sha256(blob).hexdigest(),status='PENDING_SCAN'); db.add(d); db.flush(); o.status='AWAITING_DOCUMENTS'; audit(db,user,'DOCUMENT_UPLOADED','document',d.id); db.commit(); email.send(user.email,'documents-updated',{'order_number':o.number,'document_kind':kind}); return {'id':d.id,'status':d.status}
@app.post('/api/v1/orders/{order_id}/checkout')
def checkout(order_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
 o=owned_order(db,order_id,user); items=list(db.scalars(select(OrderItem).where(OrderItem.order_id==o.id))); docs=list(db.scalars(select(Document).where(Document.order_id==o.id)))
 if not items or not o.address or {d.kind for d in docs}!={'PRESCRIPTION','GOVERNMENT_ID'}: raise HTTPException(422,'Items, address, prescription, and government ID are required')
 # Prices and tax inputs are calculated server-side from immutable accepted-quote snapshots.
 total=sum((x.medicine_price_snapshot+x.shipping_snapshot+x.service_fee_snapshot for x in items),Decimal('0'))
 stripe_key=os.getenv('STRIPE_SECRET_KEY')
 if stripe_key:
  import stripe
  stripe.api_key=stripe_key
  line_items=[{'price_data':{'currency':'usd','product_data':{'name':item.medicine},'unit_amount':int((item.medicine_price_snapshot+item.shipping_snapshot+item.service_fee_snapshot)*100)},'quantity':1} for item in items]
  params={'mode':'payment','line_items':line_items,'success_url':f"{os.getenv('APP_URL','http://localhost:3000')}/order-confirmation?session_id={{CHECKOUT_SESSION_ID}}",'cancel_url':f"{os.getenv('APP_URL','http://localhost:3000')}/checkout",'customer_email':user.email,'metadata':{'order_id':o.id,'order_number':o.number},'payment_intent_data':{'metadata':{'order_id':o.id}}}
  if os.getenv('STRIPE_TAX_ENABLED','false').lower()=='true': params['automatic_tax']={'enabled':True}
  if os.getenv('STRIPE_INVOICE_CREATION_ENABLED','true').lower()=='true': params['invoice_creation']={'enabled':True}
  try: session=stripe.checkout.Session.create(**params)
  except stripe.StripeError: raise HTTPException(502,'Unable to create secure payment session')
  session_id=session.id; checkout_url=session.url
 else:
  # Development-only fallback. Never enable in production.
  if os.getenv('ENVIRONMENT')=='production': raise HTTPException(500,'Stripe is not configured')
  session_id='mock_cs_'+uuid.uuid4().hex; checkout_url=f"{os.getenv('APP_URL','http://localhost:3000')}/order-confirmation?session_id={session_id}"
 o.checkout_session_id=session_id; o.status='PAYMENT_PENDING'; db.add(Payment(order_id=o.id,stripe_session_id=session_id,amount=total,currency='usd',status='PENDING')); audit(db,user,'CHECKOUT_CREATED','order',o.id); db.commit()
 return {'checkout_url':checkout_url,'session_id':session_id}
@app.post('/api/v1/stripe/webhook')
async def webhook(request:Request, stripe_signature:str|None=Header(None),db:Session=Depends(db_session)):
 # In production verify Stripe signature with stripe.Webhook.construct_event before parsing.
 raw=await request.body()
 if os.getenv('STRIPE_WEBHOOK_SECRET'):
  import stripe
  try: data=stripe.Webhook.construct_event(raw,stripe_signature,os.environ['STRIPE_WEBHOOK_SECRET'])
  except Exception: raise HTTPException(400,'Invalid Stripe signature')
 else:
  # Mock-only local mode. Production requires STRIPE_WEBHOOK_SECRET.
  if os.getenv('ENVIRONMENT')=='production': raise HTTPException(500,'Stripe webhook secret is required')
  import json; data=json.loads(raw)
 eid=data.get('id'); obj=data.get('data',{}).get('object',{})
 if not eid or db.get(WebhookEvent,eid): return {'received':True,'duplicate':True}
 if data.get('type')!='checkout.session.completed' or obj.get('payment_status')!='paid': raise HTTPException(400,'Unsupported event')
 session=db.scalar(select(Payment).where(Payment.stripe_session_id==obj.get('id')))
 if not session or int(session.amount*100)!=obj.get('amount_total') or obj.get('currency')!=session.currency: raise HTTPException(400,'Payment verification failed')
 o=db.get(Order,session.order_id); db.add(WebhookEvent(id=eid))
 if o.status=='CONFIRMED' and session.status=='PAID': db.commit(); return {'received':True,'already_confirmed':True}
 session.stripe_payment_intent_id=str(obj.get('payment_intent') or '') or None
 confirm_paid_order(db,o,session)
 return {'received':True}
